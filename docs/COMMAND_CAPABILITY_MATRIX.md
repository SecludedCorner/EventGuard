# Command First 能力矩陣

2026-11-01，起點 `c48d725`；依實際呼叫路徑盤點，表內「既有」不是本次重驗。CLI 共用 `cli.execute`；JSON 請明示 `--format json`。查看不採集、不呼叫模型、不 ACK；明確 mutation 另列。

| 能力／輸入 | CLI | API／共用核心／GUI | 輸出與預算 | 權限／副作用／證據與缺口 |
| --- | --- | --- | --- | --- |
| 已存事件篩選／詳情 | `events list/detail --namespace test` | `EventCatalog.list/detail`；Web、Tk 同核心 | JSON，limit 1..1000、offset、severity/source/status | 唯讀；既有 test_event_catalog、test_cli_workflow；缺庫空列表不代表安全 |
| 人工處置／重送 | `events set-status --event-id ID --status handled --operation-id OP` | `EventCatalog.set_status` → `EventStore.set_disposition`；Web／Tk | JSON，固定狀態，操作ID 1..128 | 寫狀態／歷程，不 ACK；CMD-003 補 CLI 操作ID；test_command_status_retry 實際程序驗收 |
| GUI 未決請求發現 | 尚缺 CLI | `EventCatalog.pending_requests`、`DesktopController.pending_requests` | namespace、limit 1..100、offset 0..128 | 唯讀；CMD-004 待接命令並核對真正上限／拒讀語意 |
| 保存 metadata 調查／版本 | `events investigate/detail` | `EventCatalog.investigate/detail`；Web／Tk | 有界候選／成員／版本、gaps、非因果聲明 | investigate 寫調查；detail 唯讀；既有 test_investigation*；真agent分析另有契約 |
| 人工歷程備份／預檢 | `events backup-history/preview-history` | catalog + disposition_history_backup；Tk | reports 固定名稱不覆寫；stdin 有界 JSON | 明確匯出／唯讀預檢，不恢復；既有 test_disposition_history_preview_cli |
| 七來源已存觀察／概覽 | `sources list/show`、`overview/status/activity` | `source_status`、`OperatorAPI`；Web／Tk／MCP | JSON、limit，coverage/freshness 分開 | 唯讀；既有 test_operator_status、test_operator_success_contradictions；原生partial仍待驗 |
| 採集與生命週期 | `monitor/stop`、`background`、`run`、`app status/start/pause/resume/stop/shutdown` | Monitor／OperatorAPI／Application，GUI共用 | fixture/max-cycles、期限、操作ID、退出回條 | 明確採集或控制自有Job；正常模型0；既有 test_application*、test_background_jobs；長跑未驗 |
| 規則與playbook | `rules list/validate`、`playbook validate/simulate` | configured／playbooks；Web只展示規則 | 固定schema、JSON；設定檔編輯 | simulate 不執行處置；無敏感處置授權；既有 test_rules_playbooks |
| 明確唯讀診斷 | `query`、`events diagnose/inspect` | DiagnosticAPI／OperatorAPI；MCP | 型別化操作、8KiB args、來源Job預算 | query/diagnose 可查OS；inspect只讀；既有 test_core_cli；拒讀不能安全 |
| 接收／ACK／重試／報告 | `events receive/ack/retry`、`report export` | OperatorAPI、共享inbox | event/query 綁定、JSON／escaped HTML | 明確保存收件／ACK或重試；既有 test_cli_workflow；ACK非結案 |
| agent 派送／投遞證據 | `agent start/status/pause/resume/stop/capabilities/inspect/export` | agent_service／event_ingress；Web限制控制 | 七欄CloudEvents，耐久預算／Job | start預設檢查，execute須有效批准；04失效待重新準備，真閉環未驗 |
| 公告追蹤／適用性 | `advisories start/check/status/stop/cases` | intelligence engine/service；Web投影 | config白名單、來源狀態、案件證據 | check/start會擷取；本次不執行；既有公告證據，非真防守 |
| 合成／mock | `synthetic emit`、`deliver --adapter mock`、`mock process/status` | synthetic／transport.adapters | test namespace、明示mock | 不是真agent；既有 test_events_transport |
| 預算／MCP | `budget status/initialize/reconcile`、`mcp` | BudgetAuthority／RemoteApplication | 耐久installation預算、固定工具 | initialize/reconcile明確寫入；不自動重設；MCP observer不冷啟App |

首個切片 CMD-003 推進「保存證據／可追溯人工處置」；下一 CMD-004 讓命令可發現 GUI 中回條未確認的請求，避免只靠畫面恢復。餘項持續依實際缺口增補，不代表所有 CLI 契約已完整驗收。

## 參考對照 R-CMD-001

官方 [dfir-iris/iris-web](https://github.com/dfir-iris/iris-web) 固定 `37c5521ac009bd018a2fac7bc01d70735d130c6c`；其 `iris-backend` 子模組 `f94eb25b9de60cb994184da417d0353da3405d62`，`source/app/datamgmt/manage/manage_cases_db.py` 的 `close_case`／`reopen_case` 將案件狀態與保存動作分開。具體檔頭為 LGPL-3.0-or-later，根 `LICENSE.txt` 為 LGPLv3；本次只讀、未複製或執行第三方碼，沒有引入依賴。

適用：人工狀態是獨立耐久操作，必須保留其來源與歷程。不適用：IRIS close 並不能作 EventGuard 收件ACK或已排除威脅的證據，也不能證明此版本提供 EventGuard 所需冪等契約。EventGuard 以既有標準庫交易實作，觸點 `cli.py` → `EventCatalog.set_status` → `record_attempt`；驗收 `test_command_status_retry` 檢查重送、後續狀態、衝突與 pending/ACK 分離。
