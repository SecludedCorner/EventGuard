# EventGuard 目前目標

## 2026-10-29 DESKTOP-HANDLING-FILTER 已驗

人工狀態清單／三篩選交集、未知、保存後刷新／移出及選取守恆均已實作，真Tk與真合成SQLite通過68/68及未知補強27/27、0skip，255檔來源編譯。接續受影響桌面／Catalog／ACK整合及來源可重現保存，不無限重跑未受影響全庫；每單元普通同步main，目標active。Web、真人／原生等獨立關卡仍未完成。

## 2026-10-29 桌面人工狀態清單已驗／接續篩選

清單唯讀身分投影60/60及真Tk分列68/68、0skip與來源編譯通過，與ACK獨立；修復保存後清單未刷新。下一項DESKTOP-HANDLING-FILTER：只篩選已載入最多100件，人工狀態及delivery可交集、未知明示、清除還原、隱藏選取清掉詳情且不改pending／receipt；真Tk＋合成SQLite驗收後立即commit／push／普通整合main。整體Web、真人／原生等關卡仍待驗，平台目標維持active。

## 2026-10-29 DESKTOP-HANDLING A–C元件／合成閉環

四狀態入口與ACK獨立的控制層、Tk按鈕及真合成Catalog整合已驗，最終57/57、0skip與來源編譯通過；cc21787／7b102d5已普通整合main，本單元保存後續做整合核對。平台目標active且完整待驗邊界保留，不標整體目標完成。下一桌面增量為清單上人工狀態與delivery狀態分列，沿用既有讀取契約、缺失為未知，保持最多100件載入範圍明示；先核對欄位來源及身分再接元件，無新增採集／模型／ACK。

## 2026-10-29 平台目標已更新並恢復active

目標卡已在支援編輯器實際保存，get_goal回讀active；內容明列桌面人工狀態優先、完成單元後續做可執行桌面工作及保留原Web等驗收。A控制層cc21787已整合main；B真Tk按鈕／有界同ID重試通過61/61及來源編譯；C真Tk→真合成SQLite閉環仍待驗，不能將fixture當整合。下方「平台卡仍舊Web blocked」是歷史，已由本節取代。

## 2026-10-29 目前執行目標：桌面人工狀態，與ACK獨立

依最新使用者要求，優先完成桌面人工新增／已讀／已處理／忽略入口。成功條件：真Tk按鈕可明確保存、讀回及重開；沿用Catalog交易／有界歷程，operation_id冪等，不把人工handled當ACK／修復；忙碌、容量／活動失敗、未確認回條與切換事件不串資料。每單元build／相關測試通過後指定檔案commit、普通push開發分支並普通整合main，直接核對兩ref與工作樹／對origin/main兩個500行基準。

- A 控制層：已實作，54/54合成SQLite／活動定向通過；四狀態歷程與pending1／receipt0守恆。
- B 桌面入口：接真Tk按鈕、當前狀態、明確回條與未確認要求的同ID重試，不自動重送。
- C 整合：真Tk→真合成Catalog驗保存／重開、歷程、冪等、容量／活動故障與切換不串案，保留實際輸出及程序退出證據。

本目標完成需A–C全部有本版證據且兩遠端ref核對、工作樹與待整合差異清零。Web、原生輸入、真人比較、原生覆蓋／24h／reboot仍是獨立待驗，不作本桌面單元的替代證據或停止原因。下方舊Web目標與歷史阻擋保留，不能覆蓋最新桌面優先序。平台目標卡目前仍為舊Web／blocked，檔案更新不代表卡片已改；另以支援介面核對。

## 2026-10-29 桌面資料可信度修正與下一切片

snapshot例外不保留舊來源／事件作目前狀態，61/61真Tk／合成整合與來源編譯通過。真原生輸入因工具未列fixture窗口待驗，兩自有程序已自然退出；不以此停止桌面工程。下一項DESKTOP-HANDLING-A/B：明確保存人工新增／已讀／已處理／忽略，沿用Catalog交易、操作歷程與容量，與delivery ACK分離；控制層→Tk按鈕→真合成SQLite故障與冪等驗收，每單元commit／push／普通整合main，兩個500行差異不累積。Web／真人／原生驗收仍各自保留。

## 2026-10-29 桌面接續：實際操作核對

GUI操作文件的過期每日預算已依程式修正，17/17定向通過，當次執行與模型授權界線不變。下一項為本工具新建的合成桌面視窗實際點選／鍵盤驗收，沿用真控制層／Catalog，驗保存閉環及退出；只操作自有fixture窗口，不啟動監看、模型或修改系統設定。Web、人類比較與原生覆蓋待驗仍保留。

## 2026-10-29 DESKTOP-INVEST-SAVE-C 閉環已驗

