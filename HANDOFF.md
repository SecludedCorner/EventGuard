# EventGuard 接手

本批基底3e36925，實際核對正式MCP Start/Stop：舊server走獨立background契約，回blocked/independent_background_unverifiable，沒有建立子程序；已Stop恢復disabled/explicit_stop、退出核實且沒有新採集或事件變動。修正讓新載入operator adapter持有application host，沿用GUI的核心Job路徑，但不建DesktopController、不恢復auto agent。只保存本API新建立的child與可信launch scope；EOF fences Start並用namespace/run/generation/job guard停止，換代不改新控制，最後只finish自己持有Job。固定有界operator-stop-receipt保存退出與forced證據，寫失敗不宣稱clean。CLI預設仍independent。測試／來源及提交綁定見EVIDENCE的operator-start-001批次。

修改後本主聊天一次真capabilities仍缺start_lifetime_owner，確定未載入本批契約；不要再重試Start。先完成本批驗證與提交，再由client正常重新載入EventGuard MCP，核對capabilities.background.start_lifetime_owner=application才做一次有限Start/Status/Stop。沒有可呼叫reload工具，不修改其他MCP、不強停server、不重試proxy或註冊排程。新SDK的fixture Job成功也不能升格成此聊天已更新。正式暫停保持；舊七來源／真事件／七件合成證據不重做。

最新程式645d8d9、本批只有文件與主聊天真合成接收。已沿用四工具MCP驗7件程式事件：單件、連續兩件、batch三件＋另一補收件；先讓active inbox滿3，第四件明確拒絕且pending/hash不變，ACK一件後補收成功。補收同event/query/received_at/snapshot，七張新回條與一次ACK重播；八組ID集合全同，missing/extra/duplicate_receipts空。原config及inbox-limits bytes/hash已恢復、四筆歷史五欄保留；只讀獨立validation及原生32calls在reports/chat-delivery-003。兩個helper失敗保留，沒有重做原生投遞。不是新CLI任務、跨任務退出或閒置喚醒，沒解除正式Pause。source仍吻合前批完整suite manifest，不重跑；最後commit綁定及未完成條件見EVIDENCE與goal-completion-audit.json。

最新續行基底5bff808：三個子agent完成實作，root整合後統一回歸。Monitor到期來源依實際嘗試時間公平排序，避免反覆慢查詢讓其餘來源永久busy；間隔從各自實際開始計算。QueueInbox ACK交易同時保護原receipt直到completed耐久成功，TTL/count/byte不可刪未收尾proof；pin有容量上限、滿載回滾pending，舊DB可遷移，原proof已遺失仍blocked。overview合併相同錯誤樣本，sample_occurrences不當成總錯誤數；原status/observation不變。唯讀status另顯示pending_receiver_finalizations，新欄不存在回null，不因讀狀態遷移。

本批沒有新實機盤點、主聊天新接收或背景啟用；正式背景仍explicit_stop。source與資料保留不動；舊GUI/MCP需正常重新載入新版，不能宣稱已熱更新。重現、統測及提交綁定見EVIDENCE的runtime-reliability批次；前批七來源／一件真事件證據仍獨立保存，不重做或升格。

最新人類指示已收斂：把本機資安監測、資料保存、agent可分析／必要時收event做好，不把proxy、排程或idle-chat wake當開發前提。使用者允許必要程式權限，但沒有批准登入任務，勿再詢問或自行註冊。既有GUI的Start/Pause與共享MCP即可使用，正常採集無模型。

本輪基底11d2dd76：已用主聊天正式工具monitor_once完成真實七來源，inspect/diagnose/receive/ACK一件本輪新生真事件；ACK為needs_more_evidence，仍not_assessed，完整SQLite/工具對照在reports/security-core-001。另真PS Defender七欄可讀，auto已來源特定改採有效provider；native-only仍是配置/WSC範圍。修listener身分gap誤resolved、persistence歷史entries與ref-filter、cache target binding；詳情和統一測試看EVIDENCE。已運行舊GUI/MCP不假稱熱更新；新載入使用當版程式。

