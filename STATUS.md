# EventGuard 現況

## 2026-10-29 核對讀取時間與快照限制

桌面備份核對回傳第一次讀檔前／第二次驗檔後的UTC時間，畫面正規化UTC並明示計數是區間內資料庫快照、不能證明之後狀態。缺失、非法、無時區、逆序或未來時間顯未知，不補現在時間。`reports/verify-desktop-preview-time-20261029-02`：2026-10-29 14:19（UTC+8）39/39、0skip、source_unchanged、Job自然退出0／remaining0／無強停；受控時鐘驗clock→file→DB→file→clock，真Tk直接驗區間及缺時間清舊顯未知，DB bytes及pending／receipt守恆。01的38/38為補Tk前，02為最終；`reports/build-desktop-preview-time-20261029-01`286檔hash／264檔編譯通過。未新增讀檔、掃描／模型／ACK，非真人／Web驗收。

## 2026-10-29 備份核對整合229項通過

600ea414461263d560ebec40cf5857b47907af5d `feat(desktop): verify only the last locally created history backup`（+130/−4）及bff9d16f44a15487ca18c5d57b26cb50e242cefc `feat(desktop): expose explicit backup identity checks in Tk`（+151/−7）均各自來源build／相關測試後普通push並ff-only整合main，直接兩遠端ref核對bff9d16，兩工作樹及origin/main...HEAD差異0，未累積500行。`reports/verify-desktop-history-preview-final-20261029-01`：2026-10-29 14:13（UTC+8）27模組229/229、0skip、source_unchanged、263檔語法通過，Job自然退出0／remaining0／無強停；來源build285檔hash及263檔編譯通過。`reports/release-prep-desktop-history-preview-20261029-01`綁定bff9d16完整SHA，365檔可重現，未tag／release；純文件沿用來源build／相關整合並核對引用。

本次完成DESKTOP-HISTORY-PREVIEW，不代表來源認證、完整歷程還原、容量釋放、Web／真人／原生驗收。下一桌面切片為核對讀取時間區間與快照限制，讓計數有時間上下文；平台目標維持active。

## 2026-10-29 真Tk備份核對入口

新增「核對剛才備份」按鈕與獨立唯讀結果分頁；明確點選才讀檔，開分頁不讀；只在本視窗取得成功備份回條後啟用。結果核對檔名、固定計數／守恆及未知契約，不披露個別ID；檔案變動／錯誤回條清舊成功、新備份未確認禁用核對，不混入事件詳情。`reports/verify-desktop-history-preview-widgets-20261029-03`：2026-10-29 14:10（UTC+8）31/31、0skip、source_unchanged、Job自然退出0／remaining0／無強停；01為52/52，02補後來歷程與最小按鈕邊界15/15，03再驗新備份未確認，非相加。真Tk＋真合成SQLite驗計數／順序分歧／DB bytes及pending2／receipt0守恆，850×620新按鈕未超界。`reports/build-desktop-history-preview-widgets-20261029-01`285檔hash／263檔編譯；600ea41（+130/−4）已普通同步main／開發ref。未還原／清理／釋放容量、未原生查詢／模型／ACK。

## 2026-10-29 桌面備份身分核對控制層

僅記住本程序最後成功備份一份檔名／寫入handle身分／完整檔案hash；檔案開啟後先fstat核對再讀有界內容，前後路徑／metadata及hash相符才沿用Catalog單一唯讀交易預檢，再拒絕交易期間檔案變動。不公開內部檔案身分、不讀任意路徑，重開controller須重新明確備份。`reports/verify-desktop-history-preview-20261029-02`：2026-10-29 14:04（UTC+8）35/35、0skip、source_unchanged、Job自然退出0／remaining0／無強停；真合成SQLite驗比對／DB bytes守恆、未知／重開拒絕、缺檔／變動／同metadata異hash拒絕、身分不符時read哨兵未觸發。01的37含3項重複繼承，02移除後加強前置讀取守門，為最終。`reports/build-desktop-history-preview-20261029-01`284檔hash／262檔編譯通過。Tk入口尚待接線，不稱已還原或容量恢復。

## 2026-10-29 桌面人工處置及接續增量整合223項通過

人工處置與ACK獨立的四狀態入口、清單身分投影／分列／篩選、保存後刷新、歷史查證摘要及明確歷程備份均有真Tk＋真合成SQLite閉環；修復最小視窗無可見事件列及長回條裁切。各單元已逐筆普通同步main／開發ref，直接遠端核對產品92cc0807052f8cd35d177cdc22fa4c1ff40137c2；兩工作樹及對origin/main差異0，每commit增刪合計皆少於200，無累積500行。完整提交訊息／行數見EVIDENCE最新表。

`reports/verify-desktop-handling-complete-20261029-01`：2026-10-29 13:58（UTC+8）25個受影響模組223/223、0skip、source_unchanged、261檔語法通過，Job自然退出0／remaining0／無強停；`reports/build-desktop-handling-complete-20261029-01`283檔hash相符、261檔編譯。`reports/release-prep-desktop-handling-complete-20261029-01`綁定上述產品SHA，363檔可重現；未建立tag／release，不聲稱CI或真人／原生已通過。純文件本節沿用該來源build／相關整合並檢查引用。平台目標active且最新佇列接續桌面備份身分核對入口；Web／200%／真人／原生輸入／來源覆蓋／24h／reboot及完整歷程還原／容量釋放仍獨立待驗。

## 2026-10-29 窄視窗長備份回條換行修復

真映射Tk重現850×620長備份回條以固定1000px換行、超過label實際寬度（01）；現隨Configure事件按實際寬度換行，不截掉路徑與未確認／耐久性限制。`reports/verify-desktop-message-layout-20261029-02`：2026-10-29 13:55（UTC+8）46/46、0skip、source_unchanged、Job自然退出0／remaining0／無強停，真Tk→合成備份後驗1080×760／850×620換行寬度／完整label高度、選取列及備份控制仍可見，並回歸相關Tk入口。`reports/build-desktop-message-layout-20261029-01`283檔hash／261檔編譯通過；4a1cab6（+93/−10）已普通同步main／開發ref。非真人、原生輸入或Web200%驗收，無新查詢／模型／ACK。

## 2026-10-29 最小桌面視窗的事件列可見性修復

實際映射Tk視窗發現850×620事件列不可見（02），移出自動agent設定後列仍被裁6px（03）；現將控制放獨立設定分頁，Treeview縮放時see已選事件，未提高最小尺寸或放寬驗收。`reports/verify-desktop-handling-layout-20261029-04`：2026-10-29 13:52（UTC+8）50/50、0skip、source_unchanged、Job自然退出0／remaining0／無強停；精確核對1080×760／850×620 client、完整已選列、詳情文字行、三篩選／保存／四處置／備份控制全部祖先邊界、Tk Tab路徑及自動設定分頁幾何。01僅框線測試不足，04為最終。`reports/build-desktop-handling-layout-20261029-01`282檔hash／260檔編譯通過；bec37d8（+115/−3）已普通同步main／開發ref，非真人／原生輸入／Web縮放驗收。

## 2026-10-29 桌面歷程備份真Tk入口完成

真Tk按鈕明示本安裝live／敏感識別只留本機與不釋放容量，明確點選才寫檔；忙碌防重點，回條核對要求檔名／live／fsync及未刪歷程／未ACK，不符或失敗明示未確認、不自動重試。`reports/verify-desktop-history-backup-widgets-20261029-01`：2026-10-29 13:45（UTC+8）67/67、0skip、source_unchanged、Job自然退出0／remaining0／無強停，真Tk→真合成SQLite驗只產一份可驗hash備份、DB bytes及pending2／receipt0守恆、真實檔名碰撞不覆寫與錯誤回條不報成功。`reports/build-desktop-history-backup-widgets-20261029-01`：281檔hash／259檔編譯通過。deb4948（+99/−1）已普通同步main／開發ref；完整容量恢復仍未完成，備份不等於還原／耐久性或來源認證。

## 2026-10-29 桌面歷程備份控制層

沿用Catalog單一唯讀交易及既有write_backup，DesktopController.backup_history只明確保存本機reports檔、fsync／讀回核對、不覆寫、不清理／還原／釋放容量；活動前置失敗不寫檔，缺live DB不初始化。`reports/verify-desktop-history-backup-20261029-02`：2026-10-29 13:42（UTC+8）65/65、0skip、source_unchanged、Job自然退出0／remaining0／無強停，真合成SQLite／檔案測DB bytes、pending1／receipt0及既有檔守恆；01為新增測試錯用活動回條欄位，修正對照operation_started後通過。`reports/build-desktop-history-backup-20261029-01`280檔hash／258檔編譯通過，Tk入口尚待接線。

前一桌面／診斷整合`reports/verify-desktop-diagnosis-final-20261029-01`於13:41為175/175、0skip、Job自然退出無殘留，來源build279檔hash／257檔編譯通過；`reports/release-prep-desktop-diagnosis-20261029-01`綁定65d9d839c73679e10e1473ac68e06faf0c0d4790，359檔可重現。d28d817及65d9d83已普通同步main／開發ref；Web／真人／原生待驗不變。

## 2026-10-29 歷史查證真Tk／合成SQLite閉環

新增摘要實際Tk→真Catalog驗partial／拒讀／保存列數／截斷／current_only，重開文字一致、切換無保存事件不沿用別件、保存hash衝突清掉舊摘要並停用人工處置、修復後只讀恢復。`reports/verify-desktop-diagnosis-widgets-20261029-01`：2026-10-29 13:38（UTC+8）81/81、0skip、source_unchanged、Job自然退出0／remaining0／無強停；DB bytes與pending2／receipt0守恆，DiagnosticAPI.query／ACK哨兵未觸發。`reports/build-desktop-diagnosis-widgets-20261029-01`：279檔hash及257檔編譯通過。d28d817（+120/−4）已普通同步main／開發ref；不將Tk／synthetic升格為真人／Web／原生驗收。

## 2026-10-29 桌面歷史查證摘要

event_summary已接有界另存查證摘要：歷史結果／時間、來源狀態／保存列數、截斷、current_only及缺口分列；Catalog先驗payload hash，呈現再核對事件ID及保存投影標記，缺失／不符未知，不推導目前安全或恢復。`reports/verify-desktop-diagnosis-summary-20261029-01`：2026-10-29 13:35（UTC+8）97/97、0skip、source_unchanged、Job自然退出0／remaining0／無強停，含純呈現、既有實際Tk回歸及Catalog診斷身分契約；新增摘要真Tk＋真合成SQLite閉環尚待下一單元。`reports/build-desktop-diagnosis-summary-20261029-01`：278檔hash及256檔編譯通過。ee8c256（+16/−0）已普通同步main／開發ref；沒有新增查詢／模型／ACK。

## 2026-10-29 桌面人工狀態／清單整合158項通過

54f3f2a（+142/−2）、023644a（+89/−9）、d8e6e21（+97/−10）已各自build／相關測試後commit、普通push並ff-only整合main，兩遠端直接核對d8e6e214285e3b9bf1643e25e6ecbc700e3cddfa，工作樹與對origin/main差異0。`reports/verify-desktop-handling-visible-final-20261029-01`於2026-10-29 13:32（UTC+8）158/158、0skip、source_unchanged、255檔語法通過，Job自然退出0／remaining0／無強停；包含13個受影響模組及真Tk／合成SQLite，非真人／Web／原生驗收。來源build277檔hash相符；`reports/release-prep-desktop-handling-visible-20261029-01`綁定上述SHA，357檔可重現，未發布。get_goal回讀active，桌面優先與完整待驗保留。下一個桌面缺口：目前另存查證只顯時間，需唯讀摘要分開歷史結果／可見性／截斷及未知，先核對保存契約，不新增查詢或ACK。

## 2026-10-29 真Tk人工狀態篩選

人工狀態、嚴重度及接收狀態可取交集，只涵蓋已載入最多100件；含未知選項及一鍵清除。真Tk＋合成SQLite驗交集、計數、隱藏選取清掉詳情、保存後不符篩選移出視圖、清除還原、讀取DB bytes與pending／receipt守恆；pure presenter另驗101件邊界，不宣稱全庫。`reports/verify-desktop-handling-filter-20261029-01`：2026-10-29 13:29（UTC+8）68/68、0skip；補強真Tk未知選項後02為27/27、0skip（13:30），來源產品不變，不相加。皆source_unchanged、Job自然退出0／remaining0／無強停。`reports/build-desktop-handling-filter-20261029-01`：277檔hash及255檔編譯通過。023644a（+89/−9）已普通同步main及開發ref；GUI操作文件同步更新，Web／真人／原生仍各自待驗。

## 2026-10-29 真Tk清單人工處置與接收分列

清單新增獨立人工處置欄，明示非ACK／修復；缺失或非法投影顯未知。實際Tk＋真合成SQLite驗四狀態顯示、只讀DB bytes守恆、已處理仍待接手、payload變動／缺欄未知，以及按鈕保存後清單／詳情讀回及保留選取。修復詳情請求忙碌造成清單刷新遺失：保留單一待刷新旗標，worker空閒才只讀刷新。`reports/verify-desktop-handling-list-20261029-02`：2026-10-29 13:26（UTC+8）68/68、0skip、source_unchanged、Job自然退出0／remaining0／無強停；01的67/68揭露上述缺陷，已修正。`reports/build-desktop-handling-list-20261029-01`：277檔hash及255檔編譯通過。54f3f2a（+142/−2）已普通同步main／開發ref；本單元亦逐單元保存，未觸發採集／模型／ACK。

## 2026-10-29 清單人工狀態的唯讀身分投影

Desktop snapshot以最多100件已載入事件核對Catalog保存payload hash及delivery，獨立提供handling_status；缺失、重複、損壞、身分或delivery變動皆unknown，不沿用另一事件的決定，不建立缺失DB或寫入／ACK。`reports/verify-handling-projection-20261029-02`：2026-10-29 13:22（UTC+8）60/60、0skip、source_unchanged、Job自然退出0／remaining0／無強停；`reports/build-handling-projection-20261029-01`受測來源hash及254檔編譯通過。01的58/59為測試連線未關閉，已修正並加非法身分測試，非通過證據。下一單元接實際Tk清單分列與合成閉環；本單元尚非清單UI完成。

## 2026-10-29 桌面人工狀態最終整合145項通過

cc21787（+103/−2）、7b102d5（+126/−7）、1ee626d（+128/−0）已各自build／相關測試後指定檔案commit、普通push開發分支及ff-only整合／push main，直接核對兩ref=1ee626d6dd11e0f7883de5e953eb10ecafee9564，兩工作樹與對origin/main差異0。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-handling-final-20261029-01 --timeout-seconds 180`加該目錄summary所列11個`--module`，2026-10-29 13:13（UTC+8）145/145、0skip、source_unchanged、253檔語法通過、Job自然退出0／remaining0／無強停。包含真Tk＋真合成Catalog及既有ACK分離fixture，人工狀態路徑不ACK；未執行原生採集或模型，不與前述重疊測試相加。`reports/release-prep-desktop-handling-20261029-01`綁定該SHA、355檔可重現。平台目標再回讀active／桌面人工狀態優先／保留Web及main授權皆相符；整體目標未完成，下一個桌面增量清單人工狀態可見性已排入既有文件。純文件沿用來源build／相關測試並核對引用。

## 2026-10-29 人工狀態真Tk／SQLite閉環

真Tk四狀態保存／重開與gui歷程已驗，event payload hash及pending2／receipt0保留；提交後模擬回條遺失，UI明確沿用同ID重試，另一較新CLI決定不被回退，僅2筆歷程。實際每事件歷程滿載拒絕交易且DB hash不變；活動故障後讀回復原，忙碌重點只寫1筆，切換事件不串案。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-handling-widgets-20261029-02 --timeout-seconds 180 --module test_desktop_handling_widgets --module test_gui --module test_desktop_handling --module test_disposition_history_integration`：2026-10-29 13:10（UTC+8）57/57、0skip、source_unchanged、Job自然退出0／remaining0；01亦57/57，02收緊為真容量滿載與重點守恆，為最終。`reports/build-desktop-handling-widgets-20261029-01`：275檔hash相符、253檔編譯。7b102d5已逐單元普通同步main／開發ref；平台目標active。Web、真人／原生輸入與採集待驗不變。

## 2026-10-29 桌面人工狀態按鈕與同ID重試