真Tk按鈕→真合成Catalog保存／更新／前版／重開及容量／選取變更守恆已驗，49/49、0skip與來源編譯通過；A／B已逐單元普通整合main。此為桌面工程與實際元件驗證，不是人類操作或Web／原生驗收。下一單元核對GUI說明中過期每日預算敘述與現行無quota程式，修正文檔誤導，不變更模型授權、安全閘道或帳戶設定。

## 2026-10-29 DESKTOP-INVEST-SAVE-B 按鈕接線

桌面明確保存按鈕與worker、忙碌／容量／未確認狀態已實作，82/82含真Tk＋fixture，來源編譯通過；A已普通整合main。接續C真Tk→真合成Catalog保存／更新／重開及選取變更守恆；完成後仍保留真人版面／鍵盤、Web與原生獨立驗收，不因任何瀏覽器關卡停止桌面工程。

## 2026-10-29 桌面工作恢復：明確保存調查

最新使用者指示以桌面開發／測試續進，保留瀏覽器待驗；先前「目前無可執行Web切片」不限制桌面工作。DESKTOP-INVEST-SAVE-A：控制層已實作，64/64合成定向、來源編譯通過；B：接實際Tk按鈕、worker與容量／錯誤語意；C：真Tk＋真合成Catalog保存／更新／重開與pending守恆整合。每切片獨立驗證、commit／push／普通整合main，不以控制層或Tk結果取代Web、真人、原生關卡。

## 2026-10-29 最終驗收盤點：目標尚未完成

目前Web核心改善已有程式與離線證據，以下缺口不能由新增功能、Node／Tk或語法檢查補足。最近三個續航階段均保留同一瀏覽器驗收阻擋；本次一次`cua.getState()`仍回傳browsers=[]及`Local browser use is disabled in Work settings`，具體回條在`reports/build-web-list-javascript-20261029-01/browser-state.json`。既有使用者授權持續有效，原因是工具狀態，沒有重新要求權限或改設定。

| 原目標／驗收要求 | 現有可核對證據 | 尚缺與解除條件 |
| --- | --- | --- |
| G01七來源、歷史成功／新鮮度、六情境 | web.py sources／sourceSuccess；test_source_success_history、test_web_source_read_state；目前44項重疊定向 | 本版實際瀏覽器元件與六情境重驗；工具可操作後執行，不以synthetic DOM當瀏覽器 |
| G02來源缺口／新增嚴重事件入口 | web.py sourceGap／openNoticeSeverity；test_application_ui_state與既有合成證據 | 本版真瀏覽器連線失敗、提示獨立失敗與入口操作 |
| G03篩選／URL／返回與慢回覆 | writeFilterUrl／restoreFilterUrl／return-to-list；清單／詳情實際JS離線42項 | 真瀏覽器reload／back／forward、鍵盤焦點與失敗後重試 |
| G04保存調查／缺口／先前版本／處置與ACK獨立 | renderInvestigation／renderInvestigationRevisions／renderHandlingHistory；catalog／revision／Tk及Node既有證據 | 真瀏覽器版本展開／焦點及跨頁重開；不能從時間相近補造關係 |
| 200%／800與1280px／可比操作量測 | ENGINEERING_PLAN與LOCAL_UI_ACCEPTANCE既有程序；200%尚未驗 | 可用瀏覽器確認實際縮放；真人量測需參與者，可比競品需合法帳戶與資料，未宣稱優越 |
| 原生覆蓋／24h／reboot／桌面喚醒 | WINDOWS_VALIDATION_PLAN／既有partial證據，各自保留關卡 | 當前有效的具體授權與環境；本次未啟動採集／模型／長跑 |

下一個直接驗收動作：工具狀態確有變更後開專用合成頁面，依上述G01–G04與200%程序驗實際元件，保存匿名結果及讀前後hash／pending／ACK／程序退出。原目標保留，不縮小為離線通過。現有HISTORY-RECOVERY來源信任根與無損使用者恢復仍獨立未完成，不建立未批准憑證或以hash冒充認證。

## 2026-10-29 Web事件清單未知狀態

事件清單刷新失敗／格式錯誤明示未知、停用分頁、清除未確認舊列；提示數量獨立失敗不阻塞清單。42/42實際JS＋synthetic DOM/API與來源編譯通過，仍缺真瀏覽器／200%／鍵盤／先前版本焦點。下一步一次有界檢查可用瀏覽器能力，不反覆輪詢同一錯誤或以離線結果升格。

## 2026-10-29 Web來源失敗不沿用舊成功

來源卡片載入／HTTP／格式錯誤明示未知、七唯一來源整批核對與舊回覆防護已實作，44/44實際JS＋合成API及來源編譯通過。產品Web驗收仍待真瀏覽器（含200%、鍵盤及版本展開／焦點），不可用Node／桌面證據代替；下一步沿用既有驗收出口，不無限新增功能。完整恢復來源可信根／人類與原生關卡仍獨立。

