#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from pathlib import Path


BLEND_MAP = {
	"0": "none",
	"1": "add",
	"2": "sub",
	"3": "mul",
	"4": "screen",
	"5": "overlay",
	"6": "light",
	"7": "dark",
	"8": "brightness",
	"9": "chroma",
}


UNSUPPORTED_APIS = (
	"obj.putpixel",
	"obj.copypixel",
	"obj.getpixeldata",
	"obj.putpixeldata",
	"obj.filter",
)


def read_text_with_fallback(path: Path) -> tuple[str, str]:
	"""Read file as text with encoding fallback. Returns (text, encoding)."""
	data = path.read_bytes()
	for enc in ("cp932", "shift_jis", "utf-8", "utf-8-sig"):
		try:
			return data.decode(enc), enc
		except UnicodeDecodeError:
			continue
	# Last resort
	return data.decode("latin-1"), "latin-1"


def map_ext_to_v2(ext: str) -> str:
	"""Map old script extension to v2 extension."""
	ext = ext.lower()
	if ext in (".anm", ".obj", ".cam", ".scn", ".tra"):
		return ext + "2"
	return ext


def replace_blend_numbers(line: str, report: dict) -> str:
	# obj.setoption("blend", <num>[, "force"]) -> string name
	pattern = re.compile(r"obj\.setoption\(\s*([\'\"])blend\1\s*,\s*(\d+)\s*(,\s*([\'\"])force\4\s*)?\)")

	def _sub(m: re.Match) -> str:
		num = m.group(2)
		mapped = BLEND_MAP.get(num)
		if not mapped:
			return m.group(0)
		report["blend_converted"] = report.get("blend_converted", 0) + 1
		force_part = m.group(3) or ""
		return f"obj.setoption(\"blend\", \"{mapped}\"{force_part})"

	return pattern.sub(_sub, line)


def replace_buffer_tokens_in_context(line: str, report: dict) -> str:
	# Only in specific API contexts to avoid altering other strings
	if not ("obj.copybuffer" in line or "obj.pixeloption" in line or "obj.setoption" in line):
		return line

	def _map_token(tok: str) -> str:
		if tok == "obj":
			return "object"
		if tok == "tmp":
			return "tempbuffer"
		if tok == "frm":
			return "framebuffer"
		return tok

	def _sub(m: re.Match) -> str:
		q = m.group(1)
		val = m.group(2)
		new_val = _map_token(val)
		if new_val != val:
			report["buffer_tokens_replaced"] = report.get("buffer_tokens_replaced", 0) + 1
		return f"{q}{new_val}{q}"

	# Replace only whole-string tokens "obj"/"tmp"/"frm"
	return re.sub(r"([\'\"])\b(obj|tmp|frm)\b\1", _sub, line)


def remove_movie_alpha_flag(line: str, report: dict) -> str:
	# Simplistic line-based: obj.load("movie", file[, time], flag) -> drop last arg if present
	if "obj.load" not in line or "\"movie\"" not in line and "'movie'" not in line:
		return line

	# Pattern: obj.load("movie", a[, b], c)
	pattern = re.compile(
		r"obj\.load\(\s*([\'\"])movie\1\s*,\s*([^,\)]+)\s*,\s*([^,\)]+)\s*,\s*([^\)]+)\)")

	def _sub(m: re.Match) -> str:
		report["movie_flag_removed"] = report.get("movie_flag_removed", 0) + 1
		file_part = m.group(2).strip()
		time_part = m.group(3).strip()
		return f"obj.load(\"movie\", {file_part}, {time_part})"

	return pattern.sub(_sub, line)


def annotate_unsupported_apis(line: str, report: dict) -> str:
	for token in UNSUPPORTED_APIS:
		if token in line:
			report["unsupported_calls"] = report.get("unsupported_calls", 0) + 1
			# Keep original call, append TODO comment
			if "[A2_TODO]" not in line:
				return line.rstrip("\n") + " -- [A2_TODO] AviUtl2 unsupported; migrate to pixelshader/computeshader\n"
			break
	return line