真Tk新增new／read／handled／ignored入口及人工狀態標示；未選取、詳情未知或忙碌時禁用，結果綁定事件／operation_id，保存後只讀重載。未確認要求保留同ID，明確再點原狀態才重送，不自動重試；最多128個未確認key，滿載拒絕新要求而不丟冪等識別。容量／活動前置失敗不宣稱成功。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-handling-buttons-20261029-01 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop_handling --module test_desktop_investigation_widgets`：2026-10-29 13:05（UTC+8）61/61、0skip、source_unchanged、Job自然退出0／remaining0，真Tk＋fixture及控制層SQLite。`reports/build-desktop-handling-buttons-20261029-01`：274檔hash相符、252檔編譯。cc21787已同步main；平台目標已用支援編輯介面保存桌面優先內容，get_goal回讀active，保留原Web及獨立驗收，不再是舊blocked卡。下一步真Tk→真Catalog人工狀態整合，尚未宣稱該閉環完成。

## 2026-10-29 桌面人工狀態控制層

DesktopController.set_status固定source=gui並要求明確operation_id，沿用Catalog交易與有界操作歷程；活動先保存意圖且目標只hash，不採集／模型／ACK。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-handling-controller-20261029-01 --timeout-seconds 180 --module test_desktop_handling --module test_desktop --module test_disposition_history_integration --module test_activity`：2026-10-29 12:58（UTC+8）54/54、0skip、source_unchanged、Job自然退出0／remaining0。真合成SQLite驗四狀態／gui歷程、同ID重播不覆蓋後來決定、容量／活動失敗保留舊DB、非法狀態／缺key拒絕，pending1／receipt0不變。`reports/build-desktop-handling-controller-20261029-01`：274檔hash相符、252檔編譯。目標檔已更新桌面A–C閉環，平台卡仍舊Web blocked，不冒稱已恢復；Tk按鈕為下一單元，既有Web／真人／原生待驗保留。

## 2026-10-29 桌面增量最終整合121項通過

控制層acadbaa（+94/−2）、按鈕13d9d94（+101/−4）、真Tk閉環1940a3b（+143/−1）、操作文件caa19c5（+26/−10）、讀取失敗ce55788（+44/−0）均逐單元build／測試後commit／普通push開發ref，再普通ff-only整合main，未累積超過500行。直接遠端核對兩ref=ce557888581a230b3ea8f12e39c60f058dec02aa，原專案與整合工作樹乾淨／對origin/main差異0。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-save-final-20261029-01 --timeout-seconds 180`加該目錄summary所列10個`--module`，2026-10-29 10:33（UTC+8）121/121、0skip、source_unchanged、251檔語法通過，Job自然退出0／remaining0／無強停；不與前述重疊定向相加。`reports/release-prep-desktop-investigation-20261029-01`綁定ce55788完整SHA，353檔可重現，未建立tag／release。真人／Web／原生及原生輸入待驗保留；純文件本節沿用該版本來源build／相關測試並核對引用，不停止已授權桌面工作。

## 2026-10-29 桌面狀態讀取失敗明示未知

修正snapshot例外只顯錯誤但保留舊資料：七來源／筆數／事件與詳情改為未知或清空，依賴舊詳情的保存禁用；接收及自動狀態明示未知，不宣稱已撤銷權限／停止，未變更保存設定。恢復讀取後可重新顯示原事件。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-snapshot-failure-20261029-03 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop_investigation_widgets --module test_desktop_source_consistency`：2026-10-29 10:30（UTC+8）61/61、0skip、source_unchanged、Job自然退出0／remaining0；01先重現1失敗，02／03通過，最終為03。`reports/build-desktop-snapshot-failure-20261029-02`：273檔hash相符、251檔編譯通過。caa19c5已同步main／開發ref。另原生點選有界2次，CUA未列專用fixture視窗，未送點選／鍵盤；01／02兩自有子程序皆合作自然exit0／remaining0／未強停，回條在reports/desktop-ui-acceptance-20261029-01及02。此局部待驗不阻止桌面開發，Web／真人／原生採集仍各自待驗。

## 2026-10-29 桌面操作文件移除過期每日預算說明

GUI／CONNECT_AGENT依現行程式修正：沒有每日五次quota或預算初始化前置；桌面dispatcher仍有當次預設5個任務與waiting_task_limit，不因跨日自動恢復，模型帳戶／授權界線保留。這是修正文檔，不是修改或執行模型限制。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-guide-no-quota-20261029-01 --timeout-seconds 180 --module test_application_no_quota --module test_communication_no_quota --module test_agent_automation`：2026-10-29 10:19（UTC+8）17/17、0skip、source_unchanged、Job自然退出0／remaining0；純文件核對src/desktop.py的run參數與dispatcher上限語意、本地引用及diff，沿用當前來源build。1940a3b已普通同步main與開發ref，桌面保存閉環已驗；Web、真人與原生待驗保留。

## 2026-10-29 桌面保存調查閉環實測

真Tk按鈕→DesktopController→真合成Catalog／SQLite已驗保存、更新保留1前版、重開讀回；容量失敗原DB hash不變，pending2／receipt0，保存中切換事件不顯錯案。完成訊息標明原請求事件ID，避免新選取被誤認為已保存。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-investigation-widgets-20261029-03 --timeout-seconds 180 --module test_desktop_investigation_widgets --module test_gui --module test_desktop_investigation --module test_investigation_revision_integration`：2026-10-29 10:16（UTC+8）49/49、0skip、source_unchanged、Job自然退出0／remaining0。01為fixture刷新間隔超上限及未清視窗造成3error／3fail；02修正間隔／清理後47/49，2項斷言誤用前版標籤，03改核對實際成員雜湊語意後通過。`reports/build-desktop-investigation-widgets-20261029-01`：273檔hash相符、251檔編譯成功。13d9d94已普通同步main／開發ref；Web、真人版面／鍵盤、原生驗收仍保留待驗。

## 2026-10-29 桌面保存調查按鈕與失敗呈現

實際Tk新增「建立／更新保存調查」，只在所選事件詳情已核對且非忙碌時啟用；序列worker執行，忙碌時重點不重複保存。結果綁定請求事件，保存後只讀重載；容量不足明示舊案保留，其他未確認結果不宣稱成功／不自動重送。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-investigation-button-20261029-01 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop_investigation --module test_desktop`：2026-10-29 10:09（UTC+8）82/82、0skip、source_unchanged、Job自然退出0／remaining0；真Tk按鈕＋fixture controller驗無選取禁用、明確單次保存／讀回、容量失敗與pending保留，不是完整真Catalog按鈕驗收。`reports/build-desktop-investigation-button-20261029-01`：272檔hash相符、250檔編譯通過。前單元acadbaa已普通同步main／開發ref。下一單元補真Tk→真合成Catalog保存／更新／重開整合；Web／真人／原生待驗不變。

## 2026-10-29 桌面明確保存調查：控制層

依使用者最新指示續做桌面，瀏覽器待驗保留。原專案乾淨但落後15個已整合commit，已ff-only同步至20f8895；+1246/−28是舊checkout對已推送基準的同步，非新backlog，當時對origin/main差異0。新增DesktopController.investigate沿用EventCatalog已保存metadata調查；活動先落意圖、記錄目標hash，無採集／模型／ACK。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-investigation-controller-20261029-01 --timeout-seconds 180 --module test_desktop_investigation --module test_desktop --module test_activity --module test_event_investigation`：2026-10-29 10:05（UTC+8）64/64、0skip、source_unchanged、Job自然退出0／remaining0；合成資料驗保存／重開、容量失敗舊案不變、活動失敗不保存、缺事件不建立、pending2／receipt0不變。`reports/build-desktop-investigation-controller-20261029-01`：272檔hash相符、250檔編譯通過。只完成控制層，桌面按鈕接線與Tk驗收下一單元；Web／真人／原生關卡仍待驗。

## 2026-10-29 清單修正整合與驗收阻擋盤點

df55da8bb06bca06853b3b0fb9354e4a340717c4（fix(web): make failed event list refreshes explicitly unknown，+110/−2）已普通push開發ref、ff-only merge／普通push main並直接核對兩ref一致，工作樹／對main差異0。42/42與249檔編譯見下節；`reports/release-prep-web-list-read-state-20261029-01`綁定此SHA，351檔來源包可重現；`reports/build-web-list-javascript-20261029-01`完整served JS語法通過、私有Job自然退出0／remaining0。單次瀏覽器inventory仍空且回傳Work settings disabled，回條已保存；未把授權問題歸給使用者。最終目標逐項盤點見MAINTENANCE_GOAL頂部：核心功能有離線證據，本版真瀏覽器／200%／焦點、人類可比量測、原生各自仍缺外部條件，目標未完成。純文件沿用本版來源build／相關測試，檢查diff及引用路徑；不反覆輪詢或添加無關功能代替驗收。

## 2026-10-29 Web事件清單失敗與獨立刷新

清單重新確認時筆數標示尚未確認、分頁暫停；HTTP／格式錯誤清除舊列，筆數未知並停用分頁，隱藏未確認詳情。比對筆數／分頁一致性與唯一合法ID，晚到成功／失敗不覆蓋新清單。高嚴重度提示失敗只顯示未知，不再阻止事件清單獨立刷新；恢復前清除舊提示cache以重建內容。`py -3.13 -B scripts/verify.py --run-dir reports/verify-web-list-read-state-20261029-03 --timeout-seconds 180 --module test_web_event_list_read_state --module test_application_ui_state --module test_event_catalog --module test_web_detail_read_state --module test_web_source_read_state`：2026-10-29 03:59（UTC+8）42/42、0skip、source_unchanged、Job自然退出0／remaining0，實際JS＋synthetic DOM/API，非瀏覽器。01原程式重現失敗；02測試未載入實際invalidate helper而1失敗，補入後03通過。`reports/build-web-list-read-state-20261029-01`：271檔hash相符、249檔編譯成功。Web真瀏覽器／200%／真人／原生仍待驗。

## 2026-10-29 Web讀取故障修正已同步main

f8ec035（fix(web): mark failed detail reads unknown and gate writes，+124/−5）與87f7575（fix(web): clear unconfirmed source cards and ignore stale replies，+101/−3）已逐單元普通push開發ref，再ff-only merge／普通push main，直接ls-remote核對兩ref=87f7575915a9f0fed0d53ad788b256e1fc44b909；相對main累積由233行清零，工作樹乾淨。41項與44項為重疊定向，不能相加；最終來源與詳情JS合成驗證見下節。`reports/release-prep-web-read-state-20261029-01`：綁定該SHA、350檔可重現。`reports/build-web-javascript-20261029-02`：完整served JS以既有Node --check通過、私有Job自然退出0／remaining0／未強停；01回條reason不合法失敗未冒稱通過，改用既有test_teardown後02為最終。純文件沿用來源build及測試，diff／引用路徑檢查通過。真瀏覽器／200%／真人／原生／完整恢復仍未驗，CI亦未確認。

## 2026-10-29 Web來源卡片失敗與舊回覆防護

來源讀取中清除舊卡片並明示未知；HTTP／格式錯誤不沿用先前成功，七個唯一來源驗證完成後才依固定順序一次呈現。新請求序號阻擋晚到成功／失敗覆蓋新結果，保持歷史成功、原結果、目前狀態與新鮮度分列。`py -3.13 -B scripts/verify.py --run-dir reports/verify-web-source-read-state-20261029-02 --timeout-seconds 180 --module test_web_source_read_state --module test_web_detail_read_state --module test_application_ui_state --module test_source_success_history --module test_product_sources`：2026-10-29 03:52（UTC+8）44/44、0skip、source_unchanged、Job自然退出0／remaining0。Node執行實際renderer／node／時間函式，六情境及缺失／重複／空集合／晚到回覆合成已驗，非瀏覽器。01為43通過1失敗（fixture把本地化日期當ISO），改與實際when函式輸出比較後02通過；不更動產品日期語意。`reports/build-web-source-read-state-20261029-01`：270檔hash相符、248檔編譯成功。Web／200%／真人／原生維持待驗。

## 2026-10-29 Web詳情失敗與身分核對

詳情新增讀取狀態；同事件刷新失敗時清除舊內容、處置／調查／投遞資料維持未知並停用寫入，重試成功才恢復。回覆event_id須符合請求，晚到失敗／成功不串到其他案件，失敗不續查delivery；按鈕處理函式亦拒絕未確認詳情。`py -3.13 -B scripts/verify.py --run-dir reports/verify-web-detail-read-state-20261029-03 --timeout-seconds 180 --module test_web_detail_read_state --module test_application_ui_state --module test_event_catalog --module test_investigation_revision_renderer`：2026-10-29 03:49（UTC+8）41/41、0skip、source_unchanged、Job自然退出0／remaining0；Node執行實際JS函式與處理器＋synthetic DOM/API，非瀏覽器驗收。`reports/build-web-detail-read-state-20261029-02`：269檔hash相符、247檔編譯通過。01／02各41/41；修復寫檔造成的換行雜訊後03重驗，diff-check通過，不提交無關換行修改。Web真瀏覽器／200%／真人／原生仍待驗。

## 2026-10-29 桌面與歷程增量已整合main

56786b4（+162/−10）、534d0f1（+122/−6）、1518062（+35/−1）、dd4deeb（+87/−6）均已審查、build／相關測試通過、逐單元普通push開發ref，再以ff-only merge普通push main。直接ls-remote核對兩ref=dd4deebaa9846b61f29974d64436c3c83563b589，工作樹及對origin/main差異0；未改寫歷史、刪分支或release。最終跨受影響模組整合：`py -3.13 -B scripts/verify.py --run-dir reports/verify-main-desktop-history-20261029-01 --timeout-seconds 180`加該目錄verification-summary所列13個`--module`，2026-10-29 03:42（UTC+8）131/131、0skip、source_unchanged、Job自然退出0／remaining0，246檔語法檢查通過。`reports/release-prep-history-transition-preview-20261029-01`綁定該40碼SHA，348檔來源包可重現；未確認CI，不等於真人／瀏覽器／原生或完整恢復驗收。本節純文件沿用上述來源build／測試並檢查diff與既有路徑。

## 2026-10-29 唯讀恢復預檢呈現轉換衝突

`events preview-history` JSON及中文文字新增備份內逐事件相鄰轉換檢查，與目標前綴／事件身分獨立；無相鄰紀錄不當通過，相符只限已提供紀錄，第一筆以前／遺漏／完整性、來源與可恢復性仍未知。與恢復拒絕閘道共用純函式，不寫入／還原／刪除或ACK。`py -3.13 -B scripts/verify.py --run-dir reports/verify-history-transition-preview-20261029-03 --timeout-seconds 180 --module test_disposition_history_backup_preview --module test_disposition_history_preview_cli --module test_disposition_history_restore --module test_disposition_history_restore_prefix --module test_disposition_history_restore_integration --module test_application_cli_text --module test_disposition_history_contract`：2026-10-29 03:39（UTC+8）34/34、0skip、source_unchanged、Job自然退出0／remaining0；含多事件交錯、noop、DB hash與pending／receipt保留。01模組名稱錯誤未執行，02為33/33，最終03通過。`reports/build-history-transition-preview-20261029-02`：268檔hash相符、246檔編譯通過。剩餘驗收仍為可證來源／完整使用者恢復、Web、真人與原生關卡。

## 2026-10-29 歷程恢復的內部轉換一致性

修正append-only恢復原語：同一事件的下一筆previous_status必須符合上一筆status，逐事件核對保存順序，不以時間重排；內容重算hash不能繞過此檢查，衝突在寫入前拒絕。`py -3.13 -B scripts/verify.py --run-dir reports/verify-history-transition-order-20261029-02 --timeout-seconds 180 --module test_disposition_history_restore --module test_disposition_history_restore_prefix --module test_disposition_history_restore_integration --module test_disposition_history_backup --module test_disposition_history_backup_preview --module test_disposition_history_store --module test_disposition_history_integration`：2026-10-29 03:36（UTC+8）35/35、0skip、source_unchanged、Job自然退出0／remaining0；01先重現1失敗，02通過，衝突DB hash及pending／receipt保留。`reports/build-history-transition-order-20261029-01`：268檔hash相符、246檔編譯成功。只驗合成內部原語，未建立來源認證、使用者還原／容量釋放流程或實機恢復。前單元534d0f1已普通ff merge／push並核對兩ref一致。

## 2026-10-29 桌面詳情讀取與重試

