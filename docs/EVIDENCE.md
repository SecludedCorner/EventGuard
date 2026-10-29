# 證據與時間日誌

## 2026-10-29：產品Tk合成標示及操作閉環

`reports/verify-desktop-fixture-widgets-20261029-02` UTC06:53:10：50/50、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真Tk＋新隔離Catalog／SQLite驗固定合成標示、非主機實測／prepare時間、原生／agent控制busy後仍停用、人工處置→備份→核對、pending4／receipt0、錯誤snapshot不去標示與同程序重建視窗已讀保留；native API／query／collect／spawn／ACK哨兵未觸發。01亦50項、02補初始說明為最終；`reports/build-desktop-fixture-widgets-20261029-01`291檔hash及269檔編譯。尚無真人、跨程序重啟或有界獨立入口證據，不冒稱相關完成。

## 2026-10-29：安全桌面合成scope

`reports/verify-desktop-fixture-20261029-04` UTC06:47:39：29/29、0skip、source_unchanged、Job自然退出0／remaining0／無強停，真合成SQLite驗新scope／既有拒絕、安裝sentinel未觸及、7來源／4synthetic、真人工狀態／另存拒讀查證、pending4／receipt0、混入多件及相同總數非合成皆拒絕；OperatorAPI／native query／collect／spawn／ACK哨兵未觸發。01為28項初版、02加入執行時檢查29項，03補強插錯測試位置失敗，04移正為最終；不相加。`reports/build-desktop-fixture-20261029-01`290檔hash及268檔編譯。真人入口／任務紀錄與Tk合成標示未完成，沒有真人參與結果。

## 2026-10-29：核對上下文最終整合與普通遠端保存

`reports/verify-desktop-preview-context-final-20261029-01` UTC06:33:23：21個受影響模組173/173、0skip、source_unchanged、266檔語法通過，Job自然退出0／remaining0／無強停；真Tk／合成SQLite、檔案及自有Job API，沒有採集／模型／ACK。選取模組不同於前版229，不相加、不作全庫或真人／原生驗收。`reports/build-desktop-preview-context-final-20261029-01`288檔hash／266檔編譯。`reports/release-prep-desktop-preview-context-20261029-01`綁定f3394dfc18b67663cf6ba6780b2c6a2ca93a6446，368檔可重現，archive SHA256 b95ad172933aeca690bb8f34865b2ebed7450e1cfef7eb68c84c132854518ac0，非tag／release。

9e92d4a `feat(desktop): disclose backup verification read intervals`（相對父commit +108/−0）；c586bd7 `fix(desktop): surface known history transition conflicts`（+79/−0）；f3394df `feat(desktop): preserve event context when leaving backup checks`（+90/−0），皆逐單元build／相關測試後指定檔案commit、普通push及ff-only整合／push main，直接兩ref核對f3394df，兩工作樹與待整合差異0。完整恢復／來源可信根、Web／真人／原生關卡未驗；下一項準備安全真人桌面合成入口，不捏造參與者結果。

## 2026-10-29：返回事件上下文與Tk焦點

`reports/verify-desktop-preview-navigation-20261029-02` UTC06:28:15：48/48、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真映射Tk＋合成SQLite驗明確進入核對焦點目標、捲軸可見、返回保留事件及篩選／詳情、不增加核對讀取、DB bytes守恆；核對pending時先返回、晚到結果不搶頁。01的47/48找到映射前焦點仍在舊Text，已先完成idle幾何再focus_set，未放寬斷言。`reports/build-desktop-preview-navigation-20261029-01`288檔hash／266檔編譯；focus-lastfor不證明OS鍵盤／真人操作，沒有採集／模型／ACK。

## 2026-10-29：桌面呈現已知轉換衝突

`reports/verify-desktop-history-transition-20261029-01` UTC06:22:42：32/32、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真Tk＋合成SQLite兩筆歷程故意有不連續previous_status，備份與DB hash／前綴一致、identity_conflicts0仍正確顯已知轉換衝突1；單筆顯未觀察，多筆一致顯非完整性證明，非法計數／未知格式保留未知。DB bytes、pending2／receipt0守恆；`reports/build-desktop-history-transition-20261029-01`287檔hash及265檔編譯。無還原／清理／模型／原生採集／ACK，非真人或Web驗收。

## 2026-10-29：核對時間區間與實際Tk

`reports/verify-desktop-preview-time-20261029-02` UTC06:19:43：39/39、0skip、source_unchanged、Job自然退出0／remaining0／無強停。受控時鐘證明區間包住兩次檔案驗證與DB快照；真Tk顯正確UTC、缺失時間清舊且不補造，純呈現驗無時區／非法／逆序／未來未知，DB bytes及pending／receipt守恆。01為38/38，02加新元件斷言為最終，非相加；`reports/build-desktop-preview-time-20261029-01`286檔hash／264檔編譯。沒有額外自動讀檔、原生採集／模型／ACK，非Web或真人驗收。

## 2026-10-29：桌面備份核對最終整合及遠端

`reports/verify-desktop-history-preview-final-20261029-01` UTC06:13:02：27模組229/229、0skip、source_unchanged、263檔語法通過，Job自然退出0／remaining0／無強停；含真Tk／合成SQLite／本機暫存檔及自有Job API，不與前面重疊定向相加。`reports/build-desktop-history-preview-final-20261029-01`285檔hash及263檔編譯。`reports/release-prep-desktop-history-preview-20261029-01`綁定bff9d16f44a15487ca18c5d57b26cb50e242cefc，365檔可重現，archive SHA256 5d4b13b740163247f009b144cc5416cb854dc0c23eb3db1669548de47571ea39；無tag／release。沒有新增採集、模型或ACK，非真人／Web／原生驗收。

600ea41 `feat(desktop): verify only the last locally created history backup`（相對父commit +130/−4）；bff9d16 `feat(desktop): expose explicit backup identity checks in Tk`（+151/−7），皆逐單元build／相關測試後指定檔案commit、普通push及ff-only整合／push main，直接核對兩ref=bff9d16，兩工作樹與待整合差異0。完整恢復／容量釋放與來源認證未知；後續純文件SHA由Git歷史及忽略的source-commit.json核對。

## 2026-10-29：備份核對真Tk閉環

`reports/verify-desktop-history-preview-widgets-20261029-03` UTC06:10:19：31/31、0skip、source_unchanged、Job自然退出0／remaining0／無強停。實際Tk→真合成Catalog／備份檔，明確點選才讀、分頁開啟不讀、不披露ID、後來操作顯順序分歧、DB bytes及pending2／receipt0守恆、變檔／錯誤回條清舊成功、新備份未確認禁用。01的52/52含GUI回歸，02的15/15加入新按鈕850×620邊界，03加未確認新備份；重疊不相加。`reports/build-desktop-history-preview-widgets-20261029-01`285檔hash／263檔編譯。完整性／來源／容量／可恢復性均未知，無還原／清理／模型／採集／ACK，非真人或Web驗收。

## 2026-10-29：桌面備份核對控制層

`reports/verify-desktop-history-preview-20261029-02` UTC06:04:46：35/35、0skip、source_unchanged、Job自然退出0／remaining0／無強停；真合成SQLite／本工具暫存檔驗已存在計數、零衝突仍recoverability未知、DB bytes守恆、未知／重開controller拒絕、缺失／交易期間變動及同metadata異hash拒絕。對不符檔案身分，read哨兵證明未讀內容；CLI原receipt不新增內部file_identity欄位。01含重複繼承測試，02去重補強為最終。`reports/build-desktop-history-preview-20261029-01`284檔hash及262檔編譯；Tk按鈕仍待驗，無還原／清理／模型／採集／ACK。

## 2026-10-29：桌面處置／查證／備份最終受影響整合

`reports/verify-desktop-handling-complete-20261029-01` UTC05:58:22：25模組223/223、0skip、source_unchanged、261檔語法無誤，Job自然退出0／remaining0／無強停。真Tk＋真合成SQLite／本機暫存檔及自有Job API，不與前述重疊定向相加；無採集／新模型／ACK，非真人／Web／原生輸入。`reports/build-desktop-handling-complete-20261029-01`283檔hash及261檔編譯通過。`reports/release-prep-desktop-handling-complete-20261029-01`綁定92cc0807052f8cd35d177cdc22fa4c1ff40137c2，363檔可重現，archive SHA256 190aaf99684183b6a496b9e50bc4671614785c330dda23c6977d373b91953a82；非tag／release，目錄項耐久性及完整還原未驗。

下列各單元均先build／相關測試、指定檔案stage，再普通push開發ref與ff-only整合／push main；直接遠端核對產品兩ref為92cc080，兩工作樹及origin/main...HEAD差異0。數字均相對各父commit，包含本次新增檔；沒有以工作樹乾淨掩蓋待整合差異。後續純文件提交另由Git歷史核對。

| SHA | 完整訊息 | +／− |
| --- | --- | --- |
| 54f3f2a | feat(desktop): bind loaded handling states to saved event identity | 142／2 |
| 023644a | feat(desktop): display handling separately and refresh after decisions | 89／9 |
| d8e6e21 | feat(desktop): filter loaded events by human handling state | 97／10 |
| ee8c256 | docs(desktop): record verified handling visibility integration [skip ci] | 16／0 |
| d28d817 | feat(desktop): summarize saved diagnostic gaps without new queries | 120／4 |
| 65d9d83 | test(desktop): verify saved diagnostic summaries through real Tk | 100／0 |
| deb4948 | feat(desktop): back up handling history without changing source data | 99／1 |
| bec37d8 | feat(desktop): add explicit handling history backup controls | 115／3 |
| 4a1cab6 | fix(desktop): keep selected events visible at minimum window size | 93／10 |
| 92cc080 | fix(desktop): wrap long operation receipts to the actual window width | 62／1 |

## 2026-10-29：長備份回條的實際Tk換行

`reports/verify-desktop-message-layout-20261029-02` UTC05:55:40：46/46、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真Tk實際備份後長路徑／限制文字，在1080×760與850×620核對wraplength不超過實際label、完整所需高度、已選事件列及備份控制可見；01重現固定1000px超寬，已修正隨Configure換行。`reports/build-desktop-message-layout-20261029-01`283檔hash及261檔編譯通過；合成資料與自有視窗，非人類／原生輸入／Web200%，沒有採集／模型／ACK。

## 2026-10-29：映射Tk最小視窗事件列修復

`reports/verify-desktop-handling-layout-20261029-04` UTC05:52:29：50/50、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真映射Tk精確client1080×760／850×620，完整已選資料列及詳情文字可見、三篩選／保存／處置／備份控制未超出任何祖先邊界、Tk Tab路徑可達及自動設定分頁幾何。02找到最小視窗無事件列、03仍裁選取列6px；移設定分頁及縮放see修復，未提高最小尺寸。01只驗框線不充分，04為最終；`reports/build-desktop-handling-layout-20261029-01`282檔hash及260檔編譯通過。非人類／原生輸入或Web200%驗收，無採集／模型／ACK。

## 2026-10-29：歷程備份真Tk／合成SQLite

`reports/verify-desktop-history-backup-widgets-20261029-01` UTC05:45:50：67/67、0skip、source_unchanged、Job自然退出0／remaining0／無強停。實際Tk按鈕→真控制層／合成SQLite／本機暫存檔，驗明確點選才備份、忙碌重點只一份、hash／live範圍相符、DB bytes及pending2／receipt0守恆；真檔名碰撞不覆寫、錯誤回條不假報成功、不自動重試。`reports/build-desktop-history-backup-widgets-20261029-01`281檔hash及259檔編譯通過。備份檔含敏感識別不提交；無清理／還原／原生採集／模型／ACK，目錄項耐久性未驗，非真人或Web驗收。

## 2026-10-29：桌面歷程備份控制層與前版診斷整合

`reports/verify-desktop-history-backup-20261029-02` UTC05:42:48：65/65、0skip、source_unchanged、Job自然退出0／remaining0／無強停；真合成SQLite／檔案驗備份hash／讀回、來源DB bytes、pending1／receipt0守恆、不覆寫與非法檔名／活動失敗／缺DB拒絕。01新增測試錯用state欄位，改驗既有operation_started=False契約；`reports/build-desktop-history-backup-20261029-01`280檔hash及258檔編譯通過。僅控制層，Tk按鈕未完成，無刪除／還原／容量釋放／原生／模型／ACK。

前版`reports/verify-desktop-diagnosis-final-20261029-01` UTC05:41:27：175/175、0skip、source_unchanged、Job自然退出無殘留；`reports/build-desktop-diagnosis-final-20261029-01`279檔hash／257檔編譯。359檔可重現來源包`reports/release-prep-desktop-diagnosis-20261029-01`綁定65d9d839c73679e10e1473ac68e06faf0c0d4790，archive SHA256 ea12af4beeab4f30c54ef178239c36ec2eee1cffad884e6d2bb1c97c115237de，非release或真人驗收。

## 2026-10-29：歷史查證真Tk／SQLite閉環

`reports/verify-desktop-diagnosis-widgets-20261029-01` UTC05:38:45：81/81、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真Tk新摘要＋真合成Catalog驗partial／拒讀／截斷／current_only、重開一致、切換不串查證；故意損壞保存hash後清舊摘要／禁用處置，fixture修復後只讀恢復。DB bytes及pending2／receipt0守恆、DiagnosticAPI.query／ACK哨兵未觸發。`reports/build-desktop-diagnosis-widgets-20261029-01`279檔hash及257檔編譯通過；不是Web／真人／原生證據。

## 2026-10-29：歷史查證摘要呈現單元

`reports/verify-desktop-diagnosis-summary-20261029-01` UTC05:35:55：97/97、0skip、source_unchanged、Job自然退出0／remaining0／無強停。驗有界來源／狀態／列數／截斷／current_only、無保存／不符ID／超限未知、惡意字串惰性轉義，及既有Tk／Catalog／診斷契約回歸。`reports/build-desktop-diagnosis-summary-20261029-01`278檔hash及256檔編譯通過；新摘要的真Tk＋真合成SQLite閉環另列下一單元，無原生查詢／模型／ACK。

## 2026-10-29：桌面人工處置可見性最終整合

`reports/verify-desktop-handling-visible-final-20261029-01` UTC05:32:26：13模組158/158、0skip、source_unchanged、255檔語法無誤，Job自然退出0／remaining0／無強停；真Tk＋合成SQLite及自有Job API，不與前述重疊定向相加。`reports/build-desktop-handling-visible-final-20261029-01`277檔hash相符；`reports/release-prep-desktop-handling-visible-20261029-01`綁定d8e6e214285e3b9bf1643e25e6ecbc700e3cddfa，357檔可重現，archive SHA256 9f6d6994488acc4a9fd2203f3aa36a296f2f6526aeb8e0ad311b96d17e0c08e4。普通推送後兩ref一致，兩工作樹及對origin/main差異0；get_goal實際回讀active。未建立release或升格為真人／Web／原生驗收。

## 2026-10-29：真Tk人工狀態篩選與未知

`reports/verify-desktop-handling-filter-20261029-01` UTC05:29:32：68/68、0skip，實際Tk三篩選交集／清除、隱藏選取、保存後移出視圖及pending／receipt守恆；補強未知選項實際點選後`02` UTC05:30:39為27/27、0skip，產品來源未改，不將兩次重疊測試相加。皆source_unchanged、Job自然退出0／remaining0／無強停。presenter驗只篩前100／101截斷；`reports/build-desktop-handling-filter-20261029-01`：277檔hash及255檔編譯通過。無採集／模型／ACK，GUI操作文件描述與本次實作一致，仍非真人比較或Web驗收。

## 2026-10-29：真Tk人工狀態清單

`reports/verify-desktop-handling-list-20261029-02` UTC05:26:29：68/68、0skip、source_unchanged、Job自然退出0／remaining0／無強停；真Tk欄位＋真合成SQLite確認人工狀態與delivery分列、讀取不改DB、payload不符／缺欄未知、按鈕保存後清單刷新及選取保留。01的失敗找到清單刷新被詳情請求擋掉，已用待刷新旗標修正，非放寬驗收。`reports/build-desktop-handling-list-20261029-01`：277檔hash及255檔編譯通過；無採集／模型／ACK，非真人／Web驗收。

## 2026-10-29：清單人工狀態唯讀投影

`reports/verify-handling-projection-20261029-02` UTC05:22:53：60/60、0skip、source_unchanged、Job自然退出0／remaining0／無強停。真合成SQLite驗implicit new、保存決定、缺DB不建立、payload／delivery變動、重複與非法身分皆未知，讀取DB bytes守恆；既有真Tk人工處置回歸通過。`reports/build-handling-projection-20261029-01`來源hash及254檔編譯通過。01測試漏關SQLite連線造成cleanup錯誤，已修正；未執行原生採集／模型，尚未完成清單UI顯示。

## 2026-10-29：人工狀態最終桌面整合與目標active

`reports/verify-desktop-handling-final-20261029-01` UTC 2026-10-29 05:13:55：11個受影響模組145/145、0skip、source_unchanged、253檔語法無誤，Job自然退出0／remaining0／無強停，實際Tk元件＋合成metadata／SQLite及自有Windows Job API；人工狀態路徑不ACK，既有ACK資料另有fixture覆蓋，未原生採集／模型。`reports/release-prep-desktop-handling-20261029-01`：1ee626d6dd11e0f7883de5e953eb10ecafee9564，355檔可重現，archive SHA256 5ea9f73bc8081e695f3d354b6c21225de282f27a131f3c324247949df31ec0ea。兩ref已普通同步且工作樹／待整合差異0；get_goal回讀active、桌面優先／保留Web／普通main授權相符，未把目標編輯或push當整體產品完成／CI或真人驗收。

## 2026-10-29：真Tk人工決定與delivery守恆

`reports/verify-desktop-handling-widgets-20261029-02` UTC 2026-10-29 05:10:46：57/57、0skip、source_unchanged、Job自然退出0／remaining0。真Tk按鈕＋真Catalog／合成SQLite驗四狀態gui歷程與重開、payload hash及pending2／receipt0不變；實際提交後回條遺失，UI同ID重播不回退另一CLI決定且歷程僅2筆；實際每事件容量滿載交易回滾DB hash相同、活動故障只讀復原、忙碌重點1筆、切換不串案。01亦通過，02加強容量／重點後為最終。`reports/build-desktop-handling-widgets-20261029-01`：275檔受測hash相符、253檔編譯；未原生採集／模型／ACK，非真人或Web驗收。

## 2026-10-29：人工狀態Tk按鈕與目標恢復

