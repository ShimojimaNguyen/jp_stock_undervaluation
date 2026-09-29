# JPX 業種別PER・PBR ベンチマーク：一次情報URL候補リスト

作成: Benchmark Agent
収集方法: search_the_internet_with_serper は環境エラー（`SERPER_API_KEY` 未設定）で実行不能だったため、
read_website_content によるJPX公式サイト（jpx.co.jp）の直接クロールで代替収集した。
以下URLはすべて実際に取得・内容確認済み（404だったものは除外済み）。

## 1. 最優先（統計本体ページ）

| # | 名称 | URL | 確認結果 |
|---|------|-----|----------|
| 1 | 規模別・業種別PER・PBR（連結・単体）一覧【日本語・本命】 | https://www.jpx.co.jp/markets/statistics-equities/misc/04.html | 取得成功。ページ表記「2026/08/03 更新」。毎月第1営業日13:00更新。 |
| 2 | Average PER and PBR by Size and Types of Industry (Consolidated)【英語版・同一データ】 | https://www.jpx.co.jp/english/markets/statistics-equities/misc/04.html | 取得成功。Update: Aug. 03, 2026。 |
| 3 | PER・PBR計算要領（2024年2月1日改定）PDF | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/202402PERPBRHPj.pdf | リンク実在（04.html内リンク）。加重平均/連結・単体の定義、赤字企業の扱い等の算出定義。 |

## 2. 実データファイル（Excel直リンク・最新〜近時）

| 対象月 | URL |
|--------|-----|
| 2026年7月末（最新） | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx |
| 2026年6月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001iof6-att/perpbr202606.xlsx |
| 2026年5月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001entg-att/perpbr202605.xlsx |
| 2026年3月末（期末基準） | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000svf7-att/perpbr202603.xlsx |
| 2025年12月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000g2os-att/perpbr202512.xlsx |
| 2025年3月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000014op5-att/perpbr202503.xlsx |
| 長期データ（総合・時系列） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/longrange-perpbr.xlsx |
| 2013〜2019年アーカイブ(zip) | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/2013-2019(PDF&Excel).zip |
| 1999年11月〜2012年アーカイブ(zip) | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/1999.11-2012(PDF).zip |

## 3. 補完・クロスチェック用のJPX公式ページ

| # | 名称 | URL | 用途 |
|---|------|-----|------|
| 4 | 業種別時価総額 | https://www.jpx.co.jp/markets/statistics-equities/misc/07.html | 33業種別の時価総額。加重PER/PBRの分母検算、業種規模の把握。 |
| 5 | 株価平均・株式平均利回り | https://www.jpx.co.jp/markets/statistics-equities/misc/03.html | 2026年7月分掲載。配当利回りとの整合チェック。 |
| 6 | 市場別時価総額 | https://www.jpx.co.jp/markets/statistics-equities/misc/02.html | プライム/スタンダード/グロース区分別の水準比較。 |
| 7 | 東証上場銘柄一覧（2026年7月末） | https://www.jpx.co.jp/markets/statistics-equities/misc/01.html | 33業種コードと銘柄の対応付け（中央値を自前算出する場合の母集団定義）。 |
| 8 | その他統計資料トップ | https://www.jpx.co.jp/markets/statistics-equities/misc/index.html | 上記各統計へのハブ。 |

## 重要な留意点（次工程への申し送り）

1. **JPX公表値は「加重平均」であり「中央値」ではない。** 04.html のExcelは規模別・業種別の
   合計純利益／合計純資産に基づく加重平均PER・PBR（連結・単体）を掲載しており、
   銘柄中央値は公表していない。「業種別PER・PBR中央値」が必要な場合は、
   (a) JPX加重平均値をベンチマーク代理指標として使う、または
   (b) 上場会社財務データ／東証上場銘柄一覧から銘柄別値を取得し自前で中央値算出する、
   のいずれかを選択する必要がある。この点は推測せず明示すべき制約。
2. 最新データ時点は **2026年7月末**（ページ更新 2026/08/03）。翌月分は毎月第1営業日13:00更新。
3. 出典表記は「日本取引所グループ『規模別・業種別PER・PBR』（20XX年X月末時点）」で統一する。
4. 株探・Yahoo!ファイナンスの業種別PER/PBRは中央値ではなく独自集計であり、JPXと定義が異なるため
   併記する場合は必ず出典と定義差を注記すること。