切換事件立即清除舊詳情並顯示讀取中；worker結果綁定實際請求ID，錯誤／身分不符維持未知且可重點同列重試，不補造pending。合併中的選擇以最後選取為準，過期結果不顯示其他事件。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-detail-failure-20261029-04 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_gui_saved_evidence --module test_desktop`：2026-10-29 03:33（UTC+8）79/79、0skip、source_unchanged、Job自然退出0／remaining0，含實際Tk與fixture；01先重現2失敗，02／03及最終04通過。`reports/build-desktop-detail-failure-20261029-02`：268檔hash相符、246檔編譯通過。前單元56786b4已普通ff merge／push並直接核對main及開發ref一致，工作樹與分支差異清零；未做Web、真人、原生驗收。

## 2026-10-29 桌面來源欄位統一保存資料入口

修正桌面來源列混用舊overview與新保存成功紀錄：狀態、筆數、時間、原因及歷史成功改由同次source_status結果投影。最後結果與新鮮度分列，未知／讀取失敗不回退舊成功；stale保留歷史拒讀但current_coverage未知，test成功不供live使用。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-source-consistency-20261029-05 --timeout-seconds 180 --module test_desktop_source_consistency --module test_desktop --module test_gui --module test_source_success_history`：2026-10-29 03:27（UTC+8）77/77、0skip、source_unchanged，Job自然退出／remaining0；含實際Tk＋保存合成觀察、讀前後hash不變與採集哨兵。`reports/build-desktop-source-consistency-20261029-01`：268檔hash相符、246檔編譯成功。01的2失敗與03的1失敗是固定fixture時間晚於wallclock，改固定過去epoch後時間保護保留；02為75/75、04為76/76，最終以05為準。人工／Web／原生仍待驗。

## 2026-10-29 保存證據變更到桌面元件的整合核對

新增測試以合成SQLite建立最新與前版調查，再移除／變更關聯事件，經真EventCatalog讀取到實際Tk元件；最新與前版都顯未知，不沿用「保存成員相符」。每次讀取前後SQLite hash相同、anchor仍pending、未採集／模型／ACK。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-evidence-changes-20261029-01 --timeout-seconds 180 --module test_gui_saved_evidence --module test_gui --module test_gui_presenter --module test_investigation_revision_read --module test_investigation_revision_integration --module test_event_investigation`：79/79、0skip；補正缺display的TclError明示skip路徑後，`--run-dir reports/verify-desktop-evidence-changes-20261029-02 --timeout-seconds 180 --module test_gui_saved_evidence` 於2026-10-29 03:19（UTC+8）2/2、0skip、source_unchanged，兩次Job自然退出／remaining0。`reports/build-desktop-evidence-changes-20261029-01`：267檔hash相符、245檔編譯成功。此為實際元件＋合成資料，不是人類操作或實機驗收。

## 2026-10-29 桌面前版調查只讀摘要

桌面詳情新增最多最近3版保存摘要，保持後端讀取順序，成員與診斷狀態獨立；錨點身分缺失／不符不顯其他案件，時間異常保持未知，舊資料不補造前版，容量滿載明示。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-revision-summary-20261029-02 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop --module test_investigation_revision_read --module test_investigation_revision_integration`：2026-10-29 03:15（UTC+8）85/85、0skip、source_unchanged；真Tk＋合成EventCatalog驗真保存前版到文字元件與未知時清除，pending不變，Job自然退出／remaining0。`reports/build-desktop-revision-summary-20261029-01`：266檔hash相符、244檔編譯，含未提交修改。01為補強缺失身分前的85/85，最終證據以02為準。人工／Web／原生仍各自待驗。

## 2026-10-29 桌面保存時間線與證據缺口

桌面調查詳情加入最多16項保存時間線，保留快照順序而不重排／推導關係；每項列出保存來源可見性，缺失／內容改變維持未知，恢復轉換不當目前修復證明。最多8項中文缺口，未知原因不補造。前兩個摘要單元已普通同步main與開發ref至c3d34fa，對main差異曾清零。本次 `py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-saved-timeline-20261029-02 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop --module test_event_investigation`：2026-10-29 03:12（UTC+8）91/91、0skip、source_unchanged、Job自然退出／remaining0；包含真EventCatalog合成資料到實際Tk元件、拒讀／partial、順序與界限測試。`reports/build-desktop-saved-timeline-20261029-02`：266檔受測hash相符、244檔編譯成功，含未提交變更。人工版面／鍵盤、Web與實機仍待驗。

## 2026-10-29 桌面人工處置與操作歷程摘要

桌面事件詳情新增人工處置狀態與最後8筆保存操作，來源標為通道而非已驗證操作者；已處理不當ACK或修復，無紀錄／損壞維持未知，容量滿載與更早歷程未知分列。`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-handling-summary-20261029-01 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop --module test_disposition_history_read --module test_disposition_history_integration`：2026-10-29 03:07（UTC+8）84/84、0 skip、source_unchanged，真Tk＋fixture核對handled仍pending、舊歷程清除、唯讀元件；Job自然退出0／remaining0。`reports/build-desktop-handling-summary-20261029-01`：266檔受測hash相符、244檔編譯通過。未採集／模型／ACK；人工UI與Web待驗不升格。

## 2026-10-29 桌面保存調查友善摘要

事件詳情在既有唯讀 Tk 文字元件新增保存調查摘要，分列成員雜湊／診斷證據、新鮮度、關聯項目與缺口。缺少調查不補造，錨點身分不符不顯示其他案件，格式異常維持未知；歷史相符不等於來源認證或目前安全，未推定程序樹／攻擊鏈。2026-10-29 03:05（UTC+8）`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-investigation-summary-20261029-02 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop --module test_event_investigation`：87/87、0 skip、source_unchanged，含真 Tk 元件＋fixture、只讀刷新與舊案清除，Job 自然退出 0／remaining 0。`reports/build-desktop-investigation-summary-20261029-01`：266檔hash與受測來源相符、244檔編譯成功，含未提交變更。人工桌面版面／鍵盤與 Web 瀏覽器驗收仍待驗。本次在已附加的整合工作樹從572bb49增量接續，HEAD原為detached，保存仍推指定開發遠端ref，不覆寫其他checkout。

## 2026-10-29 main 整合已推送（最新）

已以普通 merge commit `93910625f509b43a4aae7ee22abe58c3e1e9e5b8` 合併開發成果至 origin/main，推送後直接 ls-remote 核對一致；父 main=c80a4be、開發來源=66638ae。相對第一父 commit：50 檔 +3971/−72，為本次已批准清理的既有 backlog，非新的未提交修改。原開發分支已 ff 同步此 main；相對 origin/main 待整併 diff 已為 0。本地舊 main 無共同祖先，原樣保留，未改寫歷史或建立 tag／release。

本次整合回報純文件：`reports/release-prep-main-checkpoint-20261029-01` 綁定父9391062，346檔build可重現；`py -3.13 -B scripts/verify.py --run-dir reports/verify-main-checkpoint-20261029-01 --timeout-seconds 180 --module test_package_candidate`，2026-10-29 03:01（UTC+8）8/8、0 skip、Job自然退出／remaining0；diff／本地連結檢查通過，不重跑未受影響的完整產品測試。

完整證據保存在 `reports/main-integration-20261029-01`：首輪 1738 執行、1735 通過、1 失敗、2 skip；修正公開 fixture 的 checkout 路徑假設後，第二輪 1738 執行、1736 通過、0 失敗、2 symlink 環境 skip，source_unchanged、Job 自然退出 0／remaining 0／無強停。第二輪 `verify-main-integration-20261029-02` UTC 2026-10-28 18:59:49；346 檔來源包可重現、244 檔 Python 編譯成功。這些是 fixture／受管程序與 Tk 元件測試，不是 Web 瀏覽器、真人、原生覆蓋、24h／reboot／桌面喚醒驗收。後續兩個 500 行比較基準及主線整合流程見 CLAUDE；CI 狀態獨立，不以 push 成功當 CI 通過。

## 2026-10-29 整合測試的受保護 checkout 路徑修正

隔離整合工作樹在 `.codex` 下，首次完整回歸的 shipped facts example 測試直接把該路徑交給 inventory，觸發既有 private_or_build_path_refused 保護。main 整合暫停；測試改將已知公開範例複製至專用臨時目錄再驗證，沒有修改產品拒讀規則。`reports/verify-inventory-fixture-location-20261029-01` 因指定不存在模組而未執行測試，保留此命令失敗；正確命令 `py -3.13 -B scripts/verify.py --run-dir reports/verify-inventory-fixture-location-20261029-02 --timeout-seconds 180 --module test_intelligence_integration --module test_adversarial_intelligence`，2026-10-29 02:50（UTC+8）：16/16、0 skip、source_unchanged，Job 自然退出／remaining 0。`reports/build-inventory-fixture-location-20261029-01`：266 檔 hash 相符、244 檔 Python 編譯通過。尚需在隔離整合樹重跑完整回歸，未將首輪失敗改記通過。

## 2026-10-29 500 行範圍更正與 main 整合

使用者澄清上限包含開發分支相對 main 待整併差異，並明確授權測試通過後普通 merge／push main。CLAUDE 已更新兩個比較基準與整合流程；不再以開發分支已 push 代替整合。開始時工作樹乾淨、開發分支 c83ff95 遠端一致；origin/main=c80a4be，相對差異 49 檔 +3936/−71。這是既有 backlog，先完成整合，暫不增加產品功能。本地 main 為保留的不同歷史，無共同祖先；不覆寫，從 origin/main 準備隔離整合 checkout。整合結果另記，尚未宣稱 main 更新或產品驗收完成。

2026-10-29 02:41（UTC+8）父版本來源 build：`py -3.13 -B scripts/package_candidate.py --root reports/release-prep-branch-limit-20261029-01 --commit c83ff950e59646c0de48fce907b43bee2a89ecfa`，346 檔可重現；`py -3.13 -B scripts/verify.py --run-dir reports/verify-branch-limit-20261029-01 --timeout-seconds 180 --module test_package_candidate`，8/8、0 skip、Job 自然退出／remaining 0。純文件另做 diff／連結檢查，不含新產品驗收。

## 2026-10-29 桌面詳情共用保存資料入口

DesktopController.inspect 改用既有 EventCatalog.detail，帶回已保存調查、修訂與處置歷程；仍明示 system_query_executed=false，不執行 diagnose／採集／模型／ACK。合成事件在臨時 live 目錄建立保存調查後，讀取保持 SQLite hash 與 pending 不變。2026-10-29 02:35（UTC+8）`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-saved-detail-20261029-01 --timeout-seconds 180 --module test_desktop --module test_gui --module test_event_investigation`：75/75、0 skip、source_unchanged、Job 自然退出 0／remaining 0。`reports/build-desktop-saved-detail-20261029-01`：受測 manifest 266 檔相符、244 Python 編譯成功，包含未提交變更。此切片接通資料與原始結構化檢視，友善摘要下一單元；人工桌面與瀏覽器仍待驗。

## 2026-10-29 持續執行順序更新

MAINTENANCE_GOAL 與 CLAUDE 已明定瀏覽器待驗不阻塞桌面／離線產品工程、每單元驗證後立即保存並接續，保留所有原 Web／實機驗收條件。平台目標卡片仍為 blocked；嘗試其「編輯目標」介面兩次均遇座標幾何不可用，未宣稱卡片已更新或恢復。磁碟佇列可繼續執行，不建立排程。2026-10-29 02:33（UTC+8）父 SHA 5208415 的來源 build 346 檔可重現（reports/release-prep-continuous-goal-20261029-01）；`py -3.13 -B scripts/verify.py --run-dir reports/verify-continuous-goal-20261029-01 --timeout-seconds 180 --module test_package_candidate`：8/8、0 skip、source_unchanged，Job 自然退出／remaining 0。本次純文件，不提供新產品驗收。

## 2026-10-29 桌面來源缺口摘要

Tk 七來源頁新增只讀摘要，分列可讀且新鮮、拒讀、部分可讀、讀取失敗、過期、未知／尚無觀察及不適用；明示分類可重疊、均非安全判定。歷史成功不增加目前可讀計數，未出現的來源仍列未知。2026-10-29 02:28（UTC+8）`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-source-gaps-20261029-01 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop --module test_source_success_history`：75/75、0 skip、source_unchanged，含真 Tk 元件刷新摘要與 fixture，Job 自然退出 0／remaining 0。`reports/build-desktop-source-gaps-20261029-01`：當前工作樹 266 檔 hash 與受測來源相符、244 檔 Python 編譯成功。未採集／模型／ACK；人工版面與瀏覽器關卡仍待驗。

## 2026-10-29 桌面版七來源歷史成功時間

既有 Tk 桌面版沿用 DesktopController；快照從 source_status 只讀保存的 live 成功紀錄，七來源表格新增「最後成功時間（歷史）」。目前可見性／新鮮度獨立顯示；未知、無效、無時區及未來時間保持未知，零列不抹除歷史成功。未啟動監看、原生採集、模型或 ACK。

2026-10-29 02:25（UTC+8）：`py -3.13 -B scripts/verify.py --run-dir reports/verify-desktop-source-history-20261029-01 --timeout-seconds 180 --module test_gui --module test_gui_presenter --module test_desktop --module test_source_success_history`，74/74、0 skip、source_unchanged；包含真 Tk 元件配合 fixture、六情境表格驗證、保存來源讀前後 hash 不變，Job 自然退出 0／remaining 0。`reports/build-desktop-source-history-20261029-01/build-result.json`：對照同一受測來源 manifest，266 檔 hash 相符、244 Python 檔編譯成功；這是未提交工作樹的來源 build，非獨立 exe。桌面人工操作／縮放、Web 修訂／鍵盤／200% 及實機關卡仍待驗。

## 2026-10-29 500 行上限與瀏覽器工具排查

CLAUDE.md 已增加相對 HEAD 的未提交新增＋刪除 500 行硬上限，包含 staged／unstaged／本次 untracked，保留每 commit 約 200 行與每單元立即 push。開始時工作樹乾淨。本次僅修改規則與診斷記錄。

2026-10-29 01:34（UTC+8）：`py -3.13 -B scripts/package_candidate.py --root reports/release-prep-diff-limit-20261029-01 --commit 02725aa91ccac28e98688aa3b07d63d16e8d5020`，父版本來源 build 346 檔可重現，不含本次文件；`py -3.13 -B scripts/verify.py --run-dir reports/verify-diff-limit-20261029-01 --timeout-seconds 180 --module test_package_candidate`，8/8、0 skip、source_unchanged，Job 自然退出 0／remaining 0。文件另做 diff／本地連結與修改量檢查；無新增產品驗收。

瀏覽器存取排查已嘗試重建連線與直接選取內建瀏覽器；原生視窗 Raise／還原後成功讀取設定頁並觀察瀏覽器開關開啟，但操作中亦出現視窗尺寸變更及控制項快取失效，仍未證明瀏覽器工具已恢復。不得沿用失效識別操作或將未知根因歸咎未授權；未更動權限、未保存或提交畫面。原生 UI 狀態恢復不等於瀏覽器驗收通過。

## 2026-10-29 既有授權提醒與瀏覽器限制更正

CLAUDE.md 已記錄本專案既有讀改、fixture／合成測試、隔離瀏覽器驗收及指定開發分支 commit／push 授權；相同範圍不重複詢問。使用者設定畫面顯示瀏覽器已開啟，但工具回報停用，原因未確認；舊文的「Work 設定禁用」僅代表工具原文，不證明使用者未授權。UI／鍵盤／200% 仍待實測。

本次純文件變更；2026-10-29 01:23（UTC+8）來源 build：`py -3.13 -B scripts/package_candidate.py --root reports/release-prep-permission-reminder-20261029-01 --commit df5680825d518a94bfa447a82630a65b8470315e`，346 檔可重現。`py -3.13 -B scripts/verify.py --run-dir reports/verify-permission-reminder-20261029-01 --timeout-seconds 180 --module test_package_candidate`：8/8、0 skip、source_unchanged、Job 自然退出 0／remaining 0；此來源 build 為父版本，不含本次文件改動，不代表新增產品或瀏覽器驗收。

## 2026-10-28 可重跑修訂元件合成行為測試

新增專案測試直接執行實際修訂 renderer，合成 DOM 核對診斷變更與成員相符分列、部分診斷、重繪展開／摘要焦點、外部焦點不搶及切事件不沿用。使用既有 Node 與 Windows 私有 Job；缺少任一條件明示 skip、不下載。`reports/verify-revision-renderer-reusable-20261028-01` UTC 11:29:27：21/21、0 skip、244 AST、source_unchanged；受管 Job 自然 0／remaining 0／無強停。合成 DOM 非瀏覽器，不提供版面、200% 或真實鍵盤證據；Work 設定仍禁用本機瀏覽器。

## 2026-10-28 修訂收合摘要診斷狀態 WIP

