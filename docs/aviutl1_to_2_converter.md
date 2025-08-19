AviUtl1 → AviUtl2 自動変換ツール 概要

目的
- AviUtl1 時代の Lua スクリプト（*.anm, *.obj, *.scn, *.cam, *.tra）を、AviUtl2 環境で動作しやすい形へ自動変換します。
- 互換性確保に必要な置換（blendの文字列化、バッファ名、movie引数など）に加え、2 で重い/非対応な処理の最適化（putpixel→シェーダー、drawpoly一括化、tempbuffer周りの安定化）を実施します。

配置と実行
- スクリプト: `temp/convert_aviutl1_to_2.py`
- 使い方（PowerShell）
  - 単体: `python temp/convert_aviutl1_to_2.py "Script_Aviutl1/xxx.anm" --outdir converted`
  - 複数: `python temp/convert_aviutl1_to_2.py a.anm b.anm c.obj --outdir converted`
- 出力は `converted/` 以下に、拡張子を `*.anm2/*.obj2/*.scn2/*.cam2/*.tra2` に変更して保存されます（UTF-8, LF）。

主な自動変換（互換置換）
- 合成モードの数値→文字列
  - 置換表: 0→"none", 1→"add", 2→"sub", 3→"mul", 4→"screen", 5→"overlay", 6→"light", 7→"dark", 8→"brightness", 9→"chroma"
- バッファ名の統一
  - "obj"→"object", "tmp"→"tempbuffer", "frm"→"framebuffer"（API 呼出し文脈に限定して安全に置換）
- `obj.load("movie", file, time, flag)` の flag 削除
- 非対応 API の検知と注記
  - `obj.putpixel`, `obj.copypixel`, `obj.get/putpixeldata`, `obj.filter` に `-- [A2_TODO]` を付与（シェーダー移行を促す）

主な最適化/自動リライト
- putpixel の二重ループ→ピクセルシェーダー
  - 代表パターンを検出して `pixelshader("ps_puyopuyo_map", ...)` 呼び出しに変換し、必要な HLSL ブロックを冒頭に自動挿入
- `obj.drawpoly(...)` 多発→テーブル一括描画
  - `drawpolyT` の中身を `table.insert(vertex,{...})` 化し、ループ外で `obj.drawpoly(vertex)` の単一呼出しへ集約
- tempbuffer 区間の安定化
  - `obj.setoption("drawtarget","tempbuffer",...)` の直後に `obj.setoption("sampler","clamp")` を自動注入（未指定時）
  - `obj.load("tempbuffer")` の直後に `obj.draw()` を補完（非表示回避）
  - tempbuffer 区間内の `obj.setoption("blend", ...)` はすべて `"none"` に強制（境界のチラつき/変色低減。方式6を既定採用）

変換方針の根拠（仕様差）
- 2 では pixel 出力系（putpixel/copy/...）が非対応のため、シェーダー移行が必要（`lua_aviutl2.txt:13-18, 565-589`）
- 合成モードは 2 で文字列指定が基本（`lua_aviutl2.txt:327-349`）
- バッファ名は 1 と 2 で異なる（`lua_aviutl1.txt:385-397`, `lua_aviutl2.txt:538-551`）
- `drawpoly({table})` は一括描画で高速（`lua_aviutl2.txt:220-233`）

制限・注意
- パターンマッチングによる自動化のため、Lua 構文が大きく異なる場合は最適化が適用されないことがあります。
- putpixel→シェーダーは代表的な 2 重ループのみ対象です。個別ロジックはテンプレートを参考に調整してください。
- `obj.effect` の旧→新パラメータ名は `effect.conf` に依存するため、必要に応じ名称変換テーブルを追加してください。

既知の良好動作サンプル
- ぷよぷよT: putpixel による描画をシェーダーへ移行して動作
- 風揺れT: drawpoly バッチ化＋tempbuffer 安定化で負荷とチラつきを軽減、blend=none 方式（6）を既定採用

出力確認チェックリスト
- 文字コードが UTF-8 か（BOM 無し）
- blend が文字列指定になっているか
- バッファ名が 2 の名称に統一されているか
- tempbuffer 区間で `sampler` 指定と `blend="none"` が入っているか
- `obj.load("tempbuffer")` の直後に `obj.draw()` が存在するか

今後の拡張候補
- `obj.effect` の名称変換テーブル対応
- シェーダー挿入のテンプレート化（複数プリセット）
- Lua パーサ導入による構文安全な変換

連絡事項
- 変換器の出力やログで気づいた点があれば `log.txt` へ追記してください（解析し、ルールを強化します）。


