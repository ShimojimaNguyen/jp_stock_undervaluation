# JPX「規模別・業種別PER・PBR」最新データ時点とダウンロードリンク特定結果

作成日時: 本ステップ実行時 / 担当: Benchmark Agent
取得方法: `read_website_content` によるJPX公式ページ直接読み取り（JS描画部分は r.jina.ai 経由レンダリングで静的HTML化して全リンク抽出）

---

## 1. 対象ページ（一次情報源）

| 項目 | 内容 |
|---|---|
| ページ名 | 規模別・業種別PER・PBR（連結・単体）一覧 |
| URL（日本語） | https://www.jpx.co.jp/markets/statistics-equities/misc/04.html |
| URL（英語） | https://www.jpx.co.jp/english/markets/statistics-equities/misc/04.html |
| ページ最終更新表示 | **2026/08/03 更新**（英語版: Update : Aug. 03, 2026） |
| レンダリング済みPublished Time | Mon, 03 Aug 2026 04:00:28 GMT |
| 更新サイクル | 毎月第1営業日 午後1時 更新予定 |
| 発行元 | 株式会社東京証券取引所 株式部データサービス室（databank-geppou@jpx.co.jp / 050-3377-7774） |

---

## 2. 【確定】最新データ時点

> ## 最新データ時点 ＝ **2026年7月末（2026年07月末現在）**

根拠:
- 2026年の月次テーブルで **1月～7月にExcelリンクが存在**、**8月以降は「-」（未掲載）**。
- ファイル名規約 `perpbrYYYYMM.xlsx` の最大値が `perpbr202607.xlsx`。
- ページ更新日 2026/08/03（＝8月第1営業日）に7月末分が公表されたことと整合。

---

## 3. 【確定】ダウンロード／閲覧用リンクURL

### 3-1. 最新（2026年7月末現在）— 本命
```
https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx
```
- 形式: Excel (.xlsx)
- 内容: 各月末現在の 市場区分別（プライム／スタンダード／グロース）× 規模別 × 33業種別 の PER・PBR（**連結ベース・単体ベース 両方**）

### 3-2. 2026年 月次バックナンバー（時系列レンジ算出用）
| 対象年月 | URL |
|---|---|
| 2026年1月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000k4id-att/perpbr202601.xlsx |
| 2026年2月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000ofbv-att/perpbr202602.xlsx |
| 2026年3月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000svf7-att/perpbr202603.xlsx |
| 2026年4月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt00000142v7-att/perpbr202604.xlsx |
| 2026年5月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001entg-att/perpbr202605.xlsx |
| 2026年6月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001iof6-att/perpbr202606.xlsx |
| **2026年7月末（最新）** | **https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx** |
| 2026年8月末以降 | 未掲載（"-"） |

### 3-3. 2025年 月次（前年同月比較・正常レンジ算出用）
| 対象年月 | URL |
|---|---|
| 2025年1月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000000eyis-att/perpbr202501.xlsx |
| 2025年2月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000000ybjd-att/perpbr202502.xlsx |
| 2025年3月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000014op5-att/perpbr202503.xlsx |
| 2025年4月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001963i-att/perpbr202504.xlsx |
| 2025年5月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001jra4-att/perpbr202505.xlsx |
| 2025年6月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001nrns-att/perpbr202506.xlsx |
| 2025年7月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc000001ryyo-att/perpbr202507.xlsx |
| 2025年8月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000022ifd-att/perpbr202508.xlsx |
| 2025年9月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/um3qrc0000026p4r-att/perpbr202509.xlsx |
| 2025年10月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt0000003a1o-att/perpbr202510.xlsx |
| 2025年11月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000busa-att/perpbr202511.xlsx |
| 2025年12月末 | https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000000g2os-att/perpbr202512.xlsx |

### 3-4. 補助資料（レンジ判定・定義確認に必須）
| 資料 | URL |
|---|---|
| **長期データ（総合）** Excel（長期の正常レンジ判定に有用） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/longrange-perpbr.xlsx |
| **PER・PBR計算要領（2024年2月1日）** PDF（算出定義の根拠） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/202402PERPBRHPj.pdf |
| 2013年～2019年 アーカイブ（PDF・Excel, ZIP） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/2013-2019(PDF&Excel).zip |
| 1999年11月～2012年 アーカイブ（PDF, ZIP） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/1999.11-2012(PDF).zip |
| お知らせ（2022年4月8日・市場区分見直し対応）PDF | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/oshirase.pdf |
| 【参考】市場区分見直し後のサンプルファイル（様式確認用） | https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq00000015r6-att/perpbr202111.xlsx |

### 3-5. 関連統計ページ（業種別ベンチマーク補完用）
- その他統計資料トップ: https://www.jpx.co.jp/markets/statistics-equities/misc/index.html
- 東証上場銘柄一覧（33業種コード付き）: https://www.jpx.co.jp/markets/statistics-equities/misc/01.html
- 市場別時価総額: https://www.jpx.co.jp/markets/statistics-equities/misc/02.html
- 業種別時価総額: https://www.jpx.co.jp/markets/statistics-equities/misc/07.html
- 株価平均・株式平均利回り: https://www.jpx.co.jp/markets/statistics-equities/misc/03.html

---

## 4. 後続ステップへの申し送り（重要・データ品質）

1. **JPX公表値は「加重平均」および「単純平均」であり、「中央値」ではない。**
   タスクが求める「業種別PER・PBR中央値」はこのExcelから直接は得られません。
   - 選択肢A: JPX値を「業種平均ベンチマーク」として提示し、中央値でない旨を明示
   - 選択肢B: 中央値が必要な場合は銘柄別データ（上場会社財務データ）から自前算出、または株探等の中央値掲載ソースを併用
   - いずれの場合も**推測値は使用しない**（不明時は「データ不足」と報告）

2. 対象業種（33業種分類における該当名称）
   - 機械 / 化学 / 電気機器 / 輸送用機器 / 銀行業
   （※「銀行」はJPX表記では **「銀行業」**。他に「証券、商品先物取引業」「保険業」「その他金融業」が別立て）

3. Excelは市場区分別（プライム／スタンダード／グロース／全市場）× 連結／単体 の複数シート構成のため、
   ベンチマーク提示時は **「市場区分」「連結or単体」「対象年月」** の3点を必ず併記すること。
   推奨基準: **プライム市場・連結・2026年7月末**。

4. 出典表記の標準形（他Agentへ提供時に必須）:
   > 出典: 日本取引所グループ「規模別・業種別PER・PBR（連結・単体）一覧」2026年7月末現在
   > (https://www.jpx.co.jp/markets/statistics-equities/misc/04.html), 取得ファイル perpbr202607.xlsx, ページ更新日 2026/08/03

---

## 5. DONE判定
- [x] 最新データ時点の明文化 → **2026年7月末**
- [x] ダウンロード/閲覧用リンクURLの明文化 → **https://www.jpx.co.jp/markets/statistics-equities/misc/t13vrt000001ranp-att/perpbr202607.xlsx**（＋バックナンバー19本、補助資料6本、関連ページ5本）