修訂收合摘要現在同時顯示事件成員與診斷證據狀態，避免成員相符掩蓋診斷變更或缺失。`reports/verify-revision-diagnostic-summary-20261028-01` UTC 11:27:37：26/26、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-diagnostic-summary-dom-20261028-01` 實際 renderer 合成 DOM 五種診斷狀態通過，不是真瀏覽器；Work 設定仍禁用本機瀏覽器，UI 待驗。

## 2026-10-28 前版診斷結果語意 WIP

前版診斷 observed 顯示「已觀測，非安全判定」，partial 顯示「部分觀測，資料不完整」，不認得的結果顯示未知。`reports/verify-revision-diagnostic-result-20261028-01` UTC 11:26:05：28/28、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-diagnostic-result-dom-20261028-01` 直接執行實際 renderer 的三組 synthetic DOM，非瀏覽器；Work 設定仍禁用本機瀏覽器，UI 待驗。

## 2026-10-28 歷程預檢拒絕重複 JSON 欄位

標準輸入的備份 JSON 在所有物件層拒絕重複欄位，避免解析器對來源或完整性欄位採不同值；不改既有備份格式。`reports/verify-history-preview-duplicate-20261028-01` UTC 11:23:39：35/35、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 測頂層及巢狀重複、正常預檢、DB／pending／ACK 不變；此檢查不認證來源或證明可還原。

## 2026-10-28 歷程預檢實際 CLI 合成驗證

`reports/history-preview-real-cli-20261028-03` 使用既有 PowerShell 7 管線與真正 `EventGuard.cmd`／CLI、專用 synthetic event-source；預檢 exact_prefix、1 筆已存在且可還原性 unknown，無 ID 輸出。合成 DB SHA256 前後 57e5bb4065816cb369753eae5efb19c75ee52efcd91bb5b5968b2abf5914b8a8、pending 1／ACK 0／native 0／model 0；Job 自然退出 0／remaining 0／無強停。`...-02` 另驗直接 stdin 檔案 handle，亦自然 0；`...-01` 輔助程式退出原因無效而未保存原 Job 回條，殘留狀態未確認，不列為通過。均非真實資料還原或容量釋放。

## 2026-10-28 歷程預檢機器輸出未知狀態

JSON 明確將來源真實性、歷程是否完整、容量與可還原性標為 unknown，即使身分零衝突也不升格為可還原。`reports/verify-history-preview-unknown-20261028-01` UTC 11:18:26：10/10、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic CLI／前綴定向；無真實還原或容量釋放。

## 2026-10-28 歷程預檢順序比對

唯讀預檢增加目標與備份的完全前綴／分歧及筆數，避免僅看身分衝突誤認順序一致。`reports/verify-history-preview-order-20261028-01` UTC 11:14:43：13/13、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 核對短前綴及已分歧目標，與內部追加原件的接受／拒絕一致。完全前綴仍不證明來源真實性、備份是否涵蓋全部歷程、容量或可還原性；無真實還原或容量釋放。

## 2026-10-28 歷程完全前綴追加與分歧拒絕

`reports/verify-history-restore-prefix-20261028-01` UTC 11:10:51：15/15、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 實測先還原一筆後再追加尾段，順序不變、重開重播不增列；目標後續已有不同操作時整筆拒絕，DB／pending／ACK 不變。仍無使用者入口、來源認證、真實還原與容量釋放。

## 2026-10-28 歷程還原內部交易與容量回滾

EventStore 新增僅內部使用的追加還原交易：先預留 ACK 空間，再以實際 DB 使用量複核；容量不足整筆回滾。`reports/verify-history-restore-integration-20261028-01` UTC 11:08:45：42/42、0 skip、242 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 核對前後容量失敗、重開與操作重播、pending／ACK／來源不變。沒有 CLI／UI 還原入口、備份來源認證、真實還原或容量釋放；歷程追加不改目前處置狀態。

## 2026-10-28 歷程備份追加還原交易原件

新增未接產品入口的交易原件：僅在目標現存歷程與備份是完全一致前綴、scope 及每個事件 payload 身分吻合時追加缺失尾段，保留順序；不刪源、不改處置狀態、不 ACK、不自行 commit。savepoint 失敗回滾；呼叫端仍須獨立驗證來源真實性、ACK 保留及實際 bytes，才能決定交易。`reports/verify-history-restore-primitive-20261028-02` UTC 11:05:31：18/18、0 skip、241 AST、source_unchanged，Job 自然 0／remaining 0／無強停。synthetic 測空目標、重播、錯 scope／hash／未綁定／改事件、容量拒絕與中途失敗；這不等於已完成還原產品、容量釋放或授權真實資料操作。

## 2026-10-28 處置歷程備份唯讀預檢 CLI

新增 `events preview-history`，從標準輸入有界接收已保存備份，對指定 namespace／事件庫唯讀核對身分，只輸出彙總計數；交互式 stdin、超大內容、錯誤／未綁定 scope 拒絕。沒有還原、清理或 ACK，零衝突也不證明來源真實性、容量或可還原性。`reports/verify-history-preview-cli-20261028-02` UTC 11:01:42：38/38、0 skip、239 AST、source_unchanged；Job 自然 0／remaining 0／無強停。僅 synthetic；無損釋放容量尚未實作。

## 2026-10-28 調查保留政策明示 WIP

事件詳情說明：沒有前版的已 ACK 事件／調查可能依期限或容量輪替，有前版時錨點受保護但空間可能不足；同步修正 MAINTENANCE_GOAL 過時的修訂進度。`reports/verify-investigation-retention-copy-20261028-01` UTC 10:59:13：62/62、0 skip、238 AST、source_unchanged；Job 自然 0／remaining 0／無強停。靜態元件與保留策略合成回歸通過；Work 禁用本機瀏覽器，實際畫面仍未驗。

## 2026-10-28 修訂診斷 loopback GET

`reports/verify-revision-diagnostics-http-20261028-01` UTC 10:56:47：17/17、0 skip、238 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 真 loopback GET 核對同一前版事件成員相符時，診斷變更仍另回 changed；DB bytes／pending／ACK 不變，model 0。這不是真瀏覽器驗收。

## 2026-10-28 前版診斷證據呈現 WIP

