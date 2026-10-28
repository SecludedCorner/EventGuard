# EventGuard 目前目標

## 2026-10-28 競品 GUI 研究已落地，工程準備完成

本輪明確範圍為研究／文件／準備，沒有產品實作。公開來源、固定 GitHub SHA、授權與封存見 [研究](research/competitor-gui/README.md)，現況證據、每項依賴／風險／授權及驗收見 [規格](research/competitor-gui/ENGINEERING_PLAN.md)。它們是本佇列附件，不另建管理系統。

| 順序 | 工作與狀態 | 下一個具體動作 |
| --- | --- | --- |
| 1 | P1-GUI-001 DONE（synthetic 瀏覽器與定向） | Web 七來源卡片補 last_success_at/state 與 freshness；只沿用 source_status 1.0，完成六情境合成／真瀏覽器驗收。 |
| 2–3 | P1-GUI-002A/B 已實作（合成瀏覽器已驗）；003 PLANNED | 來源缺口摘要、可點的新增高嚴重度提示；再做篩選／頁碼及返回焦點保存，按規格拆 A/B。 |
| 4–6 | P1-INVEST-004、P2-HISTORY-001、P2-INVEST-REV-001 PLANNED | 已保存調查易讀化 → 有界處置歷史 → 有界案件修訂；不新增推論攻擊鏈或敏感回應。 |
| 7 | P2-UX-001 PLANNED | 在以上切片後做合成任務可用性驗收；跨產品比較待合法帳戶／可比資料及另行授權。 |

P1-GUI-001 已將 API 最後成功／新鮮度接到七來源卡片；驗收與限制見 STATUS／EVIDENCE。下一步 P1-GUI-002A。原生 coverage／偵測率／GUI 體驗／真環境可靠性分開量測，不宣稱超越兩家 EDR。
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
