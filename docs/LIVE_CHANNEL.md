# 本機持續等待與專用 agent 接收

正常採集不需要模型。自動模式另外明示啟用，使用既有登入與本機 MCP SDK；不建立帳號、憑證、服務或排程。設定步驟及聊天 MCP 範本見 [CONNECT_AGENT](CONNECT_AGENT.md)，本機結果見 [EVIDENCE](EVIDENCE.md)。

## 一條事件通路

`Monitor → 原來源 EventStore → QueueInbox → agent_dispatch → 單次 Codex CLI → query/result → 原來源 ACK`。

GUI 自動模式與 `scripts/eventguard_agent.py watch` 使用同一 `agent_dispatch.run(continuous=True)`。純 Python 等待 pending；沒有事件不建立 attempt、不扣模型任務數、不啟動 CLI。GUI 的普通刷新仍是本機資料讀取，不是模型輪詢。

有 pending 時先檢查耐久每日預算與來源 lease，再啟動一個事件綁定 CLI。CLI 結束後回到同一程式等待；不需每日重開。`watch --max-seconds` 限制每次 CLI，沒有一小時 host 壽命；舊 `run` 與 `eventguard_watch.py` 保留有限驗收語義。

## 授權與停止

「允許接收」只控制資料存取。「自動交給專用 agent」才表示可使用既有模型額度；兩者預設關閉。存下選擇後，下次明確 Start 可沿用，單純開視窗不啟動。

人類取消自動勾選或按暫停會停止新任務，向本工具工作者合作取消；需要寬限逾時時只清理私有 Job 並如實記錄強停。沒有完整子樹退出證據就不能宣稱停止或另啟一份。

每日五次額度用完時，程式持續 `waiting_budget`；pending 不丟棄。失敗任務 `waiting_attention`，同事件不自動叫模型重試。單事件預算或容量拒絕在同一 owner 中鎖住，不能每次 poll 建新目錄。人類可以查看、接收或檢查原證據後明確重試。

同來源只允許一份 dispatcher，source/state 綁定與固定 `data/agent-budget` 不因換 run 目錄重置。一天界以 UTC+08 計算；閒置每分鐘只觀察本機預算時鐘，沒有網路／模型請求。未初始化、時鐘異常、未知退出或保存失敗均明示阻擋，見 [預算契約](AGENT_BUDGET.md)。

## 工具與資料範圍

單次 CLI 只應呼叫 `receive_event()`、`query_evidence(event_id)`、`ack_event(event_id, query_id, decision)`。提示不預帶事件 ID 或內容；snapshot 只含 `event_id`、枚舉 `event_type`、`transition`、`severity`、`synthetic`、`observed_at`、`coverage_status`。外層另有 query/result ID 與接收時間。

不回主機 ID、程序／產品名稱、路徑、PID、端點、任意 evidence/reason/gaps 或事件全文。query 讀同一份保存的最小摘要，不另查 Windows。`reviewed_metadata` 和 `incident_conclusion=not_assessed` 不能當診斷或結案。

CLI 保持 read-only、shell 關閉、單次 `-c` MCP 設定；同時停用此專案既有的 `eventguard_test`，避免該聊天合成佇列混入任務。這不是任意平台工具的安全隔離保證；驗收拒絕任何額外工具或不符的回傳。事件及外部文字始終是不可信資料，不能授予處置權限。

## 證據

每個 run 的 `status.json` 顯示 `continuous`、任務數、佇列檢查數、目前原因與退出狀態；`summary.json` 在 owner 結束時保存。`attempts/<id>/` 保留真正 CLI JSONL（含實際工具回傳）、stderr、assessment 與 capture-start/capture-exit、supervisor-exit 回條。耐久 query/result 檔在 `--state-dir`；GUI 使用 `data/agent-delivery`。

成功要比對生成、receive、query、result、原 outbox ACK 的 ID 集合與計數，並確認完整 turn、exit 0、自然退出及私有 Job 無殘留。登入成功、模型文字宣稱或 SQLite 行數不足以證明通路。儲存層 `real_agent_woken=false` 保留；跨 trace 的實際執行證明由獨立驗收給出。

所有執行資料只留忽略的 data/logs/reports，不上傳完整會話或 Codex 內部紀錄。這個能力是持續程式按事件啟動專用短期任務，不是喚醒任意既有桌面聊天。無24小時 soak／重開機證據就不宣稱全天候；登入自啟另需批准 [排程](BACKGROUND.md)。