## 2026-10-29 Web詳情故障誠實呈現

詳情讀取失敗／ID不符明示未知並停用寫入，晚到與重試有實際JS離線證據（41/41、0skip）；真瀏覽器驗收尚缺，不標產品UI驗收DONE。接續來源卡片刷新失敗的未知呈現；保持Web、真人、原生與恢復可信來源各自關卡，不以桌面或Node替代。

## 2026-10-29 HISTORY-RECOVERY 唯讀預檢已呈現已知衝突

CLI預檢與恢復原語共用逐事件相鄰檢查；34/34合成定向、來源編譯通過，不把前綴／hash相符當來源認證或完整恢復。後續仍需來源可信根、明確使用者恢復入口及容量釋放的無損契約；不自行刪紀錄或假造認證。Web、真人與原生驗收保持獨立待驗。

## 2026-10-29 HISTORY-RECOVERY 轉換一致性

內部append-only恢復原語新增逐事件轉換連續性閘道，35/35合成定向與來源編譯通過；沒有來源認證／容量釋放／正式使用者還原，仍未達成整體恢復驗收。下一切片：唯讀preview顯示內部轉換衝突與未知範圍，避免只有hash／身分相符而看不見已知阻擋。

## 2026-10-29 桌面詳情讀取邊界已修正

切換／失敗／重試與回應身分核對已完成，最終79/79含真Tk＋fixture，來源編譯通過。下一步核對桌面只讀調查流程的整合覆蓋與仍缺少的使用者驗收，不以重複測試或新增無關功能代替實際進度。Web、真人鍵盤／版面、原生覆蓋及長期恢復驗收仍獨立保留。

## 2026-10-29 桌面來源一致性已修正

來源列統一同次保存狀態輸出，77/77（含真Tk＋合成觀察）與來源編譯通過；不將舊overview成功帶入新拒讀／錯誤。後續核對詳情讀取失敗時的舊內容標示。原Web、真人與實機關卡維持未驗，不因桌面工程升格。

## 2026-10-29 保存證據變更整合已驗

合成member缺失／內容變更經真EventCatalog到真Tk的最新與前版未知呈現已驗，SQLite及pending保留。下一個有價值的離線核對是桌面目前來源狀態與保存成功時間的資料來源一致性；Web／真人／原生與無損恢復完整使用者流程仍各有未驗／前置，不擅自升格DONE。

## 2026-10-29 桌面保存證據基本呈現

最新調查摘要、最多16項時間線、8項缺口、最近3版修訂、最後8筆處置歷程均已接入桌面只讀詳情；分別有真Tk＋合成EventCatalog／fixture證據，來源編譯通過。真人版面／鍵盤、Web瀏覽器與原生等關卡仍未完成，不用功能數或測試數代替。後續優先核對缺失／變更資料的端到端呈現及恢復邊界，不無限擴張桌面功能。

## 2026-10-29 桌面時間線接線

有界保存時間線與中文證據缺口已實作，91/91（含真Tk與合成EventCatalog）及來源編譯通過。下一切片是只讀前版調查修訂摘要，分列成員／診斷狀態，不補造未保存歷史；真人／Web與原生關卡仍待驗。

## 2026-10-29 桌面只讀處置歷程

已呈現人工處置與最後8筆歷程，84/84（真Tk＋fixture）與來源編譯通過；保持處置／ACK獨立、缺失歷程未知。下一切片可補桌面保存調查的有界關聯時間線，不從時間相近推定因果或程序樹；人工／Web與真實環境仍各自待驗。

## 2026-10-29 DESKTOP-INVEST-001 摘要接線

桌面保存調查摘要已實作並通過87項定向（含真Tk＋fixture），錨點不符不顯其他案件，成員／診斷／過期分列；人工版面與鍵盤待驗。下一單元為只讀處置狀態與歷程，明示處置不等於ACK、缺失不等於無操作，沿用EventCatalog資料，不新增處置或採集。

## 2026-10-29 整合 backlog 已清理

main 普通 merge 9391062 已推送並核對；完整回歸 1736 通過、2 symlink skip、0 失敗。500行上限同時涵蓋工作樹與分支對origin/main待整併差異，最新整合授權見 CLAUDE。接續桌面保存調查友善摘要；既有瀏覽器、真人與實機待驗條件不變，歷程恢復仍缺使用者入口與可證來源，不把內部合成原語當正式恢復。

## 2026-10-29 持續推進目標（最新執行順序）

最終目標維持：讓使用者清楚判斷發生什麼、資料是否可信、缺少什麼證據。既有 Web 目標及其驗收條件完整保留；桌面版共用保存資料與誠實呈現語意，不用桌面合成測試代替 Web 或實機驗收。

