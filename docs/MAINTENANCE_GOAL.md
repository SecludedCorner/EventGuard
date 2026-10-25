# EventGuard 目前目標

## 持續工程工作佇列：2026-10-25 23:26 接續（優先閱讀）

目前專案 EventGuard；主 checkout 分支 feat/local-codex-acceptance，基底 a34e466。既有真 CLI 收件鏈、1477 項回歸及政策更新沿用，不重做。最新人類要求持續實作整個專案；先前單次收件目標達成是基準，不代表以下可執行可靠性工作已完成。只使用本專案、一般權限與既有 Python/SDK；推送／系統變更／實機來源採集仍守既有授權。

| ID／優先級 | 預期成果與驗收 | 依賴／環境／權限 | 目前證據與未驗範圍 | 下一個可執行動作 |
| --- | --- | --- | --- | --- |
| P2-MCP-EXIT-001（DONE） | 成功 ACK 回應真正 flush 後 MCP 自然退出；活體綁定 query HANDLE，PID＋creation＋本次 CLI Job 相符，OS exit 0；未知不得升格 | Windows、已安裝 SDK、既有單事件 CLI 授權；不新增 transport 或 PID 終止 | 真04五層exit0／三工具各1、pending0，strict原始證據重驗及活體query HANDLE通過；43.44秒 | 後續變更受影響才複驗；保留舊缺證據不升格 |
| P1-SOAK-001（DONE：有限範圍） | synthetic 滿載拒絕保留 ID/hash、同 ID 恢復、completion 故障 pin 保護、重建 consumer 同 query、唯一 ACK 與集合守恆；原 Job 回條 | 新 reports、標準庫、私有 Job；模型／原生掃描／網路 0 | SQLite close修復後3/3；真跑有限harness 64唯一ACK/pending0，81.88秒；60秒到期失敗另留 | 接續guard異常收尾與wall-time/資源採樣，不冒充24h/OS重啟 |
| P2-GH-PAGES-001（待實作） | GitHub 公開來源有界分頁；固定頁數/bytes/deadline，同 origin/path，拒循環／惡意 Link，partial/304 不洗完整 | 現有公告來源程式；先 fixture，外部抓取仍依來源與既有授權 | 現遇 rel=next 回 pagination_required，尚未整合分頁 | 上述切片驗收後，直接實作 source paginator 與對抗 fixtures |
| P2-SOAK-MEASURE-001（待實作） | 有界 wall-time profile 與本工具程序資源採樣；記實際耗時、容量、query/ACK 守恆 | 依賴有限 harness；只觀測自有 HANDLE/Job，不盤點全機 | 新 harness 的 duration 是工作上限、可提早結束；未量測 CPU/RAM/handle | 初版有限流程通過後加 pacing/採樣，不改舊證據時長 |
| P2-OS-001（BLOCKED） | 固定單來源／上下文的真 Windows coverage 與必要互動驗證 | 需具體來源、時限、回復範圍授權；不提權／不改防護或網路 | 現有 denied/unknown 不能視安全；不自動全機重掃 | 保存現有 WINDOWS_VALIDATION_PLAN/COVERAGE_PLAN，待範圍確定再執行 |
| P3-24H／DESKTOP／PUBLISH（暫緩或受外部條件限制） | 真跨午夜 24h、既有桌面喚醒、正式發布分別驗收 | 長時環境、受支援入口、發布明確批准；不可用短測代替 | 都未因本輪單測或 CLI ACK 自動完成 | 不阻擋上述可執行工程；只在必要條件具備時納入 |

P1-SOAK-GUARD-002（下一項）：驗證guardian在spawn後任一異常先寫合作stop，再有限grace/自有Job收尾；保留原資料/退出狀態。現main的異常finally尚未單獨證明此順序，下一步故障注入後修正。

每個切片實作→必要驗證→保存/提交後自動選下一項。局部失敗只阻擋相應項目，不以 checkpoint、文件或 commit 作停止條件。原117項首輪116過1error保留，soak close修復後3/3；真04與soak-finite-02的原始回條/守恆證據已完成。詳見最新STATUS/EVIDENCE。

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
