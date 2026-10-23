# 證據與時間日誌

這是測試數、命令與時間紀錄的唯一閱讀入口；現況請看 [STATUS](../STATUS.md)，下一步看 [維護目標](MAINTENANCE_GOAL.md)。原始回傳、SQLite、CLI JSONL、runtime 與私有資料只留本機忽略的 reports，不提交。

## 2026-10-23：本聊天手動接收、ACK修正與限定MCP接線

基底 `d46236fdd20d59ff4c9ff1c7c7091bfd497f484d`，同一feature。本聊天開始時與設定加入後均查可用工具，EventGuard專用工具數為0；正式接收開關唯讀結果為enabled_waiting_receiver／receiver_verified=false。使用者要求實際接收，故以本聊天命令工具呼叫既有OperatorAPI；沒有啟動額外Codex／模型、Windows採集、真事件ACK或新的監看。這是正在回應的agent手動讀取實際工具回傳，**不是原生MCP已載入或閒置聊天被事件喚醒**。

命令 `py -3.13 -B reports/chat_receive_probe.py setup` exit0：程式在全新隔離root生成1件公開合成事件，不預先回傳其ID／內容。接著 `receive-next` 實際讀到event及query，`inspect EVENT_ID`讀到保存的TCP／port／綁定與process_binding_missing；`state`確認pending／receipt0。第二次receive收到相同event/query；本聊天明確 `ack EVENT_ID QUERY_ID reviewed_metadata` 後來源ack且SQLite receipt恰1。生成／唯一接收／查證／ACK集合相同，預期補收1次，沒有缺漏或重複回條。原始生成manifest、逐次時間／實際回傳與SQLite留 `reports/chat-receive-001/`；ID不抄入公開文件。

實測發現舊API在已ACK時接受query-wrong／不同decision並回already_received，未新增回條但誤稱請求已匹配。修正為QueueInbox.open_readonly：只驗既有marker/policy、query/result與來源實際receipt，不mkdir、建立snapshot或再次ACK。相同event/query/decision回ack_replay_verified=true；錯query回same_event_query_required，改decision回inbox_result_decision_conflict，缺失／已輪替回ack_replay_evidence_unavailable，receipt衝突回outbox_ack_identity_conflict。修正後在同一事件上實際重試均得到上述預期結果，receipt保持1；測試另覆蓋位元組不變、其他receiver、輪替、缺policy及唯讀物件所有寫入拒絕。原workflow固化「改decision仍成功」的預期已同步修正。

**本批驗證數字唯一來源**：`reports/chat-receive-001/selected-001/verification-summary.json`。命令 `py -3.13 -B reports/chat-receive-001/verify_selected.py`，重用既有verify.worker／私有Job guardian，明確選operator_api、operator_workflow、operator_status、queue_inbox、storage_retention、agent_access六個受影響模組；Python **3.13.3**，2026-10-23T04:43:53.761109+00:00：**108/108通過、0 failure/error/skip、122 AST**，33.625秒，exit **0**。source_unchanged/passed_checks=true、per_test_residuals=[]，guardian自然exit0、remaining0、未強停。這是局部合成／SDK／SQLite契約，不稱新完整suite；前批完整結果保留歷史，不累加。

使用者明確批准後，命令 `py -3.13 -B reports/chat-receive-001/install_project_mcp.py` exit0，新建專案 `.codex/config.toml` 的eventguard_test；只連本輪合成operator root、test namespace與四個list／inspect／receive／ACK工具，沒有全域設定或其他MCP變更。設定digest與安裝回條留project-mcp-installed.json；`.codex/`已加入Git忽略，不提交本機設定。`emit-mcp`另生成1件新合成事件並保留pending，未向本聊天透露ID／內容或ACK，供用戶端重載後驗收。

原生聊天MCP仍為**blocked／待用戶端重載**。依 [OpenAI官方MCP設定](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) 已請使用者在設定→MCP servers對eventguard_test按Restart；沒有能力在本聊天自行重載工具清單，也沒有把命令工具當原生MCP。首個stdio readiness輔助程式已收tools/list，但收尾誤用非白名單reason而例外，無有效退出回條，不宣稱通過；stderr保留。修正輔助程式後第二次server回 `this inbox state already has an active stdio owner`、exit3／child_exited=true／remaining0／未強停；沒有辨識該owner來源，也沒有終止、刪鎖或換state繞過。保留mcp-ready-002 stderr、transcript與exit；不能以這些結果聲稱原生工具接收成功。

## 2026-10-23：補讀25引擎與各真上游repo

兩個子agent補讀主repo最新固定 `654dd7165112c38da4e7bf894fdccb9a251d2c1d`，含完整tree（未截斷）、catalog、25個plans、registry、launcher/adapter及執行邊界；並逐一讀25個真上游固定source_revision的README與代表CLI入口／manifest（最多前180行）。[引擎表](SCANNER_ENGINES.md)逐項列用途／輸入／命令／依賴／網路／輸出與pinned程式來源；[runtime研究](SCANNER_RUNTIME_REVIEW.md)列可採納與不可照搬機制。`reports/scanner-engines-001/catalog-review.json`核對25個unique引擎／repo／README／代表檔、13網路／12離線、執行數0；不擴查其餘69筆來源依賴、不宣稱25個repo完整安全審計。前輪僅UI及部分adapter的閱讀範圍不回溯升格。

本輪沒有安裝／執行25引擎、下載binary／容器、測模型或外掃目標。新增文件的相對連結／固定來源檢查與本地來源綁定回條留reports；後續超量輸出提早停止只是候選，未實作或列作驗收成功。私人資料、runtime、完整會話及原有docs/research均保留不提交；不推送或觸發CI。

## 2026-10-23：研究 ai-security-scanner 並直接採納

基底 `32f9975182e189ad3b9723d8df78e3db022cdd4e`，同一feature。兩個子agent分別讀採集與結果介面，固定公開commit `46b7d1900fc25ef8ae4e4b568b638c915f28d130`；主線另核對README、LICENSE、adapter及混合壞列測試、篩選與技術展開程式。來源及取捨見 [SCANNER_LESSONS](SCANNER_LESSONS.md)。未執行上游程式或測試，未下載依賴；只參考設計概念並獨立實作，無程式／資產複製或授權更動。

**目前完整數字唯一來源**：`reports/scanner-study-001/full-001/verification-summary.json`。命令 `py -3.13 -B scripts/verify.py --run-dir reports/scanner-study-001/full-001 --timeout-seconds 600 --scope full`；在正常一般使用者桌面context驗證（有限sandbox例外，沒有UAC或Windows提權），Python **3.13.3**，2026-10-23T03:56:47.584648+00:00：**684 discovered、682 passed、0 failure/error、2 symlink權限skip、122 AST**，161.884秒，exit **0**。passed_checks/source_unchanged=true、per_test_residuals=[]；guardian自然exit0、child_exited=true、remaining_owned_processes=0、forcibly_terminated=false。沒有再重跑mock子集或累加舊結果。

本批新增合成採集列隔離、呈現、真Tk自身元件及Desktop總數契約案例。七來源native／fallback遇非物件壞列保留合法siblings，部分資料不升格完整，也不觸發錯誤恢復或清baseline；列／錯誤上限、不啟動fallback掩蓋、外層仍拒絕及不記壞文字均有斷言。人類摘要沿用既有guidance，原JSON預設收合；篩選只作用於載入的最多100件，儲存總數／截斷明示，零結果不能視為安全；選取與晚到回覆、observed_at與不可信控制字元均驗證。

命令 `py -3.13 -B reports/scanner-study-001/visual_probe.py` exit **0**：只渲染本工具Tk視窗＋公開合成控制器，`synthetic-window.bmp`與`visual-result.json`保留畫面與斷言，已視覺檢查。兩筆事件、中文摘要、正確時間、嚴重度／接收狀態篩選、顯示／載入／總數及截斷提示可見；raw_collapsed/human_sections_verified=true。測試視窗正常退出，沒有長期程序、原生採集、ACK、模型或排程操作；不擷取其他應用或桌面。這是合成介面證據，不是正式監看或真agent。

原有正式GUI／監看保留，本批不讀寫其事件、不為更新而重啟或全機重掃；已開視窗不熱更新，新介面於下次正常開啟載入。本批沒有真模型、接收器連線、正式壞資料注入、登出／重開機、24小時soak、Task建立／Run、服務、提權或安全設定變更。source-commit回條綁受測bytes及本批文件；reports、runtime、憑證、私人歷史及原有docs/research不提交、不推送。

## 2026-10-23：可直接操作的 GUI

基底 `fd1e874e380512b2566dc2690368c20acd3813cd`，同一 feature；最新使用者明確要求開始／暫停、可見狀態與agent開關，取代舊GUI非目標。兩層互斥ownership實作後統一驗證；核心仍使用既有Python3.13標準庫／tkinter，不下載安裝、不提權／UAC、不改安全設定／執行政策、不建立排程或服務、不啟動模型。操作見 [GUI](GUI.md)。

**前批完整數字來源**：`reports/gui-001/full-001/verification-summary.json`。命令 `py -3.13 -B scripts/verify.py --run-dir reports/gui-001/full-001 --timeout-seconds 600 --scope full`；在正常一般使用者桌面context驗證（有限sandbox例外，不是Windows提權），Python **3.13.3**，2026-10-23T01:59:57.766146+00:00：**664 discovered、662 passed、0 failure/error、2 symlink權限skip、119 AST**，197.795秒，exit **0**。passed_checks/source_unchanged=true、per_test_residuals=[]；guardian自然exit0、child_exited=true、remaining_owned_processes=0、forcibly_terminated=false。fixture／mock子集包含於本次，不另重跑或累加。

新增GUI按鈕／接收勾選／唯讀選取、X最小化、退出未確認保留視窗、UIworker序列化與中斷收尾測試；真Tk自身元件使用fixturecontroller，不是實機採集或真agent。`reports/gui-001/visual_probe.py`只渲染本工具Tk視窗及公開合成資料；命令 `py -3.13 -B reports/gui-001/visual_probe.py` exit0，`synthetic-window.bmp`／visual-result保存自身畫面，已視覺檢查七列、開始／暫停與勾選可見。沒有擷取其他應用或桌面；合成截圖不當成正式監看證明。

完整suite另有**真Windows有限應用Job**：保留父應用Job handle而不detach、明確暫停自然退出；合成parent正常退出後，host以原PID＋建立時間觀測owner退出，合作取消／退出，outer Job remaining0且未強停。原有獨立背景CLI的外部Job拒絕契約保留，沒有使用test-only allow_parent_job作正式入口。第二層審查找到keeper可能留下孤兒與fixture誤顯live兩項，已修parent存活監看、namespace拒絕與相應測試；詳見lifecycle-evidence。

agent開關SDK函式案例：公開合成事件以live-profile寫隔離root；off時receive不回傳event metadata，on後receive取得同event/query，off後ACK被拒且仍pending，人類API可ACK一次。這是真已安裝SDK工具函式＋SQLite，**不是agent或模型**。gate設定損壞／保存失敗明示，pending／query不清空。live dispatcher在off時不檢查CLI或啟動模型；正常GUI不呼叫dispatcher。人類共用核心不受agent gate阻擋。

正式命令 `py -3.13 -B scripts/eventguard_gui.py --start` 在正常一般使用者context已開啟可見視窗並持續運作（當次exec session35464；GUI是明示保留的正式應用，不是測試殘留）。`py -3.13 -B scripts/eventguard.py --format json status`只讀回保存狀態，原始JSON留 `reports/gui-001/live-status.json`：background **running**、current_monitor **running_verified**、model_calls **0**、七來源均fresh且有筆數。這份狀態是當次快照，使用者可隨時按暫停，後續不能假定仍運作。

| 正式來源 | 狀態／總列數 | 界線 |
| --- | --- | --- |
| defender | partial／11 | 一般權限保存觀察；不是安全或受侵判定 |
| listeners | partial／198 | 一般權限保存觀察；不是安全或受侵判定 |
| processes | partial／595 | 一般權限保存觀察；不是安全或受侵判定 |
| startup | ok／39 | 一般權限保存觀察；不是安全或受侵判定 |
| services | ok／315 | 一般權限保存觀察；不是安全或受侵判定 |
| tasks | ok／218 | 一般權限保存觀察；不是安全或受侵判定 |
| versions | ok／1 | 一般權限保存觀察；不是安全或受侵判定 |

