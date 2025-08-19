AviUtl 1 → 2 Lua 拡張仕様 差分と移植ガイド

概要
- 目的: AviUtl1 時代の Lua スクリプト（*.anm, *.obj, *.scn, *.cam, *.tra）を、AviUtl2 の Lua 仕様へ安全に移行するための参照資料です。
- 本書は「非互換点」「追加点」「API 差分」「自動変換ルール（候補）」をまとめます。

重大な非互換点（必読）
- 文字コード/配置場所
  - 1: SJIS 前提。`package.path/cpath` は `exedit.auf` と `script` に初期化。
  - 2: UTF-8（旧形式は SJIS 継続可だが制約あり）。配置は `ProgramData\aviutl2\Script\`（1階層下も可）。
- キャッシュ再読み込みの挙動
  - 2: 「キャッシュを破棄」でスクリプト（シェーダー含む）が再読み込みされますが、設定項目の変更は反映されません。
- ピクセル書き込み API の廃止（シェーダーへ移行）
  - 1 に存在: `obj.putpixel`, `obj.copypixel`, `obj.pixeloption("put"|"blend")`, `obj.getpixeldata`, `obj.putpixeldata`, `obj.filter`（フィルタオブジェクト実行）
  - 2 の代替: `pixelshader(...)`, `computeshader(...)`, `obj.clearbuffer(...)`。`obj.getpixel` は読取のみ継続。
- 合成モード（blend）の指定方法
  - 1: 数値列挙（0=通常,1=加算,2=減算,3=乗算,4=スクリーン,5=オーバーレイ,6=比較(明),7=比較(暗),8=輝度,9=色差）
  - 2: 文字列指定（"none","add","sub","mul","screen","overlay","light","dark","brightness","chroma"...）。旧数値も互換受理。
- バッファ名の変更と copybuffer の仕様差
  - 名称変更: 1 の `"tmp"/"obj"/"frm"` → 2 の `"tempbuffer"/"object"/"framebuffer"`
  - 2 の `copybuffer`: 出力先に `framebuffer` を指定する場合はコピー元の制限あり。`cache:` の寿命は「1フレーム毎に破棄」。
- 動画読み込み
  - 1: `obj.load("movie", file[, time, flag])`（`flag`=アルファ有無）
  - 2: `obj.load("movie", file[, time])`（アルファ指定は廃止）
- 旧スクリプト形式の pixel 出力系は 2 では非対応（シェーダーに移行）

主な追加・拡張（2 での進化点）
- 設定ディレクティブ拡張: `--track@var`, `--check@var`, `--color@var`, `--file@var`, `--font@var`, `--figure@var`, `--select@var`, `--value@var`, `--label`, `--script`, `--information`
  - 旧形式（`--track0`, `--check0`, `--color`, `--file`, `--dialog`, `--param`）も利用可能
- シェーダー API: `pixelshader(name, target, resource[, constant], blend)`, `computeshader(name, {target}, {resource}[, {constant}, countX, countY, countZ])`, `obj.clearbuffer(target[, color])`
- 描画強化: `obj.drawpoly({table}[, alpha])`（一括・法線/頂点色に対応）、`obj.setoption("sampler", "clip|clamp|loop")`
- 読み込み拡張: `obj.load("figure", ..., round)`（角丸/SVG 対応）、`obj.load("framebuffer", ..., alpha)`（アルファ保持）
- ユーティリティ: `rotation(...)` 追加。`debug_print` は内部ログ（設定で ODS へも出力可）
- 文字装飾: `obj.setfont` の `type` が 0～6 に拡張（1 は 0～4）
- get 系: `obj.getoption("track_mode")` は 0 か「モード名称」の文字列を返却（1 は数値）。`obj.getpoint` に `timecontrol`/`framerate` が追加
- スクリプトエンジン指定: `--script:種別` で `luaJIT`/`lua` を選択可（2 の新形式のデフォルトは `luaJIT`、旧形式は `lua`）
- obj.effect: 旧パラメータ名は `effect.conf` による読み替え。数値型パラメータ指定への対策あり（beta 更新）

API 差分（代表）
- obj.setoption("blend", ...)
  - 1: 数値 0..9 / 2: 文字列（数値互換あり）
  - 2 の追加名例: `"shadow"`, `"light_dark"`, `"diff"`（いずれも 1 では未定義）
- obj.copybuffer(dst, src)
  - 1: dst=`obj|tmp|cache`, src=`frm|obj|tmp|cache|image`
  - 2: dst=`object|tempbuffer|cache|framebuffer(制限)`, src=`framebuffer|object|tempbuffer|cache|image`
- obj.load
  - movie: 1 の `flag`（アルファ）廃止
  - figure: 2 に `round` 追加、SVG 名指定可
  - framebuffer: 2 に `alpha` フラグ追加
- obj.setfont
  - 1: `type`=0..4（標準/影/影(薄)/縁/縁(細)） / 2: `type`=0..6（縁(太)/縁(角) 追加）
- pixel 関連
  - 1: get/put/copy/pixeldata + filter
  - 2: get + pixelshader/computeshader/clearbuffer（出力先やブレンド指定は API 引数で）
- obj.getpixel / obj.pixeloption
  - 1: `pixeloption("get"="obj|frm", "put"="obj|frm", "blend"=0..9)`
  - 2: `pixeloption("type"="col|rgb|yc", "get"="object|framebuffer")`（put・blend は非対応）
- obj.getoption("track_mode")
  - 1: 数値（0=無し/1=直線/.../8=反復）
  - 2: 0 以外はモード名称の文字列
 - obj.getpoint
  - 2: `timecontrol` と `framerate` の取得が追加
- その他
  - `obj.drawpoly({table})` 追加（2）
  - `obj.setoption("sampler", ...)` 追加（2）
  - `rotation(...)` 追加（2）

置換マッピング（機械変換の基本）
- 合成モード（推奨: 文字列化）
  - 0→"none", 1→"add", 2→"sub", 3→"mul", 4→"screen", 5→"overlay", 6→"light", 7→"dark", 8→"brightness", 9→"chroma"
- バッファ名
  - "tmp"→"tempbuffer", "obj"→"object", "frm"→"framebuffer"
- obj.load("movie")
  - 第4引数 `flag` を削除
- obj.copybuffer 組合せ
  - `framebuffer` への出力は 2 で制限あり。自動変換時は変換前の組合せを検査し、非対応はワーク（tempbuffer）経由に変更
- obj.getoption("track_mode")
  - 1 の数値比較が出現する箇所は、名称比較に置換（または互換ラッパで数値→名称対応を吸収）

自動変換ルール（正規表現のたたき台）
- 注意: ルールは Lua 構文を厳密に解釈しない簡易置換の雛形です。実装時はトークン化 or 木構文解析を推奨します。

1) 文字コード
- 入力: SJIS（*.anm,*.obj,*.scn,*.cam,*.tra） → 出力: UTF-8 (BOM なし)

2) バッファ名
- パターン: `\b("tmp"|"obj"|"frm")\b` → ルール: tmp→tempbuffer / obj→object / frm→framebuffer

3) blend 数値 → 文字列
- パターン: `obj\.setoption\(\s*"blend"\s*,\s*(\d)\s*(,\s*"force"\s*)?\)`
- 置換: `obj.setoption("blend", "<mapped>")`（force オプションはそのまま維持）

4) obj.load("movie") の flag 削除
- パターン: `obj\.load\(\s*"movie"\s*,\s*([^,\)]*)(?:\s*,\s*([^,\)]*))?(?:\s*,\s*[^,\)]*)\)`
- 置換: `obj.load("movie", <file>[, <time>])`（第3引数を time と解釈）

5) copybuffer の名称置換と組合せ検査
- 名称は 2) で統一置換。
- 組合せが `framebuffer` への書込みで非対応の場合: `tempbuffer` に出力→最後に `object` へ合成/差し替え等、手続き変換を適用（実装側で検査）

6) getoption("track_mode") の戻り値差
- パターン（数値比較）: `obj\.getoption\(\s*"track_mode"\s*,[^\)]*\)\s*==\s*(\d+)`
- 置換: 対応名称と比較（例: `== 1` → `== "linear"` 等）。名称マッピングは実装側にテーブルを持たせる。

シェーダー移行（自動変換の対象外・注意喚起）
- 次の API は 2 で非対応のため、自動変換では TODO マーカーを付与し、手動またはテンプレート化したシェーダーへ移植します。
  - `obj.putpixel(...)`
  - `obj.copypixel(...)`（座標単位のコピー）
  - `obj.pixeloption("put"|"blend")`
  - `obj.getpixeldata(...)` / `obj.putpixeldata(...)`
  - `obj.filter(...)`（スクリーン全体フィルタ）
- 推奨方針
  - 単純な明度/色操作: `pixelshader` で実装（例は `lua_aviutl2.txt` のサンプル参照）
  - 近傍参照や逐次処理: `computeshader` 利用。必要に応じ `tempbuffer` をワークに。

補助ラッパ（互換層）設計メモ
- 目的: スクリプト本文の変更を最小化するため、2 の環境に 1 風の関数/定数を与える
- 例
  - `BLEND = { [0]="none", [1]="add", [2]="sub", [3]="mul", [4]="screen", [5]="overlay", [6]="light", [7]="dark", [8]="brightness", [9]="chroma" }`
  - `function set_blend(v, force) return obj.setoption("blend", BLEND[v] or v, force) end`
  - `function bufname(x) return x=="tmp" and "tempbuffer" or x=="obj" and "object" or x=="frm" and "framebuffer" or x end`
  - `function copybuffer(dst, src) return obj.copybuffer(bufname(dst), bufname(src)) end`
- 注意: `putpixel` 相当は提供不可（シェーダー実装が必要）

`obj.effect` パラメータ名の互換
- 2 は `effect.conf` による旧→新の名称読み替えを行います。未定義のものは定義追補で対応。
- 自動変換: 既知の変換表を JSON 等で管理し、名称を明示置換することで `effect.conf` 依存を軽減可。

参考原文（抜粋の所在）
- 文字コード/配置: `lua_aviutl2.txt:13-16`
- 旧 pixel 出力系の非対応: `lua_aviutl2.txt:17-18`
- シェーダー API: `lua_aviutl2.txt:565-611`
- clearbuffer: `lua_aviutl2.txt:556-564`
- blend 指定: `lua_aviutl1.txt:214-223`, `lua_aviutl2.txt:327-349`
- バッファ名と copybuffer: `lua_aviutl1.txt:385-397`, `lua_aviutl2.txt:538-551`
- load(movie) 引数差: `lua_aviutl1.txt:119-126`, `lua_aviutl2.txt:239-246`
- drawpoly(table): `lua_aviutl2.txt:220-233`
- sampler: `lua_aviutl2.txt:393-399`
- rotation: `lua_aviutl2.txt:683-692`
- getoption(track_mode) 戻り値差: `lua_aviutl1.txt:274-279`, `lua_aviutl2.txt:404-409`

付録: サンプル変換（概念）
```lua
-- AviUtl1
obj.setoption("blend", 1)
obj.copybuffer("obj", "frm")
obj.load("movie", path, time, 1)

-- AviUtl2（自動変換後の一例）
obj.setoption("blend", "add")
obj.copybuffer("object", "framebuffer")
obj.load("movie", path, time)
```

今後の実装（Python 自動変換ツール）
- ステップ
  1) 入力のエンコーディング判定→UTF-8 へ変換
  2) 字句解析（Lua コメント/文字列を正しくスキップ）
  3) 上記置換マッピングの適用
  4) `copybuffer` 組合せの検査と必要な手続き挿入
  5) 非対応 API の検出と TODO コメント挿入（シェーダー移行指示）
  6) 変換レポート出力（変換数、警告、TODO 一覧）
- 出力
  - `converted/` 配下に *.anm2, *.obj2, *.scn2, *.cam2, *.tra2 として保存（UTF-8）
  - ログ（差分サマリ、警告）

備考
- 2 の旧形式サポートは限定的（pixel 出力系は非対応）。移行対象に該当 API がない場合は、最小置換のみで 2 でも動作する可能性があります。