前版畫面分開顯示診斷相符、變更、缺失、未綁定或未知，並顯示當時保存診斷摘要；不把事件成員雜湊相符解讀為診斷相符或主機安全。`reports/verify-revision-diagnostics-web-20261028-01` UTC 10:55:18：25/25、0 skip、238 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-diagnostics-dom-20261028-01` 實際 renderer 五種合成 DOM 狀態通過；非瀏覽器，Work 禁用本機瀏覽器，頁面驗收仍 WIP。

## 2026-10-28 前版調查的診斷證據狀態

事件詳情唯讀 API 為每個前版分別回報診斷 matched／changed／missing／not_bound；讀取方未提供診斷則 unknown，不以事件成員相符推定診斷相符。`reports/verify-revision-diagnostics-20261028-02` UTC 10:53:47：22/22、0 skip、238 AST、source_unchanged，Job 自然 0／remaining 0／無強停。synthetic 測保存診斷更改／移除、舊案未綁定與未提供來源；無重新採集、ACK 或模型。Web 尚未呈現此欄且瀏覽器受阻。

## 2026-10-28 修訂自動更新展開與焦點 WIP

同一事件自動重繪按穩定 revision_id 保留展開狀態與原摘要焦點；使用者焦點在外部時不搶焦點；切事件立即清除舊版 DOM，防止相同 revision_id 跨事件串用。`reports/verify-revision-refresh-20261028-02` UTC 10:51:46：29/29、0 skip、237 AST、source_unchanged、Job 自然 0／remaining 0／無強停。`reports/revision-refresh-dom-fixture-20261028-01` 實際 renderer 的三組合成 DOM 驗證插入新版後保留、外部焦點、切事件不沿用；不是真瀏覽器，Work 設定仍禁用本機瀏覽器，UI 未驗收。

## 2026-10-28 修訂穩定識別前置

事件詳情修訂資料加上有界 SQLite revision_id，供 UI 重繪辨識同一版本；不代表操作者或認證身分。`reports/verify-revision-stable-id-20261028-01` UTC 10:49:46：34/34、0 skip、237 AST、source_unchanged，Job 自然 0／remaining 0／無強停。synthetic 核對重讀識別穩定、舊庫及資料不變。UI 展開／焦點保留尚未接線，瀏覽器仍受 Work 設定阻擋。

## 2026-10-28 修訂呈現合成 DOM 補充

`reports/revision-web-dom-fixture-20261028-01/run.js` 對目前實際 renderInvestigationRevisions 執行三組合成 DOM fixture：未知／無歷程／缺口與容量滿載，Node exit 0；驗證中文缺口與文字輸出。此非瀏覽器、無版面或鍵盤證據，不改變 Work 設定阻擋及 UI WIP。

## 2026-10-28 先前版本缺口中文說明 WIP

先前版本與最新快照共用固定缺口中文標籤，未知代碼仍按不可信文字顯示；`reports/verify-investigation-revision-gap-labels-20261028-02` UTC 10:44:47，43/43、0 skip、237 AST、source_unchanged，Job 自然 0／remaining 0／無強停。`reports/revision-web-javascript-check-20261028-02` 本機 Node `--check` 語法通過，不是 JS 行為／瀏覽器驗收；Work 禁用本機瀏覽器，修訂畫面仍 WIP。完整 fixture 回歸僅針對前版 d0faaf1。

## 2026-10-28 案件修訂完整合成回歸

產品來源 `d0faaf1b156d7344e0571696eebc5c728e9dcf62`：`reports/verify-full-revision-20261028-01` UTC 10:41:02，1715 執行／1712 通過／3 跳過／0 失敗錯誤，237 AST、source_unchanged；2 skip 為 symlink 不可建立、1 skip 為 notification_icon_unavailable。Job 自然 0／remaining 0／無強停，無 native 掃描／模型。`reports/release-prep-revision-20261028-01` 來源 commit 339 檔、兩 ZIP 可重現 SHA256 887d7e8b758e455bcb68fb16bacba162acd0ad002660dbf43b3f0ca47c71a299；僅候選來源封裝，非發布。瀏覽器 Work 設定禁用，修訂 UI 仍待真瀏覽器驗收；容量無損釋放、200%／人類／原生／24h／重啟／桌面喚醒各自未達。

## 2026-10-28 調查容量不足錯誤回報

調查更新遇容量不足時 loopback API 明確回報 investigation_capacity，Web 顯示容量不足與原調查／事件未變更。`reports/verify-investigation-revision-capacity-error-20261028-02` UTC 10:29:30：49/49、0 skip、237 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成 HTTP 注入容量錯誤、核對回碼與 DB 不變；交易滿載回滾見先前 integration 證據。Web JS 僅靜態測，因 Work 禁用本機瀏覽器尚未驗實際顯示。

## 2026-10-28 修訂全域上限與並行合成測試

`reports/verify-investigation-revision-concurrency-20261028-02` UTC 10:26:43：17/17、0 skip、237 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成記憶體 SQLite 實際塞入 256 版本並拒絕第 257 筆；兩執行緒同事件更新後前版與兩個新快照均可讀、pending 2／ACK 0。全域滿載只測儲存原件，尚未驗整體產品流量或跨程序壓力；瀏覽器與容量恢復仍未完成。

## 2026-10-28 保護有修訂的事件錨點

自動期限、筆數與空間輪替排除有已保存修訂的 ACK 事件，避免原事件和最新案件被清除後版本無法回看；其他 ACK 事件沿用既有政策。`reports/verify-investigation-revision-retention-20261028-03` UTC 10:24:57：61/61、0 skip、236 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成測試涵蓋過期、空間輪替與筆數壓力，原案／修訂／pending 保留。保留錨點可能使容量先滿，尚無安全歸檔／釋放方案；不可自行刪除。瀏覽器 WIP 仍未驗。

## 2026-10-28 調查修訂 Web 呈現 WIP（瀏覽器待驗）

事件詳情新增前版展開、觀測、缺口、證據未知與容量說明；`reports/verify-investigation-revision-web-20261028-01` UTC 10:21:28：46/46、0 skip、236 AST、source_unchanged，僅契約／合成測試，非瀏覽器驗收。`reports/investigation-revision-browser-20261028-01` 隔離合成伺服器已準備，但 IAB 回報 Local browser use is disabled in Work settings，沒有實際操作／渲染證據；Job 合作退出 0／remaining 0／無強停、0 POST／native／model，DB SHA256 前後 9565ba61b68544acb447b85f98c3ce7f0473e6007a0c7ae663f45b125a1355ee。此切片是 WIP，須恢復允許的瀏覽器後依規格驗收，不能標 UI DONE。

## 2026-10-28 事件詳情修訂唯讀 API

既有事件詳情 GET 增加有界 `investigation_revisions`，包含已保存前版與 evidence_status；舊庫未記錄、損壞／成員缺失為 unknown。`reports/verify-investigation-revision-api-20261028-01` UTC 10:19:28：67/67、0 skip、236 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成 loopback GET 與 catalog 一致、來源 DB hash 不變、model 0；尚未接 Web 呈現，也未驗過期 anchor 回看、全域滿載或併發。

## 2026-10-28 案件修訂唯讀核心

有界唯讀交易核對快照與事件身分、hash；舊庫無表明示未記錄，此前歷史 unknown；成員缺失／變更為 unknown，不修改來源。`reports/verify-investigation-revision-read-20261028-01` UTC 10:17:54：34/34、0 skip、236 AST、source_unchanged，Job 自然 0／remaining 0／無強停。只完成讀取核心，尚未接 API／Web；hash 非認證，anchor 過期後的回看仍未實作。

## 2026-10-28 案件修訂原子保存

明確更新已保存調查時，在同一 SQLite 交易先驗並保存上一版，再寫最新案；相同快照重送不新增版本。容量不足或舊快照損壞直接失敗，回滾保留先前資料與 pending／ACK。`reports/verify-investigation-revision-integration-20261028-03` UTC 10:16:28：56/56、0 skip、234 AST、source_unchanged；Job 自然 0／remaining 0／無強停，均 synthetic。每事件 16、全域 256 上限後不自動清理；版本讀取／瀏覽器、全域滿載和併發尚未驗。已有舊版之前的歷史不能重建；到期 anchor 的歷史保留與回看方案仍需處理。

## 2026-10-28 案件修訂交易儲存原件

新增受呼叫端交易控制的有界 append 原件；不自行 commit 或淘汰，容量／位元組不足拒絕，回滾可撤銷建表與插入。`reports/verify-investigation-revision-store-20261028-01` UTC 10:13:48：29/29、0 skip、233 AST、source_unchanged；Job 自然 0／remaining 0／無強停。尚未接產品寫入、核實實際 DB 成長、讀取或 UI；此原件不代表能回看調查。

## 2026-10-28 案件修訂有界契約前置

純契約定義每事件 16、全域 256 上限與 64 KiB case，綁定錨定事件／內容 hash、實際保存時間；相容 1.0／1.1 case，拒絕偽造狀態、身分及超限。不寫資料、不補造歷史，也未提供使用者功能。`reports/verify-investigation-revision-contract-20261028-02` UTC 09:53:30：33/33、0 skip、231 AST、source_unchanged、Job 自然 0／remaining 0／無強停。交易保存、讀取、瀏覽器及容量故障驗收尚未實作；完整清單見 MAINTENANCE_GOAL。指定競品研究任務原目標已完成，後續市場比較未視為已實測。當前 Codex 工程目標達使用額度限制，保存後不承諾自動續跑。

## 2026-10-28 調查更新的覆蓋提示

事件詳情在建立／更新按鈕前明示僅保留最新快照、更新取代舊版且不能回看。`reports/verify-investigation-retention-warning-20261028-03` UTC 09:51:31：35/35、0 skip、229 AST、source_unchanged、Job 自然 0／remaining 0／無強停。`reports/investigation-retention-ui-20261028-01` 隔離真瀏覽器打開合成事件詳情，提示與按鈕可見且順序正確；SQLite SHA256 前後 ED790B81…B697E0、0 POST／native／model，Job 自然 0。此提示未提供版本保存。

200% 縮放嘗試見 `reports/ux-zoom-20261028-01`：IAB 快捷鍵後 CSS viewport／devicePixelRatio 未改變，未達驗收，無法用窄視窗代稱真縮放；合成 DB hash 不變、0 POST／native／model，Job 自然 0。

## 2026-10-28 歷程備份身分唯讀預檢核心

新增未接操作入口的唯讀預檢：核對備份完整性與 namespace、事件實際 payload hash、未綁定記錄、缺事件及 operation 衝突，只輸出計數，不執行或授權還原。`reports/verify-history-backup-preview-20261028-01`：19/19、0 skip、229 AST、source_unchanged、Job 自然 0／remaining 0／無強停；synthetic 驗證相同、缺少、衝突、範圍錯誤、舊格式 unknown、來源不改。這不檢查容量、歷程順序、來源真實性或能否恢復；完整還原及釋放容量仍未實作。

## 2026-10-28 歷程備份 CLI 與來源範圍

明確執行 `events backup-history --namespace test|live --name history-backup-<名稱>.json` 才會寫入 reports；讀取使用 query-only，輸出僅為摘要，來源不刪除、不 ACK。快照 1.1 綁定 namespace，1.0 回報 unknown；SHA256 非簽章。`reports/verify-history-backup-cli-20261028-03`：42/42、0 skip、228 AST、source_unchanged、Job 自然退出 0／remaining 0／無強停，僅 synthetic。實際 junction、斷電後目錄項持久性、完整 DB 備份、還原與容量釋放尚未驗證。下一步建立不修改資料的還原前檢查；不得刪除歷程。

## 2026-10-28 歷程備份不覆寫落盤核心

新增明確呼叫的 reports 本機備份寫入器：先驗快照、檔案 fsync、hard-link 不覆寫、重讀及 hash／schema 再驗，保留原資料；目錄項持久性未確認，hash 非簽章。遇不支援 hard link、既有目的地或無效內容直接失敗；尚未接 CLI／UI，也未實作還原、跨檔重播或釋放容量。

`reports/verify-history-backup-file-20261028-02` UTC 09:38:15、25/25、0 skip、228 AST、source_unchanged、Job 自然 0／remaining 0／無強停；合成檔測既有檔不覆寫、錯誤清理僅自建暫存、source DB／pending／ACK 不變及模擬 junction 拒絕。真 junction／停電後目錄 durability 未驗；工作樹來源 ZIP 含兩新檔。

## 2026-10-28 歷程快照驗證核心

新增有界快照完整性驗證，核對 schema、事件／操作識別、狀態、來源、時間、重複、256／4096 上限、長度與 canonical SHA256；輸出快照也先驗證。SHA256 不是簽章，不證明操作者身分或防竄改。`reports/verify-history-backup-validation-20261028-02` UTC 09:36:09、20/20、0 skip、226 AST、source_unchanged、Job 自然 0／remaining 0／無強停。仍僅記憶體，沒有持久檔、還原或容量釋放；下一步不覆寫落盤。工作樹來源 ZIP 自檢。

## 2026-10-28 歷程無損恢復前置：唯讀快照

新增有界 query-only SQLite 快照核心，保留操作識別、前後狀態、來源及已綁定／未綁定 hash，計算 canonical SHA256；拒絕損壞資料，不修補或改寫來源。這只是記憶體中的歷程 payload，含敏感 metadata，尚未接 CLI／檔案保存、全庫備份、還原或容量釋放，不能當作已完成恢復或防竄改證據。

`reports/verify-history-backup-payload-20261028-01` UTC 09:33:28、45/45、0 skip、226 AST、source_unchanged、Job 自然 0／remaining 0／無強停；合成 SQLite 核對唯讀交易、舊表、不綁定保留、hash、損壞拒絕及 pending／ACK 未變。工作樹 ZIP 含兩個新檔。下一步安全落盤與驗證，不能自行刪除或宣稱已釋放容量。

## 2026-10-28 GUI／歷程整合完整回歸

來源 commit `7de39b3cec4c99308783afb3dc7f0c6240e47b25`：`py -3.13 -B scripts/verify.py --run-dir reports/verify-full-gui-history-20261028-01 --timeout-seconds 1800`，UTC 09:23:05–09:31:17、1670 run／1667 pass／3 skip、0 fail/error、224 AST、source_unchanged；兩項 symlink 建立不可用、一項 notification_icon_unavailable。原 Job 自然 0／remaining 0／無強停／逐測殘留 0；native scan／model 0。synthetic／fixture 全回歸不等於原生覆蓋或真 agent 收件。

`reports/release-prep-gui-history-20261028-01` 精確 7de39b3 候選 326 檔、兩 ZIP 一致；文件 checkpoint 另以 `reports/verify-full-checkpoint-docs-20261028-01` 19/19、0 skip 及工作樹 ZIP 自檢。全庫／byte 歷程滿載無損恢復、人類 UX／200% zoom、真機 24h／重啟／喚醒仍未完成。

## 2026-10-28 處置歷程單事件容量局部恢復

每事件上限從 32 調整為 256，全庫仍 4096 且受既有 byte／ACK reserve 限制；不刪或覆寫舊歷程。`reports/gui-history-capacity-recovery-20261028-01` 合成真瀏覽器驗舊版 32 筆滿載後可完成新處置、舊 32 列逐筆相同、32 筆未綁定仍未知、pending／receipt null；`-02` 驗新 256 筆滿載明示拒絕、狀態與 pending 不變。兩 Job 自然 0／remaining 0／無強停、各 1 合成 POST、native／model 0。

`reports/verify-history-capacity-recovery-20261028-02` UTC 09:20:47、72/72、0 skip、224 AST、source_unchanged、Job 自然退出；含 256 單事件與 4096 全庫滿載的資料保全。這是提高有界容量、恢復舊 32 限制的部分改善，不是永久恢復：256／4096 或 byte 滿載仍拒絕新處置，尚無不丟失證據的全庫恢復。工作樹 326 檔 ZIP 自檢。

## 2026-10-28 事件詳情切換安全修正

切換到不同事件時立即隱藏舊詳情，避免新事件還在載入時，畫面顯示舊事件卻操作新事件；同事件輪詢仍保留詳情。`reports/gui-detail-switch-safety-20261028-01` 合成瀏覽器延遲第二事件，確認舊詳情隱藏／可見處置按鈕 0，放行後顯示第二事件及其 delivery；0 POST／native／model、Job 自然 0／remaining 0／無強停。`reports/verify-detail-switch-safety-20261028-01` UTC 09:17:08、49/49、0 skip、224 AST、source_unchanged、Job 自然退出；來源工作樹 ZIP 自檢。歷程容量恢復仍未完成。

## 2026-10-28 處置歷程事件身分綁定

發現事件 ID 可在保留期後重用，舊歷程若只靠 ID 可能誤歸屬；新紀錄與重播綁定驗證過的 payload hash。舊表未綁定資料不自動回填，讀取與重播顯示未知／衝突；新寫入時同交易惰性加欄、保留舊列，不以目前內容倒推舊身分。

`reports/verify-history-identity-20261028-02` UTC 09:14:14、96/96、0 skip、224 AST、source_unchanged、Job 自然 0／remaining 0／無強停；合成測試含內容改變、舊表遷移、重播衝突、回滾與 pending。`reports/gui-history-identity-20261028-01` 合成真瀏覽器核對相符／變更／未綁定，讀取前後 SQLite hash 一致、0 POST／native／model、Job 自然退出。工作樹 326 檔 ZIP 來源自檢，非 commit 候選。容量恢復仍未完成。

## 2026-10-28 六情境合成前後觀察

固定 ad1f127／338cdc5 完成六種 synthetic 自動化觀察：新增嚴重清單 3→1 操作；拒讀 1→0 操作；最後成功舊版卡片不可見、新版可見；保存關聯、診斷缺口及 handled／pending 各自 1→1 操作。舊版缺口顯示代碼，新版有中文；各案例未觀察錯誤結果或誤判安全。各次自動化耗時見 `reports/ux-compare-20261028-01/comparison.json` 與 `-02/comparison.json`，非人類測量；舊版錨定列以合成 API 定位，非使用者尋找時間。

兩版本第二 fixture hash 前後一致、0 POST／native／model、Job 自然 0／remaining 0／無強停；`reports/verify-ux-six-synthetic-20261028-01` UTC 09:10:33、46/46、0 skip、224 AST、Job 自然退出。僅完成合成觀察；人類／200% zoom／合法競品對照及歷程容量恢復仍未完成。來源 build 為工作樹 ZIP 自檢。

## 2026-10-28 合成 GUI 前後比較（部分）

固定 ad1f127 與 338cdc5 來源包、相同 synthetic SQLite／來源，實際瀏覽器各量一次：篩選新增嚴重事件由 3 操作／516ms 變 1 操作／293ms，兩者均顯示 2 件與嚴重首列；查看拒讀的最後成功時間，舊卡 1 操作／434ms 無法完成，新卡 1 操作／398ms 可見且目前仍拒讀。兩案例未觀察錯誤結果或誤判安全；時間為自動化單次 wall time，不是人類速度或統計結論。

`reports/ux-compare-20261028-01` SQLite hash 前後一致，0 POST／native／model，兩 Job 自然 0／remaining 0／無強停；新版來源頁 800／1280px 無橫向溢位。六情境、人類參與者、200% zoom 與合法競品環境尚未測，P2-UX-001 僅部分完成。`reports/verify-ux-comparison-20261028-01` 26/26、0 skip、224 AST、Job 自然退出；工作樹來源 ZIP 自檢。處置歷程容量恢復仍待做。

## 2026-10-28 P2-HISTORY-001C 處置歷程 Web

事件詳情顯示時間、前後狀態、無變更請求、來源通道、此前未知及數量容量；明示來源不是已驗證操作者、處置不是 ACK。損壞歷程顯示無法確認，不以數量未滿推定剩餘位元組。

`reports/gui-handling-history-20261028-01` 合成真瀏覽器核對正常／無紀錄／損壞／32 筆滿載，SQLite hash 讀取前後一致、4 pending／0 receipt，0 POST／native／model、Job 自然退出。`reports/verify-gui-handling-history-20261028-01` UTC 09:03:29、47/47、0 skip、224 AST、source_unchanged、Job 自然 0／remaining 0／無強停。工作樹 326 檔 ZIP 自檢，非 commit 候選。容量恢復仍未實作，滿載拒絕新處置；後續需另定不損失重要證據的恢復方式及操作量測。

## 2026-10-28 P2-HISTORY-001C 唯讀後端

事件詳情新增有界 `handling_history`：包含狀態轉換、無變更請求、時間與來源；不暴露操作識別、不宣稱操作者身分。舊 DB 顯示未記錄且此前未知；損壞／超限顯示 unknown，不在讀取時建表或修補；數量容量不代表剩餘位元組。

`reports/verify-history-read-20261028-01` UTC 09:00:59、53/53、0 skip、224 AST、source_unchanged、原 Job 自然 0／remaining 0／無強停；合成 SQLite 檢查前後 bytes、pending／ACK、舊 schema、無變更及損壞。工作樹 326 檔來源 ZIP 自檢，非 commit 候選。Web 顯示與容量恢復尚未完成，下一步 UI。

## 2026-10-28 P2-HISTORY-001B 原子寫入已接線

事件處置狀態與有界操作紀錄同 SQLite 交易；同 ID 跨 Application 重建可重播、不回退後來狀態，衝突及容量不足明示；滿載仍可重播，寫入前後保留 ACK 空間。無變更請求也占冪等槽，32／4096 滿載會阻擋新操作，恢復方式尚未提供；舊歷程不能補造，畫面尚未顯示歷程。

`reports/verify-history-integration-20261028-05` UTC 08:58:18：99/99、0 skip；精簡重複測試後 `reports/verify-history-integration-20261028-07` 7/7、0 skip；223 AST、source_unchanged、Job 自然 0／remaining 0／無強停。`reports/history-integration-20261028-03`／`-04` 最終來源合成瀏覽器分別驗成功及容量拒絕，均保留 pending／無 ACK、Job 自然退出；POST 為明示合成處置，native／model 0。工作樹 325 檔來源 ZIP 自檢，非 commit 候選。下一步 001C 唯讀歷程與 UI。

## 2026-10-28 P2-HISTORY-001B 交易核心（尚未接產品）

新增 SQLite transaction helper：要求由呼叫方開交易、延遲建表、同操作識別重播／衝突、無變更請求也保存有界冪等識別但不算狀態轉換；以 32／4096 筆與呼叫方提供的 ACK 預留後可用位元組拒絕滿載，不自行 commit 或 ACK。這是獨立核心，未接 EventStore／Application／Web，尚不能回看或持久記錄實際處置。

`reports/verify-history-transaction-core-20261028-01` UTC 08:46:57、57/57、0 skip、222 AST、source_unchanged，Job 自然 0／remaining 0／無強停。synthetic SQLite 測交易回滾、相同 ID 重播、衝突、無變更、容量拒絕及 pending／receipt 未變；不代表產品已整合。工作樹來源 ZIP build 包含兩個新檔，非 commit 候選。下一步把同一操作識別及來源傳入真寫入交易，測故障回滾與重啟。

## 2026-10-28 歷程契約換行修正

前一 checkpoint 的 staged `git diff --check` 對新檔 CRLF 報尾隨空白，但 PowerShell 未自動停止後續 commit；該 checkpoint 已推送，不改寫歷史。本單元將兩個新檔統一 LF，內容語意不變；重新 diff-check 無輸出。`reports/verify-history-line-endings-20261028-01` UTC 08:45:06、27/27、0 skip、220 AST、source_unchanged、Job 自然退出。來源 build 為工作樹 ZIP 自檢。後續提交改成獨立檢查退出碼，再執行 commit。下一步 P2-HISTORY-001B。

## 2026-10-28 P2-HISTORY-001A 處置歷程純契約

新增純驗證：歷程只接受具界限的事件／操作識別、狀態轉換、來源與有限時間；單事件 32／全庫 4096 筆預定上限，滿載拒絕新紀錄。來源不是已驗證使用者身分，舊資料不能憑最新狀態補造歷程。此切片不建立資料表、不接寫入或 UI；現有事件處置行為未改，不能稱歷程功能完成。

`reports/verify-disposition-history-contract-20261028-02` UTC 08:43:52：58/58、0 skip、220 AST、source_unchanged，原 Job 自然 0／remaining 0／無強停。工作樹 build 包含兩個新檔；非 commit 綁定候選。下一步 001B 在同交易接入、處理重試識別、容量／ACK 預留及回滾；完成前不得宣稱可回看歷程。

## 2026-10-28 P1-INVEST-004B 逐觀測理由與缺口

已保存時間線每筆觀測旁顯示錨定或既有同主機／來源／穩定身分關聯依據、對應缺口，以及原事件缺失／變更的未知；診斷缺口有中文說明。未改關聯算法或推定程序樹／攻擊鏈。

`reports/gui-investigation-reasons-20261028-02` 真瀏覽器 synthetic 案件：錨定列顯示截斷與未保存診斷，變更成員列顯示未知；PID 重用、異來源、缺身分候選未進時間線，16 成員，SQLite hash 讀前後不變。兩輪 Job 自然 0／remaining 0／無強停，0 POST／native／model。定向 `reports/verify-gui-investigation-reasons-20261028-01` UTC 08:41:23、63/63、0 skip、218 AST、source_unchanged、Job 自然退出。工作樹 320 檔 ZIP 來源自檢，不是 commit 候選。下一步依佇列評估有界歷程與合成 UX 驗收。

## 2026-10-28 P1-INVEST-004A 保存調查摘要

Web 已保存調查增加快照概況：錨定事件、保存時間、成員 hash 狀態、快照新鮮度、保存成員／候選／缺口數及截斷；未知與過期明示，不判安全或因果。既有關聯與資料儲存規則未改。

`reports/gui-investigation-summary-20261028-02` 真瀏覽器合成案例：16 成員／26 候選／截斷、過期及缺口可見，重新開啟內容一致；改變獨立 synthetic 成員後證據變未知，該狀態讀取前後 SQLite SHA256 不變。Job 自然 0／remaining 0／無強停，0 POST／native／model。定向 `reports/verify-gui-investigation-summary-20261028-01` UTC 08:38:09、62/62、0 skip、218 AST、source_unchanged、Job 自然退出。來源 build 是工作樹 320 檔 ZIP 自檢，非 commit 候選。下一步 P1-INVEST-004B，關聯理由與缺口靠近觀測。

## 2026-10-28 修正網址分頁 regex 的 Python 載入警告

P1-INVEST-004A 的合成 fixture 建立時發現 Web 內嵌 JavaScript `\d` 讓 Python 3.13 發出 SyntaxWarning；改為等價 `[0-9]`，頁碼語意不變。`py -3.13 -B -W error::SyntaxWarning -c "import sys; sys.path.insert(0, 'src'); import eventguard.web"` 通過；`reports/verify-gui-url-regex-20261028-01` UTC 08:35:31、33/33、0 skip、218 AST、Job 自然退出。工作樹來源 ZIP build 320 檔自檢，非 commit 候選。下一步接續已保存調查摘要；尚未驗收。

## 2026-10-28 P1-GUI-003B 補驗完成

`reports/gui-detail-edge-20261028-01` 使用隔離 synthetic 事件與真瀏覽器：延遲 high 清單回覆時切到 critical，放行後畫面仍是 critical 2 筆；在獨立 synthetic SQLite 將所選事件設 handled（無 ACK），使它離開 new 清單，返回焦點正確落在篩選按鈕。原 Job 自然 0／remaining 0／無強停、0 POST／native／model。定向 `reports/verify-gui-detail-edge-20261028-01`：UTC 08:32:43，33/33、0 skip、218 AST、source_unchanged、Job 自然退出。工作樹來源 ZIP build 320 檔 hash 自檢；非 commit 候選。下一步 P1-INVEST-004A。

## 2026-10-28 P1-GUI-003B 詳情返回與延遲回覆

事件詳情新增鍵盤可用的返回清單按鈕，回到原事件焦點，清單週期重繪保留事件按鈕焦點；失去原列時回篩選按鈕。切換／返回使在途詳情與 delivery 回覆失效，避免舊事件證據覆蓋新選取。

`reports/gui-detail-return-20261028-01` 合成真瀏覽器：高事件第二頁開啟／返回原事件與頁碼；五秒週期後焦點不變；延遲第一事件詳情並切換第二事件，放行舊回覆後詳情與 delivery 均為第二事件，返回焦點正確。Job 自然 0／remaining 0／無強停，0 POST／native／model。`reports/verify-gui-detail-return-20261028-01` UTC 08:30:12、61/61、0 skip、218 AST、source_unchanged、Job 自然退出。工作樹來源 build 320 檔 ZIP 自檢，非 commit 候選。慢事件清單回覆及原列消失後焦點的瀏覽器故障注入尚未驗證；下一步先補驗再做 P1-INVEST-004。

## 2026-10-28 P1-GUI-003A 網址篩選與頁碼

Web 網址只保存嚴重度／來源／處置狀態的既有列舉及 0–10000 頁碼，不含事件內容；重新載入、返回／前進可恢復。無效／重複／未知／超限參數顯示固定錯誤並不顯示事件；重新選取可恢復。篩選或頁碼變化使在途舊事件清單回覆失效。根路由現在提供固定頁面給含查詢網址，仍驗 Host／長度，不反射 query。

合成真瀏覽器核對高 55 件第二頁、reload／back／forward、嚴重入口、四種無效網址和三篩選恢復。`reports/gui-url-filters-20261028-01` 首測重現根路由 route_not_found，修正後 `-02` 通過；兩個原 Job 自然 0／remaining 0／無強停，無 POST／native／model。定向 `reports/verify-gui-url-filters-20261028-01` 31/32：舊靜態測試切段含新 helper，修正後 `-02` 32/32、0 skip、218 AST、source_unchanged、原 Job 自然退出。另擴充路由／控制測試 `reports/verify-gui-url-filters-20261028-03`：68 run、67 pass、1 skip（notification_icon_unavailable）、0 fail/error，218 AST，Job 自然退出。來源 build 為工作樹 320 檔 ZIP 自檢，不是 commit 候選。慢事件回覆與詳情／焦點仍待 003B。

## 2026-10-28 P1-GUI-002B 新增事件入口

高／嚴重事件分開顯示可點按數字，進入對應嚴重度＋新增狀態，清除來源篩選與詳情、回第一頁；兩次獨立計數明示時間可能不同。相同數字不重建按鈕以保留焦點。

合成真瀏覽器測試：55 高、2 嚴重、1 資訊；高首頁 50／次頁 5，從次頁點嚴重得到 2 筆、首列及篩選一致，跨頁鍵盤回高首頁正確。`reports/gui-high-links-20261028-01` Job 自然 0／remaining 0／無強停，0 POST／native／model。`reports/verify-gui-high-links-20261028-01`：UTC 08:21:48，30/30、0 skip、218 AST、source_unchanged、Job 自然退出。工作樹來源 build 320 檔 ZIP／逐檔 hash 自檢，非 commit 候選。下一步 P1-GUI-003A。

## 2026-10-28 P1-GUI-002A 慢回覆切頁修正

合成瀏覽器重現切頁後舊成功回覆暫時覆蓋來源失敗；切頁現在使舊來源回覆失效，忙碌期間的刷新合併排隊，完成後重新讀取。修正後同情境顯示未確認，恢復正常後能顯示觀測成功；不推定主機安全。

`reports/gui-source-gap-race-20261028-01`／`-02` 保存修正前後合成 Job 回條，皆自然退出／remaining 0／無強停。`reports/verify-gui-source-gap-race-20261028-01`：UTC 08:19:20，41/41、0 skip、218 AST、source_unchanged、Job 自然退出。工作樹來源 build 320 檔 ZIP 自檢，非 commit 綁定正式候選包。下一步 P1-GUI-002B。

## 2026-10-28 P1-GUI-002A 事件頁來源缺口摘要

事件頁只讀 `/api/sources`，要求七個不同的已知來源；非 ok／非 fresh 列出缺口，缺項、重複、空回覆或讀取錯誤顯示未確認，不宣稱主機安全。來源讀取失敗不清除事件。刷新由既有 busy 串行；尚未注入慢回覆驗證切頁競態。

`reports/verify-gui-source-gap-20261028-01`：UTC 08:15:39，41/41、0 skip、218 AST、source_unchanged，Job 自然退出／剩餘 0／無強停。隔離瀏覽器在合成 fixture 核對七來源成功、拒讀、過期、缺項、重複、空與錯誤，錯誤時合成 pending 事件仍可見；`reports/gui-source-gap-20261028-01` 原 Job 自然 0／remaining 0／無強停，0 POST／native／model。測試不代表真主機覆蓋。

來源 build 是工作樹 320 檔 ZIP／逐檔 hash 自檢，非提交 SHA 的正式候選包。下一步補慢回覆切頁驗證並做 P1-GUI-002B。

## 2026-10-28 P1-GUI-001 七來源卡片

Web 卡片分列最後採集、原結果、目前狀態、最後成功、新鮮度與觀測列數；缺失／無效／未來成功時間顯示未知，拒讀或過期不被歷史成功覆蓋。合成零列不表示安全；來源文字以 textContent 顯示。

定向：`py -3.13 -B scripts/verify.py --run-dir reports/verify-gui-source-cards-20261028-02 --timeout-seconds 180 --module test_source_success_history --module test_application_ui_state`，UTC 08:11:37，18/18、0 skip、218 AST、source_unchanged，Job 自然退出／剩餘 0／無強停。三次 HTTP GET 比較資料檔 bytes 與合成 pending／stats 未變。

未提交工作樹來源 build：`reports/gui-source-cards-20261028-01/working-tree-build.zip`，320 個已追蹤檔案逐檔 hash／ZIP 自檢；含本切片，並非既有以 commit 建置的正式候選包。

隔離真瀏覽器實際核對 `#source-cards` 七卡：拒讀、過期、未知、無效及未來時間、零列與 HTML 樣式文字；800px 無水平溢位、Enter 切換頁面，合成 worker 退出 0／剩餘 0／無強停。證據 `reports/gui-source-cards-20261028-01`；來源 build 與限制見 EVIDENCE。非實機採集或使用者研究；後續 P1-GUI-002A。