def convert_text(text: str, report: dict) -> str:
	lines = text.splitlines(keepends=True)
	out_lines: list[str] = []
	for line in lines:
		orig = line
		line = replace_blend_numbers(line, report)
		line = remove_movie_alpha_flag(line, report)
		line = replace_buffer_tokens_in_context(line, report)
		line = annotate_unsupported_apis(line, report)
		out_lines.append(line)
	converted = "".join(out_lines)

	# Replace heavy obj.putpixel loops with a pixel shader invocation when possible
	converted2, replaced = replace_putpixel_loops_with_shader(converted, report)
	if replaced:
		report["putpixel_loop_replaced"] = replaced
		# Inject shader block if missing
		if "pixelshader@ps_puyopuyo_map" not in converted2:
			shader_block = (
				"--[[pixelshader@ps_puyopuyo_map:\n"
				"cbuffer constant0 : register(b0) {\n"
				"    float MS; float Cx; float Cy; float Rot; float Rb; float ALL; float _pad0; float _pad1;\n"
				"    float dA[256];\n"
				"};\n"
				"float4 ps_puyopuyo_map(float4 pos : SV_Position) : SV_Target {\n"
				"    float i = pos.x;\n"
				"    float j = pos.y;\n"
				"    float x = i - Cx;\n"
				"    float y = j - Cy;\n"
				"    float fai = atan2(y, x);\n"
				"    float r = 127.5 * sqrt(x*x + y*y) / Rb;\n"
				"    float th = frac((fai / 3.14159265 + 1.0) * 0.5 - Rot / 360.0) * ALL;\n"
				"    int th1 = (int)floor(th);\n"
				"    float th2 = th - th1;\n"
				"    float da = dA[th1];\n"
				"    if (th2 > 0.0) da = lerp(dA[th1], dA[th1+1], th2);\n"
				"    r *= da;\n"
				"    float rr = 127.5 - r * cos(fai);\n"
				"    float gg = 127.5 - r * sin(fai);\n"
				"    return float4(rr/255.0, gg/255.0, 0.0, 1.0);\n"
				"}\n"
				"]]\n\n"
			)
			converted2 = shader_block + converted2
	else:
		converted2 = converted

	# Batch drawpoly loops to a single obj.drawpoly({table}) call where possible
	converted3, batched = batch_drawpoly_calls(converted2, report)
	if batched:
		report["drawpoly_batched_loops"] = batched

	# Ensure draw after loading from tempbuffer when no explicit draw exists
	converted4, injected = ensure_draw_after_tempbuffer_load(converted3, report)
	if injected:
		report["inserted_draw_after_tempbuffer_load"] = injected

	# Ensure sampler clamp after switching to tempbuffer to reduce seams/flicker
	converted5, sampler_injected = ensure_sampler_clamp_with_tempbuffer_target(converted4, report)
	if sampler_injected:
		report["inserted_sampler_clamp"] = sampler_injected

	# Force blend to 'none' while drawing into tempbuffer segments (mode 6 default)
	converted6, forced_blend = force_tempbuffer_blend_none(converted5, report)
	if forced_blend:
		report["forced_tempbuffer_blend_none"] = forced_blend

	return converted6