正常使用者本輪tasks可讀，與前批受限context的unknown不同；這是不同執行context的實際證據，不能反推所有歷史拒讀根因。新鮮度、觀察上限與不確定性仍保留；事件均先存本機，沒有自動ACK或處置。

沒有實際登出／重開機、24小時soak、Phase7狀態注入或真模型／接收器連線驗收。使用者沒有批准前次排程plan，故沒有Task mutation或Run；原plan因新來源變更失效。GUI開始不需要排程，但登入後自動恢復仍未啟用。source-commit回條綁受測bytes與本批文件；runtime、含本機metadata的JSON／SQLite／畫面、私人研究及憑證均不提交、不推送。

## 2026-10-23：背景監看、耐久啟停與登入恢復入口

基底 `08a4ef8ff7e5762c499b7cb270de1e86a0361822`，同一 feature 分支。依本次授權完成一般權限背景功能、兩層互斥 ownership 開發、主線整合及功能完成後統一驗證。契約見 [BACKGROUND](BACKGROUND.md)，範圍見 [維護目標](MAINTENANCE_GOAL.md)。沒有真模型／Codex、提權／UAC、下載安裝、變更安全設定、服務或排程 mutation；原有研究與執行資料保留、不推送。

**前批完整數字來源**：`reports/background-001/full-003/verification-summary.json`。命令 `py -3.13 -B scripts/verify.py --run-dir reports/background-001/full-003 --timeout-seconds 600 --scope full`；Windows／Python **3.13.3**，2026-10-23T01:02:20.976464+00:00：**613 discovered、611 passed、0 failure/error、2 symlink 權限 skip、111 AST**，202.398 秒、exit **0**。passed_checks/source_unchanged=true，per_test_residuals=[]；guardian child_exited=true、exit0、remaining_owned_processes=0、forcibly_terminated=false。scope 為 fixture／SDK／Python fake CLI 與分列真 Windows owned Job APIs，不是 provider 掃描／真 agent／重開機／長時證據。

命令 `py -3.13 -B scripts/verify.py --run-dir reports/background-001/mock-final-002 --timeout-seconds 180 --scope mock`：**104/104 通過**、0 failure/error/skip，10.346 秒、exit0，source_unchanged=true、無殘留。mock 是 full 子集、不相加，不代表 Linux 原生支援或遠端 CI。full/mock source-manifest 同一最終來源；source-commit.json 另綁本地提交與文件。

命令 `py -3.13 -B reports/background-001/retained_probe.py 002` exit **0**：真 Windows 私有 Global Job／keeper 交接、兩個有限 fixture host、同一耐久 outbox。程式產生 **1 個合成 listener 事件**，receive後仍 pending／receipt0；合作 Stop、公開 serve確認 disabled、明確 Start後補收**同 event/query及payload**，明確 ACK、再次 ACK只有**1 張 SQLite receipt**。生成／唯一接收／query／ACK集合一致，missing=[]、duplicate_receipts=[]；預期重收1次。重啟另產生1個 monitor_gap，保持 pending，不被自動ACK。原始 generated-manifest、actual-operations（實際工具回傳與ACK前pending證據）、event/query集合、SQLite、control/ready/handoff/owner/stop回條及guardian退出保留在 `retained-002/`。子程序自然退出0、remaining0、未強停；fixture host受test guardian約束、lifetime_limited=true，交接時child_exited=null，不能當獨立常駐／真agent／主機重開機證明。

full的 lifecycle-evidence 另有實際Windows keeper交接、無關PID不能授權停止、只有本工具 hanging fixture Job被清理、真正stdio EOF等案例；預期強停案例保留forcibly_terminated=true，不能改報自然退出。中斷／generation競爭／手動disabled／滿載baseline與pending保留／backoff／Global跨session及Local拒判等為fixture/mock，分開記錄，不升格為OS故障注入。

正式命令 `py -3.13 -B scripts/eventguard.py --format json background start` 在正常一般使用者環境 exit **2**：`blocked / independent_background_unverifiable`、desired_enabled=true、model_calls=0、external_job_escape_attempted=false；命令執行端外部 Job 限制使獨立生命週期無法證明，**沒有正式 host 啟動**。啟用意圖保留供待批准同步排程接續，不使用breakaway。證據 `production-start.stdout.json`／stderr；既有live事件未ACK或清除。

排程只做唯讀查詢／dry-run。受限環境 `status` exit2：stage=get_folder、HRESULT80070003、parent_folder_confirmed=false，保持unknown。有限 sandbox 例外在正常一般使用者環境查同一安裝專用任務，exit0：stage=get_task、parent=true、HRESULT80070002／absent。兩context SID不同、任務名稱不同，沒有把受限identity套成登入使用者；不修改token、UAC、ACL或安全設定。原始query JSON／stderr在 `schedule-staged-query.*`、`schedule-normal-query.*`。

最終命令 `py -3.13 -B scripts/eventguard_schedule.py install --dry-run --start-now --plan-dir reports/background-001/schedule-review-002` 在正常一般使用者環境 exit0、executed=false。`schedule-review-002/plan.json`＋UTF-16 task.xml 綁當前使用者、Python3.13、全部核心／config／playbook hashes及單一ONLOGON／InteractiveToken／LeastPrivilege任務；無期限／不依賴網路或電池／失敗最多三次重試。**建立及一次立即Run尚待使用者批准，尚未執行。**原始含本機SID及路徑的計畫只留reports，不提交。Run接受不等於成功採集；批准後仍要核對host/monitor owner與coverage。

首輪 `full-001/` 原始 **2 failures／3 errors／2 skips** 保留，source_unchanged=true、guardian自然exit1、remaining0。實際CompareObjectHandles未由Kernel32匯出；改依 [Microsoft官方API](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-compareobjecthandles) 從System32 Kernelbase.dll載入並補缺DLL/export的拒絕測試。滿載案例誤比較輸入與收斂後資料，改為比較實際保存前後的payload hash；不改產品丟棄／保留政策。審查發現啟動ready或serve backoff/setup Ctrl+C可能漏耐久disable，已修generation比對、合作清理與相應案例。

第二輪 `full-002/` 原始 **1 failure／0 errors／2 skips** 保留，source_unchanged=true、自然exit1、remaining0。hanging Job已空但已核對的owner HANDLE尚未signal；新stop_persistent改在原有3秒退出預算內等待同一HANDLE，逾時仍不確認。新增延遲／逾時fixture，實際強停案例保留原斷言；最終003通過。早期retained-001/mock-final與舊plan只作歷史，不代替最終來源。

本批沒有再做七來源全機採集、登出／重開機、Phase7注入或24小時soak；既有監看可見性不能沿用舊成功宣稱長期完成。正式模型預算未初始化，沒有模型輪詢、任務或新永久帳戶權限。`completion-audit.json` 重讀最終來源、實際操作、SQLite／ID、退出回條與文件連結；原始執行資料全部忽略不提交。

## 2026-10-23：由使用流程完成實作與統一驗證

基底 `d4257437757a701874c6f00de6022340bff2bc94`、同一 feature 分支。按使用者要求全面盤點、兩層互斥 ownership 平行開發；子代理只實作及寫案例，所有功能完成並交叉審查後才由主線統一測試。架構、功能斷點與整合決策見 [USABILITY_IMPLEMENTATION](USABILITY_IMPLEMENTATION.md)。沒有真 Codex／模型、部署、永久 MCP 註冊、提權、服務／排程、Phase 7 注入或長期監看，原有研究目錄保留。

**前批完整數字來源**：`reports/usability-001/full-002/verification-summary.json`。命令 `py -3.13 -B scripts/verify.py --run-dir reports/usability-001/full-002 --timeout-seconds 600 --scope full`；Windows／Python **3.13.3**，2026-10-22T22:58:41.264908+00:00：**528 discovered、526 passed、0 failure/error、2 symlink 權限 skip、105 AST**；238.956 秒、exit **0**。passed_checks/source_unchanged=true、per_test_residuals=[]；guardian child_exited=true、exit0、remaining_owned_processes=0、forcibly_terminated=false。scope 為 fixture／SDK／Python fake CLI 與分列真 Windows owned Job API，不是 provider 採集或真 agent。新增停止、同輪閘道、資料保存、綁定、namespace、控制字元、容量及原子替換案例均納入。

命令 `py -3.13 -B scripts/verify.py --run-dir reports/usability-001/mock-final --timeout-seconds 180 --scope mock`：**104/104 通過**、0 failure/error/skip，10.12 秒、exit0、source_unchanged=true、無殘留。mock 是 full 子集，不相加，不代表 Linux 原生支援或遠端 CI。full/mock source-manifest 相同；本地 source-commit.json 將受測來源與本批文件綁定實際 Git tree，執行資料不提交。

命令 `py -3.13 -B reports/usability-001/workflow_probe.py workflow 003` exit **0**。使用實際分開的 CLI 程序、隔離 root 與三幀 fixture，由確定性規則真正產生 protection/listener/persistence **3 個不同事件**；生成／接收／query／ACK／SQLite receipts 的 ID 集合與計數相符。每件 receive 後取得 query ID，明確 ACK，再重複 ACK 不新增回條；missing=[]、duplicate_closures=[]，report 共三件、再啟動 stopped、owner record 已移除、所有 managed 子程序自然退出／remaining0。重啟另產生一件預期的 planned monitor_gap，保持 pending；它未參與前面三個規則事件的 ACK。SQLite 讀回確認總共四件、三 ACK／一 gap pending，沒有把新 gap 忽略或自動結案。這是人類 CLI 的合成工作流程，沒有真模型。原始 argv、exit、stdout/stderr、Job 回條、觀察、HTML/JSON、SQLite 及集合比對留在 `workflow-003/`，不提交。

完整 suite 的 `test_operator_api.OperatorMCPTests.test_real_stdio_protocol_views_and_eof_exit_without_agent` 以**真 Python stdio＋已安裝 SDK**呼叫十三個 operator tools，包含 scoped status/overview、observation、事件診斷、receive→query ID→ACK、report、stop，EOF 自然退出0。`full-002/lifecycle-evidence.json` 保存全部 request／response、同 event/query、單一 SQLite receipt；與 CLI 共用核心。不是 agent、模型、工具已載入目前聊天或新自動喚醒證明。原三工具接收契約保持相容。

命令 `py -3.13 -B reports/usability-001/workflow_probe.py native` exit **0**，**一般權限固定七來源各呼叫一次**，透過新版本 native worker／Runner，保存安全來源投影，再由真 CLI sources/overview/report 讀取。這不是持續 monitor、狀態注入或 agent；全部 owned worker 自然退出、remaining0、無 owner 殘留。證據在 `native/collection-attempts.json`、`native-summary.json`、`collector-exit.json`、commands 與 data/live/observations，原始主機 metadata 留本機。

| 來源 | 實際狀態／總列數 | 限制或拒讀證據 |
| --- | --- | --- |
| Defender | partial／11 | effective_defender_status_unavailable；可讀設定不等於有效防護，部分 optional registry Win32 2 |
| listeners | partial／190 | 表可讀；部分 ListenerOpenProcess object/access_denied/Win32 5，身分未知 |
| processes | partial／615 | 部分 OpenProcess object/access_denied/Win32 5；PID 0 object_unavailable/87 |
| startup | ok／21 | 本輪來源可讀，不是惡意／安全結論 |
| services | ok／315 | 本輪來源可讀，不表示已判斷服務暴露或漏洞 |
| tasks | unknown／0 | TaskGetFolder object/COMError HRESULT -2147024893（0x80070003）；不能當作主機沒有工作 |
| versions | ok／1 | 固定 allowlist 的版本資料，不是全機軟體／修補適用性證明 |

