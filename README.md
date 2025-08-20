AviUtl1 → AviUtl2 スクリプト移植ツール

本リポジトリは、AviUtl1 時代の Lua スクリプトを AviUtl2 仕様へ移植するための資料と自動変換スクリプトを含みます。

構成
- `docs/aviutl1_to_2_diff.md`: AviUtl1 と AviUtl2 の仕様差分と移植指針
- `docs/aviutl1_to_2_converter.md`: 変換スクリプトの概要とルール
- `convert_aviutl1_to_2.py`: 変換スクリプト本体（Python）

前提
- Windows + Python 3.10 以降
- 実行は PowerShell 推奨（パスに日本語が含まれても動作する想定）

使い方（例）
- 単体/複数ファイルの変換:
```powershell
python convert_aviutl1_to_2.py "ScriptPath1.anm" "ScriptPath2.anm" --outdir converted
```

出力
- `converted/` 以下に `*.anm2/*.obj2/*.scn2/*.cam2/*.tra2`（UTF-8, LF）として生成されます。

変換後スクリプトの配置
- `ProgramData\aviutl2\Script\`（またはその1階層下）へコピー

既定で行う主な変換/最適化（抜粋）
- blend 数値 → 文字列（0→"none", 1→"add", ...）
- バッファ名の統一（"obj"→"object", "tmp"→"tempbuffer", "frm"→"framebuffer"）
- `obj.load("movie", file, time, flag)` の `flag` 削除
- 代表的な `obj.putpixel` 二重ループ → ピクセルシェーダー呼び出しに移行（必要な HLSL を自動挿入）
- `obj.drawpoly(...)` 多発 → テーブル一括描画に集約
- tempbuffer 区間の安定化
  - `obj.setoption("sampler","clamp")` を自動注入（未指定時）
  - `obj.load("tempbuffer")` 直後に `obj.draw()` を補完
  - tempbuffer 区間の合成は既定で `blend="none"`（境界チラつき抑制）

参考
- 詳細は `docs/aviutl1_to_2_diff.md` と `docs/aviutl1_to_2_converter.md` を参照してください。
- 本スクリプトはAviutl1,2それぞれのlua.txtの差分をCursor GPT5に差分解析を行わせ、それを元に出力したものとなります。
- ティム氏の風揺れT 及び ぷよぷよTで動作検証済みです。[https://tim3.web.fc2.com/sidx.htm](https://tim3.web.fc2.com/sidx.htm)