def replace_putpixel_loops_with_shader(text: str, report: dict) -> tuple[str, int]:
	"""
	Detects nested i/j loops writing with obj.putpixel and replaces them with a pixelshader call.
	Assumes variables MS, Cx, Cy, Rot, Rb, ALL, dA[] are prepared in the script as in Puyo example.
	"""
	if "obj.putpixel" not in text:
		return text, 0

	lines = text.splitlines(keepends=False)
	replaced_count = 0
	i = 0
	while i < len(lines):
		if "obj.putpixel(" in lines[i]:
			# find outer for i loop start
			start = None
			for k in range(i, -1, -1):
				if re.search(r"^\s*for\s+i\s*=\s*0\s*,\s*MS-1\s*do\s*$", lines[k]):
					start = k
					break
			if start is None:
				i += 1
				continue

			# robustly find end of the outer 'for i' by tracking a simple block stack of 'for'/'if'
			stack: list[str] = []
			end_idx = None
			for k in range(start, len(lines)):
				linek = lines[k]
				if re.search(r"^\s*for\s+\w+\s*=.*do\s*$", linek):
					stack.append("for")
				elif re.search(r"^\s*if\b.*then\s*$", linek):
					stack.append("if")
				elif re.match(r"^\s*end\s*$", linek):
					if stack:
						stack.pop()
						if not stack:
							end_idx = k
							break
			if end_idx is None:
				i += 1
				continue

			indent_match = re.match(r"^(\s*)", lines[start])
			indent = indent_match.group(1) if indent_match else "\t"
			replacement = [
				f"{indent}local constants = {{MS, Cx, Cy, Rot, Rb, ALL}}",
				f"{indent}for i=0,ALL do table.insert(constants, dA[i]) end",
				f"{indent}obj.pixelshader(\"ps_puyopuyo_map\",\"object\",nil,constants,\"copy\")",
			]

			lines = lines[:start] + replacement + lines[end_idx+1:]
			replaced_count += 1
			i = start + len(replacement)
			continue
		i += 1

	new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
	# remove stale TODO comments related to putpixel if replaced
	if replaced_count:
		new_text = re.sub(r"\s*--\s*\[A2_TODO\].*putpixel.*\n", "\n", new_text)
	return (new_text, replaced_count)


def batch_drawpoly_calls(text: str, report: dict) -> tuple[str, int]:
	"""
	Optimizes patterns that call obj.drawpoly repeatedly via a helper like drawpolyT.
	- Rewrites drawpolyT to push vertices into global table 'vertex' with table.insert(vertex, {..}).
	- For each 'for i=0,N do ... end' block that calls drawpolyT(...), insert 'vertex = {}' before the loop
	  and 'obj.drawpoly(vertex)' after the loop.
	Returns (new_text, number_of_loops_batched)
	"""
	lines = text.splitlines(keepends=False)
	# 1) Rewrite drawpolyT bodies: obj.drawpoly(...) -> table.insert(vertex, {...})
	inside_drawpolyT = False
	inside_return_func = False
	for idx, ln in enumerate(lines):
		st = ln.strip()
		if not inside_drawpolyT and st.startswith("local drawpolyT=(function()"):
			inside_drawpolyT = True
			continue
		if inside_drawpolyT:
			# end of the drawpolyT factory
			if ")()" in st and st.endswith(")()") and st.startswith("end") or st.endswith("end)()"):
				inside_drawpolyT = False
				inside_return_func = False
				continue
			# detect function body head to inject epsilon UV adjust vars
			mret = re.search(r"^(\s*)return\s+function\(.*v0\s*,\s*v1\)\s*$", ln)
			if mret:
				indent = mret.group(1) + ("\t" if "\t" in ln[:len(mret.group(1))+1] else "\t")
				inject = f"{indent}local eps=0.5; local v0e=v0+eps; local v1e=v1-eps; local vce=(v0e+v1e)/2"
				lines.insert(idx+1, inject)
				inside_return_func = True
				continue
			if "obj.drawpoly(" in st and not st.startswith("--"):
				m = re.match(r"^(\s*)obj\.drawpoly\((.*)\)\s*$", ln)
				if m:
					indent, args = m.group(1), m.group(2)
					# prefer adjusted UV aliases if they exist
					args2 = re.sub(r"(?<![\w])vc(?![\w])", "vce", args)
					args2 = re.sub(r"(?<![\w])v0(?![\w])", "v0e", args2)
					args2 = re.sub(r"(?<![\w])v1(?![\w])", "v1e", args2)
					lines[idx] = f"{indent}table.insert(vertex, {{{args2}}})"

	# 2) Find loops 'for i=0,N do' containing drawpolyT( and wrap with vertex init and batched draw call
	batched_loops = 0
	i = 0
	while i < len(lines):
		m_for = re.match(r"^(\s*)for\s+i\s*=\s*0\s*,\s*N\s*do\s*$", lines[i])
		if not m_for:
			i += 1
			continue
		indent = m_for.group(1)
		# scan block to matching end
		stack: list[str] = []
		end_idx = None
		contains_drawpolyT = False
		for k in range(i, len(lines)):
			lk = lines[k]
			if re.search(r"^\s*for\s+\w+\s*=.*do\s*$", lk):
				stack.append("for")
			elif re.search(r"^\s*if\b.*then\s*$", lk):
				stack.append("if")
			elif re.match(r"^\s*end\s*$", lk):
				if stack:
					stack.pop()
					if not stack:
						end_idx = k
						break
			if "drawpolyT(" in lk:
				contains_drawpolyT = True
		# Not a proper block
		if end_idx is None or not contains_drawpolyT:
			i += 1
			continue
		# insert vertex = {} before loop if not present immediately
		ins_before = f"{indent}vertex = {{}}"
		lines.insert(i, ins_before)
		end_idx += 1  # shift due to inserted line
		# insert obj.drawpoly(vertex) after loop
		ins_after = f"{indent}obj.drawpoly(vertex)"
		lines.insert(end_idx + 1, ins_after)
		batched_loops += 1
		# move index after the inserted after-line
		i = end_idx + 2

	
	new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
	return new_text, batched_loops