proxy批准後helper用不存在的Job reason導致exit1，沒有保存連線及child回條；只保留失敗、不再重試。新指示取代下方舊「等metadata／排程批准才繼續」；舊排程digest因這輪source改動失效。既有research/attachments與私人runtime不提交。

## 前批接手紀錄（非目前待辦；以本頁開頭及 STATUS 為準）

最新續行基底af839b36。本輪沒有產品碼變動；取得既有Codex CLI0.163.0-alpha.11.2的queue/proxy help，以及當版登入恢復真dry-run。一般使用者任務absent（已確認folder後GetTask80070002）；sandbox GetFolder80070003屬不同身分unknown，兩者分開。新plan只register、不Run，現有explicit_stop不變。方案SHA與批准內容見docs/WAKE_RECOVERY_GATES.md，不重查或重建相同方案。

唯讀control socket探測已備妥在reports/wake-queue-research-001/proxy_probe.py，只initialize＋精確目前thread/read(includeTurns=false)，不送queue/turn、不開server。**自動核准審查拒絕**：metadata亦被認定私人Codex session存取且缺精確授權，helper沒有執行、proxy沒有啟動；不可改用另一方法繞過。先等這項明確批准，再探測一次；即使成功仍不是idle wake，模型傳送另有批准關卡。真排程註冊也仍需本次SHA批准。目標維持active，不能宣稱已完成或自行解除Pause。

最新使用者把產品定位為資安情報中心，要求所有操作經EventGuard且在GUI看得到。共享operator adapter現有15工具（含activity），開始／停止仍走原核心；GUI與operator MCP操作記於data/activity.sqlite3，最多256筆，保持running，故障不阻止Stop。只記固定動作/結果碼與目標hash，不記提示、事件全文、完整命令列；不涵蓋聊天思考、任意外部檔案編輯或舊綁定CLIadapter的每一步。

使用者要求「建立目標，繼續完成」，已建立active持續目標，未設token預算。來源基底bf99496cf3d73601fc2d8a1bf50c1c2fe8709b66，同一feature。正式MCP已批准，不再詢問；目前本主聊天已有15工具，已實際呼叫capabilities／status／activity，activity可讀到操作。當次status顯示background stopped／desired_enabled=false，既有pending保留；current monitor無owner、舊heartbeat過期。本批沒有開始採集、啟用模型或ACK正式資料。

本輪找到並修正具體接線缺陷：同一operator root終身鎖會令第二client在initialize前exit3；不刪鎖、不動既有owner，改短期mutation lease。讀取與Stop可通過，scoped Stop在控制鎖內核對namespace並綁原instance/run/Job，換代回busy，缺ID不退回global。legacy bound owner仍exclusive。主聊天另完成一件新隔離合成事件補收同event/query與冪等ACK，SQLite只新增一張回條。雙stdio client及相關回歸證據留reports/goal-center-001，精確數字看EVIDENCE。

閒置同一聊天的事件觸發仍未接通。不能以手動收取、SDK、新對話、另一個CLI或定時模型輪詢代替；須client提供可用事件觸發入口及明確模型授權再驗收。重開機登入排程未批准，舊plan digest因程式改動失效；不自行建立／Run。下一步依docs/MAINTENANCE_GOAL.md，不重做已成功通路或再次索取CLI日額。

GitHub後續採納：runner超4MiB合計輸出提早走合作寬限與owned Job cleanup，reason=output_limit；JSON最多32層且拒絕解碼後重複key。25引擎研究不代表執行掃描器。使用者要求的上游回饋已由子agent整理、root核實並發送：公開issue #88附三份公開MD；另一項依上游SECURITY政策走私人報告。回讀證據只留reports/upstream-feedback-001，不公開私人細節，不自動追蹤或另發訊息。

