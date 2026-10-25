# EventGuard 現況

## 2026-10-25：目標增量更新（接續04:50交接）

主checkout3fe8148、worktree3155297已增量核對，未整合。新驗收仍prepare-only：manifest無execution、未入列、無capture-start。
預算測試遷移、event_source綁定、stop暫態修正及完整無模型回歸已完成，從剩餘目標移除。
最新目標見[MAINTENANCE_GOAL](docs/MAINTENANCE_GOAL.md)。本輪只更新文件，未重跑測試、未啟動模型、未新建reports、未commit或push。
原App goal仍paused；不新建或假標complete。整合與真驗維持04:50交接的確認關卡，不把使用者貼回交接內容當新模型授權。


## 交接暫停：2026-10-25 04:50（台北時間，最新）

使用者要求交接，停止開發。目標停在blocked，未標complete。
最新程式在worktree分支`claude/eventguard-quota-test-migration`，HEAD 3155297（含c8d42e1）。未push。worktree路徑`.claude/worktrees/eventguard-handoff-increment-721d6d`。
主checkout分支feat/local-codex-acceptance仍在3fe8148，追蹤檔乾淨；未追蹤`.codex-remote-attachments/`、`docs/research/`保留。整合c8d42e1與3155297需人類確認（主checkout乾淨，可fast-forward）。
本交接段在worktree內未提交（HANDOFF、STATUS、EVIDENCE），刻意不做文件單獨commit。
真通訊：使用者曾授權eventguard-single-test-20261025-01，但在啟動前改為要求交接。未執行。manifest無service_execution、未入列、無模型任務。
授權紀錄`human-approval.json`已標execution_started=false；下一位執行前必須請人類重新確認。
沒有本工具程序在執行。正式monitor desired off；正式agent service未啟動；App未執行。

## 無模型工程收尾與真通訊準備：2026-10-25 04:10（台北時間）

依新目標推進。唯讀核對與checkpoint一致：HEAD 3fe8148；舊事件仍pending、receipts0；continuation仍terminal_failed_no_retry；monitor desired off。
完整回歸（3fe8148，主checkout）：1460測試，1458過、0失敗、2略過（symlink不可用）。guardian自然exit0、remaining0、無強停、model_calls0。無失敗需修。
Event範圍一致：App新增明確`event_source`綁定。只限test範圍、`--idle`、不通知；綁定時不採集，開始／恢復回`monitor_outside_bound_event_source`。
CLI `run --event-source`、`events list/detail/set-status --event-source`、Web事件頁、十工具MCP及處置保存都讀同一source。status與capabilities回報`event_scope`。
Agent status另回`event_source_matches_application`，不再讓Agent頁與事件清單默默指向不同source。綁定source的投遞查詢只在agent service指向同一source時讀它的state。
小清理：GUI補`waiting_task_limit`標籤。`operations._budget_status`保留：已無呼叫者，但它是測試圍住歷史預算的單一接縫；刪除需大量改測試，無產品收益。
驗證：新測試8/8；相關22模組284測試中一個CLI參數斷言隨新契約更新後17/17。最終整套（本批原始碼）：verify-full-20261025-03為1468測試，1466過、2略過、0失敗；guardian自然exit0、remaining0。
前一輪-02有1項間歇失敗：test_operator_monitor_owner的SDK stop回background_owner_changed。該模組單獨重跑2次24/24通過，-03整套也通過。根因已查：status讀檔暫時失敗（raw_error_omitted、無run_id）被stop等待迴圈當成owner更換。已改為寬限期內繼續等待；迴圈內本就不送訊號，寬限期後仍保守回busy。
新增測試覆蓋暫態後退出及整段讀不到兩種情況。背景相關5模組101/101；修正後整套verify-full-20261025-04為1469測試1467過、2略過、0失敗，guardian自然exit0、remaining0。
真SDK：已安裝MCP SDK對綁定App呼叫十工具；list_events／inspect_event只見綁定事件，預設範圍事件查不到；start_monitor受阻。
瀏覽器：內建瀏覽器看到綁定source提示、1件綁定事件與MCP操作受阻紀錄。App自然exit0、殘留0。兩者都是合成資料，不是實機或真收件。
真通訊準備：新目錄`reports/service-acceptance-eventguard-single-test-20261025-01`只prepare，未執行。候選CLI SHA256符合，版本codex-cli 0.164.0-alpha.11.1，login status回報已登入；原始輸出未保存。
授權請求在該目錄`AUTHORIZATION_REQUEST.md`。目標停在等待人類授權；不得自行`--execute`。
前批證據也已複製到主checkout `reports/`（verify-budget-baseline-20261025-01、verify-budget-migration-20261025-01〜03），位元組一致。
仍需人類決定：真通訊授權、推送、研究稿與附件、跨source全域阻擋、選配長期驗證、worktree清理。

