# JPX「規模別・業種別PER・PBR」— 最新掲載月とデータファイルURL抽出結果

作成: Benchmark Agent / 手順2 成果物
取得方法: `read_website_content` による直接読取（静的HTMLはJS描画のためリンク未取得 → プロキシレンダリング経由で全リンク抽出に成功）

---

## 1. 出典ページ（一次情報）

| 項目 | 内容 |
|---|---|
| ページ名 | 規模別・業種別PER・PBR（連結・単体）一覧 |
| URL（日本語） | https://www.jpx.co.jp/markets/statistics-equities/misc/04.html |
| URL（英語） | https://www.jpx.co.jp/english/markets/statistics-equities/misc/04.html |
| ページ更新日 | 2026/08/03（英語版: Aug. 03, 2026） |
| Published Time（HTTPヘッダ） | Mon, 03 Aug 2026 04:00:28 GMT |
| 更新頻度 | 毎月第1営業日 午後1時 |
| 発行元 | 株式会社東京証券取引所 株式部データサービス室（databank-geppou@jpx.co.jp） |

---

## 2. 【DONE条件①】最新掲載月＝基準日

> **最新掲載月 ＝ 2026年7月末時点（2026年7月31日 月末現在）**

- 2026年の掲載状況: 1月〜7月＝Excel掲載済／**8月〜12月＝「-」（未掲載）**
- ページ更新日が 2026/08/03（＝8月第1営業日）であり、同日に「2026年7月末現在」データが公開された整合が取れている。
- したがって本タスクで参照すべき最新ベンチマークの基準日は **2026年7月31日（月末）**。

---

## 3. 【DONE条件②】データファイルURL

### 3-1. 最新ファイル（2026年7月末時点）＝ 本命
```
https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx
```
- 形式: Excel（.xlsx）／PDF版は現行年次では提供されずExcelのみ
- 収録内容: 各月末現在の 市場区分別（プライム／スタンダード／グロース）× 規模別 × 33業種別の PER・PBR（連結ベース・単体ベース）

### 3-2. 直近12か月（時系列レンジ算出用）

| 基準年月 | データファイルURL |
|---|---|
| 2026年7月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx |
| 2026年6月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001iof6-att/perpbr202606.xlsx |
| 2026年5月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001entg-att/perpbr202605.xlsx |
| 2026年4月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt00000142v7-att/perpbr202604.xlsx |
| 2026年3月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000svf7-att/perpbr202603.xlsx |
| 2026年2月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000ofbv-att/perpbr202602.xlsx |
| 2026年1月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000k4id-att/perpbr202601.xlsx |
| 2025年12月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000g2os-att/perpbr202512.xlsx |
| 2025年11月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000busa-att/perpbr202511.xlsx |
| 2025年10月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt0000003a1o-att/perpbr202510.xlsx |
| 2025年9月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000026p4r-att/perpbr202509.xlsx |
| 2025年8月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000022ifd-att/perpbr202508.xlsx |

### 3-3. 2025年 その他（1〜7月）

| 基準年月 | URL |
|---|---|
| 2025年1月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000000eyis-att/perpbr202501.xlsx |
| 2025年2月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000000ybjd-att/perpbr202502.xlsx |
| 2025年3月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000014op5-att/perpbr202503.xlsx |
| 2025年4月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001963i-att/perpbr202504.xlsx |
| 2025年5月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001jra4-att/perpbr202505.xlsx |
| 2025年6月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001nrns-att/perpbr202506.xlsx |
| 2025年7月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001ryyo-att/perpbr202507.xlsx |

### 3-4. 過去年ファイル命名規則
2020〜2024年も同一命名規則 `perpbr{YYYYMM}.xlsx`（ディレクトリハッシュは月ごとに異なる）。
例：2024年12月末 → https://www.jpx.co.jp/markets/statistics-equities/misc/mklp77000000p7l9-att/perpbr202412.xlsx

### 3-5. 補助ファイル（定義・長期系列・アーカイブ）

| 資料 | URL |
|---|---|
| **PER・PBR計算要領（2024年2月1日）** ※定義の根拠 | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/202402PERPBRHPj.pdf |
| 長期データ（総合） Excel | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/longrange-perpbr.xlsx |
| 2013年〜2019年（PDF・Excel）ZIP | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/2013-2019(PDF&Excel).zip |
| 1999年11月〜2012年（PDF）ZIP | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/1999.11-2012(PDF).zip |
| お知らせ（2022年4月8日・市場区分見直し対応） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/oshirase.pdf |
| 【参考】市場区分見直し後のサンプルファイル | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/perpbr202111.xlsx |

---

## 4. 後続工程への申し送り（重要）

1. **JPX公表値は「加重平均」および「単純平均」であり、中央値（median）ではない。**
   タスク要件の「業種別PER・PBR中央値」はJPX統計から直接取得できない。
   → 対応案A: 銘柄別データ（JPX「上場会社財務データ」）から33業種ごとに自前で中央値算出。
   → 対応案B: 株探（kabutan）等の業種別中央値掲載ソースを併用し、出典・時点を明記。
   → いずれも不可の場合は「データ不足」と報告し、推測値は使用しない。
2. 対象主要業種（33業種分類上の名称）: **機械／化学／電気機器／輸送用機器／銀行業**。加えて参考として「鉄鋼」「非鉄金属」「精密機器」「情報・通信業」等。
3. Excelは市場区分（プライム／スタンダード／グロース）別シート構成。ベンチマークは通常 **プライム市場・連結ベース** を基準とし、必要に応じ全市場合計も併記する。
4. 04.html は JavaScript 描画のため素の HTML 取得ではリンクが得られない。再取得時は本ファイルの直リンクを使用するか、レンダリング経由で取得すること。

---

出典: 日本取引所グループ（JPX）／東京証券取引所「規模別・業種別PER・PBR」 https://www.jpx.co.jp/markets/statistics-equities/misc/04.html （ページ更新日 2026/08/03、最新掲載データ基準日 2026年7月31日）
