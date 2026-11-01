# Command First 能力矩陣

2026-11-01，起點 `c48d725`；依實際呼叫路徑盤點，表內「既有」不是本次重驗。CLI 共用 `cli.execute`；JSON 請明示 `--format json`。查看不採集、不呼叫模型、不 ACK；明確 mutation 另列。

| 能力／輸入 | CLI | API／共用核心／GUI | 輸出與預算 | 權限／副作用／證據與缺口 |
| --- | --- | --- | --- | --- |
| 已存事件篩選／詳情 | `events list/detail --namespace test` | `EventCatalog.list/detail`；Web、Tk 同核心 | JSON，limit 1..1000、offset、severity/source/status | 唯讀；既有 test_event_catalog、test_cli_workflow；缺庫空列表不代表安全 |
| 人工處置／重送 | `events set-status --event-id ID --status handled --operation-id OP --expected-payload-hash SHA256` | `EventCatalog.set_status` → `EventStore.set_disposition`；Web／Tk | JSON，固定狀態，操作ID 1..128、hash64；兩新選項可省略 | CMD-003/006已驗，test_command_status_retry/status_identity；hash不符exit2不寫，人工狀態不ACK |
| agent接收權限 | `agent access status/enable/disable` | `agent_access.status/set_enabled`；Tk set_agent_delivery另協作停止其自有worker | 本工具接收gate；不是模型執行批准；CLI不宣稱程序已退出 | CMD-007已驗，test_command_agent_access；壞設定exit2、保存失敗exit4；不啟receiver／模型 |
| 自動agent持久opt-in設定 | `agent automation status/enable/disable`；enable選填--codex-executable | agent_automation.describe/configure；Tk共用configure，controller另控制自有worker | schema1.0、設定state／enabled；dispatcher_state未驗、child_exited=null | CMD-014真CLI／API／桌面fixture52/52；CLI不啟停模型／worker，接收gate獨立；I/O失敗4、拒絕2 |
| GUI 未決請求發現 | `events pending-requests` | `EventCatalog.pending_requests`、`DesktopController.pending_requests` | namespace、limit 1..100、offset 0..128；固定event ID排序 | 唯讀；CMD-004已驗：test_command_pending_requests／test_desktop_pending_catalog；unknown=exit5，零件available=exit0 |
| 原人工操作結果查回 | `events operation-result --event-id ID --operation-id OP` | `EventCatalog.operation_result` | schema1.0、operation原結果／current現況、available/not_recorded/unknown | CMD-005 API／CLI已驗：test_disposition_operation_read、test_command_operation_result；unknown=5、不確認journal |
| 保存 metadata 調查／版本 | `events investigate/detail` | `EventCatalog.investigate/detail`；Web／Tk | 有界候選／成員／版本、gaps、非因果聲明 | investigate 寫調查；detail 唯讀；既有 test_investigation*；真agent分析另有契約 |
| 人工歷程備份／預檢 | `events backup-history/preview-history` | catalog + disposition_history_backup；Tk；command_input共用讀取 | reports 固定名稱不覆寫；stdin 有界 JSON，可在EOF前取消exit130 | CMD-013真私有console／CLI多區塊預檢已驗；明確匯出／唯讀預檢，不恢復，test_disposition_history_preview_cli／command_query_console_cancel |
| 七來源已存觀察／概覽 | `sources list/show`、`overview/status/activity` | `source_status`、`OperatorAPI`；Web／Tk／MCP | JSON、limit，coverage/freshness 分開 | 唯讀；既有 test_operator_status、test_operator_success_contradictions；原生partial仍待驗 |
| 採集與生命週期 | `monitor/stop`、`background`、`run`、`app status/start/pause/resume/stop/shutdown` | Monitor／OperatorAPI／Application，GUI共用 | fixture/max-cycles、期限、操作ID、退出回條 | 明確採集或控制自有Job；正常模型0；既有 test_application*、test_background_jobs；長跑未驗 |
| 規則與playbook | `rules list/validate`、`playbook validate/simulate` | configured／playbooks；Web只展示規則 | 固定schema、JSON；設定檔編輯 | simulate 不執行處置；無敏感處置授權；既有 test_rules_playbooks |
| 明確唯讀診斷 | `query`（--args文字或 - 讀stdin）、`events diagnose/inspect` | DiagnosticAPI／OperatorAPI；MCP；共用bounded_json | 8KiB UTF-8／32層／重複key拒絕，stdin可BOM、TTY拒絕，來源Job預算 | CMD-008/010/017已驗；來源n/a／未請求exit5、unsupported view=2；真PowerShell→.cmd管線，query/diagnose可查OS、health/inspect只讀 |
| 指令取消 | query stdin讀取中斷回固定結果；status=cancelled為exit130 | CLI輸入邊界／DiagnosticAPI既有取消狀態 | schema1.0、query_input_cancelled；輸入階段不dispatch，stdout結果／stderr診斷分開 | CMD-012注入與真私有console控制事件已驗，Windows空／未完JSON管線在EOF前取消；真人鍵盤／原生來源中途取消未驗，不能把取消當安全或成功 |
| 接收／ACK／重試／報告 | `events receive/ack/retry`、`report export` | OperatorAPI、共享inbox | event/query 綁定、JSON／escaped HTML | 明確保存收件／ACK或重試；既有 test_cli_workflow；ACK非結案 |
| agent 派送／投遞證據 | `agent start/status/pause/resume/stop/capabilities/inspect/export` | agent_service／event_ingress；Web限制控制 | 七欄CloudEvents，耐久預算／Job | start預設檢查、execute須有效批准；06短期合成調查通過，正式來源／桌面喚醒另驗 |
| 合成真調查批准綁定 | `scripts/validate_delivery.py investigation`預設只準備；execute需新scope批准 | investigation_scope／delivery_validation，共用builder與私有Job | 一事件／一任務／180秒；原生路徑正規化、capture前及事後launch hash核對 | CMD-009已修；06實際四步／分析／ACK／launch／自然退出通過；05綁定未完整通過仍保留，禁止重跑已消耗範圍 |
| 公告追蹤／適用性 | `advisories start/check/status/stop/cases` | intelligence engine/service；Web投影 | config白名單、來源狀態、案件證據 | check/start會擷取；本次不執行；既有公告證據，非真防守 |
| 保存公告完整列舉 | `advisories cases --limit 100 --offset 100`；case-id/event-id選單案 | `IntelligenceStore.case_page`與advisory共用投影 | schema1.0／limit1..100／offset／total／has_more；單頁交易快照 | CMD-011 API44/44／CLI12/12；跨頁不凍結，不擷取／啟模型，missing selector=unknown/exit5 |
| 合成／mock | `synthetic emit`、`deliver --adapter mock`、`mock process/status` | synthetic／transport.adapters | test namespace、明示mock | 不是真agent；既有 test_events_transport |
| 預算／MCP | `budget status/initialize/reconcile`、`mcp` | BudgetAuthority／RemoteApplication | 耐久installation預算、固定工具；status blocked=exit2、ready=0 | CMD-015真CLI／預算45/45；initialize/reconcile明確寫入、錯誤4相容，不自動重設；MCP observer不冷啟App |

