# OpenOctopus：跨應用事件入口需求

> 保存註（2026-10-28）：以下「目前／本輪／未提交」與政策均指原研究日期及固定基準，不是現行能力、授權或驗收。現況以 [STATUS](../../../STATUS.md) 與 [HANDOFF](../../../HANDOFF.md) 為準。本頁 reports 連結是「本機證據、不隨repo提供」；本次未讀取或上傳 reports 內容。

研究時間：2026-10-24 02:10 UTC+08。狀態：設計提案。未實作於 OpenOctopus，未做真模型驗收。

## 1. 結論

OpenOctopus 應把「等事件」做成普通程式能力。事件先保存。程式做訂閱、篩選、合併、限額及路由。有合格事件才啟動 agent 回合。沒有事件時，模型請求數為零。

事件入口是 host 核心能力，應屬於共用 Rust 核心。建議由普通 Rust host 等 SQLite／IPC，再做確定性 admission，最後交給自管 agent 任務。Iced 與 Web 讀取同一份狀態，呼叫同一份型別化操作 API。每個應用只實作 producer adapter。不要為每個來源新增一套 agent、訊息代理或雲端服務。

先支援 OpenOctopus 自己管理的任務。接管任意 Codex 桌面聊天屬於不同能力。能力未證實時顯示 `unverified` 並阻擋啟動；明確不支援時才顯示 `unsupported`。不能改用私人 control socket 或 session 檔案補上。

## 2. 已知與未知

來源敘述：研究當時經授權唯讀參考 OpenOctopus 整合任務的一般進度摘要；不保存聊天名稱、UUID 或內部連結。本研究未獨立編譯該外部專案。

| 項目 | 證據與判定 |
| --- | --- |
| 桌面方向 | 2026-10-24 的正常 `read_thread` 摘要表示：Iced 獨立桌面套件共用 Rust 核心，延續 Web 操作設計。這是該任務的進度陳述；本研究未獨立 checkout 或編譯。 |
| 任務、對話、設定及工具接頭 | 同一摘要提到既有整合工作。本研究不把進度陳述升格為已驗證 API 契約。 |
| 完整 MCP 與演化整合 | 摘要仍有候選修正與驗證工作。不能據此宣稱已有事件訂閱或喚醒。 |
| 共用事件入口、耐久 Inbox、事件喚醒 | 未從已讀摘要取得實作證據。本文列為需求。 |
| 任意既有 Codex 桌面聊天的外部喚醒 | 未驗證。MCP 工具可呼叫，不等於閒置聊天可自動啟動新回合。 |
| EventGuard 接收契約 | 本機程式碼已讀。基底 `008a931121f03c1ceaa1abb6f26cbe08abf3bf48`。不代表本研究啟動過真 agent。 |

只讀指定聊天的正常工具摘要。不讀 raw sessions、登入檔或憑證。不列其他聊天。不向該任務發訊息。本文件不保存私人對話、命令或工作路徑。

## 3. 能直接沿用的 EventGuard 契約

| 現有能力 | 本地來源 |
| --- | --- |
| 精確七欄模型 snapshot | `src/eventguard/queue_inbox.py:84`、`:95` |
| 耐久收件；重讀沿用同一事件 | `src/eventguard/queue_inbox.py:467` |
| query 綁定 event ID 與 payload hash | `src/eventguard/queue_inbox.py:501` |
| 先保存結果，再 ACK；ACK 可恢復且冪等 | `src/eventguard/queue_inbox.py:547` |
| 固定短任務；不得模型輪詢；不接管桌面聊天 | `src/eventguard/agent_dispatch.py:41` |
| 驗證工具回傳、ACK 及退出證據 | `src/eventguard/agent_dispatch.py:354` |
| 安裝級每日五次與跨程序 authority | `src/eventguard/agent_budget.py:24`、`:27`；[預算契約](../../AGENT_BUDGET.md) |
| pending、未知退出不得清理；滿載明示背壓 | [保留政策](../../STORAGE_RETENTION.md) |

模型只取得：`event_id`、`event_type`、`transition`、`severity`、`synthetic`、`observed_at`、`coverage_status`。不得加入產品名、路徑、PID、URL、原始證據或事件全文。

`query_evidence` 目前只回保存的最小 snapshot。回傳明示 `snapshot_only=true`、`system_query_executed=false`。ACK 的 `reviewed_metadata` 不代表診斷。結果固定 `incident_conclusion=not_assessed`。不能用更強的結果名稱包裝同一份資料。

