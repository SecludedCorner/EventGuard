# Falcon／Singularity GUI 與官方 GitHub 研究

查閱日期：2026-10-28（台北）。EventGuard 比對基準：`f86254bb0393b606b1202b370efa18b35f649e8e`。
本頁是公開資料研究；工程入口仍為 [MAINTENANCE_GOAL](../../MAINTENANCE_GOAL.md)，驗證紀錄為 [EVIDENCE](../../EVIDENCE.md)。

## 結論與證據分級

優先借鏡的是「帶篩選條件的總覽 → 告警佇列 → 保留上下文的詳情 → 證據／歷程 → 受控動作」。這是設計推論，尚未證明 EventGuard 比任一產品更好。[F1] [F2] [S1]

- **官方文件**：能確認描述的介面／契約，不能證明本帳戶享有功能或實際效果。[F1] [F3]
- **廠商展示**：公開文章、圖片、白皮書及 tour 是廠商選定情境。舊圖保留原日期，不稱為目前所有租戶的畫面。[F2] [F4] [S1] [S2]
- **公開程式靜態查閱**：固定 SHA 能核查特定實作；本輪未下載、安裝、執行廠商程式或其測試。[G1] [G2] [G3] [G4]
- **正式主控台實測：未做**。沒有登入兩家帳戶；操作延遲、授權差異、鍵盤／螢幕閱讀器、資料完整性、偵測率及回應成效均未驗。

2026-10-21 SentinelOne 公告 ASOC，並描述資料管線、agentic investigation 與受控回應；本輪另核對目前 Hyperautomation 產品頁。這些新宣稱不能使 2024 Operations Center 展示自動成為 2026 正式環境驗收。Falcon 以目前 Developer Center 的詳情插槽／告警 API 語意交叉核對舊展示；未取得租戶 build 編號。[S3] [S4] [F1] [F3]

## 八個工作流程的可借鏡之處

| 面向 | Falcon 公開證據 | Singularity 公開證據 | EventGuard 設計取捨（推論） |
| --- | --- | --- | --- |
| 總覽 | Assessment dashboard 將 coverage、結果與 SLA 分開，可進入特定資產。[F2] | Overview 可縮小到告警及資產；目前 Hyperautomation 展示把執行量與歷程分頁呈現。[S1] [S4] | 首屏同時顯示「需處理事件」和「觀測缺口」，不做無依據的安全分數。 |
| 告警佇列 | SIEM 展示依 severity、log source、tags 篩選；不是 SDK 產生的偵測效果。[F4] | 統一告警清單有嚴重度、處置、分派、來源及分組。[S1] | 先改善現有三篩選與回清單位置；單機產品先不加入團隊分派。 |
| 篩選脈絡 | 詳情插槽接收 detection／host／case context，並不出現在清單層。[F1] | 文章示範以 File Hash／Asset Name 分組，再進入詳情。[S1] | 顯示有效條件、可清除、可返回；不可只篩當頁後聲稱全庫總數。 |
| 事件詳情 | detection、host、case、workflow execution 各有明確詳情入口。[F1] | Alert Details drawer 可進入關聯及事件搜尋。[S1] | 摘要、原觀測、保存調查、缺口、人的處置、投遞證據分層；不要先堆 JSON。 |
| 時間線／關聯 | 白皮書描述 Incident Workbench 的實體／程序圖及時間範圍。[F4] | Storyline 可連到 Event Search；Graph Explorer 展示資產與告警關聯。[S1] | 每個關聯標理由、時間窗與來源；缺穩定身分時保留 UNKNOWN，禁止從相近時間畫攻擊鏈。 |
| 來源健康 | 公開資產圖同時寫 Online 與 sensor operational and outdated；可用性不等於版本符合。[F2] | 此次公開展示不足以核實所有來源 denied／partial／stale 的正式 UI 規則。 | 七來源的狀態、新鮮度、最後成功及原因應同時可見；不能用連線成功掩蓋拒讀。 |
| 操作歷史 | Foundry 文件有 workflow execution 詳情入口；未核實完整產品稽核保存期限。[F1] | 告警 History 及 Hyperautomation 執行狀態／耗時／時間可追溯；Purple MCP 有 history 查詢。[S1] [S4] [G4A] | 人工處置歷程、調查修訂、程序活動分開；缺使用者身分不可杜撰稽核 actor。 |
| 受控回應 | Workbench 展示工作流程自動化，但不是本地執行授權。[F4] | 公開 Mitigation Actions 圖列 kill、quarantine、remediate、rollback；現行頁描述 human approval gates。[S1] [S4] | 保留空 allowed_actions；借鏡「範圍／前置／結果」資訊，不複製會改系統的按鈕。 |

