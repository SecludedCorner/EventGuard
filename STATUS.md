# EventGuard 現況

## 持續工程 checkpoint：MCP 自身退出與有限恢復流程通過（最新）

基底 a34e466，分支 feat/local-codex-acceptance。本輪依持續工程授權繼續實作，沒有將前次 commit 或單事件通過當停止條件。

P2-MCP-EXIT-001 已完成：event-bound 專用入口新增 ACK 成功回應真正 write＋flush 後合作退出；既有 observer／readonly 不自動關閉。新增 query-only 所屬 Job member HANDLE 觀測，先核對 PID／creation／本次 CLI 私有 Job，再在活體時保留同 HANDLE，未授予 terminate 權限；缺失／unknown 不升格成功。capture 保存 start/exit，額外 --require-mcp-exit 重讀原始證據，舊驗收契約仍可讀。

新真驗收 reports/service-acceptance-eventguard-mcp-exit-20261025-04：一件合成事件、三工具各 1、pending 0／receipts 1；MCP、CLI、supervisor、host、outer 五層 exit 0。四個原有 Job remaining 0／無強停，MCP 有 ACK flush、正常 stdio-exit 與活體綁定 HANDLE 的 OS exit 0 證據。外層 43.442485 秒；獨立 SQL／hash／時序核對及 --verify-only --require-mcp-exit 重驗通過，已補上前輪 MCP 自身退出缺口。仍不是桌面喚醒或完整 IO 隔離證明。

P1-SOAK-001 已完成有限整合：新增 scripts/soak.py／eventguard.soak，以純 synthetic producer／EventStore／QueueInbox 演練滿載拒絕保留、原 ID/hash 恢復、completion 保存故障 pin 保護、重建 consumer 同 query、冪等 ACK 與排空守恆。reports/soak-finite-20261025-02 接受 64／唯一 ACK 64／pending 0，實際 81.881672 秒，guard 自然 exit 0／remaining 0／無強停。這是 harness，不是真 agent、OS 重啟或 24h。

失敗與修復：首輪 10 模組 117 測試，116 過／1 error（soak 的 SQLite read-only 連線僅交易 context 未 close，Windows temp 收尾鎖檔）；改用 closing 後 test_soak guardian 3/3 通過。其餘 114 項 MCP／transport／Job 測試來源未變，沿用逐測試通過證據，未冒充同輪全綠。真流程首輪 64 件／60 秒工作上限在 52 件 ACK 後到期，保留原失敗與 12 件未入列 producer；集合守恆重驗無丟失。第二輪同 64 件改採 180 秒有界 profile，未宣稱 60 秒通過。

證據：reports/verify-mcp-exit-soak-20261025-01、reports/verify-soak-close-20261025-01；真04的 communication-result.json／mcp-exit-validation.json／五份 mcp marker/process 回條；兩個 soak 目錄的 validation.json／conservation-recheck.json。執行資料不提交。

CURRENT/NEXT：保存本切片後直接處理 P1-SOAK-GUARD-002 的異常收尾、P2-SOAK-MEASURE-001 的真 wall-time／自有資源採樣，以及 P2-GH-PAGES-001 的公告來源有界分頁。完整工作佇列在 docs/MAINTENANCE_GOAL.md。實機來源與 24h 的未驗範圍不變，未 push。

## 2026-10-25：加入 Continuous Execution Policy（最新文字變更）

依使用者提供原文，將持續工程推進政策加入 AGENTS.md；原有專案與安全界線保留。台北 23:18，以 Python 文字比對驗證整段逐字一致、只出現一次、既有內容位元組不變，並執行 git diff --check。證據 reports/continuous-execution-policy-20261025-01/validation.json。純文件變更，未重跑程式回歸或真 CLI，不新增產品驗收結論。

## 2026-10-25：真 Codex 收件鏈通過（最新）

最新直接人類指示「解除額度限制，與各種阻擋限制，請全力開發」已撤銷前輪兩次真 CLI 上限與暫停接線要求；下方「額度用完／不得第三次」均為歷史。本輪基底 `836d0df`，分支 `feat/local-codex-acceptance`，保留 AGENTS 安全界線。本輪新授權後實際只啟動 1 個真 CLI 任務；未 push。