`reports/verify-desktop-handling-buttons-20261029-01` UTC 2026-10-29 05:05:09：61/61、0skip、source_unchanged、Job自然退出0／remaining0；真Tk＋fixture驗四狀態點選／讀回、同ID未確認重試且無自動重送、pending保留。`reports/build-desktop-handling-buttons-20261029-01`：274檔hash相符、252檔編譯通過。目標卡透過目前聊天的支援編輯器修改／保存後，get_goal回讀status=active且內容為桌面優先；原Web目標／待驗未消失。操作依[官方進度列說明](https://learn.chatgpt.com/docs/long-running-work)，未用內部DB或browser改設定；不提交目標UI截圖。真Catalog人工狀態Tk閉環仍為下一單元。

## 2026-10-29：桌面人工狀態控制層

`reports/verify-desktop-handling-controller-20261029-01` UTC 2026-10-29 04:58:37：54/54、0skip、source_unchanged、Job自然退出0／remaining0。真臨時SQLite驗new／read／handled／ignored、gui歷程、同operation_id重播不回退較新決定、容量與活動失敗不改DB、非法狀態／key拒絕，pending1／receipt0；採集／spawn模型／ACK哨兵未觸發。`reports/build-desktop-handling-controller-20261029-01`：274檔受測hash相符、252檔編譯。只完成控制層，不當Tk按鈕／Web／真人／原生驗收；桌面目標檔更新與平台卡實際狀態分別記錄。

## 2026-10-29：桌面最終整合與可重現來源

`reports/verify-desktop-save-final-20261029-01` UTC 2026-10-29 02:33:00：10個受影響模組121/121、0skip、source_unchanged、251檔語法無誤，Job自然退出0／remaining0／無強停，fixture／合成Tk及標明的自有Windows Job API，未原生採集／模型／ACK。`reports/release-prep-desktop-investigation-20261029-01`：ce557888581a230b3ea8f12e39c60f058dec02aa，353檔可重現，archive SHA256 ea6f876554ceffcd395b17b2c060b573dfe22832aa2787d8d76efd18f75f942e。直接ls-remote兩ref一致，工作樹及對origin/main差異0；各單元增刪見STATUS，不把普通push或此包當release／CI／真人／Web／原生通過。

## 2026-10-29：桌面snapshot失敗與可恢復未知

`reports/verify-desktop-snapshot-failure-20261029-03` UTC 2026-10-29 02:30:02：61/61、0skip、source_unchanged、Job自然退出0／remaining0，真Tk驗舊來源／事件清除、筆數及設定狀態未知、詳情保存禁用、重讀恢復且原fixture設定／pending不變；01原程式重現1失敗，02／03通過。`reports/build-desktop-snapshot-failure-20261029-02`：273檔受測hash相符、251檔編譯。原生輸入另有2次有界fixture，工具inventory未暴露目標，click／keyboard=0，未冒稱通過；reports/desktop-ui-acceptance-20261029-01與02的guardian-exit均自然0／remaining0／未強停。回條不含私人視窗清單／截圖，不影響既有真Tk元件證據或新增採集／模型／ACK。

## 2026-10-29：桌面無每日quota操作說明

`reports/verify-desktop-guide-no-quota-20261029-01` UTC 2026-10-29 02:19:22：17/17、0skip、source_unchanged、Job自然退出0／remaining0。沿用現行無每日quota／automation測試；GUI及CONNECT_AGENT的舊每日預算、翌日恢復與初始化前置已改為當次任務上限與有效授權，沒有產品或帳戶設定變更／模型呼叫。來源依src/desktop.py與agent_dispatch.py，純文件另檢查本地連結／diff並沿用來源build。1940a3b80b0f785fa3858739895fc0b45fe3f00e已普通整合main並核對兩ref。

## 2026-10-29：真Tk保存／更新／重開調查

`reports/verify-desktop-investigation-widgets-20261029-03` UTC 2026-10-29 02:16:00：49/49、0skip、source_unchanged、Job自然退出0／remaining0。真Tk按鈕與真DesktopController／Catalog／合成SQLite，固定過去as_of只控制快照時鐘，所有保存交易實際執行；更新保留前版、重開一致，容量失敗DB hash及pending2／receipt0保留，切換事件不串案，採集／子程序／模型／ACK哨兵未觸發。01因fixture超出既有刷新限制與清理問題有3error／3fail，02修正後2個標籤斷言失敗，03核對實際「成員與保存雜湊相符（非來源認證）」後通過。`reports/build-desktop-investigation-widgets-20261029-01`：273檔受測hash相符、251檔編譯成功；真人、Web與原生不升格。

## 2026-10-29：桌面保存按鈕與worker

`reports/verify-desktop-investigation-button-20261029-01` UTC 2026-10-29 02:09:40：82/82、0skip、source_unchanged、Job自然退出0／remaining0。真Tk按鈕＋fixture驗未選取／讀取中／忙碌禁用、雙點只保存一次並只讀重載、容量失敗訊息不洩例外且可再操作，pending不變；控制層真合成SQLite測試沿用同批。`reports/build-desktop-investigation-button-20261029-01`：272檔受測hash相符、250檔編譯通過。acadbaa3b6dae805ac733c22e9886c6fbe9353fe已普通merge／push並核對main／開發ref一致。按鈕尚未與真Catalog合併驗證；Web／真人／原生待驗保留。

## 2026-10-29：桌面保存調查控制層

`reports/verify-desktop-investigation-controller-20261029-01` UTC 2026-10-29 02:05:42：64/64、0skip、source_unchanged、Job自然退出0／remaining0。全新臨時root的合成事件，真DesktopController／EventCatalog／SQLite驗明確保存與重開、活動目標僅hash、容量失敗舊DB hash保留、活動失敗不啟動保存、缺事件不補造，pending2／receipt0；採集、子程序／模型與ACK哨兵未觸發。`reports/build-desktop-investigation-controller-20261029-01`：272檔受測hash相符、250檔編譯通過。尚未接桌面按鈕，不當UI驗收；Web／真人／原生仍各自待驗。

## 2026-10-29：清單main整合與單次瀏覽器核對

df55da8bb06bca06853b3b0fb9354e4a340717c4已普通ff-only merge／push main，直接ls-remote核對main及開發ref一致，未提交及對main差異0。`reports/release-prep-web-list-read-state-20261029-01`：351檔可重現，archive SHA256 1036c260d8422bc0470f078e2a706464576f110bc353365d8e3f76459a0ec739；`reports/build-web-list-javascript-20261029-01`完整served JS語法通過、Job自然退出0／remaining0／無強停。同目錄browser-state.json只保存單次cua.getState的去識別錯誤：browsers=[]、Work settings disabled；不保存私人視窗清單／截圖。42項離線通過不能證明真瀏覽器／200%／真人／原生。目標盤點明列未達成及外部解除條件，未冒稱完成。

## 2026-10-29：事件清單失敗／提示隔離

`reports/verify-web-list-read-state-20261029-03` UTC 2026-10-28 19:59:51：42/42、0skip、source_unchanged、Job自然退出0／remaining0。Node執行實際events／invalidateEventList／refresh，合成驗失敗未知、停用分頁／隱藏詳情、錯誤／重複ID、計數不符、零列非安全、慢回覆不覆蓋，以及notice失敗仍能更新清單。01為原程式重現失敗；02fixture缺實際helper為41/42，03補入後通過。`reports/build-web-list-read-state-20261029-01`：271檔受測hash相符、249檔編譯成功。未新增採集／模型／ACK，非瀏覽器、人類或原生驗收。

## 2026-10-29：Web修正普通整合與來源包

直接ls-remote核對main及feat/local-codex-acceptance=87f7575915a9f0fed0d53ad788b256e1fc44b909，普通ff-only merge／push，未提交及對main差異0。`reports/release-prep-web-read-state-20261029-01`：350檔可重現，archive SHA256 9ec057a1c8404f9758e93d6977f391a575824ef498eca213ddcc536bc621e5bd。`reports/build-web-javascript-20261029-02`完整served JS以Node --check通過，Job自然退出0／remaining0／無強停；01自寫驗證回條使用不支援reason，未列通過，02改用既有test_teardown為最終。相關41與44項重疊，不相加；真瀏覽器、CI、真人及原生結果均不由此推定。

## 2026-10-29：Web來源卡片讀取失敗離線行為

`reports/verify-web-source-read-state-20261029-02` UTC 2026-10-28 19:52:57：44/44、0skip、source_unchanged、Job自然退出0／remaining0。實際JS sources／node／時間函式以synthetic DOM/API驗拒讀後歷史成功、過期、未知／缺失／無效／未來時間、零列、HTML樣式文字；缺來源／重複／空資料及HTTP錯誤不留舊成功，慢成功／失敗不覆蓋新資料。01本地化日期斷言錯誤為43/44，02修正fixture比較後通過。`reports/build-web-source-read-state-20261029-01`：270檔受測hash相符、248檔編譯成功。這不是瀏覽器／人類可用性／原生驗收；既有待驗不變。

## 2026-10-29：Web詳情失敗離線行為

`reports/verify-web-detail-read-state-20261029-03` UTC 2026-10-28 19:49:34：41/41、0skip、source_unchanged、Job自然退出0／remaining0。實際JS詳情／delivery與按鈕處理器在Node＋synthetic DOM/API驗同案失敗清除、未知／停用、重試、錯案ID、晚到結果及未確認時不送保存請求；非瀏覽器。`reports/build-web-detail-read-state-20261029-02` 269檔hash相符、247檔編譯。01／02通過後發現混合換行被寫檔正規化，保存原未改行bytes移除無關diff，03為最終；blocker回條留reports，未放寬diff檢查或UI驗收。

## 2026-10-29：main同版本桌面／歷程整合

已普通ff-only merge／push並直接核對main與開發ref=dd4deebaa9846b61f29974d64436c3c83563b589；未提交及對origin/main差異皆0。`reports/verify-main-desktop-history-20261029-01` UTC 2026-10-28 19:42:14：13個受影響模組131/131、0skip、source_unchanged、246檔語法無誤，Job自然退出0／remaining0／無強停，未原生採集／模型／ACK。`reports/release-prep-history-transition-preview-20261029-01`：348檔可重現，source-commit.json保存直接遠端核對與各次來源差異，較早單元後續受其他提交改動的hash未冒稱仍相同。本節純文件沿用來源build，Web／真人／原生與完整恢復仍未驗。

## 2026-10-29：CLI唯讀相鄰轉換預檢

`reports/verify-history-transition-preview-20261029-03` UTC 2026-10-28 19:39:22：34/34、0skip、source_unchanged、Job自然退出0／remaining0。合成JSON／中文CLI驗前綴及身分相符仍可存在轉換衝突，逐事件交錯／noop與空集合正確，未知範圍明示；讀前後DB hash、pending／receipt不變。01錯誤指定不存在的test_presentation未執行且build無manifest，未冒稱成功；02為33/33，最終03及`reports/build-history-transition-preview-20261029-02` 268檔hash相符／246檔編譯通過。真實恢復與來源認證仍未驗。

## 2026-10-29：歷程轉換衝突拒絕

`reports/verify-history-transition-order-20261029-02` UTC 2026-10-28 19:36:56：35/35、0skip、source_unchanged、Job自然退出0／remaining0，合成內部恢復／備份／保存整合。01先驗證重算hash但轉換不連續的備份可被錯誤接受；修正後寫入前拒絕且目標DB hash／pending1／receipt0不變，既有前綴／冪等／容量回滾測試通過。`reports/build-history-transition-order-20261029-01`：268檔受測hash相符、246檔編譯通過。來源認證、使用者入口、容量釋放與實機恢復未完成。534d0f19230e251895981699daa3a386c556166c已普通整合並核對main／開發ref一致，348檔來源包可重現見`reports/release-prep-desktop-detail-failure-20261029-01`。

## 2026-10-29：桌面詳情讀取失敗／切換

`reports/verify-desktop-detail-failure-20261029-04` UTC 2026-10-28 19:33:53：79/79、0skip、source_unchanged、Job自然退出0／remaining0。真Tk驗讀取中不留舊案、失敗未知且不補pending／不洩漏例外、同列重試、身分不符與晚到錯誤、快速切回原事件；未採集／模型／ACK，pending保留。01先重現2失敗，02為77/77、03為78/78、最終04為79/79。`reports/build-desktop-detail-failure-20261029-02`：268檔受測hash相符、246檔編譯成功。前單元56786b40542f9f374186bf91e6a8cc5a035a0a67以ff-only merge整合並普通push main，ls-remote核對兩ref一致；348檔來源包可重現，見`reports/release-prep-desktop-source-consistency-20261029-01`。Web／真人／原生驗收未升格。

## 2026-10-29：桌面來源一致性

`reports/verify-desktop-source-consistency-20261029-05` UTC 2026-10-28 19:27:20：77/77、0skip、source_unchanged、Job自然退出／remaining0。新拒讀取代舊overview成功、過期拒讀歷史、損壞／test不供live、保存失敗不當ok，並在真Tk表格核對狀態／零筆／成功時間／原因與摘要；讀前後保存檔hash相同，採集入口哨兵未觸發。`reports/build-desktop-source-consistency-20261029-01`：268檔hash相符、246檔編譯。01／03固定fixture在wallclock未來造成2／1失敗，02／04及最終05通過；未放寬產品時間保護，原失敗保留。

## 2026-10-29：缺失／變更證據到桌面元件

`reports/verify-desktop-evidence-changes-20261029-01` 79/79；02於UTC 2026-10-28 19:19:01為最終新增模組2/2，0skip、source_unchanged、Job自然退出／remaining0。真SQLite＋EventCatalog＋Tk驗關聯member刪除／payload變更後最新案與前版皆未知，讀前後hash及pending不變。`reports/build-desktop-evidence-changes-20261029-01`：267檔受測hash相符、245檔編譯成功。未把component／合成測試當Web、真人或實機驗收。

## 2026-10-29：桌面前版調查元件驗證

`reports/verify-desktop-revision-summary-20261029-02`：85/85、0skip、source_unchanged，Job自然退出／remaining0。真Tk＋合成EventCatalog建立兩版後驗保存前版呈現、未知時清除與pending保留；純呈現驗4版只顯示3版、成員相符與診斷變更分列、缺失／不符身分不顯錯案及時間未知。`reports/build-desktop-revision-summary-20261029-01` 266檔受測hash相符、244檔編譯通過；非真人／Web驗收。

## 2026-10-29：桌面保存時間線元件驗證

`reports/verify-desktop-saved-timeline-20261029-02`：91/91、0skip、source_unchanged，Job自然退出／remaining0。實際Tk配合合成EventCatalog驗保存項目，純呈現驗快照順序、不推因果、缺失／變更未知、拒讀／partial，以及16項時間線／8項缺口限制；不改輸入、不ACK。`reports/build-desktop-saved-timeline-20261029-02` 266檔hash相符、244檔編譯。原01為新增來源可見性前的91/91，最終來源以02為準。Web／真人／原生待驗不變。

## 2026-10-29：桌面處置與歷程只讀呈現

`reports/verify-desktop-handling-summary-20261029-01` UTC 2026-10-28 19:07:52：84/84、0skip、source_unchanged，Job自然退出／remaining0；真Tk＋fixture驗handled與pending並存、歷程未知清除舊內容、唯讀顯示，純呈現驗10筆只顯示最後8筆及容量／未知語意。`reports/build-desktop-handling-summary-20261029-01` 266檔hash相符、244檔編譯；不提供真人／Web驗收。前單元e4ecad7已推開發ref並核對，工作樹曾清空、對main差異85行。

## 2026-10-29：桌面保存調查摘要元件驗證

`reports/verify-desktop-investigation-summary-20261029-02` UTC 2026-10-28 19:05:37：87/87、0 skip、source_unchanged，Job自然退出／remaining0。實際 Tk 唯讀文字元件＋fixture 驗保存案、成員未知／診斷缺失／過期分列，以及切換至無案時清除舊案；純呈現另驗錨點身分與異常欄位。`reports/build-desktop-investigation-summary-20261029-01`：266檔受測hash相符、244檔編譯。未採集／模型／ACK；非瀏覽器、人工桌面版面或鍵盤驗收。

## 2026-10-29：完整回歸通過並普通推送 main

遠端 main 直接核對為 `93910625f509b43a4aae7ee22abe58c3e1e9e5b8`，普通 merge 父 c80a4be／66638ae，50 檔 +3971/−72。已將隔離工作樹回條複製至原專案 `reports/main-integration-20261029-01`，包含首輪1失敗、第二輪1736通過／2 symlink skip／0失敗、兩組來源包與build結果；第二輪Job自然退出0／remaining0／未強停，來源266檔hash相符、244檔編譯、346檔來源包可重現。開發分支ff同步main後對origin/main diff為0；無force push／tag／release。後續純文件保存不改變受測產品來源，CI與所有真人／原生關卡另驗。

## 2026-10-29：修正合成範例的 checkout 路徑假設

首輪 `reports/verify-main-integration-20261029-01` 位於隔離工作樹，shipped facts example 被 `.codex` 路徑保護拒讀，整合暫停。測試把同一公開範例複製到測試臨時目錄；產品路徑限制未變。`reports/verify-inventory-fixture-location-20261029-02` UTC 18:50:36：16/16、0 skip、source_unchanged，Job 自然退出／remaining 0；01 命令因不存在模組被 parser 拒絕，未執行測試。`reports/build-inventory-fixture-location-20261029-01` 當前266檔hash相符、244檔編譯成功。完整整合待修正後重驗。

## 2026-10-29：分支差異上限與 main 整合授權

直接核對遠端 main=c80a4be90c7e9893544e72fab04c12e7653b33cc、開發分支=c83ff950e59646c0de48fce907b43bee2a89ecfa；本機與遠端 SHA 相符。`git diff origin/main...HEAD --shortstat`：49 檔 +3936/−71，工作樹／index 相對 HEAD 無差異。使用者明確批准測試通過後普通 merge／push main；本次先保存規則，完整整合與測試另記。

## 2026-10-29：桌面保存詳情資料接線

`reports/verify-desktop-saved-detail-20261029-01` UTC 2026-10-28 18:35:58：75/75、0 skip、source_unchanged，Job 自然退出 0／remaining 0。合成臨時資料驗保存調查／修訂／歷程返回及讀前後 SQLite hash 不變、pending 保留；非實機採集或真人桌面測量。`reports/build-desktop-saved-detail-20261029-01`：266 檔 hash 相符、244 Python 編譯通過，含當前修改；友善調查摘要尚未實作。

## 2026-10-29：持續執行佇列更新

MAINTENANCE_GOAL、CLAUDE 更新持續推進順序，原目標與所有待驗關卡保留；平台目標卡片編輯未成功，仍 blocked。`reports/release-prep-continuous-goal-20261029-01` 父來源 5208415，346 檔 build 可重現；`reports/verify-continuous-goal-20261029-01` UTC 18:33:16（台灣 10/29 02:33），8/8、0 skip、Job 自然退出／remaining 0。文件 diff 與連結另檢，非產品新驗收。

## 2026-10-29：桌面來源缺口摘要

`reports/verify-desktop-source-gaps-20261029-01` UTC 2026-10-28 18:28:05：75/75、0 skip、source_unchanged；真 Tk＋fixture 核對摘要刷新、拒讀／過期重疊、缺失來源與不可信狀態維持未知，沒有新採集或模型，Job 自然退出／remaining 0。`reports/build-desktop-source-gaps-20261029-01` 綁定當前受測 manifest 266 檔、編譯 244 檔；非 exe 或真人 UI 驗收。前單元 e72c494 已推送且遠端一致（+105/−5）。

## 2026-10-29：桌面七來源歷史成功時間

`reports/verify-desktop-source-history-20261029-01` UTC 2026-10-28 18:25:19：74/74、0 skip、source_unchanged，Job 自然退出 0、remaining 0、無強停。控制器測試以保存的成功後拒讀資料核對歷史不丟、唯讀 hash 不變，採集入口設失敗哨兵；真 Tk 元件＋fixture 驗六情境與七來源欄位，不是主機採集或真人操作。`reports/build-desktop-source-history-20261029-01`：受測 manifest 266 檔 hash 相符，244 Python 檔編譯成功，包含本次未提交產品／測試變更。瀏覽器與 200% 未驗；未提交私人圖片或 runtime。

## 2026-10-29：修改上限與新增工具診斷

本次從乾淨 HEAD 02725aa 接續，規則明定未提交新增＋刪除不得超過 500 行，不取代單一 commit 約 200 行。原生工具實際執行視窗 Raise／還原，成功讀到設定與開啟的瀏覽器控制；中途出現 `window bounds changed`、控制項快取失效及目標觀察不一致，未改權限，未取得可靠瀏覽器存取。本記錄僅保存錯誤類型；私人畫面與內容未寫入專案。產品驗收不因這次診斷升格。

`reports/release-prep-diff-limit-20261029-01`：父來源 build 可重現、346 檔；`reports/verify-diff-limit-20261029-01`：2026-10-29 01:34（UTC+8）、8/8、0 skip、Job 自然退出／remaining 0。檢查限包裝與文件，不是瀏覽器操作驗收。

## 2026-10-29：授權提醒與狀態歸因更正

CLAUDE.md 保存專案既有操作與不重複詢問規則，未提交私人圖片或單次執行授權回條。使用者提供畫面中的瀏覽器控制開啟；工具仍回報停用，不能據此認定使用者未授權，根因未明。`reports/release-prep-permission-reminder-20261029-01`：父 SHA df56808，346 檔來源 build 可重現；`reports/verify-permission-reminder-20261029-01` UTC 17:23:12（台灣 10/29 01:23）：8/8、0 skip、244 AST、source_unchanged，Job 自然退出 0／remaining 0。本次文件另做 diff／本地連結檢查；這些檢查不提供產品 UI 或真實環境驗收。

## 2026-10-28：修訂元件可重跑 synthetic 行為測試

`reports/verify-revision-renderer-reusable-20261028-01` UTC 11:29:27，21/21、0 skip、244 AST、source_unchanged；Job 自然 0／remaining 0／無強停。測試直接擷取實際 renderer 於合成 DOM 執行，驗證診斷變更與成員相符分列、partial、同事件重繪焦點／展開、外部焦點與切事件；既有 Node 受私有 Job 管理。這不是瀏覽器、版面、可及性或真實使用者驗收。

## 2026-10-28：修訂摘要診斷狀態合成測試

`reports/verify-revision-diagnostic-summary-20261028-01` UTC 11:27:37，26/26、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-diagnostic-summary-dom-20261028-01/run.js` node exit 0，五種診斷狀態均出現在實際 renderer 的合成 summary 中；非瀏覽器、無版面或鍵盤證據。

## 2026-10-28：前版診斷結果語意合成測試

`reports/verify-revision-diagnostic-result-20261028-01` UTC 11:26:05，28/28、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-diagnostic-result-dom-20261028-01/run.js` node exit 0：實際 renderer 的 observed／partial／未知三組 synthetic DOM；不是瀏覽器或真實診斷。

## 2026-10-28：歷程預檢 JSON 歧義測試

`reports/verify-history-preview-duplicate-20261028-01` UTC 11:23:39，35/35、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic CLI 驗證頂層及 namespace 巢狀重複欄位拒絕，正常備份仍通過，DB／pending／ACK 不變；不代表來源認證或可還原性。

## 2026-10-28：歷程預檢實際 CLI 合成路徑

`reports/history-preview-real-cli-20261028-03/summary.json`：PowerShell 7 `Get-Content -Raw` 管線 → EventGuard.cmd → 真 CLI，在專用 synthetic source 顯示 exact_prefix／1 已存在／recoverability unknown、不輸出 event／operation ID；DB SHA256 前後 57e5bb4065816cb369753eae5efb19c75ee52efcd91bb5b5968b2abf5914b8a8，pending 1／ACK 0／model 0／native 0，原私有 Job 自然 0／remaining 0／無強停。`...-02` 直接 stdin 檔案 handle 亦通過。首次 `...-01` CLI 已輸出結果，但驗收輔助程式傳入無效 Job 退出原因導致回條未保存，原 Job 殘留狀態未確認；不列為完整通過。無真實資料驗收。

## 2026-10-28：歷程預檢未知欄位合成測試

`reports/verify-history-preview-unknown-20261028-01` UTC 11:18:26，10/10、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic JSON 在零身分衝突下仍將來源、歷程完整性、容量與可還原性標記 unknown，未還原、未授權。

## 2026-10-28：歷程預檢與還原前綴一致性

`reports/verify-history-preview-order-20261028-01` UTC 11:14:43，13/13、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 目標短前綴回 exact_prefix、分歧回 diverged 並與內部 restore 接受／拒絕一致；CLI 不輸出識別資料。不是來源認證、歷程涵蓋完整性或可還原性驗證。

## 2026-10-28：歷程完全前綴合成測試

`reports/verify-history-restore-prefix-20261028-01` UTC 11:10:51，15/15、0 skip、243 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 一筆前綴後只追加缺失尾段，重開重播不增列；已有不同後續操作的目標拒絕，bytes／pending／ACK 保留。沒有真實資料操作、來源認證或容量釋放。

## 2026-10-28：歷程還原 EventStore 合成交易

`reports/verify-history-restore-integration-20261028-01` UTC 11:08:45，42/42、0 skip、242 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 內部交易核對初始／寫後容量不足回滾、重開操作識別重播、原來源與 pending／ACK 不變；無入口、來源認證或真實還原，不能用它宣稱滿載已恢復。

## 2026-10-28：歷程追加還原原件合成測試

`reports/verify-history-restore-primitive-20261028-02` UTC 11:05:31，18/18、0 skip、241 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 兩資料庫核對原事件身分、完整前綴、無綁定／scope／hash 拒絕、容量不足、中途失敗 savepoint 回滾、呼叫端 rollback／commit、重播及 pending／ACK。未接產品入口；未認證備份來源、未檢驗實際 DB 容量／長期恢复、未釋放容量。

## 2026-10-28：歷程備份 stdin 預檢合成測試

`reports/verify-history-preview-cli-20261028-02` UTC 11:01:42，38/38、0 skip、239 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic CLI 測合法彙總、錯 scope／修改 hash／超限拒絕、互動 stdin 不等待、無識別輸出、DB／pending／ACK 不變；非還原、容量或真實使用者資料驗收。

## 2026-10-28：調查保留政策提示合成回歸

`reports/verify-investigation-retention-copy-20261028-01` UTC 10:59:13，62/62、0 skip、238 AST、source_unchanged；Job 自然 0／remaining 0／無強停。核對目標元件文字與既有有／無修訂的保留測試，不代表已在瀏覽器顯示，也不代表容量恢復已實作。

## 2026-10-28：修訂診斷 HTTP GET 合成測試

`reports/verify-revision-diagnostics-http-20261028-01` UTC 10:56:47，17/17、0 skip、238 AST、source_unchanged、Job 自然 0／remaining 0／無強停。synthetic loopback GET 驗證 prior evidence_status=saved_snapshot 與 diagnostic_evidence_status=changed 分開，DB bytes 相同、pending 2／ACK 0／model 0；非瀏覽器。

## 2026-10-28：修訂診斷呈現合成驗證

`reports/verify-revision-diagnostics-web-20261028-01` UTC 10:55:18，25/25、0 skip、238 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-diagnostics-dom-20261028-01/run.js` node exit 0：5 種診斷狀態與保存摘要、未知及非安全聲明；合成 DOM 不是瀏覽器或原生資料。

## 2026-10-28：修訂診斷狀態合成測試

`reports/verify-revision-diagnostics-20261028-02` UTC 10:53:47，22/22、0 skip、238 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 以已保存診斷核對匹配、變動、缺失、舊 schema 未綁定，以及未提供診斷時 unknown；DB／pending／ACK 不變。未重新採集或執行模型；Web 尚未顯示。

## 2026-10-28：修訂重繪合成 DOM

`reports/verify-revision-refresh-20261028-02` UTC 10:51:46，29/29、0 skip、237 AST、source_unchanged，Job 自然 0／remaining 0／無強停。`reports/revision-refresh-dom-fixture-20261028-01/run.js` node exit 0、3 情境直接執行實際 renderer：新增版本後同 ID 保留、外部焦點不搶、切事件不保留；非真瀏覽器。首次 `...-01` 一項測試錯誤，靜態測試仍尋找舊函式簽名；更新為新簽名後重驗通過。

## 2026-10-28：修訂穩定識別合成回歸

`reports/verify-revision-stable-id-20261028-01` UTC 10:49:46，34/34、0 skip、237 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 重讀 revision_id 穩定、source DB 不變；未測 UI 展開或瀏覽器。

## 2026-10-28：修訂呈現合成 DOM fixture

`node reports/revision-web-dom-fixture-20261028-01/run.js` exit 0、3 情境：未知、無歷程、已保存版本的缺失／中文缺口／容量滿載與文字；直接擷取當前程式的 renderInvestigationRevisions 和固定標籤執行合成 DOM。不是瀏覽器或可及性驗收，不提供版面、焦點、資料庫、實機、模型或 ACK 證據。

## 2026-10-28：案件修訂缺口標籤 WIP

`reports/verify-investigation-revision-gap-labels-20261028-02` UTC 10:44:47，43/43、0 skip、237 AST、source_unchanged；Job 自然 0／remaining 0／無強停。`reports/revision-web-javascript-check-20261028-02/app.js` Node --check 0；僅語法及靜態元件契約，不是真瀏覽器。首次 `...-01` 42/43，因共用標籤移出函式後舊靜態測試仍限定字串位置，更新為核對共用標籤與目標引用後重驗通過。

## 2026-10-28：修訂後完整合成回歸

`reports/verify-full-revision-20261028-01/verification-summary.json`，來源 `d0faaf1b156d7344e0571696eebc5c728e9dcf62`，UTC 10:41:02，1715 run／1712 pass／3 skip／0 fail/error，237 AST、source_unchanged、636.987 秒；2 symlink unavailable、1 notification_icon_unavailable。Job 自然 0／remaining 0／無強停，machine_scan_executed=false、model_calls=0。`reports/release-prep-revision-20261028-01` 精確來源 339 檔、可重現 archive SHA256 887d7e8b758e455bcb68fb16bacba162acd0ad002660dbf43b3f0ca47c71a299。此證據不驗修訂 UI、原生覆蓋、24h、重啟、桌面喚醒或競品。

## 2026-10-28：調查容量錯誤回報測試

`reports/verify-investigation-revision-capacity-error-20261028-02` UTC 10:29:30，49/49、0 skip、237 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成 loopback POST 注入容量錯誤取得 HTTP 503／investigation_capacity，DB bytes 不變；中文提示只檢查目標腳本，尚未在真瀏覽器執行。

## 2026-10-28：全域上限與並行更新合成測試

`reports/verify-investigation-revision-concurrency-20261028-02` UTC 10:26:43，17/17、0 skip、237 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 原件建立 16 個事件各 16 筆，全球第 257 筆拒絕且原數不變；兩執行緒更新保留原始及兩新版快照，pending／ACK 不變。首次 `...-01` 一測試失敗，原因是預期時間缺少保存格式的微秒；修正測試格式後重驗通過。未測跨程序／長時負載，無容量釋放。

## 2026-10-28：有修訂錨點保留合成測試

`reports/verify-investigation-revision-retention-20261028-03` UTC 10:24:57，61/61、0 skip、236 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成 DB 核對 ACK 錨點期限、空間輪替、數量輪替不刪及版本／當前案件／事件不變，無修訂事件既有到期測試仍過；不代表永久歸檔或無損容量恢復。首次 `...-01` 使用不存在的 test_event_store 模組，參數檢查拒絕且未起 worker；換成實際模組後 `...-02`／`...-03` 各 61/61。

## 2026-10-28：案件修訂 Web WIP 與瀏覽器阻擋

`reports/verify-investigation-revision-web-20261028-01` UTC 10:21:28，46/46、0 skip、236 AST、source_unchanged；Job 自然 0／remaining 0／無強停；僅元件靜態契約與合成 API，非 JavaScript／瀏覽器驗收。`reports/investigation-revision-browser-20261028-01` 合成 DB 準備好後本機瀏覽器因 Work settings 禁用，未進頁；伺服器合作退出、Job 自然 0／remaining 0／無強停、0 POST／native／model、DB SHA256 前後 9565ba61b68544acb447b85f98c3ce7f0473e6007a0c7ae663f45b125a1355ee。不得視為瀏覽器通過。

## 2026-10-28：案件修訂事件詳情唯讀 API

`reports/verify-investigation-revision-api-20261028-01` UTC 10:19:28，67/67、0 skip、236 AST、source_unchanged；Job 自然 0／remaining 0／無強停。synthetic 舊庫與保存版本、真 loopback GET 與 catalog 相同、DB bytes 不變、模型 0；未驗 UI、過期 anchor、全域容量與併發。

## 2026-10-28：案件修訂唯讀合成回歸

`reports/verify-investigation-revision-read-20261028-01` UTC 10:17:54，34/34、0 skip、236 AST、source_unchanged，Job 自然 0／remaining 0／無強停。synthetic 驗證舊表缺失不建立、前版重讀及來源 bytes 不變、成員消失或更改 unknown、損壞 hash unknown、pending／ACK 未變。尚未接 API／Web、真機及 anchor 過期恢復。

## 2026-10-28：案件修訂交易保存合成回歸

`reports/verify-investigation-revision-integration-20261028-03` UTC 10:16:28、56/56、0 skip、234 AST、source_unchanged；Job 自然 0／remaining 0／無強停。合成 SQLite 核對前版內容與保存時間、重複快照不增列、16 筆滿載、容量前後回滾、損壞舊案拒絕及 pending／ACK 不變。首次 `...-01` 有 2 errors：測試重新產生 synthetic event 導致 payload 身分不同；固定使用原 fixture 後 `...-02` 36/36、`...-03` 56/56。未測全域滿載、並行、舊 anchor 過期修訂讀取或 UI。

## 2026-10-28：修訂儲存原件合成測試

`reports/verify-investigation-revision-store-20261028-01` UTC 10:13:48、29/29、0 skip、233 AST、source_unchanged；私有 Job 自然 0／remaining 0／無強停。SQLite 合成測驗證必須由呼叫端交易控制、不自行提交、回滾、不可信快照拒絕、16 筆容量與位元組上限。全域滿載、實際 DB 增量／ACK 保留與產品接線尚未驗。

## 2026-10-28：有界案件修訂純契約

`reports/verify-investigation-revision-contract-20261028-02` UTC 09:53:30、33/33、0 skip、231 AST、source_unchanged；私有 Job 自然退出 0／remaining 0／無強停。合成測試涵蓋 1.0／1.1 case、錨定事件與 hash、偽造／超限／非法時間及筆數上限。純函式無資料庫讀寫；未測版本實際保存、競態、容量故障、歷史讀取或瀏覽器。SHA256 非簽章。完整缺口與下一步見 `docs/MAINTENANCE_GOAL.md`。

## 2026-10-28：調查更新限制瀏覽器驗收

`reports/verify-investigation-retention-warning-20261028-03` UTC 09:51:31，35/35、0 skip、229 AST、source_unchanged，Job 自然 0／remaining 0／無強停。`reports/investigation-retention-ui-20261028-01`：合成事件「查看」後，事件調查區域的提示與建立／更新按鈕皆可見，提示位於按鈕前；只做 GET，SQLite SHA256 前後 ED790B81DE89B668DE32121DB789F2E8CE72D64A1C688689574743B5A5B697E0，0 POST／native／model；私有 Job 自然 0／remaining 0／無強停。一次瀏覽器 DOM 屬性查詢因控制介面不支援 `compareDocumentPosition` 失敗，改用實際可見性及頁面快照核對順序。

`reports/ux-zoom-20261028-01`：IAB 執行縮放快捷鍵及還原基準後，innerWidth 均 1280、devicePixelRatio 均 1.5，無法證明 200% 縮放；故未通過該關卡。合成 DB hash 前後相同，0 POST／native／model，私有 Job 自然 0／remaining 0／無強停。

## 2026-10-28：歷程備份身分預檢合成測試

`reports/verify-history-backup-preview-20261028-01` UTC 09:44:42，19/19、0 skip、229 AST、source_unchanged；Job 自然退出 0／remaining 0／無強停。比對合成 SQLite 實際事件內容與備份、缺失／未綁定／衝突／舊範圍 unknown；來源 DB／pending／ACK 未變。預檢不驗證容量、順序、來源真實性，不能宣稱已完成還原。

## 2026-10-28：明確歷程備份 CLI 與 namespace

`reports/verify-history-backup-cli-20261028-03` UTC 09:42:38，42/42、0 skip、228 AST、source_unchanged；Job 自然退出 0、remaining 0、無強停；synthetic 驗證 CLI 明確呼叫、摘要不洩識別、缺庫不建立、既有檔不覆寫、原 DB 不變，以及 1.1 namespace 綁定／1.0 unknown。先前 `--module test_presentation` 指定不存在的模組，參數檢查即失敗，未啟動測試 worker；已改為實際模組重驗。真 junction／斷電持久性、還原和容量釋放均未驗，hash 非簽章。

## 2026-10-28：歷程備份不覆寫合成測試

`reports/verify-history-backup-file-20261028-02` 25/25／0 skip／228 AST／source_unchanged、Job 自然 0／remaining 0／無強停。synthetic 測驗證後 reports 落盤／重讀、既有目的地不覆寫、無效內容拒絕、link 失敗只清自建暫存、模擬 junction 拒絕、DB／pending／ACK 不變。實際 junction 與意外斷電後目錄項 durability 未驗；不以 hash 宣稱防竄改或認證，未提供還原或自動清理。

## 2026-10-28：歷程快照驗證核心

`reports/verify-history-backup-validation-20261028-02` 20/20／0 skip／226 AST／source_unchanged、Job 自然 0／remaining 0／無強停；synthetic 測合法快照、內容竄改、重複 operation ID、狀態錯誤、非 ASCII hash、損壞來源及唯讀。資料完整性 hash 不提供認證或防竄改；尚無可持久保存的檔案或恢復流程。

## 2026-10-28：歷程唯讀快照前置

`reports/verify-history-backup-payload-20261028-01` 45/45／0 skip／226 AST／source_unchanged，Job 自然 0／remaining 0／無強停；合成 SQLite 測明確 query-only 交易、舊表無資料、操作順序／no-op／未綁定 hash、canonical hash、損壞拒絕、原 DB bytes 與 pending／ACK 不變。此版本僅產生記憶體 payload，尚無備份檔、還原或安全釋放容量，不能稱恢復完成。

## 2026-10-28：GUI／歷程整合完整回歸

`reports/verify-full-gui-history-20261028-01` 綁 7de39b3：1670 run／1667 pass／3 skip（2 symlink creation unavailable、1 notification_icon_unavailable）、0 fail/error，491.239 秒、224 AST、source_unchanged，Job 自然 0／remaining 0／無強停、逐測殘留 0、0 native scan／model。`reports/release-prep-gui-history-20261028-01` 以同 commit 建置，326 檔、兩 ZIP SHA256 `450706127a89381ebd34d252c1b4e7c8d5474271fa680a10b4b445ce9c4b6510` 一致；候選並非發布。

文件保存前 `reports/verify-full-checkpoint-docs-20261028-01` 19/19、0 skip、224 AST、Job 自然退出；工作樹 ZIP 含文件。本完整回歸不證明人類 UX、真原生覆蓋、24h、重啟、真 agent 或容量耗盡恢復。

## 2026-10-28：處置歷程容量局部恢復

`reports/gui-history-capacity-recovery-20261028-01`：從舊 32 筆滿載 synthetic DB 出發，真瀏覽器新處置成功；舊 32 列逐筆保留、未綁定仍未知，總 33、pending／receipt null。`-02`：256 筆 synthetic no-op 顯示滿載，嘗試新處置顯示容量不足且狀態／pending 不變。兩 Job 自然 0／remaining 0／無強停、各 1 合成 POST、native／model 0；shutdown_requested_reason 是 harness 預設，實際合作停止。

`reports/verify-history-capacity-recovery-20261028-02` 72/72／0 skip／224 AST／source_unchanged、Job 自然退出；含實際 256／4096 記錄滿載與資料保全測試。提升上限不等於全庫／byte 滿載的恢復機制，亦不保證永久操作。

## 2026-10-28：詳情切換安全合成驗收

`reports/gui-detail-switch-safety-20261028-01`：先開合成事件 A，延遲 B 的詳情並點 B；載入中 `#detail` hidden、可見處置按鈕 0；放行後詳情及 delivery 均為 B。worker 0 POST／native／model，原 Job 自然 0／remaining 0／無強停；shutdown_requested_reason 為 harness 預設，實際合作停止。`reports/verify-detail-switch-safety-20261028-01` 49/49／0 skip／224 AST／source_unchanged，Job 自然退出。

## 2026-10-28：處置歷程身分綁定

新操作與事件 payload hash 同交易保存；同操作 ID 重新使用於不同內容或舊版未綁定紀錄時衝突。舊 schema 只在明確寫入時惰性加欄，舊列 hash 仍 NULL，不偽造歸屬；讀取不遷移，任何未綁定或不同 hash 的該事件歷程顯示 unknown。

`reports/verify-history-identity-20261028-02` 96/96／0 skip／224 AST／source_unchanged、Job 自然 0／remaining 0／無強停。`reports/gui-history-identity-20261028-01` 合成真瀏覽器：相符顯示歷程、內容變更與未綁定顯示未知，SQLite SHA256 前後均 `dfc40af88be1da77ae80c6d95b2f1899a96fb6a96659b10116ddab52c3920240`；worker 0 POST／native／model，Job 自然退出。非真主機或攻擊測試。

## 2026-10-28：六情境合成比較補全

`reports/ux-compare-20261028-02/comparison.json` 延續 `-01` 的嚴重清單與最後成功，補拒讀、保存關聯、診斷缺口、handled／pending：拒讀舊 1 操作／446ms、新 0／45ms；關聯各 1，舊 848ms／新 775ms；缺口各 1，舊 838ms 顯示原始代碼／新 789ms 顯示中文；handled／pending 各 1，舊 758ms／新 850ms，兩者皆可見。這是單次自動化 wall time，舊版錨定列索引以 fixture API 先核對，不計人類尋找或閱讀時間；不能據此推論完成率、統計效果或超越競品。

第二組共用 SQLite hash `ed790b81de89b668de32121db789f2e8ce72d64a1c688689574743b5a5b697e0` 前後不變；兩 Job 自然 0／remaining 0／無強停、0 POST／native／model。`reports/verify-ux-six-synthetic-20261028-01` 46/46、0 skip／224 AST／Job 自然退出。人類六任務、200% zoom、競品帳戶與真實環境仍未驗證。

## 2026-10-28：GUI 合成固定版本前後比較

`reports/release-prep-ux-before-20261028-01` 與 `-after-20261028-01` 各兩份可重現 archive，固定 ad1f127／338cdc5；`reports/ux-compare-20261028-01/comparison.json` 記相同 synthetic DB hash `a40645cbbb8777cadf0f8e857cebafcbda71541ad0f8f3a9636cdc2d74ea8a09` 與真瀏覽器操作。嚴重／new 篩選：舊版 3 次選擇／提交、516ms，新版按提示 1 次、293ms，皆 2 件／首列嚴重；拒讀後最後成功：舊卡 1 操作／434ms 未呈現，新卡 1 操作／398ms 可見且拒讀仍在。觀察錯誤結果與誤判安全均 0，但樣本僅兩項單次自動化操作，不能推論人類或產品優越性。

兩個私有 Job 自然 0／remaining 0／無強停、0 POST／native／model，來源 GET 各 7；shutdown_requested_reason 為 harness 預設，實際合作停止。新版來源頁 800／1280 viewport 無橫向溢位；未測 200% zoom、完整六情境或競品租戶。`reports/verify-ux-comparison-20261028-01` 26/26、0 skip／224 AST／Job 自然退出。

## 2026-10-28：P2-HISTORY-001C 合成瀏覽器

`reports/gui-handling-history-20261028-01` 四 synthetic 事件：三筆 GUI／MCP／CLI 轉換與 no-op；沒有記錄；刻意損壞後未知；32 筆滿載提示。畫面明示來源非已驗證身分與處置非 ACK。SQLite SHA256 前後皆 `0cb758f6764eeedcef8c36a7abd9ef218f1d7e9bfcb3067731d71f9c78166e90`，4 pending／0 receipt；worker 0 POST／native／model、Job 自然 0／remaining 0／無強停，shutdown_requested_reason 為 harness 預設且實際合作停止。

`reports/verify-gui-handling-history-20261028-01` 47/47／0 skip／224 AST／source_unchanged、Job 自然退出。歷程來源沒有認證，並非防竄改稽核；容量恢復尚無。

## 2026-10-28：P2-HISTORY-001C 合成唯讀後端

`reports/verify-history-read-20261028-01` 53/53／0 skip／224 AST／source_unchanged，Job 自然 0／remaining 0／無強停。合成 SQLite 證實舊 DB 讀取不建表、歷程讀取前後 bytes 不變、轉換與 no-op 分開、損壞來源顯示 unknown、32 筆顯示數量上限、pending 1／receipt 0。這是 API 讀取切片，不是 Web 呈現或容量恢復驗收。

## 2026-10-28：P2-HISTORY-001B 合成整合

`reports/verify-history-integration-20261028-05` 99/99／0 skip／223 AST／source_unchanged，Job 自然 0／remaining 0／無強停；合成 SQLite 測跨新 Application 重播、無變更重播、識別衝突、插入後失敗與 reserve 檢查回滾、滿載不變。`reports/history-integration-20261028-03` 合成瀏覽器操作 new→read，DB 保存同交易紀錄、事件仍 pending／receipt null；`-04` 滿載時顯示容量不足且狀態不變。各 worker 一次授權合成 POST、native／model 0、Job 自然 0／remaining 0／無強停；非真主機／真 agent 驗收。容量恢復、UI 歷程與斷電實測未完成。


## 2026-10-28：P2-HISTORY-001B 交易核心

純 SQLite synthetic 測試驗證 helper 無呼叫方交易即拒絕，建立與插入可 rollback，同 ID 重播／衝突，無變更請求記冪等但不算轉換，筆數／位元組不足拒絕且 pending／receipt 不變。`reports/verify-history-transaction-core-20261028-01` 57/57／0 skip／222 AST／source_unchanged，Job 自然 0／remaining 0／無強停。此 helper 尚未連接產品處置寫入，in-memory SQLite 測試不證明磁碟故障、跨程序或重啟已驗收。

## 2026-10-28：歷程契約換行修正

`73b79df` 的 staged diff-check 因 CRLF 回報尾隨空白；PowerShell 命令沒有依退出碼中止，錯誤已保存並普通推送，不改寫既有 commit。本單元僅將兩個新檔轉 LF，`git diff --check` 通過；`reports/verify-history-line-endings-20261028-01` 27/27／0 skip／220 AST／source_unchanged、Job 自然 0／remaining 0／無強停。後續獨立檢查結果後再提交。

## 2026-10-28：P2-HISTORY-001A 純契約

`disposition_history.py` 為純資料驗證，限制狀態轉換、無使用者身分宣稱的來源、bounded ID／有限時間及 32／4096 筆候選上限；無 SQLite 讀寫。`reports/verify-disposition-history-contract-20261028-02` 58/58、0 skip、220 AST、source_unchanged、Job 自然 0／remaining 0／無強停；包含新契約、event catalog、outbox 及 Application RPC 定向，並非完整回歸或已持久化歷程驗收。

## 2026-10-28：P1-INVEST-004B 合成逐觀測理由

真瀏覽器 `#investigation-view ol` 合成保存案件含 16 成員：錨定列有截斷及「沒有保存診斷」，被修改的 synthetic 成員列有「原事件內容已變，證據未知」及限定 metadata 的同主機／來源／穩定身分理由；PID 重用、異來源、缺身分候選不在時間線。第一輪發現診斷代碼未翻譯，補既有五種診斷代碼中文後於 `reports/gui-investigation-reasons-20261028-02` 重驗；0 POST／native／model，Job 自然 0／remaining 0／無強停。SQLite SHA256 讀取前後同為 `1bf0d18fa9b18e7cf136974866bb11deedb1d87785104b39c144b7a1db78367e`。shutdown_requested_reason 是 harness 預設，實際合作停止。

`reports/verify-gui-investigation-reasons-20261028-01` 63/63／0 skip／218 AST／source_unchanged，Job 自然退出；含 correlation 與診斷負控制。合成結果不代表真環境覆蓋、攻擊鏈或競品比較。

## 2026-10-28：P1-INVEST-004A 合成保存調查

獨立 synthetic fixture 根據既有 investigation metadata 建立保存案件，含 16 成員、26 候選、truncated=true；真瀏覽器 `#investigation-view` 顯示錨定事件、hash 相符、快照過期、缺口及截斷，重開文字一致。原始資料庫 hash `2bf9ea39710c5db4d3a02b86346657d108b80e574aa65fd8d04abfe2a10d018f` 在第一次瀏覽前後一致。測試另在隔離 SQLite 更改一個 synthetic 成員內容及其自洽 hash；已保存案件改顯示證據未知，讀取前後 SQLite hash 同為 `1bf0d18fa9b18e7cf136974866bb11deedb1d87785104b39c144b7a1db78367e`。初次只改 payload 造成 local_storage_unavailable，之後改為一致的合成記錄才進行未知狀態驗收，沒有改產品資料或略過錯誤。

`reports/gui-investigation-summary-20261028-02` 原 Job 自然 0／remaining 0／無強停，worker 0 POST／native／model；shutdown_requested_reason 為 harness 預設，實際合作停止。`reports/verify-gui-investigation-summary-20261028-01` 62/62、0 skip、218 AST、source_unchanged；既有負控制測試含 PID 重用、異來源與缺身分，不以合成測試聲稱真實偵測效能。

## 2026-10-28：網址 regex Python 警告

準備調查合成 fixture 時 Python 3.13 對 Web 字串內 `\d` 發出 SyntaxWarning；等價 `[0-9]` 修正後以 `-W error::SyntaxWarning` 匯入通過。`reports/verify-gui-url-regex-20261028-01` 為 33/33、0 skip、218 AST／source_unchanged、Job 自然 0／remaining 0／無強停；不代表新調查介面已完成。

## 2026-10-28：P1-GUI-003B 慢清單與消失列補驗

`reports/gui-detail-edge-20261028-01` 合成真瀏覽器：延遲 high 列表、切換 critical/new、放行舊回覆後仍為 critical／2 筆、首列嚴重；選 `evt-url-critical-1` 後由測試程式在獨立 SQLite 設 handled、明示 ack_performed=false，週期更新使該列不再符合 new；按返回後焦點回篩選按鈕、篩選網址保留。這是合成故障注入，非真主機事件。Job 自然 0／remaining 0／無強停，worker 0 POST／native／model；shutdown_requested_reason 是 harness 預設，實際合作停止。

`reports/verify-gui-detail-edge-20261028-01` 33/33／0 skip／218 AST／source_unchanged，Job 自然退出；本次沒改產品程式。僅涵蓋所述情境，不保證所有競態。

## 2026-10-28：P1-GUI-003B 詳情返回與延遲詳情

合成真瀏覽器於 high/new 第二頁開啟 `evt-url-high-4`，焦點到返回按鈕；按 Enter 回原列、網址仍 page=1。延遲該詳情、立即開啟 `evt-url-high-3`，放行舊回覆後畫面與 delivery event_id 仍為後者，返回焦點亦為後者。另等待一個五秒週期後，同一合成列按鈕焦點未變。沒有執行人工處置或 ACK；不代表所有競態已排除。慢事件清單回覆及原列消失後焦點尚待注入。

`reports/gui-detail-return-20261028-01` 來源 GET 10、POST 0、native/model 0，原 Job 自然 0／remaining 0／無強停；shutdown_requested_reason 為 harness 預設，實際合作停止。`reports/verify-gui-detail-return-20261028-01` 61/61、0 skip、218 AST、source_unchanged；UI 靜態契約不代替瀏覽器證據。

## 2026-10-28：P1-GUI-003A 合成網址導航

合成瀏覽器高 55／嚴重 2／資訊 1，直接載入 high/new/page=1 顯示 5 筆；reload 保持，上一頁顯示 50，back 回 5、forward 回 50，嚴重提示進 critical/new 2 筆。無效嚴重度、重複參數、page=10001、未知參數均顯示固定錯誤與空列表；選 high/listeners/new 後恢復 55 筆，網址只包含列舉。未對慢事件回覆做瀏覽器注入。

首輪 `reports/gui-url-filters-20261028-01` 原根路由返回 route_not_found；修正根路由後 `-02` 成功。兩 worker 原 Job 均自然 0／remaining 0／無強停，後者 15 來源 GET／0 POST／0 native／0 model；shutdown_requested_reason 為 harness 預設，實際合作停止。首輪 verify 31/32 是靜態切段失敗，修正測試範圍後 `reports/verify-gui-url-filters-20261028-02` 32/32／0 skip／218 AST／source_unchanged；非人類或真主機驗收。

## 2026-10-28：P1-GUI-002B 合成高嚴重度入口

`reports/gui-high-links-20261028-01`：隔離伺服器以合成 pending 事件建立高 55、嚴重 2、資訊 1。實際瀏覽器點高後為 severity=high／status=new、總數 55／首屏 50、首列高；下一頁 5 筆後點嚴重，severity=critical／status=new、總數及本頁均 2、首列嚴重、上一頁停用。從來源頁以 Enter 回高首頁成功；數字分別查詢，不是共同快照。worker 0 POST／native／model，原 Job 自然 0／remaining 0／無強停；shutdown_requested_reason 為 harness 預設，實際合作停止。

`reports/verify-gui-high-links-20261028-01`：30/30、0 skip、218 AST、source_unchanged，Job 自然退出；含 UI 靜態契約與 catalog fixture，非完整瀏覽器競態驗收。未測人類時長、真主機或競品。

## 2026-10-28：來源摘要延遲切頁競態

`reports/gui-source-gap-race-20261028-01`：舊合成成功回覆延遲、切往來源頁再回事件頁，切換 fixture 為錯誤後，舊版仍短暫顯示七來源觀測成功，構成重現；原 Job 自然 0／remaining 0／無強停。

`reports/gui-source-gap-race-20261028-02`：相同步驟於修正版先顯示未確認，延遲回覆放行後新失敗顯示無法確認；再切換正常 fixture／按篩選可恢復觀測成功。worker 來源 GET 8／POST 0／native 0／model 0，原 Job 自然 0／remaining 0／無強停；shutdown_requested_reason 是 harness 預設，實際為合作停止。靜態契約不取代此真瀏覽器情境，仍非所有可能競態的完整證明。定向 `reports/verify-gui-source-gap-race-20261028-01` 41/41，0 skip；來源 build 工作樹逐檔自檢。

## 2026-10-28：P1-GUI-002A 合成來源缺口摘要

隔離真瀏覽器核對 `#source-gap-summary`：七個唯一來源 ok/fresh 時只稱觀測成功；過期／拒讀顯示來源與缺口；缺項、重複、空與 HTTP error 均為未確認，始終明示不代表安全。HTTP error 下 `#event-rows` 仍含一個人工建立的合成 pending 事件。與真主機資料、人工 UX 計時或競品比較無關；慢回覆切頁競態尚未注入。

`reports/gui-source-gap-20261028-01/worker-exit.json`：來源 GET 20、POST 0、native/model 0、web thread 已退出；guardian-exit 自然 0／remaining 0／無強停。shutdown_requested_reason 為 harness 預設 timeout 標籤，實際合作 stop.request，reason 為 natural_exit。`reports/verify-gui-source-gap-20261028-01`：41/41，0 skip、218 AST、source_unchanged，Job 自然退出；靜態 UI 契約測試不是瀏覽器行為測試。工作樹 ZIP 僅是來源建置自檢，不是已提交 SHA 候選包。

## 2026-10-28：P1-GUI-001 合成來源卡片

目標 `#source-cards` 實際瀏覽器觀察七張卡片：歷史成功後拒讀保留原因、舊成功顯示目前過期、未知／無效／未來時間顯示未知、零列顯示 0、HTML 樣式名稱與原因為文字且無 img／b 節點。800px 寬 `scrollWidth=785`、鍵盤 Enter 切事件與來源頁；沒有保存截圖。合成 API fixture 非真主機資料；before／after 人類操作時間與競品比較未取得。

`reports/gui-source-cards-20261028-01/guardian-exit.json` 原 Job 自然 exit 0、remaining 0、無強停；worker-exit.json 記 5 次來源讀取、0 POST、model/native 0、web thread 已退出。guardian 的 shutdown_requested_reason 記為 timeout 是 harness 傳入的預設理由，實際 stop.request 為合作停止、reason 為 natural_exit，不能把它讀成 timeout 發生。

`reports/verify-gui-source-cards-20261028-02`：18/18、無 skip、218 AST，含三次實際來源 HTTP GET 前後持久檔 byte 相等及 synthetic pending／stats 不變；0 native／model；測試 Job 自然退出。瀏覽器 fixture 狀態為合成注入，與後端持久化只讀測試分開，不能稱完成真實來源覆蓋。


## 2026-10-28：競品研究工程規格與來源界線核對

第一證據單元已普通 push f1ed1e07f884e961e96aaffa3cbf9cf51544578d／feat/local-codex-acceptance，+113/-0；遠端同 SHA，status／shortstat 無輸出。第二單元只補 [規格](research/competitor-gui/ENGINEERING_PLAN.md) 與既有管理入口；所有產品項目是未實作提案。新增重要發現：source_status 1.0 的最後成功／新鮮度尚未接到七來源卡片，不能以公告卡片或 API 測試冒充 GUI 已完成；Tk activity 已存在，也不能誤報產品全無操作歷程。

本次命令見 STATUS 頂部。build02 綁 f1ed1e0，319 檔／兩 ZIP SHA256 1dc7c1220b379e9ed14538fc6a324bdb8fefde3025e62e1df5014d84514e7b16 相同、兩原 Git Job 自然退出。verify02：UTC 07:47:52–07:47:55（台北 15:47:52–15:47:55）、2.142 秒、29 run=expected／29 pass／0 fail/error/skip、218 AST、source_unchanged、原 Job 自然 0／remaining 0／逐測試殘留 0。來源 hash 240 項對照，沒有改產品碼／測試。既有 74/74 與此 29/29 不相加，不是全庫或提案驗收。

第二單元文件路徑／引用／未知限制及差異檢查、source binding 與 commit／push 回條留 reports/research-gui-20261028-01；build02 不包含未提交規格。研究未讀私人圖片／事件內容、未採集／啟模型／連競品帳戶。原生 partial、24h/reboot 與正式競品實測仍缺，第一切片驗收需後續實作再做。

## 2026-10-28：競品公開證據與 EventGuard 對照來源驗證

研究基準 f86254bb0393b606b1202b370efa18b35f649e8e，查閱日期台北 2026-10-28。官方來源／四個固定 GitHub SHA／角色與授權／封存列於 [研究](research/competitor-gui/README.md)。實際只看公開頁面及四張官方圖片，不保存圖、不登入主控台、不執行廠商程式。GitHub REST 一般 shell 請求失敗（HttpRequestException，未記原始例外），web 部分固定連結 cache miss，改以公開 GitHub 瀏覽器頁面核對；沒有提權。Falcon PDF 僅文字／圖說成功，內嵌像素未顯示，保留限制。

命令見 STATUS 本節。build 首次目錄名稱錯誤在 child 前拒絕；合法 reports/release-prep-gui-research-20261028-01：318 檔、reproducible=true、ZIP SHA256 af17e147165a16b67a1ea6ab90c584da44c2f94cb5142ef22f8ef197db7a4c5e、兩原 Job 自然 0／remaining 0／無強停。reports/verify-gui-research-20261028-01：UTC 07:33:12–07:33:20（台北 15:33:12–15:33:20）、6.872 秒、74 run=expected／74 pass、0 fail/error/skip、218 AST、source_unchanged、原 Job 自然 0／remaining 0／逐測試殘留 0。六定向模組涵蓋 catalog、調查／診斷、來源成功歷史、served UI 契約及打包器；UI 測試不等於 JS 互動／競態或原生覆蓋驗收。

本單元純文件；原生 partial、24h/reboot 與正式競品效果仍未驗。build 綁既有來源，不能稱新文件已打包或目前產品已改善。文件／相對連結檢查與 Git 保存回條在 reports/research-gui-20261028-01（ignored，本機證據，不隨 repo 提供）；只 stage 已審查文件，普通 push feat/local-codex-acceptance 並核對遠端，不推 main/tag/release。

## 2026-10-28：原子checkpoint政策單元的提交前驗證

工作樹原乾淨／c80a4be與upstream相同；此單元只改AGENTS、CLAUDE與必要狀態／證據，整合新規則並撤除3個未推commit的累積節奏。build命令py -3.13 -B scripts/package_candidate.py --root reports/release-prep-policy-check-20261028-01 --commit c80a4be90c7e9893544e72fab04c12e7653b33cc：318檔、reproducibletrue、兩原Git Job自然退出；只驗既有產品來源，不稱未提交文件已打入包。

py -3.13 -B scripts/verify.py --run-dir reports/verify-checkpoint-policy-20261028-01 --timeout-seconds 180 --module test_package_candidate --module test_verify_candidate --module test_verify_completion --module test_verify_portability：UTC06:53:13–06:53:16（台北14:53:13–14:53:16），1.388秒、31run=expected31／31pass／0skip/fail/error、218AST無錯、source_unchanged、原Job自然0／remaining0／無強停／逐測試殘留0。最初文件diff-check偵測新增行CRLF混用，修正新增行換行後才通過；沒有在失敗狀態commit。政策／文件連結／提交量及明列四檔另核對，最後單一docs(workflow) commit普通push開發分支並記錄hash、message、父commit差異與status／shortstat。無圖片／runtime／秘密／模型／原生查詢，不修改既有歷史。

## 2026-10-28：main整併實證、完整本機SDK回歸及隱私附件排除

使用者直接授權推main後，git fetch --all --prune／ls-remote核實origin/main與feat/local-codex-acceptance均a4e13fa75ea0d2d8b455281811114de3efe91844，git diff --quiet與rev-list為0差異／0/0；逐支merge-base --is-ancestor確認handoff、quota、research、publication及開發分支全部包含，私人本機main與其他worktree保留。gh api PR1為closed／mergedtrue、2026-10-22T09:09:47Z／615f77f，依要求remove_artifact後list_artifacts為空，不刪GitHub合併紀錄。git diff 4a1a95b a4e13fa精確為58files／5368新增／39刪除；這是已提交歷史區間，UI基準只作推論。main-consolidation-20261028-01/state-before.json保留核對，review開啟請求queued未宣稱已呈現或歸零。

py -3.13 -B scripts/verify.py --run-dir reports/verify-main-integration-20261028-01 --timeout-seconds 1800：UTC06:33:14–06:40:24（台北14:33:14–14:40:24），428.735秒；1636run=expected1636／1633pass／3skip／0fail/error，兩skip因symlink建立不可用、一項notification icon不可用；218AST無錯、source_unchanged、stopped_early/stop_requested皆false、原guardian自然0／remaining0／無強停／逐測試殘留0。source-commit.json比對240來源與b534包零差異；本機既有SDK路徑實跑，無native inventory／新模型／真agent重驗。未把環境skip算通過。

新隱私要求只核對四個已知圖片的檔名／存在與Git紀錄，經絕對路徑範圍及無reparse確認後刪除，四原檔皆不存在並移除空附件目錄；不讀內容、不掃其他私人目錄。git ls-files／git log --all相關路徑無紀錄，GitHub main recursive tree未截斷且無相關路徑；完整回條只留ignored reports，不提交私人檔名／圖片。新增.gitignore附件及剪貼簿排除，check-ignore兩正向／一般產品圖片一反向皆如預期。平台聊天附件未移除，不宣稱法證安全抹除；原生及產品未驗限制不變。

本checkpoint只含.gitignore與既有結果文件，普通push開發分支及快轉main，另核對同SHA與tracked clean；不以多餘merge／reset／clean／force消除歷史統計，不打tag／發布／刪分支／建排程。

## 2026-10-28：b53479a新候選的固定來源、完整CI與實際交付

工程checkpoint b53479a28ea030a92ae23ba50ed24d6aca2be679，明列七檔審查／無固定秘密模式、git diff --cached --check通過，普通push既有feat/local-codex-acceptance，直接ls-remote相同。相對8b9cf27為7檔460新增；沒有src/config/playbooks/contrib/.github或啟動cmd改動。定向03的240來源hash逐一等於新ZIP檔案，source-binding.json與source-commit.json保存零差異；31/31只作本機定向，舊b57完整1624不移植。

py -3.13 -B scripts/package_candidate.py --root reports/release-prep-candidate-20261028-03 --commit b53479a28ea030a92ae23ba50ed24d6aca2be679：318檔、兩ZIP byte相同／SHA256d755a8d85a9fec15343a88b7b0adeb24b003f7d21d6e3322b127df73b3e10605，兩原Git Job自然0／remaining0／無強停。新工具verify_candidate.py以該ZIP／release-manifest.json及外部相同commit與hash、--root reports/candidate-verify-release-20261028-01 --smoke實跑，manifest核對及13/13 checks／四原CLI Job自然0／remaining0／無強停。source未變、一件synthetic pending／一份case／零ACK／無live namespace，保存重開相同且唯讀DB hash不變；無模型／native。

同一新包的兩次負向實際CLI皆帶--smoke：全零錯誤外部hash→candidate-verify-reject-pin-20261028-01的external_archive_hash_mismatch；只竄改manifest LICENSE digest→candidate-verify-reject-manifest-20261028-01的manifest_content_mismatch。兩者exit2、passedfalse、owned_steps空且未建立unpacked；negative-cli-crosscheck.json為2/2，原包／manifest未改。新候選獨立index反向patch在candidate03/rollback/rollback-result.json為5/5、九Git Job自然退出；公開main tree相同、真index／checkout未變。artifact-crosscheck.json為8/8，CI終結與最終保存另閉合。

gh api及gh run view只抽固定摘要核對[新精確run40642090530](https://github.com/SecludedCorner/EventGuard/actions/runs/40642090530)，head_sha=b53479a、UTC06:14:47 completed/success。Windows job122662316404：1636run=expected1636、1589pass／47可選SDK不可用skip、0fail/error、337.593秒、218AST、source_unchanged、stopped_early/stop_requested皆false、per_test_residuals0，原Job自然0／remaining0／無強停。Linux job122662316070為fixture104/104、0skip，不是Linux native；固定欄位及skip分類保存candidate03/ci-*.json，不保存完整logs／不安裝依賴／手動dispatch／rerun。

本輪補齊repo可重現驗包與隔離smoke，新候選含工具本體；後續四份純文件checkpoint只補結果，另存遠端SHA、產品無差異、0/0與乾淨tracked回條。排程未建立／恢復，私人main及其他worktree／附件不動，無main/tag/release／部署／分支刪除。原生111缺列／21error、24h/reboot與既有桌面喚醒未升格；真04只沿用歷史範圍，runtime／授權／回條不提交。

## 2026-10-28：驗包／包內 smoke 自臨時腳本固化

8b9cf27後核對repo只有package_candidate，既有smoke與resume只在reports；新增scripts/verify_candidate.py與tests/test_verify_candidate.py。明確外部40hex commit／64hex ZIP hash，輸入快照後核對原archive audit與完整逐檔manifest，JSON型別精確且拒重複key；篡改者即使更新ZIP及自述manifest仍不能替代外部pin。拒缺必要檔、來源不符、逃逸／私人路徑／碰撞、大小超限、redirect及覆寫舊輸出；smoke前拒絕不啟child。工具預設離線；可選合成CLI在Windows私有Job下有界執行，原退出不明／強停／殘留／逾時均不能過。

guardian命令見STATUS頂部，reports/verify-candidate-tool-20261028-03：UTC06:07:49–06:07:51／1.193秒、31run=expected31／31pass／0skip/fail/error、218AST無錯、source_unchanged、原Job自然0／remaining0／無強停／逐測試殘留0，native/model0。01/02亦31/31；02改掉跨平台不必要os.name mock且assert固定拒絕原因，03收緊remaining必須int0，拒絕False假零；保留三輪，不把數量累加。

新工具實際命令使用原candidate02/candidate.zip／release-manifest.json，外部--expected-commit b57b43be8333327584ef05af4e71740b5b80d621、--expected-sha256 2d5ae6a55a24aebd344a630a53b61abc075cfb9af3b62664afb1d9582a8f62d5、--root reports/candidate-verify-historical-20261028-01 --smoke；verification-result為passedtrue／manifest_verifiedtrue，13/13 checks，一件synthetic pending／一份case／零ACK／無live namespace，唯讀重開DB hash不變，四個原CLI Job自然0／remaining0／無強停。沒有啟真模型／native query，也不把此操作稱新候選完整測試。

此checkpoint先保存工具、測試、CHANGELOG與既有狀態；下一步實際新SHA打包／驗包，另核精確CI。舊b57完整1624、舊CI、歷史真04與native partial各維持原scope；排程已刪除，本輪不恢復，runtime及原回條不提交。

## 2026-10-28：固定候選全部發布前準備通過；沒有發布

固定來源b57b43be8333327584ef05af4e71740b5b80d621（修owned Git完整路徑與提前停止假綠），整合父checkpoint3ed82a8。公開main615f77f／handoff、quota、research、publication全部包含，private main不可達；其tip tree與公開sanitized root相同，不需要上傳私人祖先。branch-integration.json保存祖先與基準；候選相對origin/main615f77f為285檔、55340新增／1961刪除，是已提交範圍，不是工作樹累積。無衝突／main push／正式tag／release／部署／分支刪除。

py -3.13 -B scripts/verify.py --run-dir reports/verify-release-preparation-full-20261028-02 --timeout-seconds 1800：guardian UTC05:43:35啟動、summary05:50:36（台北13:43:35–13:50:36），worker419.655秒；1624run=expected1624、1621pass、3skip、0fail/error、stopped_early=false/stop_requested=false、216檔AST無錯、source_unchanged、原Job自然0／remaining0／無強停／逐測試殘留0。skip為兩symlink建立不可用、一notification icon不可用。238驗證來源hash逐項等於候選ZIP內同commit檔案，source-commit.json／source-binding.json保存零差異；不把原01部分1533項假綠或新文件checkpoint當受測產品。

py -3.13 -B scripts/package_candidate.py --root reports/release-prep-candidate-20261028-02 --commit b57b43be8333327584ef05af4e71740b5b80d621：實際兩次git archive，316檔／同commit，兩ZIP SHA256均2d5ae6a55a24aebd344a630a53b61abc075cfb9af3b62664afb1d9582a8f62d5；兩個原私有Job自然0／remaining0／無強停。release-manifest.json逐檔hash、package-result.json原回條。初01失敗保留，沒有宣稱失敗launch有退出證據。

同candidate02/smoke_package.py實際解壓後執行包內emit/list/investigate/detail，原四CLI均自然0。最後輔助SQL誤用status而非delivery_status，smoke-check-failure.json標harness非產品；resume_smoke.py讀原回條／輸出，不重發或重存，僅額外一次唯讀detail；smoke-result.json共14/14、五個原Job自然0／remaining0／無強停，DB一件合成pending／一份保存case／零ACK，重開case相等、唯讀DB hash未變、316檔hash相符。模型／native0，不是真agent重驗。

rehearse_rollback.py於獨立GIT_INDEX_FILE中read-tree候選、git apply --reverse --cached --check與實際apply、write-tree；rollback-02/rollback-result.json為5/5，所得tree810eca95236e0e5955446e1689c0c6aca9fdfdc9精確等於公開main，真index hash／tracked checkout未變、九個原私有Git Job自然0／remaining0／無強停。完整binary diff SHA256c4dfe62e6fd35d274df8af92db5e37e8c592ee0952bded1a9be05c7cb3d45faf。原rollback目錄因輔助2MiB上限不足4297994 bytes而在建立alternate index前停止，四原回條／原diff保留；只改輔助8MiB上限到新目錄02完成。不是runtime或DB恢復測試。

gh api及gh run view唯讀核實[run40639767342](https://github.com/SecludedCorner/EventGuard/actions/runs/40639767342)精確head b57，completed/success（UTC05:49:21更新）；Windows job122654933138為1624run=expected、1577pass／47既有可選SDK不可用skip，完整閘道false-stop／true-source與原Job自然0／remaining0／無強停；fixture job122654933375為104/104、0skip，無Linux native支援。不下載、手動dispatch或rerun。固定欄位及skip分類保存candidate02/ci-*.json，沒有保存完整logs。

CHANGELOG與RELEASE_PREPARATION完成候選說明／hash／來源回復／未驗限制；原native111缺列／21error仍partial，24h/reboot、桌面聊天喚醒及競品比較未驗。真04歷史收件通過沿用，不新增模型或native批准。最後純文件checkpoint普通push現有開發分支並另存遠端核對，完成後暫停本聊天15分鐘接續；原跨專案暫停任務未動。runtime、ZIP、原授權／回條、未追蹤圖片均不提交。

## 2026-10-28：實際build與中斷驗證器的兩個修復

3ed82a8的package_candidate首輪01只回candidate_build_failed；該root與build-failure-analysis.json保留。JobPopen以applicationName原值呼叫CreateProcessW，不為git短名稱查PATH；改shutil.which後只接受現有absolute .exe，再交私有Job，不下載或使用cmd wrapper。新增兩個注入測試，沒有真Git child。

修來源前以guardian-stop.request合作停止完整01；UTC05:33:10–05:40:08，417.007秒、1533run／1530pass／3skip、0fail/error，原Job自然0／remaining0／無強停、source_unchanged，但原passed_checks=true不能作完整證據。acceptance-classification.json明確拒絕。實際根因是stopTest只result.stop()，worker/parent未比對預期總數。修非空expected_tests／run相等、stopped_early與stop_requested皆false才接受，worker及parent同時套用；新增4個純注入suite回歸。

py -3.13 -B scripts/verify.py --run-dir reports/verify-release-prep-repairs-20261028-01 --timeout-seconds 180 --module test_package_candidate --module test_verify_completion --module test_verify_portability：UTC05:42:43–05:42:44、.681秒、19/19／expected19、0fail/error/skip，AST216無錯、source_unchanged、原Job自然0／remaining0／無強停、無逐測試殘留，native/model0。新完整02同原full入口／1800秒已開始，未出結果不宣稱通過。修復依checkpoint保存後繼續真ZIPbuild與副本smoke，不以單元測試代替build。

## 2026-10-28：發布前整合與source candidate build前置

最新人類要求全部release準備、不執行release，從98d507d接續。fetch後公開origin/main仍615f77f；git merge --no-ff --no-commit origin/main無衝突／原產品tree無變更。候選已含其他可分享開發分支；私人本機main與原worktree保留，不推main／tag或刪分支。新CHANGELOG明示Unreleased，工作佇列見RELEASE_PREPARATION。

新增package_candidate.py，只以指定commit git archive建立source ZIP；Git child執行前進私有Job，有界wait／原退出回條，兩次archive與逐檔SHA／來源版本／必要檔案／容量／路徑／symlink／私人檔案閘道。初5個合成ZIP安全測試於verify-release-package-20261028-01為5/5、.366秒、AST215無錯、source_unchanged、原Job自然0／remaining0／無強停。補Windows別名／非canonical路徑與私人副檔名後，6個測試納入完整guardian：py -3.13 -B scripts/verify.py --run-dir reports/verify-release-preparation-full-20261028-01 --timeout-seconds 1800；結果仍待回條，不提前稱通過。native/model均不啟動。

已建立本聊天15分鐘接續，原跨專案暫停排程未改；同一runner先核對原作業，完成準備後暫停。此階段先checkpoint保存，再續同commit實際ZIPbuild、解壓副本合成CLI、臨時index反向diff及完整驗證。runtime、ZIP與自有程序回條只存reports，不提交；正式release及原native身份缺口不由此升格。

## 2026-10-28：baseline四表計數誤PASS重現與修復

從47af11f接續，先新增3個有辨識力回歸並修正正向fixture的原不一致count。01命令py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-count-regression-20261028-01 --timeout-seconds 180 --module test_windows_listener_validation，UTC05:11:16–05:11:25、7.971秒；18方法／13pass，5個failure entries含同方法4個subcase，0error/skip，原Job自然exit1／remaining0／無強停，原source_unchanged。證明原驗證器未核對四表count與返回列數，並非未知環境失敗；原回條不改寫。

只改project_baseline：有界1000列依TCP/UDP及ipaddress.version分四組，與原四表count逐項相符才complete；不以grand total掩蓋錯表，保存table_counts_consistent。原native API、身分查核、error分類、授權與Job退出門檻不變。02命令py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-count-regression-20261028-02 --timeout-seconds 180 --module test_windows_listener_validation --module test_listener_error_summary --module test_listener_identity --module test_collector_contract，UTC05:11:45–05:11:55／8.699秒，52/52、0fail/error/skip、213檔AST無錯、source_unchanged，原Job自然0／remaining0／無強停／逐測試殘留0，machine_scan_executed=false/model0。涵蓋匹配四表與完整空表仍可通過；不重跑長測試或原生。

另用gh api repos/SecludedCorner/EventGuard/pulls/1 --jq固定metadata唯讀核對圖中PR：number1／title Publish bounded Codex event delivery with MIT license／closed／mergedtrue／merged_at2026-10-22T09:09:47Z／merge_commit_sha615f77f55a29f856b2305fc54a5225b5ed58bc65。一般網路沙箱拒絕後經既有讀取例外成功；未讀登入檔、未改PR／附件或帳戶。新release merge/tag流程仍等人類指定，不以既有已合併PR冒充新版本發布。

原235列／111身分缺口／21錯誤六份runtime hash保留；本次計數guard不是舊身分根因修復。既有diagnostics-20261028-01因script hash變更標superseded，不執行／不覆寫原manifest。此次只保存程式／測試與必要現況文件；runtime不提交，普通push原開發分支並核對遠端，受測位元組另以source-commit.json綁定。沒有主線合併、tag、分支刪除或新native/model授權。

## 2026-10-28：保留既有listener錯誤分類，僅離線驗證

從a7bdfc0增量接續。現有contract/native/winapi已提供access_denied、object_unavailable、listener_pid_reused、api_unavailable、query_failed及stage/operation/status，WindowsCollectors亦保留；缺口只在project_baseline丟掉原因。新增固定allowlist分組與64筆prefix上限，不複製任意文字、錯誤數字、PID、路徑或端點。reported/retained/classified/unknown/unretained與count_consistent/truncated分列；無法核對總數時unretained=null，分類完整不改原baseline完整性判斷。來源manifest另納入既有winapi.py，未改原native backend。

6個新測試只注入process_created_at結果或fixture collector：既有錯誤經NativeBackend→WindowsCollectors→投影保存分類、同owner多端點與error筆數不同、未知／畸形／私人文字丟棄、64/80保留截斷守恆、缺／矛盾／bool總數不洗綠、partial不能由summary覆蓋、合成execute實際保存。命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-error-summary-20261028-01 --timeout-seconds 180 --module test_listener_error_summary --module test_windows_listener_validation --module test_listener_identity，UTC03:56:35–03:56:44（台北11:56:35–11:56:44+08:00）、7.506秒、27/27、0fail/error/skip、213檔AST無錯，source_unchanged／原Job自然0／remaining0／無強停／逐測試殘留0；machine_scan_executed=false/model0。不是原生採集、真agent或新全庫CI。

py -3.13 -B scripts/validate_windows_listener.py --root reports/windows-listener-diagnostics-20261028-01只prepare，query_started=false，run6dd82da8fcd84d72ace2fd6689bc20e7、manifest a0a3d93cebe3c71b874dd638d7dfb9e79e9b74fda16fec29b030ec88e9282477、12來源hash，template approved=false；無human-approval/intent/result/outer回條。唯一後續決策包在同目錄NEXT_DIAGNOSTIC.json與WINDOWS_VALIDATION_PLAN頂部，沒有另問批准或執行。舊235列／111身分缺口／21錯誤原件不可回推原因，原六收據hash核對仍應一致；新分類不是舊根因證據。不跑舊長測試／模型、不改系統／授權，runtime不提交，普通commit/push現有分支並另留遠端回條。

## 2026-10-27：一次已批准 native listeners 實跑，partial 如實保存

人類於03:00 UTC回覆 dot 的三項具體範圍「同意1、2、3」，原主責只接第3項。接續 edc088c，原 root/run/manifest hash與11 source hashes匹配且未執行，於 reports/windows-listener-baseline-20261026-01/human-approval.json先保存原文、轉達來源及時間；批准保守綁03:00:00–03:30:00 UTC，執行在有效窗內。manifest與未批准template原件均保留，不將一般持續工程要求當OS授權。

命令 py -3.13 -B reports/windows-listener-preparation-20261026-01/run-owned.py --root reports/windows-listener-baseline-20261026-01，只執行一次。原result UTC03:04:36.844483–03:04:37.668540（台北11:04:36.844483–11:04:37.668540+08:00）、elapsed0.739012秒，query_started=true；四表GetExtendedTcpTableIPv4/IPv6計數28/13、GetExtendedUdpTableIPv4/IPv6計數132/62，皆ok，共235列、未截斷。error_count21、process_identity_missing_count111（列數，不是111個不同owner），identity unknown／source partial／complete=false，整體blocked:baseline_incomplete。固定計數不足以判斷21錯誤的具體原因，不能歸咎必需管理員、sandbox或特定程序；未重查原始事實。

owned_query managedtrue／自然exit0／remaining0／forciblyfalse；outer-start保留原HANDLE，outer-exit自然exit2／remaining0／forciblyfalse／wrapper_errorfalse／deadlinefalse／cooperative_stop not_needed。命令返回1，沒有逾時或強停。stop watcher已退出；raw_facts_saved=false、model0、injectionfalse、host_safety_assessed=false、full_lifecycle_verified=false。未開socket、改registry／系統、啟其他來源或長期採集。

同目錄acceptance-crosscheck.json獨立13/13核對run/批准hash與時窗/scope/計數/退出/11source hashes，保存六份原artifact hash；receipt_consistency_passed=true與baseline_acceptance_passed=false分列，不把收據核對當驗收PASS。沒有產品碼修改、CI／全庫／真04重跑；原受測產品1e8f7e0沿用。只保存必要聚合結果到狀態／計畫文件，runtime、批准原文及自有PID回條不提交；普通commit/push原開發分支，不是正式發布。原一次批准已用完；不重複要求這次批准，也不自行補查／提權／放寬標準，後續精確native診斷須另授權。

## 2026-10-27：原 soak 日期／時區更正，原生批准仍缺

以 reports/soak-idle-30m-20261026-01/exercise/summary.json 的原 started_at／finished_at 核對：UTC 2026-10-25T17:12:21.291029+00:00 至 2026-10-25T17:44:01.298238+00:00；台北為 2026-10-26 01:12:21.291029–01:44:01.298238+08:00。末段實際樣本窗的 UTC 日期亦為 2026-10-25。修正 STATUS／本頁及 SOAK_PLAN 的日期關聯、HANDOFF 頂部接續；1900.017392 秒 monotonic wall、1802.489810 秒末窗與原資源結論不改，原資料不覆寫。

PowerShell 讀取原 JSON 與固定批准目錄、DateTimeOffset 明示 +08:00 轉換、Get-FileHash 前後核對四份原收據，結果留 reports/soak-time-correction-20261027-01/state-verified.json／validation.json；沒有重跑 soak／全庫／CI，沒有新模型或 native query。P2-OS-001 尚無直接具名批准、human-approval.json 或執行 intent/result/outer-start；現有 template approved=false。原範圍與單一待決問題已明載 STATUS／HANDOFF，這次轉達不代答，不建立重複請求或 runner。僅四份文件以 [skip ci] checkpoint 保存並普通 push 原開發分支，遠端實查結果另留回條；不將文件 HEAD 宣稱另受測產品。

## 2026-10-26：固定checkpoint推送提醒

直接人類要求不再等提醒才push；本輪只改AGENTS.md／新增CLAUDE.md入口及STATUS/EVIDENCE。政策為每checkpoint審查後commit並普通push，連續小commit上限3、交接前補推、遠端核對與失敗保留／有界重試；不自動擴分支、推main／其他refs或提交runtime／秘密。沒有建立定時背景程序。2026-10-26T16:00:08.752770+00:00以Python逐項文字／入口核對8/8、git diff --check；reports/git-push-policy-20261026-01/validation.json保留結果，沒有程序碼修改、本機回歸／模型／採集或CI重跑。以[skip ci]文件checkpoint推送並另留遠端確認回條，不把文件SHA稱為新受測版本。


## 2026-10-26：1e8f7e0的精確遠端CI終結success（最新）

本輪第一動作只以GitHub連接器GET /actions/runs/40345960922及該run jobs核對：head_sha=1e8f7e0e74f2018849b44cb02e2052d2fe817da4、attempt1、event push，status completed／conclusion success，updated_at2026-10-26T15:11:02Z。Windows job121652823962及Fixture/SQLite job121652824391均屬該run且completed/success，沒有沿用其他SHA。只為列明optional skips再讀job結果摘要，不保存raw logs，不手動rerun/dispatch、不修改workflow或權限。

Windows摘要：Python3.13.16，1603項／1556pass／47skip／0failure/error，source_unchanged，原私有Job child自然0／remaining0／無強停，model0／machine_scan=false。47skip原名單保存在repair-windows-summary.json，均為未安裝的可選MCP SDK及其transport/SSE相關依賴；缺依賴保持skip，沒有安裝或冒稱執行。Linux mock摘要104/104、0skip/fail/error，原Popen worker自然exit0，managedfalse／created_at、job、remaining=null／process_tree_verified=false，scope明示non_windows_mock_single_worker_only及linux_native_support=false；不可改寫成Linux native或程序樹退出證明。

新終結收據reports/ci-head-bc56e37-20261026-01/repair-ci-terminal.json與兩份原摘要保存run/job/SHA及scope。原bc56e37 run40339572814 failure、repair-ci-observed-01.json及複製保存的repair-ci-observed-02.json pending均保留，repair-ci-latest.json現指向終結成功。本輪未重跑本機全庫、九案例或真收件；未採集主機、啟模型或敏感處置。

僅更新三份狀態文件，文件commit使用[skip ci]避免純狀態更新觸發反覆CI；產品受測版本仍1e8f7e0，不把文件SHA宣稱另有CI成功。提交後以相對1e8f7e0的變更路徑只含這三份文件核對，再普通push原開發分支；runtime回條不提交。下一既定P2-OS-001仍待原具名單次listeners批准，不重新詢問，也不將本次成功升格為正式發布／真主機防護／24h/reboot／任意桌面喚醒。


## 2026-10-26：bc56e37遠端CI精確失敗與相容性修復（最新）

連接GitHub以GET actions/runs?head_sha=bc56e37b4cfb63ed3e0a9caf98d11a66b140372d&branch=feat/local-codex-acceptance，及該SHA/check-runs核對：run40339572814，event push、attempt1、check suite109331954956、status completed/conclusion failure。Windows job121630253841，UTC14:25:52–14:30:58；mock job121630254549，14:25:52–14:26:00，均failure。legacy statuses空不能蓋過Actions。讀job必要log：Windows只輸出1595 tests摘要（9 failure entries、1 RustSec error、47 skip），無unit trace／artifacts；mock明示scripts/verify.py:137 AttributeError:Popen無created_at。沒有借用其他SHA綠燈、沒有rerun/dispatch。metadata／過濾錯誤存reports/ci-head-bc56e37-20261026-01，不存raw logs。

reproduce.py以自有Job跑6個已失敗方法、缺mcp spec與本工具temp短路徑別名（GetShortPathName只讀本測試路徑），重現與CI同名9 failure entries，無error；直接CRLF fixture重現TOMLDecodeError。模型／native source query0，原worker自然0／Job0。修test根目錄resolve並明示單一SDK preflight fixture後，reproduce-after.py同條件6方法無failure/error，CRLF accepted；原／修後report分開保留，未重跑真ACK／九案例／全庫。

修復產品／harness：RustSec僅將CRLF正規化LF，fenced TOML不再留下bare CR。verifier不讀非Windows不存在的created_at；起始managedfalse、creation/job=None，保留原Popen exit_code，tree/remaining維持unknown，不宣稱Linux native；cooperative stop檔→grace→只該child收尾，強停／逾時／owner錯誤／停用記錄失敗不得pass。mock worker-only成功與Windows privateJob成功分契約，Windows finish仍委派原實作。新增7個有辨識力guardian fixtures（含timeout合作exit0不得洗綠）與1個LF/CRLF結果等價fixture，不改workflow或權限。

命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-ci-portability-20261026-01 --timeout-seconds 600 --module test_verify_portability --module test_desktop --module test_schedule --module test_agent_service --module test_intelligence_sources：UTC14:59:10.520043–14:59:30.759849，19.115秒，127/127、0fail/error/skip、source_unchanged／自然0/Job0。追加timeout0與保存失敗兩個邊界後，verify-ci-guardian-20261026-01同入口只--module test_verify_portability，UTC15:01:10.427819–15:01:11.953336，7/7、.367秒；其餘四模組來源未變。py -3.13 -B scripts/verify.py --run-dir reports/verify-ci-mock-contract-20261026-01 --timeout-seconds 180 --scope mock：UTC15:01:19.179420–15:01:28.653361，8.205秒，104/104、無skip/fail/error、source_unchanged、原Windows guardian自然0/Job0。這是本機Windows mock範圍，不是Linux實跑；三個範圍不相加為全庫，也不宣稱遠端新版本CI已過。

依原人類授權普通commit/push原開發分支，再唯讀核對新SHA CI；不手動重跑舊run、不新增CI／權限、不推main／force／runtime。新HEAD若pending/unknown就如實保留，舊bc56仍failure。


## 2026-10-26：遠端實查成功，推後續做九案例量測（最新）

推送命令 git push origin HEAD:refs/heads/feat/local-codex-acceptance 成功，回9576b13..548efe8；後續 git ls-remote --heads origin refs/heads/feat/local-codex-acceptance 實查548efe8bbfc7548b5b2d530db2c9203295583bce，與本機HEAD相同，git rev-list --left-right --count HEAD...origin同名為0/0。只此開發ref、沒有force或main／其他refs／正式發布。初始工作樹2個新golden檔，checkpoint連同3份狀態共5檔/+106；先前264檔/+52654/-1961明確為已提交歷史9576b13→cd117f9比較，不是未提交量。回條reports/git-checkpoint-20261026-01/remote-verified-first.json，runtime不提交。已保留他人兩個未追蹤目錄。

依要求推後立刻續工程：py -3.13 -B reports/investigation-source-golden-20261026-01/exercise.py。九個隔離source shape各2 synthetic事件，固定fixture預期關聯／UNKNOWN，逐案保存case/producer/validation／自身資源前後快照。總wall1.2740033秒，各案建案37.255–101.101ms，9/9、錯加0／漏加0、4個entity/source unknown；總DB405504B，18件保留pending、0ACK／receipts。獨立crosscheck.json逐案mode=ro/query_only/closing核對來源payload hash、保存case、producer synthetic與守恆，9/9；原worker PID55624／UTC14:21:45.154679綁定HANDLE自然exit0／remaining0／forciblyfalse，source hash不變。無Web／模型／原生來源query／額外ACK，全部只在EventGuard reports。不是惡意偵測率、7來源完整覆蓋、峰值或競品同環境基準。

本補記作新checkpoint並同分支push；最終remote-verified-final.json保存推後直接ls-remote實查，未驗成功前不以預期冒稱。每個後續可保存階段即提交及普通推送，真正實機／模型／敏感動作仍按各自原授權界線。


## 2026-10-26：使用者授權開發分支遠端保存（最新）

使用者直接要求先Git checkpoint並推既有授權開發分支，再續開發。核對cwd EventGuard、branch feat/local-codex-acceptance、HEAD cd117f93ef4e6af1346e44065a888716a9a664ec、upstream origin同名，origin HTTPS GitHub/SecludedCorner/EventGuard。普通工具網路沙箱git ls-remote連線拒絕；已批准的工具網路例外下唯讀查回遠端feat=9576b13a6773ce81c3a01799743d30094a48449a、main=615f77f55a29f856b2305fc54a5225b5ed58bc65，未改Windows／帳戶設定。當時ahead57，遠端→HEAD264檔/+52654/-1961；未提交只是兩個golden檔案，其他未追蹤目錄保留，畫面變更基準不混用。

reports/git-checkpoint-20261026-01/history-audit.json：review本分支全部待推歷史265路徑、55946新增patch行，runtime/秘密檔案路徑及私鑰/OpenAI/GitHub/AWS/JWT高信度pattern無命中；固定pattern不保證偵出所有秘密。只推指定ref，保留其他本機驗收refs，不推runtime或原始證據。既有workflow可能按普通push跑離線CI，不手動dispatch、不宣稱CI通過。

新增test_investigation_source_golden.py及9案例JSON。01定向29test methods、9subcase errors皆因測試讀list_events不存在的payload_hash，原trace保留；改以event_payload_hash(validate_event(row))比對公開介面不動產品。命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-investigation-source-golden-20261026-02 --timeout-seconds 180 --module test_investigation_source_golden --module test_event_investigation --module test_investigation_diagnostics：UTC14:17:44.336103–14:17:49.912372、4.368秒，29/29、211AST無錯、source_unchanged、guardian自然0/remaining0/無強停，model0/scanfalse。這個checkpoint在推送確認前不宣稱已遠端保存。


## 2026-10-26：已保存診斷的案件來源脈絡（最新）

接續bc5f028。investigation引擎新增1.1診斷摘要及固定缺口，catalog只接validate_saved_review通過的同事件紀錄，store在保存交易內重核review hash防競態；Web／CLI呈現query類型、來源、狀態、列數及時間。rows不轉送，不執行新DiagnosticAPI／collector／模型，ACK及人工處置分開。1.0案件向後相容；新8個有辨識力測試含缺失、過期／未來、空結果／partial、跨事件誤綁、保存競態、後續變更／刪除、格式竄改及舊schema。

核心命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-investigation-diagnostics-20261026-01 --timeout-seconds 600（11個--module見summary完整argv）：UTC13:46:47.588845–13:47:32.948041，44.31秒，160項159pass／1通知圖示skip，0failure/error；210檔AST無錯，source_unchanged，自有guardian自然0／Job0／無強停／逐測試殘留0。之後只增加Web／presentation顯示，命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-investigation-diagnostic-views-20261026-01 --timeout-seconds 300 --module test_local_product --module test_core_cli --module test_cli_workflow --module test_investigation_diagnostics：UTC13:48:56.020628–13:49:15.043912，17.977秒，52項51pass／1同skip、0fail/error、source_unchanged／自然0/Job0。兩個範圍不加總成全庫；前者核心來源與最終相同，Web/presentation以後者及產品03為準。

產品命令 py -3.13 -B reports/investigation-product-20261026-03/exercise.py，私有Job執行worker；UTC13:50:08.807087–13:51:51.290008。明示FixtureAPI建立已保存診斷system_query_executed=false，非native查詢；producer-manifest／fixture-diagnosis保留輸入。CLI建案→真IAB更新→HTTP／CLI同案→關server→重開IAB／CLI同case、同診斷hash，web-saved.png／web-reopened.png及完整AX可檢閱。18/18，source-sha256十檔相符，2個保存query摘要、8事件仍pending／0receipts／1case、read前後DB hash不變，兩Web thread退出；原worker PID39088／建立時間綁定HANDLE自然0／remaining0／無強停。沒有新增模型、native源採集或ACK。

有限成本03：一次CLI建案0.0966885秒、重開HTTP讀0.0080031秒，DB57344→65536B、case JSON3210B。自身資源兩點CPU0.59375→0.703125秒、private24027136→25030656B、handles120不變；此區間包含fixture準備，不冒充僅建案CPU／峰值／整Job／production或人類調查時間。來源commit以提交後source-commit.json綁定；runtime不提交、不push。原真04／1563pass／舊idle保持歷史scope。官方競品差距表只列宣稱及未測，沒有勝負結論。


## 2026-10-26：可保存事件調查與競品差距（最新）

基底124b42c，既有Python3.13.3／一般使用者。新增events/investigation.py、EventCatalog/Store懶建event_investigations表、CLI investigate／text、Web同源CSRF保存與時間線，fixture和20項新測試。每錨點一份最新case、64KiB上限，保留pending與ACK容量；源事件輪替同步清case，成員內容／hash變動或缺失標UNKNOWN。只有同host/source和穩定實體可關聯，owner_ref是host範圍hash，OS帳戶owner固定unknown。沒有模型、原生來源query、ACK或敏感處置。

命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-investigation-20261026-01 --timeout-seconds 240 --module test_event_investigation：首14/14。擴充10模組02為151/150pass/1通知skip；審查定位跨episode的序號／同時metadata不應直接比較，停止該判定路線，最低成本綁episode_ref，增加正常多端點與序號重置負控制。03命令同10模組（完整argv在summary），152/151pass/1同skip/0failure/error，UTC13:32:15.829372–13:32:55.929317，39.046秒，209Python AST無錯、source_unchanged=true、guardian自然0／remaining0／無強停／逐測試殘留0。

產品命令 py -3.13 -B reports/investigation-product-20261026-01/exercise.py：私有Job執行worker，CLI建案後實際IAB點查看／更新保存，保存web-saved.png／web-reopened.png與AX；合作關頁／重開server後同案件恢復，14核對全true，8件仍pending／ACK0，原HANDLE自然0／Job0／無強停。頁面頂部監看控制刻意未綁定，顯示未知且停用，未啟動採集。

episode修正後命令 py -3.13 -B reports/investigation-product-20261026-02/exercise.py：UTC13:35:07.530143–13:35:08.773920，最終來源8檔hash相符，CLI→HTTP GET→同源POST→CLI→Web關閉／重開→CLI同case，14/14。producer-manifest保存本輪8個完整synthetic輸入；related恰2、6負控制排除，資料庫保持8 pending／0 receipts／1 case，reopen讀前後hash不變；worker自然0/Job0/無強停。01視覺屬相同web.py、不能把01舊engine source說成最終；02保留最終來源hash及HTTP／SQLite產物。

有限量測02：一次CLI建案0.0891329秒、HTTP存0.027727秒／重開讀0.0071434秒；source DB49152→57344B、case JSON2574B。入列8件後、單次建案前後自身CPU0.671875→0.734375秒，private bytes25288704→24354816、handles120→120。只有自身pseudo-HANDLE兩點快照，非峰值、整Job、分析員調查時間或受控競品基準；不拿RAM下降判長期成長率。沒有本次真模型／native採集。CrowdStrike／SentinelOne官方宣稱、方法、未測與實際程式對照在MAINTENANCE_GOAL同一表，沒有宣稱超越。保留原真04、1563pass及舊idle的scope。

純格式界線：web.py原有mixed換行不作整檔格式重寫，以git -c core.whitespace=cr-at-eol diff --check核對。執行資料／SQLite／授權不提交，僅本機commit、不push。接續P1-INVEST-002只讀已保存診斷，不由listeners待批阻擋全部離線工作。


## 2026-10-26：observer長窗、原生閘道與所有權競態（最新）

操作交付增量（2026-10-26T07:43:13.5264320+00:00，基底 d805ec5）：修正 AGENT_SERVICE 的「真投遞未完成」舊文字，新增可用入口、單事件 service 命令、五份固定 JSON 的 PowerShell Get-Content／ConvertFrom-Json 查閱、固定 metadata 結果與人工處置／ACK 界線；README導入，CONNECT_AGENT／LIVE_CHANNEL指向現行無每日五次的 App/service，保留舊相容流程。獨立審查修正「所有失敗仍pending」誤述：ACK後收尾失敗不回退來源。

唯讀驗證：PowerShell Parser.ParseInput 核對新讀檔區塊，Get-Content／ConvertFrom-Json 核對同event/query/result及既有三工具／自然退出摘要，Get-FileHash前後核對五份原證據與baseline manifest綁定的11個來源檔、四份操作文件本機連結；reports/operator-entry-review-20261026-01/validation.json 為17/17、failed_checks空、model_tasks_started=0、native_queries_started=0、subprocesses_started_by_check=0。未重跑真ACK、完整回歸或verify-only，未啟動任何collector；原baseline仍無human-approval.json／intent／result／outer-start，template未批准。只文件變更，沿用1563pass／3skip／0fail及真04原證據，未宣稱重新驗收。提交前執行 git diff --check；runtime報告不提交、不push。

基底4a1a95b，Python3.13.3，一般使用者；模型／原生掃描在本增量測試中均0。既定真04五層退出／三工具各1的原證據未重跑或覆寫。

- observer根因：reports/soak-observer-cprofile-20261026-01，12秒受控cProfile，record累積wall .809478秒，其中usage .775133秒≈95.8%；內層_guard與stat為重疊累計，不相加當CPU。原worker自然0/Job0。修正僅排空後單writer byte accounting重用；每append guard/size/cap及mutation/phase/final全樹檢查保留，非即時防篡改。
- `py -3.13 -B scripts/verify.py --run-dir reports/verify-soak-observer-budget-20261026-01 --timeout-seconds 180 --module test_soak`：11/12，恢復語意fixture12件I/O超20秒；原失敗保存。該fixture改虛擬monotonic/sleep而SQLite仍真，02同命令12/12，UTC17:06:53–17:07:22、source_unchanged、自然0/Job0，非性能證據。
- `py -3.13 -B scripts/soak.py --root reports/soak-measured-20261026-03 --duration-seconds 180 --min-wall-seconds 60 --pacing-seconds .05 --max-events 16`：UTC17:07:38起，真wall60.012212秒／16ACK／pending0，idle31.411523秒CPU0.945115%；50樣本皆有效，原Job自然0。跨輪host I/O未控制，觀察下降非單因果證明。
- `py -3.13 -B scripts/soak.py --root reports/soak-idle-30m-20261026-01 --duration-seconds 1980 --min-wall-seconds 1900 --pacing-seconds .05 --max-events 16`：UTC 2026-10-25 17:12:21–17:44:01（台北 2026-10-26 01:12:21–01:44:01+08:00），1900.017392秒、475樣本。measurement-crosscheck.json獨立32/32、SQL mode=ro+query_only+closing、原artifact hash未改。最後真樣本窗為 UTC 2026-10-25 17:13:58.791556–17:44:01.281371、1802.489810秒／450筆，CPU6.1875秒=0.343275%；private首14061568B／峰14135296B，峰增73728B<32MiB；handles首/峰/末111，增0<20。完整idle1874.956124秒；非插值恰1800秒、非24h/整Job/production。原HANDLE1432自然0、remaining0、無強停，7source hash相符。
- `py -3.13 -B scripts/verify.py --run-dir reports/verify-windows-listener-gate-20261026-01 --timeout-seconds 180 --module test_windows_listener_validation`：13/13；追加固定stop watcher及兩個行為fixture後02為15/15、UTC17:26:35–17:26:50，自然0/Job0/source_unchanged。mock collector未查原生；完整/denied/partial/forced/unknown、批准缺失/失效/錯scope/hash、intent fsync故障、loopback無候選與wildcard兩輪恢復分開驗證。
- `py -3.13 -B scripts/validate_windows_listener.py --root reports/windows-listener-baseline-20261026-01`：只prepare，無collector、query_started=false。AUTHORIZATION_REQUEST.md與未批准template保留；非同步請求尚未回覆，沒有執行--execute。外層reports/windows-listener-preparation-20261026-01/run-owned.py保留原HANDLE、20秒觸發合作stop／3秒grace／僅原Job，固定錯誤摘要、無raw console；未以source/fixture資料當人類授權。
- `py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261026-03 --timeout-seconds 1800`：UTC17:27:59–17:38:48，1561／1556pass／3skip／2fail，無error/殘留、source_unchanged、自然exit1/Job0。兩fail為App pause的monitor_ownership_changed、SDK stop的background_owner_changed。原trace及回條保存，不能改稱環境flaky或綠。
- 修復：background.py以鎖內selected_owner作scoped_run/stop target，不用可能缺失/過期的status；App僅固定unverifiable作一次完整重觀測，同owner/liveness verified才控制，foreign/持續unknown拒絕。新增2+3確定性fixtures，已通過對應回歸。定向命令在reports/verify-owner-snapshot-races-20261026-01/verification-summary.json（8模組完整argv）；最新完整回歸 1566 項／1563 通過／3 略過、0 failure/error；source_unchanged=true，原Job自然0／remaining0／無強停。
- P0定向guardian：126項125pass／1通知圖示略過，UTC17:48:10–17:49:40、source_unchanged、自然0/Job0，原兩個實際失敗與新增確定性fixtures都過，無逐測試殘留。最新完整命令：py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261026-04 --timeout-seconds 1800。UTC 2026-10-25T17:51:54.025484+00:00 至 2026-10-25T18:02:08.911585+00:00，613.649秒；最新完整回歸 1566 項／1563 通過／3 略過、0 failure/error；source_unchanged=true，原Job自然0／remaining0／無強停。 三項略過為兩項symlink creation unavailable及一項notification_icon_unavailable；model_calls0、machine_scan_executed=false。

本切片變更檔案：src/eventguard/application.py、background.py、soak.py；scripts/validate_windows_listener.py；tests/test_application_controls.py、test_background.py、test_soak.py、test_windows_listener_validation.py；STATUS.md、HANDOFF.md及docs/EVIDENCE.md、MAINTENANCE_GOAL.md、SOAK_PLAN.md、WINDOWS_VALIDATION_PLAN.md。前一4a1a95b的公告分頁、store/view、agent status與GUI/Web等23檔清單在該commit，最新頂部沿用對應真公開分頁及產品頁面證據，不重跑模型。

本版來源commit由提交後各source-commit.json綁定，reports/SQLite/授權/native輸出只留本機；不push。所有成功判斷保持scope，未評估主機安全。

## 2026-10-26：產品呈現、canonical 分頁、guardian與資源量測

基底 9a34a5b，分支 feat/local-codex-acceptance；依既有授權繼續，未 push、未改系統／帳戶設定。AGENTS 的 Continuous Execution Policy 已在 a34e466 逐字加入，繼續有效。

- P2-MCP-STATUS-001：CLI／Web／Tk 加入有界 MCP 退出摘要，從當次 attempt 原始 marker／HANDLE 證據重讀；舊資料、缺檔、外來 run 或非零皆維持 unknown，不信任快取的 verified。實際閒置 test App 的 API／CLI／瀏覽器一致顯示「MCP退出已驗證、退出碼0、ACK flush」。GUI 關閉後原 HANDLE 自然0／Job0／無強停，collection/model/新增CLI 均0。真04原64檔hash全不變；只新增App descriptor/lock。
- P1-SOAK-GUARD-002：spawn後任何有界異常先嘗試耐久 stop.request，再 grace／原自有Job收尾；保存失敗維持 unconfirmed。P2-SOAK-MEASURE-001：獨立 minimum wall、pacing、僅本worker pseudo-HANDLE的 CPU/private bytes/working set/handle 採樣，未知=null，JSONL有界。兩輪真有限harness各16 accepted/16唯一ACK/pending0，wall 60.037116／60.045564秒，皆自然0／Job0，非模型、OS重啟或24h。
- P2-GH-PAGES-001：GitHub有界分頁，預設5／最多8頁；一次固定metadata驗證 canonical repository ID，最多max_pages+1 GET，共用bytes/deadline；僅forward after或連續page，固定origin/path/filters/page-size，拒redirect／循環／混用／錯誤mapping。partial保留last-good、304不得洗完整；完整success才清舊單頁validators；max_pages屬resource policy，不使legacy cache換binding。

定向14模組253項252過／1通知圖示略過；首輪完整1534項1530過／3略過／1舊dict斷言失敗，已補新增unknown欄位後77/77。真canonical/after與soak增量定向201/201。最新完整回歸 1543 項：1540 通過、3 略過、0 failure/error，source_unchanged=true，guardian自然0／remaining0／無強停，model_calls0、machine_scan=false。原失敗不覆寫。

真公開分頁04：兩公告頁＋一次metadata GET，uv repo id699532645，17369/65536 bytes，1.305084秒；正確partial/github_pagination_page_limit，兩頁smoke及27項獨立核對通過。追加05按預設5頁上限仍partial，完整來源要求未達；只寫隔離test cache，未改正式cache，不再加大cap洗綠。早期01 transport_denied及wrapper無效finish reason缺退出回條、02/03 canonical不相容均保留。

資源實測：降低harness輪詢20Hz→4Hz後，短窗idle CPU 4.392866%→4.069045%單核心，仍未達<1%目標；兩次不是受控主機負載實驗，不能認定因果，更不代表產品monitor性能。下一項 P2-IDLE-CPU-003 只診斷自身harness observer成本，根因有證據才修。30分鐘idle／24h／全Job資源與實機來源仍未驗。

證據目錄：reports/verify-product-pagination-metrics-20261026-01、verify-agent-status-compat-20261026-01、verify-github-cursor-soak-20261026-01、verify-full-20261026-01/-02、soak-measured-20261026-01/-02、mcp-status-product-20261026-01、public-fetch-github-pages-20261026-01…05。原先 receive→query→result→ACK 及五層退出真證據仍是 reports/service-acceptance-eventguard-mcp-exit-20261025-04；本切片沒有重跑模型。執行資料不提交。


主要命令與UTC證據：

- py -3.13 -B scripts/verify.py --run-dir reports/verify-product-pagination-metrics-20261026-01 --timeout-seconds 600（14個 --module，完整argv在summary）；UTC16:27:43–16:28:30，253／252pass／1skip。
- py -3.13 -B scripts/verify.py --run-dir reports/verify-agent-status-compat-20261026-01 --timeout-seconds 300 --module test_agent_service --module test_mcp_status --module test_dispatch_inspection --module test_agent_dispatch；UTC16:39:07–16:40:15，77/77。
- py -3.13 -B scripts/verify.py --run-dir reports/verify-github-cursor-soak-20261026-01 --timeout-seconds 600（10個 --module，summary保留完整argv）；UTC16:44:23–16:45:16，201/201。
- py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261026-02 --timeout-seconds 1800；結束UTC 2026-10-25T16:54:30.401615+00:00，1543 項：1540 通過、3 略過、0 failure/error；三項略過原因由summary保留。各輪原HANDLE/Job回條、逐測試輸出、source-manifest均保存。
- py -3.13 -B scripts/soak.py --root reports/soak-measured-20261026-01 --duration-seconds 180 --min-wall-seconds 60 --pacing-seconds .05 --max-events 16；02同參數且root換新，runtime來源唯一差異為wait上限.05→.25。兩份measurement-crosscheck與compare-to-first另核對原資料hash、mode=ro/closing SQL、樣本PID、單調CPU、byte cap；59個樣本皆有效、handles皆111，無截斷。idle_after43.749913／45.311611秒，不能稱60秒idle。
- 產品驗證：reports/mcp-status-product-20261026-01/run.py啟動私有Job的閒置Application，test/custom source、collector/notification/MCP disabled；read-product.py讀同instance API與CLI，瀏覽器實按Agent頁與關閉程式。product-crosscheck.json、browser-ax.txt、agent-status-detail.png與process-exit.json交叉一致，原64檔不變；不讀原始Codex sessions。
- 公開GET由私有Job worker執行，01工具sandbox傳輸拒絕；02起使用逐命令一般使用者sandbox例外，不是Windows提權／UAC／系統網路變更。無Authorization/conditional，沒有原始body或完整例外。04 public-fetch-crosscheck核對同origin、ID mapping、剩餘timeout逐次下降、bytes與原HANDLE自然退出；無每request原始monotonic或body，因此不宣稱可獨立重算所有網路bytes或可即時打斷OS blocking syscall。


## 持續工程：P2-MCP-EXIT-001 與 P1-SOAK-001 實作、失敗恢復及驗收

基底 a34e466be965b7d3b1a634081cce367d28d91918，branch feat/local-codex-acceptance。增量核對主checkout/remote/worktree，只在本專案工作；其他worktree、附件與研究稿保留。既有真03與完整1477回歸不重跑、不替代新切片驗證。維護目標已加入有ID、驗收、依賴、權限與下一步的持續佇列。

### P2-MCP-EXIT-001：ACK flush 後自然退出與所屬 Job HANDLE 證據

變更 application_stdio.py 的可選 response_flushed 同步callback：完整 write 且 flush 成功後才呼叫，short write／flush失敗不回呼，callback異常固定原因碼；非Windows帶callback明示不支援，預設observer與SDK lazy import保留。

eventguard_inbox_mcp.py 新增專用 --exit-after-ack：handler僅綁定真正request_context ID與durable ACK完整dict，transport flush該精確成功response後才set Event；沿用既有Windows PeekNamedPipe合作輸入，沒有timer假保證或關閉其他程序。readonly/operator observer不套用。stdio-exit marker記 ack_response_flushed／one_shot，仍不單靠marker聲稱OS退出。

processes.observe_owned_member只對原JobPopen仍持有的私有Job，OpenProcess(0x101000)核對PID/creation/Job membership並保留query/synchronize HANDLE，不授予terminate權限。mcp_lifecycle綁活體start與同HANDLE exit，純讀assessor再對照CLI capture及三phase marker；missing/denied/identity mismatch/unknown均false。capture只讀固定marker，從不根據外部PID強停。validate_delivery新增可選 --require-mcp-exit，結果另存mcp-exit-validation，不把舊缺證據升格。

定向命令：py -3.13 -B scripts/verify.py --run-dir reports/verify-mcp-exit-soak-20261025-01 --timeout-seconds 600 --module test_application_stdio_transport --module test_application_stdio --module test_mcp_one_shot --module test_owned_member_observation --module test_mcp_lifecycle --module test_inbox_startup_evidence --module test_agent_dispatch --module test_delivery_validation --module test_process_governance --module test_soak。UTC15:45:39–15:48:15.992638，Python3.13.3；117測試116過1error，失敗只在soak temp SQLite鎖檔收尾。其餘114項MCP/transport/Job測試通過（含SDK保持client stdin開啟而ACK後server自然0、query HANDLE同Job防偽），2項其他soak測試也過。source_unchanged=true，guardian自然exit1/remaining0/無強停，model_calls0，無逐測試殘留。此輪整體passed_checks=false，保留原錯誤。

修復soak.py::_receipt使用contextlib.closing，避免SQLite transaction context被誤當close。py -3.13 -B scripts/verify.py --run-dir reports/verify-soak-close-20261025-01 --timeout-seconds 120 --module test_soak，UTC15:50:16–15:50:32.493694；3/3、0failure/error/skip、source_unchanged=true、guardian自然0/remaining0/無強停、model_calls0。未為此修復重跑未受影響114項。

真04：全新 reports/service-acceptance-eventguard-mcp-exit-20261025-04，human-approval先記最新持續工程/先前解除次數上限授權；單一synthetic event、一個nativeCLI任務、180秒有界，無系統/帳戶/全域MCP變更、無UAC。固定CLI SHA256仍1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098。經批准的單次工具沙箱例外執行 run-authorized.py，內層 validate_delivery.py service --root <當次root> --codex-executable <既有nativeCLI> --execute --require-mcp-exit。

唯一event evt-a6e83a0f0b754013952fca894cd615b8；query query-e85382e01908af81ab062291cd2a317c4e5dd406；result result-f74e17df447ef06d4161e92ff6f13f39767ce234；attempt c80429f00b0f4da28342c84f81ca29dd；thread 01a173c2-ca5c-7462-8950-7506d82c9e71。三工具各1、events1/receipts1/pending0/hash一致。活體query HANDLE於15:51:48.709791Z取得；receive15:52:03.738→query07.428→結果10.620→ACK10.671993→stdio-exit10.842307→同HANDLE exit snapshot17.877339，順序及owner/member匹配。outer15:51:40.490903–15:52:23.919237，43.442485秒；MCP/CLI/supervisor/host/outer皆exit0，其他四層Job remaining0/forcibly=false，MCP正常退出marker與held HANDLE共同證明自然退出。無模型請求數量測，勿以1任務當1請求。

communication-result與mcp-exit-validation均passed=true；獨立mode=ro/trace/217來源+3runtime hash核對一致。py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-mcp-exit-20261025-04 --verify-only --require-mcp-exit 於15:54:53.166982Z重讀仍通過、未啟新模型。主要證據為該root validation.json、mcp-exit-validation.json、communication-result.json，attempt下5份mcp-start/list/stdio-exit/process-start/process-exit與capture/supervisor回條。history warning布林false不推全IO隔離，也不代表桌面喚醒。

### P1-SOAK-001：有限 synthetic 整合與有界失敗恢復

新增src/eventguard/soak.py、scripts/soak.py、tests/test_soak.py。producer原事件/hash先耐久保存；consumer暫停填滿、拒絕ID/hash保留、pending不變；注入一次completed保存失敗，驗pin保護、維護不刪未完成proof；重建QueueInbox同query收尾與冪等ACK，再重新接受原被拒ID/hash並排空。accepted=uniqueACK+pending、交集空、hash一致；完整歷史由本輪manifest保留，產品可按政策輪替已ACK資料。controller在Job before run，有限deadline/事件/bytes、原HANDLE退出；只synthetic API，模型/網路/原生採集0。

第一輪命令 py -3.13 -B scripts/soak.py --root reports/soak-finite-20261025-01 --duration-seconds 60 --max-events 64：實際60.499713秒，soak_work_deadline_reached，52接受/52唯一ACK/0pending，另12原producer未入列仍在manifest；guardian自然exit2/remaining0/無強停，validation=false。純讀producer/progress/SQLite守恆重驗通過，只證明無丟失，不將未跑完改成功。

第二輪同64件，另新目錄 py -3.13 -B scripts/soak.py --root reports/soak-finite-20261025-02 --duration-seconds 180 --max-events 64；實際81.881672秒，64接受/64唯一ACK/0pending/0unaccepted，滿載恢復、一次completion故障與同query恢復均成立。guardian自然exit0/remaining0/無強停，source_unchanged=true、validation=true；conservation-recheck重算無errors。duration是工作上限，可提早結束，未宣稱60秒profile通過、24h、OS重啟、agent收件或資源效能驗證。資源採樣與最小wall-time待下一切片。

本checkpoint未跑完整回歸；既有1477只作前版基準。所有新reports/原失敗/SQLite/回條留本機不提交；程式、測試與四份現有工程文件集中提交並綁source-commit。保存後自動接續P1-SOAK-GUARD-002、P2-SOAK-MEASURE-001與P2-GH-PAGES-001，不以commit停止。實機來源/正式發布仍需各自明確範圍，未push。

## 2026-10-25：新開發授權下真 receive→query→結果→ACK 通過（最新）

基底 `836d0df8baccebb5d84b0cd7c5a1c4679f45bcaf`，分支 `feat/local-codex-acceptance`。人類最新原文「解除額度限制，與各種阻擋限制，請全力開發」撤銷前輪兩次真 CLI 上限與暫停接線。新授權與 UTC 時間先記入當次 human-approval.json；本輪只用了 1 個真 CLI 任務，每次仍採一件合成事件／單任務／180 秒有限驗收，不更改系統、帳戶或全域／專案 MCP 設定，不移植憑證、手讀原始 sessions 或 push。兩個舊失敗與 pending／ACK 0 原樣保留。

### 里程碑①：配置與能力先以無模型證據定位

`reports/native-mcp-metadata-20261025-01/run.py` 在自有 Job 執行現有原生 CLI 的同組生成配置＋mcp get eventguard_inbox --json。UTC 14:34:42，自然 exit 0／remaining 0／無強停，stderr 0；enabled=true、stdio、固定 Python/args、三工具 allowlist、startup 20／tool 60 秒。只保存已知 inbox 欄位；不讀全域設定原文、認證或 session，環境只記 CODEX 變數名稱、不存值。required 欄位未由該 metadata 輸出提供，不以 null 斷言不生效。結果在同目錄 result.json。

`reports/native-cli-capabilities-20261025-01/run.py` 於 14:37:58 執行 features list／exec --help／debug --help；`reports/native-prompt-help-20261025-01/run.py` 於 14:40:41 只取 debug prompt-input --help。均自然 exit 0、remaining 0、stderr 0、模型 0。已安裝 build 將 sqlite 列 removed true，因此沒有猜測關閉旗標。prompt-input 文件只承諾 input list，不作工具曝光證明；沒有執行 prompt/context dump。[官方 MCP](https://learn.chatgpt.com/docs/extend/mcp)、[非互動模式](https://learn.chatgpt.com/docs/non-interactive-mode) 與本機 metadata 分開採證。

### 里程碑②：最小程式與定向驗證

`scripts/eventguard_inbox_mcp.py` 新增可選 --startup-evidence-dir，只准傳入 project root 的 data/logs/reports 子樹、拒 redirect／重用；安全 marker 只含程序／instance、時間、固定 phase／工具名，無 env／完整命令／事件 payload。未指定的既有 observer 不產生 marker。SDK list_tools 只記 response_prepared，不冒稱 agent 已收件；stdio-exit 明示 os_exit_verified=false。

`src/eventguard/agent_dispatch.py` 顯式 enabled=true，保留 required=true、20 秒 startup、60 秒工具期限與三工具 allowlist；加入 attempt marker 目錄。移除每次 fresh sqlite_home，使用原生 CLI 已初始化的狀態，保留 --ephemeral、單次 history.persistence=none、專用 log_dir。減少主動重建索引是待實測假說，不是完整 IO 隔離保證。未混入父程序環境清理或工具搜尋等未證候選。

`tests/test_agent_dispatch.py` 補命令契約；新 `tests/test_inbox_startup_evidence.py` 5 項測試涵蓋 runtime 子樹／redirect／observer 無 marker／初始化失敗固定 exit marker，以及真 SDK JSON-RPC initialize→tools/list→EOF，事件不 receive、不 ACK。命令 `py -3.13 -B scripts/verify.py --run-dir reports/verify-inbox-startup-evidence-20261025-01 --timeout-seconds 300 --module test_inbox_startup_evidence --module test_agent_dispatch --module test_queue_inbox --module test_delivery_consolidation`。Python 3.13.3，UTC 14:43:37.99–14:44:41.979206（台北 22:43:37–22:44:41）；54 run/pass、0 failure/error/skip、source_unchanged=true、passed_checks=true，guardian 自然 exit 0／remaining 0／無強停、model_calls 0。該目錄保留 source-manifest、unit-tests、lifecycle 與 guardian 回條。

### 里程碑③：真收件與原始證據重驗通過

新目錄 `reports/service-acceptance-eventguard-development-20261025-03`，prepare 命令 `py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-development-20261025-03`。human-approval.json 先記最新授權，使用已驗 runtime wrapper、既有 Python 3.13 與同一 native CLI（SHA256 `1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`）。經自動批准審查許可單次工具沙箱例外，執行 `py -3.13 -B reports/service-acceptance-eventguard-development-20261025-03/run-authorized.py`，其固定內層為 validate_delivery.py service --root <當次root> --codex-executable <同native CLI> --execute；仍為一般 Windows 使用者、CLI read-only、Job 執行前綁定。

外層原 HANDLE 建立 14:45:35.160074Z，完成 14:46:24.460919Z，49.314202 秒（台北 22:45:35–22:46:24）。service 先空佇列閒置、14:45:40.746686Z 入列後才啟動唯一 CLI，完成後再次閒置再合作停止。

唯一 event `evt-c8062b5b20af4d5ba2da37a7b64afbd9`，query `query-85018bad257d934db1abe6b32f067cef897baa73`，result `result-2ca68cd2b51688866fe9bf20fc8059b3eca3d29f`；host run `50769a4ff7004ad5b490e98bf4faf517`，attempt `d77738f895154561bc04c7a5577b8050`，CLI JSONL thread `01a17386-45bc-71e3-ada2-0d9ba99971c0`。

CLI JSONL 真工具完成順序 receive_event→query_evidence→ack_event，計數各 1。UTC receive 14:46:00.113→query 14:46:04.985→結果保存 14:46:09.326→SQLite ACK 14:46:09.354601。mode=ro 獨立核對 payload hash、各 ID 及回傳一致；events 1／receipts 1／pending 0、無缺漏／重複。模型請求數未量測，不以一個 CLI 任務或完成回合數當模型請求數。

CLI、capture worker／supervisor、host、outer validation 都有原 HANDLE／Job 自然 exit 0、remaining 0、forcibly_terminated=false；outer capture_complete=true、無輸出截斷。validation 與 communication-result passed=true，chronology／monotonic／lifecycle／idle-before-after／one-attempt 全驗證。`py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-development-20261025-03 --verify-only` 於 14:47:21.957069Z 重讀原始證據仍 passed=true，未新啟模型。執行來源 210 檔／runtime 3 檔與快照一致；同一 run 後續不重用。

本次有同 instance／PID 的 mcp-server-started 與 mcp-tools-listed marker，精確三工具；沒有 mcp-stdio-exit.json。後查已記錄 MCP PID 為 missing，CLI owned tree 已空，但沒有 MCP 自身原 HANDLE／OS 退出碼，不可推為其獨立自然退出。這是額外證據限制，不取代或否定原契約明列 CLI／worker／host 的自然退出回條。當次只檢查固定字串布林：legacy metadata／invalid transport／WSA 10013 均 false；未手讀原始 sessions，不以無警告宣稱完整 IO 隔離。組合修正已成功，不宣稱哪一項改動是唯一根因。

主要證據：當次根目錄 `communication-result.json`、`validation.json`、`acceptance-crosscheck.json`、`communication-final-status.json`、`human-approval.json`、`execution-source-manifest.json`、`runtime-source-manifest.json`、`execution-intent/start/exit.json`、`service-owner-stop.json`；上述 run/attempt 下 CLI JSONL、capture-start/exit、supervisor-start/exit、summary 與兩份 MCP marker。資料、授權、原始 CLI 輸出與 SQLite 只留本機 reports，不提交。

完整回歸：`py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261025-05 --timeout-seconds 1800`，台北 22:48:26–22:55:41。1477 項：1474 通過、3 略過、0 failure/error；兩項 symlink 不可用、一項 notification_icon_unavailable。passed_checks=true、source_unchanged=true；guardian 自然 exit 0／remaining 0／無強停、無逐測試殘留，model_calls 0、machine_scan_executed=false。證據 `reports/verify-full-20261025-05/verification-summary.json`；提交後 source-commit.json 綁定本版受測來源。

本輪沒有正式長期監看、實機掃描、服務／排程／UAC／帳戶設定或推送。既定專用 CLI 真收件目標已通過；MCP 自身退出擴證、完整 IO 隔離、長期運行與既有桌面聊天／dot 喚醒列 DEFERRED，不把合成 ACK 當主機安全／風險處置。舊兩次失敗證據與 pending 原樣保留。

## 2026-10-25：里程碑診斷、第二次真任務未收件、必要 MCP 契約修正（最新）

本輪基底 `c5401e910b4939af9de4d0afe060f7026ec540fa`，分支 `feat/local-codex-acceptance`。接手追蹤檔乾淨；既有 `.codex-remote-attachments/`、`docs/research/` 保留不提交。使用者要求最小可驗證增量、里程碑回報；沿用先前明確授權的第二次（最後一次）真通訊額度，沒有新建持續模型權限或改動系統／帳戶設定。

### 里程碑①：無模型連線對照完成

`reports/connection-diagnostic-20261025-01/probe.py` 使用既有 Python 標準庫，僅對 chatgpt.com 發 unauthenticated HEAD、不附憑證、不送事件。`run-probe.py` 在私有 Job 內啟動同一 probe，保留原 HANDLE。

命令 `py -3.13 -B reports/connection-diagnostic-20261025-01/run-probe.py sandbox`：UTC 08:25:19.487640，transport_reachable=false、os_error_code=10013；自然 exit 0、remaining 0、無強停。其後經自動批准審查允許單次工具沙箱例外，以同一 Windows 一般使用者執行 `.../run-probe.py approved-user`：08:25:49.983805，HTTP 403、transport_reachable=true，程序亦自然 exit 0／remaining 0。沒有 UAC、Windows 權限提升或設定變更。這支持執行環境差異解除通訊端拒絕症狀；不能以 HTTP 403 推定模型／帳戶授權。證據 `sandbox.json`、`approved-user.json`、各自 start/exit 回條與 `comparison.json`；模型任務 0。

### 里程碑②：外層收尾補驗完成

只在 `reports/invocation-proof-20261025-01` 保存單次 runtime `invocation.py`／`selftest.py`，未新增核心抽象。沿用 processes.spawn/finish；argv[0] 是絕對 sys.executable，執行前私有 Job；spawn 後 finally 保留原 HANDLE，合法 reason 為 descendants_remaining／timeout／owner_exception，stdout/stderr 各有界，intent 單次、沒有重試。合作 stop 先核對 manifest／owner／control 的 application_owner 與原 child identity 及 source/state 範圍，總期限預留 15 秒清理。

命令 `py -3.13 -B reports/invocation-proof-20261025-01/selftest.py`，UTC 08:30:08–08:30:14：4/4 通過。自然 exit 0、自然 exit 2 均有原回條；超量 stdout/stderr 各留 1024 bytes、明示 truncated；合成不合作逾時案例 expected_forced=true，只終止其自有 Job、exit 1460、remaining 0、約 4.232 秒，另一 Job sentinel 仍 alive 後自然 exit 0。外層 selftest guardian 自然 exit 0、remaining 0、無強停。自測 scope 明示模型／網路均 0，不能把「所有測試無強停」寫成通過條件。主要證據 `selftest-summary.json`、`case-*/execution-exit.json`。

### 里程碑③：第二次真任務完成回合，通訊驗收仍失敗

新目錄 `reports/service-acceptance-eventguard-single-test-20261025-02` 以 `py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-single-test-20261025-02` prepare，沒有模型。事前核對前目錄 capture-start 僅 1、新目錄 0；manifest 一件 synthetic、無 service_execution。固定 native CLI SHA256 仍為 `1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`。`human-approval.json` 執行前記錄原人類「失敗可新目錄，最多兩次」授權與時間；execution-source-manifest 與 runtime-source-manifest 保存來源快照。

經自動批准審查允許本命令的工具沙箱例外，執行 `py -3.13 -B reports/service-acceptance-eventguard-single-test-20261025-02/run-authorized.py`；它使用經自測的 wrapper 與相同 Python 3.13 直接執行 `scripts/validate_delivery.py service --root <第二次root> --codex-executable <相同native CLI> --execute`。仍為一般 Windows 使用者、read-only CLI sandbox、同三工具與最小資料配置；不改全域／專案 MCP、系統或帳戶設定，不提權、不加繞過旗標。外層原 HANDLE 建立 08:31:27.664743Z，結束 08:33:33.574558Z，elapsed 125.921415 秒（台北 16:31:27–16:33:33），在 180 秒界線內。

唯一 event `evt-21ad65fcd92b42fda49755a57d27ee4b`，host run `e69dbd4a9b4b406eae41e76782482de2`，attempt `255b34adfb2640f8ad5e8e9e93791a2a`，本次 JSONL thread `01a17231-2d7e-7861-9a8f-15f4be37c430`。trace 有 thread.started、turn.started、兩則 agent_message、turn.completed；agent 回報工具未提供，停止未重試。provider_turn_completed=true、CLI 自然 exit 0；沒有 MCP tool call。固定結果類別 `required_mcp_tools_unavailable` 只描述可證表現，MCP 載入根因仍 unknown。沒有 WSA 10013、invalid transport 或 HTTP 401 證據。

`collect-evidence.py` 只讀當次資料；SQLite 以 mode=ro：events 1、pending 1、receipts 0、無重複。QueueInbox.open_readonly 無此 event evidence，query/result ID 皆 null；生成／入列各 1，receive/query/result/ACK 皆 0，summary passed=false。失敗發生在 verify_service 之前，因此 validation.json 不存在，沒有補造。CLI／supervisor／host 自然 exit 0；outer validation 自然 exit 2。各層 managed／child_exited=true、remaining 0、forcibly_terminated=false，outer capture_complete=true、無截斷、original_handle_retained=true。自然退出與業務成功分開記錄。

主要證據：根目錄 `communication-result.json`、`communication-final-status.json`、`execution-intent/start/exit.json`、`human-approval.json`、`service-owner-stop.json`、`manifest.json`；上述 run/attempt 下 `codex.jsonl`、`codex.stderr.txt`、`summary.json`、capture-start/exit 與 supervisor-start/exit 回條。`source-state-note.json` 明示實測基底 c5401e9；下述 source/tests 修改在實測結束後，收集時 source hash 比較已不同，不能說新版已真驗。執行資料只留本機忽略的 reports，不提交。

隱私邊界另記：CLI 當次 stderr 自帶歷史 rollout metadata 索引警告。操作者沒有另行開啟那些原始歷史檔案，也未把路徑／內容複製到公開文件；但不能保證 CLI 內部未讀歷史，此隔離行為仍需釐清。後續不新增任何 CLI 命令，不以調整未核實 feature 旗標或複製 Codex home／憑證來避開限制。

### 最小無模型修正與驗證

`src/eventguard/agent_dispatch.py` 單次 eventguard_inbox MCP 配置增加 required=true、startup_timeout_sec=20，保留 tool_timeout_sec=60、原 stdio command/args 與 allowlist。目的是避免必要 server 初始化失敗後繼續空工具回合；[官方非互動模式](https://learn.chatgpt.com/docs/non-interactive-mode) 說明 required=true 的初始化失敗即退出契約，[MCP 文件](https://learn.chatgpt.com/docs/extend/mcp) 說明 startup/工具期限。此為保守配置修正，不宣稱實測工具缺失根因已修復。

`tests/test_agent_dispatch.py` 增補既有 TOML／disabled transport 契約，涵蓋 live/test、ACK／readonly 工具清單與期限。命令 `py -3.13 -B scripts/verify.py --run-dir reports/verify-required-inbox-20261025-01 --timeout-seconds 300 --module test_agent_dispatch --module test_delivery_consolidation --module test_delivery_validation`。Python 3.13.3，UTC 08:37:47–08:38:51.643418（台北 16:37:47–16:38:51）；60 run/pass、0 failure/error/skip，source_unchanged=true、passed_checks=true，guardian 自然 exit 0／remaining 0／無強停、model_calls 0、machine_scan_executed=false。`git diff --check` 通過。證據 `verification-summary.json`、source-manifest、unit-tests、lifecycle 與 guardian 回條；提交後 source-commit.json 綁定本版受測來源。沒有重跑完整回歸，也沒有新版真 CLI 重驗。

補充最低成本交叉檢查：`py -3.13 -B reports/sdk-inbox-discovery-20261025-01/probe.py`，UTC 08:45:48（台北 16:45:48），標準庫 JSON-RPC client 以現有單次 command 的 server command/args，對同一第二次 root／source／inbox／event 啟動已安裝 MCP SDK 1.6.0 server；只發 initialize、notifications/initialized、tools/list。三工具 receive_event/query_evidence/ack_event 都可探索；沒有 tools/call、模型任務或 native CLI。mode=ro 前後核對 events 1／pending 1／receipts 0 不變。私有 Job 原 HANDLE 證明 server 自然 exit 0、remaining 0、無強停。證據該目錄 result.json。這支持同範圍 server 本身能啟動與列工具，剩餘阻擋在原生 CLI 載入／工具曝光的未明差異，不能當真模型已呼叫工具或 required 修正已真驗。

本輪兩次真 CLI 額度已用完（兩目錄各 capture-start 1），第三次必須新授權；不得重用已執行目錄。BLOCKERS：額度耗盡、MCP 工具缺失根因 unknown、CLI 內部歷史隔離待釐清。DEFERRED：wrapper 產品化、完整回歸、長期與桌面喚醒驗證。保留兩件 pending／ACK 0 與第一輪原失敗，無當前測試背景程序留存。只提交程式、測試與文件，未 push。

## 2026-10-25：一次真 CLI 通訊失敗與失敗早停修正（最新）

基底 `ea00c7023ac532e08d1a2c3eff4d5e7d611b5b67`，分支 `feat/local-codex-acceptance`。接手唯讀核對 HEAD／分支符合；追蹤檔乾淨，既有未追蹤 `.codex-remote-attachments/`、`docs/research/` 保留且不提交。先讀 AGENTS、README、STATUS／HANDOFF 頂部、EVIDENCE 最新段、DEVELOPMENT／COVERAGE_PLAN／INGRESS_PLAN／LOCAL_MCP_EXPERIMENT。最新直接人類授權覆蓋歷史「未執行／不可重試」描述：本輪最多兩次、每次一件合成事件、一個 native CLI 任務、180 秒；失敗可分析修正後新目錄 prepare。未授權 push 或系統／帳戶變更。

### 本次真通訊：失敗

根目錄 `reports/service-acceptance-eventguard-single-test-20261025-01`。事前核對 manifest 無 service_execution、未入列、capture-start 0，原生 CLI SHA256 仍為 `1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`。未重跑 login／version，沿用既有 metadata，不讀認證或原始 sessions。授權原文範圍、記錄時間與前次已撤回紀錄保存在 `human-approval.json`，於執行前寫入；執行後標 consumed。

執行原授權命令：`py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-single-test-20261025-01 --codex-executable C:\Users\yulin\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.exe --execute`。由本機 reports 中的單次 `run-authorized.py` 以私有 Job 啟動同一 Python launcher；不修改全域或專案 MCP 設定。

驗收程式 UTC 06:55:19.248895–06:57:01.864288（台北 14:55:19–14:57:01），102.615 秒，180 秒內。唯一事件 `evt-c29ff48b381d42799d0dc4e3be5c4a15`，host run `f63a975acba84efcba9adaa15d179e81`，attempt `c98110977757441c9c0a8962d5a9236a`。CLI JSONL thread `01a171d7-be28-7200-8795-6f2e34338ca5`；只屬本次新產生輸出。

CLI 自然 exit 1。JSONL 與 stderr 顯示 WebSocket 存取通訊端遭拒，WSA 10013；改用 HTTPS transport 後仍連線失敗。未見舊 `invalid transport`。只有 thread.started／turn.started，沒有 MCP tool call 或完成回合。不把 turn.started 當已完成模型請求；模型請求數未量測。網路拒絕的政策／環境根因 unknown，未查或修改防火牆、網路、帳戶、全域設定，未換權限或加繞過旗標。

SQLite 以 `mode=ro` 核對：生成／入列各 1，source events 1、pending 1，receipts 0，無重複；inbox 無該事件 evidence。receive/query/result/ACK 全 0。`communication-result.json` 的 passed=false，不生成假的通過 validation。

CLI PID 59760，建立時間 06:55:25.796606Z，capture_complete=true、自然 exit 1、remaining 0、forcibly_terminated=false。supervisor PID 6904 自然 exit 0、remaining 0。host PID 34792，建立時間 06:55:19.359944Z，操作者在 CLI 失敗後依本次 scope 合作停止；`service-owner-stop.json` 原 HANDLE 確認自然 exit 0、remaining 0、無強停。最終 service stopped／exited_verified、desired off。未停止其他程序。

外層證據限制另記：包裝器第一次用相對 `py`，CreateProcessW 在驗收前失敗，service_execution 仍空、capture-start 0；將這段失敗保存為 `prelaunch-failed-01*`，改為同 launcher 絕對路徑後才發生上述一次真 CLI 任務。包裝器收尾使用不支援的 finish reason `completed`，因此沒有外層 launcher 原 HANDLE 退出回條，外層 OS exit code unknown。`execution-exit-unconfirmed.json` 如實保存，沒有補造 `execution-exit.json`。後續僅查已記錄 launcher PID 37704／驗收 interpreter PID 51676，均為 missing；這只支持當時已不存活，不替代自然退出回條。各層 CLI／worker／host 原回條不受此缺口影響。

主要證據：根目錄下 `human-approval.json`、`execution-intent.json`、`execution-source-manifest.json`、`execution-start.json`、`execution-exit-unconfirmed.json`、`communication-result.json`、`communication-final-status.json`、`manifest.json`、`service-owner-stop.json`；`data/agent-service/runs/f63a975acba84efcba9adaa15d179e81/attempts/c98110977757441c9c0a8962d5a9236a/` 下 `codex.jsonl`、`codex.stderr.txt`、`capture-start.json`、`capture-exit.json`、`supervisor-start.json`、`supervisor-exit.json`、`summary.json`。執行資料只留本機 reports，不加入 Git。

### 無模型修正與驗證

實測發現：CLI 已失敗退出，dispatcher waiting_task_limit／tasks_started=1／tasks_passed=0／child_exited=true，`_wait_service` 卻仍等工作期限。修改 `src/eventguard/delivery_validation.py`：這種已終止的唯一失敗任務立即 raise 固定類別 `service_acceptance_task_failed_pending_preserved`，沿既有 finally 合作停止 host；不增加重試或任務數。修改 `tests/test_delivery_validation.py`，新增立即失敗、尚未確認退出繼續等待、成功 predicate 正常返回三項 fixture。本次真通訊使用修正前原始碼；修正後只有以下無模型測試。

命令：`py -3.13 -B scripts/verify.py --run-dir reports/verify-service-failfast-20261025-01 --timeout-seconds 300 --module test_delivery_validation --module test_launch_receipts`。Python 3.13.3；UTC 06:59:00.036731–06:59:19.330415（台北 14:59:00–14:59:19）。33 run/pass，0 failure/error/skip，passed_checks=true、source_unchanged=true，guardian 自然 exit 0、remaining 0、無強停、model_calls 0、machine_scan_executed=false。`git diff --check` 通過。證據為該目錄 `source-manifest.json`、`unit-tests.txt`、`worker-summary.json`、`lifecycle-evidence.json`、`guardian-start.json`、`guardian-exit.json`、`verification-summary.json`。提交後以 `source-commit.json` 綁定實際 commit 與受測來源；未重跑完整回歸，1467/1469 是既有版本結果，不能當本修正完整回歸。

本輪真 CLI 任務共 1，第二次未執行：尚無已建立、在授權內能解除網路拒絕的修正，不在相同條件盲目重跑。既有目錄永久單次使用；若有後續有效授權及具體改善條件，剩餘一次也必須全新 prepare／記錄授權。未 push，未建立常駐監看、服務或排程，未實機掃描。專用 CLI 真收件仍失敗；既有桌面聊天／dot 閒置喚醒亦未驗證。

## 2026-10-25：合併worktree分支（最新）

本合併提交把feat/local-codex-acceptance（8176095）與claude/eventguard-quota-test-migration（6456759）合在一起，含c8d42e1、3155297。
主checkout fast-forward到本提交後，下方「主checkout仍在3fe8148」「未整合」「最新程式在worktree」等描述即屬過時。
衝突只在HANDOFF、STATUS、EVIDENCE頂部：兩邊段落全保留，較新段落在上，重複的舊標題行只留一份。程式與測試無衝突。
真通訊仍未執行。eventguard-single-test-20261025-01仍須人類重新確認才可--execute。未push。

## 2026-10-25：接回其他AI成果並更新剩餘目標

本輪只讀核對兩checkout的git status/branch/HEAD/worktree list/log與merge-base。主3fe8148、worktree3155297；主是後者祖先，僅相差c8d42e1、3155297。未整合、未fetch或push。
讀回verify-full-20261025-04/verification-summary：1469項/1467通過/2略過/0失敗、model_calls0、source_unchanged=true、guardian自然exit0/remaining0。與worktree同檔逐位元組相同；未重跑測試。
讀回新service驗收manifest與source SQLite(mode=ro)：evt-c29ff48b381d42799d0dc4e3be5c4a15，service_execution=null、enqueued/stages空、capture-start0、source事件0。
human-approval.json明示execution_started=false及下一次重新確認。未執行CLI、模型、server或採集。
更新兩處docs/MAINTENANCE_GOAL及HANDOFF/STATUS入口，保留04:50與舊交接內容。原App goal查回paused；工具沒有修改既有objective的介面，未另建goal或假結案。
本輪不新增reports。文件修改留未提交，遵守不做文件單獨commit。主未追蹤附件/研究與worktree既有交接修改全部保留。

## 2026-10-25：交接暫停，真通訊未啟動

時間：台北04:40–04:50；UTC 2026-10-24 20:40–20:50。
收到授權「授權 eventguard-single-test-20261025-01，依 AUTHORIZATION_REQUEST.md 範圍執行一次。」後，執行前核對通過：主checkout HEAD 3fe8148、乾淨；manifest無service_execution；候選CLI SHA256仍符合；主data無agent-service。
寫入reports/service-acceptance-eventguard-single-test-20261025-01/human-approval.json後，使用者在啟動前要求交接。未執行validate_delivery --execute，未入列、未啟動host、CLI或模型。
human-approval.json已更新execution_started=false、consumed_by_this_execution=false，next_use要求人類重新確認。
Git：worktree分支claude/eventguard-quota-test-migration HEAD 3155297，比origin多44；主checkout feat/local-codex-acceptance 3fe8148，比origin多42。皆未push。
本段及HANDOFF／STATUS交接段在worktree未提交。

## 2026-10-25：完整回歸、Event範圍綁定與真通訊準備

時間：台北03:40–04:10；UTC 2026-10-24 19:40–20:10。Python3.13.3。無模型任務。
唯讀核對：主checkout HEAD 3fe8148；只剩兩個未追蹤目錄；舊驗收passed=false、continuation terminal_failed_no_retry、事件pending、receipts0；monitor control enabled=false。
完整回歸：`py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261025-01 --timeout-seconds 1800`（主checkout）。19:41:47Z–19:48:59Z。1460測試，1458過，0 failures／errors，2略過（symlink creation unavailable）。passed_checks=true、source_unchanged=true；guardian自然exit0、remaining0、無強停、model_calls0。
Event範圍綁定：改src/eventguard/events/catalog.py、application.py、web.py、cli.py；新增tests/test_event_source_binding.py。
修改先以腳本寫入主checkout，後因工作區規則移到worktree；diff位元組一致後，主checkout那四檔還原為3fe8148。
驗證：reports/verify-event-source-20261025-01（新模組8/8）；-02（22模組284測試，283過；test_local_product一項因CLI多傳event_source=None而失敗，更新斷言）；-03（test_local_product 17/17）。皆guardian自然exit、remaining0、model_calls0。
真SDK／瀏覽器：reports/event-source-binding-001。私有Job啟動idle test App，綁定合成source。MCP SDK 1.6.0經App自身loopback listener呼叫10工具：list_events只含綁定事件，inspect預設範圍事件回application_read_unavailable，start_monitor回monitor_outside_bound_event_source。
內建瀏覽器get_page_text：綁定source提示、符合條件1件、最近動作受阻原因。stop.request後App回stopped、執行緒退出；程序exit0、remaining0、無強停（probe-exit.json）。
真通訊準備：主checkout以`scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-single-test-20261025-01`只prepare（19:59:02Z）。一件high合成事件evt-c29ff48b381d42799d0dc4e3be5c4a15；manifest無service_execution。
候選CLI：SHA256符合1103e9e0…a098。`--version`與`login status`在私有Job執行，exit0、remaining0、無強停；版本codex-cli 0.164.0-alpha.11.1；login只存「已登入」布林值，原始輸出未保存。結果在native-cli-metadata.json。
授權請求：同目錄AUTHORIZATION_REQUEST.md。未執行--execute，未建立service或模型任務。
最終整套（worktree，本批原始碼）：verify-full-20261025-02於20:00:54Z–20:10:32Z，1468測試1465過、1 failure、2略過。失敗為test_operator_monitor_owner.test_sdk_start_status_stop_uses_application_job_without_agent，stop回busy／background_owner_changed。
同模組單獨重跑verify-owner-rerun-20261025-01、-02皆24/24。verify-full-20261025-03於20:11:53Z–20:23:05Z，1468測試1466過、0失敗、2略過，passed_checks=true、source_unchanged=true；guardian自然exit0、remaining0、無強停、model_calls0。
根因：失敗回覆含raw_error_omitted且無run_id，來自background.status的例外分支（讀檔暫時失敗）。stop的等待迴圈把它當成owner更換而立即回busy。
修正src/eventguard/background.py：迴圈內遇到無run_id的暫時讀取失敗就繼續等待；寬限期後的檢查不變。新增test_background.test_scoped_stop_waits_through_transient_unreadable_status。
verify-owner-fix-20261025-01：test_background、test_operator_monitor_owner、test_background_integration、test_background_jobs、test_background_persistence_recovery共101/101。
verify-full-20261025-04於20:27:21Z–20:36:27Z：1469測試，1467過、0失敗、2略過；passed_checks=true、source_unchanged=true；guardian自然exit0、remaining0、無強停、model_calls0。
限制：真SDK與瀏覽器只證明合成source的顯示與工具範圍，不是實機採集或agent收件。login status不證明MCP工具或模型可用。

## 2026-10-25：無額度契約的測試遷移

時間：台北02:00–02:28；UTC 2026-10-24 18:00–18:28。Python3.13.3，C:\Python313\python.exe。
位置：worktree分支claude/eventguard-quota-test-migration，基底f5810b5。帶入主checkout三份交接文件未提交diff，cmp位元組一致。主checkout未寫入。
唯讀核對：git -C主checkout status／diff／rev-parse；Python讀原驗收目錄JSON；SQLite以mode=ro讀source。evt-06865bfcc4874a0788c7b4114b28e3b5仍pending、attempts0；receipts0；capture-start仍1份；data/background/control.json enabled=false。主checkout data與reports在交接後無新檔。
基線：`py -3.13 -B scripts/verify.py --run-dir reports/verify-budget-baseline-20261025-01 --timeout-seconds 1500`加12個`--module`（acceptance_control、agent_dispatch、agent_service、budget_integration、delivery_consolidation、dispatch_inspection、dispatch_lifecycle、launch_receipts、operator_workflow、process_governance、agent_budget、budget_cli）。
18:02:54Z–18:03:59Z。211測試，148過，3 failures，59 errors，1略過。56 errors為AttributeError open_authority；其餘為日額度斷言及MagicMock spawn。guardian自然exit1、remaining0、無強停。交接的靜態發現已實際跑出。
修改：只改tests下13檔。fixture改為暫存launch gate＋歷史預算sentinel與拒讀；capture worker以同一fixture包裝。
舊的reserve／日界／五次共享／預算重查／admission latch測試，改成launch intent不重用、最後pre-spawn暫停、spawn不明不重試、有限max_tasks等待、6事件無日上限、跨入口6次無上限、失敗事件latch只隨pending改變。
另改test_gui、test_operator_status、test_intelligence_integration、test_delivery_validation的舊額度斷言或理由碼。
驗證01：18:16:22Z–18:18:47Z。12模組208測試206過、1 error。執行中又改測試，source_unchanged=false，作廢。
驗證02：18:19:24Z–18:23:17Z。16模組291測試288過、2 failures。新測試未先建立專用inbox，回dedicated_empty_inbox_state_required。修正後以直接Python重現該單一測試：spawn被拒，未啟動子程序；只作除錯，不作證據。
驗證03：18:24:24Z–18:27:30Z。命令同基線，另加test_gui、test_intelligence_integration、test_operator_status、test_delivery_validation，run-dir為reports/verify-budget-migration-20261025-03。
291測試，290過，0 failures／errors，1略過（symlink creation unavailable）。passed_checks=true、source_unchanged=true。guardian自然exit0、remaining0、無強停。model_calls0、real_agent_woken=false、machine_scan_executed=false。
證據檔：worktree reports/verify-budget-migration-20261025-03下source-manifest、unit-tests、worker-summary、lifecycle-evidence、guardian-start／exit、verification-summary。reports不在Git。
副作用：基線以舊fixture執行時，capture走真實gate，在worktree建立data/agent-runtime/launch.lock（1 byte，gitignored）。新fixture改用暫存gate。未刪除。
限制：只跑受影響16模組，不是全套回歸。fake CLI與真Windows Job，不是真模型、真收件或喚醒。test_application_no_quota與test_communication_no_quota未變更，未重跑。

## 2026-10-25：只交接EventGuard，停止開發

時間：台北00:50；clock回2026-10-24 16:50:52 UTC。Checkpoint HEAD f5810b52064fbde8f5d59928ff139277867f2165，分支feat/local-codex-acceptance。
命令：git status --short、git branch --show-current、git rev-parse HEAD、git diff --stat、git ls-files --others --exclude-standard。核對前無tracked/staged變更，保留2張附件與11份未追蹤研究稿。
只讀Python查核：background.status(root)回stopped/exited_verified/desired_enabled=false；agent_service.status(root)回not_started/not_recorded；agent_service.status(原run)回stopped/exited_verified/pending1/tasks_started1。
真App MCP status回blocked/application_not_running/live；RemoteApplication對同run/test回application_not_running。主專案test descriptor scope_invalid，未接管或修復它。
SQLite以mode=ro查原source：event evt-06865bfcc4874a0788c7b4114b28e3b5仍pending，receipts=[]。capture-start檔案數1；continuation仍terminal_failed_no_retry。
讀回既有no-quota-unit-001與transport-config-unit-001的verification-summary，只核對12/12與1/1原證據，不重跑、不當最終完整回歸。
Python3.13.3、C:\Python313\python.exe；importlib.metadata查MCP SDK1.6.0。未啟動native CLI或模型。
歷史bin/8925276705115dea/codex.exe已不存在。同一安裝找到bin/2993767bd1dfb009/codex.exe，SHA256 1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098。只查檔案metadata/hash；新CLI版本、登入與新帳號能力未知。
collaboration.list_agents只列/root running，沒有開發子agent工作。本goal依使用者要求update_goal回paused，未complete。
已重新讀AGENTS/README/STATUS/HANDOFF、最新EVIDENCE、DEVELOPMENT及App/agent通路文件；已知歷史預算與未執行描述以新checkpoint明確取代，歷史保留。
本輪只更新既有HANDOFF/STATUS/EVIDENCE，保存完整Prompt、進度、限制、阻擋與下一步。未新增reports/交接資料夾，未提交文件單獨commit，未push。
沒有新採集、測試、CLI、server或模型啟動。未修改或停止其他專案或既有工作；無新程序需清理。

## 2026-10-24：失敗通訊的無模型收尾

基底 d0adb12。未啟動第二個exec或agent service。原失敗及grant consumed不變。
原驗收目錄的native-help、exec-help、mcp-list-help、debug-help均exit0，保留stdout/stderr與Job回條。
help確認 --ignore-user-config 僅列在exec。前次metadata命令使用不支援的參數位置；舊stderr未保存，不補造原文。
新命令：codex -C <同run root> <同一組生成-c設定> mcp get eventguard_inbox --json。
transport-native-get-001/result.json：native config解析exit0、stderr0 bytes、enabled=true、stdio。
此入口可能載入正常使用者設定，不等同exec的ignore-user-config分層。未改設定、未起server或模型。
原metadata exit2及wrapper錯誤保留。新查核有intent argv、stdout/stderr及自然exit0/remaining0回條。

同root的Application使用test namespace、auto_start=false、notifications=false、mcp_enabled=true。
真SDK initialize/list_tools/status完成，10工具。GUI與MCP status對上instance 44de3ddc0db44d7aba7ddbef3f5bf9a0。
兩者皆顯示原event evt-06865bfcc4874a0788c7b4114b28e3b5、attempt ab0992a7064948ef86bad8434222539e、CLI exit1、pending1、ACK=false。
Web摘要新增上次CLI失敗、退出碼及event/attempt。真瀏覽器已執行該JS並保存畫面，不把停止當通訊成功。
只驗Agent頁與MCP status。Event頁預設catalog仍是data/test；不聲稱list_events/inspect_event已接自訂source。
GUI關閉後App自然exit0，Web/MCP/probe threads退出、remaining0、無強停。
source/inbox檔案前後SHA256相同。採集starts0、capture-start仍1、新模型任務0。
證據：同root/same-run-app-001的sdk-status.json、browser-view.json、failed-attempt.jpg、app-exit.json、validation.json，以及root/observe-app-process-exit.json。
本次validation.passed只表示失敗證據顯示與退出通過。原communication-result.passed仍false，真收件仍未通過。
未重跑12項no-quota或既有契約測試。Web本次以真GUI/MCP及資料不變查核驗證。



## 2026-10-24：取消 App 日預算；單次真 CLI 通訊失敗

本節取代下方早期「等待日界」的現況。基底 7663b57，未提交修改另隨程式提交。
指令：`py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-eventguard-single-test-20261024-01 --codex-executable <既有原生 codex.exe> --execute`。
時間 2026-10-24T10:25:16Z 至 10:25:33Z。Python 3.13.3；Codex CLI 0.164.0-alpha.11.1。
唯一 event `evt-06865bfcc4874a0788c7b4114b28e3b5`。
唯一 attempt `ab0992a7064948ef86bad8434222539e`，CLI PID 48976，建立時間 10:25:22.189816Z。
生成／入列各1；receive/query/result/ACK各0。SQLite pending1，receipts0。無重複。
真正原生CLI任務啟動1；觀察到的provider turn0。未量測模型請求數，不以task數當請求數。
CLI JSONL 0 bytes。stderr為 `Error loading config.toml: invalid transport`，位置 `mcp_servers.eventguard_test`。
CLI自然exit1，驗收exit2，17.554秒。各層子程序退出，remaining0、forcibly_terminated=false。
單次grant已消耗。不重試模型。不是通訊、收件或喚醒成功。

證據目錄同上述root。主要檔：communication-result.json、execution-exit.json、communication-final-status.json、service-owner-stop.json，以及run/attempt下的capture-start.json、capture-exit.json、codex.jsonl、codex.stderr.txt。
原生App MCP status實際為blocked/application_not_running，live namespace。不是同次test App，也無同次GUI驗證。
歷史authority與installation marker前後hash一致。沒有重設、刪除或換目錄。

無模型工程驗證分開記錄：no-quota-unit-001 於10:20:05Z完成12/12，model_calls0；不重跑。
失敗後只修正disabled MCP entry為完整但停用的stdio定義。transport-config-unit-001於10:28:14Z完成1/1，model_calls0；只證明TOML/命令契約。
額外native metadata查核exit2；第一次metadata wrapper使用無效finish reason而失去回條，失敗紀錄保留。第二次有自然exit2/remaining0回條。兩者均非exec、非模型，不當作native修正成功證據。
未重跑全套。舊預算耦合測試尚未全面遷移；先前整套數字不能當本批回歸結果。



## 2026-10-24：單次模型驗收授權與保守首次初始化（等待日界）

基底 `7663b57`。本次真正模型任務 **0**，不是測試通過。
直接人類授權轉達與本session接收紀錄見唯一目錄 `reports/service-acceptance-eventguard-single-test-20261024-01`。
Grant為 `eventguard-single-test-20261024-01`。Scope：一件七欄合成事件、最多一個native CLI模型任務、180秒、GPU0、無自動重試。
固定authority DB/marker/journal/WAL/SHM/locks全不存在，agent host not_started/not_recorded；未動其他程序。
以正式prepare入口建立一件manifest事件，source仍空；prepare exit0，Job remaining0、無強停。
以正式CLI `budget initialize`首次初始化，沒有known-used參數，不假設今日0用量。
2026-10-24T10:02:58Z：固定SQLite policy bootstrap_day=2026-10-24、bootstrap_unknown=1，今日guard used=5、remaining=0。
`budget_bootstrap_usage_unknown`是預期保守阻擋；實際admissions/global_active/event_usage皆0，不是五次真任務。
依實際帳本最早為2026-10-25 00:00:00+08:00，再核對quota，不改時間或重設帳本。
`bootstrap-result.json`保留實際SQLite摘要、marker雜湊與初始化程序exit0/remaining0回條。
原生CLI `--version`、`login status`皆exit0；版本 `codex-cli 0.164.0-alpha.11.1`，既有登入可用。
這兩個是metadata命令，不是專用模型任務；原始登入輸出、認證與Codex home內容不保存。
原生App MCP status目前application_not_running，只記operator context，沒有啟動GUI或模型，不冒充同App模型驗收。
授權未消耗，service_execution/attempt/run/delivery/query/ACK尚未建立。
`CONTINUE.md`與`continuation.json`固定同事件、同authority、同一--execute接續點；失敗或未知不得另開目錄重試。
沒有修改程式、重跑既有套件、啟動正式監看、排程、GPU或動DeltaVault。既有統合者追蹤接續，不建立新輪詢。
本段暫留接續資訊，不作文件單獨commit。原始執行資料均留本機，不提交。


這是測試數、命令與時間紀錄的唯一閱讀入口；現況請看 [STATUS](../STATUS.md)，下一步看 [維護目標](MAINTENANCE_GOAL.md)。原始回傳、SQLite、CLI JSONL、runtime 與私有資料只留本機忽略的 reports，不提交。

## 2026-10-24：中文 App CLI 與一般使用者通知

基底 `c610b616037e33ac55f99ed471623ffc99fbad22`。未改控制器、採集或儲存協定。
補齊 `app` 文字模式：直接顯示採集狀態、實例、版本、來源、原因、可用操作及頁面。
原本落入通用ASCII JSON，對人不易閱讀。JSON模式與API不變。
未知不顯示已停止；重播不暗示再次操作；shutdown回條不暗示實際退出。控制字元與未知enum不成指令或例外。

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/application-lifecycle-001/text-001 --timeout-seconds 120 --module test_application_cli_text --module test_cli_workflow --module test_core_cli
```

Python3.13.3。`2026-10-24T05:07:01.404381Z`：33 run/pass，0 skip/failure/error。
guardian10.342秒、exit0、無強停、remaining0、來源不變；逐測試無殘留。
這是CLI顯示增量，不重跑已驗的整套產品測試。
實際原生CLI `--format text app status` 另存 `text-001/app-status-text.txt`，UTF-8中文正確。
該次應用已不在運行，CLI正確exit2並顯示application_not_running；探測wrapper誤設assert0而失敗。
保留真exit回條，不重開應用來改寫這個結果，也不把CLI exit2寫成通過。

`2026-10-24T05:02:08Z` 另在一般使用者環境做一次真Windows通知。
僅程式生成一件synthetic high事件，真NotificationService→Shell_NotifyIconW。
系統接受要求；四秒後關閉自身視窗。NotificationService重新建立後回already_notified，沒有再送。
事件仍pending，source receipt_count=0，model_calls=0。
native child exit0、私有Job無殘留/強停。證據 `reports/notification-intent-001/native-ordinary-001/result.json` 與 `exit.json`。
不能聲稱人已看見。先前sandbox通知skip仍保留，不改為通過。

同一已批准專用入口隨後自動載入十工具，沒有要求重開Codex。
`native-control.py` 啟動本專案100秒上限的閒置App；通知關閉，採集/模型/正式事件讀取均為零。
2026-10-24T05:14–05:15Z：本聊天原生MCP status、實際原生CLI中文status及Web GET/status為同instance、revision0、stopped。
實際原生shutdown_application回shutdown_requested。稍後手持HANDLE驗exit0、remaining0、無強停；Web/SDK均退出。
關閉後原生status正確blocked/application_not_running，沒有冷啟新App。observer本身仍由Codex管理。
證據 `reports/application-lifecycle-001/native-control-001`：ready、native-status、cli-status、web-status、native-shutdown、exit及native-after-shutdown。
這是活躍聊天的工具操作面驗收，不是收到事件或閒置喚醒證據。

七項必做條件與原Goal逐項對照在 `reports/application-lifecycle-001/product-requirements.json`。
既有rules/source/history模組未重跑；核對相關程式/測試位元組與原受測manifest一致，原逐測試紀錄均ok。
原歷史整輪曾有不同case-freshness清理錯誤，未冒稱該整輪通過；已修正模組及本批整合驗證另有證據。
目前無已知未實作的無模型必要功能。真模型收件/喚醒、當前聊天十工具熱載入及長期實機均維持未驗證。

## 2026-10-24：獨立 App、共用 CLI 與公告公開投影

基底 `9903ad5574e80666eb379652e7f4154d111c14b3`。分支 `feat/local-codex-acceptance`。未推送。
本批程式、測試及文件一起提交。測試來源與實際 commit 的位元組綁定留本機 `source-commit.json`。
核心標準庫。選配 transport 使用既有 MCP SDK。沒有產品模型或正式來源掃描。

### 整合定向測試

Python 3.13.3。新功能完成並 freeze 後執行：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/application-lifecycle-001/verify-001 --timeout-seconds 600 --module test_local_notifications --module test_notification_recovery --module test_agent_dispatch --module test_application_host --module test_application_lifecycle --module test_application_stdio --module test_application_stdio_transport --module test_application_mcp --module test_application_rpc --module test_application_controls --module test_application_ui_state --module test_monitor_web_controls --module test_local_product --module test_event_ingress --module test_queue_inbox --module test_storage_retention --module test_agent_budget --module test_intelligence_sources --module test_intelligence_store --module test_intelligence_integration --module test_intelligence_case_freshness --module test_intelligence_applicability --module test_nvidia_advisories --module test_adversarial_intelligence --module test_advisory_views --module test_application_advisories --module test_core_cli --module test_cli_workflow
```

實際輸出：`Ran 487 tests ... OK (skipped=1)`。486 pass，0 failures，0 errors。
唯一 skip：`notification_icon_unavailable`。不能宣稱看見 Windows 通知。
摘要時間 `2026-10-24T04:46:42.774689Z`。guardian 161.192 秒。
來源不變、原生 exit 0、無強停、remaining 0；逐測試無殘留。不是全儲存庫全套重跑。

覆蓋：

- CLI start/pause/resume/stop/start/shutdown 真 Application，三個實際 Windows 私有 Job 自然退出。
- 真 stdio/SSE initialize、tools/list、tools/call。十工具同實例；不是模型收件或喚醒。
- 冷 stdio 只列工具、不建 App/runtime。無 App 時 blocked；之後 metadata 綁定。
- MCP client EOF 不停止 App 或採集。重連相同實例；App 替換後 metadata 重綁，舊 operation ID 被拒絕。
- 同步狀態、操作來源、busy/replay、舊回覆拒絕、處置保存及 pending 保留。
- 通知 prepared 在 sink 前 commit。未知回條不重送；儲存失敗、容量、legacy migration可判定。
- 一個合成故障子程序自行 exit 23；這是預期故障，不是應用成功退出。無強停、Job無殘留、pending保留。
- NVIDIA CSAF partial/last-good/304/去重、公開投影與十類對抗文字全鏈。
- outbox/inbox/dispatcher 容量與保留、跨重啟預算及未知退出政策。

### 原收件通路補充查核

為避免只證明新應用操作面，另外實跑原 operator、SDK stdio 及 ACK 中斷保留：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/application-lifecycle-001/receiver-001 --timeout-seconds 180 --module test_operator_clients --module test_local_stdio --module test_inbox_retention_recovery
```

實際輸出：`Ran 16 tests ... OK`。16 pass，0 skip/failure/error。
摘要時間 `2026-10-24T04:50:45.421329Z`。guardian 31.086 秒。
來源不變、原生 exit 0、無強停、remaining 0；逐測試無殘留。
雙真 stdio client 對同事件補收同 event/query ID；重播 ACK 後來源 receipt_count 仍為1。
真正 SDK wait/query/ACK、取消/EOF、結果保存與ACK中斷恢復分開核對。
這是合成來源、真正協定及本機程序，不是真模型喚醒。以上兩批測試不與歷史數字加總。

### 真瀏覽器與 SDK：公告頁

`py -3.13 -B reports/nvidia-advisory-001/demo.py`，最後有效資料在 `demo-003/`。
普通程式用兩份自寫 CSAF fixture 產生兩筆公告事件，第二輪不重發。外部來源 GET=0，產品模型=0。
真已安裝 SDK initialize/list/status/list_events/inspect_event/set_event_status，共用 instance。
瀏覽器實際開「資安公告」，可見 URL、發布/更新/擷取/最後成功與 unknown適用性。
惡意 script/img 文字原樣顯示，但 DOM中對應script/img/iframe數為0，無外部連結；不改控制顏色或執行操作。
SDK把一件標已讀，GUI可見MCP來源；GUI改已處理，刷新後仍保存並顯示GUI來源。
GUI點關閉程式後，本機 final.passed=true，原生process exit0，Web/SDK/截止thread均退出。
兩件仍pending，ACK=0。已處理不等於ACK。沒有啟動採集worker。

本機保留 `demo-manifest.json`、`sdk-protocol.json`、`final.json`、DOM及：
`advisories-visible.jpg`、`handled-after-reload.jpg`。
先前兩次示範失敗證據保留：第一次及 `demo-002/`。
原因是示範禁止子程序時拋 RuntimeError，uvicorn 的 platform.system 在此環境觸發 Python 的 Windows版本fallback。
第二次只記檔名/函式/行號，確定是該fallback；未保存原始例外或命令列。
最後改以 PermissionError 表示禁止啟動，標準庫可正常fallback；沒有放行子程序、安裝或改安全政策。
失敗示範同樣已合作退出，事件仍pending。不把失敗寫成通過。

### 官方樣本與研究界線

NVIDIA固定commit `2c9454053cf5d2942d4f361d455c749b725fe920` 的5903 JSON僅RAM解析。
`2026-10-24T04:26:56Z`：Python3.13 -B，exit0，10391 bytes，1 record，CVE-2026-65142。
同來源SHA256一致：`72aa9d435f542a5abf248dccffd97317b1ceccb40489c9bee46f07b9ed540664`。
這是同發布者位元組一致，不是獨立真偽驗證。本機適用性unknown，正式來源仍disabled。
只保留 metadata/重現碼摘要在 `reports/nvidia-advisory-001/official-sample-summary.json`，不保存全文。
fixture與對抗文字均自寫，不引入上游runtime。

本次使用 OpenAI Docs 技能查官方入口，使用 Computer Use 做真瀏覽器驗收。
公開queue可用命令不等於此桌面閒置喚醒已驗。官方依據與一次有界模型驗收範圍見 [AGENT_EVENT_DRIVEN](AGENT_EVENT_DRIVEN.md)。
OpenOctopus可拆工協定見 [OPENOCTOPUS_EVENT_PROTOCOL](OPENOCTOPUS_EVENT_PROTOCOL.md)；外專案尚未實作。
一般使用者公開Codex CLI只更新既有eventguard-app為Python -u stdio；同一程式與live範圍，未更動其他MCP。
2026-10-24T04:58:34Z：CLI exit0、private Job自然退出、remaining0。回條為native-entry-refresh.json。
較早原生catalog仍為舊九工具，status回application_instance_changed。回傳保留在native-client-after-entry-refresh.json。
該時刻只證明設定更新；稍後才自動載入十工具，最後catalog/狀態保留在native-client-final.json。
本批沒有啟用正式監看、讀正式事件、初始化預算、模型、排程或自啟。
24小時、重開機、七來源目前主機實測及真模型喚醒均未執行。

## 2026-10-24：實際瀏覽器操作、成功歷史與公告時效

基底 `54d231c896a5c865e4838025ae5b2d86d872d90e`。同一 feature 分支。沒有推送。
本批使用 Computer Use 技能及實際瀏覽器 Playwright 操作，不以直接 HTTP 呼叫替代點擊。
`reports/browser-controls-001/launch.py run-001`／`run-002` 啟動既有真 CLI main(root=隔離目錄)。
CLI 仍走原 Application、背景 owner、collector fixture、規則及 EventStore。沒有 fake API 或模型。
每次前景有 600 秒上限，外層持有實際私有 Job／子程序 HANDLE。使用 OS 選取可用埠，明確拒絕 8765。
正式資料、其他服務、MCP、排程與模型預算未變。沒有為此下載依賴或改安全設定。

實際操作保存在 `browser-actions.json` 與七張 JPEG：

- 真頁面開始後產生合成事件。點暫停，再查看七來源的拒讀／未知、原因與建議。
- 實際選來源、嚴重度及人類狀態，按篩選、查看，將同一事件標為已讀及已處理。
- 刷新後仍可找回；點恢復、查看五條規則，再點停止。
- 第一輪暴露停止要求已回覆但頁首仍顯示監看中；修正後第二輪實際點擊確認頁首為已提出停止要求。
- 頁面明示合成資料。精確可存取名稱能操作下拉選單。
- 同一目錄整個應用重啟後，實際頁面仍見相同 ID、handled 與 pending。
- 第二輪七來源頁明示最後成功及最後採集。成功後的合成拒讀與未知保留成功歷史。

開始由正式 run 入口完成；沒有冒稱瀏覽器點擊不存在的開始按鈕。
`ui-validation.json` 的八項核對全 true。兩個 CLI 應用及三個 monitor 實際 OS exit 均 0，未強停，remaining=0。
SQLite ACK 數為 0；指定事件仍 pending。唯讀 CLI／catalog 查閱前後，資料檔 SHA 未變。
`sources-cli.txt` 實際顯示保存的最後成功、拒讀原因及過期狀態，不因查閱刷新時間。
這是合成來源與真 Windows 程序／瀏覽器；沒有實機來源掃描、真模型收件或長期運轉證明。

本批另補兩項契約：

- 每來源只有一個耐久 last_success_at。與 observation 同一 JSON 原子保存；失敗、partial、不適用或保存失敗不提升它。
- 公告 current assessment 在讀取時驗來源綁定與有效期。歷史 assessment、事件與 ACK 不改。
  盤點有效期沿既有設定；人工 facts 需原始 observed_at。讀檔／304 不刷新期限，舊資料缺期限保守 unknown。

統一相關測試命令：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/browser-controls-001/verify-001 --timeout-seconds 240 --module test_source_success_history --module test_intelligence_case_freshness --module test_product_sources --module test_monitor_progress --module test_monitor_admission_barrier --module test_local_product --module test_monitor_web_controls --module test_application_controls --module test_cli_workflow --module test_configured_rules --module test_intelligence_applicability --module test_intelligence_store --module test_intelligence_integration --module test_core_cli
```

結果：251 run、249 pass、1 error、1 skip，exit 1。67.558 秒，09:57:37 UTC+08 結束。
唯一 error 是新測試兩個 sqlite3.connect context 沒有 close，Windows teardown 回 WinError 32。
改用 closing；未修改產品程式或放寬斷言。原失敗保留。

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/browser-controls-001/verify-002 --timeout-seconds 60 --module test_intelligence_case_freshness
```

修後 17 run、17 pass、0 skip/error/failure，exit 0。2.717 秒，09:59:09 UTC+08 結束。
其餘通過且未改的模組採首輪結果，不累加成新測試數，不冒稱最終來源全套重跑。
Python **3.13.3**。174 Python AST 無錯。兩輪 source_unchanged=true、per_test_residuals=[]。
兩輪 guardian 都實際退出、remaining=0、未強停；首輪 OS 1、修後 OS 0。
唯一 skip 仍為 notification_icon_unavailable，不能算 Windows 通知可見。
正式停止 control SHA256 仍為 `78F20282862F179B8DEB4AF769BD0692932EC273AE930C13375E987781CB41BA`。
固定模型 authority／marker 均不存在。原 Goal 仍 blocked；工具沒有恢復介面，未假結案重建。
提交後以本批 `source-commit.json` 綁定最後受測來源。截圖、SQLite、CLI 輸出與執行資料不提交 Git。

## 2026-10-24：無模型監看控制與事件庫重啟完整性

基底 `bba651fedf5f556af57037c4fa5263c5eebd0e22`。分支維持 `feat/local-codex-acceptance`。
依新指示先交付本機工程，不啟用模型、正式監看、agent host、排程或網路來源。
`get_goal` 實際回 blocked；工具沒有 resume／改寫能力。未呼叫 create_goal，未假結案重建。

產品缺口已補：run 的 Web 有監看本體的暫停／恢復／停止。它與 agent 派送控制分開。
暫停先關閉本應用捕捉的 owner，核對退出與回條。Web、pending 與人類處置狀態保留。
恢復先核對 namespace／run／generation、重讀規則，再在原控制鎖內原子比對 generation。
不接管外部 host。未知退出、保存失敗或世代變更不回成功，不重新啟動採集。
stop 的 HTTP 只回要求；主迴圈負責真正關閉，最終 OS 回條另行核對。

EventStore 的既有空檔、缺表、缺必要欄位不再被 CREATE IF NOT EXISTS 重建成空佇列。
初始化、policy 與已知 legacy migration 使用同一 writer transaction。失敗回滾。
首次並行初始化的空檔窗口有界等待；損毀資料沒有被宣稱已恢復。

第一輪 `reports/local-controls-001/verify-001` 因執行 session 消失而缺最終回條。
工具實際回 `Unknown process id`。原日誌保留，不能判通過或推定自然退出。
超過原 300 秒期限仍缺 worker-summary、guardian-exit、verification-summary。
為此在既有 verify 入口加入固定 guardian-start 回條，保存本工具 worker 的 PID／建立時間／Job。
這是啟動證據，不是退出證據。第二輪另用 verify-002，不覆寫第一輪。

第二輪 `verify-002`：289 run、286 pass、2 failure、1 skip，exit 1。Python 3.13.3。
18 個相關模組；完整命令在該目錄 verification-summary.json。170.088 秒，09:07:06 UTC+08 結束。
source_unchanged=true、172 Python AST 無錯。guardian OS exit 1、remaining=0、未強停、per_test_residuals=[]。
原失敗保留，不改寫為通過：

- 新庫 auto_vacuum 回 0，預期 2。移到新庫無表且 BEGIN 前設定；既有檔不走這段。
- Windows 操作流程第一個 host 實際 exit 1460，第二個 0。末次 HANDLE 回條 force=false，不能抵銷非零退出。
  1460 是本工具 Job 終止碼；另一個 Job handle 的原 force 保留於 owner aggregate，不能只看末次 wrapper。
  五秒寬限不足是目前最符合觀測的原因，尚無原 stop 文件可單獨確認 I/O 根因。
  Application 改用既有 CLI 的十秒合作寬限，測試仍要求 OS 0、未強停及零殘留，未放寬斷言。

唯一 skip 是 Windows 通知 notification_icon_unavailable，不算 pass。
修正後只重驗受影響範圍，結果另記，不累加測試數或聲稱最終來源全套重跑。

最終修後命令：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/local-controls-001/verify-003 --timeout-seconds 180 --module test_application_controls --module test_store_open_integrity --module test_local_product --module test_event_catalog --module test_events_transport --module test_storage_retention --module test_inbox_retention_recovery --module test_background_integration --module test_intelligence_integration
```

`verify-003`：134 run、133 pass、1 skip、0 failure/error，exit 0。九個受影響模組。
Python **3.13.3**。58.950 秒，09:12:08 UTC+08 完成。source_unchanged=true；172 Python AST 無錯。
guardian 自然 OS exit 0、remaining=0、forcibly_terminated=false、per_test_residuals=[]。
同一通知 skip 仍保留。其餘已通過且未受修正影響的模組採 verify-002 結果，不加總為另一套測試數。

`lifecycle-evidence.json` 保存真 Windows application-owned Job＋loopback HTTP 的完整操作回條。
pause 後 Web 仍可讀七來源；指定合成事件改 handled 後，resume／stop／新 catalog 仍見同 ID、handled、pending。
兩個實際子程序 HANDLE 均 OS exit 0、remaining=0、未強停；應用 thread 與 Web thread 均退出。
另有真前景 CLI exit 0、SQLite 滿載恢復、同 query 重收與單次 ACK，以及離線公告結果先存再 ACK。
後端收件與 ACK 都沒有真模型，不升格為真正 agent 已收到。
正式監看 control SHA256 仍為 `78F20282862F179B8DEB4AF769BD0692932EC273AE930C13375E987781CB41BA`。
固定模型 budget DB／marker 均未建立，沒有初始化或重置。沒有正式啟用、來源掃描、外部網路或排程。
提交後以 `reports/local-controls-001/source-commit.json` 核對受測來源與 raw Git blob；執行資料不提交。
尚未驗證瀏覽器實際點擊、24 小時、重開機與真模型通路；HTTP 測試不是視覺驗收。

## 2026-10-24：按事件查看進度與有界應用生命期

基底 `c8b84d40bd4eca6c120e5455c28434ed181fcdd2`。分支維持 `feat/local-codex-acceptance`。
本批補產品查詢及必要的驗收入口，不建立新佇列、provider、服務或排程。無真模型、正式背景、來源掃描或外部網路。

指定事件的 CLI／Web 現在重讀原 ledger／archive、綁定與原始回條。完成帳本輪替後，仍保留最多三個 attempt 參照。
新的 binding 綁 event ID、完整 payload hash、namespace、inbox profile 及來源／inbox scope。exclusive write＋fsync，不覆寫。
查詢只進入明確 root 的受管理 run／attempt，重驗 capture、supervisor、原始 CLI trace 及同事件 inbox。不用 summary.passed 判成功。
CLI 程序啟動是 observed；typed 協定、工具收件、回合與退出分開。scope 明示不提供獨立模型來源證明。舊資料缺綁定維持未知。
helper 壞資料不抹除獨立 inbox 證據。查詢不建檔、不扣額度、不接收或 ACK。模型七欄及 query 未擴張。

本輪唯讀查詢目前 Python 的 IsProcessInJob，實際回 parent_job_present=true、spawned_children=0、model_calls=0。
這證明原 service 驗收走獨立背景入口會被既有 guard 拒絕。現在有限驗收沿正式 spawn_application_host／retain_application_host。
driver 保留原 child HANDLE，parent PID／建立時間與期限在 host 及最後 CLI gate 都重查。沒有 breakaway，也沒有測試 allow_parent_job 注入。
先合作 stop，再保存 retained HANDLE 的獨立退出回條。原 stop 的 unknown 不改寫；只有相符原 HANDLE 實際回 OS 0 才能補強自然退出證據。
缺回條、身分不符、強停或非零仍不通過。產品獨立 start 預設不變。有限模式明示 lifetime_limited，不證明長期獨立背景。

| 命令／證據 | 實際結果 | 範圍 |
| --- | --- | --- |
| `py -3.13 -B scripts/verify.py --run-dir reports/event-ingress-001/operator-delta-001 --timeout-seconds 240 --module ...` | 290 run；289 pass；1 skip；0 failure/error；exit 0；140.233 秒；04:10:11 UTC+08 完成 | 16 個相關模組。完整命令見同目錄 verification-summary.json。不是最終來源全套重跑 |
| 同組 `unit-tests.txt` | 實際 SQLite＋CLI＋loopback HTTP 在輪替後仍查同一舊事件；global 最新任務改變不影響。原始 binding 保存失敗仍保 pending 位元組，reserve／spawn 都零 | provider／Job JSON 為明示 fake。不是模型工具收件證據 |
| 同組 `lifecycle-evidence.json` | 正式 application-owned Windows 空佇列 host 的 start／pause／resume／stop；retained HANDLE OS exit 0、remaining 0、未強停；provider_attempt_count=0 | 真 Windows Job／handle。父預檢 budget 是 mock。沒有初始化正式預算 |
| `py -3.13 -B scripts/eventguard.py agent status --format json` | exit 0；not_started；desired_enabled=false；host_liveness=not_recorded；budget_unavailable | 固定 authority.sqlite3、installation.json 均不存在；未初始化或假設零用量 |

Python **3.13.3**。169 個 Python AST 無錯。source_unchanged=true；guardian 自然 exit 0、remaining=0、forcibly_terminated=false、per_test_residuals=[]。
唯一 skip 為原生通知 notification_icon_unavailable，不升格為 pass。沒有為此重掃主機、提權或更改設定。
提交後 `reports/event-ingress-001/operator-source-commit.json` 以 raw Git blob 核對最後 source-manifest。
正式監看 control SHA256 仍為 `78F20282862F179B8DEB4AF769BD0692932EC273AE930C13375E987781CB41BA`。未解除停止。

真模型的單件、最多一任務、180 秒方案仍待當次批准與有效預算。未再次索取，未自行執行。
尚未驗證真模型通路、正式長期背景、24 小時及桌面 queue。不能宣稱事件已自動交給真正 agent。
功能、測試及文件集中提交；不推送；執行資料、既有私人研究及附件不提交。

## 2026-10-24：pending 阻塞、worker 身分與退出補強

基底 `9640df6581b996126137dd4e7066023c3950cf20`。同一 feature 分支。功能、測試與文件一起提交，不推送。
本批沒有真模型、正式背景、主機採集、網路、排程、proxy、其他專案或聊天操作。既有研究及附件保留未追蹤。

篩選前檢查所有 pending 的格式、schema、hash、處置及 retry／lease 時間。壞資料不再被 SQL 篩成空佇列。
錯誤使用固定清單，不回傳原文。記憶體 LRU 最多 1000 筆，每筆原文最多 8192 bytes；key 含完整原文、PK 及 stored hash。
host 顯示固定阻塞原因，保留來源位元組，不 reserve／spawn。人類修復後，舊 Job 已確認退出時可明確重新 start；不再因舊 state=blocked 永久拒絕。

新 managed worker 在 spawn 前保存 required 與 nonce。parent 隨後保存真 PID、建立時間及三份綁定資料。
worker 最多等待五秒，核對自己的實際身分後才可啟動 CLI。complete 與 status 共用 proof。
CLI skipped 不代表 worker 已退出。startup、當輪收尾及 status 都另核對 supervisor；缺證據保留 started，禁止重入。
legacy 不補造新身分。service 驗收另核對 SQLite created_at／acked_at、工具階段、三層程序及同 scope 的 UTC／monotonic。

| 命令／證據 | 實際結果 | 範圍 |
| --- | --- | --- |
| `py -3.13 -B scripts/verify.py --run-dir reports/event-ingress-001/proof-delta-001 --timeout-seconds 240 --module ...` | 245 run；243 pass；1 fail；1 error；exit 1；115.118 秒；03:33:08 UTC+08 完成 | 14 個相關模組；完整命令見同目錄 verification-summary.json |
| `py -3.13 -B scripts/verify.py --run-dir reports/event-ingress-001/proof-delta-002 --timeout-seconds 180 --module test_agent_dispatch --module test_dispatch_lifecycle --module test_delivery_validation --module test_dispatch_takeover --module test_agent_service --module test_agent_entrypoints` | 119 run；119 pass；0 skip；exit 0；67.413 秒；03:38:53 UTC+08 完成 | 修正後只重驗受影響的六模組 |
| `proof-test-index.json` | 247 unique；247 pass；missing=[]；unexpected=[]；current_source_mismatches=[] | 最新結果按完整 test ID 合併，不累加重跑數；不是最終來源全套重跑 |
| `proof-delta-002/lifecycle-evidence.json` | 真 Windows worker／CLI 的 PID 與建立時間綁定相符；退出碼均 0。空佇列 host start／pause／resume／stop 退出碼 0；teardown=[] | Windows 私有 Job＋fake CLI／backend／隔離預算。不是模型收件證據 |
| `py -3.13 -B scripts/eventguard.py agent status --format json` | exit 0；not_started；desired_enabled=false；host_liveness=not_recorded；budget_unavailable | 固定 authority.sqlite3 與 installation.json 均不存在；沒有初始化或推定當日零用量 |

Python **3.13.3**。兩輪來源在測試期間均未改變。guardian 均自然退出，remaining=0、forcibly_terminated=false、per_test_residuals=[]。
第一輪 guardian exit 1 保留，未改寫為通過。第二輪只改三個受影響 Python 檔，其餘已通過模組不重跑。
提交後以 `reports/event-ingress-001/proof-source-commit.json` 綁定實際 Git blob 與最後 source-manifest。

原 fail 是 status 新增退出查核後，將已停止且未啟動 CLI 的終態覆成 not_started；現在保留既有終態。
原 error 是新反例測試只用了 SQLite transaction context，沒有 close 連線，造成 Windows 清理 WinError 32；改用 closing 並明確 commit。
另補 skipped worker 缺 exit／start、重開兩次仍零 reserve／spawn，以及已知退出 4 仍不算 agent 成功的測試。
Windows smoke 即使 stop 拋錯仍執行 teardown；逾時只按測試持有的 PID、建立時間及私有 Job 清理，保存實際回條。原錯不轉成功。

最初的測試選單含不存在模組，由 argparse 拒絕，未啟 worker。索引初稿未處理測試中 CLI stdout，未產生索引；修正後嚴格核對每輪數量及當前 discovery。
正式監看 control 的 SHA256 仍為 `78F20282862F179B8DEB4AF769BD0692932EC273AE930C13375E987781CB41BA`。未解除停止。

未驗證：真模型 receive→query→結果→ACK→自然退出、正式長期背景、24 小時及桌面 queue。七欄與每日五次 authority 不變。
單次真驗方案仍為一件公開合成事件、最多一任務、180 秒，須先有當次批准與有效預算。沒有重複索取或自行啟動。

## 2026-10-24：事件驅動的專用 agent host

基底 `008a931121f03c1ceaa1abb6f26cbe08abf3bf48`。分支維持 `feat/local-codex-acceptance`。
功能、設定、測試與文件集中提交。提交對照留在本機 `reports/event-ingress-001/source-commit.json`。
沒有真模型、正式背景、網路擷取、排程、proxy 或其他聊天操作。既有私人研究與附件未納入提交。

| 命令／證據 | 實際結果 | 範圍及限制 |
| --- | --- | --- |
| `py -3.13 -B scripts/verify.py --run-dir reports/event-ingress-001/full-001 --timeout-seconds 600` | 1,177 run；1,174 pass；3 skip；exit 0；`passed_checks=true` | fixture、SDK、fake CLI、真本機 HTTP 及明示 Windows Job API。不是模型或採集掃描 |
| `verify.py --module ...`，完整 25 模組命令見 `final-delta-001/verification-summary.json` | 391 run；388 pass；1 fail；1 error；1 skip；exit 1 | 修正 resume/preflight 及 OS exit 取證後回歸。兩項失敗完整保留 |
| `py -3.13 -B scripts/verify.py --run-dir reports/event-ingress-001/final-delta-002 --timeout-seconds 180 --module test_delivery_validation --module test_delivery_consolidation --module test_agent_service` | 55 run；55 pass；exit 0；`passed_checks=true` | 修復下述測試契約問題。重驗受影響模組，沒有盲目重跑模型 |
| `py -3.13 -B scripts/validate_delivery.py service --root reports/event-ingress-001/service-ready-001` | exit 0；`prepared_only_no_model_invoked`；一件合成事件；來源仍空 | 未加 execute。沒有 host 或模型啟動。只是備妥真驗入口 |
| `py -3.13 -B scripts/eventguard.py agent status --format json` | exit 0；`not_started`；`desired_enabled=false`；`budget_unavailable` | 固定 budget DB/marker 均不存在；未初始化或假設零用量。原監看停止設定雜湊與上輪相同。見 `readiness.json` |
| Windows 空佇列 host 的 `lifecycle-evidence.json` | start／pause／resume／stop；OS exit 0；remaining 0；未強停；provider 未啟動 | 真 Windows Job＋隔離合成資料。只有父預檢 budget 是 mock；子程序不初始化正式預算。不證明模型收件或獨立長期壽命 |
| `node --check -` 經私有 Job，見 `web-syntax-final.json` | exit 0；stderr 空；Job 自然退出 | JavaScript 語法檢查。Web 路由另由真 loopback HTTP 測試。未作瀏覽器視覺或長期運轉驗收 |

全套與修復後定向回歸按當前測試 ID 去重為 **1,194 unique：1,191 pass、3 skip、0 failure/error，missing=[]**。
這不是最終來源全套重跑。逐項結果見 `combined-index-final.json`；受測來源與 `final-delta-002/source-manifest.json` 完全相同。Python **3.13.3**。
三個 skip 是兩項 symlink 權限測試及原生通知不可用。所有 guardian 均自然退出，remaining=0、未強停，沒有 per-test 殘留；失敗回歸的 worker exit 1 保留。

兩項回歸失敗的原因：生成事件原用秒精度，EventStore 的 `validate_event` 轉成微秒精度，導致 raw manifest hash 不同。現在生成與驗證共用 canonical 契約，另加雜湊一致性測試。另一項是舊測試遍歷新增 service case，但只替換舊 stage adapter；現在明列原四案例，service 由獨立測試覆蓋。沒有放寬工具 trace、ID、結果、ACK、閒置或退出條件。

測試索引初稿把 unittest 已含方法名的 ID 再附一次方法名，故檢查失敗；保留 `combined-index.json`。修正解析後使用 `combined-index-final.json`，不把索引失敗當產品通過或新增測試。

新驗收 case 使用原 `validate_delivery.py`。程式先啟動普通 host 等空佇列，再加入一件 high 合成事件，核對 receive→query→結果→ACK、前後短暫閒置、唯一 attempt、CLI／supervisor／host 退出。預設 prepare／verify 不呼叫模型；execute 需另有當次範圍。intent 先保存，失敗後同目錄拒絕重跑。fake receipts 與真模型仍明確分開。

未驗證：真模型通路、桌面 queue 喚醒、正式長期背景、24 小時 soak、完整漏洞診斷與 OpenOctopus 外部專案整合。七欄未擴大。ACK 不是風險處置或主機安全證明。

## 2026-10-23：公告追蹤與靜態適用性

基底 `bb6ecff55efbd86bd178e7b0005f077bca765ac9`。沿用 `feat/local-codex-acceptance`。本批只有新功能證據目錄 `reports/advisory-tracker-001`。正式背景與真模型未啟用。原 dot 追蹤不變。

三個子任務實作來源、盤點／版本及 SQLite。root 整合 CLI、背景 Job、原事件入口與驗收。核心沒有新增依賴或 MCP import。snapshot 七欄不變，只新增事件枚舉。未改帳本初始化或每日五次政策。

| 命令 | 實際結果 | 範圍 |
| --- | --- | --- |
| `py -3.13 -B scripts/verify.py --run-dir reports/advisory-tracker-001/verify-001 --timeout-seconds 600` | 1,066 run；1,062 pass；1 error；3 skip；exit 1。`source_unchanged=false` | 首次統測。ZDI 實抓修復在測試期間完成，設定 4 MiB 與已載入 2 MiB validator 不符。本輪保留，不當成固定版本通過 |
| 同命令，run-dir 改 `verify-002` | 1,077 run；1,073 pass；1 error；3 skip；exit 1。`source_unchanged=true` | 錯誤為新增 control 損壞測試未建立 host.lock 的父目錄。正式隔離背景 start／status／stop 已通過 |
| `py -3.13 -B reports/advisory-tracker-001/verify-delta.py` | 225 run；224 pass；1 skip；exit 0。`passed_checks=true`；受測來源不變 | 修正測試前置目錄。加範例 facts 解析、synthetic 隔離及盤點失敗可見性。重驗 10 個相關模組。沿用 verify 的私有 Job worker，沒有另加產品 harness |
| `py -3.13 -B reports/advisory-tracker-001/public-fetch.py` | 一般使用者有限 10 來源 GET。6 success；ZDI body_too_large；2 TLS 驗證失敗；Debian timeout；exit 0（探測程序正常結束，非全來源成功） | 真公開 HTTP。不是合成資料或模型 |
| ZDI 單次 HEAD 與修復後 GET | HEAD 200，2,403,491 bytes。GET success。六 ID 集合相同，32005=connman；exit 0 | `public-fetch-zdi-retry.json`。ZDI 設 4 MiB，上限仍有界。未繞過 TLS |
| `py -3.13 -B reports/advisory-tracker-001/replay-public.py replay-public-003` | 7 個已成功實抓來源；8 案件；10 事件。生成／receive／query／ACK 各 10，集合相同；missing=[]。第二輪新增 0；exit 0 | 真公開正規化資料＋6 個合成資產。直接 backend calls。模型 0。不是實機適用性或真 agent 驗收 |
| `.\EventGuard.cmd advisories status --format json` | exit 0；not_started；agent_enabled=false；budget_unavailable；剩餘未知 | 只查看現有計數。私人舊佇列數值不提交。沒有啟用、初始化或重置。沒有讀私人 session 或憑證 |

第二次統測與最後差集去重後為 **1,079 unique：1,076 pass、3 skip、0 failure/error**。不是在最終來源重跑全套。測試索引為 `combined-index.json`。Python **3.13.3**。最終差集 AST 共 **160** 檔無語法錯誤。

三個 skip 是兩項既有 symlink 權限測試，以及受限環境的原生通知。沒有將 skip 記為 pass。兩次統測與最後差集 guardian 都自然退出，owned remaining=0、forcibly_terminated=false。差集的 `lifecycle-evidence.json` 包含隔離合成背景 start／status／stop 與完整私有 Job 退出回條。沒有測試後殘留。

重播一曾因人工 facts 用非 canonical 生態名稱而只讀到 Rust 三資產。coverage 明示 invalid_facts_asset。其「passed」只涵蓋當時 ID 集合，不能當 Linux／uv 適用性驗收。重播二修正，重播三用最終程式再驗並要求 inventory success、6 資產。前次證據未覆寫。

實抓成功為 ZDI、RustSec 三案、Rust feed、uv 官方 API、CVE API。LKML／kernel git 的錯誤為 `tls_verification_failed`；Debian 為 `timeout`。未改憑證、安全設定、代理或驗證旗標。ZDI 日期只視為 vendor notified。未確認的 CVE、核心 commit 或發行版 backport 仍未知。官方來源與查核時間見 ADVISORY_SOURCES。

實作後另驗證：預設 facts 範例可讀，但含 synthetic 標記時不能進 live scope；來源換 URL 不沿用舊 ETag／快取；同 CVE 多元件不輪流告警；來源失敗在退避期間仍可見；pending 不改寫；outbox 成功而 mark 失敗後以相同事件位元組補送；ACK 前故障保留同 query 與已保存結果。這些都是離線／合成範圍。

正式 `data/background/control.json` 前後 SHA256 均為 `78F20282862F179B8DEB4AF769BD0692932EC273AE930C13375E987781CB41BA`。未解除既有停止。`source-manifest.json` 綁定受測位元組，提交後 `source-commit.json` 核對實際 commit。只提交功能、設定、測試與文件。不提交 reports、data、附件或既有私人研究。不推送。

尚未驗證：正式長期 HTTP、24 小時 soak、Linux 主機盤點、實際部署／運作版本、真模型 trace／工具接收／自然退出及 dot 交接。七欄不足以提供漏洞完整診斷；完整證據留本機。ACK 只表示收到。正式啟用與有限真模型驗收另等批准，不要求排程或重開 Codex。

## 2026-10-23：本機產品六項功能

本批基底為`98968ba4435fa178a4b8d05cc721150440f46186`。分支不變。以最新產品範圍為準。MCP 接線、閒置喚醒與開機自啟改為選配。它們不再阻擋工作。本輪不做 proxy、排程或模型呼叫。

新增 CLI／Web 事件檢視、可設定規則、四種處置狀態、七來源狀態頁、本機通知及單一 run 入口。Web 只綁127.0.0.1。列表先篩全庫，再分頁。事件內容用文字顯示。狀態寫入有來源與CSRF檢查。處置狀態存同一事件DB，不改payload、delivery、ACK或回條。清理原事件時同步清理處置列。pending不因已處理而刪除。

規則檔含五條預設。每輪重讀。只接受固定型別條件。不用eval、自由命令或任意查詢。無匹配時保留原分類。預設不把escalated或resolved降錯級。壞檔明示錯誤，既有query仍收尾。來源頁只讀保存觀察，顯示時間、結果、stage、原因碼及建議。Defender denied與tasks unknown分開。合成0x80070003保留為路徑不可見，不改寫AccessDenied或安全。

先完成全部功能，再執行以下統測。三個子任務分工資料、規則、來源與通知；root整合CLI、Web與run。執行資料只新增本功能批次`reports/local-product-001`，沒有一般接線或目標稽核的新報告。

| 命令 | 結果 | 範圍 |
| --- | --- | --- |
| `py -3.13 -B scripts/verify.py --run-dir reports/local-product-001/full-001 --timeout-seconds 900` | 20:09:16台北完成。948 run，944 pass，1 error，3 skip。exit1。257.805秒 | 全套。原錯誤與回條保留 |
| `py -3.13 -B reports/local-product-001/verify_delta.py` | 20:16:19台北完成。32 run，31 pass，0 error/failure，1 skip。exit0。9.653秒 | 只重測通知與本機產品兩模組。精確命令以delta-001/verification-summary.json為準 |
| `py -3.13 -B reports/local-product-001/verify_delta.py --modules test_local_product,test_core_cli,test_cli_workflow,test_local_notifications --run-dir reports/local-product-001/delta-002` | 20:25:15台北完成。59 run，58 pass，0 error/failure，1 skip。exit0。17.26秒 | 新增UTF-8修正後的最後相關差集 |

Python3.13.3。148個Python AST無錯。每組source_unchanged=true、per_test_residuals=[]。guardian皆自然退出，remaining0、forcibly_terminated=false；原全套仍exit1。回條保留shutdown_requested_reason=descendants_remaining，不把提出收尾當成從未清理。

唯一error在新通知滿載測試。測試ACK後未執行來源保留清理。原事件仍存在，通知回條依法保留，因此沒有新的event_id。修正測試先maintain並確認ACKed原事件已移除，再驗證通知回條滿載恢復。pending不丟。另讓失敗重試保留已載DLL/API，避免每秒重載。補兩項fake DLL計數測試。這些不是實際Windows彈窗證據。

實際啟動檔驗證另發現管線中文亂碼。CLI現在只對非tty管線固定UTF-8，不改Windows設定。修正後`.\EventGuard.cmd rules validate --format text`實際顯示「規則檔：config/rules.json。檢查通過。」及五條中文名稱，exit0。新增真owned Python子程序測試，嚴格以UTF-8解碼並核對中文。只補跑相關CLI／產品差集，其餘通過項目不重跑。

`combined-index.json`按完整測試ID合併結果。951個不同測試，948通過、3略過。不是把重跑數量相加。最後來源未全套重跑。最終manifest相較全套只改notifications.py、web.py、cli.py、test_local_notifications.py與test_local_product.py，差集已覆蓋。兩項skip為symlink權限不足；另一項為受限環境notification_icon_unavailable。未為略過項提權。

另以既有一般使用者送出一次固定合成Windows通知。僅使用sandbox例外，無UAC或管理員權限。實際輸出os_accepted_notification_request=true、own_icon_and_window_closed=true，命令exit0。未改系統設定。證據為windows-notification.json。這只證明OS接受要求；human_visibility_verified=false。原受限環境skip不改寫成功。

瀏覽器實際操作隔離合成頁：列出事件、選high篩選、開詳情、按已讀。新程序讀同DB，確認已讀仍保存。重載頁面後同事件仍為已讀。七來源的denied／unknown、HRESULT與建議可見，五條規則可見。高嚴重度頁面提示可見。畫面為ui-event.png。兩次demo均有期限，結束後web_thread_exited=true、child_exited=true、forcibly_terminated=false、model_calls=0；原owned退出回條在demo/data/background/operator-stop-receipt.json。沒有啟用正式監看或重新盤點主機。

本批測試為fixture、真loopback HTTP、SDK／fake CLI及有限Windows合成Job。先前實機七來源證據不被升格。本輪沒有真漏洞利用、24小時、重開機或長期承諾。程式與文件集中本地提交，不推送。執行資料、憑證、私人歷史、research與附件不提交。以下章節保留歷史，舊MCP阻塞與待批准事項不再是本輪產品前置。

## 2026-10-23：查詢啟動前耐久保存、跨 client 仲裁與實際執行回條

本批基底`5a4c7a766503be6a99ca1c997456696c3e55bd5b`，同一feature，保留research及附件。正式控制仍disabled/explicit_stop、原bytes/hash未變；無新主機盤點、事件接收／ACK、真模型、Codex CLI、proxy探測、排程或安全設定變更。正式主聊天本批一次真正capabilities仍缺application lifetime與新query admission標記，原回傳留`reports/query-admission-001/native-capabilities-before.json`；與前兩個目標回合是相同client reload阻塞，沒有重試Start。

`py -3.13 -B reports/global-admission-001/reproduce_before.py`於10:57:26.944581 UTC保留原碼反例，before-result.json為defect_reproduced=true、safety_passed=false：兩個獨立真Monitor與OS InstanceLock，但來源／未知Runner是fixture。第一個query退出未確認、shutdown gate寫入PermissionError後marker不存在、singleton釋放，第二個Monitor仍採集七個fixture來源。child/provider/model皆0，source未變；不是實機磁碟故障。顯式任意collector注入仍是library seam，after不以在fixture手動補marker假稱所有入口已保護。

修正在既有Runtime／Runner內加入root-bound query_launch hook，不另建控制器：固定query-admission.lock涵蓋舊Job核實、確切Global Job計畫atomic/fsync及spawn返回；保存失敗不spawn，未知Job保持閘道。所有gate write/recover/unlink同lease；先有exact Job空／missing證據與耐久recovered回條才clear，owner退出僅釋lease不等於子樹已退出。同process只能釋放自己原本持有且已退出的child／空Job handle，另一client不收養、不開PID、不動其他程序。預設Monitor→WindowsCollectors→Runner、CLI query與OperatorAPI diagnose均接此hook；獨立library須明確傳hook、舊MCP不熱更新。新capability明示scope、pre-spawn拒絕及post-spawn釋lease失敗保留child的差別。

Monitor對確實零spawn的policy拒絕保留baseline、不扣長來源間隔，按既有保存背壓／短defer恢復。診斷保存busy／unknown但不虛稱已執行system query，cache驗證一致。審查另找到native已執行後fallback零spawn可能抹掉前一attempt的問題；每attempt現保留安全process投影，任何已spawn attempt都不能回退last或宣稱整來源零執行。舊多attempt缺process證據亦保守保留已嘗試語義，不補造成功或安全結論。

| 根目錄命令 | 實際結果／UTC | 範圍與退出 |
| --- | --- | --- |
| `py -3.13 -B reports/global-admission-001/verify_admission.py` | 11:14:28.687846完成；319 run、317 pass、1 fail、1 symlink權限skip；85.491秒 | focused-001保留唯一新測試時序fail：原合成query exit0後立即assert Job.active0，當下仍1；source不變、無逐測試殘留，guardian自然exit1、未強停、remaining0。不能列整組通過 |
| `py -3.13 -B reports/global-admission-001/verify_reap.py` | 11:15:53.703892完成；只重測該case，1/1通過；0.227秒 | focused-002；測試改為最多3秒自然等待同一Job清空，沒有finish／強停來湊條件；產品source未改 |
| `py -3.13 -B reports/global-admission-001/verify_projection.py` | 11:20:08.832234完成；最後受影響差集49/49通過；4.893秒 | focused-003；完整review_binding／collector_contract／monitor_admission_barrier，另capability與production diagnosis兩個精確case，覆蓋per-attempt投影、cache、Monitor與新欄位 |

後兩組均Python3.13.3、137個Python AST無誤、0failure/error/skip、source_unchanged=true、per_test_residuals=[]，guardian自然exit0、未強停、remaining0。初組其餘已通過項目保留，不重跑或把三組數量相加為完整suite；final-evidence-index.json核對323個不同test，最終322通過、1skip，列明各版本manifest差異及最終有效範圍。Windows case僅固定合成Python worker／私有Job及跨process lease，不是新Windows provider盤點、真磁碟故障、模型、主聊天新版Start、長期或OS重啟證據。其他case為fixture／SDK／fake CLI，與前批七來源實機與真工具投遞分開。

原始before-output、unit-tests、lifecycle-evidence、source-manifest、guardian-exit與每組verification-summary均留`reports/global-admission-001`。只讀文件／source／正式Pause核對為`py -3.13 -B reports/global-admission-001/check_release.py`，結果見document-check.json；最後本地commit綁定source-commit.json。執行資料、真事件、憑證與私人歷史不提交、不推送。本主聊天需client正常結束舊EventGuard MCP連線並載入新碼後，核對兩項capability，才可驗一次有限Start/Status/Stop；此聊天無reload工具，不強停或追proxy旁支。24小時、登入／重啟及閒置同聊天事件觸發仍未通過，不宣告整體目標完成。

## 2026-10-23：隔離實機生命週期與 supervisor metadata 故障恢復

本批基底`ecdb479716dd7736839db7681112529e2cdf1fc7`，同一feature；正式背景仍disabled/explicit_stop。本主聊天一次capabilities／status核對仍是舊server、沒有新lifetime標記，所以不再呼叫其Start；原生回傳留`reports/operator-live-001/native-*-before.json`。沒有連proxy、建立排程／服務、自啟、提權或真模型任務。

**實機部分與fixture分開。** `py -3.13 -B reports/operator-live-001/probe_live.py`啟動ecdb479的實際`eventguard_inbox_mcp.py --operator-root ... --namespace live --allow-live`；使用新隔離root、原設定／playbook與普通sandbox執行上下文，沒有替換Monitor／host argv／collector，沒有重用正式live資料。只在隔離root開放工具權限，不改正式開關、config、每日預算或MCP設定。SDK client不是本聊天原生工具。

10:26:53.472564 UTC明確Start回started/application；七來源於本輪均有新observed_at/saved_at、實際backend attempt、同Monitor instance及host PID＋建立時間，evaluation_status=committed。Defender為denied（provider AccessDenied／PermissionDenied、CimException、HRESULT -2146233088），tasks為unknown（TaskGetFolder／COMError、HRESULT -2147024893）；listeners／processes partial，startup／services／versions ok。拒讀／未知如實保存，不推斷需要管理員、與前批不同上下文可讀結果相互替代、或主機安全。原始coverage及安全原因碼留隔離observations與health，不提交真實事件、名稱或路徑。

Probe於10:28:55.136413 UTC **exit1 / validation.passed=false**：helper條件誤排除了有實際attempt的unknown，因此等到120秒期限；它的額外SQL計數亦用了錯誤表名，只記schema_not_counted，未改DB。原輸出及程式保留。期間沒有重啟server或重掃來湊成功，退出走正常stdin EOF；SDK server、application host及七來源worker各自證據均自然退出、未強停、remaining0。operator-stop-receipt保留原run／generation／Job，隔離控制回disabled，正式Pause bytes完全未變；所有本輪隔離事件保留pending、零ACK回條。

後續`py -3.13 -B reports/operator-live-001/verify_saved.py`只讀既存JSON與SQLite(mode=ro/query_only)，exit0，`real-collection-evidence-002.json`為evidence_valid=true、seven_source_attempts_verified=true、lifecycle_verified=true、**all_sources_readable=false**。核對時間用timezone-aware datetime；不把helper exit1改為產品成功。它補上host/Monitor身分、source payload hash、pending／無receipt及同root activity的background_start completed/started、active0；第一次較窄只讀核對也保留。此verifier沒有子程序、provider或模型。原sdk-calls、server-exit、隔離owned stop回條、source-manifest與兩份只讀證據均保留。activity屬隔離root，不假稱出現在正式GUI帳本；不是新版主聊天Start、閒置喚醒、24小時或OS登入證據。

**已重現的長期故障。** `py -3.13 -B reports/supervisor-recovery-001/reproduce.py`於10:26:54.233586 UTC exit0；before-result.json顯示defect_reproduced=true。Fake Keeper/Monitor隔離fixture只讓控制thread一次run.json寫入拋PermissionError，此後全部恢復；舊serve仍只嘗試一次Monitor、retry_waits=[]、退出後enabled=true，mocked status=enabled_not_running，必須手動Start。child/native/model attempted0，控制thread已退出、source未變。這是實際執行的控制流程反例，不是Windows磁碟故障或真OS退出證據。

修補run／heartbeat發布失敗先取消當次Monitor並保留supervisor／enabled，沿原RESTART_DELAYS等待；新Monitor前必須成功耐久發布run，並在active lock內檢核故障競態。Stop／owner退出／generation變更與控制未知的邊界保留，最後回條仍不可寫則明示blocked/evidence_write_failed。已進行的ecdb479實機部分與本次故障恢復補修分開，不宣稱補修後又重掃七來源；當版測試、source hashes與最終提交綁定統一留`reports/supervisor-recovery-001`。

Keepalive初版複查又以`py -3.13 -B reports/supervisor-recovery-001/reproduce_gate.py`重現未知query閘道遺忘：10:37:59.490982 UTC，安全測試實際1fail（helper exit0表示expected_failure_reproduced=true），第二個Monitor在原gate尚未保存／查證前被建立。gate-before-result.json及原測試輸出保留；該反例是uncommitted keepalive初版的控制流程，不冒稱實機或ecdb479原樣測試。child/native/model0、source未變。最小補修只在background保留原Monitor/Runner與首次Job證據；marker缺失也不放行，需同Job既有gate確認empty／missing並完成原Runner自身handle收尾，未知繼續等待、Stop及控制換代仍先處理，不改Monitor/runtime或另建控制器。

剩餘界線已列回維護目標：此fence只保同supervisor重試。若gate完全無法耐久保存且Monitor已釋放singleton，其他獨立client仍可能看到無marker；本批沒有聲稱跨client磁碟故障admission已全域阻擋。這是讀碼確認的待重現／補強項，不冒充已驗證安全。OS重啟、24小時與新版主聊天Start也仍未通過；不因此縮小整體目標或宣告完成。

最終fixture／相關整合命令：`py -3.13 -B reports/supervisor-recovery-001/verify_recovery.py`，2026-10-23T10:44:46.757319 UTC完成、Python3.13.3、56.731秒，**79/79通過、exit0**；0failure/error/skip、136個Python檔AST無誤、source_unchanged=true、per_test_residuals=[]，guardian自然exit0、未強停、remaining0。四模組為新test_background_persistence_recovery（9項）、test_background、test_background_integration、test_operator_monitor_owner；涵蓋heartbeat與main publish故障恢復、持續故障Stop、control未知／換代、admission競態、gate失敗與原Runner handle收尾、Ctrl+C保留未知，以及既有SDK合成Job生命週期。來源盤點／模型不執行，沒有將fixture或SDK case升格成真磁碟故障、主聊天更新或24小時證據；不重跑／累加先前全套。source-manifest、unit-tests、lifecycle-evidence、guardian-exit與verification-summary在focused-001；文件檢查與最後source/commit綁定在document-check.json及source-commit.json。

## 2026-10-23：正式 Start 缺口與 MCP 應用持有生命週期

本批基底`3e3692507bceadbd7cd701b612396f7658cb6327`，同一feature；保留既有研究／附件。先實際呼叫本主聊天正式status→start_monitor→status→stop→status。Start於10:00:28 UTC回`blocked / independent_background_unverifiable`，desired_enabled=true；這是外部Job下舊server走independent契約，**未建立child**，不是監看成功或child自然退出。10:00:34 UTC Stop恢復disabled/explicit_stop；最後host已退出、remaining0、未強停。沒有新來源觀察／事件／ACK變動，也沒有啟動模型。原生回傳及EventGuard activity在`reports/operator-start-001/native-calls.json`、`activity-after.json`，可見agent_mcp的失敗開始與成功停止。

`py -3.13 -B reports/operator-start-001/verify_before.py`於10:05:33.635464 UTC exit0：before-validation.json為observation_valid=true、**start_monitor_passed=false**、cleanup_restored_original_pause=true。它核實這次失敗與恢復，不把helper exit0混作產品Start成功。七來源實機及正式事件接收仍沿用security-core-001，未重做盤點或處理其餘backlog。

修正operator adapter明確選既有application-owned核心；CLI預設independent不變。不經DesktopController、不恢復GUI保存的auto-agent選擇、不用測試allow_parent_job或breakaway。Start只保存自身callback的新child與可信scope；EOF先封鎖新Start並等已接受Start，再於控制鎖內核namespace/run/generation/job，含「新Start已改control但未寫launch」競態；不採納其他client既有host或追停新owner。最後只finish實際owned Job。status的launch_intent與後續run持續顯示application lifetime。固定有界operator-stop-receipt經atomic/fsync保留退出、forced與原因；空觀察者不覆寫，EOF／中斷收尾強停、未確認或保存失敗不能報clean exit0。

root＋lead＋兩個子任務兩層分工，source freeze後統測；新增24項契約／ownership案例。四項SDK案例使用真正Windows私有Job及合成Monitor，涵蓋Start/Status/Stop、正常EOF、Start未回應前EOF、雙client observer不接管／不停止他人host。它們是SDK協定及程序治理證據，**不是主聊天新碼已載入、真主機採集或agent喚醒證據**。

| 根目錄命令 | 實際結果／UTC | 範圍與退出 |
| --- | --- | --- |
| `py -3.13 -B reports/operator-start-001/verify_owner.py` | 10:16:04.545898；149/149通過，76.143秒 | ownership、operator_api/clients、background、desktop/integration、QueueInbox、delivery_consolidation；focused-001保留所有回條 |
| `py -3.13 -B reports/operator-start-001/verify_integration.py` | 10:18:23.680843；107/107通過，31.912秒 | 與上一組模組不重疊：background_integration/jobs、local_stdio、stop_binding、operator_status/workflow、activity、core_cli；integration-001保留所有回條 |

兩組均Python3.13.3，135個Python檔AST無誤，0failure/error/skip、source_unchanged=true、per_test_residuals=[]；guardian自然exit0、forcibly_terminated=false、remaining0。每組source-manifest／unit-tests／lifecycle-evidence／guardian-exit／verification-summary均保存；不把兩組加成完整suite，也不以先前全套覆蓋本批新碼。沒有主機inventory、真Codex／額外模型、排程、自啟或安全設定變更。

修改後主聊天只再呼叫一次真正`capabilities`，仍缺`background.start_lifetime_owner`等新標記，保存在native-capabilities-after.json；**當前server仍舊，不再重試Start**。官方[app-server文件](https://learn.chatgpt.com/docs/app-server)記載config/mcpServer/reload會重新讀設定並排入已載入thread的refresh；本聊天沒有可呼叫reload工具，未核實此client上EventGuard-only reload入口。沒有連proxy、改其他MCP、強停server或藉此建立排程。待client正常重新載入後核對`start_lifetime_owner=application`，才做一次有限真Start/Status/Stop；目前正式背景仍暫停，未宣稱已熱更新。

文件檢查與當版source/commit綁定在同目錄document-check.json、source-commit.json；執行資料與完整回傳不提交。應用持有監看依賴server及祖先Job，意外退出未必保存回條；24小時soak、OS重啟／登入、閒置同一聊天事件觸發仍未驗證，目標不因本批局部修補宣告完成。

## 2026-10-23：本主聊天連續／批次與容量恢復的真工具接收

程式基底`645d8d9ea8def504fd66b0cb16fcfd3850ea86c9`，同一feature，本批只更新文件，不改產品碼。沿用已批准的eventguard_test及`reports/chat-receive-001/operator`合成test佇列；未改MCP設定、正式live資料或日額帳本，未啟動額外Codex任務／模型、OS盤點、背景或排程。既有server載入世代沒有辨識，不宣稱本批熱更新或重驗新schema故障。

`py -3.13 -B reports/chat-delivery-003/producer.py setup`先確認原佇列四件均ACK且active inbox=0，保存原config／inbox policy bytes與SHA。只把這個合成root的inbox.max_events暫設3，其他來源／data保留。`emit single`、`emit continuous-1`、`emit continuous-2`、`emit batch-recovery`分段產生7件公開合成事件；ID及隨機port先存manifest，不輸出給聊天。主agent從真list回傳才取得各ID；第二件continuous在前件ACK後才產生。所有producer命令觀察exit0；不是Codex CLI或worker退出證據。

主聊天實際呼叫四個原生工具，原始參數／回傳／返回時間在`native-calls-all.json`。receive內含真正query_evidence的七欄snapshot／query_id，沒有獨立query工具，也沒有執行Windows診斷。batch三件先receive／inspect而不ACK，第四件receive明確回`inbox_event_capacity_pending_preserved`；容量前後active=3、pending=4，來源hash／回條／接收檔案不變。ACK一batch釋放一格後，原第四件成功receive；先保存仍pending、snapshot/query存在且result/completed不存在的唯讀證據，再處理其他batch，最後補收同event/query/received_at/snapshot並ACK。ACK重播同result_id，不另建回條。

**獨立比較命令**：`py -3.13 -B reports/chat-delivery-003/verify.py`，Python3.13.3，自然exit0，`validation.json`為passed=true、missing=[]、extra=[]、duplicate_receipts=[]。生成／accepted／原生list發現／成功receive／query／inspect／新ACK／SQLite回條八組ID集合完全相同，各7件。共32次真工具呼叫：list6、receive9（8成功＋1容量拒絕）、inspect9、ACK8（7新增＋1重播）。補收件成功receive兩次；recovered_same_event_and_query=true、pending_evidence.verified=true、capacity_recovery.verified=true。這是工具接收證據，不是mock或SDK代呼；沒有新CLI JSONL或子任務正常退出證據，不能當作原五個真CLI任務驗收、跨任務退出恢復、閒置喚醒或重開機成功。

最後`producer.py checkpoint final`與`restore`均exit0，新事件全ACK、active=0；config及inbox-limits原bytes／hash均恢復。四件歷史的event_id／payload_hash／delivery_status／receipt／updated_at五欄一致，當前payload canonical hash吻合原hash。沒有保存歷史payload原始bytes，不能宣稱原序列化文字逐byte比對。原始manifest、emission、每階段checkpoint、SQLite及完成檔留本機；驗證器只用mode=ro/query_only讀DB，記錄來源hash。

兩次helper失敗原樣保留：以過長shell參數回存JSON遭Windows 206，該保存程序未啟動；改由apply_patch保存既有tool log，沒有重做投遞。補收比較最初把dict的key順序當差異，改比較既有第二次回傳的key/value，實際query／時間／snapshot都相同，沒有再呼叫receive。證據在log-save-failure.json及comparator-helper-failure.json；不是產品或投遞失敗。

當版source仍完全吻合前批full source manifest；本批沒有重跑未變的完整suite，也不與前批測試數相加。文件／提交綁定在`reports/chat-delivery-003/source-commit.json`；goal-completion-audit.json保留仍未證明的長時／登入／閒置條件，目標未宣告完成。執行資料、ID、完整回傳、研究及附件不提交或上傳。

## 2026-10-23：長期採集公平性、ACK 收尾恢復與精簡狀態

本輪基底`5bff8082edef38d6d30cfd816f1579cb073fc313`，沿用同一feature及資料；三個子agent分工，root整合後統一測試。正式MCP只唯讀查status，確認背景仍disabled／host已退出；沒有解除explicit_stop、追加實機採集、ACK正式事件、呼叫真Codex／模型、建立排程或變更安全設定。前批主聊天真七來源／接收證據獨立保留，不以本輪fixture升格。

**修正前可重現問題。** (1) Monitor固定來源順序與round開始時間計算interval：在合法60秒query timeout、前幾來源30秒interval下，虛擬20輪1209.5秒只嘗試defender20次，其餘六來源未collect；另一測試看到listener實際間隔80秒、小於設定120秒。新測試對原碼實際2fail，輸出在reports/fair-collection-001/test_before_observed.json。(2) completed寫入故障後SQLite已ACK、triple仍在；配置兩個outbox TTL=0，維護清掉payload／receipt後，新pending因舊triple固定回bound_event_missing。實際原輸出保留reports/inbox-finalization-001/before.json，不是把錯誤文字推測成實機問題。

**實作。** 到期來源按實際嘗試開始時間最舊／未嘗試優先，stable tie不變；round_budget跳過仍busy＋30秒defer，不更新last，不放寬45秒啟動預算、query timeout或合作停止。ACK交易原子保存receipt及pending_finalization，TTL／count／byte清理排除未完成proof；completed耐久後才解除、再清triple，重啟可補完。pin受receipt_limit與byte cap限制，滿載回滾新ACK、pending不丟。status／overview唯讀顯示未收尾數，舊schema回null且不遷移；升級前已遺失proof仍blocked。舊長駐程式須正常重新載入，不宣稱熱更新。

overview只合併完全相同的安全錯誤樣本，sample_occurrences不當成總失敗數；原error_count／errors_truncated／各stage及OS碼／attempt順序／coverage／freshness保留。原status、observation及collector契約不變。對前批已保存的coverage離線投影，UTF8大小41622→8666 bytes，減少79.2%；這是大小量測，不是模型token、CPU或實機監看效能保證。

| 命令／範圍 | 實際結果 | 證據 |
| --- | --- | --- |
| `py -3.13 -B reports/fair-collection-001/reproduce.py`，前後相同虛擬clock fixture | 原碼20輪只defender；修改後20輪七來源都有實際fixture collect，回歸在14輪內全部嘗試；非真provider或24小時 | before.json、after.json、reproduce.py |
| `py -3.13 -B reports/fair-collection-001/verify.py`，monitor progress模組 | Python3.13.3；18/18通過、exit0；3項新測試含公平／實際interval／停止，Popen0、source_unchanged=true | test-result.json、test-output.txt |
| `py -3.13 -B reports/inbox-finalization-001/verify.py`，本機SQLite／合成事件 | 09:22:16–09:22:29 UTC；9/9通過、exit0；TTL0、completed／finalize故障、completed-only恢復、count與64KiB／80cycle byte壓力、pin滿載回滾與解除恢復、舊schema遷移、不同proof拒絕、遺失legacy proof仍blocked；source_unchanged=true，無child／provider／模型 | after.json、test-output.txt |
| `py -3.13 -B reports/overview-errors-001/verify.py`，精簡overview fixture | 09:20:55–09:20:58 UTC；14/14通過、exit0、source_unchanged=true；無child／live query／模型；其後root新增readonly未收尾數測試，以下統測涵蓋 | result.json、test-output.txt |
| `py -3.13 -B scripts/verify.py --run-dir reports/runtime-reliability-001/full-001 --timeout-seconds 900` | 09:32:37.970933 UTC完成；Python3.13.3，815執行、813通過、2skip、0failure/error，463.486秒；134個Python AST無誤，source_unchanged=true、per_test_residuals=[]、passed_checks=true | verification-summary.json、unit-tests.txt、lifecycle-evidence.json、source-manifest.json、guardian-exit.json |

完整suite兩項skip均為一般使用者無法建立symlink，未提高權限；其餘scope為fixture／SDK／fake CLI與明確標記的真Windows owned-job API。guardian自然exit0、child_exited=true、未強停、remaining0；沒有主機盤點、真模型、真agent喚醒、OS重開機或24小時soak。本輪成功不抹去前批600秒逾時或其強停回條，測試數不與前批／子agent相加。

文件核對命令`py -3.13 -B reports/runtime-reliability-001/check_release.py`，核對full source manifest、README行數、本機連結及文件hash；最後傳入本地commit寫source-commit.json，將完整受測source／文件hash與提交綁定。執行資料及既有research／附件不提交，不推送。

## 2026-10-23：收斂本機資安監測、資料品質與真工具接收

基底`11d2dd76d99742fcc3b4715c2ff8d1b92aae77ca`，同一feature。人類最新要求回到「本機監測→保存→agent可分析／必要時收event」，排程與proxy不再是前置。未建立排程、服務或自啟，未啟動另一個Codex／模型，未改安全設定或執行政策。MCP實際操作的回傳、實機資料與ID只留本機忽略`reports/security-core-001`，不提交真資安紀錄。

**真實資料流程（修正前當版已運行MCP）。** 本主聊天實際呼叫正式`monitor_once`，08:32:58 UTC開始，七來源各執行一次並保存觀察與事件。Defender/listeners/processes為partial，startup/services/tasks/versions為ok，各有資料、evaluation_status=committed，所有查詢child自然exit0／remaining0，monitor最終stopped／cycles1／model_calls0。這是有限唯讀實測，沒有持續恢復已暫停的背景，也不是24小時或OS重開機證據。

主聊天從本輪新生事件選一件真listener事件，實際`inspect_event→diagnose_event→receive_event→ack_event→inspect_event`；查證是固定事件port的即時唯讀查詢，結果partial、當時未再觀測到端點且缺程序綁定，沒有把查無資料判恢復。保存診斷後事件仍pending；ACK decision=`needs_more_evidence`，只表示已收到，incident_conclusion保持not_assessed。`py -3.13 -B reports/security-core-001/verify_native_flow.py`於08:57:08.692253 UTC exit0，核對實際工具回傳／來源payload hash／同event/query／saved review／SQLite receiver_receipt_id，選定集合生成／查證／收到／ACK各1且相同、missing_for_selected=[]、duplicate_receipts=[]、該事件回條1張。只驗一件，沒有宣稱正式backlog全送完。報告工具另實際匯出JSON／HTML，路徑在native-report-tool.json；正式activity可回查本輪操作。

**四項實作。** (1) listener身分不可比時保留同端點舊事件、重置恢復streak，不因ref暫失產新件或誤resolved；可比較PID重用與真正消失仍按原規則。(2) persistence新事件保存最多5筆entries，opaque entry_ref對照原changed_keys，固定enum及ASCII80名稱投影，不存路徑／命令；目標消失後仍可讀歷史。typed query只接受事件refs並在max_rows前篩選，避免25個舊service遮住新目標。(3) 新／保存查證核對operation/source/port/程序實例/ref；錯配拒絕，舊未綁定cache清列並明示unverifiable。(4) Defender auto改採既有Get-MpComputerStatus七項有效狀態；其他六來源原生優先，通用拒讀／partial不重試政策不變。native-only配置／WSC仍不升格為有效狀態。

**Defender一般使用者實測另列。** `py -3.13 -B reports/security-core-001/probe_defender.py`一次明確powershell backend，08:39:31 UTC啟動，status=ok、七欄、provider無錯誤；證據defender-provider-001.json。修改選路後`py -3.13 -B reports/security-core-001/probe_auto_defender.py`於08:48:29 UTC啟動，auto實際backend=powershell、七欄ok、passed=true；證據defender-auto-002.json。兩個程序各自然exit0、無強停、remaining0／runner_pending=false，未改Defender設定。這是當前一般使用者可讀性，不改寫以前sandbox CIM拒讀或native-only partial證據，也不表示主機安全。

**Fixture與整合驗證分開。** analysis子agent命令`py -3.13 -B reports/analysis-evidence-regression-003/verify.py`，Python3.13.3，相關75/75通過、exit0；Popen0／nativecollect0／model0、source_unchanged=true。新增23項歷史目標、同名task路徑、截斷前ref篩選、對抗名稱與cache錯配測試；舊規則隱私canary改為含指令／路徑／控制字元並保留不落原文斷言。listener子agent以原碼跑新7項為6fail/1pass，記憶體套最小patch後新7＋舊6全通過；與rules合跑曾因舊canary契約衝突有1fail，該失敗保留，最終已整合修正。不以記憶體patch測試取代root當版統測。

完整回歸命令`py -3.13 -B scripts/verify.py --run-dir reports/security-core-001/full-001 --timeout-seconds 600`到期限未完成，停在watch測試階段；worker_summary缺失、source_unchanged=true、passed_checks=false。guardian exit1460、forcibly_terminated=true／reason=timeout／remaining0，**不是全套通過或自然退出**。原輸出與回條完整保留。後續僅補驗本輪受影響模組與截止時未完成的watch／stdio；結果另記，不能與部分全套或子agent數字相加冒充全套。

補驗命令`py -3.13 -B reports/security-core-001/verify_selected.py`，Python3.13.3，09:02:03.141741 UTC完成：190/190通過、0 failure/error/skip，112.576秒。範圍為collector契約／diagnostics、listener身分與恢復、persistence evidence、review binding、guidance、rules、OperatorAPI、transport、watch與local stdio；fixture／SDK／fake CLI及明確標記的Windows owned-job API，不執行主機盤點或模型。133個Python檔AST無誤、source_unchanged=true、per_test_residuals=[]；guardian自然exit0、未強停、remaining0、passed_checks=true。精確模組、回條與逐項輸出在selected-001/verification-summary.json、guardian-exit.json、unit-tests.txt。這是相關模組通過，沒有冒充完整suite。

失敗helper另保留：native-flow初版錯把附delivery欄位的資料直接hash而失敗，修為validate_event後比對，同一保存資料重驗通過，沒有重跑實機採集。先前獲批准的proxy helper使用不存在的收尾reason而exit1，未保存連線／child回條，不能宣稱收尾確認；依人類方向不再重試，紀錄在reports/wake-queue-research-001/proxy-metadata-001/helper-failure.json。

`py -3.13 -B reports/security-core-001/check_release.py`於09:08:57 UTC exit0：README 95行、所改文件本機連結無缺漏、當版程式與selected／full啟動前manifest一致，實機flow／Defender／相關suite結果可讀且通過、全套逾時失敗如實保留，HTML存在。僅核對既有檔案，未追加採集／模型；最後文件整理後同命令再核對，結果在document-check.json。

當版程式與完整source hashes、文件檢查及最後本地commit綁定留`reports/security-core-001/source-commit.json`。已啟動的舊GUI／MCP不視為熱更新；新證據形狀的fixture／新SDK測試與上述既有主聊天真事件分開。一般權限下process/listener身分仍可能拒讀，沒有完整防毒掃描、漏洞可利用性、idle-chat wake、24小時soak或OS重開機承諾。

## 2026-10-23：既有聊天喚醒前置與當版登入恢復dry-run

基底`af839b36a4f43efbc5e273680ba2f597edb93df1`，同一feature；上一目標回合有實質程式／真工具／合成驗證進展。本回合保留現有explicit_stop，不啟動監看、模型、server/daemon或排程。兩個子agent分讀喚醒入口與登入恢復，root整合；本批只有文件變更與本機忽略的探測／回條。

既有原生CLI版本`0.163.0-alpha.11.2`，使用本機已安裝codex.exe，沒有下載／更新。命令由`py -3.13 -B reports/wake-queue-research-001/help_probe.py`及control-help helper呼叫`--version`、`--help`、`queue --help`、`app-server --help`、`app-server proxy --help`、`app-server daemon --help`、`app-server daemon status --help`。七個child自然退出、私有Job remaining0、未強停；不存在的daemon status help為exit2，其他exit0。stdout、SHA及逐程序回條在help-results.json／control-help-results.json。help確認queue可指定既有session、proxy只連已運行control socket；**沒有實際送queue、連socket、起回合或server**，不能據此聲稱idle喚醒。

root備妥`reports/wake-queue-research-001/proxy_probe.py`，只用既有proxy發initialize及目前thread/read(includeTurns=false)，不resume、不查其他聊天／history、不開server或送turn。但`exec_command`的自動核准審查在執行前拒絕，認定metadata仍屬AGENTS禁止的私人Codex session存取、欠缺此精確授權。**Python／proxy均未啟動**，probe輸出目錄不存在；沒有變通或間接重試。證據proxy-approval-block.json，下一步需明確批准此metadata範圍；不是模型呼叫批准。官方文件／候選比較見[喚醒／恢復關卡](WAKE_RECOVERY_GATES.md)。

登入恢復命令：`py -3.13 -B scripts/eventguard_schedule.py install --dry-run --plan-dir reports/recovery-gate-001/schedule-review`在sandbox身分08:11:37.472131 UTC回blocked／exit1，GetFolder HRESULT80070003、parent_folder_confirmed=false，保留unknown。既有授權的一般使用者sandbox例外執行相同dry-run到新的`.../schedule-review-normal-user`，08:12:01.591273 UTC自然exit0：根folder已確認、GetTask HRESULT80070002，專屬任務absent。不同身分結果分開，沒有以GetFolder失敗推論任務不存在。

新plan/action source綁定與UTF-16 XML實際核對通過；57項來源hash與af839b36相符，SHA=`03b312cd6e08df1517c908956d0c38864c7bc2e715a4f144ab290311d04b35c6`。只有一個同使用者ONLOGON／InteractiveToken／LeastPrivilege／PT0S任務，start_now=false、AllowHardTerminate=false、不帶覆寫。現有enabled=false／explicit_stop保留；註冊即使將來批准也不會解除它。沒有Create、Run、服務或OS重啟，尚未批准安裝。

離線契約驗證命令`py -3.13 -B reports/recovery-gate-001/verify_review.py`，Python3.13.3，08:14:46.023754 UTC回條：**28/28測試通過、exit0**，Popen直接guard在suite後仍installed、child attempts0，failed_checks=[]。最後證據review-verification-003.json／offline-schedule-tests-003.txt；這些mock測試不代替上面真COM查詢，更不是實際註冊／重開機驗證。第一版helper的patch guard被既有test的patch.stopall解除，自審後改直接guard；002因先換Popen再import asyncio造成loader ImportError（1 error），修正為先載入unittest.mock，003確認全程沒有子程序。中間輸出保留，不當產品或最終通過。

新文件／連結及source hashes另核對，不重跑無改動的整套。來源、文件及本批commit綁定留reports/recovery-gate-001/source-commit.json。剩餘批准項目為精確metadata唯讀探測、僅登入註冊；模型與Phase7實機／OS操作未包含。

## 2026-10-23：建立持續目標、主聊天正式工具與多client修復

基底`bf99496cf3d73601fc2d8a1bf50c1c2fe8709b66`，分支`feat/local-codex-acceptance`；保留既有研究及附件。依使用者「建立目標，繼續完成」建立active目標，未設定token預算。本批一般權限，不啟動監看／本機inventory／真Codex或模型，不建排程／服務、不改安全設定或全域MCP。專案MCP沿用既有批准與設定，SHA256=`b851bc89137e133f1eb1e023ec74d9ffe384e154e2b2bed6eeadaee6362a70d0`，未再修改。

**具體故障與修正。** 真正使用已批准正式profile做initialize/tools-list時，child在回應前exit3；stderr長65bytes，SHA256=`82047e5e7752fa14412e0c381567babdb21f30c0791172e482c1a2b58f4a9ebf`，逐位元匹配程式固定訊息`EventGuard: this inbox state already has an active stdio owner.`。這證明當時有OS lease owner，不是僅憑鎖檔存在推測。程式原把operator整段stdio生命週期鎖成單連線；本輪改為短期mutation鎖，讀取及Stop繞過此鎖。沒有刪鎖檔或找出／終止現有owner；也沒有把所有歷史client載入延遲歸因於同一原因。

scoped Stop在background控制鎖內驗namespace，保存原owner/run；寬限後換代回busy，強制收尾只用原選定Job。Runtime request_stop接受expected_instance_id，缺失／換代不追隨新owner；OperatorAPI無效ID固定拒絕，不能退化成global stop。人類無scope停止保留。legacy bound adapter維持exclusive stdio owner。兩個有界CLI argv builder另明確停用已知`eventguard`／`eventguard_test`，保留自身eventguard_inbox／eventguard_local；不宣稱隔離所有未知平台工具或已做真CLI驗收。

| 命令（根目錄） | 實際結果／UTC | 範圍與退出 |
| --- | --- | --- |
| `py -3.13 -B reports/bounded-cli-scope-001/verify_command_scope.py` | 07:43:36.764559；5/5通過，0.659秒 | 純argv/TOML，Popen patched禁止啟動；exit0，model0 |
| `py -3.13 -B reports/goal-center-001/probe_operator.py`（修正前，輸出operator-metadata-001） | 07:44:36.259591；passed=false、initialize未回應，20.007秒 | 真profile/stdio，不呼叫業務工具；child自然exit3、remaining0、未強停，保留原失敗 |
| `py -3.13 -B reports/goal-center-001/verify_selected.py` | 07:59:00.900986；116執行、115通過、0failure/error、1skip，46.291秒 | Python3.13.3；operator_api/clients、stop_binding、background、agent_dispatch、codex_acceptance、delivery_validation。130 AST無誤，source_unchanged=true、per_test_residuals=[]、guardian自然exit0／remaining0／未強停 |
| `py -3.13 -B reports/goal-center-001/probe_operator.py`（修正後，輸出operator-metadata-002） | 07:59:07.959060；passed=true，15工具、1.852秒 | 同一正式設定SHA；只initialize/tools-list/EOF，child自然exit0、remaining0、未強停；不是聊天工具載入的替代證據 |
| `py -3.13 -B reports/goal-center-001/verify_native.py` | 07:59:01.541059；passed=true | 本主聊天原生MCP完整回傳對照合成manifest及SQLite唯讀驗證；exit0，沒有另開模型 |

新雙client測試啟動兩個真正Python/SDK stdio transport，各列15工具且同時存活。另一個legacy operator lease被測試持有時仍可連線；mutation busy時receive回未開始，list及Stop可用。解除後兩client收同event/query，ACK及重播只1張來源回條；事件仍pending才ACK。另確認legacy bound第二owner仍exit3。三個child退出碼為0/0/3、reader均退出、remaining0、均未強停。這是**真Windows私有Job／SDK協定＋合成fixture**，不是模型接收證明。實際request/response與receipt保留`selected-001/lifecycle-evidence.json`。skip為一般身分無法建立symlink，未提權。

**本主聊天真工具另列。** deferred catalog在本輪新增正式`mcp__eventguard`的15工具，root實際呼叫capabilities／status／activity均isError=false。activity讀到本輪capabilities及overview完成紀錄；`main-chat-formal-tools.json`、`main-chat-formal-activity.json`保存實際回傳。當次status為background stopped／desired_enabled=false，既有pending保留；current_monitor無owner且舊heartbeat過期。本輪不接收或ACK這批正式事件，也不把歷史coverage當新掃描／安全證明。工具載入成功與本輪鎖修正同時發生，沒有足夠client內部證據證明修正是此次平台重載的唯一原因。

另外程式向既有批准的**隔離test佇列**只新增一件synthetic listener，producer不向對話提示event ID；root原生list取得ID，receive→inspect（pending）→再次receive→ACK→相同ACK重播→inspect（ack）。event ID=`evt-7beed3e4ebcd495e85b3f5af1bcb4118`，query ID=`query-ce7ca798f2e4e56542242496702d950199f5dce3`。生成／收到／查證／ACK集合各1且相同，missing=[]、duplicate_receipts=[]；兩次receive同query、兩次ACK只新增1張SQLite receipt，receiver_receipt_id與result_id相符，incident_conclusion保持not_assessed。manifest、七次完整原生回傳及核對結果留`reports/goal-center-001/native-*`。合成四工具與正式三次狀態操作分開，不宣稱正式backlog已處理。

完整回歸命令`py -3.13 -B scripts/verify.py --run-dir reports/goal-center-001/full-001 --timeout-seconds 600`，08:04:23.984453 UTC完成：**764執行、762通過、0failure/error、2symlink權限skip**，Python3.13.3、267.299秒，130 AST無誤、source_unchanged=true、per_test_residuals=[]，guardian自然exit0、remaining0、未強停。證據`full-001/verification-summary.json`、source-manifest、unit-tests與lifecycle-evidence。部分故障注入案例刻意需owned Job強制清理，這與guardian自然退出分開記錄，不冒充其child自然退出。

完整suite之後的唯讀複查發現更窄的回報競態：同namespace的Start已重存enabled=true、但尚未寫新launch時，run ID仍舊；Stop原可誤回stopped/desired_enabled=false。最後只改`src/eventguard/background.py`及`tests/test_background.py`，scoped檢查增加desired_enabled必為false；新測試涵蓋有／無舊owner，均不得誤報停止或追停。**最終版**命令`py -3.13 -B reports/goal-center-001/verify_stop_final.py`重驗operator_api/clients、stop_binding、background、core_cli、agent_access、operator_workflow；08:05:55.754491 UTC完成，Python3.13.3，**124/124通過**、0failure/error/skip，25.535秒、130 AST無誤，source_unchanged=true、per_test_residuals=[]，guardian自然exit0／remaining0／未強停。結果與全套不相加，不宣稱最後補修後重跑全套；來源差異及最終提交綁定留`source-commit.json`。

**待驗證。** 本輪是活動回合主動呼叫，不是閒置喚醒；沒有新真模型、OS重啟、排程安裝、24小時soak或Phase7實機注入。共享GUI表存在及MCP可讀不等於舊GUI視窗熱更新。文件檢查與最終commit/source對照留本機同一目錄；不把相關模組、純argv與歷史測試相加冒充全套。

前一則使用者要求的GitHub回饋另已完成：公開[issue #88](https://github.com/TED-H-com/ai-security-scanner/issues/88)附三份公開MD，upstream main基準be38e83eba90a39ca3167f5dd4da2da97598f805；另一項依SECURITY政策提交私人報告。API回讀逐文核對，證據只留`reports/upstream-feedback-001`；不在本儲存庫公開私人內容，不自動追蹤或另傳訊息。

## 2026-10-23：情報中心操作紀錄與採集輸出硬化

基底`befeed79d4ec8c5d5541ff473e11c5cf3b8af872`，同一feature；使用者明確批准EventGuard正式專案MCP，並定位為資安情報中心。新activity表記錄共享operator MCP與GUI操作意圖／結果，GUI新增操作紀錄頁籤，CLI可讀同表。最多256筆、32個running及2MiB，先保存再操作；暫停／撤回接收／停用自動agent不因記錄故障受阻。只存枚舉、時間、目標hash，不保存提示或原始例外。讀取重新驗證已存欄位，owner缺少完成回條不推定成功。新表是產品操作歷史，不是另一套事件投遞帳本，也不覆蓋聊天思考、任意shell／檔案活動或舊綁定CLI adapter。

GitHub盤點另採納兩項：合計stdout/stderr超4MiB即要求自有Job合作停止，逾時只清理該Job；JSON容器最多32層並拒絕解碼後重複key。標準庫獨立實作；沒有下載或執行上游25個引擎。測試含真Windows自有合成flood，刻意忽略EOF，因此其`forcibly_terminated=true`是預期安全清理證據，不是自然退出或實機採集成功。

本輪測試均使用Python **3.13.3**，fixture／合成SQLite／已安裝SDK／fake CLI／真Tk元件及標明的Windows自有Job API。**不啟動真Codex、不呼叫模型、不做Windows盤點、不啟用監看／排程**。以下紀錄不相加成另一個測試數：

| 命令（專案根目錄） | 實際結果與時間 UTC | 退出及限制 |
| --- | --- | --- |
| `py -3.13 -B scripts/verify.py --run-dir reports/intelligence-center-001/full-001 --timeout-seconds 600` | 06:10:10；741執行、737通過、2 error、2 skip；343.711秒 | exit1；新測試錯把顯示limit設大於縮小後容量、另有fixture SQLite未關閉，皆已修。guardian自然退出，殘留0 |
| `py -3.13 -B reports/intelligence-center-001/verify_selected.py` | 06:12:29；100/100通過；45.644秒 | exit0；activity/operator/desktop/GUI/hardening五模組，source_unchanged=true，殘留0 |
| `py -3.13 -B scripts/verify.py --run-dir reports/intelligence-center-001/full-002 --timeout-seconds 600` | 06:17:22；420執行、411通過、6 failure、1 error、2 skip；282.314秒 | exit1，因子程序殘留提早停止，**未完成全套**。四個dispatcher案例的短啟動時限失敗；stdio producer三秒communicate取消造成殘留，自有guardian最後強制清理，remaining0。原失敗與強停不改寫成成功 |
| `py -3.13 -B reports/intelligence-center-001/repair-check/verify_selected.py` | 06:20:58；66執行、64通過、2 error；86.793秒 | exit1；dispatcher修正通過，另兩個SDK initialize超過六秒，尚未進事件接收。guardian自然退出、殘留0 |
| `py -3.13 -B scripts/verify.py --run-dir reports/intelligence-center-001/full-003 --timeout-seconds 600` | 06:28:12；745執行、742通過、1 error、2 skip；385.602秒 | exit1；只剩operator stdio測試initialize在10秒無回應而Queue.Empty；source_unchanged=true、128 AST無誤、殘留0，guardian自然退出，未強停 |
| `py -3.13 -B reports/intelligence-center-001/final-review/verify_selected.py` | 06:31:09；130執行、129通過、1 error；126.045秒 | exit1；operator握手、GUI、activity與hardening通過；舊dispatcher測試假設三秒內已開始，但實際capture-skipped，讀不存在的退出回條而失敗。source_unchanged=true、殘留0、自然退出 |
| `py -3.13 -B reports/intelligence-center-001/dispatch-check/verify_selected.py` | 06:33:47；22/22通過，0 failure/error/skip；58.543秒 | exit0；完整dispatcher模組，含ready/release同步與回條竄改拒絕；source_unchanged=true、128 AST無誤、殘留0、guardian自然退出 |

dispatcher測試改以已觀察到waiting／binding後合作取消，保留外部失敗期限；stdio測試增加冷啟動握手期限，保留原事件等待／EOF停止時限，communicate逾時繼續收尾同一子程序、不重啟或遮掩原失敗。產品事件期限與模型預算沒有放寬。full-003後針對同樣的operator握手時限改為20秒。最後的dispatcher測試改成假CLI實際寫入ready後才推進**父測試**時鐘至期限；capture子程序維持真時鐘，之後由release檔合作釋放，仍核對未退出不能重開、原回條有效及竄改attempt ID後拒絕。兩項skip均為一般身分無法建立symlink，未提權繞過。

最終版所有變動模組均有上述通過案例；最後兩次補驗之間只改`tests/test_agent_dispatch.py`。**沒有將129與22相加宣稱新的全套結果，也沒有在最後修正後重跑完整suite**。README為95行，修改文件的本地連結檢查無缺漏，git diff --check通過；回條`document-check.json`及最終來源差異綁定見本機同一證據目錄。

正式MCP於2026-10-23T06:12:51.779831+00:00加入**專案**`.codex/config.toml`，原`eventguard_test`保留，新增`eventguard`的15個工具（含activity）。正常使用者、既有Python／SDK；未改全域config、登入、信任或安全設定。回條`reports/intelligence-center-001/project-mcp-install.json`記錄before/after SHA256、保留其他servers、monitor_started=false、model_started=false。設定本身被Git忽略，不能提交。安裝後本主對話工具清單仍只有合成四工具；子agent後來回報metadata見到正式namespace，**不能代替主對話實際呼叫證據**。目前仍未證明主對話正式status／activity接通，也未接通閒置同一聊天自動喚醒。

原始測試輸出、source-manifest、verification-summary、guardian-exit及每個測試的殘留檢查保留上述reports目錄。審查發現的路徑異常穿透Stop、已存欄位重新驗證、keyword停用等邊界分別修正與補驗；最終提交綁定留`reports/intelligence-center-001/source-commit.json`。不推送資料、憑證、私人歷史或既有docs/research。

## 2026-10-23：補齊日常operator操作介面

基底7865f9b267213f8d2187f101ed9f87ecb05afdac。盤點確認operator MCP程式原有13工具，但當前聊天僅載入批准的合成四工具。新增start_monitor直接轉接OperatorAPI.background_start，原有stop已經支援背景耐久暫停，未另建控制器或佇列。start_monitor沒有自由參數；test launcher固定拒絕，live需原launcher opt-in與每次人類存取開關；不建立排程、不開自動模型。原背景owner／Job限制照常，blocked不當成啟動成功。另修正capabilities的gui=false舊宣告。

命令 `py -3.13 -B reports/operator-full-001/verify_selected.py`；Python3.13.3，2026-10-23T05:58:21.738884+00:00，operator_api／core_cli／agent_access／operator_workflow四模組 **75/75通過、0 error/failure/skip、124 AST**，31.59秒、exit0。source_unchanged=true、per_test_residuals=[]；guardian自然exit0、remaining_owned_processes=0、forcibly_terminated=false。新增測試驗證test不能啟動live、權限撤回即拒絕、參數不可加shell／namespace／自動agent，以及對原核心的映射。start_monitor本次使用mock背景核心，未啟動正式Windows採集；既有SDK／stdio測試也不是目前聊天已載入14工具的證據。

完整14工具的review設定與connection-plan保存在reports/operator-full-001，scope為本專案live，註冊本身不開始監看或模型。現行專案MCP設定未改，已向人類請求由原「合成四工具」擴為正式操作範圍；批准前不接正式資料。正常操作介面可用與「閒置同一對話會被事件喚醒」分開，後者仍未驗證。此次未推送、安裝、提權、修改安全政策或啟動額外agent。

## 2026-10-23：澄清同一對話接收，活動回合再次實測

使用者說「你一個就好了」，因此沒有把回覆解讀成今日CLI用量數，也沒有初始化預算或啟動另一個agent。基底5211e654ceea4d30621f8d80f656b587688bc10b。先直接呼叫本對話原生eventguard_test/list_events，確認原有兩件皆ACK；再用Python標準庫向已批准的隔離operator/test佇列加入一件新coverage合成事件，producer不輸出event ID給對話。主agent隨後原生list_events取得pending ID，receive_event得到query ID，inspect_event證明仍pending，再ACK同event/query。原始四個MCP回傳留reports/chat-receive-002/native-calls.json，程式manifest與validation同目錄。

接收時間2026-10-23 **13:52:37.268 UTC+08**，ACK **13:52:46.312**。本機只讀SQLite與實際回傳核對命令exit0，validation.passed=true：生成／接收／查證／ACK集合各1且相同，missing=[]、duplicate_receipts=[]，該事件只有1張匹配result_id回條。這個接收者就是目前主對話，不是fake、SDK代收或另一個CLI；額外CLI任務0、原生採集0。沒有改MCP／登入／預算／正式資料。

限制仍明確：這是已在處理使用者回合時主動呼叫工具，idle_chat_wakeup_verified=false。現有工具清單提供agent發起的MCP與聊天操作，尚無已接通、可供本機producer在本對話閒置時投遞並喚醒的入口；不能以定時模型polling或專用CLI冒充。前批CLI功能保留未啟用，後續優先核對同一對話的事件觸發能力。

## 2026-10-23：持續事件待命、GUI自動開關與接線文件

基底 `72673a3657b6e30c9c594dcc6140ddd6f147b096`，同一feature。兩個子agent分工dispatcher與GUI，第三個唯讀審查；主agent整合後統一驗證。`agent_dispatch.run(continuous=True)`／CLI `watch`不受一小時host壽命或五個總任務限制；五次是固定每日預算，max_seconds是每次CLI期限。空佇列純Python等待，無attempt／reserve／模型；日額用完等待，投遞失敗不自動重試。審查抓到reserve-only拒絕可能每次poll建立空目錄，已以同event拒絕latch修正，新增針對性測試。

GUI新增獨立「自動交給專用agent」及原生exe選擇，與接收權限分開；原子保存本機opt-in，讀視窗不啟動，明確Start才沿用，Pause取消並核對子樹退出。未開啟正式auto、操作正式backlog、重啟既有GUI／監看或建立排程。MCP接線與設定範本落於 [CONNECT_AGENT](CONNECT_AGENT.md)；更正LIVE_CHANNEL舊的CODEX_HOME覆寫範例，保持正常既有登入。單次CLI明示停用本project的eventguard_test，避免聊天測試佇列混入；不聲稱已隔離所有平台內建工具。

**完整執行**：`py -3.13 -B scripts/verify.py --run-dir reports/idle-wake-unit-001 --timeout-seconds 600`，Python **3.13.3**，報告時間2026-10-23T05:21:39.719564+00:00，**716執行、713通過、1 error、2 skip**，198.792秒、exit **1**，124個Python檔AST無誤。error為新增test_watch_receives_after_idle_then_remains_waiting_until_cooperative_stop重複傳max_tasks，TypeError發生於進入產品run之前；兩個skip均是此身分不能建立symlink。source_unchanged=true、per_test_residuals=[]，guardian自然exit1、child_exited=true、remaining0、無強停。原報告與完整trace保留，不改寫成成功。

**修正與重驗**：只移除上述測試多餘參數，產品程式不變。`py -3.13 -B reports/idle-wake-unit-002/verify_selected.py`，重用verify.worker／私有Job，選整個test_agent_dispatch模組；2026-10-23T05:22:53.791457+00:00，**22/22通過、0 error/failure/skip**、36.886秒、exit **0**。source_unchanged=true、124 AST、per_test_residuals=[]，guardian自然exit0、child_exited=true、remaining0、無強停。兩批數字不相加，不宣稱修正後再次全套；最終source與兩批manifest差異見本機source-commit回條。這些包括fixture／合成SQLite／fake CLI、真Tk元件與明示Windows私有Job測試，沒有原生盤點或真模型。

**真自動驗收尚受阻**：本輪使用者已批准公開合成事件自動驗收；既有原生CLI和正常登入可用，但固定`data/agent-budget`尚未初始化。命令 `py -3.13 -B reports/idle-wake-proof.py --codex-executable <既有原生codex.exe> --count 2 --execute` 前置檢查回 `fixed_daily_budget_required`／`budget_unavailable`，工具exit **1**，未建立事件、attempt或模型程序；原始回傳留 `reports/idle-wake-preflight-001.json`。已詢問今日台北時間已啟動專用CLI數，不能在未回答時當成0。helper已準備先空閒、程式產生事件、實際三工具及同ID ACK、再空閒／第二事件、合作停止／驗證回條，但尚未執行通過。生成／接收／ACK各0；沒有缺漏或重複結論可下，不能把前批手動MCP成功當自動喚醒成功。

未查原Codex sessions或憑證，未改登入、全域MCP、安全設定、系統服務或排程。執行證據留本機忽略目錄；文件與原始碼集中本地提交，不推送。重開機、真自動agent與24小時soak仍各自未驗證。

## 2026-10-23：主對話原生MCP實際接收通過

基底 `42b495a2d8b4f6bbd54f34b735f64dd178855ebb`。使用者提供實際/mcp畫面確認當時沒有EventGuard。本回合核對發現預設命令環境屬隔離帳戶，與正常登入身分不同；前次CLI查不到server不能推導桌面project設定未載入。只讀查得安裝套件OpenAI.Codex 26.1016.8622.0、原生CLI 0.163.0-alpha.11.2；未變更帳戶、trust、全域MCP、安全設定或重啟應用。之後平台將eventguard_test四工具加入**本主對話**，實際呼叫成功；不能據此把環境檢查或版本查詢宣稱為已證明的修復原因，先前載入延遲的精確根因仍未定案。

主agent實際呼叫原生 `list_events(limit=10)`，從回傳的pending清單才取得新合成事件ID；依序 `receive_event`、`inspect_event`、再次 `receive_event`、`ack_event`、相同 `ack_event`重播、最後 `inspect_event`。七個真MCP request參數／原始回傳保存 `reports/chat-receive-001/native-root-calls.json`；不是SDK或Python API模擬回傳。收到的是先前程式生成並等待接線的coverage合成事件：來源拒讀、未知不能當安全，沒有執行實機查詢。首次接收時間2026-10-23 **13:06:33.984 UTC+8**，ACK時間**13:06:55.985 UTC+8**；這段含接線等候，不是偵測延遲基準。

命令 `py -3.13 -B reports/chat-receive-001/verify_native_receipt.py` exit **0**，`native-receipt-validation.json`：生成／唯一接收／查證／ACK集合各1且完全相同，missing=[]、duplicate_receipts=[]；兩次receive同event/query，ACK前inspect仍pending，ACK後為ack。兩次相同ACK只保留該事件**1張SQLite回條**，重播ack_replay_verified=true／new_receipt_created=false；與實際result_id匹配。資料庫另含前批命令工具事件的1張回條，總2張，分開計數。驗證helper初次把原始manifest直接hash，未先套入庫schema正規化而斷言失敗；依既有EventStore.validate_event契約修正helper後通過，未修改產品或重做投遞。

本次證明**目前主agent能用原生工具接收合成事件**。沒有啟動額外Codex CLI模型、接收正式事件、重掃、部署或自動喚醒測試。ACK只表示收到，incident_conclusion仍not_assessed；工具內的real_agent_woken=false欄位保留原值，因其沒有喚醒證據，不能將人工發起回合偷換成閒置喚醒。已批准的MCP連線由Codex持續管理，非宣稱已退出的一次性測試worker；先前失敗回傳仍保留。

## 2026-10-23：原生MCP先前受阻的紀錄

使用者表示找不到eventguard_test／MCP設定。新子agent的工具metadata一度列出四個eventguard_test工具，實際呼叫原生 `mcp__eventguard_test__list_events`（limit=10）卻回 `isError=true`、`MCP tool eventguard_test/list_events is not available to the model`，隨後namespace被移除。原始回傳、時間與未receive／未ACK事實保存於 `reports/chat-receive-001/native-receipt-stage1.json`（2026-10-23 13:00:44 UTC+8）。這是原生工具呼叫失敗，不能用metadata出現、SDK或前批命令工具成功替代。保留待測合成事件，不盲目重試。

唯讀執行既有原生Codex的 `--version`：`codex-cli 0.163.0-alpha.11.2`、exit0；`mcp get eventguard_test --json`：`No MCP server named 'eventguard_test' found`、exit1。此CLI管理命令查user-level MCP entries，不能據此斷言專案設定未載入；專案檔仍存在並正確列四工具，沒有修改全域設定或信任政策。官方文件說明project設定僅trusted時載入，且子agent繼承父層MCP，但本輪沒有足夠證據判定具體根因。

先前直接指示Settings→MCP servers→Restart來自[官方MCP文件](https://learn.chatgpt.com/docs/extend/mcp)，未驗證使用者當前UI，現撤回「必定有此入口」的假設。[官方Developer commands](https://learn.chatgpt.com/docs/developer-commands)另提供/mcp檢視當前工具；下一步需用戶端實際狀態或介面證據。沒有提權、改安全設定、讀憑證、啟動模型CLI、重掃主機、強停或ACK。此批只改文件，檢查相對連結與diff，不重跑產品測試。

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


## 2026-10-24：無模型 MCP／GUI 同一 Application 閉環

分支 `feat/local-codex-acceptance`，基底 `d23c7d3ed2561fb8c855dffa342862ffa0fdb832`。交付 commit 另由本批 `source-commit.json` 綁定。未推送。
Windows 一般使用者，Python 3.13.3；既有 MCP 1.6.0、uvicorn 0.34.2、Starlette 0.46.2、sse-starlette 2.3.3。沒有下載或模型任務。
本機原始證據：忽略的 `reports/application-mcp-001`。核心仍標準庫；SDK 選配載入。

### 本批測試數單一來源

| 證據 | 命令／範圍 | 實際結果 |
| --- | --- | --- |
| verify-001 | 八個相關模組；420 秒期限 | SDK 連線未完成，無 worker summary。native exit 1460、forcibly_terminated=true、殘留 0。失敗，不算通過 |
| verify-002 | 只跑 test_application_mcp；90 秒期限 | 12 run、11 pass、1 error，26.847 秒。期限與 phase 記錄定位 connect 未得 endpoint；自然 exit 1、無 force／殘留 |
| verify-003 | 七個相關模組；240 秒期限 | 70 run、66 pass、3 errors、1 notification skip，68.284 秒。兩個 mock lease／清理錯誤，一個 stdin-open 退出逾時；自然 exit 1、無 force／殘留 |
| verify-004 | 下列十四模組；240 秒期限 | 181 run、180 pass、0 failure/error、1 notification skip；109.281 秒，2026-10-24 11:25:26 UTC+08。source_unchanged=true、native exit 0、無 force／殘留 |
| verify-005 | 新增真雙 client 案例後，只跑 test_application_stdio；120 秒期限 | 4/4 pass；18.744 秒，2026-10-24 11:33:34 UTC+08。source_unchanged=true、native exit 0、無 force／殘留 |

兩個成功範圍不相加。verify-005 只變更已驗模組的測試，產品來源與 verify-004 相同。
通知 skip 是 `notification_icon_unavailable`，不代表已看見通知。原始失敗完整保留。

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/application-mcp-001/verify-004 --timeout-seconds 240 --module test_application_controls --module test_application_mcp --module test_application_host --module test_application_stdio --module test_application_stdio_transport --module test_application_rpc --module test_application_ui_state --module test_monitor_web_controls --module test_local_product --module test_operator_clients --module test_core_cli --module test_cli_workflow --module test_operator_api --module test_operator_monitor_owner
py -3.13 -B scripts/verify.py --run-dir reports/application-mcp-001/verify-005 --timeout-seconds 120 --module test_application_stdio
```

範圍為 fixture、SQLite、真已安裝 SDK SSE／stdio、Windows 自有 Job／loopback；部分故障注入是 mock，不是主機資安採集。
真雙 client 以有界 timing barrier 控制進入時刻，保留正式 Application 與原生 spawn。第二端三個並行要求回 busy；release 後只有一個真 fixture host。跨 client replay 不增 child，pending 不 ACK。協定、時序及自然退出回條見 verify-005/lifecycle-evidence.json。
真 SSE 連續兩 server、同 server 重連、foreign Event、Host／Origin／token／body 邊界及未知回條亦有覆蓋。

### 修正與可見 GUI

Application 是唯一 owner；Web／MCP 共用 instance、namespace、控制鎖、revision 及 EventCatalog。stop 只停止採集；shutdown 才關閉應用。人工處置不等於 ACK。
SSE 依賴的程序全域退出 Event 不能跨 worker loop 沿用。現在只建立與清理自身 Event，並以 transport lease 防跨 loop 並行；外來 Event 明示阻擋。未修改 site-packages。
SDK stdin worker 在管線仍開時不可取消。Windows transport 改為 PeekNamedPipe、有界讀取及合作退出，不關閉其他 handle 或程序。
另補合成資料標示、詳情輪詢與亂序保護；暫時 health 讀取失敗不再誤稱規則損壞。

exercise.py 使用真 CLI main、隔離 root 與私有 Job。普通 Python 使用真 SDK；瀏覽器由 CUA 操作，沒有人工刷新。
ui-validation.json 核對雙向控制、篩選、已讀／已處理、同 ID、replay、受阻、重連、頁面自動接重啟實例、pending 與退出。
原注入 `evt-d466938628854b3e827437de8f6335f3` 跨重啟仍 handled＋pending；最後 5 pending 是一個注入加四個 monitor_gap，ACK／receipt 均 0。兩個可見應用自然 exit 0、無 force／殘留。
該輪包含中途修正，不能整輪稱最終 source。另以 final-visible 窄驗最終產品：真 MCP 壞規則受阻、修復後開始、暫停、恢復、停止與 GUI shutdown。source-match.json 核對最終產品；應用自然 exit 0、無 force／殘留。
最終實例 `8463727e86cf4ea89a8ffcb9dccd5ef1`；注入 `evt-de7eb9c1c44043cba144023b3e1eb2da` 留 pending，沒有 ACK。

08-failed.jpg 與停止圖 hash 相同，不能作新失敗色彩證據；原檔保留並標記。
補正 final-visible/failed-fresh.jpg 經 CUA getScreenshot 顯示真紅邊／失敗文字／MCP 來源；running-fresh.jpg 是真綠色畫面，均另存。
16 狀態映射及 7 亂序向量以 Node VM 執行實際 served JS prefix，全部符合；不是瀏覽器網路亂序注入。該 prefix 與最終產品相同。

### 專用入口與原生工具

既有原生 codex.exe 執行 `mcp add eventguard-app -- <既有 Python 3.13> -B <scripts/eventguard.py> mcp --allow-live`。
一般使用者 mcp get 查回 stdio／enabled=true，保存 host-registration-normal-user.json。sandbox 視圖曾查不到，錯誤與空輸出保留；未改 CODEX_HOME 或認證。
`py -3.13 -B reports/application-mcp-001/registered_entry_probe.py` 使用註冊的完整原生命令及私有 Job，完成 initialize、九工具清單、capabilities／status；GET GUI /api/status 核對同一 live instance。只讀操作 metadata，不開正式事件頁、不讀事件、不採集。child exit 0、無 force／殘留，停止設定 hash 與 budget presence 不變。
證據 registered-entry-protocol.json／registered-entry-exit.json。這是 MCP client 連線，不是模型喚醒。

較早 current-chat-catalog.json 顯示新入口未載入。稍後工具系統自動加入九工具，本 session 原生呼叫 capabilities／status 成功，另存 current-chat-native-proof.json，不覆寫舊觀察。
同一正式 instance `a3b57a57573849249ec9c7196ae3c1ad`，namespace live，stopped、revision 0、last_action=null、model_calls=0，網址 http://127.0.0.1:53573。
未要求使用者重啟。這次自動載入不保證所有客戶端都如此，也不是閒置聊天喚醒。

測試應用／採集／入口探測均合作退出；正式 MCP 控制介面由 Codex client 保留閒置，供九工具使用，並非測試殘留或 agent host。正式停止設定不變；沒有預算初始化、模型、正式長期監看、服務、排程、自啟、proxy、新登入或安全設定變更。沒有七來源重掃、24 小時、重開機或真模型驗收。執行資料、附件及研究未提交。
