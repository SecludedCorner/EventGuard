# EventGuard 接手

先讀 AGENTS、README、STATUS、docs/GUI.md、docs/EVIDENCE.md、docs/BACKGROUND.md。核對cwd/branch/HEAD/未提交變更，保留接續，不reset/clean。GUI本批基底fd1e874e380512b2566dc2690368c20acd3813cd，同一feature集中提交、不推送；原有docs/research/排除。

最新使用者明確要求GUI，取代舊「GUI非目標」。優先交付直接使用：EventGuard.cmd開視窗，開始／暫停，七來源與事件可見，agent接收勾選。Start-EventGuard.cmd開GUI並送出開始；Status／Stopcmd及原CLI保留。X僅縮小；暫停並結束需耐久disabled及完整退出證據。核心無模型、無每日採集期限。

正式GUI本輪已開啟並開始，status當次running_verified，七來源有資料。操作意圖可由使用者隨時改變，下一步先讀status，不為驗證重啟或全機重掃。GUI生命週期綁應用：child從建立就在私有Global Job，GUI不detach；host核對應用PID+creation，parent退出／未知即合作退出。沒有繞過外部Job。獨立CLIbackground模式保留舊拒絕外部Job契約。

agent_access是固定data/agent-delivery.json耐久開關，預設off。只有live適用，既有test/synthetic契約保留；每次adaptercall重新檢查，關閉不回傳metadata、不ACK，live dispatcher不啟動模型。人類OperatorAPI不受影響，pending/query保留。勾選只代表允許既有client接收，不等於已連線或喚醒目前聊天，不啟動模型。不得冒用舊有限驗收批准。

使用者並未批准前次登入排程plan。本輪無Task mutation／Run；程式變動使舊digest失效，若將來明確批准再生成新計畫。GUI開始／暫停不須排程，重開機登入恢復仍另待批准；不自行重開機、服務、自啟或排程。

一般權限、唯讀Windows、既有Python3.13標準庫／tkinter，不下載安裝、提權／UAC、改安全設定或執行政策、不讀秘密／完整命令列／原Codex sessions、不動其他程序。測試及程式事件均不可信，不提供處置授權。ACK是收到，不是修復／結案。

兩層互斥ownership開發、root整合功能後統一測試；fixture/mock/SDK函式/真Tk元件/真Windows有限Job/正式主機觀察分列。GUI畫面合成截圖不是實機安全證據。真模型、24小時、OS重啟與Phase7注入未驗證。命令、來源hash、退出／殘留及commit回條只讀EVIDENCE，不重做舊框架。

執行資料只留data/logs/reports，不提交憑證、Codex home、私人歷史或完整會話。正常已授權步驟不逐步詢問，必要外部批准需具體範圍。