**既定收件目標已通過**：新目錄 `reports/service-acceptance-eventguard-development-20261025-03`，一件合成事件，由 service 在空佇列等待後入列並啟動專用原生 Codex。台北 22:45:35–22:46:24，外層 49.314 秒；receive→query→保存結果→ACK 各 1，pending 0、receipts 1、無重複。CLI JSONL 真工具回傳、durable event/query/result、SQLite、結果先存再 ACK 時序均一致；`--verify-only` 重讀原始證據仍 passed=true，另有獨立 mode=ro 核對。

CLI、capture worker／supervisor、host、outer validation 原 HANDLE／Job 回條均自然 exit 0、remaining 0、無強停。CLI owned tree 已空。這是專用 CLI agent 真收件，不是既有桌面聊天／dot 閒置喚醒或主機安全結論。

本輪修改：單次 MCP 配置顯式 enabled=true；新增可選 startup-evidence-dir 與有界安全 phase markers，記錄 server 啟動／工具清單，保留 required／20 秒啟動／60 秒工具期限與三工具 allowlist。移除每次全新 sqlite_home override，保留 ephemeral、history.persistence=none 與專用 log_dir，不移植認證或修改全域／帳戶設定。CLI 有效配置與本機 public features/help 先以無模型 metadata 核對；沒有使用 removed 的 SQLite 功能旗標。本次組合修正成功，不能歸因單一改動。

定向 guardian：`py -3.13 -B scripts/verify.py --run-dir reports/verify-inbox-startup-evidence-20261025-01 --timeout-seconds 300 --module test_inbox_startup_evidence --module test_agent_dispatch --module test_queue_inbox --module test_delivery_consolidation`。台北 22:43:37–22:44:41，Python 3.13.3，54/54 通過、0 failure/error/skip，source_unchanged=true、guardian 自然 exit 0／remaining 0／無強停、model_calls 0。新增 5 項測試含真 SDK JSON-RPC list_tools、EOF 及 marker scope／redirect／失敗路徑。

完整回歸：`py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261025-05 --timeout-seconds 1800`，台北 22:48:26–22:55:41。1477 項：1474 通過、3 略過、0 failure/error；兩項 symlink 不可用、一項 notification_icon_unavailable。passed_checks=true、source_unchanged=true；guardian 自然 exit 0／remaining 0／無強停、無逐測試殘留，model_calls 0、machine_scan_executed=false。證據 `reports/verify-full-20261025-05/verification-summary.json`；提交後 source-commit.json 綁定本版受測來源。

證據：[真通訊結果](reports/service-acceptance-eventguard-development-20261025-03/communication-result.json)、[原始證據重驗](reports/service-acceptance-eventguard-development-20261025-03/validation.json)、[獨立交叉核對](reports/service-acceptance-eventguard-development-20261025-03/acceptance-crosscheck.json)、[定向測試](reports/verify-inbox-startup-evidence-20261025-01/verification-summary.json)。reports、SQLite、CLI 輸出與授權紀錄只留本機，不提交。

限制：本次有同 instance 的 server-started／tools-listed marker，沒有 mcp-stdio-exit marker。MCP PID 後查為 missing，CLI Job 已空，但 MCP server 自身 OS 退出碼／自然退出沒有獨立證明，不能把四層回條泛化。當次 legacy metadata／invalid transport／WSA 10013 警告布林均 false；未手動開啟原始 sessions，亦不以無警告宣稱完整 IO 隔離。上述額外證明、長期運行與桌面喚醒列 DEFERRED；不阻擋原先明列 CLI／worker／host 的收件驗收。

## 2026-10-25：第二次真任務完成回合但未收件；兩次額度已用完（最新）

本節優先於下方「第二次未執行／仍保留一次」的歷史文字。本輪基底 `c5401e9`，分支 `feat/local-codex-acceptance`。三個里程碑已完成證據收尾；真 receive→query→保存結果→ACK **仍未通過**。原授權兩次真 CLI 任務已用完，不得再啟動第三次或重用任一目錄。未 push。

