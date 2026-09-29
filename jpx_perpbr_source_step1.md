# ステップ1 完了メモ: JPX「規模別・業種別PER・PBR」データ所在の特定

## 1. 参照した統計ページ（一次情報源）
- 名称: 規模別・業種別PER・PBR（連結・単体）一覧
- 提供元: 株式会社日本取引所グループ / 東京証券取引所（株式部データサービス室）
- URL: https://www.jpx.co.jp/markets/statistics-equities/misc/04.html
- ページ表示上の最終更新表示: **2026/08/03 更新**
- 更新サイクル: 毎月第1営業日 午後1時更新予定（前月末基準のデータを掲載）

## 2. 最新公表データの基準年月
- **最新公表: 2026年7月末時点（2026年7月分）**
- ファイル名: `perpbr202607.xlsx`
- 直リンク: https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx
- 2026年8月分以降は「-」（未掲載）。よって現時点で入手可能な最新基準月は 2026年7月末。

## 3. データ本体の掲載形態
- ページ内に数値表は掲載されていない。**年×月のマトリクス表からExcel(.xlsx)ファイルをダウンロードする形式**。
- 各セルにExcelアイコンのリンクがあり、命名規則は `perpbr<YYYYMM>.xlsx`。
- Excelファイル内には、市場区分別（プライム/スタンダード/グロース）×規模別、および
  東証33業種別の PER・PBR（連結ベース／単体ベース）が収録される。
- 注: JPX公表値は業種ごとの**加重平均（合計時価総額÷合計純利益／合計純資産）**であり、
  「中央値」ではない。中央値が必要な場合は別途、銘柄別データからの算出が必要
  （→ JPX「上場会社財務データ」または株探/Yahoo!ファイナンスの銘柄別値を使用）。

## 4. 直近12か月の月次ファイル直リンク（時系列比較・正常レンジ算定用）
| 基準年月 | ファイル | URL |
| --- | --- | --- |
| 2026年7月 (最新) | perpbr202607.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx |
| 2026年6月 | perpbr202606.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001iof6-att/perpbr202606.xlsx |
| 2026年5月 | perpbr202605.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001entg-att/perpbr202605.xlsx |
| 2026年4月 | perpbr202604.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt00000142v7-att/perpbr202604.xlsx |
| 2026年3月 | perpbr202603.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000svf7-att/perpbr202603.xlsx |
| 2026年2月 | perpbr202602.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000ofbv-att/perpbr202602.xlsx |
| 2026年1月 | perpbr202601.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000k4id-att/perpbr202601.xlsx |
| 2025年12月 | perpbr202512.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000g2os-att/perpbr202512.xlsx |
| 2025年11月 | perpbr202511.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000busa-att/perpbr202511.xlsx |
| 2025年10月 | perpbr202510.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt0000003a1o-att/perpbr202510.xlsx |
| 2025年9月 | perpbr202509.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000026p4r-att/perpbr202509.xlsx |
| 2025年8月 | perpbr202508.xlsx | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000022ifd-att/perpbr202508.xlsx |

（2025年1月〜7月分も同ページに掲載あり: um3qrc...-att/perpbr2025MM.xlsx 形式）

## 5. 補助資料リンク
- 長期データ（総合）Excel: https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/longrange-perpbr.xlsx
  → 「正常レンジ（過去の変動幅）」判定の基礎データとして有用（総合ベース）。
- PER・PBR計算要領（2024年2月1日, PDF）: https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/202402PERPBRHPj.pdf
  → 算出定義（赤字企業の扱い、加重平均方式）を確認するために必須。
- 2013年〜2019年アーカイブ(zip): https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/2013-2019(PDF&Excel).zip
- 1999年11月〜2012年アーカイブ(zip): https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/1999.11-2012(PDF).zip
- 銘柄別データ（中央値算出用）: JPX「上場会社財務データ」
- 業種別時価総額（補完）: https://www.jpx.co.jp/markets/statistics-equities/misc/07.html

## 6. 次ステップへの引き継ぎ事項
- 対象業種（東証33業種のうち本タスク対象）: 機械、化学、電気機器、輸送用機器、銀行業。
  必要に応じ 情報・通信業、卸売業、建設業、鉄鋼、医薬品 等も参照可能。
- 取得すべきファイル: `perpbr202607.xlsx`（連結・単体の両シート）。
- 留意点: JPXは加重平均値のみ提供。「中央値」を求める場合は株探の業種別PER・PBR
  （中央値・平均を併記）または銘柄別データ集計で補完すること。データ時点は必ず
  「2026年7月末（JPX、2026/08/03公表）」と明記する。

---
作成: Benchmark Agent / 取得日: JPXページ更新表示 2026/08/03 時点