OpenOctopus 接線先當 adapter。不要另造 EventGuard outbox、刪原帳本或繞過原每日限額。若未來需要更多證據，先提出獨立的型別化查詢能力與授權差異。

## 4. 核心分層

```text
應用 producer → 原應用 durable outbox → adapter → 共用 durable Inbox
                                                     ↓
                       無模型 admission ← Subscription 與綁定 scope
                             ↓
                      provider adapter → 自管 agent 任務
                             ↓                  ↓
                  退出／用量回條     query → 保存結果 → ACK
                             └──────────┬───────┘
                                同一審計與 UI 狀態
```

本機優先。首版可用受控本機 IPC 與嵌入式資料庫。若使用 loopback HTTP，必須檢查來源、身分、Host、Origin、大小與速率；不能把「來自 127.0.0.1」當作授權。遠端連線是另案，不能默認開放。

## 5. 必備介面與語義

以下名稱是提案，不是目前可執行命令，也不是已發布標準。

| 介面 | 必須做到 |
| --- | --- |
| `capabilities` | 回協定版本、producer、儲存限制、投影版本、可路由目的地、可用查詢、喚醒模式與證據等級。 |
| `subscriptions/create` | 人類建立持久訂閱。固定來源、namespace、類型、嚴重度、去重與冷卻政策、目的任務範圍、期限及批准版本。 |
| `subscriptions/pause/resume/delete` | 暫停先停新 admission。保留 pending 與已啟動任務狀態。刪訂閱不代表刪原事件或撤回已啟動回合。 |
| `events/submit` | 驗證後先耐久保存。成功回條只表示 `persisted`。容量或寫入失敗時拒絕，不回成功。producer 保留原 pending。 |
| `events/status` | 區分已保存、待路由、已啟動、已接收、結果已存、已 ACK、未知退出及人工處置狀態。 |
| `inbox/receive/query/ack` | receiver 僅能取得已綁定事件。query 不能接受任意命令。結果耐久成功後才 ACK。 |
| `runs/status/reconcile` | 核對 attempt、實際 provider request／run ID、用量及終止證據。不得以鎖到期或 PID 不存在推定任務已退出。 |

共用入口的內部 envelope 可以含 `protocol_version`、`producer_id`、`installation_id`、`subscription_id`、`namespace`、`event_id`、`payload_hash`、`projection_version`、`received_at`、`correlation_id`。這些欄位用於程式路由與審計，**不得自動傳進模型 snapshot**。

同一 `(producer_id, installation_id, namespace, event_id)` 加相同 hash，重送須回原收條。同主鍵不同 hash，回身分衝突並保留雙方證據。不能覆寫原事件。相同事件可有不同訂閱的投遞，但模型任務與 ACK 計數須可區分。

原應用 outbox 的保存回條、OpenOctopus Inbox 收條、模型工具收件、來源 ACK 是不同階段。不能把入口的 HTTP 200 或 `persisted` 回條當成 agent 已收到。首版 EventGuard 仍保留「query／result 後 ACK」原契約。

租約使用 attempt ID 與 fencing token。租約過期可阻擋舊 owner 寫入。它不能證明舊模型或程序已停止。未知退出先阻擋同事件的新啟動，等待可核對的回條或明示人工調解。保證至少一次與冪等處理；不承諾 exactly-once。

## 6. 無模型 admission

每次事件或狀態變更只執行普通程式。依序核對：

1. 事件 schema、來源身分與內容 hash。
2. 訂閱存在、未暫停、未過期，且範圍匹配。
3. 目的任務由本 host 管理，或 provider 明確支援該綁定。
4. 人類批准版本、資料投影與工具權限仍有效。
5. 重複、合併、冷卻、優先級及並行上限。
6. 耐久每日預算、每事件上限及未知退出閘道。
7. 預留結果、ACK 與退出回條所需容量。
8. 同一交易保存 admission 與 launch intent，才可要求 provider 開始。

未通過時保存固定原因碼與下次程式重試條件。不要叫模型判斷能否呼叫模型。無事、暫停、冷卻、預算不足及來源未就緒，模型啟動數都為零。

程式可使用本機通知、條件變數或有界資料庫檢查。HTTP 來源定時抓取也可由程式執行。這些都不需要模型定時醒來。設定檢查週期不代表設定 AI 排程。

## 7. Provider 與任務綁定

`ProviderEventAdapter` 至少提供 `capabilities`、`start_turn`、`observe_run`、`cancel_owned_run`、`reconcile`。每次啟動保存 provider、adapter 版本、策略快照、批准範圍、請求 ID、回合 ID 與起迄時間。