## 2026-10-28 競品研究與工程開工規格完成（未實作產品）

[公開研究](docs/research/competitor-gui/README.md) 與 [工程規格](docs/research/competitor-gui/ENGINEERING_PLAN.md) 已連回 MAINTENANCE_GOAL。核對現有 Web／Tk、API、事件／調查／活動資料與測試後，第一切片定為 P1-GUI-001：補 Web 七來源卡片的最後成功／新鮮度；API 已具備、畫面尚缺。六驗收案例、觸點、後續排序及原生／偵測／真環境前置均已列明，全部產品切片仍未實作。正式主控台未測，不能稱優於競品。

第一單元 f1ed1e07f884e961e96aaffa3cbf9cf51544578d：`docs(research): verify competitor GUI and GitHub evidence [skip ci]`，+113/-0；普通 push origin/feat/local-codex-acceptance 後 ls-remote 同 SHA、ahead/behind 0/0，status／shortstat 無輸出。第二單元開始亦確認乾淨，僅改本研究的規格／既有現況文件。

本單元來源 build：`py -3.13 -B scripts/package_candidate.py --root reports/release-prep-gui-research-20261028-02 --commit f1ed1e07f884e961e96aaffa3cbf9cf51544578d`，319 檔、兩 ZIP 一致。定向：`py -3.13 -B scripts/verify.py --run-dir reports/verify-gui-research-20261028-02 --timeout-seconds 180 --module test_source_success_history --module test_application_ui_state --module test_activity`；台北 15:47:52–15:47:55，29/29、0 fail/error/skip、218 AST、source_unchanged、原 Job 自然 0／remaining 0／無強停。與先前 74 項有重疊，不相加；只驗既有來源，不是提案或新 GUI 的實作驗收。

文件／連結、240 來源 hash 與本次保存結果在 reports/research-gui-20261028-01；不提交 runtime／截圖。本輪只做兩個單一目的文件 checkpoint；推送不等於 CI／發布，未推 main/tag。研究目標完成後交由後續工程從 G01 接續，不在此研究任務擴張產品修改。

## 2026-10-28 競品 GUI／GitHub 研究：公開證據完成，工程切片待落地

從乾淨 f86254bb0393b606b1202b370efa18b35f649e8e／origin 同 SHA 接續；原聊天僅等待研究，未觀察到其他寫入。新增 [競品研究](docs/research/competitor-gui/README.md)，核對兩家官方展示、目前文件與四倉庫固定 SHA／授權／封存。修正 Lightweight Console：固定目錄只有佔位 README，不能稱有 GUI 實作。正式主控台、兩家偵測／回應成效與同環境比較未測。

來源 build：`py -3.13 -B scripts/package_candidate.py --root reports/release-prep-gui-research-20261028-01 --commit f86254bb0393b606b1202b370efa18b35f649e8e`，318 檔、兩 ZIP 一致、原 Git Job 自然退出。定向：`py -3.13 -B scripts/verify.py --run-dir reports/verify-gui-research-20261028-01 --timeout-seconds 180 --module test_event_catalog --module test_event_investigation --module test_investigation_diagnostics --module test_source_success_history --module test_application_ui_state --module test_package_candidate`；台北 15:33:12–15:33:20，74/74、0 fail/error/skip、218 AST、source_unchanged、原 Job 自然 0／remaining 0／無強停。這是既有來源驗證，未包含新文件的候選包，也不代表新版 GUI 實測。

首次 build 使用不符合 `release-prep-` 限制的目錄而受阻，未建立輸出或啟動 Git child；改合法新目錄後成功，未改 builder 或繞過閘道。文件連結／差異與來源紀錄留 reports/research-gui-20261028-01；runtime／圖片不提交。下一單元是現有實作缺口、優先順序及第一個可直接開工的小切片；本任務不實作產品、不連帳戶、不啟模型／native／排程。

## 2026-10-28 乾淨工作區與原子提交規則（最新）

本單元只落實最新Git工作規則：AGENTS／CLAUDE明定單一目的、約200行先拆、提交前build與相關測試全過、type(scope): summary、明列stage、禁amend／force／no-verify、單元後輸出hash／message／行數／status／shortstat並立即push；取代原「最多累積3個」的節奏。開始時工作樹乾淨，HEAD/upstream/main皆c80a4be。

提交前實跑c80a4be既有來源build於reports/release-prep-policy-check-20261028-01，318檔／兩次ZIP一致／兩Git Job自然退出；這不是包含尚未提交政策文件的新候選。當前來源定向verify-checkpoint-policy-20261028-01：UTC06:53:13–06:53:16（台北14:53:13–14:53:16），31/31、1.388秒、0fail/error/skip、218AST無錯、source_unchanged、原Job自然0／remaining0／無強停。新增文件換行混用曾被diff-check攔下，未commit該狀態，修正後重查；政策內容／連結與變更量另驗。僅四份文件以單一docs(workflow) checkpoint普通push既有開發分支，輸出實際SHA與乾淨狀態，不重寫舊commit、不重新宣稱產品／原生驗收。

## 2026-10-28 main整併終核、完整本機回歸與附件排除（最新）

使用者已明確授權推main並要求整併／測試。fetch後origin/main與開發分支同為a4e13fa75ea0d2d8b455281811114de3efe91844、ahead/behind0/0、tree差異0；五個可分享分支均為main祖先，沒有待合併產品碼。PR #1早於2026-10-22T09:09:47Z合併615f77f，本次依要求移除聊天PR附件，保留GitHub合併歷史。截圖+5368/-39與git diff 4a1a95bced234d75b744537f7507bd9f86235b11 a4e13fa完全相符（58檔已提交歷史），不是未提交數；UI實際基準未直接讀取，不能宣稱畫面已歸零。

依使用者要求實跑當前主線完整驗證：py -3.13 -B scripts/verify.py --run-dir reports/verify-main-integration-20261028-01 --timeout-seconds 1800，UTC06:33:14–06:40:24（台北14:33:14–14:40:24），428.735秒；1636run=expected1636、1633pass／3環境skip（兩symlink建立不可用、一notification icon不可用）、0fail/error，218AST無錯、source_unchanged、stop flags false、原guardian自然0／remaining0／無強停／逐測試殘留0。240來源hash與b534候選包全符；涵蓋本機已安裝SDK，非僅沿用CI47skip，不啟真模型／native掃描。

依最新隱私要求刪除四張已知本機圖片及其空附件目錄，不讀內容；已核對索引／全部已知Git歷史無相關檔案，GitHub main完整tree無相關路徑。圖片與含私人檔名的回條皆不提交；只新增.gitignore對附件／剪貼簿截圖的排除，git check-ignore兩項通過且一般產品圖片不被全面排除。平台聊天附件不在本機刪除範圍，未宣稱已移除。這個checkpoint僅排除規則與結果文件，沿開發分支保存後普通快轉main；產品來源未改，不重跑回歸、不打tag／發布／刪分支，私人main及其他worktree保留。

## 2026-10-28 新候選交付驗收閉合：b53479a（最新）

固定候選b53479a28ea030a92ae23ba50ed24d6aca2be679已普通push／直接核對遠端；來源切片相對8b9cf27為7檔460新增，非未保存修改。新增受版控verify_candidate.py及12個測試，外部commit／ZIP hash必填、完整逐檔manifest比對、純離線預設與可選有界私有Job合成smoke；CHANGELOG與操作命令已保存。

本機定向verify-candidate-tool-20261028-03為31/31、0skip/fail/error、1.193秒、218AST無錯、原Job自然0／remaining0／無強停；240來源hash與新候選包全符。新candidate03實際318檔／兩ZIP一致，SHA256d755a8d85a9fec15343a88b7b0adeb24b003f7d21d6e3322b127df73b3e10605；新工具在candidate-verify-release-20261028-01實跑13/13，四CLI原Job自然0／remaining0／無強停；兩個實際負向CLI在解壓／啟child前拒絕錯誤pin／竄改manifest（exit2、owned空）。新候選回復演練5/5、九個Git Job自然退出，真index／checkout不變。原b57的1624完整結果沒有改標新SHA。

精確新SHA CI run40642090530於UTC06:14:47（台北14:14:47）completed/success：Windows1636run=expected、1589pass／47可選SDK不可用skip、0fail/error、337.593秒、source_unchanged／stop flags false／原Job自然0／remaining0／無強停／逐測試殘留0；Linux fixture104/104。固定結果在reports/release-prep-candidate-20261028-03/ci-*.json，未安裝依賴或手動觸發CI。真模型／native均0，歷史真04不冒稱重驗。

最新入口docs/RELEASE_PREPARATION.md；只補四份結果文件checkpoint後普通push原開發分支並另存SHA／0/0核對。追蹤檔案應乾淨，兩張未追蹤附件／其他worktree及私人main保留。排程已刪除、不恢復；無main/tag/release／部署／刪分支。此輪交付工具缺口已閉合，原生111缺列／21error仍partial、24h/reboot及桌面喚醒仍未驗，須各自條件與授權；不把準備通過當真實環境全通過。

## 2026-10-28 候選交付增量：驗包／smoke已固化（最新）