## 實際看過的公開 GUI 圖像

只在瀏覽器檢視官方圖片，沒有保存或提交截圖；下列是觀察，不是互動可用性測試。

1. Falcon [資產詳情圖][F2I]（原文 2024-05-02）：左側摘要與健康判斷、右側 metadata，下方按領域分頁。Online 綠標與 outdated 警示並列，適合借鏡「狀態分軸」，但小字／低對比區域仍需另做可讀性驗證。
2. Singularity [告警佇列圖][S1I]（原文更新 2024-07-09）：上方時間／severity／status 條件，下方分組、多選與表格；動作選單會遮住部分列。EventGuard 可保留篩選脈絡，暫不引入批次敏感處置。
3. Singularity [處置對話框][S1M]：逐項動作說明及已選數量清楚；圖中多項預選不能成為 EventGuard 的預設授權。
4. [Hyperautomation 圖][S4I]（查閱時產品頁，圖內日期 2026-05）：Activity／Workflows 分頁、版本、動作數與執行結果分離。完成狀態仍須有可查證回條，不照抄展示中的綠色 Completed。

Falcon 白皮書文字與圖說可讀，但本機內嵌 PDF 檢視未成功顯示像素；未把它記成實際視覺檢查。公開 tour 頁已讀到說明，未執行嵌入式互動導覽或填表。[F4] [S2]

## 官方 GitHub：產品、SDK、示例不可混稱

以下 SHA 由公開 GitHub 頁面直接核對；封存是查閱時狀態，不由 commit 年代推定。授權欄只記儲存庫標示；未複製程式碼或新增依賴。

| 儲存庫／固定版本 | 查閱時狀態／授權 | 實際角色與可借鏡範圍 |
| --- | --- | --- |
| [CrowdStrike/falcon-digest][G1] `5f6f8bd8aebbbe7fb25386fb9519936c0dc91011`；tip 2026-08-03 UTC | Public，無 archived 標記；MIT | Python／Streamlit 儀表板示例，讀 Falcon API；需要 Falcon 憑證，AI chat 可另接模型。不是 Falcon 主控台或端點 sensor 原始碼。 |
| [CrowdStrike/falconpy][G2] `9c2c672a7bf31a7a187bc1308ea0708ffca444e2`；tip 2026-10-26 UTC；頁面列 release 1.6.6 | Public，無 archived 標記；Unlicense | 官方 Python SDK，研究 API 分層／錯誤回應；不是偵測引擎。release 與 main tip 不當成同一版本。 |
| [Sentinel-One/s1-integration-examples][G3] `215d853440c2d9038e09d4a5a71cbe61ce699f65`；tip 2025-06-12 UTC | 2026-10-27 archived／read-only；BSD-2-Clause；README 明示不提供正式支援 | root 列 API Browser、Lightweight Console、Nexus SDK；不能從目錄名稱推論有完整產品。 |
| [Sentinel-One/purple-mcp][G4] `a25a3831c8aea76e9897b6d22910c7c70c975a1c`；tip 2026-10-22 UTC | Public，無 archived 標記；MIT | README 定義為唯讀服務，需主控台 token／URL；查告警、事件、inventory，也可詢問 Purple AI。不是 GUI 或離線偵測器。 |

**修正初步判斷：**固定 G3 的 [lightweight-console 目錄][G3L] 只有三行 README，文字仍稱開發中；沒有可分析的 GUI 程式。不能稱已研究其分頁／元件或用它當現行主控台原始碼。API Browser／Nexus SDK 僅確認 root 的定位，本輪未執行也未審核其完整實作。

### 具體程式閱讀結果

- G1 [mcp_dashboard.py][G1D] 的 `SUB_TAB_MAP`／`render_scope_hint` 區分訂閱模組與 API scope 缺失／查證錯誤；`compute_sla_compliance` 缺可計算資料時回 None。值得借鏡「不可用原因」與「分母不足」呈現，不照搬其 SLA 閾值或分數。
- G1 [falcon_cache.py][G1C] 有每來源 pending/loading/done/error 與 TTL／is_fresh；但錯誤支線包含原始例外字串寫 log／cache。這是靜態觀察，不是漏洞判定；EventGuard 應保持固定錯誤碼及最小化資料，不移植該記錄方式。
- G4 [tools/alerts.py][G4A] 分開 list/search/detail/notes/history；`first` 有 1–100 邊界、cursor 與 filter 驗證，history 欄位允許 system event creator 為 null。值得借鏡分頁及未知 actor，不把已取得一頁叫完整歷史。
- G4 的唯讀承諾不等於不對外傳資料；其服務需要雲端主控台，Purple AI 與第三方 threat intelligence 也有另外的資料流。本輪沒有接線，沒有將任何本機事件送出。[G4]