provider adapter 必須可替換。切換須明示成本、目的任務、工具與資料範圍。主要 provider 不可用時，保留事件並顯示 blocked。不得暗中改送另一個模型、CLI 或聊天。若自管 app-server 的成熟度不符合產品要求，可先選官方 CLI 短任務 adapter；這是明示產品選擇，仍須獨立驗收。

| 目的地 | 首版要求 |
| --- | --- |
| OpenOctopus 自管新短任務 | 優先交付。新任務只取得固定投影、固定工具與固定終止條件。完成後退出。 |
| OpenOctopus 自管既有任務 | 人類明確綁定。閒置時可啟動新回合。活動時採持久排隊，預設不打斷。是否合併或 steer 必須有明確策略。 |
| Codex CLI 短任務 | 可做獨立 adapter。先沿用既有 EventGuard 入口、有限預算與退出核對。不能宣稱續接桌面聊天。 |
| 自管 Codex app-server thread | 只有 host 自己建立或獲明示控制權的 thread 可用。先驗協定版本及能力。不能據 thread ID 推定控制權。 |
| 任意既有 Codex 桌面聊天 | 能力未證實時顯示 `unverified` 並阻擋；確認不支援才用 `unsupported`。事件保留，交人類處理。不得讀私人 session 或借未記載 socket 注入。 |
| ChatGPT／dot 事件訂閱 | 獨立 provider 能力。需實際可用的訂閱、回呼、授權與端到端證據。不能等同本機 Codex 桌面功能。 |

固定 prompt 是應用設定。外部公告、事件、名稱或工具回傳都不能修改 prompt、工具權限、目的 thread 或批准範圍。

## 8. 預算、停止與恢復

EventGuard 原每日五次不可被 OpenOctopus adapter 繞過。兩個產品的帳本不能各自發五次再宣稱共用同一上限。首版由 EventGuard 原 authority 決定其實際模型 admission；OpenOctopus 只路由與顯示。日後若改為共用 authority，必須先訂遷移、歷史用量與不可重置規則，再停用舊啟動入口。

OpenOctopus 可另有全域或 provider 上限。多層限額須使用同一不可重播的 admission token，並保存兩側狀態。任何一側未確認，不得直接再開模型。失敗、取消、驗收與不確定啟動都計入。ACK、換目錄及重開程式不退款。

停止使用兩個控制。`pause` 停新任務，保留採集與事件。`stop` 停本 host 的背景處理，先合作結束自管任務。未確認退出顯示 unknown。不碰外部程序。Windows 自管子程序須在執行前放入私有 Job。寬限後若終止，只限自管 Job，並記錄 force 與原因。

程序重啟先回放 Inbox、launch intent、原 provider ID 與結果。先做 reconcile，再接新工作。不能用重啟重新發一張空預算或重新送同一啟動。host 停機期間事件保留於 producer。恢復後補收，並顯示監看缺口。

## 9. 人類與 agent 共用可見狀態

下列是 UI 與 API 的 MUST 狀態。可顯示中文名稱，但不得省略語義：

| 狀態 | 意義 |
| --- | --- |
| `persisted` | 事件已在指定儲存端耐久保存。沒有模型收件證據。 |
| `ready` | 訂閱與無模型 gate 已通過，可進入 admission。 |
| `deferred` | 冷卻、配額或政策暫緩。事件仍保留。 |
| `launch_pending` | 已保存 admission／啟動意圖。可能尚未啟動，也可能回條未到。 |
| `running` | 已核對實際 provider 回合／自管程序身分。 |
| `result_saved` | 結果已耐久保存，未必已 ACK。 |
| `ACKed` | receiver 收條已核對。不是風險結案。 |
| `unknown_exit` | 缺完整終止證據。不能假設已停止或自動再啟動。 |

這些狀態按事件投遞、任務與人工處置分開保存，不是單一線性欄位。某任務可已 ACK，卻仍是 unknown_exit。UI 必須同時顯示兩者。

Iced、Web 與 CLI 至少顯示：

- 訂閱來源、綁定目的地、資料範圍、啟用／暫停與到期時間。
- 最後來源活動、最後成功連線、資料新鮮度與失敗原因。
- pending、cooldown、blocked、容量與每日剩餘額度。
- 最近進度、admission、provider 回合與工具收件時間。
- 結果保存、ACK、自然退出、強制結束與未知退出。
- 模型請求數、任務數、可取得的 token／費用；缺資料顯示 unknown。
- 人工處置狀態。ACK、已讀、已處理與風險修補分開。

