# EventGuard 維護目標

更新：2026-10-23；目標建立基底`bf99496cf3d73601fc2d8a1bf50c1c2fe8709b66`，程式基底`645d8d9`。依使用者「建立目標，繼續完成」已建立持續目標，狀態active、未設token預算。方向是**本機資安情報中心**：人類與agent經EventGuard取得觀察、理解事件、執行允許的操作，並在產品內看到正在做什麼及結果。沿用feature與資料，不reset/clean；既有研究與附件保留。

## 本輪完成與驗證

最新人類優先序：本機資安監測→事件／觀察耐久保存→人類或agent分析與可選接收。收斂旁支，不把proxy、登入排程或閒置聊天喚醒作為此流程的前置。主聊天已完成真實七來源及一件本輪真事件的讀取／查證／接收；本輪再修資料品質與規則誤判，見EVIDENCE。

最新續行修復長期故障恢復：慢來源不再餓死其餘採集；ACK原proof保護到接收器完成耐久收尾；overview去除相同錯誤樣本重複。先以fixture重現、實作後統測，不新增採集面、agent層或模型；詳見runtime-reliability證據批次。

本主聊天另以程式產生的合成事件驗單件／連續／batch、active inbox滿載及ACK前補收。真工具回傳、pending、同query、唯一回條及原設定復原皆通過獨立比對；詳見chat-delivery-003。產品source未變，不重跑前批全套、不藉驗收另啟模型。這補齊活動回合通路證據，仍保留下面長時／閒置／OS登入條件，沒有以局部成功宣告整個目標完成。

本批實際驗正式Start，發現舊MCP錯走independent契約而被外部Job拒絕，未建立child；Stop已恢復原Pause。已改接現有application-owned核心，補多client換代／EOF只清自身Job與耐久退出回條，不啟動模型。當前聊天一次capabilities仍是舊server，需client正常重新載入後再驗Start；不把SDK fixture成功或前批全套升格成主聊天已更新。這是本輪可用性修補，不以proxy／排程作前提。

- 沿用七來源、耐久事件、事件綁定查證與報告；不新增另一套控制器或事件佇列。
- 正式MCP已在本主聊天載入15工具，實際呼叫capabilities／status／activity；前批只驗capabilities／status／activity；本輪另接收與ACK一件本輪新生真事件，未接管其餘backlog。GUI操作紀錄與工具共用同表，實際工具可讀到本輪操作；既有視窗是否已載入新版頁籤仍不推定。
- 隔離合成入口由本主聊天實際list→receive→inspect→補收→ACK→重播ACK；核對SQLite只新增一張回條，保留ACK前pending證據。
- 修正operator終身單連線鎖造成的啟動exit3：多client可同時連接，mutation採短期鎖，讀取及Stop不被該鎖阻擋。scope與原owner/run綁定，停止不追隨新owner；legacy單事件adapter維持exclusive owner。
- 單事件CLI argv明確停用已知eventguard／eventguard_test，保留自身事件綁定入口。這是離線argv證據，不是本輪真CLI隔離驗收。
- 既有GitHub研究回饋已建立公開issue與依上游政策分流的私人報告；不另啟動外部掃描器。
- 功能集中驗證後本地提交；具體命令、失敗、修正與通過範圍以 [EVIDENCE](EVIDENCE.md) 為唯一測試數來源。

## 下一步與完成門檻

正常監看由程式等待，不因模型額度停止。人類能獨立操作；agent只使用相同的型別化能力，不能給自己開權限。操作紀錄不收集聊天思考、任意shell／檔案操作或私人原文；它也不是抗同使用者竄改的安全稽核帳本。

1. 保持正式工具可用、跨client補收／冪等ACK與人類操作相容；本輪測試及提交綁定見EVIDENCE。
2. **閒置時自動喚醒同一聊天仍未接通**。需能由事件觸發目前client的指定聊天入口，並有明確模型授權，才做「先閒置→程式入列→本聊天工具接收」驗收；不得以另一個CLI或定時模型輪詢代替。MCP註冊與本輪活動回合接收不能達成此門檻。
3. 長期監看與重開機恢復：現有GUI／supervisor及耐久暫停保留；登入排程仍未批准，程式變更後舊審查digest失效。建立前須產生當版dry-run計畫；實際登入／OS重啟與24小時soak另外核實。
4. 外部漏洞情報匯入、跨主機整合及Phase7真狀態注入尚未驗證，不藉本輪擴增功能面。

先前[喚醒／恢復研究](WAKE_RECOVERY_GATES.md)保留歷史，不再是本輪前置或待追問事項。metadata probe後獲批准，但helper收尾失敗、沒有連線結論；排程未批准、不建立，舊plan已失效。若未來人類另要求閒置喚醒／OS登入恢復，仍須以真正相符的證據驗收；不把本輪工具讀取升格成這些能力。

一般權限唯讀、不UAC／提權、不安裝下載、不改安全設定／執行政策、不動非本工具程序。MCP批准不包含真模型、排程建立、系統修補或自動處置；這些仍需具體批准。runtime、憑證與私人歷史不提交或上傳。