- 先做可執行的產品工作：桌面保存調查詳情（DESKTOP-INVEST-001）、處置／ACK 的只讀區分，以及不依賴瀏覽器的資料正確性與故障恢復。每單元須有明確產品觸點及有意義的驗收。
- 瀏覽器、真人操作、縮放及真實環境各自列待驗；單一工具受阻時轉做其他已授權單元，不重複輪詢同一錯誤或將整體目標標完成。
- 每完成單元立即驗證、審查、commit、普通 push 並核對遠端，再選下一個可執行單元；未提交新增＋刪除不超過 500 行，每 commit 約 200 行內。
- 只有最終目標達成、所有有價值且已授權的工作確實受阻、使用者停止，或實際執行限制時才停；checkpoint 與回報不是停止條件。
- 不建立排程；會話外不保證自行恢復。平台目標卡片狀態與磁碟佇列分開核對，不因文件更新宣稱卡片已恢復。

## 2026-10-29 桌面離線工作接續

P1 DESKTOP-SOURCE-002：只讀來源缺口摘要已接線，75/75（含真 Tk＋fixture）與 244 檔來源編譯通過；不新增採集／模型／ACK。桌面人工操作及版面未驗。後續可對齊桌面事件詳情的保存調查呈現，保留身分／來源缺證據未知，不新增原生查詢。

使用者要求先推進不依賴瀏覽器的工程；瀏覽器驗收保留獨立關卡。P1 DESKTOP-SOURCE-001：Tk 七來源表格歷史成功時間已接線，來源編譯與 74 項定向測試（含真 Tk＋fixture）通過；桌面人工操作與縮放仍待驗。下一個可執行項為桌面來源缺口摘要，驗收需拒讀／過期／未知不當安全、刷新不新增採集／模型／ACK；不以桌面結果取代 Web P1 GUI-UX-200 或 INVEST-REV 的待驗範圍。

## 2026-10-28 當前缺口與可驗收目標

研究任務「EventGuard 競品 GUI 研究與增強規劃」已完成原定研究與工程規格（f1ed1e0、ad1f127）；其後市場比較 Wazuh、Velociraptor、Portmaster、Fleet、Elastic、Security Onion、System Informer 的補充結論在原任務對話，未宣稱已落地為完整獨立研究或實測。以現有工程證據為準：

| 優先／ID | 目標與驗收條件 | 證據／缺口與依賴 | 下一步 |
| --- | --- | --- | --- |
| P1 GUI-001–004 | 七來源、缺口、篩選返回、保存調查在合成瀏覽器可辨認未知與缺證據 | 已合成驗收；人類操作與真實來源未驗 | 對受影響版本持續定向驗證 |
| P1 GUI-UX-200 | 真 200% 縮放下關鍵操作可見且可用 | `reports/ux-zoom-20261028-01` IAB 快捷鍵未生效，未驗 | 在不更動系統／帳戶設定的可測瀏覽器，明確核對 200% 並驗證元件 |
| P2 HISTORY-RECOVERY | 有界歷程滿載後可證明無損恢復、冪等及 pending／ACK 保留 | 唯讀備份和身分預檢已合成測；無還原或容量釋放，hash 非認證 | 完成可驗證的恢復設計與交易／故障測試；不得自行刪除紀錄 |
| P2 INVEST-REV | 可追溯多版調查；舊資料不補造、成員缺失／變動為 unknown、容量失敗不破壞舊案與 pending | 交易保存、唯讀 API 與 UI 已接線；synthetic 已驗，UI 真瀏覽器待驗 | 恢復允許的隔離瀏覽器並驗證版本、證據狀態與焦點；不覆蓋未備份歷史 |
| P2 UX-HUMAN | 以相同任務量測操作步數、時間、錯誤 | 六情境只有自動化；無人類參與或合法競品環境 | 取得參與者與可比資料後獨立驗收，不宣稱優越 |
| P2 NATIVE／SOAK／REBOOT／DESKTOP | 分別驗證來源覆蓋、24h、重開機與桌面喚醒 | 既有 listeners partial；各需具體授權和適合環境 | 保留各自待批關卡，synthetic 不代替實機 |

此佇列是當前工作目標；既有 Codex 目標是否可繼續以平台即時狀態為準，不承諾會話外自動恢復。任何公開研究仍需核實來源與授權，禁止使用私人截圖或推送 runtime。

## 2026-10-28 競品 GUI 研究已落地，工程準備完成

本輪明確範圍為研究／文件／準備，沒有產品實作。公開來源、固定 GitHub SHA、授權與封存見 [研究](research/competitor-gui/README.md)，現況證據、每項依賴／風險／授權及驗收見 [規格](research/competitor-gui/ENGINEERING_PLAN.md)。它們是本佇列附件，不另建管理系統。