接續8b9cf27，追蹤工作樹原乾淨／upstream0/0，未追蹤附件保留。使用者明確續做準備；排程已刪除，本次不建立／恢復。實際缺口是repo只有打包器，解壓smoke依賴reports臨時腳本；新增scripts/verify_candidate.py及tests/test_verify_candidate.py，必填外部commit與ZIP SHA256、有界輸入快照、完整manifest／逐檔比對、重複key／型別／路徑與舊目錄拒絕；預設離線不啟子程序，--smoke才在新reports副本跑合成CLI，事先私有Job與原退出回條，無模型／native／ACK／系統變更。

py -3.13 -B scripts/verify.py --run-dir reports/verify-candidate-tool-20261028-03 --timeout-seconds 180 --module test_verify_candidate --module test_package_candidate --module test_verify_completion --module test_verify_portability：UTC06:07:49–06:07:51（台北14:07:49–14:07:51），31/31、1.193秒、0fail/error/skip、218檔AST無錯、source_unchanged、原Job自然0／remaining0／無強停／逐測試殘留0。01/02亦31/31；02移除不必要os.name mock並確認拒絕原因，03再拒絕remaining的bool假零，才是最後來源。新工具先前已對原b57 ZIP實跑reports/candidate-verify-historical-20261028-01，完整manifest與13/13 smoke、四個CLI原Job皆自然0／remaining0／無強停；最後來源接續新候選實跑。

此切片先commit／普通push原開發分支，再實際建新commit候選、外部pins驗包／smoke、來源綁定及精確CI。舊本機1624回歸仍只屬b57，不套用新SHA；其餘native partial／24h/reboot等限制不變。界線與可重現命令見docs/RELEASE_PREPARATION.md；runtime不提交，無main/tag/release／分支刪除。

## 2026-10-28 發布前準備全數完成；尚未發布（最新）

使用者指定「不用release，做完所有準備」。固定候選b57b43be8333327584ef05af4e71740b5b80d621已普通推到origin/feat/local-codex-acceptance；公開main及所有可分享分支皆為候選祖先，無語意衝突，私人本機main祖先不可達。其他worktree及兩張未追蹤圖片保留。候選對公開main615f77f的285檔／55340新增／1961刪除是已提交歷史合計，不是未保存修改；此後僅四份結果文件補記。

修後完整guardian02已自然退出：UTC05:43:35–05:50:36（台北13:43:35–13:50:36），419.655秒，1624run=expected1624、1621pass、3環境skip、0fail/error，stopped_early與stop_requested皆false；216檔AST無錯、238來源hash與候選ZIP全符、source_unchanged，原Job自然0／remaining0／無強停／逐測試殘留0。三skip是兩項symlink建立不可用、一項notification icon不可用；不是略過失敗。原01的提前停止假綠已修且原回條保留、不作完整驗收。

實際candidate02包316檔，兩次build位元組一致，SHA256為2d5ae6a55a24aebd344a630a53b61abc075cfb9af3b62664afb1d9582a8f62d5；包內CLI合成smoke14/14、五個Job自然0／無殘留。獨立index回復5/5、九個Git Job自然0，反向patch所得tree等於公開main、真index／checkout不變。精確候選CI run40639767342 completed/success：Windows1577pass／47可選SDKskip，Linux fixture104/104；本機SDK範圍則如上1621pass。全部native scan/model0，runtime不提交。

入口docs/RELEASE_PREPARATION.md／CHANGELOG.md；本機證據reports/release-prep-candidate-20261028-02與reports/verify-release-preparation-full-20261028-02。PREP-1–5已完成，最後純文件checkpoint依原分支commit/push並另存遠端SHA核對；本聊天15分鐘接續在保存核對後暫停，原跨專案暫停排程不動。未push main、打正式tag、發布、部署或刪分支。真04歷史交付已通過；native111缺列／21error仍partial，24h/reboot、既有桌面聊天喚醒未驗，須依原界線另授權／驗收，不將準備完成冒充產品所有環境完成。

下一個人類決策是何時正式發布及tag/changelog，或另批准原生診斷；兩者均不屬本次「只做準備」。不新增無關工程以延長執行。

## 2026-10-28 發布準備實跑修復與固定來源重驗（最新）

整合checkpoint3ed82a8已推；首次實際ZIP build在新01目錄失敗，私有Job launcher不替applicationName短名稱git查PATH。改先解析並驗證既有完整git.exe路徑，不執行wrapper／不下載；新增兩個fixture。原失敗目錄與固定原因保留，未將其稱build成功。

為修正build而合作停止原完整01，原worker自然0／remaining0／無強停，跑1533項／1530pass／3skip；原驗證器卻給passed_checks=true，確認另一實際缺陷。原回條保持原樣，acceptance-classification.json明示取消／不得作完整PASS。修worker與parent雙閘道：必須非空、expected_tests等於tests_run、stopped_early=false、stop_requested=false；新增完整／中斷／末項取消／空suite／缺或bool計數fixture，避免乾淨exit洗綠。

定向verify-release-prep-repairs-20261028-01為19/19、expected19、0fail/error/skip、.681秒、source_unchanged／原Job自然0／remaining0／無強停，native/model0。修後完整02已啟動於reports/verify-release-preparation-full-20261028-02，原01不重用；來源再次固定，僅文件可增量更新。接續新commit的實際ZIP02／包內合成smoke／恢復演練，全部證據閉合才稱準備完成。

## 2026-10-28 全部發布前準備已啟動（最新）

最新使用者明確改為「不用release，但完成全部release準備、安排連續任務」。不再以分支／版本未選阻擋準備：沿用現有開發候選、納入所有可分享分支及公開main既有紀錄，私人本機main祖先、其他worktree與圖片保留；不push main／tag／正式發布或刪分支，語意衝突仍停止。

同聊天15分鐘接續已建立，原跨專案暫停排程未動；完成後暫停，不並啟runner。新增scripts/package_candidate.py與6個合成ZIP安全測試，使用已安裝Git與Python、私有Job建立兩份同commit ZIP、檔案hash／路徑／容量／必要檔案檢查。初版5/5定向通過；追加Windows別名與私人檔案邊界後，完整guardian已執行於reports/verify-release-preparation-full-20261028-01，來源固定，結果未出前不記PASS。

CHANGELOG為Unreleased草稿；完整佇列、build、包內smoke、恢復演練及未來發布閘道在docs/RELEASE_PREPARATION.md。本checkpoint先保存整合／打包前置，再接實際候選包與結果，不將準備成功冒充native coverage、24h/reboot或正式發布。

## 2026-10-28 P0-LISTENER-COUNTS-003：修正baseline可誤判完整的缺陷（最新）

依使用者要求實際修bug、不能只隱藏UI或解除PR連結，從47af11f接續。發現project_baseline只查四項table status/count欄位存在，沒有核對返回列數；缺列／多報、TCP與UDP或IPv4與IPv6錯表，即使自有query自然exit0也可能判完整。先以guardian新回歸重現5個failure entries（18方法／13pass，無error），保留reports/verify-listener-count-regression-20261028-01；原正向fixture四表各1但只有1列，亦修正為TCP4=1、其他=0。

修復按每列protocol及實際IP family分組，逐表核對固定四項count，新增table_counts_consistent；不只查總和，不放寬零錯誤／身分／退出標準。三個新測試含缺列與錯表拒絕、乾淨exit不能洗綠，以及四表／完整空表仍有效。命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-count-regression-20261028-02 --timeout-seconds 180 --module test_windows_listener_validation --module test_listener_error_summary --module test_listener_identity --module test_collector_contract：UTC05:11:45–05:11:55（台北13:11:45–13:11:55+08:00），52/52、8.699秒、0fail/error/skip、source_unchanged、原Job自然0／remaining0／無強停／無逐測試殘留，native scan/model均0。不是release合併後完整回歸或原生重驗，原235列／缺111列／error21的partial不變。

gh api唯讀核實PR #1 title為Publish bounded Codex event delivery with MIT license，closed／merged=true、merge SHA615f77f、2026-10-22T09:09:47Z已合併；它是舊PR，未以解除附件代替處理。新release依使用者流程仍待指定分支、merge方式、版本號與changelog，沒有合入main／打tag／刪分支。修復按原checkpoint規則commit/push現有開發分支並另存回條。

本次script變更使既有windows-listener-diagnostics-20261028-01的source hash過期；保留原manifest／未批准template與NEXT_DIAGNOSTIC，標記superseded，不覆寫或執行。後續若要真診斷須依當時版本重新prepare及取得新精確批准；本輪不新增批准問項或native查詢。

## 2026-10-28 既有11份研究文件保存 checkpoint（最新）

依最新使用者明確授權，接續0ea26cb；本機／upstream／直接ls-remote均相同，ahead/behind0/0、追蹤檔案原乾淨，未見其他協作writer或index.lock。本次範圍為docs/research/agent-event-ingress五份與major-vulnerability-response六份既有10/23–24研究，逐檔審查後保存；不是新待推產品碼、PR發布或新研究。

最小處理：移除OpenOctopus來源的聊天識別／deep link及標題，重大漏洞README不公開cached health原始時間／狀態，保留「未獨立驗證程序存活」。11份均標明歷史基準優先／不當現況，所有reports連結逐一標明本機證據、不隨repo提供；公開來源與當時失敗／unknown／未驗證語義保留，不讀取或提交原reports。舊「未單獨commit」與每日五次等段落只保留為當時歷史，不改寫成現行要求或已驗收能力。

檢查只限檔名／內容／相對連結／歷史語義／固定秘密及私人ID模式、git diff --cached --check；命令、原／後文件hash與結果在reports/research-checkpoint-20261028-01，不是產品回歸或原生驗收。只暫存明列11份研究＋STATUS/HANDOFF，純文件checkpoint以[skip ci]普通push原origin/feat/local-codex-acceptance並直接核對遠端，實際SHA見Git及本機remote回條。兩張.codex-remote-attachments圖片保留未追蹤，不讀取、不提交；P2-OS-DIAG-002仍未批准，無新模型／native診斷／部署／主線合併或tag。

## 2026-10-28 P2-OS-DIAG-002：身分錯誤分類保存已完成，原生未重跑（最新）

接續a7bdfc0、原開發分支；追蹤工作樹原乾淨，兩個他人未追蹤目錄保留。窄讀發現NativeBackend／WindowsCollectors已有typed原因碼／階段／操作，但原baseline投影只保存總數。只改scripts/validate_windows_listener.py，加入有上限的error_summary及winapi.py來源hash綁定；不改native採集、規則或complete標準。分組只允許固定碼，未知維持unknown，保留／未保留／分類數分列；沒有新增PID、命令列、路徑、帳戶、端點或身分一致性資料。舊111缺列／21錯誤仍不可回推根因。

新增6個注入／合成測試，命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-error-summary-20261028-01 --timeout-seconds 180 --module test_listener_error_summary --module test_windows_listener_validation --module test_listener_identity：UTC03:56:35–03:56:44（台北11:56:35–11:56:44+08:00），27/27、7.506秒、0fail/error/skip、source_unchanged、原guardian自然0／remaining0／無強停／無逐測試殘留。native scan/model均0，未手動觸發CI，也未重跑真04／長測試；普通push可能觸發既有CI，其結果尚未另核實。新切片不是原1e8f7e0受測CI或真主機通過。

唯一下一診斷方案只prepare於reports/windows-listener-diagnostics-20261028-01，query_started=false、未批准、無intent/result/outer-start；run/hash與完整有界決策在docs/WINDOWS_VALIDATION_PLAN及該目錄NEXT_DIAGNOSTIC.json。沿用原一次native baseline範圍5秒／30秒與私有Job收尾，只新增固定分類數保存；本輪不開新批准問題，不執行、不沿用舊批准。拒讀／物件不可用／建立時間晚於捕捉／API不可用／一般失敗可分列，仍不能證明程序退出競態或逐owner根因。checkpoint按原規則commit/push；runtime／批准template不提交，遠端結果另存回條。

## 2026-10-27 P2-OS-001 已批准並實跑：partial，未通過完整基線（最新）

收到 dot 轉達的人類原問答：2026-10-27 03:00 UTC「同意1、2、3」，本案僅第3項單次 native listeners baseline。於原 reports/windows-listener-baseline-20261026-01 寫 human-approval.json，保守以 03:00:00–03:30:00 UTC 綁定原 root/run/manifest hash/scope；執行前確認 HEAD edc088c、原11檔 source hash 相符、無 intent/result/outer 回條，沒有重複執行。此新具名批准已取代下方歷史「尚未答覆」，一次授權現已使用。

實際命令：py -3.13 -B reports/windows-listener-preparation-20261026-01/run-owned.py --root reports/windows-listener-baseline-20261026-01。查核 UTC 03:04:36.844483–03:04:37.668540（台北 11:04:36.844483–11:04:37.668540+08:00），query elapsed 0.739012 秒，無逾時／取消。TCP IPv4／IPv6 分別28／13列，UDP IPv4／IPv6分別132／62列，四項 status=ok，共235列、未截斷；必要程序身分缺111列、error_count=21，process_identity_status=unknown。因此 source partial、complete=false，驗收 status=blocked／reason=baseline_incomplete；不能把四表成功當完整 native 驗收通過，更不能判主機安全。

原 HANDLE／Job 回條：內層 query 自然 exit 0、外層 validator 自然 exit 2，兩者 remaining_owned_processes=0、forcibly_terminated=false；外層 wrapper_error=false／deadline=false，命令返回1如實保留。只落盤固定狀態計數與自有 Job 回條，raw facts／socket／registry／system change／model 均無。本次未改產品碼或重跑 CI／全庫／真04；受測產品仍1e8f7e0。

獨立收據一致性核對13/13（不是 baseline PASS）：原 run/批准時窗/scope、四表計數守恆、退出與原11檔 hash 均相符。證據為同目錄 result.json、execution-intent.json、outer-start.json、outer-exit.json、acceptance-crosscheck.json。只憑固定計數無法區分拒讀、程序退出競態或其他身分讀取失敗，根因維持未知；沒有再查、提權或降低完整標準。P2-OS-001 現為已執行但不完整，不再等待這次批准，也不自動換目錄重跑；後續 native 診斷／重驗須另有精確必要範圍。既定離線切片已完成，未辨識出可直接修復的新離線 regression；先按 checkpoint commit/push 保存，不新增 fixture 代替真來源。

## 2026-10-27 接續核對與 soak 時區修正（最新）

接續 HEAD d922f48，分支 feat/local-codex-acceptance、upstream origin 同名；接手時追蹤檔案乾淨、ahead/behind 0/0，原兩個未追蹤目錄保留。受測產品仍為 1e8f7e0；既有 CI success、真04及調查證據沿用原 scope，不重跑全套。

原 soak summary 的實際 UTC 起訖為 2026-10-25T17:12:21.291029+00:00 至 2026-10-25T17:44:01.298238+00:00，等於台北 2026-10-26 01:12:21.291029–01:44:01.298238+08:00。下方 10/26 標題是本地日期，不能把 UTC 17:12 誤配成 10/26；1900.017392 秒 wall 及既有量測結論不變，未重跑 soak、未改原收據。

P2-OS-001 仍缺原具名單次批准：是否批准 reports/windows-listener-baseline-20261026-01 的一次 native TCP/UDP、IPv4/IPv6 listeners baseline 及必要 owner 建立時間查核（query 5 秒、總預算 30 秒，只保存狀態／計數與自有 Job 退出回條；不開 socket、不改 registry／系統、不啟模型或其他來源）？此處記錄原待決問題，沒有重新建立請求。此次轉達不代答；現有目錄無 human-approval.json、execution-intent.json、result.json 或 outer-start.json，未執行採集。有直接有效批准後才依同 root/run/hash/scope 執行一次；無已辨識的新離線缺陷，不用擴 fixture 或重跑驗證替代真來源驗收。

本次只修正文件與核對原收據；命令為 PowerShell Get-Content／ConvertFrom-Json、DateTimeOffset UTC→+08:00、Get-FileHash 及 git diff --check。證據 reports/soak-time-correction-20261027-01/state-verified.json 與 validation.json；提交／推送仍依既有 checkpoint 規則，遠端結果另留回條，不把文件 SHA 當新受測產品。

## 2026-10-26 固定Git保存規則（最新）

依直接使用者要求，AGENTS新增Git checkpoint與遠端保存規則，CLAUDE.md作簡短入口：每個可保存checkpoint立即commit/push，連續小commit最多3個未推送；恢復／交接時補推，失敗保留本機與待推SHA，推後直接核對遠端。僅原origin/feat/local-codex-acceptance，不改產品、安全或資料界線，也沒有建立背景排程。文字驗證8/8與git diff --check；證據reports/git-push-policy-20261026-01/validation.json（2026-10-26T16:00:08.752770+00:00）。本次純文件以[skip ci]保存，不重跑已通過CI／測試；受測產品版本仍1e8f7e0。


