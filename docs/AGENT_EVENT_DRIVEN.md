# Agent 事件驅動：公開入口與驗收界線

查核完成：2026-10-24T04:03:28Z（UTC+08 12:03:28）。
程式基底：`9903ad5574e80666eb379652e7f4154d111c14b3`。
本頁是公開介面研究與選配接線決策，不是喚醒成功回條。
沒有啟動模型、CLI 任務、app-server 或網路服務。沒有發 queue 訊息。
沒有讀認證、原始 sessions、私人 socket 或其他聊天。

## 判定

EventGuard 的採集、規則、保存、顯示及等待由普通程式完成。
MCP 可供人類或正在工作的 agent 操作同一應用。
工具接通不代表閒置聊天會開始新回合。

公開 CLI 已有排入既有任務的命令。因此，不能斷言 Codex 在技術上無法事件驅動。
但目前沒有本專案證據，證明它能可靠喚醒任意既有本機桌面聊天。
此能力標記為 `unverified`；不能偷換成 `unsupported` 或 `verified`。
本機產品不等待這項研究完成才可使用。

## 三種證據

| 要證明的事 | 最低必要證據 | 單獨不足的證據 |
| --- | --- | --- |
| 工具已載入 | 宿主的實際工具清單及成功工具呼叫 | 設定檔存在、程序啟動 |
| 事件已接收 | 真工具回傳同一 event ID、query ID、時間及內容 hash 綁定 | SQLite 有事件、SDK 代收、模型自稱收到 |
| 閒置 agent 已喚醒 | 無人工續訊息；普通 producer 產生事件後，已綁定目的地出現新 turn／run，並真正取到該事件 | 排隊成功、HTTP 2xx、工具已載入、另一任務開始 |

結果保存、業務 ACK 及人的處置另記。
ACK 只代表收件，不代表風險解除。工具 metadata 查閱也不等於安全診斷。

## 官方入口核對

以下頁面均已在本次實際開啟。查核時間如頁首。