人類可查事件、查已授權證據、暫停、重試符合條件的工作及標示處置。人類與 agent 使用同一型別化 API 及能力閘道。授權範圍仍可不同。GUI 不得出現假成功。外部 adapter 故障不阻擋本機採集、保存與人工查看。

## 10. 最小交付順序與驗收

| 批次 | 交付 | 完成條件 |
| --- | --- | --- |
| 1 | 純 Rust 核心 Inbox、Subscription、CLI／GUI 狀態；fake provider | 無事件零呼叫；重送無重複收條；改 hash 衝突；寫入失敗與滿載不丟 pending；重啟可恢復。明示 fake。 |
| 2 | EventGuard adapter；固定七欄與原 authority | generated／persisted／received／queried／result／ACK ID 集合逐步可對照。驗收不初始化正式預算，不改 dot。 |
| 3 | 自管 provider adapter；啟動與停止治理 | 並行不超額。ACK 前退出可補收。結果落盤後 ACK 失敗可補完。未知退出不重啟。所有子程序有退出／殘留證據。 |
| 4 | 有限真模型驗收 | 當次另批准。無事件觀察期模型任務零；合成事件真正觸發新短任務；實際工具 receive→query→結果耐久→ACK；自然退出，無殘留。不得以模型文字或 JSON 檔冒充。 |
| 5 | 長時與多應用 | 24 小時量測 CPU、RAM、handles、DB 大小及請求數；事件突發、公平性、背壓與恢復。短測不能升格為長時通過。 |
| 6 | 選配既有聊天與遠端 provider | 只有能力、授權與官方契約都確認後才加入。每種 provider 獨立驗收，不把一條成功當全平台支援。 |

必要故障矩陣：入庫前／後中斷、admission 前／後中斷、OS create 回條遺失、provider 已接收但本機未存 ID、工具接收前／後中斷、結果保存失敗、ACK 回覆遺失、時鐘回退、額度耗盡、磁碟滿、訂閱撤銷、權限縮小、來源過期與惡意指令式事件。

所有真測要區分傳輸接受、agent 真收件、agent 真啟動、診斷與人工處置。每個完成判定要附可核對 ID、時間、結果與退出證據。

## 11. 可直接貼給 OpenOctopus 任務

```text
請把「跨應用事件驅動 agent」加入 OpenOctopus 共用 Rust 核心。
Iced 與 Web 使用同一狀態與 API。先支援自己管理的任務。
下列是未來目標與驗收的 MUST 項。不是本輪已實作成果。

普通背景程式等事件、入庫、篩選、路由、限額及重試。
無事件不呼叫模型。不用 AI 排程輪詢網站或佇列。
加入 durable Inbox、Subscription、能力協商、明確任務綁定、
admission、provider adapter、結果保存、ACK 與退出核對。
ACK 只表示收件，不表示診斷、處置或案件結束。
人類與 agent 必須使用同一型別化 API。保留各自授權範圍。
必須顯示 persisted／ready／deferred／launch_pending／running／
result_saved／ACKed／unknown_exit。ACK 與退出狀態要分開。
provider 必須可替換。不可用時保留事件，不可暗中 fallback。

EventGuard 是第一個 producer。沿用其 outbox／QueueInbox。
模型 snapshot 保持七欄。完整證據留原應用。
沿用原每日五次耐久 authority，驗收也計入。
不要讓雙方各有五次造成超額。未知退出不自動重開。

先實作無模型核心與 fake provider 測試。
再提供有限真模型驗收計畫。真模型與正式背景啟用另等批准。
任意既有 Codex 桌面聊天未有能力與端到端證據時，顯示 unverified 並阻擋。
只有明確不支援時才顯示 unsupported。未知不是不可能。
不要探測私人 socket、讀 raw sessions、註冊排程或要求重開 Codex。
不要停用現有 dot 追蹤。先驗證交接，再由人類決定。

交付可見的 start／pause／status／stop、訂閱與事件頁。
頁面顯示進度、收件、ACK、模型請求數、額度與阻塞原因。
參考 EventGuard：docs/research/agent-event-ingress/OPENOCTOPUS_REQUIREMENTS.md。
本文件是設計需求，不是 OpenOctopus 現有能力證明。
```

## 12. 本輪檢查界線

只讀 EventGuard 原始碼、文件及指定聊天摘要。未改 OpenOctopus。未發送該任務訊息。未啟動 server、agent、排程或正式背景。未建立 reports。文件未單獨提交。

本文件中的協定名稱、狀態與介面皆為提案。正式標準與 Codex 桌面能力由同批研究另行查證。不能以本文取代實際 provider 的官方規格或端到端驗收。
