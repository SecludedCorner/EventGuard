# 公告來源與解析契約

本輪查核日：2026-10-23。有限官方查核窗截至 `2026-10-23T14:21:47Z`。這不是持續監看結果。

後續以新程式在一般使用者做有限實抓。RustSec 三份 raw、Rust feed、uv API、CVE API 成功。ZDI 首次因大小被拒；調整有界 4 MiB 後成功，六個 ID 齊全。LKML／kernel git 為 TLS 驗證失敗，Debian 本次逾時。沒有繞過。實際時間、輸出、失敗及修復見 [EVIDENCE](EVIDENCE.md) 與本機 `reports/advisory-tracker-001/public-fetch*.json`。

程式：`src/eventguard/intelligence/sources.py`。設定：`config/advisories.json`。

## 來源

| 來源 | 實際入口 | 解析方式 | 本輪觀察 |
| --- | --- | --- | --- |
| ZDI | [Upcoming](https://www.zerodayinitiative.com/advisories/upcoming/) | 有界 HTML table | 官方頁可讀。六個追蹤 ID 均列出 |
| LKML | 設定中的三封精確 lore 郵件與三個 lore 搜尋 | 有界 HTML；只記 ID 出現 | 沿用已發現的原始 URL。新程式是否可讀，須看本輪 fetch 結果 |
| kernel git | [33774 候選 commit](https://git.kernel.org/pub/scm/linux/kernel/git/linkinjeon/smb.git/commit/?id=68f410faedaf6ee74d81e574733c50ebcc1bd8ed) | 有界 HTML；不由標題推定修補 | 本輪網頁工具無法取得內容。對應與合併狀態仍未知 |
| Debian | [linux](https://security-tracker.debian.org/tracker/source-package/linux)、[connman](https://security-tracker.debian.org/tracker/source-package/connman) | 有界 HTML；只找追蹤 ID | 官方頁可讀。頁面套件版本不是六案的修補對應 |
| RustSec | 三份官方 advisory-db Markdown／TOML | Python `tomllib`；保留 Cargo requirements | 0381、0382 官方 raw 可讀；三份官方公告頁可讀 |
| OSV | [GET /v1/vulns/{id}](https://google.github.io/osv.dev/api/) | JSON；保留 SEMVER／ECOSYSTEM／GIT ranges | 0381 的官方 RustSec 頁提供 OSV JSON 連結。其他 API 請求本輪網頁工具不可讀 |
| Rust／rustup | [官方 feed](https://blog.rust-lang.org/feed.xml)、[rustup 1.29.2](https://blog.rust-lang.org/2026/10/20/Rustup-1.29.2/) | Atom／RSS；只記公告存在 | feed 被網頁工具辨識為 XML，不能在該工具顯示。公告正文可讀 |
| Cargo／rustup／uv | 公開 repository security advisories API | JSON；保留 vulnerable range 與 patched versions | [GitHub 官方 API 契約](https://docs.github.com/en/rest/security-advisories/repository-advisories)存在。API 是否能直接取得，須看 fetch 結果。未新增 token |
| CVE | [CVE Services API](https://cveawg.mitre.org/api-docs/) | CVE JSON 5；保留自訂版本條件 | CVE111943 的 API 本輪網頁工具不可讀；CVE 網頁只回 JavaScript shell。不能當成沒有記錄 |

上述 URL 都是實際站點或已公開 API。設定不包含臆造的 vendor API。來源失敗保留快取。不得改寫成「沒有漏洞」。

首次直接 Python HTTP 試讀限五個公開 URL：Rust blog feed、rustup tag feed、uv API、Cargo API、OSV0382。五個均回 `URLError`。只輸出異常類型，未保存代理錯誤全文。這是本環境的傳輸限制。不是來源健康或 adapter 成功的證據。最後整合驗證記錄若有新的一次實抓，以該記錄為準。

有意義的 ZDI 重試：`2026-10-23T14:30:42Z`，一般使用者 HEAD 回 200，`Content-Length=2403491`。舊 2 MiB 限制因此拒絕正常頁面。改為只有 ZDI 配置 4 MiB，程式絕對上限 8 MiB。之後單次 GET 真正解析出六個指定 ID，32005 為 connman；exit 0。精簡回條：`reports/advisory-tracker-001/public-fetch-zdi-retry.json`。未覆寫初次失敗。這證明本次官方頁與 adapter 契約，不能升格為長期穩定或本機漏洞驗證。

## 案例事實與界線

ZDI 官方 Upcoming 列出 33549、33774、33367、34068、34076 的 vendor 為 Linux。32005 為 **ConnMan**。前五項通知廠商日為 2026-10-21；32005 為 2026-10-19。這些日期不是首次公開、修補或安裝日期。清單未提供足夠版本／commit／CVE 對應。解析器保留 unknown。不上推為已確認本機受影響。

| 官方公告 | 已確認的元件／修補條件 | 仍需本機證據 |
| --- | --- | --- |
| [RUSTSEC-2026-0381](https://rustsec.org/advisories/RUSTSEC-2026-0381.html) | `webpki-roots`；patched `>=1.0.10`。`0.26.11` 是 wrapper，須另查 1.x parent | 同時盤點所有 resolved 版本。確認實際部署產物、TLS backend、trust roots |
| [RUSTSEC-2026-0382](https://rustsec.org/advisories/RUSTSEC-2026-0382.html) | `rustls-webpki`；patched `>=0.103.16, <0.104.0-alpha.1` 或 `>=0.104.0-alpha.8` | 設定的 trust anchors 是否讓相關路徑成立。不能只看 rustc |
| [RUSTSEC-2026-0383](https://rustsec.org/advisories/RUSTSEC-2026-0383.html) | `webpki-root-certs`；patched `>=1.0.10`。同樣需查 wrapper parent | 已鎖定相依不等於已編入與已部署 |
| [uv GHSA-hq85-5cpj-mr62](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62) | 官方列 `<0.13.4`、patched `>=0.13.4`；預設 bundled CA 是相關條件 | system/custom certificates 需另查。選用它們不是自動安全證據 |
| [rustup 1.29.2](https://blog.rust-lang.org/2026/10/20/Rustup-1.29.2/) | 官方表示更新相關 TLS 相依以處理 CVE-2026-111943 | 安裝與執行身分仍須新鮮本機證據。本輪不執行 rustup |

三個 RustSec 公告明列 CVE-2026-111943 別名。uv 官方頁沒有給 CVE。程式不因同一事件背景自行替 uv 建立 CVE 別名。未證實有在野利用；`exploitation=unknown`。公開 PoC、實驗室與在野攻擊不可互換。

## 共同契約

`load_config(path)` 讀取 JSON。錯誤設定明確失敗。不暗中改用預設來源。預設 `inventory.paths=[]`。沒有廣域掃描。

`namespace` 僅接受 live／test。每個來源可設定 `enabled`、頻率、資料過期秒數、`failure_threshold` 與 `important`。容量及冷卻位於 `storage`。事件觸發開關及嚴重度位於 `rules.enabled_reasons`、`rules.severity`。原因與嚴重度均為白名單，不是任意運算式。預設最高為 high。不附處置授權。

`fetch_source(source, previous=None, now=None, opener=None)` 做一輪有界抓取；GitHub 可含分頁及一次固定 repository ID 查核，其餘 adapter 維持單次 GET。回傳：

```text
status: success | partial | not_modified | failed
records: 正規化公告；partial 僅含可獨立驗證的子項，失敗與 304 為空
item_errors: 有界項目索引與固定原因碼
etag / last_modified / content_hash / fetched_at
error_code / retry_after_seconds
```

呼叫端保存快取、失敗次數與下一次時間。304 必須已有 body hash。不得拿空 records 清掉舊公告。Retry-After 支援秒數與 HTTP 日期，上限 24 小時。失敗不在 adapter 內迴圈重試。

每筆公告保存 ID／別名、元件、生態、來源 URL、發布／更新時間、affected、fixes、conditions、evidence、confidence、withdrawn 與 exploitation。擷取時間及 body hash 位於來源回條。不是完整公告鏡像。不保存原始 HTML、錯誤全文或 exploit。

RustSec patched/unaffected 是 Cargo requirement 清單。清單為 OR。同一字串以逗號連接為 AND。不可按字串排序。CVE custom version 欄位只保存型別化條件；無可靠比較器就維持未知。

ZDI 的 stage 為 `reported`。fix 的 `released` 不等於 installed／running。一般 HTML adapter 只證明 ID 出現。不同 ID 同時出現在一頁或同一 feed entry，不是 alias 證據。兩者均逐 ID 建記錄。只有 OSV／RustSec／GitHub 的明確結構化別名欄可合併。無法建立 ID、marker 消失或 table 格式變更，回傳原因碼。任何一個指定 ZDI ID 缺漏均回 `tracked_ids_missing`，不宣稱完整。追蹤 ID 從 Upcoming 消失也不代表撤回或已修；須查 Published 與原始公告。

## 邊界

- HTTPS。無 credential URL。拒絕 localhost、非公開 IP literal、非標準 port、控制字元與跨來源 redirect。
- 不送 token。不新增憑證。沒有 shell、子程序、模型、套件安裝或 toolchain 更新。
- 單次 timeout 1–30 秒。讀取檢查總時限。預設 body 上限 2 MiB。單一來源可明確配置至 8 MiB；ZDI 為 4 MiB。每輪最多 512 筆、64 個來源。有限內文不當成程式。
- GitHub `max_pages` 預設5、範圍1–8，所有頁及一次固定 repo metadata GET共用總bytes/期限；最多max_pages+1 GET。必須從named首頁開始，根據[官方分頁Link契約](https://docs.github.com/en/rest/security-advisories/repository-advisories#list-repository-security-advisories)處理forward `after`或連續page，不自行構造cursor。canonical numeric路徑須metadata的id/full_name/public一致；固定origin/path/filters/page-size，拒redirect、循環、before／page+after混用與任意path。
- 有好子項但後頁、mapping、頁數或bytes失敗為partial；無好子項為failed，均不宣稱完整。相同GHSA相同內容穩定去重，衝突撤下本輪該斷言並標partial。成功清單的hash包含有序頁長度與bytes；部分cache不覆寫last-good／success時間。
- GitHub不送單頁ETag／Last-Modified conditional，304為unexpected_304；完整success顯式清舊validators。max_pages屬資源政策，預設值遷移不使legacy binding失效。同步urllib有deadline檢查，不等於已證明OS blocking syscall可硬即時中斷。
- 真環境兩頁smoke通過仍因頁數上限維持partial，未保存正式cache；有限實抓與完整來源、主機適用性、持續健康分開，詳見最新EVIDENCE。
- HTML 有格式變更風險。LKML／kernel git 的 anti-bot 或拒讀不繞過。保留失敗與資料新鮮度。
- 上游內容可能包含指令式文字。它只能成為本機資料。不能取得命令或處置權限。

離線契約測試在 `tests/test_intelligence_sources.py`。fixture 明示 synthetic。它們不證明 Windows 主機受影響、真模型已接收或長期追蹤已通過。

## NVIDIA CSAF 增量（2026-10-24）

`nvidia_csaf` 只接受 `raw.githubusercontent.com/NVIDIA/product-security` 的精確 JSON 路徑。
設定範例預設 disabled。沒有新增全 repo 發現、廣域下載或本機產品掃描。
固定查核 [commit 2c945405](https://github.com/NVIDIA/product-security/tree/2c9454053cf5d2942d4f361d455c749b725fe920)。
[官方樣本 5903](https://raw.githubusercontent.com/NVIDIA/product-security/2c9454053cf5d2942d4f361d455c749b725fe920/2026/5903/5903.json)
為 CSAF 2.0，CVE-2026-65142。產品 ID、版本標籤、tracking revision、發布／更新時間及修補階段保留。
`0-0.43.0` 是廠商標籤，不當通用 SemVer；`0.44.0` 可用不代表本機已安裝或正在運行。
未知本機產品／版本維持 unknown。

好子項與壞子項隔離。partial 保留有效子項，另存固定錯誤；不得當 success。
最近完整 cache、ETag、內容 hash 與成功時間不被 partial 覆寫。
partial 後強制完整擷取；304 不能洗成完整成功。失敗保留 last-good，但當前適用性維持未知。
單純標題、格式、revision 或擷取時間變化不產生風險事件。
CSAF 2.0 無標準 withdrawn 狀態。缺項、失聯、disputed 或 known_not_affected 都不當作撤回。

官方固定樣本僅在記憶體解析一次。沒有保存全文或把公告複製入 fixture。
同來源 SHA256 相符只證明位元組一致，不是獨立真偽驗證。
固定 tree 未見 LICENSE；公告另有 NVIDIA 著作權與使用條款。本專案只附自寫 synthetic fixture。
本輪命令、結果與界線見 EVIDENCE。有限樣本可讀不等於長期追蹤或主機適用性已通過。

Web「資安公告」、Application status 與事件詳情使用有界公開投影。
只讀現有 DB。缺資料不建空庫，namespace 不符則 blocked。
來源失效／partial／過期維持明確原因，不把歷史排除當成當前安全。
十類自寫對抗文字只作資料；不引入 garak runtime、API key 或 GPU。