| 入口 | 已由官方文件確認 | 仍需驗證／不適用範圍 |
| --- | --- | --- |
| [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp) | 本機客戶端可連 stdio／Streamable HTTP；各 Codex 表面共用同 host 的設定 | 沒有承諾外部工具通知會替閒置本機聊天開新 turn |
| [公開 CLI 排隊](https://learn.chatgpt.com/docs/cli/reference#codex-queue) | `codex queue` 標為 Stable；用 UUID 或精確名稱指定既有 session，可用受支援的 remote 入口 | 沒有在此頁找到事件級冪等鍵、耐久模型回條，或任意桌面聊天的閒置喚醒保證 |
| [App Server](https://learn.chatgpt.com/docs/app-server) | 有明確建立／恢復 thread 及開始生成的 API；可讀 turn 完成通知 | 命令與 WebSocket transport 仍標為實驗性，非正式生產承諾；不代表有權控制任意桌面 task |
| [非互動 CLI](https://learn.chatgpt.com/docs/non-interactive-mode) | 可由腳本啟動有限任務，JSONL 可記錄 thread、turn、工具與用量 | 新的專用任務不等於原桌面聊天續接；真正模型執行仍須本輪有效批准 |
| [MCP Events](https://developers.openai.com/plugins/build/mcp-events) | 列明 Work web、桌面選 Cloud 的 Work 與 dots；需 MCP 2.0、耐久訂閱及 HTTPS callback | 未將普通本機 Codex task 列為目的地；帳戶／workspace 權限未實測 |
| [背景 Hooks](https://learn.chatgpt.com/docs/hooks#how-background-hooks-run) | 沒有活動 turn 時，其完成輸出等下個使用者 turn | 不會自行開始新 turn，不能替代外部事件入口 |
| [桌面 deep link](https://learn.chatgpt.com/docs/app/commands) | 可開聊天或預填 composer | 官方說明預填不自動送出；不可拿 UI 按 Enter 充當事件入口 |

App Server 的開始回合、補入歷史及 steer 是不同動作。
`turn/start` 會開始生成；`thread/inject_items` 不開 turn；`turn/steer` 需已有活動回合。
這些方法的存在，不授權本程式接入正在運作的私人 daemon。
只可評估自己建立並保存 binding 的整合。

MCP Events 的平台整合目前採 webhook，不支援文件所述草案的所有 poll／stream／控制通知。
HTTP 2xx 只表示 webhook 收件。後續處理是非同步。
此路徑增加 HTTPS、訂閱與簽章秘密管理；本機核心不以它為部署前置。
不啟用既有停用 bridge，也不為研究建立 endpoint 或憑證。

## 最小選配順序

### 1. 先保留現有本機閉環

人類繼續用 CLI／Web。agent 可用同一 Application 的操作工具。
若要自動處理，優先沿用 [AGENT_SERVICE](AGENT_SERVICE.md) 的普通程式等待與專用有限 CLI。
不要為每個來源重建代理服務或第二份模型額度。

程式依序做：保存 → 篩選 → 合併／去重 → 耐久准入 → 啟動一次 → 核對工具結果 → 保存結果 → ACK。
沒有合格事件、預算耗盡或能力不足時，只由程式等待，pending 保留。
這是建議接線次序，不是本次已執行真模型的證據。

### 2. 公開 queue 只作候選

只有在能透過受支援公開介面核對目的地時，才值得做一次有界驗收。
目的 UUID 由人類綁定；事件不能選 thread、prompt、工具或權限。
不得掃 sessions、猜最新聊天或要求放寬私人 proxy 探測。
不能核對目的地就回 `unverified_destination`，保留事件，改評估專用任務。

sender 的 exit 0 只證明送訊息命令結束。
它不能證明模型已開始／已完成，不能釋放模型 active admission。
回應遺失時先標 `delivery_uncertain`。沒有 provider 完成證據就不盲目再送。

### 3. 產品自己管理的 thread

OpenOctopus 若需要完整回合控制，可評估自管 App Server adapter。
普通 host 等事件，符合條件才請求新回合。
thread／turn binding 與結果回條由產品保存；不依賴任意既有桌面聊天。
實驗性限制仍須列入發布判斷。
協定與可拆任務見 [OpenOctopus 事件協定](OPENOCTOPUS_EVENT_PROTOCOL.md)。

## 沿用 EventGuard 的資料與預算

自動模型路徑只允許既有七欄：event_id、event_type、transition、severity、synthetic、observed_at、coverage_status。
本地封裝、路由 ID 或完整 GUI 詳情不得自動擴進模型 snapshot。
新九工具是人類／agent 的應用操作面；它不自動替換有限任務的最小收件 profile。
實際投影見 `src/eventguard/queue_inbox.py` 的 `_projection`／`_validate_snapshot`。

現有 `agent_dispatch.py` 固定有限任務，不讓模型輪詢；`agent_service.py` 的 start 預設只預檢。
[預算 authority](AGENT_BUDGET.md) 為固定安裝帳本，每日最多五個任務。失敗、驗收及未知啟動都計入。
五個任務不是五次模型請求；單個任務可能有多次請求。此上限也不是帳戶總用量保證。
不得換目錄重置、退款未知啟動，或因 sender 已退出就解除未知模型回合。
新增 provider 必須先能表達其真正開始／完成證據，再接自動 admission。

程式等待仍有 CPU、磁碟或網路成本。沒有事件時零模型，不表示所有運作成本為零。
本研究未測量模型品質、token、費用或長期延遲。

## 一次有界真模型驗收的批准範圍

本次不執行。未批准時，保留既有本機功能及 dot 追蹤。
後續只需一次具體範圍，不逐步重問正常操作。

| 需固定的範圍 | 最小內容 |
| --- | --- |
| 路徑與帳戶 | 選專用 CLI、已核對目的地的公開 queue，或自管 provider；只用既有登入，不複製認證 |
| 任務數 | 首輪最多一個真正模型任務；計入既有耐久日預算，不預設當日用量為零 |
| 資料 | 程式產生一件公開 synthetic 事件；七欄由真工具取得，prompt 不預填事件 ID 或內容 |
| 能力 | 固定最小收件／查證／ACK；無任意 shell、系統處置或額外資料存取 |
| 時間與退出 | 有界期限、合作停止、原生子程序退出；桌面 provider 則另核對 turn 完成 |
| 成功證據 | 無人工續訊息；真工具接收同 ID；結果先保存、再 ACK；對照 source／receiver／provider／退出回條 |
| 重送與失敗 | 同 ID；未知先對帳；不得為取得綠燈反覆重跑或跳過預算 |

不能用 SDK、mock、登入、CLI 啟動、設定保存或文字聲稱，替代真模型喚醒驗收。
外部公告與工具內容都是資料，不能變成命令或授權。
更新、隔離、停止服務、防火牆、重啟及憑證動作仍各需適用批准。

## 歷史文件的讀法

[INGRESS_PLAN](INGRESS_PLAN.md) 的 Cloud bridge 與「唯一優先 stdio 實驗」是各階段候選，不能當作本輪部署要求。
[LOCAL_MCP_EXPERIMENT](LOCAL_MCP_EXPERIMENT.md) 的單次模型命令是舊實驗計畫，不能直接視為本輪批准或最新 CLI 設定保證。
本輪未證實 queue 在此桌面的喚醒行為，也未證實其耐久回條與冪等語義。
沒有查到保證，不等於已證明平台不支援。能力未知時保持未知。