當前維護方向見docs/MAINTENANCE_GOAL.md，接線步驟見docs/CONNECT_AGENT.md。下面保留較早交接歷史；其中待批准、待初始化CLI預算等敘述不取代上方最新範圍，不能據此啟動另一個模型或重問已批准的正式MCP。

## 歷史交接（以本頁開頭及STATUS為準）

最新範圍澄清：使用者表示「你一個就好了」，目標是目前這個對話收到事件；不要再把另開專用CLI當成達成同一目標，也不要重問每日CLI數量。2026-10-23 13:52台北時間，本主對話再次以原生MCP收到程式新生成的合成事件並ACK，證據在reports/chat-receive-002；這仍是活動回合主動收取。閒置同一對話的事件觸發入口尚未接通，不能以MCP註冊、手動接收或另一個CLI代替。保留既有可選CLI實作，但未啟用、不初始化其budget；不要用模型定時輪詢規避此缺口。

先讀 AGENTS、README、STATUS、docs/CONNECT_AGENT.md、docs/EVIDENCE.md、docs/BACKGROUND.md。核對cwd/branch/HEAD/未提交變更，保留接續，不reset/clean。本批基底72673a3657b6e30c9c594dcc6140ddd6f147b096，同一feature集中提交、不推送；原有docs/research/排除。

本批新增：agent_dispatch.run(continuous=True)／CLI watch沿用原來源與固定budget跨事件、跨日待命；max_seconds只限每任務，空佇列零attempt/模型。GUI獨立auto開關與原生exe選擇，設定在忽略的data/agent-automation.json；單純開視窗不啟動，明確Start才恢復保存的選擇，Pause取消並核對owned child退出。非日額的reserve拒絕鎖定同pending，不再每poll建立空目錄。真CLI的單次設定停用project eventguard_test，避免混入聊天合成佇列。

本批真驗收尚未啟動：正常使用者login status成功，但固定budget不存在，reports/idle-wake-preflight-001.json保存budget_unavailable。已詢問人類2026-10-23台北當日EventGuard專用CLI已用數（0..5或未知），未獲回答前不能當0初始化。使用者這輪已批准有限公開合成自動驗收，不需再問同一模型授權。答覆後依AGENT_BUDGET初始化，不重設已有帳本；可用額度≥2時執行reports/idle-wake-proof.py的2事件流程，只有1時改--count 1，0時保留待測。該忽略helper使用真正continuous CLI、先觀察空閒才程式入列、核對實際三工具/SQLite/自然退出；失敗先查trace，不無變化重試。未啟用正式auto、改正式GUI或建立排程。

最新：本主對話已實際取得eventguard_test四個原生MCP工具並完成新合成事件的list→receive→inspect（仍pending）→同event/query補收→ACK→相同ACK重播→inspect（已ack）。native-root-calls.json保留七個完整實際MCP回傳；native-receipt-validation.json核對生成／收到／查證／ACK集合相同，missing=[]、duplicate_receipts=[]，該事件SQLite回條1張。先前命令工具事件另有1張，不能混成同一測試。這是本對話真正工具接收，沒有啟動另外的Codex CLI模型或自動喚醒；MCP連線由Codex管理而保留。之前工具不可用與子agent失敗屬歷史，不能再當目前阻塞，也不能刪除；本回合平台更新工具清單後成功，精確載入延遲根因未定案。

最新工作：本聊天透過命令工具實際接收一件程式合成事件、讀inspect、補收同event/query、明確ACK一次。找到ACKed事件對錯query／換decision誤回already_received，已改為唯讀驗既有query/result及實際來源回條；證據缺失不重建或猜成功。相同三元組才ack_replay_verified。相關模組驗證與原始操作在reports/chat-receive-001，數字只看EVIDENCE。