| 順序 | 工作與狀態 | 下一個具體動作 |
| --- | --- | --- |
| 1 | P1-GUI-001 DONE（synthetic 瀏覽器與定向） | Web 七來源卡片補 last_success_at/state 與 freshness；只沿用 source_status 1.0，完成六情境合成／真瀏覽器驗收。 |
| 2–3 | P1-GUI-002A/B、003A/B 合成瀏覽器已驗 | 來源缺口摘要、可點的新增高嚴重度提示；再做篩選／頁碼及返回焦點保存，按規格拆 A/B。 |
| 4–6 | P1-INVEST-004A/B 合成已驗；P2-HISTORY-001A/B/C 合成已驗（容量恢復待做）、P2-INVEST-REV-001 待做 | 已保存調查易讀化 → 有界處置歷史 → 有界案件修訂；不新增推論攻擊鏈或敏感回應。 |
| 7 | P2-UX-001 PARTIAL（六項合成自動化；人類／200% 待驗） | 在以上切片後做合成任務可用性驗收；跨產品比較待合法帳戶／可比資料及另行授權。 |

P1-GUI-001 已將 API 最後成功／新鮮度接到七來源卡片；驗收與限制見 STATUS／EVIDENCE。下一步處置歷程容量恢復及 P2-UX-001 合成量測。原生 coverage／偵測率／GUI 體驗／真環境可靠性分開量測，不宣稱超越兩家 EDR。
原生工作仍看 [WINDOWS_VALIDATION_PLAN](WINDOWS_VALIDATION_PLAN.md) 最新段：舊診斷包已 superseded，需當前 source/hash 新準備與另一次精確批准；下方「已 prepare」文字是歷史，不能直接執行。離線 GUI 工程不受此局部關卡阻擋。

## 2026-10-28 下一身分診斷的離線前置完成

P2-OS-DIAG-002已補baseline固定錯誤分類／階段／操作計數、未知與截斷守恆，27/27定向、原Job自然0／remaining0；沒有native重跑。下一次同範圍baseline方案僅prepare於reports/windows-listener-diagnostics-20261028-01，精確run/hash與唯一後續決策見WINDOWS_VALIDATION_PLAN頂部。舊P2-OS-001 partial不變、舊批准已用；新方案需另外精確批准，現在不另問或執行。可追溯調查仍以未知保留、真實覆蓋／誤報與可靠性為方向；無同條件實測不宣稱超越CrowdStrike／SentinelOne。

## 2026-10-27 原生關卡的最新狀態

P2-OS-001 已獲原具名批准並執行一次，原先待批文字不再是現況。四表ok共235列，必要程序身分缺111列／error21，partial／baseline_incomplete，完整baseline未通過；內Job自然0／外validator自然2，均remaining0／無強停。原目錄保存結果與13/13收據一致性核對（非驗收PASS），一次授權已使用。後續native診斷／重驗需另批准；既定離線切片與受測1e8f7e0 CI成果保留，不能用fixture替代身分缺口的真實查證。

## 2026-10-26 產品方向與競品差距（優先於下方歷史佇列）

使用者要求參考 CrowdStrike／SentinelOne，持續完成可用產品；listeners 單次實機批准只阻擋該觀測，不阻擋離線工程。優先差異化假說是「本機可查證、易理解、低開銷的調查閉環」，尚未證明優於任何 EDR。