## 資料可用性、隱私與比較界線

兩家正式 GUI 的調查價值依賴 sensor、資料湖、整合來源、授權模組及保留政策；EventGuard 的有限 metadata 無法靠改版面補出相同遙測。[F2] [F3] [S1] [S3]
公開圖的空欄位、成功標示不能證明產品在拒讀／斷線／時間漂移／跨來源衝突時的處理。未知處列未驗，不能宣稱廠商沒有處理，也不能宣稱 EventGuard 已勝出。
EventGuard 可驗證的方向是資料最小化、中文可讀、離線基本流程、逐條證據與缺口；正常監看不叫模型的限制繼續有效。這是產品選擇，不是同環境的安全性或效能勝負。
網頁不能鎖定產品 build；後續正式比較須有明確租戶／版本／模組／資料範圍與另行授權。此研究不授權帳戶、安裝、原生掃描、模型、系統處置或常駐遙測。

## 來源索引

所有來源查閱於 2026-10-28；動態頁面可能更新。固定 GitHub tree/blob 連結優先於預設分支。

[F1]: https://developer.crowdstrike.com/foundry/experience-capabilities/ui-extensions/
[F2]: https://www.crowdstrike.com/tech-hub/exposure-management/investigating-misconfigured-assets/
[F2I]: https://www.crowdstrike.com/wp-content/uploads/2024/05/femima4.png
[F3]: https://developer.crowdstrike.com/falcon-mcp/modules/detections/
[F4]: https://www.crowdstrike.com/wp-content/uploads/2024/10/Falcon-Next-Gen-SIEM-Unlocking-the-AI-Native-SOC.pdf
[S1]: https://www.sentinelone.com/blog/singularity-operations-center-unified-security-operations-for-rapid-triage/
[S1I]: https://images.contentstack.io/v3/assets/blt53c99b43892c2378/bltcfff6689b411830b/6a5666723a18f78ef8514de4/unified_alerts_3.jpg?format=auto&quality=90&width=2560
[S1M]: https://images.contentstack.io/v3/assets/blt53c99b43892c2378/blt0ad384028d856c54/6a566681732b9f46080d975b/unified_alerts_9.jpg?format=auto&quality=90&width=2560
[S2]: https://www.sentinelone.com/tour/
[S3]: https://www.sentinelone.com/press/sentinelone-brings-security-superintelligence-to-the-soc-with-singularity-asoc/
[S4]: https://www.sentinelone.com/platform/singularity-hyperautomation/
[S4I]: https://images.contentstack.io/v3/assets/blt53c99b43892c2378/bltb12df3fc9d45d099/6a2c600d38d9583e3cfb0355/M-11-immersive-large-card-hyperautomation-02.webp?format=auto&quality=75&width=2560
[G1]: https://github.com/CrowdStrike/falcon-digest/tree/5f6f8bd8aebbbe7fb25386fb9519936c0dc91011
[G1D]: https://github.com/CrowdStrike/falcon-digest/blob/5f6f8bd8aebbbe7fb25386fb9519936c0dc91011/mcp_dashboard.py
[G1C]: https://github.com/CrowdStrike/falcon-digest/blob/5f6f8bd8aebbbe7fb25386fb9519936c0dc91011/falcon_cache.py
[G2]: https://github.com/CrowdStrike/falconpy/tree/9c2c672a7bf31a7a187bc1308ea0708ffca444e2
[G3]: https://github.com/Sentinel-One/s1-integration-examples/tree/215d853440c2d9038e09d4a5a71cbe61ce699f65
[G3L]: https://github.com/Sentinel-One/s1-integration-examples/tree/215d853440c2d9038e09d4a5a71cbe61ce699f65/lightweight-console
[G4]: https://github.com/Sentinel-One/purple-mcp/tree/a25a3831c8aea76e9897b6d22910c7c70c975a1c
[G4A]: https://github.com/Sentinel-One/purple-mcp/blob/a25a3831c8aea76e9897b6d22910c7c70c975a1c/src/purple_mcp/tools/alerts.py