上述是採集總列數；每來源只保存最多200列，CLI本次預設顯示20列，total/exported/truncated明示。listeners較舊 Phase 1 的 success 改為 partial，是本次新增當次程序身分查核發現拒讀，不是把端點表讀取改成失敗。fallback 未在本輪重跑；舊 H1–H5 證據的界線保留，未定案 ACL／token 根因。

首輪 `full-001/` 保留 **4 failures、2 errors、2 skips** 的原始紀錄，source_unchanged=true、guardian 自然退出、remaining0。發現 Windows reader／os.replace 的 WinError5 瞬時共享衝突導致 monitor thread 提早退出；修正為僅5/32/33最多190ms重試，永久錯誤仍失敗，另修測試在失敗時釋放第二把鎖。dispatcher 初版把全 not_started 的 mocked ACK 當失敗投遞歸檔，已限縮為至少一筆有完整樹退出證據的 complete attempt，保留未啟動語義。capture 的50ms測試回4可確定是耐久 admission 後、spawn前逾時；100ms測試先讀回條掩蓋返回碼，當次檔案已隨temp清理，不能完全排除其他原因。兩項改用2秒的實際啟動預算、保留原自然／強停／零殘留斷言，產品 deadline 不放寬，短deadline no-spawn測試仍保留。

最初 workflow probe 假設中文字 stdout 是UTF-8，實際為Windows既有編碼，讀檔失敗；`workflow/`的CLI原始輸出保留，僅修證據腳本的解碼，沒有改系統編碼。`workflow-002/`已通過；後續原子替換／dispatcher修正後，以最終來源重跑上面的003。沒有用失敗或舊綠燈替代最終結果。

命令 `py -3.13 -B reports/usability-001/audit_evidence.py` exit0：重讀保留 SQLite／request-response／每份 Job 回條，核對 **115 份當前受測來源 hashes**、十三工具、七來源、三規則事件與額外 gap 的待收狀態、README **73行**及本批十份文件的相對連結；結果在 `completion-audit.json`。最初只讀 evidence reader 誤假設 event_type 是 SQLite 欄位，已改從保存 payload 取型別再驗，沒有修改資料庫或重造事件。這是證據重讀，不是新的模型／採集／狀態注入。

限制：沒有24小時soak、實機listener/HKCU注入、登出／重啟、真模型或目前聊天工具接入驗收。未知shutdown只在命名私有Job可證明空／銷毀時恢復；legacy缺Job身分、inbox完成證據先輪替等仍明示阻擋，不能刪marker／帳本假裝恢復。正式agent預算未初始化；沒有持續背景程序、排程／服務、自啟、推送或手動CI。

## 歷史：2026-10-23 共用耐久預算、退出閘道與操作狀態

基底 `3b0461988c6bc36f13d514e1e5263c91b4715123`、同一 feature 分支；三個有限子代理的預審保存在 `reports/parallel-preflight-001/`。主線整合共享入口，子代理沒有各自提交或重跑整套。正式 agent 帳本未初始化，沒有真 Codex／模型、全機採集、網路部署、提權、排程或 Phase 7 注入。

本批完成：legacy run/retry 與 generic capture CLI 退役；舊 status 純讀；dispatcher/acceptance 共用嚴格 attempt/PID+建立時間/Job 退出驗證。固定安裝 authority 先原子扣帳、一次性 argv/prompt digest、全域 active/unknown-exit、UTC+08 每日五次、事件三次、不退款、未知 bootstrap 阻擋與 terminal/tombstone 保留。最後 gate 與 OS create 之間採 serialized owner permit；午夜拒絕不留下不可恢復的未啟動 reservation。status 分開 last_report/current owner、逐來源 freshness、逐 namespace 故障，報告明示 total/exported/truncated。契約與限制見 [AGENT_BUDGET](AGENT_BUDGET.md)。

**本版完整數字唯一來源**：`reports/shared-budget-001/full-final/verification-summary.json`。命令 `py -3.13 -B scripts/verify.py --run-dir reports/shared-budget-001/full-final --timeout-seconds 600 --scope full`，Windows/Python **3.13.3**，2026-10-22T21:57:07.230903+00:00：**441 discovered、439 passed、0 failure/error、2 symlink 權限 skip、95 AST**，136.975 秒、exit **0**。passed_checks/source_unchanged=true、per_test_residuals=[]；guardian child_exited=true、exit0、remaining_owned_processes=0、forcibly_terminated=false。scope 是 fixture/SDK/fake CLI 及分列真 Windows owned Job API，不是 provider 採集或真 agent 驗收。

命令 `py -3.13 -B scripts/verify.py --run-dir reports/shared-budget-001/mock-final --timeout-seconds 180 --scope mock`：**104/104 通過**、0 skip/failure/error、5.609 秒、exit0，source_unchanged=true、無殘留。mock 是 full 的明示子集，不相加，不代表 Linux 原生支援或遠端 CI。兩者 source-manifest 必須與目前受測來源完全相同；提交後以 `reports/shared-budget-001/source-commit.json` 綁定 Git tree 位元組，`completion-audit.json` 對照各完成條件／測試／來源／文件。

保留完整資料的命令 `py -3.13 -B reports/shared-budget-001/probe.py` exit0；輸出 `{passed:true, unique_generated:7, received:8, queried:8, acked:7, daily_usage:{2026-10-23:3,2026-10-24:5}, remaining_owned:0, model_calls:0}`。這是 **Python fake CLI、實際本機 SQLite、Windows 私有 Job、兩個 fake clock 預算日**；未改系統時鐘，不能宣稱跑了兩天或八個真模型任務。`retained-probe/id-comparison.json` 保存生成／接收／query／ACK ID 集合與 Counter 比對；missing=[]、duplicate_closures=[]，唯一重複接收是 recovery 同 event/query 的預期補收。四案例 manifest、JSONL/stderr、實際工具回傳、SQLite receipts、pending-proof、八份自然退出回條均留在同一 ignored reports 目錄，沒有提交 runtime。

其他必要證據在完整 suite：八個並發連線競爭最後額度；跨 acceptance/dispatch/retry 五次實際 Python fake CLI，第六次換目錄／來源零 worker；未知退出跨來源／次日；票證重播／命令變更拒絕；marker/DB 缺少、損壞、busy、byte/count 滿載與保守恢復；保留每日／事件計數與 retired-token 摘要；人類 budget CLI 與合成 namespace／heartbeat／>1000 報告。它們不是帳戶級防竄改或真模型成本證據。局部命令與輸出亦保留在 budget-unit-result.json、完整 unit-tests.txt 與 lifecycle-evidence.json。

保留非最終結果：第一個主線 22 項局部測試有 1 項失敗，新的 strict verifier 先拒絕非零 CLI，原測試預期的 stage_failed 尚未保存；修成保存明確 failed assessment，再回固定 stage failure，不放寬自然退出／ACK 判定。budget 最初 default validator keyword 不一致導致 fixture capture return2，修正介面並補 actual writer schema 測試。初次 budget tests 的 SQLite fixture 未 close 造成 teardown WinError32，改 closing；report fixture 超出產品事件上限被正確拒絕，改為明示直接填入 legacy fixture，不放寬產品 cap。這些早期失敗不列通過。

`full/` 的前一版 **440 discovered／438 passed／2 skip**、exit0，沒有程序殘留；最終唯讀審查仍找到午夜 prelaunch reservation 缺口，因此新增修正與回歸後才執行上面的 full-final/mock-final。舊綠燈不能替代未覆蓋的邊界；原記錄保留，不終止測試掩蓋問題。operator 最終審查也指出 budget status 會更新耐久時鐘檢查點，文件已明示它不初始化／不扣額度，但不是帳本位元組唯讀。

限制：時鐘回退／超過36小時未觀測會保守阻擋；日彙總、事件／retired-token 摘要仍有限容量，不能刪帳歸零。沒有 24 小時 soak、登出／重啟、實機狀態注入、真 agent 或 provider 重驗。Phase 7 與敏感／不可逆操作仍須當次批准。未推送或手動觸發 CI，原有 docs/research/ 保留。

## 歷史：2026-10-23 Phase 5 收斂及 Phase 7 計畫

起點 `fa572ca33a972be5ffc691ba3a48b2ccbf256d06`，同一 feature 分支。新驗收使用正式 QueueInbox，重用 dispatcher command/capture/assessor；舊重複 producer/capture 已移除，保留原 wire schema 的測試與 SQLite 唯讀證據 reader。停用 bridge 移到 contrib，核心 import 隔離；四個 cmd 入口改為檢查既有 Python 3.13，CI 僅備妥設定。差異與相容理由見 [收斂對照](DELIVERY_CONSOLIDATION.md)。

本批唯一完整數字來源 `reports/phase5-consolidation-001/verified-complete/verification-summary.json`。命令 `py -3.13 -B scripts/verify.py --run-dir reports/phase5-consolidation-001/verified-complete --timeout-seconds 600 --scope full`，Windows/Python **3.13.3**，2026-10-22T21:13:40.762835+00:00：**355 discovered、353 passed、0 failure/error、2 symlink 權限 skip、86 AST**；135.892 秒，exit **0**，passed_checks/source_unchanged=true、per_test_residuals=[]。guardian 自然退出、child_exited=true、exit 0、remaining_owned_processes=0、forcibly_terminated=false。scope 是 fixture/SDK/fake CLI 與分列的真 Windows owned Job API；沒有本輪資產掃描或真模型。

命令 `py -3.13 -B scripts/verify.py --run-dir reports/phase5-consolidation-001/mock-final --timeout-seconds 180 --scope mock`：**104/104 通過**、0 skip/failure/error、exit 0、source_unchanged=true、無殘留。這是上面 suite 的明示子集，不相加；不是 Linux 原生支援或遠端 CI。full/mock 的 96 份受測來源 hashes 完全相同，含 contrib、cmd 與 workflow；提交後以同目錄 source-commit.json 綁定實際 Git commit 位元組。

保留原始證據的 probe：`py -3.13 -B reports/phase5-consolidation-001/probe.py` exit 0，`probe/manifest.json` 四案例 passed，**7 個唯一 synthetic events、8 次 receive/query、7 筆真本機 SQLite ACK receipts，missing=[]、duplicates=[]**；recovery 有 pending-proof，同 event/query 補收。CLI 是明示 **fake Python CLI**，不是 Codex；JSONL、工具返回、manifest、DB、inbox 與 owned child 自然退出回條都保留。十二組搬移前後 synthetic projection 全物件相同。最後來源另對原 fake traces 做 verify，沒有再開模型／重造事件。

實際新 single/continuous/batch/recovery 準備入口四項 exit 0，舊 single alias 準備 exit 0；沒有 --execute，不啟動 agent。bridge check exit 0 且 listener_started/credentials_read=false。cmd 既有 Python --version 成功；只在 child 的 PATH 排除 Python 後回 exit 2，系統 PATH 未改。入口 argv/stdout/stderr/Job 回條見 entry-probes.json、compat-entry-probes.json、cmd-missing-python.json。

保留失敗與未完成證據：初次新等價 fixture 使用 SQLite connection 的交易 context 卻未 close，導致臨時 DB WinError 32；改為 closing，不放寬 ACK 檢查。`final/` 的完整輪有一項既有 Job 測試失敗：Job active=0，但立即只查舊 PID 顯示 alive，無殘留；原證據不能確定是退出時序或 PID 重用。測試改為先記 PID+建立時間、有界等待確認原身分退出，並用獨立 owned Job sentinel；增加延遲／PID 重用 fixture，不變更生產終止邏輯。`verified-final/` 工具會話失聯、日誌中斷且沒有摘要／退出回條，記為未完成、退出狀態未知，不列為通過；後續另用新 verified-complete 目錄完整驗證。所有失敗紀錄保留。

文件檢查 `py -3.13 -B reports/phase5-consolidation-001/check_docs.py` 核對本批本機連結、README 上限及七份歷史快照 hashes；結果見 docs-check.json，不宣稱查過外部連結或其他研究文件。未推送、未遠端 CI、未啟動模型／監看／排程／服務、未提權或改安全設定。每日五次耐久總額仍是缺口；現有 max_tasks=5 僅每輪。Phase 7 [可逆實機與故障恢復計畫](WINDOWS_VALIDATION_PLAN.md) 已獨立提交 `cda77a0b031f2368a9b504c2fa84820442c37adc`，和 24 小時 soak 都尚未執行，仍須當次批准。