def ensure_draw_after_tempbuffer_load(text: str, report: dict) -> tuple[str, int]:
	lines = text.splitlines(keepends=False)
	injected = 0
	i = 0
	while i < len(lines):
		if re.search(r"obj\.load\(\s*([\'\"])tempbuffer\1\s*\)", lines[i]):
			# look ahead to end of current block or next 'end'/'else'
			has_draw = False
			for k in range(i+1, min(i+12, len(lines))):
				if re.search(r"obj\.draw\(\)", lines[k]):
					has_draw = True
					break
				if re.match(r"^\s*end\b|^\s*else\b", lines[k]):
					break
			if not has_draw:
				indent = re.match(r"^(\s*)", lines[i]).group(1) if re.match(r"^(\s*)", lines[i]) else "\t"
				lines.insert(i+1, f"{indent}obj.draw()")
				injected += 1
				i += 1
		i += 1
	return ("\n".join(lines) + ("\n" if text.endswith("\n") else ""), injected)


def ensure_sampler_clamp_with_tempbuffer_target(text: str, report: dict) -> tuple[str, int]:
	lines = text.splitlines(keepends=False)
	injected = 0
	i = 0
	while i < len(lines):
		m = re.search(r"obj\.setoption\(\s*([\'\"])drawtarget\1\s*,\s*([\'\"])tempbuffer\2", lines[i])
		if m:
			# if the next few lines don't set sampler, inject clamp
			has_sampler = False
			for k in range(i+1, min(i+6, len(lines))):
				if re.search(r"obj\.setoption\(\s*([\'\"])sampler\1\s*,", lines[k]):
					has_sampler = True
					break
			if not has_sampler:
				indent = re.match(r"^(\s*)", lines[i]).group(1) if re.match(r"^(\s*)", lines[i]) else "\t"
				lines.insert(i+1, f"{indent}obj.setoption(\"sampler\",\"clamp\")")
				injected += 1
				i += 1
		i += 1
	return ("\n".join(lines) + ("\n" if text.endswith("\n") else ""), injected)