CMD-003..009推進可追溯處置、GUI未決發現、結果查回、身分綁定、接收設定、輸入與批准契約，已逐單元實作及驗證。餘項依實際缺口增補，不代表所有CLI契約、原生覆蓋或整體盯哨已完整驗收。

CMD-004已接線並驗收，可用 `EventGuard.cmd --format json events pending-requests --namespace test --limit 1`，再以 `events detail --namespace test --event-id <回傳ID>` 讀原operation ID；offset用於下一頁。查閱不確認或重送GUI要求。schema沿用catalog欄位，unknown時events空但total/request_total/has_more為null，不能解讀為零項。CMD-005可按operation ID查原結果；重送的目前狀態不等於原操作結果。

## 參考對照 R-CMD-001

官方 [dfir-iris/iris-web](https://github.com/dfir-iris/iris-web) 固定 `37c5521ac009bd018a2fac7bc01d70735d130c6c`；其 `iris-backend` 子模組 `f94eb25b9de60cb994184da417d0353da3405d62`，`source/app/datamgmt/manage/manage_cases_db.py` 的 `close_case`／`reopen_case` 將案件狀態與保存動作分開。具體檔頭為 LGPL-3.0-or-later，根 `LICENSE.txt` 為 LGPLv3；本次只讀、未複製或執行第三方碼，沒有引入依賴。

適用：人工狀態是獨立耐久操作，必須保留其來源與歷程。不適用：IRIS close 並不能作 EventGuard 收件ACK或已排除威脅的證據，也不能證明此版本提供 EventGuard 所需冪等契約。EventGuard 以既有標準庫交易實作，觸點 `cli.py` → `EventCatalog.set_status` → `record_attempt`；驗收 `test_command_status_retry` 檢查重送、後續狀態、衝突與 pending/ACK 分離。

## 參考對照 R-CMD-002

官方 [Velociraptor](https://github.com/Velocidex/velociraptor/tree/61daa5f66b8bbaf946ab5d57dd8b087e07663762)，固定SHA `61daa5f66b8bbaf946ab5d57dd8b087e07663762`；`services/launcher/flows.go:GetFlowDetails` 以client_id+flow_id查持久context。根LICENSE AGPLv3，具體檔頭AGPL-3.0-or-later，無子模組內容採用。官方 [Shuffle](https://github.com/Shuffle/Shuffle/tree/c439ab39ee3780d629219fa3cd0e08aec795cb3b)，本機HEAD已核 `c439ab39ee3780d629219fa3cd0e08aec795cb3b`；`backend/go-app/test-suite/execution_e2e_test.go:getExecution/TestExecutionLifecycle`按execution_id讀結果、核對重讀與持久歷史一致。根LICENSE AGPLv3，該測試檔無另標授權。

採用契約：操作與讀回結果分開，固定ID、原結果／現況分離；EventGuard觸點為既有record_attempt表及新disposition_operation_read／catalog API，對應test_disposition_operation_read。未採用遠端執行、授權token、VQL或第三方程式；僅以既有Python標準庫獨立實作，不複製／執行第三方碼，不新增依賴。hash僅核資料一致性，不證明操作者或來源可信。

## 參考對照 R-CMD-003

[psutil](https://github.com/giampaolo/psutil/tree/c24bae0a977d31f79ac820f3d18cfb33e1465a32)本機HEAD已核`c24bae0a977d31f79ac820f3d18cfb33e1465a32`，根LICENSE為BSD-3-Clause；`psutil/__init__.py:Process._get_ident/_raise_if_pid_reused`結合PID與建立時間、拒讀保留無法判定，`psutil/_pswindows.py:wrap_exceptions`區分讀取失敗類別。這些檔案未另列不同授權、無子模組被使用。借鏡「短ID不足以支持後續操作、須核身分且錯誤類別分離」，EventGuard只暴露既有payload hash交易綁定並新增型別化衝突碼，對應test_command_status_identity。不複製／執行psutil、不新增採集、PID處置或重試；hash不是OS程序身分或可信簽章，不能宣稱完成原生身分覆蓋。

## 參考對照 R-CMD-004

[Fluent Bit](https://github.com/fluent/fluent-bit/tree/ad9867358257123c34b529860fe984e92a69844c)本機HEAD已核`ad9867358257123c34b529860fe984e92a69844c`；根LICENSE與`src/flb_pack.c`檔頭Apache-2.0。`flb_json_tokenise`區分INVAL／PART，`flb_pack_json_state`明確處理串流尾端不完整訊息。只借「解析失敗有明確界線、不得混作有效範圍」契約；該檔不是EventGuard duplicate/depth策略的來源或保證。本次不讀／採用其第三方parser子庫，不複製／執行C碼、不引依賴。EventGuard CLI是一筆完整JSON命令，不採串流接收或保留半批；重用自有bounded_json拒絕重複key／超深輸入，對應test_command_query_json／test_scanner_hardening，尚非NAS或Fluent Bit相容性驗收。

## 參考對照 R-CMD-005

[Timesketch](https://github.com/google/timesketch/tree/ea3d2ddabb91f096da596d0959adad5925a58446)本機HEAD已核`ea3d2ddabb91f096da596d0959adad5925a58446`；`timesketch/api/v1/resources/sketch.py:SketchListResource.get`以paginate取得items／total／has_next，回objects與meta。根LICENSE及該檔頭為Apache-2.0，無子模組內容使用。借鏡有界清單同時表達總數及下一頁，避免把100筆窗口當全部；EventGuard以標準庫SQLite獨立實作case_page並重用既有判讀，對應test_advisory_case_page／test_command_advisory_cases。不複製／執行Timesketch或引入Flask／SQLAlchemy；不借此宣稱跨命令凍結快照、遠端查詢或真威脅關聯。

## 參考對照 R-CMD-006

[osquery](https://github.com/osquery/osquery/tree/99ea20493a2614eab939cbc02ebfaa114a3caecb)本機HEAD已核`99ea20493a2614eab939cbc02ebfaa114a3caecb`；`osquery/sql/sqlite_util.cpp:readRows`讀取結果後要求SQLITE_DONE，其他終態／finalize錯誤回failure，該檔狀態名稱表含SQLITE_INTERRUPT。根LICENSE及檔頭明列Apache-2.0 OR GPL-2.0-only，未使用子模組。借鏡「有結果或收到取消不等於成功終態」；EventGuard只獨立補CLI既有cancelled狀態的非成功碼及輸入中斷結果，對應test_command_query_cancellation。不複製／執行osquery、不引SQL引擎或原始錯誤文字，也不宣稱其Windows來源／取消語意與EventGuard完全相同；既有三項Windows子模組checkout限制保留。