## 2026-10-23：文件落地與維護目標更新

本批只改公開專案文件，未修改 src／scripts／config／tests／playbooks。README 短入口、STATUS 一頁現況、HANDOFF 與 [維護目標](MAINTENANCE_GOAL.md) 已收斂，下一個程式實作為 Phase 5；Phase 2 舊 A／B 關卡不再等待。原文件保存在 [history](history/README.md)，來源提交與搬移 hashes 見 snapshot-manifest。操作、架構、接線與 collector 文件已校正 Phase 3 Job／Phase 2 診斷的過期說法。

實際用既有 `py -3.13`（Python 3.13.3）在 `reports/docs-refresh-001/quickstart` 執行 README 的隔離 fixture 流程：monitor、synthetic emit、同 event inspect、JSON／HTML report 四個 CLI 都 exit 0；監看 stopped、同 event ID、SQLite 一件 pending／零 receipt。這不是 agent 接收或 Windows provider 採集。真 stdout／stderr、命令 argv 與報告位置保存於 `reports/docs-refresh-001/quickstart-manifest.json` 及鄰接檔案。

命令 `py -3.13 -B reports/docs-refresh-001/check_docs.py` exit 0，驗證本批文件及移存快照的相對連結目標存在（不檢查 anchor 或外部網路），README 行數上限、原檔／移存 hash 與受測來源一致性；實際計數與結果見 `reports/docs-refresh-001/docs-check-final.json`。首次檢查腳本未明示 UTF-8 而被 Windows cp950 解碼拒絕，改為顯式 UTF-8 後再驗證，沒有更改程式或放寬檢查。未重跑完整 suite、模型、採集、排程、soak 或 Phase 7；最近完整程式測試仍是下節 Phase 4。

已實際讀取 App goal，仍是舊 objective／blocked；目前 API 沒有更新 objective 或恢復操作。沒有重建 goal、開自動喚醒排程或誤標整體完成；可核對的目前工作目標保存在專案文件。所有命令與 reports 路徑均相對於專案根目錄。

最新完整程式驗證對應提交 `1e90a5398c5d4c555924bffb70bb77cb429dd782`（Phase 4）。本機 `reports/phase4-capacity-001/verified/source-commit.json` 已比對全部受測來源位元組；文檔整理沒有重跑或變更程式驗證。下節的「基底」是該批工作開始版本，不是最後提交。

| 階段 | 已提交程式／文件 | 證據性質 |
| --- | --- | --- |
| Phase 0 | `dbac91b` | 靜態稽核，保留 AUDIT 原文 |
| Phase 1 | `088be75` | 七來源一般權限實測；部分 coverage 仍不足 |
| Phase 2 比較／共用介面 | `a130dce`／`c09f396` | fixture、SDK stdio；無新真模型 |
| Phase 3 | `677fe2a` | 真 Windows 私有 Job API＋分開標示的 hanging fixture／gap fixture |
| Phase 4 | `1e90a53` | synthetic SQLite／檔案滿載恢復；沒有 24 小時 soak |

下文保留各時間點的工程日誌。只有最近的驗證節代表目前程式基準；其餘舊「尚未實作／等待選案」均屬當時狀態，不構成今天的阻塞或操作授權。

## 歷史：Phase 4 容量／保留已實作（2026-10-23 03:11 台北）

基底 `677fe2a6b78e7f961be45693c8e95d00a5f2a88f`，同一 feature 分支。ACKed payload／review 的 TTL 與壓力清理、有限 receipt 去重窗、inbox 完成回條合併／輪替、dispatcher 已核實 terminal 帳本壓縮及上限已接入；設定見 `config/default.json` 與 [STORAGE_RETENTION](STORAGE_RETENTION.md)。pending／retry／未 ACK failed 都不清除，移除舊七天 failed 自動清除邏輯。上限存在 SQLite／inbox 專用政策，ACK opener 沿用；status 顯示 outbox 實際政策及輪替數。inbox admission 預留收尾空間；帳本開始 child 前預留終態更新大小。

唯一完整測試數來源：`reports/phase4-capacity-001/verified/verification-summary.json`。命令 `C:\Python313\python.exe -B scripts/verify.py --run-dir reports/phase4-capacity-001/verified --timeout-seconds 600`；Windows／Python **3.13.3**，2026-10-22T19:11:31.019298Z：**343 discovered、341 passed、0 failure/error、2 symlink 權限 skip、80 AST**，131.775 秒，exit **0**。`passed_checks=true`、`source_unchanged=true`、`per_test_residuals=[]`；guardian `child_exited=true`、exit **0**、`remaining_owned_processes=0`、`forcibly_terminated=false`。scope 含 fixture／SDK／fake CLI 與分開標示的真 Windows Job API，沒有模型或七來源全機採集。

新增 17 項容量測試覆蓋：count／byte 失敗回滾、ACK 後恢復、TTL 與 review 清理、未 ACK failed 保留、政策跨 opener、ACK 不改寫／衝突拒絕、inbox 同 query／result 重播及 mutation busy、completion 寫入失敗修復、來源 pending 與完成檔衝突、帳本 archive 前後寫入／中斷恢復、byte／count／TTL 輪替，以及 **64 KiB 下 100 次入列／ACK 循環仍保留指定 pending hash**。首次 targeted 測試的唯一錯誤是新 review fixture 缺少既有 API 必需的 payload_hash；補齊 fixture 後 17 項通過，未放寬來源比對。另有既有 73 項相關測試通過；不能與完整數重複相加。

保留實體證據的命令 `python -B reports/phase4-capacity-001/capacity_probe.py` exit **0**：`probe/manifest.json` 的 **5 個案例全部 passed、missing=[]**，涵蓋 outbox count／bytes、inbox count／bytes 與 dispatcher 帳本。manifest 核對原始 offered／accepted／ACK／恢復 event ID、前後 pending hashes、同 query、實際回傳與真 SQLite receipts；各 source DB／inbox 完成檔／帳本均保存在相鄰 probe 子目錄。沒有直接讀取或清理正式 data。帳本的 terminal child／交付成功欄位是明示的合成 fixture，不能升格成真 agent 或真 child exit 證據。

完整 suite 輸出、source hashes、每案例 lifecycle evidence、guardian 退出回條都在 verified 子目錄；提交後 `source-commit.json` 對照本次提交與所有受測來源位元組。執行資料／manifest／DB／完整 trace 仍在 Git 忽略目錄，未提交或推送。

**尚未驗證與限制：** [24 小時 soak 計畫](SOAK_PLAN.md) 已寫，**尚未執行**；也未跑長時 provider、登出／重啟、Phase 7 注入或新真 agent。去重與已完成歷史有有限保留窗，壓力可提前輪替；不承諾永久 exactly-once。SQLite free pages 重用而不自動縮檔，journal／原子寫入暫存／檔案系統開銷及完整 reports 另計。全是未解決資料時維持明確背壓，不能藉清 pending 假裝恢復。本輪未啟動模型、長期背景程序或排程，未提權、下載安裝、改安全設定、處理其他程序或推送。Phase 5 收斂尚未開始。

## 前一階段：Phase 3 已實作並驗證（2026-10-23 02:32 台北）

本批基底 `c09f396745fe835df45b3986ae704c0213054c43`，同一 `feat/local-codex-acceptance` 分支；保留既有歷史與執行資料。新增 Windows 私有 Job Object：子程序在建立時原子加入，協作寬限後只回收本工具 Job，保存 PID＋建立時間、強停原因、退出碼與剩餘數。native 查詢改成固定 section 的 Python worker，與 PowerShell fallback 共用 Runner；monitor、capture、dispatcher／驗收 supervisor、watch、smoke 入口已接入。AGENTS 的強停限制已限縮為不得處理非本工具啟動的程序。契約及界線見 [PROCESS_LIFECYCLE](PROCESS_LIFECYCLE.md)。

啟動先核對前次 checkpoint／heartbeat／PID 建立時間，建立 unknown coverage 的 `monitor_gap`。滿佇列或保存失敗時保留同 ID marker、停止新採集並顯示 `blocked_monitor_gap`；恢復後再耐久入列。查詢無法確認退出時顯示 `shutdown_unconfirmed`，不宣稱 stopped。ACK 與診斷的原有語義保留，強停樹不能通過投遞驗收。

**本輪唯一完整測試數來源：** `reports/phase3-process-005/verification-summary.json`。命令 `C:\Python313\python.exe -B scripts/verify.py --run-dir reports/phase3-process-005 --timeout-seconds 600`；Windows／Python **3.13.3**，2026-10-22T18:32:43.540422Z：**326 discovered、324 passed、0 failure/error、2 symlink 權限 skip、78 AST**，87.502 秒，exit **0**，`passed_checks=true`、`source_unchanged=true`、`per_test_residuals=[]`。guardian PID＋建立時間及實際回條在 `guardian-exit.json`：`child_exited=true`、exit **0**、`remaining_owned_processes=0`、`forcibly_terminated=false`。此數字不可與歷史測試數相加。

證據留本機忽略目錄：同目錄 `source-manifest.json`、`unit-tests.txt`、`worker-summary.json`、`lifecycle-evidence.json`、worker stdout/stderr、guardian 回條；提交後的 `source-commit.json` 核對測試 source hashes 與實際提交。實測分界：一般 token 的真 Windows Job／孫程序／巢狀 Job／owner 異常退出／外部於目標 Job 的合成 sentinel；hanging Python fixture 的 Runner、capture stdin、monitor stop 與全域期限；固定 Python executable 版本 worker smoke。`monitor_gap` 的 stale／identity／時鐘／損壞 checkpoint、滿載與同 ID 恢復是 **fixture＋SQLite**，不是登出／重開機實測。

排程命令 `python -B scripts/eventguard_schedule.py install --dry-run` 與 `uninstall --dry-run` 都 exit **0**、`executed=false`；`install --execute` 仍 exit **2**、`approval_required`、`executed=false`。輸出與三個乾淨退出回條在 `reports/phase3-schedule-001/manifest.json` 及鄰接 stdout/stderr。沒有執行 schtasks 或建立／刪除排程。

保留失敗證據：`phase3-process-001/002` 是 guardian baseline 尚未辨識 discovery 建立的 conhost 而失敗，改為比對固定 Job 成員 PID＋建立時間；`003` 找出新增事件類型上限、未受管 fake stop 相容性與舊 pending timeout 預期；`004` 只剩新增測試使用低於既有最小值的 duration。修正後才跑 `005`，沒有覆寫前次證據。`003/004` 的逐項殘留都為空、最終 guardian 剩餘 **0**；超短期限實際 runner 的失敗交付與自然退出診斷見 `reports/phase3-timeout-diagnostic-001/`，未冒充真模型驗收。

**尚未驗證／與 AUDIT 差異：** 原先無法停止卡住 OS 查詢的限制已改由 worker Job 隔離並以 hanging fixture 驗證；native 一輪改為七個短期 Python worker，增加的性能成本未量測。沒有重跑七來源 provider 採集、真模型、登出／重開機、Phase 7 狀態注入或長時 soak；兩個 symlink 測試仍略過。沒有啟用長期監看、自啟、服務或排程；沒有提權、網路、下載安裝、修改安全政策、強停非本工具程序或推送。下一階段為 Phase 4 容量／保留；本次交付停在 Phase 3。

以下保留歷史紀錄，其舊限制與舊測試數不代表目前實作。

更新：2026-10-22 UTC。本檔只記錄工程事實，不包含真實主機的警報、路徑或安全結論，也不授予操作權限。

**本機耐久佇列已接通專用 Codex CLI agent；完整產品仍為工程預覽。** 有限合成 A／B1／B2／C，以及新增前景入口的合成與有界實機佇列接收試跑均已有真工具證據；本輪已退出，目前沒有持續監看。完整 coverage、長期可靠性及原生診斷仍未驗收。最新證據見本檔末節與 [LIVE_CHANNEL](LIVE_CHANNEL.md)；以下保留各時間點歷史，不以 mock 或舊測試冒充新結果。