## 2026-10-26 精確版本遠端CI已成功（最新）

受測可用產品版本為1e8f7e0e74f2018849b44cb02e2052d2fe817da4，分支feat/local-codex-acceptance。獨立GET核實Offline verification run40345960922／attempt1／push，head_sha完全相同，UTC2026-10-26T15:11:02Z（台北23:11:02）已completed/success。Windows job121652823962：1603項、1556pass／47可選SDK及相關transport/SSE依賴skip，0failure/error；原Job自然exit0／remaining0／無強停。Linux mock job121652824391：104/104、無skip/fail/error，僅自身worker exit0，creation/job/tree/remaining未知，仍明示無Linux native。

新終結收據reports/ci-head-bc56e37-20261026-01/repair-ci-terminal.json；兩次pending與bc56e37原failure各自保留，latest回條已指向成功。完整47個skip名單保存在repair-windows-summary.json，不把skip當實際執行，也不借本機SDK或其他SHA綠燈補足。這輪只讀遠端metadata及必要結果摘要，沒有CI rerun/dispatch、本機全庫／九案例重跑、workflow／權限變更或新模型／主機採集。

本次只更新STATUS/HANDOFF/EVIDENCE，以[skip ci]提交／普通push保存狀態，避免純觀察形成CI循環。這個文件checkpoint的SHA不是另一個受測SHA；產品程式與1e8f7e0相同，CI成功只綁定1e8f7e0。下一既定里程碑P2-OS-001仍是原單次listeners baseline，需原具名問題的直接批准；不重問、不擴範圍。正常收件／調查與CI閉環已交付，不宣稱真主機防護、既有聊天喚醒、24h/reboot、Linux native或已超越競品。


## 2026-10-26 精確CI失敗已核對與修復（最新）

已唯讀核對bc56e37b4cfb63ed3e0a9caf98d11a66b140372d的push CI：Offline verification run40339572814／attempt1，結論failure；Windows job121630253841及mock job121630254549都失敗，不能用空legacy statuses或本機綠燈代用。Windows摘要為9個failure entries／1error，mock因非Windows Popen無created_at在驗證器137行中斷，原run無artifacts，沒有更細unit trace。原CI狀態保持failure。

已在隔離合成條件重現全部9個Windows失敗名稱及RustSec CRLF TOMLDecodeError。修正：desktop/schedule/service測試根目錄先canonical resolve、損壞pending測試明示fixture SDK前置；產品安全閘道不改。RustSec解析正規化CRLF。驗證器非Windows僅保留原Popen worker的退出碼、合作取消／有界自有child收尾，creation/job/tree缺證據維持None/false；只有mock scope可接受worker-only證據，timeout/owner failure即使exit0也不得pass。Windows原privateJob finish不變，workflow／權限未改。

本機受影響127/127；相同短路徑＋缺SDK重現6方法／原9failure entries現為0，CRLF accepted、兩次Job均自然0/無殘留。最後guardian邊界7/7、mock範圍104/104，皆source_unchanged、自然0/Job0、model0/scanfalse；不同範圍不加總成全庫，也不是Linux實跑或遠端CI通過。修復提交依既有規則普通push同分支後，另查新SHA的既有CI，不手動dispatch/re-run、不新增workflow或權限。證據在reports/ci-head-bc56e37-20261026-01及verify-ci-*。


## 2026-10-26 已確認遠端保存並接續golden量測（最新）

已普通fast-forward推至origin/feat/local-codex-acceptance；git ls-remote實查遠端與本機同為548efe8bbfc7548b5b2d530db2c9203295583bce，ahead/behind=0/0。先前57個待推commit及本checkpoint已保存，不是正式發布；未推main／其他保留refs，不force、不改歷史。推前累積264檔/+52654/-1961是9576b13→cd117f9的比較，548efe8本身只有5檔/+106。其他兩個未追蹤目錄仍保留。

之後已接續原任務，完成reports/investigation-source-golden-20261026-01：9案例全過、錯加0／漏加0，4案例缺實體／來源維持UNKNOWN，18事件仍pending／ACK0，逐案保存與重開一致。獨立9/9 SQLite mode=ro/query_only核對來源hash與case；自有worker原HANDLE自然0／Job0／無強停。每案建案37.255–101.101ms，九來源庫合計405504B；僅這組synthetic來源shape，不是7來源全覆蓋、惡意偵測率或production效能。02定向29/29證據沿用，產品碼未改。

本補記為下一個小checkpoint，同既有分支普通推送並實查遠端；實際最終SHA見Git及reports/git-checkpoint-20261026-01/remote-verified-final.json，不用文件意圖代替推送結果。後續每個可獨立保存階段提交並推送，不再累積。尚缺真來源／OS帳戶owner／跨來源因果、24h/reboot及實際競品同環境評測；原listeners具名批准不重問、不代授權。離線下一實作僅在有具體產品缺陷或契約缺口時進行，不用擴fixture數替代真路徑。


## 2026-10-26 Git遠端保存 checkpoint（最新）

最新直接使用者要求先提交及遠端保存，再接續開發；這是本專案既有開發分支的push授權，取代下方本輪「只本機／不push」限制，但不授權正式發布或推其他分支。位置EventGuard，分支feat/local-codex-acceptance，上游origin同名，remote https://github.com/SecludedCorner/EventGuard.git。推送前遠端實查9576b13a6773ce81c3a01799743d30094a48449a，本機cd117f9已領先57commit；比較遠端→HEAD為264檔、+52654/-1961行，屬歷史累積，不是當前未提交量。

本checkpoint保存9個多來源golden case及其測試。首輪9個subcase同因測試誤讀list_events未公開payload_hash欄位而error，產品碼未改；改用公開schema正規化後計算hash。定向02為29/29，無fail/error/skip、source_unchanged，自有Job自然0／remaining0／無強停，未採集／啟模型／ACK。先保存，再續逐案例成本／錯加／漏加產物。

推送範圍只refs/heads/feat/local-codex-acceptance，不推其他本機保留refs。57commit逐檔路徑及所有新增patch行審查：265路徑／55946新增行，無runtime禁入路徑或高信度secret pattern命中；不等於形式化無秘密保證。reports/data/logs/SQLite/授權及他人未追蹤.codex-remote-attachments/、docs/research/不加入。推送結果以遠端核對回條及後續補記為準，不把意圖當成功。


## 2026-10-26 調查查證脈絡接通（最新）

接續bc5f028，P1-INVEST-002完成：新1.1案件納入同事件已驗證的保存診斷hash／時間／query類型／來源／狀態／列數，rows不複製、不重新diagnose。缺失／過期／未來／空結果／partial列缺口；跨事件誤綁及保存競態拒絕，診斷後續變更／刪除標明且保留原case，1.0仍可讀。CLI／Web均顯示來源脈絡。

新增8 fixture，核心定向160項159pass／1通知skip、0failure/error；之後僅Web／presentation變更的52項增量51pass／1同skip、0failure/error，兩輪source_unchanged，原Job自然0／remaining0／無強停，不相加為全庫。最終reports/investigation-product-20261026-03原來源10檔hash相符，18/18；真IAB保存／重開同case及診斷hash、2項保存query摘要一致，8事件仍pending／ACK0／單case，原worker自然0／Job0／無強停。診斷來自FixtureAPI，明示system_query_executed=false，不是原生主機證據。

原真04與1563pass、30分鐘idle均保留原scope；未重跑模型／全庫或native baseline。兩個調查切片已可用，操作及競品差距在OPERATIONS／MAINTENANCE_GOAL；沒有同環境競品實測，不能宣稱超越或全天候防護。下一可離線切片為P2-INVEST-COVERAGE-003多來源黃金資料集／誤關聯與UNKNOWN量測；listeners原具名批准仍待答覆，只阻擋該次原生觀測。執行資料不提交，本機commit、不push。


## 2026-10-26 事件調查產品切片（最新）

基底124b42c、分支feat/local-codex-acceptance；已新增同SQLite的保存案件、穩定實體關聯時間線、來源／過期／矛盾／截斷限制、CLI events investigate 與Web建立／更新。查看及重開不重算，不採集、不啟模型、不ACK，allowed_actions空；OS帳戶owner未保存，固定UNKNOWN，不把host雜湊當帳戶證據。

最新定向 reports/verify-investigation-20261026-03：152項、151通過／1 notification_icon_unavailable略過、0失敗／error，source_unchanged；guardian自然0／Job0／無強停。這不是重跑全庫；原1563pass與真04原版scope沿用。review發現跨episode序號不可比，最低成本改成同episode檢查，新增正常多端點／序號重置負控制，01/02前版證據保留。

最終產品 reports/investigation-product-20261026-02：CLI→HTTP→CLI→重開同case14/14，8事件全保留pending、ACK0、1最新case，自有worker自然0／Job0／無強停；01有實際瀏覽器保存／重開圖，web.py相同，02是episode修正後的最終來源重核。一次建案89.13ms、DB增8KiB、case2574B；非人類調查時間／production峰值或競品勝負。官方競品差距與量測方法在docs/MAINTENANCE_GOAL.md，操作在docs/OPERATIONS.md。

CURRENT/NEXT：離線P1-INVEST-002可繼續，接同事件已保存的診斷/query來源脈絡與時效，不重新diagnose。listeners具名批准只阻擋該次原生觀測；不是全部離線工程停止條件。真EDR／跨產品優劣、OS owner／跨來源攻擊鏈、24h／reboot／既有桌面喚醒仍未驗。先本機提交，不push。


## 2026-10-26 持續工程：長窗與所有權修復（最新）

操作入口補記（2026-10-26T07:43:13.5264320+00:00）：README／AGENT_SERVICE 已交付當前入口、一次 service 操作、固定 metadata 結果／ACK／五層退出查閱方法及適用情境；CONNECT_AGENT／LIVE_CHANNEL 舊相容流程加現行入口指引。17/17 唯讀核對，五份原真04證據 hash 不變、native baseline 11檔 source hash 相符，無新模型／採集／重跑回歸。紀錄 reports/operator-entry-review-20261026-01/validation.json。原聊天無新增 baseline 答覆，唯一待決點仍為同一目錄的單次批准，不重複提問。

基底4a1a95b，分支feat/local-codex-acceptance；只本機提交、不push。既定真CLI鏈仍通過：真04的一件合成事件 receive→query→result保存→ACK各1、pending0；MCP/CLI/supervisor/host/outer五層自然0。UI/API/CLI真頁面顯示亦已驗證。本增量沒有新模型任務。

P2-IDLE-CPU-003／30M：profile定位本harness每秒全樹usage成本，改為排空後單writer的已驗總量＋自身append delta。每筆仍_guard/實際大小/sample與report cap；mutation／phase／final仍全樹檢查，外部其他檔突變不是即時防篡改。12/12定向通過；恢復語意fixture明示虛擬deadline，不冒充真wall。真03 wall60.012212秒、idle31.411523秒CPU0.945115%，16ACK/pending0、自然0。

長窗 reports/soak-idle-30m-20261026-01：UTC 2026-10-25 17:12:21–17:44:01（台北 2026-10-26 01:12:21–01:44:01+08:00），wall1900.017392秒、16ACK/pending0、475有效樣本；原HANDLE自然0/Job0/無強停，7檔source hash不變。獨立32/32核對：最後實際1802.489810秒窗CPU0.343275%單核心、private峰增73728B（72KiB）、handle增0（111不變），三目標通過。這是自身harness idle，非整Job／production／24h／重啟或主機安全證據。

P0-OWNER-SNAPSHOT-005：已通過對應回歸。背景stop改綁control.lock內已驗selected_owner，避免診斷status瞬斷/舊run_id誤綁scope；App僅對固定unverifiable、無明確foreign identity的快照重觀測一次，第二份必須完整同namespace/run/PID/creation/Job/generation才控制，持續unknown仍阻擋。新增2背景＋3App確定性fixture；不推斷原失敗特定Win32錯碼。最新完整回歸 1566 項／1563 通過／3 略過、0 failure/error；source_unchanged=true，原Job自然0／remaining0／無強停。

P2-OS-001前置已完成：新增scripts/validate_windows_listener.py與15個fixture（guardian15/15），缺批准/過期/hash/scope不符/預存stop/intent fsync失敗不查詢；合作stop即使complete也不得pass。實際reports/windows-listener-baseline-20261026-01僅prepare，query_started=false。範圍一次native listeners／query5秒／30秒工作預算，無socket/registry/模型、只保存狀態計數與自有Job回條。原loopback陽性案例按產品語義不成立，已修正WINDOWS_VALIDATION_PLAN；不改規則或改綁全介面過測。

CURRENT/NEXT：下一個必需關卡是已準備的一次native listeners基線；非同步批准尚未回覆，沒有human-approval.json，不可執行。 其他實機來源/負向socket案例、既有桌面喚醒、24h及發布仍未驗或缺範圍，不自行排程、擴權、推送或承諾會話外喚醒。證據與完整命令見EVIDENCE；runtime／授權／SQLite不提交。

## 2026-10-26 持續工程：產品狀態、分頁與有界量測（最新）

基底 9a34a5b，分支 feat/local-codex-acceptance；依既有授權繼續，未 push、未改系統／帳戶設定。AGENTS 的 Continuous Execution Policy 已在 a34e466 逐字加入，繼續有效。

- P2-MCP-STATUS-001：CLI／Web／Tk 加入有界 MCP 退出摘要，從當次 attempt 原始 marker／HANDLE 證據重讀；舊資料、缺檔、外來 run 或非零皆維持 unknown，不信任快取的 verified。實際閒置 test App 的 API／CLI／瀏覽器一致顯示「MCP退出已驗證、退出碼0、ACK flush」。GUI 關閉後原 HANDLE 自然0／Job0／無強停，collection/model/新增CLI 均0。真04原64檔hash全不變；只新增App descriptor/lock。
- P1-SOAK-GUARD-002：spawn後任何有界異常先嘗試耐久 stop.request，再 grace／原自有Job收尾；保存失敗維持 unconfirmed。P2-SOAK-MEASURE-001：獨立 minimum wall、pacing、僅本worker pseudo-HANDLE的 CPU/private bytes/working set/handle 採樣，未知=null，JSONL有界。兩輪真有限harness各16 accepted/16唯一ACK/pending0，wall 60.037116／60.045564秒，皆自然0／Job0，非模型、OS重啟或24h。
- P2-GH-PAGES-001：GitHub有界分頁，預設5／最多8頁；一次固定metadata驗證 canonical repository ID，最多max_pages+1 GET，共用bytes/deadline；僅forward after或連續page，固定origin/path/filters/page-size，拒redirect／循環／混用／錯誤mapping。partial保留last-good、304不得洗完整；完整success才清舊單頁validators；max_pages屬resource policy，不使legacy cache換binding。

定向14模組253項252過／1通知圖示略過；首輪完整1534項1530過／3略過／1舊dict斷言失敗，已補新增unknown欄位後77/77。真canonical/after與soak增量定向201/201。最新完整回歸 1543 項：1540 通過、3 略過、0 failure/error，source_unchanged=true，guardian自然0／remaining0／無強停，model_calls0、machine_scan=false。原失敗不覆寫。

真公開分頁04：兩公告頁＋一次metadata GET，uv repo id699532645，17369/65536 bytes，1.305084秒；正確partial/github_pagination_page_limit，兩頁smoke及27項獨立核對通過。追加05按預設5頁上限仍partial，完整來源要求未達；只寫隔離test cache，未改正式cache，不再加大cap洗綠。早期01 transport_denied及wrapper無效finish reason缺退出回條、02/03 canonical不相容均保留。

資源實測：降低harness輪詢20Hz→4Hz後，短窗idle CPU 4.392866%→4.069045%單核心，仍未達<1%目標；兩次不是受控主機負載實驗，不能認定因果，更不代表產品monitor性能。下一項 P2-IDLE-CPU-003 只診斷自身harness observer成本，根因有證據才修。30分鐘idle／24h／全Job資源與實機來源仍未驗。

證據目錄：reports/verify-product-pagination-metrics-20261026-01、verify-agent-status-compat-20261026-01、verify-github-cursor-soak-20261026-01、verify-full-20261026-01/-02、soak-measured-20261026-01/-02、mcp-status-product-20261026-01、public-fetch-github-pages-20261026-01…05。原先 receive→query→result→ACK 及五層退出真證據仍是 reports/service-acceptance-eventguard-mcp-exit-20261025-04；本切片沒有重跑模型。執行資料不提交。


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