1. **連線診斷完成**：同一個無認證 HEAD 探針在工具沙箱內重現 WSA 10013；經自動批准審查允許單次工具沙箱例外後，一般 Windows 使用者環境回 HTTP 403，支持連線可達。探針模型任務 0、兩個 Job 自然 exit 0／remaining 0；未改系統／帳戶／網路設定、未觸發 UAC。403 不證明帳戶或模型存取。
2. **退出回條補驗完成**：只在本機 reports 保存專用 wrapper，直接使用既有 Python 3.13、合法 finish reason、原 HANDLE 與有界輸出。無模型自測 4/4：自然 exit 0、自然 exit 2、輸出截斷、合成逾時隔離。逾時案例明示 expected forced，僅終止自己的 Job；另一 Job sentinel 自然退出。外層 guardian 自然 exit 0、remaining 0。
3. **第二次真驗收已完成但失敗**：新目錄 `reports/service-acceptance-eventguard-single-test-20261025-02`，執行前另記 `human-approval.json`。台北 16:31:27–16:33:33，外層 125.921 秒。此次 provider turn 完成、CLI 自然 exit 0，但 agent 回報未提供 eventguard_inbox 工具，JSONL 沒有任何 MCP tool call。固定失敗類別 `required_mcp_tools_unavailable`；生成／入列各 1，receive/query/result/ACK 各 0，pending 1、receipts 0、無重複。CLI／worker／host 自然 exit 0，外層驗收自然 exit 2；均有原 HANDLE／Job 回條、remaining 0、無強停。此次沒有 WSA 10013 或 invalid transport，不沿用前次失敗原因。

最小修正：`src/eventguard/agent_dispatch.py` 的單次 inbox MCP 配置新增 `required=true`、`startup_timeout_sec=20`，保留原工具 allowlist／60 秒工具期限；`tests/test_agent_dispatch.py` 增補 TOML／transport／live-test 與 ACK-readonly 契約斷言。此修正意圖是在必要 server 初始化失敗時停止，**沒有證據證明工具缺失根因已修復**，也尚未真 CLI 重驗。

驗證：`py -3.13 -B scripts/verify.py --run-dir reports/verify-required-inbox-20261025-01 --timeout-seconds 300 --module test_agent_dispatch --module test_delivery_consolidation --module test_delivery_validation`。台北 16:37:47–16:38:51，Python 3.13.3，60/60 通過、0 failure/error/skip；source_unchanged=true、guardian 自然 exit 0／remaining 0／無強停、model_calls 0。未重跑完整回歸。

證據：[連線比較](reports/connection-diagnostic-20261025-01/comparison.json)、[wrapper 自測](reports/invocation-proof-20261025-01/selftest-summary.json)、[第二次真通訊](reports/service-acceptance-eventguard-single-test-20261025-02/communication-result.json)、[定向測試](reports/verify-required-inbox-20261025-01/verification-summary.json)。第二次實測執行來源是 `c5401e9`；其後才改 required 契約，`source-state-note.json` 區分執行來源快照與收集時工作樹差異。reports 不提交。

補充無模型交叉檢查：以相同第二次 root／source／inbox／event，透過標準庫 JSON-RPC 呼叫已安裝 SDK server 的 initialize／tools/list，成功列出 receive_event、query_evidence、ack_event；不呼叫事件工具，前後 events 1／pending 1／receipts 0 不變，server 自然 exit 0、remaining 0、無強停。證據：[同範圍 SDK discovery](reports/sdk-inbox-discovery-20261025-01/result.json)。這把剩餘問題縮小到原生 CLI 的 MCP 載入／工具曝光，仍不能判定根因。

**BLOCKERS**：兩次真通訊額度已耗盡；MCP 工具缺失根因未知；原生 CLI 當次 stderr 自帶歷史 rollout metadata 索引警告，操作者未另行開啟那些檔案，但 CLI 內部歷史隔離尚未證明，因此不再新增任何 CLI 命令。後續真驗收需先釐清此界線，並取得新授權。
**DEFERRED**：通用 wrapper 產品化、完整回歸、長期運行及既有桌面聊天／dot 喚醒。舊、新兩件未 ACK 的合成事件原樣保留，不改成已收件或安全結論。

## 2026-10-25：真 CLI 單事件驗收失敗，已修正失敗早停（最新）

本節取代下方「真通訊未執行／仍須重新確認」的現況。基底 `ea00c70`，分支 `feat/local-codex-acceptance`。本輪使用者已明確授權最多兩次、每次一件合成事件／一個 CLI 任務／180 秒；授權與時間已在執行前寫入該次 `human-approval.json`。本輪實際啟動真 CLI 任務 **1 次**，第二次未執行，未 push。

真通訊 **失敗，尚未收件**。執行既有 `reports/service-acceptance-eventguard-single-test-20261025-01`，台北 14:55:19–14:57:01（UTC 06:55:19–06:57:01），102.62 秒內收尾。CLI 自然 exit 1：WebSocket 連線遭 WSA 10013 存取拒絕，轉 HTTPS 後仍連線失敗；沒有舊的 `invalid transport` 錯誤。這只能確認連線受拒，未確認是主機政策、sandbox 或其他來源；未修改網路／系統／帳戶設定，也未提權。