## 歷史協定基準：本機 stdio MCP 等待（04:16 UTC）

雲端部署／host／HTTPS 路線已停止推進，既有程式保留停用。新增 local_wait.py、scripts/eventguard_local_mcp.py 與專用測試：只等待合成事件、查已保存 snapshot、同事件結果先落盤再 ACK。沒有註冊 MCP、寫設定、啟動模型、開網路埠或啟用正式監看。

官方 Codex 預設工具逾時 60 秒，可調整；永久等待、逾時後不恢復推理均無已驗證保證。真實 Codex 一次 wait→query→ACK 的實驗需另有精確批准；[實驗範圍與命令](LOCAL_MCP_EXPERIMENT.md)。本地協定測試結果與真模型驗證必須分開。

2026-10-22T04:16:27Z：`python -B scripts/verify.py` 通過 202 tests（0 failure/error/skip）、44 Python AST，26.808 秒。新增 6 個後端測試與 4 個真正 stdio／SDK 測試：事件返回、查證／ACK、逾時、取消不回覆已取消 request、EOF 自然退出、缺 SDK 失敗方式與外部合成 producer。測試自己啟動的子程序均已自然退出；未使用 kill／terminate。

04:16:35Z 的獨立合成 stdio trace 確認協定協商 `2024-11-05`、等待 0.569 秒後返回、同 event/query 的結果與 ACK、child exit 0；原始證據只在忽略的 reports。本次 client 是已安裝 Python MCP SDK 1.6.0，模型呼叫 0，原生採集 0。不是 Codex 模型接續、長時性能或永久等待的驗證。

## 新接線程式增量（未部署）

- 已加入 `src/eventguard/mcp/` 與 `scripts/eventguard_bridge.py`：authenticated MCP 方法、訂閱保存、驗證 callback、簽章 HTTPS、producer 入口／adapter、限額內合成證據查詢與結果修訂。沒有 OAuth 授權伺服器；固定 Bearer 是 API-key 模式，需平台／自訂 plugin 實際支援與另行批准的 credential。
- 2026-10-22T03:50:53Z：完整 suite **192 tests、0 failure/error/skip，40 AST 通過**，16.508 秒；全部合成／mock，DPAPI 僅公開測試 fixture。舊 91 tests 是基準，不能與新數字重複相加。
- bridge `check` 確認範例停用、不開 listener、不讀 credential；停用設定的 `serve` 拒絕啟動。所有測試沒有開埠、真 DNS／HTTPS、模型或原生安全採集。
- 已覆核並修正 producer Authorization 與 callback 標頭隔離、目前 subscriber／host 授權縮限、非法 JSON-RPC ID、同 key refresh 不重複保存 vault 及短 TTL 輪替。
- 部署與平台互通仍 **pending**。普通本機 Codex task 的外部喚醒沒有被此程式實作或驗證；候選目標為受支援的 Work Cloud／dot 訂閱聊天。

明確容量界線：bridge 1000 個事件、20 個訂閱（含 revoked）、每事件20筆查證／10次不可變結果修訂；DB 主檔8MiB，DELETE journal 可能有額外暫存空間；不自動丟棄 pending，也尚無自動保留清理。DPAPI vault 最多128個加密檔，正常同key刷新重用ref，key更換／重訂閱仍需容量管理。DNS查詢有10秒呼叫端上限，但OS resolver不能kill；每poster僅1未完、全process最多4個daemon resolver，自然退出前可能仍pending。這些限制須在部署前納入維護與長時驗收。

詳細範例與接線條件見 [MCP_BRIDGE_DEPLOYMENT](MCP_BRIDGE_DEPLOYMENT.md)。新原型不解決原生 coverage 缺口，也不滿足「真正 agent 喚醒→診斷→同事件結果」的產品完成定義。

## 已完成及證據

| 項目 | 已驗證範圍 | 不能據此聲稱 |
| --- | --- | --- |
| 無 GUI headless 核心 | 前景執行、分層頻率、單例、合作停止、狀態與本機心跳 | 已安裝長駐、服務、自啟或獨立 watchdog |
| 七類採集與診斷介面 | Defender 設定、監聽端點、程序 metadata、啟動項名稱、服務、排程 metadata、固定 Python runtime 版本 | 所有 Windows 主機均已實測、完整資產盤點、連線流量／事件全文／簽章／威脅歷史已涵蓋 |
| 確定性規則 | baseline/diff、去重、cooldown、升級、兩次完整成功觀察才恢復、coverage 降級 | 沒有事件代表安全、歷史 inactive 代表已清除 |
| 耐久儲存 | detector state 與 outbox 同交易、容量背壓、重試、租約、ACK 與重啟去重 | exactly-once、無限重試、磁碟永不滿 |
| 宣告式 playbook | 四條規則、結構驗證與 dry-run；不執行工具或處置 | 寫入規則就取得權限、agent 已依此完成調查 |
| 輸出 | 本機 JSON 與 escaping／CSP 的 HTML | 已上傳、已被 agent 閱讀 |
| 測試 | Windows／Python 3.13.3：2026-10-22 02:55:12 UTC，91 tests、0 failure/error/skip，26 Python AST 通過 | Linux／雲端全套已過、原生採集全數成功 |
| 合成 smoke | 02:55:15 UTC，正常兩輪零事件、outbox→mock ACK→合成診斷→mock_closed、重複抑制、跨程序單例／停止；殘留測試子程序 0 | 真正 Codex／dot 被喚醒、真實系統處置已完成 |

上述測試對應本機保留的驗收快照 `fd45578`。發布用原始碼／測試／設定／playbook 應逐檔核對與該快照相同；文件可另行演進。測試原始輸出只保存在本機忽略目錄，未作為公開範例或上傳主機報告。重現方式見 [DEVELOPMENT](DEVELOPMENT.md)。

## 獨立原生驗收摘要

後續獨立驗收確認固定快照、91 tests 與 26 AST 一致；工具可啟動、接受合作停止並退出。但部分原生來源回傳 denied，整體結論仍為 **BLOCKED**，且沒有真正 agent 喚醒。這不是安全或入侵結論。單次程序 RAM 峰值不包含所有子程序，不能當作長時資源驗收。原始實機報告、警報與執行資料不納入 Git；公開協作只保留此工程摘要。下一步依 [COVERAGE_PLAN](COVERAGE_PLAN.md) 分來源核實執行身份／API 可用性，不提高整個程序權限、不繞過拒絕。

## 已知限制與風險

- `query_persistence_diff` 目前回傳 `current_only`，不實作診斷基線比對；名稱不能取代回應中的 coverage。
- 版本查詢僅固定 Python runtime；無一般產品更新判斷。未提供 Authenticode、威脅歷史、原始事件內容或網路探測。
- 監聽範圍區分 localhost／LAN／all interfaces，不能由此推定 Internet 可達。
- 每輪採集預算 45 秒，預算跳過來源以 30 秒短退避重試。單查詢期限 15 秒／輸出上限 4 MiB；已開始的 OS 查詢不 kill，pending 時保留單例鎖，自然退出前 stop 可能等待無限久。
- 每次 evaluation 最多交付 20 事件，延後事件保留原 ID；這不是獨立每分鐘速率限制。pending 不被容量輪替偷偷丟棄；滿載時明示降級並保留舊基線。
- 最多 8 次傳輸嘗試、有限去重保留窗及 ACK 儲存預算；超窗或不確定投遞須核對收據，不可猜測成功。DisabledAdapter 不增加 attempts。
- 程序／主機全停無法自我告警。`status` 是最後報告，不能證明目前程序存活或主機安全。
- 停止或重啟後不會自行恢復；服務、排程、開機自啟及獨立 watchdog 均未安裝。

## 資源預算：目標與實測分開

| 指標 | 驗收目標或實際機制 | 實測狀態 |
| --- | --- | --- |
| 一般採集 | Defender／監聽／程序 120 秒，啟動／服務／任務 600 秒，版本 21600 秒 | 設定與排程邏輯已測；未做長時主機負載量測 |
| 並行／優先序 | 單原生查詢，監看程序嘗試 below-normal；增量規則，不做 AI heartbeat | 邏輯已測；整體 CPU／I/O 效果未量測 |
| CPU／RAM／I/O／電池 | 完整目標在 TARGET_DESIGN，需 idle 與高負載基準、電池／插電情境及分位數 | **未量測，不聲稱達標** |
| 儲存 | outbox 1000 事件／8 MiB 等預設，日誌輪替與背壓 | 容量／失敗案例已測；長時／磁碟故障實機驗收未做 |
| 真 ingress | 無事等待不推理，只有事件開啟必要回合 | 有界 CLI 接收已通過，見末節；長期運作未驗收 |

## 下一步與完成定義

1. 依 [INGRESS_PLAN](INGRESS_PLAN.md) 選定受官方支援的接收端與任務語義，確認憑證、有效授權、持續權限與成本；不能把建立 GitHub 儲存庫或雲端開發環境視為接線完成。
2. 實作可信 adapter 與 receiver；僅在明確批准的最少合成資料範圍先測。ACK、agent run／turn、診斷與結案各自保存可核對證據。
3. 同一合成事件經真正 receiver 喚醒真 agent，agent 按白名單完成按需診斷並回存結果；離線／重啟／重複事件仍冪等，正常心跳不開模型回合。全部通過才可稱真 E2E 完成。
4. 完成目標 Windows 主機之低負載原生 smoke、長時資源／休眠／崩潰恢復與失敗注入驗收；測試後明確停止自己程序。

每次更新保留 UTC、revision、命令／輸入類型、實際結果及未驗證範圍；禁止把設計值、舊測試數或 mock 狀態改寫成實測成功。新增真實主機證據只留經批准的本機忽略目錄，不寫入此文件或 Git 歷史。

## 2026-10-22：雲端接續與可執行 MSI 驗收入口

來源 `359a771539fe652b18a2a5469689c3d986b49611`；開始時 work 分支乾淨，fetch 確認 origin/main 相同，未倒退或覆寫既有提交。新增工作分支 `feat/local-codex-acceptance`。

實作：`scripts/acceptance_codex.py` 與 `src/eventguard/codex_acceptance.py` 協調一次官方 Codex exec，等真正 server wait 紀錄後由程式注入唯一 synthetic 事件，核對三個實際 MCP tool items、同 event/query 結果、SQLite ACK 及 child exit。run/status/stop 使用專用新目錄；不重試模型、不永久註冊、不改安全設定，合作停止不 kill。server single-wait 拒絕第二次等待。另修正 SDK 1.29 SessionMessage 包裝與取消 request ID 正規化；舊 SDK 路徑保留，本輪未重新取得 SDK 1.6。

測試命令與證據（皆為本輪，不沿抄交接 202/44）：

- Python 3.13.5，`python3.13 -B scripts/verify.py`，2026-10-22T05:13:15Z：210 tests，200 passed，0 failure/error，10 skipped（5 無可選 SDK、5 Windows-only），47 AST 通過，exit 0。忽略證據 `reports/cloud-python313-final.json`。
- Python 3.12.14 / 已安裝 MCP 1.29.0，`python -B scripts/verify.py`：210 tests，205 passed，0 failure/error，5 Windows-only skipped，47 AST 通過，exit 0；最終時間見本輪 `reports/verification-summary.json`。其中 5 項真正 stdio/SDK 測試包含 wait/query/ACK、取消無回覆、EOF 自然退出、單次等待逾時後拒絕再等。7 項 runner 測試含明示 fake CLI 的協調、ACK、停止及 pending-child-exit；fake CLI 絕非真模型證據。
- `python3.13 -B scripts/acceptance_smoke.py`，2026-10-22T05:08:27Z：passed=true，正常零事件、disabled 零 attempt、mock ACK、mock_closed、去重、跨程序單例與合作停止；remaining_test_processes=0。`reports/acceptance-smoke.json`；不是正式 agent／原生採集。
- `python3.13 -B scripts/eventguard_bridge.py --config config/bridge.example.json check`：有效但 enabled/network_enabled/listener_started/credentials_read 均 false。bridge 保持停用。
- `git -c core.whitespace=cr-at-eol diff --check` 通過；reports、runtime、帳戶內容不納入提交，舊 MVP 不動。

