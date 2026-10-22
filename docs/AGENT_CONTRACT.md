# EventGuard 事件與接線契約

**正式agent接收端未指定／未接通。** 本版只提供明確adapter界線與安全本機mock；沒有外部webhook、憑證、模型API或自動CLI模型。不能宣稱已喚醒真正Codex／dot，也不能假設任意任務都有webhook或永久等待能力。

## 狀態不可混淆

| 狀態 | 代表什麼 | 不能代表什麼 |
| --- | --- | --- |
| persisted | 本機event耐久落盤 | 已送出／已喚醒 |
| transmitted | 一次傳輸嘗試 | 接收端已保存 |
| receiver_accepted | 接收端已驗證並耐久接收 | agent已開始 |
| ack／acked | 已取得對應event_id的可信耐久回執 | 已診斷／處置／結案 |
| agent_started | 真實平台開始／恢復指定任務，有run_id | 已完成調查 |
| agent_processed | 本次事件工作結果已保存 | 主機安全／一定已處置／案件已結 |
| case_closed | 案件符合明確結案條件 | 整台主機安全 |
| mock_processed／mock_closed | 本機合成契約的診斷／結案 | 真實agent_started或處置 |

本版mock只接受synthetic=true事件；real_agent_woken必須為false。正式事件不能用mock變成已喚醒或已處理。

## 事件與回執

事件schema 2.0保留event_id、host_id、episode_id、correlation_id、sequence、event_type、detector／rule版本、transition、severity、synthetic、觀測與持久時間、window、baseline_version、evidence、inference、coverage、privacy、evidence_refs。欄位需白名單／限長，單事件上限8KiB；不得包含秘密、完整命令列、事件Message/XML、原始例外或私人內容。路徑遮罩使用者目錄。

同一轉態固定event_id，升級／恢復建立新event_id但同episode；重試另記嘗試與lease，不改事件身分。規則與event裡的rule_ref只是調查參考，不是權限。receiver與agent都需冪等；副作用另用action_id與查證，避免事件重送重複處置。

正式ACK必須來自經驗證receiver，包含相符event_id、耐久接收語義`ack_type=receiver_persisted`及receipt_id／receiver_receipt_id。HTTP成功、檔案生成、CLI啟動或聊天文字不是ACK。ACK不等待調查；實際ACK與agent_started到達順序可以交錯。無可信ACK時仍是未確認交付。

採至少一次投遞語義與冪等，不承諾exactly-once或無條件最終送達。離線／暫時故障退避重試，最多8次後failed；failed不代表已送達。接收端恢復且持久資料仍在，經查證的續送才能繼續。超過receiver去重保留窗口的自動或人工續送須先核對收據／案件，不能當新事件重做處置。

## 本版adapter

- `DisabledAdapter.connected=False`：沒有接收端，不送出、不增加嘗試、不假ACK。
- `MockReceiverAdapter`：只在本機SQLite耐久接收合成事件、去重並回mock receiver ACK。`process_mock`只跑合成診斷callback、保存mock案件，不執行系統動作或模型。
- 正式adapter：尚未實作／啟用。需使用者選定平台與目的地後驗證，不自行補外部服務。

## 正式接線前置契約

1. 指定可信receiver、擁有者、主機與task_ref，批准可傳metadata與目的地；本機可讀不等於可傳給外部模型。
2. 驗證平台對該任務的事件接收、真正等待不推理、喚醒／恢復、任務TTL與實際run_id；缺能力就blocked，不以AI定時輪詢替代。
3. 定義身分／傳輸保護、schema協商、冪等保留、ACK查詢、路由故障、限流及agent離線的wake_pending恢復。
4. 讓agent可在批准範圍使用本版capabilities列出的診斷CLI或未來受支援橋接；不能假設跨機可以直接讀Windows路徑。
5. 先批准受控合成測試路由，驗證同event_id到receiver ACK、真實task/run_id、按需診斷、結果回執及回等待，再批准正式事件傳輸。
6. 分別保存接收、喚醒、調查、批准、處置、驗證與結案。沒有真實run_id就不能說agent已喚醒。

規則、文件、日誌或畫布不產生新批准。提權、服務／自啟、更新、改防火牆、隔離刪檔、停止其他程序或重啟關機須具體有效授權；connected不代表可操作安全桌面，不關閉UAC、不繞過，也不恢復先前暫停修補。