## 預算測試遷移：2026-10-25 02:30（台北時間）

接手後增量推進。只改測試；未改src、設定或runtime。未commit、未push。
位置：worktree `.claude/worktrees/eventguard-handoff-increment-721d6d`，分支`claude/eventguard-quota-test-migration`，基底f5810b5。
已帶入主checkout三份交接文件的未提交修改，位元組一致。主checkout本身未改，HEAD、diff與未追蹤附件／研究稿都照舊。
唯讀核對與交接一致：grant仍consumed；事件仍pending、receipts0；continuation仍terminal_failed_no_retry；正式monitor desired off；交接後無新runtime或reports。未啟動採集、派送、App或模型。
遷移前基線：受影響12模組211測試，148過、3 failures、59 errors。其中56個是patch已移除的`agent_dispatch.open_authority`。
`tests/budget_fixtures.py`改為無額度契約。短OS-create gate移到暫存目錄。本程序及capture worker都圍住歷史預算：讀取即失敗；結束時核對sentinel未變。
過時日額度測試改測新契約。保留耐久、併行與停止覆蓋：
- launch intent先落盤；同目錄不重用；gate busy／unavailable可見。
- pause／stop在各閘門前不啟動；最後pre-spawn暫停留not_started紀錄與skip證據。
- spawn結果不明時保留started紀錄；後續run拒絕；pending不丟。
- 有限max_tasks只等待不再啟動。它是單次run界線，不是日額度。
- 同一watch連續6事件、跨入口6次啟動都無五次上限；每事件三次上限保留。
另修正GUI、operator status、公告status仍斷言`agent_budget`／`daily_remaining`／「每日最多5」的舊測試。
結果：16模組291測試，290過、0失敗、1略過（symlink不可用）。guardian自然exit0、remaining0、無強停、model_calls0、source_unchanged。
範圍只有fixture、fake CLI及真Windows Job。不是全套回歸，也不是真模型或真收件。
證據：worktree內`reports/verify-budget-migration-20261025-03`；基線`reports/verify-budget-baseline-20261025-01`。中途01、02兩輪不作通過證據，原紀錄保留。
仍未完成：真receive→query→結果→ACK與自然退出（需新的人類有限授權）；Event頁自訂source綁定；全套回歸；24小時／重開機；桌面閒置喚醒。
觀察：`operations._budget_status`已無呼叫者。跨source全域阻擋隨authority移除；本批未加測試肯定或否定。

## 交接暫停：2026-10-25 00:50（台北時間）

本專案已收斂至可恢復交接點，goal為paused，未宣稱完成。停止開發，等待交接。
分支feat/local-codex-acceptance；HEAD f5810b52064fbde8f5d59928ff139277867f2165。
核對前追蹤檔乾淨；交接後只留HANDOFF.md、STATUS.md、docs/EVIDENCE.md未提交修改，不做文件單獨commit。
未追蹤2張附件及11份研究Markdown保留，未加入Git。未push、未新建交接資料夾或reports。
正式monitor stopped/exited_verified、desired_enabled=false；正式agent service not_started/not_recorded。
原合成service stopped/exited_verified，單一事件仍pending、receipts0；capture-start回條仍只有1份。
live App與同run test App均application_not_running；主專案test observer為scope_invalid。未停止任何程序。
本輪只有唯讀狀態核對及文件保存。沒有新模型、採集、測試、CLI執行或背景程序。
Python3.13.3/MCP SDK1.6.0可匯入。歷史CLI路徑已消失；新候選bin/2993767bd1dfb009/codex.exe存在，未執行或驗登入。
單次真通訊仍失敗，transport修正只有native metadata及契約證據；不得寫成真收件成功。
已完成/未驗證/阻擋/下一步及完整接手Prompt見HANDOFF.md頂部。該段取代下方所有過時預算/跨日等待/授權描述。
本機忽略的reports/data與設定不能靠Git clone重建；換帳號不移植Codex home或憑證。

## 單次通訊實測：2026-10-24（最新）

本次未能通訊。真正原生 CLI 已啟動一次。載入設定時退出：
`Error loading config.toml: invalid transport`，位置為 `mcp_servers.eventguard_test`。
CLI exit 1。驗收 exit 2。耗時 17.55 秒。未進入 provider turn，沒有模型回覆。
同一合成事件生成／入列各 1；receive、query、結果、ACK 均 0。事件仍 pending，無重複。
CLI、supervisor 與 host 已退出。無強停、無殘留。不自動重試；單次授權已消耗。

最新人類指示取消 App 的每日預算限制。通訊路徑不再讀取或改寫歷史預算。
歷史 bootstrap 與帳本保留，前後 SHA256 相同。舊 waiting_budget_day 已被取代。
正常無事件不呼叫模型。這次驗收仍限定最多一個 CLI 任務及 180 秒。