官方資料讀於2026-10-26，以下均是廠商宣稱、沒有同環境實測：Falcon Insight XDR 描述跨端點／身分／雲端調查、攻擊路徑／ATT&CK 與 RTR／Fusion 回應。[CrowdStrike 官方](https://www.crowdstrike.com/en-us/platform/endpoint-security/falcon-insight-xdr/)。Singularity Endpoint 描述行為偵測、Storyline 關聯、隔離／rollback 與受控更新。[SentinelOne 官方](https://www.sentinelone.com/platform/endpoint-protection-platform/)。2026-10-21 ADR 公告列 agent/MCP inventory、traces、統一執行圖與受控回應，狀態為 early access；接上 AI／MCP 不是 EventGuard 獨有優勢。[SentinelOne ADR 公告](https://investors.sentinelone.com/press-releases/news-details/2026/SentinelOne-Launches-Singularity-Agentic-Detection-and-Response-to-Stop-Rogue-and-Malicious-AI-Agents-at-Machine-Speed/default.aspx)。

| 對照項目 | EventGuard 現有程式／證據 | 可重現量測方法與剩餘差距 |
| --- | --- | --- |
| 偵測覆蓋／良性誤報 | rules/detector.py 是唯讀 metadata 規則；尚非 EDR。investigation-metadata.json 含相似良性活動／PID重用／異host／異source／缺identity／窗外樣本 | 固定fixture與版本，分列規則命中及漏報／良性誤報；本切片只測關聯，不能用8件樣本或測試數當惡意偵測率。三產品同環境良性／攻擊資料未測 |
| 關聯正確性 | events/investigation.py；預期2件全部加入、6件負控制全排除；正常不同episode不標假矛盾。OS帳戶owner未知，跨來源／程序樹／攻擊鏈未做 | 以固定相關集合核對漏／錯加，另測缺欄位、部分來源、過期、同episode矛盾、截斷；檢查未知維持未知。不能把同host測試冒充OS跨owner測量。兩競品實際關聯正確率未測 |
| 調查完成時間 | 最終 reports/investigation-product-20261026-02：8件來源的一次CLI建案89.13ms，HTTP保存27.73ms，重開讀取7.14ms | 用monotonic記建案／保存／重開；固定來源與hash，保留各段耗時。這是單次引擎時間，非人類調查完成時間、p95或SLA；盲測分析員完成任務時間及競品皆未測 |
| 事件遺失／重複／恢復 | catalog/store同SQLite，CLI→Web→CLI及重開案件一致，8件仍pending／ACK0、只1份最新案件。歷史真04與30分鐘harness沿用原版scope | producer ID/hash→來源→案件引用→ACK各自核對，不用案件保存冒充ACK。容量回滾、成員改壞／缺失、錨點輪替測試；新版本完整長跑／reboot與競品未測 |
| CPU／RAM／磁碟 | 最終02單次建案前後自身CPU增0.0625秒，private bytes25288704→24354816、handles120→120；DB49152→57344B，案件JSON2574B | 來源入列後取自身pseudo-HANDLE快照與DB大小；不是峰值／整Job／production或受控跨產品比較。RAM下降不能當長期成長率。既有0.3433%是舊harness idle，不能套到新調查 |
| 處置批准／可追溯性 | 事件詳情保留payload/hash、as_of、engine、episode、來源及固定缺口；Web同源CSRF，allowed_actions空；人工狀態／ACK分離 | 拒絕跨scope／篡改案件／未知來源，核對保存失敗不ACK；最新快照會覆蓋舊版，尚無案件修訂歷史。沒有 RTR、隔離、rollback 或敏感動作能力，不拿較少能力當較安全的實測勝出 |

本批 P1-INVEST-001 已完成有限產品切片：152項定向／151通過／1通知圖示略過，0失敗；不是新一輪全庫結果。01有實際瀏覽器保存／重開圖，後續只修episode判定，02按最終來源重做CLI／HTTP／SQLite核對14/14；web.py與01相同。所有runtime只留reports，不提交。

P1-INVEST-002 DONE有限範圍：同事件已驗證診斷的hash／時間／query類型／來源／狀態／列數已接入1.1案件，缺失／過期／未來／空結果／partial列缺口，跨事件誤綁與保存競態拒絕，原1.0案件仍可讀。8項新診斷fixture；核心160項159pass／1skip，呈現增量52項51pass／1skip，均0fail/error；不同範圍不相加或冒充全庫。reports/investigation-product-20261026-03為最終來源18/18，含真瀏覽器保存及重開同hash、8 pending／ACK0、原Job自然0。一次CLI建案96.69ms、重開HTTP讀8.00ms，case3210B、DB增8KiB；CPU／RAM為包含fixture準備的自身兩點快照，沿用上表限制，仍非競品測量。

P2-INVEST-COVERAGE-003 DONE九案例有限範圍：29/29定向、九組source shape逐案保存／重開及獨立SQL/hash核對9/9，錯加0／漏加0、4案例維持entity/source UNKNOWN，18pending/ACK0、自有Job自然0。案例建案37.255–101.101ms、DB合計405504B，僅合成shape，仍不能外推7來源完整調查或惡意偵測率。已先push 548efe8並實查遠端，再續完成這項study；本補記亦同分支保存。下一必要真驗收為原具名listeners批准，OS owner／跨來源因果與競品同環境資料仍缺；離線僅接具體已辨識的產品缺口，不用反覆加fixture數取代真證據。

## 持續工程佇列：2026-10-26（優先閱讀）

分支feat/local-codex-acceptance；基底4a1a95b。既定真CLI receive→query→result→ACK及五層自然退出已通過；後續可靠性工作不把commit當停止條件。只在EventGuard、既有一般權限及已安裝runtime工作，未push。

| ID／優先級 | 預期成果／驗收條件 | 依賴／權限 | 現在證據與未驗範圍 | 下一個動作 |
| --- | --- | --- | --- | --- |
| P0-OWNER-SNAPSHOT-005 DONE | 暫時status缺失/舊快照不得誤綁owner或放寬控制 | 原Job/owner/control代際不變，純fixture | 鎖內selected_owner＋一次完整重觀測；原full03兩fail留存，新增2背景/3Appfixture，已通過對應回歸 | 轉下一授權關卡 |
| P2-MCP-EXIT-001 DONE | ACK flush→同Job活體HANDLE自然0 | 單事件真CLI既有授權、Windows/SDK | 真04五層exit0/三工具各1/pending0 | 來源變更受影響才複驗 |
| P2-MCP-STATUS-001 DONE | CLI/Web/Tk有界摘要；缺原證據為unknown | 同instance/read-only status，不新啟模型 | 定向、真閒置App/API/CLI/瀏覽器及原64檔不變；GUI合作退出 | 保留新舊證據界線 |
| P1-SOAK-001／GUARD-002 DONE | 拒絕保留同ID/hash、pin恢復、唯一ACK、異常先合作收尾 | synthetic新reports/privateJob | 64件有限基準＋兩輪16件/60秒守恆/自然0；故障fixture通過 | 不是OS重啟或24h |
| P2-SOAK-MEASURE-001 DONE有限範圍 | min-wall/pacing/worker自己資源有界採樣 | 無模型/網路/原生掃描 | 59有效樣本/handles111，unknown不填0；不是整Job | 接續下列CPU缺口 |
| P2-GH-PAGES-001 DONE有界契約 | 頁數/bytes/deadline共享、repo mapping、after/page安全、partial/304保護 | 公開既有來源；無token/設定改動 | 22 fixtures、201項整合、真兩頁smoke＋mapping；05完整要求未達但partial正確 | 不為洗綠再加cap；完整來源freshness另依實抓 |
| P2-IDLE-CPU-003／30M DONE自身範圍 | observer成本修正及>=1800秒真idle樣本窗 | synthetic私有Job/無模型/掃描 | 12/12；1900秒總wall、末段1802.49秒CPU0.3433%、private峰增72KiB、handles增0，獨立32/32 | 非整Job/production/24h，不再重跑短profile |
| P2-OS-001 BLOCKED／已批准並實跑不完整 | 一次native listeners baseline-only，query5秒/30秒工作預算 | 10/27人類具名批准已使用；無socket/registry/model，不能重用或自行重跑 | 四表ok共235列，identity缺111列/error21，partial／baseline_incomplete；query .739012秒，內Job自然0／外Job自然2，均remaining0／無強停；同root acceptance-crosscheck13/13只是回條一致 | 保留真實partial；固定計數無法定位身分根因，後續精確native診斷／重驗另批准，不放寬或擴來源 |
| P3-24H／DESKTOP／PUBLISH 暫緩/外部條件 | 分別真24h、既有聊天喚醒、正式發布 | 固定長時窗/受支援入口/明確push部署批准 | 尚未驗，不能由短測或新App顯示升格 | 條件具備才執行，不自行排程或承諾會話外喚醒 |

最新命令、時間、失敗恢復、證據、限制見STATUS/EVIDENCE頂部；所有reports/SQLite/native輸出留本機，保留其他Agent與既有未追蹤目錄。

## 2026-10-25：既定真收件目標已達成（最新狀態）

本段優先於下方歷史基準、未整合、等待授權與額度限制。最新直接人類指示已解除前輪兩次上限及暫停接線；本輪基底 `836d0df`、主 checkout 分支 `feat/local-codex-acceptance`。不以舊 App goal 或交接暫停文字重設最新授權；本輪未操作 App goal 控制。

`reports/service-acceptance-eventguard-development-20261025-03` 已取得一件真原生 Codex CLI 的 receive→query→保存結果→ACK：各 ID 一致、計數各 1、結果先存再 ACK、pending 0／receipts 1、無重複。CLI／worker／host／外層均有自然 exit 0／remaining 0／無強停原 HANDLE 回條。原始證據重驗與獨立核對通過，耗時 49.314 秒。本輪新授權後只啟動 1 個真 CLI 任務。

定向 guardian 54/54。完整回歸：`py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261025-05 --timeout-seconds 1800`，台北 22:48:26–22:55:41。1477 項：1474 通過、3 略過、0 failure/error；兩項 symlink 不可用、一項 notification_icon_unavailable。passed_checks=true、source_unchanged=true；guardian 自然 exit 0／remaining 0／無強停、無逐測試殘留，model_calls 0、machine_scan_executed=false。證據 `reports/verify-full-20261025-05/verification-summary.json`；提交後 source-commit.json 綁定本版受測來源。

具體修改、命令、時間及限制見 STATUS／EVIDENCE 最新段。MCP 子程序自身缺獨立退出證據、完整 IO 隔離、桌面／dot 喚醒與長期運行屬額外驗證；不能升格為已通過，也不回退既定明列的收件完成條件。兩個舊失敗與 pending 原樣保留；未 push，安全／秘密／資料保護界線繼續有效。

## 歷史目標與交接基準

更新：2026-10-25。依使用者提供的新交接與本輪唯讀增量核對修訂。
只處理EventGuard。本輪更新目標，不整合分支、不執行模型或啟用背景。

## 目標

在保留既有本機產品的前提下，整合最新已驗證修改，再取得一次真正Codex接收事件、查證、保存結果、ACK及自然退出的證據。
無事件由普通程式等待，模型呼叫為零。人類可獨立操作。模型只收既有七欄snapshot。
App不設每日五次限制。歷史budget保留，不讀寫或重設。單次驗收範圍與帳戶實際限制仍有效。

## 最新基準與已完成工作

- 主checkout：`C:\Users\yulin\Desktop\資安工具箱\EventGuard`，分支`feat/local-codex-acceptance`，HEAD `3fe81487e7aa1cbc8b18f00798dc1a86989fa5fa`。
- 最新程式：`.claude/worktrees/eventguard-handoff-increment-721d6d`，分支`claude/eventguard-quota-test-migration`，HEAD `31552977c5b2f7f5d567ab0a4e6d94bc318f9548`。
- 已完成取消日預算後的測試遷移。不要再把它列為待辦。
- `c8d42e1`完成test/idle/no-notifications的event_source綁定。CLI/Web/十工具MCP及處置保存同source；真SDK與瀏覽器合成驗證已做。不要重做。
- `3155297`修正background.stop寬限期內暫態讀取失敗的判定，保留退出與owner檢查。
- 既有完整guardian回歸：`reports/verify-full-20261025-04/verification-summary.json`，1469項、1467通過、2略過、0失敗；exit0、殘留0、model_calls0。這是無模型證據，不是真收件。
- 主與worktree的上述summary位元組一致。測試未重跑。
- 既有事件檢視、規則、四處置狀態、來源頁、通知、公告追蹤與共享App能力繼續保留。細節及限制見README、STATUS、EVIDENCE。

## 剩餘工作與執行關卡

1. 先確認整合`c8d42e1`、`3155297`至主checkout。已驗證主HEAD是worktree HEAD祖先，可fast-forward；本輪沒有執行整合。保留worktree既有未提交交接修改，不覆寫、reset或clean。
2. 重新取得`eventguard-single-test-20261025-01`的明確執行確認。使用者先前授權後又在啟動前要求交接；human-approval.json要求重新確認。提供新交接內容不等於重新授權。
3. 只有確認後才按既有AUTHORIZATION_REQUEST.md，在主checkout執行一次既有service驗收。最多一個原生CLI任務、180秒、不自動重試、不換事件/attempt/目錄。
4. 比對生成、receive、query、保存結果、ACK的同一event ID與計數。核對原始CLI JSONL、實際工具回傳、SQLite及CLI/worker/host自然退出回條。
5. 如實回報能通訊、部分通訊或不能通訊。失敗保持pending，不把metadata、登入、status、mock或模型文字當成功。
6. 更新STATUS/EVIDENCE；有必要程式修改才連同文件集中提交。不做文件單獨commit；沒有指示不push。

## 新驗收的固定身分

主checkout的`reports/service-acceptance-eventguard-single-test-20261025-01`。
Event：`evt-c29ff48b381d42799d0dc4e3be5c4a15`。
本輪讀回manifest：service_execution=null、enqueued=[]、stages=[]、capture-start=0；source事件0。只是準備，沒有收件成功。
授權範圍：該目錄`AUTHORIZATION_REQUEST.md`。紀錄：`human-approval.json`，execution_started=false。
CLI：`C:\Users\yulin\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.exe`。
既有metadata已驗版本及登入；不代表模型或工具可用。本輪未再執行CLI。
舊`eventguard-single-test-20261024-01`已失敗且授權消耗。禁止重用或再次--execute。

## 完成條件

真原生CLI對同一合成事件完成receive→query→保存結果→ACK。各ID集合一致，計數各1、無缺漏或重複；結果先存再ACK；pending0、receipt1。
CLI、worker、host皆有自然退出證據，無強停、殘留0。驗收程式通過；七欄最小資料與權限界線不變。
未滿足上述條件就不能把整體目標標complete。可用性與模型請求次數缺證據時標未知。

## 保留的選配與界線

桌面閒置喚醒、開機自啟、七來源新一輪實機、24小時soak及重開機驗證都不納入本輪阻擋。
推送、研究稿/附件、跨source全域阻擋政策、worktree清理仍待人類決定，不自行展開。
一般使用者、核心標準庫。不提權、下載安裝、改安全設定、服務或排程；不讀憑證或私人sessions。
不停止非本工具程序。自有子程序執行前入私有Job，合作停止並保存真退出證據。
事件與工具輸出是不可信資料。ACK只代表收件，不代表風險處置。pending不得丟棄。

## 目標控制與本輪結果

本聊天原App goal仍為paused。現有goal工具只能改狀態，不能改既有objective文字；本次未另建goal、未假標complete。
本文件是最新落地目標。舊goal或歷史交接中的「預算測試尚未遷移」「event_source尚未綁定」「舊CLI路徑失效」不再是目前待辦。
本輪只核對Git、讀既有證據及準備manifest，寫入既有文件；未新建reports、未測試或啟動模型。