def adjust_blend_for_tempbuffer_draw(text: str, report: dict) -> tuple[str, int]:
	lines = text.splitlines(keepends=False)
	changed = 0
	i = 0
	while i < len(lines):
		if re.search(r"obj\.setoption\(\s*([\'\"])drawtarget\1\s*,\s*([\'\"])tempbuffer\2", lines[i]):
			# search ahead for a blend setting and upcoming draw/drawpoly before target switch
			blend_idx = None
			next_target_idx = None
			draw_found = False
			for k in range(i+1, min(i+50, len(lines))):
				if re.search(r"obj\.setoption\(\s*([\'\"])drawtarget\1\s*,", lines[k]):
					next_target_idx = k
					break
				if blend_idx is None and re.search(r"obj\.setoption\(\s*([\'\"])blend\1\s*,\s*([\'\"])alpha_add2\2\s*\)", lines[k]):
					blend_idx = k
				if re.search(r"obj\.(drawpoly\(|draw\()", lines[k]):
					draw_found = True
			# If we found alpha_add2 and a draw within this tempbuffer segment, switch to draw
			if blend_idx is not None and draw_found and (next_target_idx is None or blend_idx < next_target_idx):
				indent = re.match(r"^(\s*)", lines[blend_idx]).group(1) if re.match(r"^(\s*)", lines[blend_idx]) else "\t"
				lines[blend_idx] = f"{indent}obj.setoption(\"blend\", \"draw\")"
				changed += 1
		i += 1
	return ("\n".join(lines) + ("\n" if text.endswith("\n") else ""), changed)


def force_tempbuffer_blend_none(text: str, report: dict) -> tuple[str, int]:
	"""
	Within segments where drawtarget=="tempbuffer", change any
	obj.setoption("blend", <anything>) to obj.setoption("blend", "none").
	"""
	lines = text.splitlines(keepends=False)
	changed = 0
	in_temp_seg = False
	for i, ln in enumerate(lines):
		if re.search(r"obj\.setoption\(\s*([\'\"])drawtarget\1\s*,\s*([\'\"])tempbuffer\2", ln):
			in_temp_seg = True
			continue
		if in_temp_seg and re.search(r"obj\.setoption\(\s*([\'\"])drawtarget\1\s*,", ln):
			# switched target
			in_temp_seg = False
			continue
		if in_temp_seg and re.search(r"obj\.setoption\(\s*([\'\"])blend\1\s*,", ln):
			indent = re.match(r"^(\s*)", ln).group(1) if re.match(r"^(\s*)", ln) else "\t"
			lines[i] = f"{indent}obj.setoption(\"blend\", \"none\")"
			changed += 1
	return ("\n".join(lines) + ("\n" if text.endswith("\n") else ""), changed)


def process_file(src_path: Path, out_root: Path) -> dict:
	report: dict = {"source": str(src_path)}
	text, encoding = read_text_with_fallback(src_path)
	report["input_encoding"] = encoding
	converted = convert_text(text, report)

	# Decide output path
	rel = src_path
	# Make relative to workspace root if possible
	try:
		rel = src_path.relative_to(Path.cwd())
	except Exception:
		pass
	out_path = out_root / rel
	new_ext = map_ext_to_v2(out_path.suffix)
	out_path = out_path.with_suffix(new_ext)
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(converted, encoding="utf-8", newline="\n")
	report["output_path"] = str(out_path)
	report["output_encoding"] = "utf-8"
	return report


def main() -> int:
	parser = argparse.ArgumentParser(description="Convert AviUtl1 Lua scripts to AviUtl2-compatible form")
	parser.add_argument("inputs", nargs="+", help="Input script files (*.anm,*.obj,*.scn,*.cam,*.tra)")
	parser.add_argument("--outdir", default="converted", help="Output root directory")
	args = parser.parse_args()

	out_root = Path(args.outdir)
	reports = []
	for p in args.inputs:
		src = Path(p)
		if not src.exists():
			print(f"[WARN] Not found: {src}")
			continue
		reports.append(process_file(src, out_root))

	# Summary
	print("=== Conversion Summary ===")
	for r in reports:
		print(f"- {r['source']} -> {r['output_path']} ({r['input_encoding']} -> {r['output_encoding']})")
		for k in ("blend_converted", "buffer_tokens_replaced", "movie_flag_removed", "unsupported_calls"):
			if r.get(k):
				print(f"  * {k}: {r[k]}")
	return 0


if __name__ == "__main__":
	exit(main())