修正停用 MCP entry 的 transport 定義，並新增無模型契約測試。
修正後的真模型通訊未重驗。後續受支援的 native mcp get 設定解析 exit 0；舊 exit 2 查核保留。
後續唯讀 test App 的真 SDK MCP status 與 GUI 已對上同 event/attempt、CLI失敗及pending1。這是顯示失敗證據，不是收件。
App已自然exit0，無殘留；source/inbox位元組未變。新增模型任務0，總CLI測試仍1。
證據：`reports/service-acceptance-eventguard-single-test-20261024-01/communication-result.json`。
原 stderr、CLI JSONL、SQLite、intent、各層退出回條與歷史失敗均保留。
只提交程式、測試與文件。不提交執行資料。完整歷史見 docs/EVIDENCE.md。

更新：2026-10-24，UTC+08。分支：`feat/local-codex-acceptance`。本批基底：`9903ad5`。

EventGuard 可獨立採集、比對、保存及顯示。正常等待與查閱不呼叫模型。
CLI、Web及十個選配MCP工具共用Application與事件庫。MCP斷線不關閉應用。

## 使用

`.\EventGuard.cmd run` 前景啟動採集、Web與通知。
`.\EventGuard.cmd run --idle` 只開控制介面。預設 `http://127.0.0.1:8765`；埠被占用可指定 `--port 8877`。

已開啟應用後，使用 `app status/start/pause/resume/stop/shutdown` 或GUI/MCP操作。
stop只停採集，介面仍可查詢及再次開始。shutdown提出關閉要求，實際退出另核對。
GUI顯示真實狀態、最近動作、CLI/GUI/MCP來源與失敗原因。

stdio固定為observer。沒有App也能列工具，但回blocked，不建立第二owner。
明確讀status/capabilities可重新核對同root/namespace。變更不自動轉新instance；舊操作ID仍受保護。
設定、工具載入、收到事件、閒置喚醒分開。操作指南見 [APPLICATION_MCP](docs/APPLICATION_MCP.md)。

## 本批功能

- app文字模式以中文顯示採集、來源、原因、版本與可用操作。JSON/API不變。
- 通知先耐久保存意圖。回條不明時顯示未知，不盲目重送。事件仍pending。
- 公告頁、App status與公告事件詳情顯示有界公開來源、時間、新鮮度與適用性。
- 不公開本機inventory/facts/path/PID/原始evidence。自動派送仍只有既定七欄。
- 新增NVIDIA CSAF停用範例。壞子項與好子項隔離；partial不洗成success，不覆寫完整cache。
- 公告及十類對抗文字都只作資料。未知不變安全。處置狀態不ACK。
- 專用有限agent派送明確停用完整App MCP，避免擴大七欄profile。

## 實際驗證

相關測試、真SDK stdio/SSE、真Windows自有Job、原收件/ACK恢復與真瀏覽器均已執行。
瀏覽器確認同一instance、MCP處置同步、GUI改已處理後刷新保存；兩事件仍pending、ACK零。
通知中斷與滿載恢復、重連、舊operation fencing及預算政策已定向驗證。
一般使用者真Windows通知要求已接受，服務重建不重送，自身視窗已關閉；人是否看見未驗。
先前sandbox通知圖示skip及示範失敗均保留。沒有把fixture升格為主機安全或真agent驗收。
測試數、命令、時間、Python及證據只見 [EVIDENCE](docs/EVIDENCE.md)。
本機新功能證據在 `reports/application-lifecycle-001`、`reports/notification-intent-001`及`reports/nvidia-advisory-001`。
本批測試/示範程序均有退出證據。未強停、未啟用正式長期監看、未改正式控制或預算。

## 選配與未驗證

公開Codex入口研究見 [AGENT_EVENT_DRIVEN](docs/AGENT_EVENT_DRIVEN.md)。普通本機桌面任務閒置喚醒仍未驗證。
OpenOctopus提案與工作包見 [OPENOCTOPUS_EVENT_PROTOCOL](docs/OPENOCTOPUS_EVENT_PROTOCOL.md)，尚未在外專案實作。
既有eventguard-app入口已加Python -u，範圍與其他MCP不變。
本聊天隨後自動載入十工具。原生status與CLI/Web metadata核對同一閒置App。
原生shutdown提出要求後，私有Job原生exit0、Web/SDK退出，無殘留。應用關閉後observer回blocked，不自行冷啟動。
目前沒有測試App留存。MCP observer由Codex管理。這不是事件接收或閒置喚醒證據；未要求使用者重開。
真模型驗收需另核定一次有界範圍；本批產品模型為零。既有dot追蹤未停用。
未做七來源當前主機掃描、24小時soak或重開機。不宣稱全天候通過。
不建立服務、排程、自啟、proxy或新登入。不下載安裝、不提權、不推送。
