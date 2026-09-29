# JPX「規模別・業種別PER・PBR」最新データ時点とファイルリンク特定結果

作成日: 本ステップ実行時点 / 担当: Benchmark Agent
取得方法: read_website_content によるJPX公式ページ（日本語版・英語版）の直接読み取り、
およびレンダリング後HTML（r.jina.ai 経由の同一URL）からのリンク抽出。推測URLは含まない。

---

## 1. 参照した一次ソース（ページ）

| 区分 | URL | ページ最終更新表示 |
|---|---|---|
| 日本語版（本命） | https://www.jpx.co.jp/markets/statistics-equities/misc/04.html | 2026/08/03 更新 |
| 英語版 | https://www.jpx.co.jp/english/markets/statistics-equities/misc/04.html | Update: Aug. 03, 2026 |

ページタイトル（日）: 「規模別・業種別PER・PBR（連結・単体）一覧」
ページタイトル（英）: 「Average PER and PBR by Size and Types of Industry（Consolidated）」

---

## 2. 【確定】最新データ時点

**最新データ時点 ＝ 2026年07月末（2026-07-31 基準、月末値）**

根拠:
- 掲載マトリクスの2026年行は 1月〜7月にExcelリンクが存在し、8月〜12月は「-」（未掲載）。
- ページ更新日が 2026/08/03（＝8月第1営業日）であり、JPXの運用ルール
  「毎月第1営業日 午後1時更新予定」と整合。すなわち 2026/08/03 更新分＝2026年7月末基準データ。
- 英語版も同一（2026年行 Jan.〜Jul. のみリンクあり）。

次回更新見込: 2026年9月第1営業日 13:00 → 2026年8月末基準データ（perpbr202608.xlsx）掲載予定。

---

## 3. 【確定】最新データファイルの直接ダウンロードURL

### ★ 最優先（2026年7月末 基準・Excel）
https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx

- ファイル名: perpbr202607.xlsx
- 形式: Excel (.xlsx)
- 収録内容: 東証各市場（プライム／スタンダード／グロース）の
  規模別（大型・中型・小型）および業種別（33業種）の PER・PBR、連結ベース＋単体ベース
- 注意: ダウンロード後、Excelの「保護ビュー」警告で一部の値が非表示になる場合あり
  →「編集を有効にする」をクリックすること（JPX公式注記）

### 直近12か月分（時系列比較・レンジ算出用）

| 基準年月末 | ダウンロードURL |
|---|---|
| 2026年07月末（最新） | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx |
| 2026年06月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001iof6-att/perpbr202606.xlsx |
| 2026年05月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001entg-att/perpbr202605.xlsx |
| 2026年04月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt00000142v7-att/perpbr202604.xlsx |
| 2026年03月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000svf7-att/perpbr202603.xlsx |
| 2026年02月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000ofbv-att/perpbr202602.xlsx |
| 2026年01月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000k4id-att/perpbr202601.xlsx |
| 2025年12月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000g2os-att/perpbr202512.xlsx |
| 2025年11月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000busa-att/perpbr202511.xlsx |
| 2025年10月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt0000003a1o-att/perpbr202510.xlsx |
| 2025年09月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000026p4r-att/perpbr202509.xlsx |
| 2025年08月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000022ifd-att/perpbr202508.xlsx |
| 2025年07月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001ryyo-att/perpbr202507.xlsx |

（注）URLの中間ディレクトリ（例 t13vrt000001ranp-att）は月ごとにJPX側で発番される
不規則な文字列であり、規則的に生成できない。上記は全てページHTMLから実際に抽出した実リンク。

### 2025年 その他（1〜6月）

| 基準年月末 | ダウンロードURL |
|---|---|
| 2025年01月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000000eyis-att/perpbr202501.xlsx |
| 2025年02月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000000ybjd-att/perpbr202502.xlsx |
| 2025年03月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000014op5-att/perpbr202503.xlsx |
| 2025年04月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001963i-att/perpbr202504.xlsx |
| 2025年05月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001jra4-att/perpbr202505.xlsx |
| 2025年06月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001nrns-att/perpbr202506.xlsx |

---

## 4. 補助・定義確認用ファイル（同ページ掲載）

| 資料 | 形式 | URL |
|---|---|---|
| PER・PBR計算要領（2024年2月1日） | PDF | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/202402PERPBRHPj.pdf |
| 長期データ（総合）※過去長期時系列 | Excel | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/longrange-perpbr.xlsx |
| 2013年〜2019年 一括 | ZIP(PDF/Excel) | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/2013-2019(PDF&Excel).zip |
| 1999年11月〜2012年 一括 | ZIP(PDF) | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/1999.11-2012(PDF).zip |
| お知らせ（2022年4月8日：市場区分見直し対応） | PDF | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/oshirase.pdf |
| 【参考】市場区分見直し後のサンプルファイル（2021年11月版） | Excel | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/perpbr202111.xlsx |

会社別データ（自前で中央値を算出する場合の元データ）:
「上場会社財務データ」ページ（同ページからリンク）

---

## 5. 次ステップへの重要な申し送り（データ定義上の留意点）

1. **JPX公表値は「加重平均」であり「中央値」ではない。**
   英語版タイトルが "Average PER and PBR by Size and Types of Industry" である通り、
   業種内の合計時価総額÷合計純利益（または合計純資産）で算出される加重平均値。
   タスクが求める「業種別PER・PBR中央値」を厳密に出すには、
   「上場会社財務データ」の会社別Excelから業種ごとに個社PER/PBRを並べて中央値を取る必要がある。
   → 本ベンチマークでは「JPX加重平均（公式値）」と「個社中央値（自前集計）」を分けて提示すべき。

2. 業種区分は東証33業種（機械・化学・電気機器・輸送用機器・銀行業 等）。
   perpbr202607.xlsx 内に連結／単体の両シートが含まれる。

3. 「正常レンジ」の算出は、上記の直近12〜36か月分xlsx（2023年以降のURLも同ページに全て掲載あり）
   を時系列で並べ、業種別に最小〜最大／±1σ等を取ることで構成可能。

4. 本ステップ時点で、Excelファイルの中身（実数値）はまだ取得していない。
   実数値は「データ不足」であり、次ステップでの perpbr202607.xlsx 取得・パースが必要。

---

## 6. DONE 判定

- [x] 最新データ時点の明文化 → **2026年7月末（2026-07-31）基準**
- [x] ダウンロード/閲覧用リンクURLの明文化 →
      https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx
      （加えて過去19か月分＋補助資料6点のURLを実リンクとして記載）
