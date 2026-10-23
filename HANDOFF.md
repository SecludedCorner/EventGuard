# EventGuard 接手

先讀 AGENTS、README、STATUS、docs/GUI.md、docs/EVIDENCE.md、docs/BACKGROUND.md。核對cwd/branch/HEAD/未提交變更，保留接續，不reset/clean。本批基底d46236fdd20d59ff4c9ff1c7c7091bfd497f484d，同一feature集中提交、不推送；原有docs/research/排除。

最新工作：本聊天透過命令工具實際接收一件程式合成事件、讀inspect、補收同event/query、明確ACK一次。找到ACKed事件對錯query／換decision誤回already_received，已改為唯讀驗既有query/result及實際來源回條；證據缺失不重建或猜成功。相同三元組才ack_replay_verified。相關模組驗證與原始操作在reports/chat-receive-001，數字只看EVIDENCE。

使用者已明確批准「限定的專案MCP接線」：.codex/config.toml僅eventguard_test，指向本輪隔離operator root與test namespace，只開list_events／inspect_event／receive_event／ack_event。不含正式事件、不改其他設定、不啟動模型；.codex已忽略不提交。使用者找不到設定入口；不能繼續假定Settings→MCP servers必定可見。新子agent曾有四工具metadata，實際list_events回MCP tool eventguard_test/list_events is not available to the model並隨後移除namespace，證據native-receipt-stage1.json；未receive、query或ACK。新事件仍pending。工具metadata出現不等於可用，阻塞原因尚未定案；後續先取得用戶端/mcp狀態或實際介面，再核對有效設定。不要以SDK／CLI手動接收替代原生成功，不強停owner、刪鎖、改安全設定或把設定移到全域。

上游研究已補讀最新654dd716的完整25引擎catalog/plans/registry/launcher/adapter，及25個上游各README＋代表入口；不是所有repo逐行安全審計。見docs/SCANNER_ENGINES.md與SCANNER_RUNTIME_REVIEW.md；沒有安裝／執行掃描器。候選輸出超量提早停止仍未實作，勿干擾接收主線。

本批已依使用者指定研究 ai-security-scanner，兩個子agent分讀架構／UX，概念獨立實作後統一驗證。gui_presenter 提供人類摘要／原始JSON展開、當前最多100件本地篩選與完整性提示；observed_at修正。collector對非物件壞列留固定原因／計數及合法siblings，partial不清baseline或判恢復。研究固定commit、採納依據與未採納範圍見docs/SCANNER_LESSONS.md。命令與結果只讀EVIDENCE；不執行上游掃描器、不新增依賴。

最新使用者明確要求GUI，取代舊「GUI非目標」。優先交付直接使用：EventGuard.cmd開視窗，開始／暫停，七來源與事件可見，agent接收勾選。Start-EventGuard.cmd開GUI並送出開始；Status／Stopcmd及原CLI保留。X僅縮小；暫停並結束需耐久disabled及完整退出證據。核心無模型、無每日採集期限。

正式GUI前批已開啟並開始，status當次running_verified，七來源有資料；本批保留、不重啟／重掃，新UI於下次正常開啟載入，不能宣稱已熱更新。操作意圖可由使用者隨時改變，下一步先讀status，不為驗證重啟或全機重掃。GUI生命週期綁應用：child從建立就在私有Global Job，GUI不detach；host核對應用PID+creation，parent退出／未知即合作退出。沒有繞過外部Job。獨立CLIbackground模式保留舊拒絕外部Job契約。

agent_access是固定data/agent-delivery.json耐久開關，預設off。只有live適用，既有test/synthetic契約保留；每次adaptercall重新檢查，關閉不回傳metadata、不ACK，live dispatcher不啟動模型。人類OperatorAPI不受影響，pending/query保留。勾選只代表允許既有client接收，不等於已連線或喚醒目前聊天，不啟動模型。不得冒用舊有限驗收批准。

使用者並未批准前次登入排程plan。本輪無Task mutation／Run；程式變動使舊digest失效，若將來明確批准再生成新計畫。GUI開始／暫停不須排程，重開機登入恢復仍另待批准；不自行重開機、服務、自啟或排程。

一般權限、唯讀Windows、既有Python3.13標準庫／tkinter，不下載安裝、提權／UAC、改安全設定或執行政策、不讀秘密／完整命令列／原Codex sessions、不動其他程序。測試及程式事件均不可信，不提供處置授權。ACK是收到，不是修復／結案。

兩層互斥ownership開發、root整合功能後統一測試；fixture/mock/SDK函式/真Tk元件/真Windows有限Job/正式主機觀察分列。GUI畫面合成截圖不是實機安全證據。真模型、24小時、OS重啟與Phase7注入未驗證。命令、來源hash、退出／殘留及commit回條只讀EVIDENCE，不重做舊框架。

執行資料只留data/logs/reports，不提交憑證、Codex home、私人歷史或完整會話。正常已授權步驟不逐步詢問，必要外部批准需具體範圍。