- 同一事件生成／入列各 1；receive／query／結果保存／ACK 各 0；source pending 1、receipts 0、無重複。JSONL 有 thread.started／turn.started，沒有 MCP 工具呼叫或完成回合。模型請求數未量測。
- CLI 自然 exit 1、capture worker／supervisor 自然 exit 0、host 自然 exit 0；各層 Job remaining 0、無強停。host 為 stopped／exited_verified。不是喚醒既有桌面聊天或 dot 的證據。
- 外層包裝器先因相對 `py` 路徑而在啟動驗收前失敗（CLI 0 次），改用同一 launcher 的絕對路徑後才執行上面唯一一次真通訊。包裝器收尾又使用不支援的 finish reason，缺少外層 launcher 的原 HANDLE 退出回條；退出碼記 unknown，未補造。之後對已記錄 launcher／驗收 interpreter PID 的唯讀核對均為 missing。這不替代原 HANDLE 證據；CLI／worker／host 的原回條完整。

發現並修正 `src/eventguard/delivery_validation.py`：唯一任務已失敗且自有程序樹確認退出、dispatcher 為 waiting_task_limit 時，立即走原有 finally 合作停止 host，不再空等 160 秒工作期限。本次實測使用修正前程式，由操作者在失敗後合作停止；修正後只做無模型驗證。新增 `tests/test_delivery_validation.py` 三項 fixture，覆蓋立即失敗、未確認退出繼續等待、成功正常返回。

驗證命令：`py -3.13 -B scripts/verify.py --run-dir reports/verify-service-failfast-20261025-01 --timeout-seconds 300 --module test_delivery_validation --module test_launch_receipts`。台北 14:59:00–14:59:19，Python 3.13.3，33/33 通過、0 failure/error/skip；source_unchanged=true、guardian 自然 exit 0、remaining 0、無強停、model_calls 0。沒有重跑完整回歸；1467/1469 是上一版既有結果。

證據：[真通訊結果](reports/service-acceptance-eventguard-single-test-20261025-01/communication-result.json)、[定向測試](reports/verify-service-failfast-20261025-01/verification-summary.json)。原 JSONL、stderr、SQLite、授權及程序回條均只留本機 reports，不提交執行資料。詳細 event／attempt 與檔案清單見 EVIDENCE。

目前未建立在授權內可解決 WSA 10013 的修正，因此保留第二次額度，避免在相同條件重跑。不得重用本次已消耗目錄。真 receive→query→保存結果→ACK 仍受阻；若後續在本輪授權仍有效時重試，須先有具體改善證據，使用全新 prepare 目錄並另記授權。超過兩次、push 或更改系統／帳戶設定都需再詢問使用者。

## 2026-10-25：合併worktree分支（最新）

本合併提交把feat/local-codex-acceptance（8176095）與claude/eventguard-quota-test-migration（6456759）合在一起，含c8d42e1、3155297。
主checkout fast-forward到本提交後，下方「主checkout仍在3fe8148」「未整合」「最新程式在worktree」等描述即屬過時。
衝突只在HANDOFF、STATUS、EVIDENCE頂部：兩邊段落全保留，較新段落在上，重複的舊標題行只留一份。程式與測試無衝突。
真通訊仍未執行。eventguard-single-test-20261025-01仍須人類重新確認才可--execute。未push。

## 2026-10-25：目標增量更新（最新閱讀入口）

最新程式在`.claude/worktrees/eventguard-handoff-increment-721d6d`，HEAD3155297；主checkout仍是3fe8148，未整合。
本輪已核對兩處Git與既有驗收證據。預算測試遷移、event_source綁定、背景stop修正均已完成，不重列為待辦。
最新落地目標見[MAINTENANCE_GOAL](docs/MAINTENANCE_GOAL.md)。最新完整交接讀worktree的HANDOFF/STATUS/EVIDENCE；下方較早checkpoint屬歷史。
剩餘順序：確認整合兩提交；重新確認eventguard-single-test-20261025-01；確認後才跑一次真通訊。這次只更新目標，不構成執行授權。
本輪未合併、未啟動模型/測試/背景、未push。交接修改保留未提交，不做文件單獨commit。原App goal仍paused。

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