實際 Codex 嘗試：CLI 0.163.0 的 `login status` 顯示已登入，兩次單次驗收皆 CLI exit 1，錯誤 `failed to initialize in-process app-server client: Read-only file system (os error 30)`。第二次已按官方 schema 單次指定可寫 sqlite_home/log_dir，錯誤相同；沒有進入 wait、沒有 event ID、工具呼叫或 ACK。證據僅本機忽略的 `reports/codex-cloud-001`、`reports/codex-cloud-002`，沒有從原始 sessions 取證或複製憑證。真實模型接續、帳戶閒置請求數、真正 Codex timeout/cancel 行為仍 BLOCKED，不能用上述測試替代。

官方核對：Codex 0.163.0 tag 的 DEFAULT_TOOL_TIMEOUT 為 300 秒；新入口明確設 tool_timeout_sec=60、wait=30。完整來源、MSI 最短命令、退出碼與排障見 `docs/CODEX_ACCEPTANCE.md`。MSI Python3.13／SDK／登入／Windows 原生來源與長期低負載尚未驗收，沒有宣稱桌面任務可接續或永久等待。

交付：已將 `28170cb` 推送到 `origin/feat/local-codex-acceptance`，遠端 SHA 已核對。`gh pr create --base main --head feat/local-codex-acceptance` 被 GitHub GraphQL API 拒絕（Forbidden），所以 PR 尚未建立；不是 Git push 或測試失敗。可從 GitHub 的該分支建立 PR，不能把 compare/new-PR 連結稱為已存在的 PR。

## 2026-10-22：同事件重試、退出回條與本機整批驗證

本批接續 `b36cdba`，未重跑遠端 CI、未呼叫模型、未重新嘗試已知受阻的 Codex／GitHub API。完成一批後只建立一個本機提交；本輪不推送，保留遠端 CI 額度。

- 新增手動 `retry`：最多三次 attempt（含前置條件失敗），沿用同一 runtime、event/query/result ID。結果先落盤但 ACK 失敗可重試；已 ACK 事件拒絕再次啟動模型。原始 trace 與 attempt-summary 保留，僅核對當輪新增 wait。
- 新增獨立 capture worker 與有 fsync 的退出回條。runner 逾時或自然退出後 worker 繼續等待自己的 CLI 自然退出；無完整回條時拒絕重試，不靠 PID 猜測。stdout/stderr 各 4 MiB 上限，超量繼續排空但驗收失敗。
- runner、capture、stdio 加跨程序檔案鎖；第二個 stdio process 拒絕同 runtime。停止作用於當輪，舊 stop 不影響 retry。status 可用退出回條補完先前 pending 判定，不呼叫模型。
- metadata 逐檔拒絕 symlink/junction，拒絕 `..` 別名；有界讀取及原子 fsync 寫入。Windows shell 包裝預先拒絕，可指定既有原生 Codex 執行檔，不安裝依賴或更動執行政策。
- 驗收現在核對真實 MCP 回傳內容、wait 起迄、同事件/query、結果/ACK、完整 CLI turn；文字成功或損壞證據不能通過。

本輪實測（本機、合成／fixture，非真 agent／MSI）：

| 命令／runtime | UTC | 結果 | 忽略的證據 |
| --- | --- | --- | --- |
| `python -B scripts/verify.py`，3.12.14 / MCP 1.29.0 | 2026-10-22T05:50:12+00:00 | 227 discovered，222 passed，5 Windows-only skipped，0 failure/error，53 AST 通過 | reports/cloud-sdk-retry-final.json |
| `python3.13 -B scripts/verify.py`，3.13.5 | 2026-10-22T05:51:15+00:00 | 227 discovered，216 passed，11 skipped（6 SDK + 5 Windows-only），0 failure/error，53 AST 通過 | reports/cloud-python313-retry-final.json |

新增／擴充測試涵蓋同事件重試、result-before-ACK 失敗恢復、已 ACK 零重啟、舊 stop 不污染新 attempt、實際 runner 程序退出後回條仍保存、跨程序鎖、拒絕第二個 stdio、損壞 metadata／回傳／trace、輸出上限及路徑重導向。程序 fixture 均自然退出，不使用 kill/terminate。`git -c core.whitespace=cr-at-eol diff --check` 通過。先前真 Codex app-server 唯讀阻塞、真 timeout/cancel、帳戶閒置用量與 MSI 原生／長期監看仍未驗證；本批不提升產品完成度。操作與證據配置見 `docs/CODEX_ACCEPTANCE.md`。

## 2026-10-22T06:15:00+00:00：只驗證真事件通路，網路端點仍受阻

本輪來源 HEAD `e7b50b356a8021165a7f76d14e288927bbeb3bf0`；開始時工作區乾淨。沒有修改產品功能、執行 CI、推送或提交。

先以 file-syscall trace 確認舊錯誤：Codex 0.163.0 對唯讀 CODEX_HOME/installation_id 的 read-write/create open 回 EROFS；sqlite/log 覆寫不能修正。已用專用可寫 runtime 並以符號連結引用既有登入（未讀取或複製憑證內容），`login status` 可辨識帳戶，實際 CLI 成功建立 installation_id、越過先前初始化失敗，但尚無事件接收工具呼叫。

獨立無憑證 HTTPS 連線診斷：chatgpt.com 與 api.openai.com 的 CONNECT 都被既有網路代理以 403 拒絕（curl exit 56 / HTTP 000）。目前只開放 package_managers preset，沒有模型端點。已保存只新增 chatgpt.com 的網路設定草稿，保留原 preset；工具回報 saved、requires_publish=true。草稿不代表目前 runtime 已放行，需在環境設定檢閱、儲存並發布，再重測。沒有要求新憑證或繞過網路政策。

本次真 CLI 嘗試 `reports/channel-probe/run-002` 的 runner 已達 180 秒觀測上限，記為 pending_child_exit；capture worker PID 5895 與 Codex PID 5896 最後檢查仍存在，沒有退出回條，沒有送 process signal，不宣稱已停止。端點通路未建立前不再開新模型任務。不得把這次啟動或已登入當成 agent 已收到事件。

已準備忽略目錄 `reports/channel-probe/validate_delivery.py` 的有限驗收：continuous 2 件、batch 3 件、recovery 在真正 agent wait/query 後先正常退出、確認 pending 再由第二個真任務以同 event/query ACK。預設 prepare-only，真任務必須明確 --execute；比對實際工具回傳與生成／收到／ACK Counter。三種 prepare 命令已執行，均輸出 prepared_only_no_model_invoked；沒有執行 B/C 真模型驗收，也沒有宣稱無缺漏。網路開通後先處理現存 attempt 的退出狀態，再完成 A，才執行 B/C。

證據僅保存於忽略目錄：channel-status.json、file-access.trace、run-001、run-002 及各案例 manifest。A 單事件目前 BLOCKED；B 連續／批次與 C 失敗補收 NOT RUN。MSI、本機長期監看與帳戶閒置用量均不因本輪診斷而提升為通過。

## 2026-10-22T06:23:23+00:00：MSI 從 GitHub 取得有限通路驗收

依使用者最新指示，取消下載包，將驗收入口與操作文件集中推送到 `feat/local-codex-acceptance`。本輪只補通路驗收，不新增監看來源、GUI、原生診斷或雲端服務；不手動觸發 CI，提交使用 [skip ci]。GitHub 的 main 尚不是這批來源，MSI 應取得指定分支。

新增 `scripts/validate_delivery.py`：continuous=2 件（前一 ACK 後才入列下一件）、batch=3 件原子入列、recovery=第一個真任務只 wait/query 正常退出，確認 pending 後第二個真任務補收同 event/query 並 ACK。預設 prepare-only，需明確 --execute 才用既有帳戶執行模型；提示不帶事件 ID／內容，不自動重試模型，保存實際工具回傳與 ID Counter 核對。支援 --codex-executable 指定 MSI 既有原生 CLI。操作見 `docs/MSI_CHANNEL_CHECK.md`，先 A 真通過才跑 B/C；使用 MSI 正常登入，禁止帶入雲端 CODEX_HOME／auth／runtime。

本機驗證：`python -B scripts/verify.py`，231 discovered，226 passed，5 Windows-only skipped，0 failure/error，55 AST 通過，exit 0。另以 Python3.13 跑新增4項入口測試，全部通過。這是程式／fixture 檢查，不是 MSI 或真正模型送達證據。reports、憑證、runtime、ZIP 與真 CLI log 都不納入 Git。

雲端重測 ChatGPT CONNECT 仍403；無可用工具可讀取發布失敗詳情，不能推定其原因。已保存的 chatgpt.com 網路草稿不等於目前 runtime 放行。既有 run-002 最後狀態仍 pending_child_exit，未取得退出回條，沒有強制終止或另開重複模型任務。A/B/C 真通路未驗證，等待 MSI 實跑結果，不提升產品完成度。

## 2026-10-22 06:58 UTC／14:58 台北：MSI 有限真通路 A／B1／B2／C 通過

本輪來源核對：工作目錄為本專案，初始 `publication`／`359a771539fe652b18a2a5469689c3d986b49611`，無未提交變更。正常 fetch 後取得並切換 `feat/local-codex-acceptance`，HEAD 與使用者指定 `4ffc86c1b931a8706d26723c676e974dba4fbc1d` 完全相同，沒有更新須保留合併；未 reset、clean、強制覆寫或動舊 MVP。保留原本地分支與私人歷史。

前置檢查：Python 3.13.3 可匯入既有 MCP SDK 1.6.0；PATH 的 codex 為 npm 包裝，另找到既有 npm 原生 0.158.0 與桌面安裝原生 0.163.0-alpha.11.1。本輪選後者為 `$codexExe`。明確以程序環境 `$env:CODEX_HOME = Join-Path $env:USERPROFILE '.codex'` 指向正常本機 home 後，`& $codexExe login status` 回 Logged in using ChatGPT。沒有建立登入、讀取／複製憑證內容、帶入雲端 home 或安裝任何依賴。

先前 sandbox 對 `.git/FETCH_HEAD` 的寫入遭拒，自動核准審查亦依 AGENTS 的不得提權規則拒絕 Git sandbox 例外；使用者之後明確批准限定 Git 例外，再批准本輪有限驗收程式的 sandbox 例外。均使用同一一般使用者，無 UAC／管理員權限或安全設定變更；內層 Codex 保持 read-only、shell 關閉。這些批准僅屬本輪，不是持續存取授權。

A 三次 attempt 全部保留於同一 run，沒有另建目錄繞過 retry 上限：

| attempt／UTC | 結果 | 事件與工具證據 | 自然退出 |
| --- | --- | --- | --- |
| 1，06:39:54–06:40:39 | 初始化 `in-process app-server` Access denied／os5，runner exit 1 | 未進 wait、未生成事件、無 query／ACK | CLI exit 1、child_exited=true、完整回條 |
| 2，06:45:32–06:46:36 | 真 agent 嘗試 wait，被 `MCP tool call requires approval, but approval policy is never` 拒絕；runner exit 1 | 真 CLI turn 已完成，但沒有實際工具返回／事件／ACK，summary 正確拒絕成功 | CLI exit 0、child_exited=true、完整回條 |
| 3，06:49:27–06:50:26 | 修正逐工具單次批准後真正 passed，runner exit 0 | 一次 wait→程式產生事件→query→ACK；實際 wait 3.190 秒、相同 event/query/result 與 SQLite receipt | CLI exit 0、child_exited=true、完整回條 |

第一個錯誤與 Codex 需要可寫開啟正常 home 的 `installation_id` 相符；只覆寫 sqlite_home/log_dir 不能解決。CLI 自身啟動亦產生歷史索引 metadata 警告，操作者未開啟既有 session 檔；包含私人路徑的本次 stderr／Codex state 僅留忽略 reports，不能上傳。未以修改權限、複製憑證或新登入繞過。