使用者已明確批准「限定的專案MCP接線」：.codex/config.toml僅eventguard_test，指向本輪隔離operator root與test namespace，只開list_events／inspect_event／receive_event／ack_event。不含正式事件、不改其他設定、不啟動模型；.codex已忽略不提交。先前子agent的native-receipt-stage1.json保留不可用失敗；後來主對話已實際可呼叫並完成接收。不要只憑metadata判成功，不強停owner、刪鎖、改安全設定或把設定移到全域。下一步若驗證其他真事件來源或自動喚醒，必須另外核對授權，不自動擴大這次synthetic-only範圍。

上游研究已補讀最新654dd716的完整25引擎catalog/plans/registry/launcher/adapter，及25個上游各README＋代表入口；不是所有repo逐行安全審計。見docs/SCANNER_ENGINES.md與SCANNER_RUNTIME_REVIEW.md；沒有安裝／執行掃描器。候選輸出超量提早停止仍未實作，勿干擾接收主線。

本批已依使用者指定研究 ai-security-scanner，兩個子agent分讀架構／UX，概念獨立實作後統一驗證。gui_presenter 提供人類摘要／原始JSON展開、當前最多100件本地篩選與完整性提示；observed_at修正。collector對非物件壞列留固定原因／計數及合法siblings，partial不清baseline或判恢復。研究固定commit、採納依據與未採納範圍見docs/SCANNER_LESSONS.md。命令與結果只讀EVIDENCE；不執行上游掃描器、不新增依賴。

最新使用者明確要求GUI，取代舊「GUI非目標」。優先交付直接使用：EventGuard.cmd開視窗，開始／暫停，七來源與事件可見，agent接收勾選。Start-EventGuard.cmd開GUI並送出開始；Status／Stopcmd及原CLI保留。X僅縮小；暫停並結束需耐久disabled及完整退出證據。核心無模型、無每日採集期限。

正式GUI前批已開啟並開始，status當次running_verified，七來源有資料；本批保留、不重啟／重掃，新UI於下次正常開啟載入，不能宣稱已熱更新。操作意圖可由使用者隨時改變，下一步先讀status，不為驗證重啟或全機重掃。GUI生命週期綁應用：child從建立就在私有Global Job，GUI不detach；host核對應用PID+creation，parent退出／未知即合作退出。沒有繞過外部Job。獨立CLIbackground模式保留舊拒絕外部Job契約。

agent_access是固定data/agent-delivery.json耐久開關，預設off。只有live適用，既有test/synthetic契約保留；每次adaptercall重新檢查，關閉不回傳metadata、不ACK，live dispatcher不啟動模型。人類OperatorAPI不受影響，pending/query保留。勾選只代表允許既有client接收，不等於已連線或喚醒目前聊天，不啟動模型。不得冒用舊有限驗收批准。

使用者並未批准前次登入排程plan。本輪無Task mutation／Run；程式變動使舊digest失效，若將來明確批准再生成新計畫。GUI開始／暫停不須排程，重開機登入恢復仍另待批准；不自行重開機、服務、自啟或排程。

一般權限、唯讀Windows、既有Python3.13標準庫／tkinter，不下載安裝、提權／UAC、改安全設定或執行政策、不讀秘密／完整命令列／原Codex sessions、不動其他程序。測試及程式事件均不可信，不提供處置授權。ACK是收到，不是修復／結案。

兩層互斥ownership開發、root整合功能後統一測試；fixture/mock/SDK函式/真Tk元件/真Windows有限Job/正式主機觀察分列。GUI畫面合成截圖不是實機安全證據。真模型、24小時、OS重啟與Phase7注入未驗證。命令、來源hash、退出／殘留及commit回條只讀EVIDENCE，不重做舊框架。

執行資料只留data/logs/reports，不提交憑證、Codex home、私人歷史或完整會話。正常已授權步驟不逐步詢問，必要外部批准需具體範圍。
