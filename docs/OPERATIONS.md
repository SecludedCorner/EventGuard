# EventGuard 操作與故障排除

從專案根目錄使用既有 `C:\Python313\python.exe -B scripts/eventguard.py`。不需安裝依賴、管理員或執行政策變更。本版沒有GUI；命令的實際子命令／能力以 `--help`、`capabilities` 及本版STATUS為準。

## 首次使用

先讀README／AGENTS／STATUS，確認本次主機與唯讀範圍。先執行capabilities與status，不以測試之名反覆全機掃描。正式receiver尚未接通時維持disabled；不新增webhook／金鑰或模型程序。

優先用README的synthetic流程：emit → playbook validate／simulate → deliver mock → mock process → report export。每一步記錄同一event_id、receipt、mockcase結果；mock_closed不是實機agent結案。不要為測試開真埠、關防毒或修改啟動項。

## 開始、停止與狀態

`monitor` 是使用者明確啟動的前景長期程序；它持續做本機低頻規則檢查，不呼叫模型。`--max-cycles N` 用於有界運行；`--fixture path` 使用合成快照而非實機採集。fixtures須以本版實際檔案與格式為準，不能把任意檔案當指令。

同專案另一終端的`stop`提出合作式停止；不taskkill。停止排新工作後，已開始的唯讀操作自然結束。`status`應分開本機監看、資料新鮮度、coverage、事件佇列與接收端；歷史heartbeat不保證程序仍活著，也不是主機安全狀態。停止後查事件是否pending／retry、mock是否仍未處理，不自動刪資料。

真實監看寫data/live；`monitor --fixture tests/fixtures/normal.json --max-cycles 1`寫data/test且不採集系統。`synthetic emit`、`deliver --adapter mock`及`mock process`強制test。查看合成事件與報告時明確用`events list --namespace test`、`playbook simulate --namespace test --event-id EVENT_ID`、`report export --namespace test`；不能把合成驗收當真實主機狀態。

未批准持久啟動時，登出／重啟後需使用者重新啟動。不得因希望自動恢復就自行建立服務、排程、自啟或watchdog。

## 按需診斷

只用capabilities列出的操作與型別化args。先查事件涉及的單一來源／埠／程序實例，不先跑全機。程序身分使用PID與建立時間，防止重用；資料過期時重新確認，不對新的PID套用舊結論。查詢限15秒、列數上限與資料最小化由工具驗證，拒絕任意shell／未知欄位。

對`partial / denied / unknown / not_applicable / error / timeout`分別說明，不能把空結果當安全。歷史inactive防毒訊號缺日期／處置結果時，只保留背景與缺口，不猜active infection或清除。

## 常見故障

| 現象 | 先查什麼 | 安全處理 |
| --- | --- | --- |
| 沒有事件 | 來源時間、基線、規則filter、coverage | 正常可能零事件；不可僅因此說安全，不用頻繁模型輪詢 |
| coverage降級 | 固定錯誤碼、來源權限、最後成功時間 | 保留未知；不提權繞過，不修改系統設定 |
| pending累積 | adapter是否disabled、receiver是否真已選定 | disabled是未接通，不是假故障；不要把mock接收當正式送達 |
| retry／failed | 嘗試數、lease、ACK與目的路由 | 不確定先查收據；同event_id續送，不盲目新增事件 |
| 佇列／磁碟滿 | 容量、已ACK／failed保留、實際寫入錯誤 | 不靜默刪pending；降級／背壓；清理與刪除需授權 |
| 診斷不符合程序 | PID與建立時間是否一致 | 標stale／unknown，不對另一程序處置 |
| playbook衝突／缺規則 | rule_id／version、節點、filter、allowed_actions | 安全採證後提問；規則不是授權，沒有允許動作就不處置 |
| 程序全部停止 | 本機無法自我報告 | 不假裝已有獨立watchdog或遠端已收到 |
| 遠端連線但UAC不可見 | 當前桌面與安全桌面能力 | connected非可操作；不關閉UAC／不繞過／不恢復暫停修補 |

## 維護與移除

規則修改先驗證與dry-run；版本、變更理由及回復點都要保存。宣告式畫布是後續可選層，不改變runtime批准檢查。更新程式前先停止本工具排程並保留執行資料；不要與正在更新的程式衝突。

移除前呈現未送事件及未完成案件，使用者決定保留／匯出；本版不自動刪資料。不曾建立服務／排程／自啟時，不能宣稱已卸載那些項目。不要動舊MVP或既有閱讀入口。

## 驗證紀錄

本版測試以mock／fixture／安全合成event優先，測試結束停止自己的監看程序。整合者把實際命令、時間、成功／失敗數、輸出檔與限制寫到STATUS。長時CPU／RAM／I/O／電池數字要量測，不能因單元測試通過就宣稱達標；正式agent E2E未接通則維持blocked。