必要實作修正：`command()` 以同一工具清單產生 `enabled_tools` 與逐工具 `approval_mode="approve"`，僅對本次已授權公開合成工具有效；不改總批准政策或永久設定，不加 bypass。以 `single_wait`／`allow_ack` 參數取代 B/C 的字串替換，C 第一階段的設定完全沒有 ACK 白名單或批准表。測試直接解析 TOML 確認批准範圍及 read-only／shell 關閉均保留。官方語義見 [MCP 文件](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) 及[本機版本實作](https://github.com/openai/codex/blob/680c4ba93ec79c292287fb9e0b627dc7a76e3b5e/codex-rs/core/src/mcp_tool_call.rs#L2467-L2479)。

依序執行的真驗收命令（A 後續兩次使用同參數的 `retry`，沒有自動模型重試）：

```powershell
python -B scripts/acceptance_codex.py run --run-dir reports/msi-single-001 --codex-executable $codexExe
python -B scripts/acceptance_codex.py retry --run-dir reports/msi-single-001 --codex-executable $codexExe
python -B scripts/validate_delivery.py continuous --root reports/msi-continuous-001 --codex-executable $codexExe --execute
python -B scripts/validate_delivery.py batch --root reports/msi-batch-001 --codex-executable $codexExe --execute
python -B scripts/validate_delivery.py recovery --root reports/msi-recovery-001 --codex-executable $codexExe --execute
```

| 案例／驗證完成 UTC | 生成唯一事件 | 真接收／query／ACK | 結果與證據根目錄 |
| --- | --- | --- | --- |
| A，06:50:26 | 1 | 1／1／1 | summary.passed=true；reports/msi-single-001，成功 trace 在 attempts/0003 |
| B1，06:52:16 | 2 | 2／2／2 | validation.passed=true、missing=[]；reports/msi-continuous-001 |
| B2，06:54:35 | 3 | 3／3／3 | validation.passed=true、missing=[]；reports/msi-batch-001 |
| C，06:57:02 | 1 | 2／2／1 | validation.passed=true、missing=[]、recovered_same_event_and_query=true；reports/msi-recovery-001 |

C 第一階段只執行 wait/query，CLI 正常退出；`read-before-ack/pending-proof.json` 於 06:56:05.435Z 記錄 pending、result_present=false，才啟動第二階段。第二次工具回傳相同 event ID／query ID，結果於 06:56:56.885Z 保存再 ACK；SQLite 僅一筆結案 receipt。

集合核對：合計 7 個不同程式生成事件、8 次實際接收／query（C 預期重收一次）、7 次 ACK、7 筆 SQLite ACK／receipt；missing、unexpected、unexpected_duplicates 均為空。逐事件 ID、query ID、接收時間、結果時間、source SHA-256、真 trace 路徑與退出回條核對在 `reports/msi-channel-001/delivery-audit.json`；`python -B reports/msi-channel-001/audit_delivery.py` 於 06:58:05Z exit 0。另有唯讀獨立審查直接解析真 JSONL 與 SQLite mode=ro，未只採信 summary。五個成功真 Codex 任務均 exit 0、完整且未截斷回條，四個 runtime 的 stdio-owner.lock 均已釋放。另保留上述兩個失敗 attempt，所以本輪共七次驗收用 `codex exec` 啟動；未 kill／terminate、未留本輪未知退出狀態。

必要本機測試與限制：

- `python -B -m unittest discover -s tests -p test_local_stdio.py -v`：6 tests 全通過，13.085 秒；僅 SDK／合成協定，不作真 agent 證明。
- `test_delivery_validation.py`：4 tests 全通過，0.417 秒；`test_codex_acceptance.py`：10 discovered、9 passed、1 symlink 權限 skip，13.279 秒。皆以 `python -B -m unittest discover -s tests -p <檔名> -v` 執行，fake CLI 測試明示非真模型。
- 全套以 `python -B -` stdin harness 執行 `unittest.defaultTestLoader.discover('tests')` 與 `ast.parse`，獨立輸出目錄避免覆寫既有 reports 基準。06:53:15Z：231 discovered、229 passed、0 failure/error、2 symlink 權限 skip，55 Python AST 通過，53.809 秒，exit 0。證據 `reports/msi-channel-001/unit-tests.txt`、`unit-summary.json`。未為略過項提權；無模型、網路服務或實機掃描。

以上只完成本階段的有限公開合成事件工具接收、耐久保存及補收 ACK 驗收，不是任意既有桌面對話接續、Windows 原生採集、長期 dispatcher／監看服務、永久等待、帳戶零閒置用量或完整主機安全的驗證。正常監看仍不呼叫模型；既有 bridge 保持停用。所有 manifest、JSONL、工具回傳、SQLite、runtime 與本輪診斷保留本機忽略 reports，不納入 Git。

## 2026-10-22 08:13 UTC／16:13 台北：前景事件入口與有界實機接收通過

本批接續 `f093c2df531c7bbfc732e134cf718f00ebbfd22f`，仍在 `feat/local-codex-acceptance`。初始無未提交變更；集中提交前 fetch 再核對遠端與 HEAD 相同，沒有 reset、clean 或覆寫。使用者要求把事件接上，另明確批准一輪前景試運轉：最多一小時／五個 agent 任務，只送最小摘要。實際採更小的 300 秒／最多兩個實機任務；加上一次公開合成通路，共三個真 CLI 任務，沒有自動重試模型。先前 A／B／C 的結果保留，未重跑或重複計數。

實作可直接使用的 `scripts/eventguard_watch.py`（run/status/stop），整合既有 Monitor 與 `agent_dispatch.py`，不擴充來源、GUI 或原生診斷。Monitor 新增時限與共享合作停止；首輪保存後才交給 dispatcher。純 Python 等待原 live outbox，有 due/pending 事件才啟動專用 CLI；未執行時只是 preflight。停止／截止在實際 native Popen 前再次核對，根本未啟動者另記 capture-skipped；已開始 CLI／查詢自然退出，沒有 kill／terminate。

`queue_inbox.py` 只投影固定七欄 snapshot：event ID／類型／轉態／severity／synthetic／觀測時間／coverage status，不回程序或產品名稱、路徑、PID、事件全文、任意 evidence／reason／gaps。三工具 receive/query/ACK 只綁定一件事件，prompt 不帶 ID／內容；query 僅查同一保存摘要，結果為 `reviewed_metadata`、`incident_conclusion=not_assessed`。MCP 設定與逐工具批准只屬單次 CLI，保留 read-only／shell 關閉，使用正常本機 home 與既有登入，未永久註冊、建立登入、讀取或複製憑證。

耐久 snapshot/query/result ID 與原 outbox ACK 互相核對，結果先保存再 ACK；同 ID 重收沿用同 query/result，已 ACK 不重複結案。來源全域鎖與固定 state 綁定阻止平行 receiver 或換目錄繞過未知退出；每事件最多三次明確嘗試、失敗不自動重開模型。容量／保存失敗明確 blocked，不清除 pending。詳見 [LIVE_CHANNEL](LIVE_CHANNEL.md) 的容量、啟動與恢復限制。

本輪使用既有 Python 3.13.3／MCP 1.6.0／原生 Codex 0.163.0-alpha.11.1，程序環境明確指向正常 home，`$codexExe` 為既有原生執行檔。真執行命令：

```powershell
python -B scripts/eventguard_agent.py run --run-dir reports/msi-queue-synthetic-001/dispatch --source-dir reports/msi-queue-synthetic-001/source --state-dir reports/msi-queue-synthetic-001/inbox --codex-executable $codexExe --max-seconds 180 --max-tasks 1 --execute
python -B scripts/eventguard_watch.py run --run-dir reports/msi-live-001 --codex-executable $codexExe --max-seconds 300 --max-tasks 2 --execute --allow-live
```

第一條為程式生成的一件公開合成事件，source/inbox 均隔離；真工具 receive→query→ACK、三 ID 及 SQLite receipt 匹配，任務上限正常退出，runner／CLI exit 0。合成 source 刻意放入不應傳出的名稱／路徑／指令誘餌，實際工具返回沒有洩出，snapshot 僅七欄。證據 `reports/msi-queue-synthetic-001`，07:51:56–07:53:29 UTC。

第二條為本輪已授權的實機前景試運轉，08:07:15 UTC 開始監看，兩輪後於 08:10:23 UTC 合作停止。達任務上限後 watch=completed、monitor_exited=true、agent=task_limit_reached、child_exited=true，runner／各 CLI exit 0，完整未截斷退出回條及所有本輪 owner 鎖釋放。獨立審查以 SQLite mode=ro 的最小欄位與實際 JSONL 確認事件在本輪觀測／保存，非舊 backlog；收到/query/結果/ACK/receipt ID 集合匹配，交給 agent 的集合無缺漏、額外或非預期重複。任務上限外事件仍耐久 pending，沒有假稱全部佇列已交付；完整實機數量及 ID 只留本機忽略 audit，不納入 Git。部分來源仍 partial，沒有把 ACK 解讀為安全或完整 coverage。

獨立核對命令 `python -B reports/live-channel-evidence-001/audit_live_delivery.py`，08:12:31 UTC exit 0、passed=true，保存 `delivery-audit.json`。審查直接解析三個真 CLI 的工具返回及 receipt，未以 agent 文字或 summary 取代；另核對 watch／Monitor／source dispatcher／stdio inbox／capture 鎖已釋放。沒有讀取原始 native evidence、Codex sessions 或將 stderr／runtime 上傳。

必要測試與問題保留：

- 全套以 `python -B reports/live-channel-evidence-001/verify_source.py` 執行，08:03:39 UTC：269 discovered、267 passed、0 failure/error、2 symlink 建立權限 skip，64 Python AST 通過，84.916 秒，exit 0；逐檔雜湊確認跑測試期間 source 未變動。`final-unit-tests.txt`／`final-unit-summary.json` 留忽略目錄。此 suite 是 fixture／fake CLI／SDK 檢查，模型呼叫與實機掃描均為零，與上述真任務分開。
- 首輪 suite 的 1 failure／1 error 留在 `unit-tests.txt`／`unit-summary.json`：分別為停止閘道改動後的競時 fixture 與 Windows 狀態檔共享衝突。已修正 fixture、在 JSON 原子 replace 加僅限指定 Windows 錯誤的有界重試（最多 190 ms）；持續拒絕仍失敗並保留舊值，未更改權限。
- 較早的一次合成 EOF 測試在關閉 stdin 後，SDK 預設工作群未退出，父測試 exit 1，留一個已核對的 Python 測試程序。修正 stdio 工作群的 EOF 合作取消後，新 EOF 測試自然 exit 0，inbox 18 項測試通過；但舊程序仍存在，且沒有強停批准，未 kill／terminate，不能宣稱所有測試程序皆已退出。身分／啟動時間與檢查證據只留 `reports/live-channel-evidence-001/known-test-orphan.json`。該程序不是本輪實機監看或模型任務，沒有採集系統資料。

本輪前景試跑已結束，目前沒有持續監看；再次執行需當次有效範圍。已接通的是本機事件到專用短期 CLI agent，沒有證明任意桌面對話自動接續、完整 Windows coverage、原生診斷／處置、長期低負載、休眠／崩潰恢復或永久等待。舊 MVP、私人歷史、憑證與 runtime 未推送；集中提交只含審查後 source／tests／操作文件，指定 feature 分支，[skip ci]，不手動觸發 CI。

## 2026-10-22：MIT 與最新驗收摘要發布

使用者明確指定 MIT 並要求公開 `SecludedCorner/EventGuard`。本批以 `cc6e799` 為程式來源，新增 LICENSE、README 驗收結果表，同步 HANDOFF 與 PUBLISHING；沒有修改 Python、模型設定或監看來源，沒有啟動模型／實機採集或重跑原 suite。README 保留 A／B／C 的 7 唯一事件／8 接收與 query／7 ACK、新入口有限真通路及 269 項測試結果，並明列目前一小時／五任務限制及未完成的長期能力。

後續公開合成投遞探針已追加到使用者指定的專用合成佇列，本次只讀核對仍 pending、0 ACK；未證明 dot 收到或回應，不列為成功通路。該探針的 manifest、入列回條與資料庫留在本機忽略 reports；未發布事件 ID、使用者路徑或完整執行資料。

發布前只讀審查涵蓋遠端 main 與 feature 的全部可達內容：9 commits、143 個 unique blobs，均來自與私人舊歷史分離的 publication root；`fd45578` 不在遠端可達祖先中。未發現執行目錄、原始會話、憑證、資料庫或封存檔被追蹤；三處路徑命中均為明示匿名 synthetic 隱私測試 fixture。GitHub 端未有 Actions run／artifact、issue、PR 或 release／附件。本機原始資料與未推送分支保留，不使用 --all／--mirror／force。

本批驗證為既有證據核對、MIT 標準文字比對、Markdown 本地連結與 git diff --check；不把這些文件檢查當成新模型或長時間驗收。Git 作者 metadata 的公開範圍另依 PUBLISHING 檢查，不因原始碼掃描通過而忽略。透過指定 feature 與 PR 更新 main，公開可見性與 MIT 辨識結果以 GitHub API 發布後回讀為準。

## 2026-10-22 18:35 台北：Phase 1 原生採集與拒讀證據

來源基準 `dbac91b`，分支 `feat/local-codex-acceptance`；使用者明確確認 Phase 1、一般權限唯讀實作及逐來源驗證。本節對應的 Phase 1 提交以 Git 記錄及本機 `reports/phase1-collectors-001/source-commit.json` 核對；驗證另存精確 source hashes。不 fetch／push、不啟動真 Codex／模型、不提權／UAC、不下載安裝、不改系統政策、不做 Phase 7 狀態注入。

本批實作：標準庫 ctypes／winreg 的七來源 native backend、同一封裝契約的 PowerShell fallback、stage／exception_type／HRESULT／Win32／provider_code／category 原因碼；錯誤與 coverage 經 monitor 保存後可由 status／DiagnosticAPI 讀取。原生有 partial／denied／unknown 等結果時不自動重試另一途徑。Defender 設定與 Security Center 彙總不升格成即時防護狀態；tasks 只讀 COM Name／Path／State。契約與七來源範圍見 [COLLECTOR_CONTRACT](COLLECTOR_CONTRACT.md)。

實際命令（全在本機忽略 reports；probe 腳本及原始資料不提交）：

```powershell
python -B reports/phase1-collectors-001/monitor_probe.py
python -B reports/phase1-collectors-001/probe.py --backend powershell --label powershell-final
python -B reports/phase1-collectors-001/verify.py
```

第一條在隔離 runtime 做一輪真實七來源，18:33 台北完成：listeners／startup／services／versions 為 ok；processes partial（OpenProcess 有 Win32 5 等逐物件缺口）；Defender partial（設定／彙總可讀，七個有效防護欄位仍 unknown）；tasks unknown，object 階段 COM HRESULT 0x80070003／object_unavailable，OS 原文「系統找不到指定的路徑。」。另一次 `schtasks /query /fo csv /nh` 同樣找不到路徑、exit 1；不把該結果改寫成沒有排程或已證明權限拒絕。

第二條同上下文逐來源一次對照：五個 provider 明確 CimException、provider_code=AccessDenied／category=PermissionDenied／HRESULT 0x80131500；startup／versions 為 ok。七個 PowerShell 子程序均實際啟動並自然 exit 0，CLI 正常退出不等於來源成功。新 native 主路徑因此取得多個原先 CIM 拒讀來源的 metadata；不推定桌面 shell 與本工具 token 等價。匿名 token metadata 為非 elevated／has_restrictions／非 AppContainer，沒有讀帳號或私人 SID。

實機證據：`monitor-final/source-*.json`、`monitor-result.json`、實際 CLI 回傳 `status.json`、`exit-receipt.json`；`powershell-final/*/command.json`、`raw-evidence.jsonl`（真 stdout／stderr）、`process-exit.json`、`manifest.json`；`schtasks-evaluation` 保留比較的 argv／原始輸出與退出。全部在 `reports/phase1-collectors-001`。原始 OS 訊息標記為 FormatMessage 來源，不冒充 provider Exception.Message。隔離 monitor stopped、monitoring=false、runner_pending=false、singleton 可重新取得；probe／monitor／全套測試各程序 exit 0。沒有新常駐監看／模型程序；不宣稱已清理歷史已知 orphan。

測試數單一來源為 `full-summary.json`：Python 3.13.3，全套 287 discovered、285 passed、0 failure/error、2 symlink 建立權限 skip；69 個 Python AST 無錯，86.771 秒，source hashes 全程不變。範圍為 fixture／SDK stdio／fake CLI，與上述真實 Windows 採集分開；沒有真模型。相關 collector／core／rules 的 84 項亦全通過，見 `targeted-final-summary.json`。

本輪修正中保留的失敗：初輪 tasks 的 OS 訊息格式化將有號 HRESULT 轉成超出 C long 的數值，遮住原錯誤；修正後取得真 0x80070003，再加入回歸測試。native 版本初輪拿到 Windows build tuple，已改讀與 fallback 相同的 ProductVersion；PID 時刻亦統一 UTC 微秒。大型 coverage 測試發現原 health 64 KiB 寫入限制不容新安全證據，現 health 讀寫同為 2 MiB；config 等其他限制不變。status 的 SQLite 唯讀連線未明確 close 所造成的測試分享衝突已修正。初輪 source／目標測試失敗證據均保留，不算通過。

尚未做到：tasks 的成功讀取、Defender 七個有效狀態、所有程序欄位可讀；H1–H5 的可支持／未排除範圍見契約。原生／COM 單一 OS 呼叫永不返回的硬性停止、Job Object、monitor_gap、長期容量／soak、背景自啟及 agent 診斷均仍屬後續 phase；本批不證明全天候或整機安全。AUDIT 不覆寫，時間歷史與 README 全面收斂留 Phase 6。

## 2026-10-22 21:53 台北：Phase 2 角色比較，等待選案

使用者說「繼續」後恢復目標，先核對工作目錄、分支 `feat/local-codex-acceptance`、HEAD `088be7561c5ead1bb4e289ad3b4ef6ce03748398` 及乾淨工作樹；保留已完成 Phase 1，不重跑七來源或模型。此批只新增 [AGENT_ROLE_DECISION](AGENT_ROLE_DECISION.md) 與交接紀錄，未修改程式、測試、設定或 playbook，兩候選執行路徑皆未實作。

實際命令 `python -B reports/phase2-role-001/compare.py`，Python 3.13.3，exit 0；程式建立一件專用 synthetic listener 事件，直接呼叫既有 playbook、QueueInbox 與 fixture DiagnosticAPI。receive/query 的七欄 snapshot 相同，query 新增觀察 0；ACK 及重播的 result ID 相同、SQLite receipt 一筆、incident_conclusion=not_assessed、real_agent_wake_verified=false。兩次相同型別化 fixture 查詢的觀察相同，不需要模型取得；不是已完成 B 或真 agent 測量。程序名的指令式文字仍可出現在 DiagnosticAPI 輸出，控制字元會去除；B 不能直接暴露這份結果。

測試數以 `reports/phase2-role-001/summary.json` 為準：相關既有 fixture 18 項通過、0 failure/error/skip，0.9717 秒；另有 18 個探針斷言，不和測試數相加。未重跑全套。原始碼 hashes 前後一致；該探針 model_calls=0、real_codex_tasks=0、native_provider_queries=0、external_attempts=[]。單次元件計時不是完整 A/B 效能評比；模型品質／延遲／token／金額均未測。原始回傳、synthetic event、SQLite 回條與 tests.txt 全留忽略 reports，不提交。

建議 A：確定性 playbook＋本機報告，agent 降為可選；B 的事件綁定、字串 projection 與可量增益要求已寫入比較報告。依原請求等待使用者選 A／B 後才實作；選 B 亦不自動批准真模型。Phase 1 的 tasks／Defender／程序 coverage 限制仍在；Job Object、容量、長期驗證及實機注入尚未進行。本批不啟動背景監看、不建立排程、不提權、不下載安裝、不操作網路、不推送。

## 2026-10-22 22:32 台北：獨立核心與人類／agent 共用操作

使用者已明確改定方向：「不論有沒有 agent 都要能獨立運作，人類要能操控並知道發生了甚麼；也提供 agent 介面，使用同一套操作與可見資訊」。先前 A／B 等待關卡已解除。來源基準 `a130dcef3648330adadfef99875873db0888f22e`、原 feature 分支，原有未提交變更為空；沒有模型／真 Codex、提權、下載安裝、系統政策變更、網路、永久 MCP 註冊、排程、自啟或實機狀態注入。

實作共用 OperatorAPI，CLI 與同一 stdio 入口的 operator mode 共用能力、狀態、事件清單／檢視、事件綁定唯讀查證、報告及合作停止；MCP 另提供固定一輪 monitor_once，長期前景仍用 CLI。核心不依賴 SDK／模型，舊三工具接收／摘要 query／ACK 與驗收契約保留。原有 status／report 邏輯移入共用層，read-only 視圖不初始化或修改 SQLite。新事件表顯示固定說明、具體觀測、coverage 與最近診斷。

查證只從耐久事件綁定 protocol／port、process_instance_ref 或 persistence kind，不接受 agent 的自由查詢參數；缺程序實例留 process_binding_missing。產出 observations、coverage、uncertainties 與固定 incident_conclusion=not_assessed，另保存到同一 SQLite 的最新 event_reviews，不修改 pending／ACK／receipt。資料最小化、字串與快取 schema 驗證、固定錯誤 envelope、容量／ACK reserve 回滾及 ACK 事件輪替清理均有對應測試；介面契約見 [HUMAN_AGENT_INTERFACE](HUMAN_AGENT_INTERFACE.md)。

精確測試數單一來源為本機 `reports/phase2-operator-001/verified/summary.json`：Python 3.13.3，命令 `python -B reports/phase2-operator-001/verify.py --label verified`，304 discovered、302 passed、0 failure/error、2 symlink 建立權限 skip；72 Python AST，來源 hashes 前後不變，92.134 秒，exit 0。含 17 項新操作介面測試與既有 suite，範圍 fixture／已安裝 SDK stdio／fake CLI；沒有真 agent 或本輪 Windows provider 驗收，不與歷史實機／模型數字累加。

`verified/operator-stdio-trace.json` 保留真 Python 子程序的八個 tools/call request／實際 SDK response、child PID、exit 0、reader thread 已退出及該程序 remaining_owned_children=0；不是 Codex agent 接收證據。舊通路測試仍通過。另命令 `python -B reports/phase2-operator-001/demo.py --final` 在隔離 runtime，實際執行人類 CLI main 的 fixture 監看、產生三件 synthetic、list／inspect、阻止 synthetic 原生 query、fixture 注入診斷與 JSON／HTML 報告。`demo-final/manifest.json` 保存命令 argv、真 stdout、同事件關聯、診斷與 source hashes；三件仍 pending、0 receipt，核心未 import MCP，monitor stopped，exit 0。所有原始資料留忽略 reports，不提交。

保留的失敗與修正：第一輪全套發現預先建立診斷表占用小型 outbox 空間，使既有滿載／ACK 輪替測試失敗；改為明確 diagnose 時才在同交易建表，失敗連 DDL 一併回滾。可讀性測試另發現原 schema 會丟棄既有 synthetic Defender 的 property，現在保留此 metadata key、共用 view 僅接受固定防護欄位枚舉。初輪／release 失敗證據及中間 final 成功快照均保留，當前版本只以 verified 為準；沒有放寬原容量或移除既有測試。

尚未驗證：新 agent 介面的真模型操作／效益、重開機後的 Windows coverage、任意 OS hang 的硬性退出、長期控制／自啟、monitor_gap 與 soak。Phase 1 tasks／Defender／程序可讀性缺口未改寫為成功；診斷與 ACK 仍不代表主機安全。Phase 3–7 尚未實作，本輪不宣稱全天候或已將工具載入任意桌面聊天。具體提交由 Git 與本機 source-commit.json 綁定，不推送。
