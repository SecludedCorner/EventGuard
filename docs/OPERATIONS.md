# 本機操作與故障排除

先用 [README](../README.md) 的隔離 fixture，再看 [共用介面](HUMAN_AGENT_INTERFACE.md)。以下使用既有 Python 3.13，一般權限，不安裝依賴、不啟動模型。

## 前景監看與事件

`EventGuard.cmd agent access status`唯讀查看本工具接收權限；enable／disable明確保存此gate。這是接收設定，receiver狀態仍須另外驗證；它不授權模型、啟動／停止程序或確認退出，既有程序用其owner的控制入口。保存失敗exit4，壞設定blocked=exit2；正常等待不呼叫模型。實際執行enable仍由使用者決定，本次開發只操作隔離合成安裝。

```powershell
py -3.13 -B scripts/eventguard.py capabilities
py -3.13 -B scripts/eventguard.py status
py -3.13 -B scripts/eventguard.py monitor
```

monitor 需要由人類明確啟動；另一同專案終端 `py -3.13 -B scripts/eventguard.py stop` 合作停止自己的 instance。子查詢在私有 Job，寬限後只清理本工具程序樹；是否退出查回條，不能只看 stop 請求。沒有 watchdog、自啟或已執行的長時保證。

`events list --namespace live` 查看已存 ID，`events inspect --namespace live --event-id EVENT_ID` 查看當時事實。只有明確 `events diagnose` 才執行事件綁定唯讀查詢；不接受自由命令。合成資料用 test namespace，不拿 test 結果判真主機安全。`report export` 只寫本機 JSON／HTML。

query的`--args`限一筆完整JSON物件、8KiB／32層；重複欄位（含unicode escaped同名）及過深結構在查詢前exit2，固定query_input_duplicate_key／query_input_depth_exceeded，不採最後值覆蓋。PowerShell可直接用管線傳給`--args -`，實際批次入口亦已驗：

```powershell
'{"request_id":"health-1"}' | .\EventGuard.cmd --format json query health --args -
```

health只查工具能力，不查Windows來源。stdin限UTF-8（可BOM），上游關閉後解析；超過8KiB即拒絕，互動終端不等待。`--args`文字參數仍可用；含引號的JSON經Windows批次檔時使用stdin管線，避免shell改變內容。此入口不隱含採集、模型或ACK。

## 保存事件調查

人工處置可用固定operation ID重送及唯讀查回原結果；每個不同要求用不同ID：

```powershell
.\EventGuard.cmd --format json events set-status --event-id <ID> --status read --operation-id review-001
.\EventGuard.cmd --format json events operation-result --event-id <ID> --operation-id review-001
.\EventGuard.cmd --format json events pending-requests --limit 10 --offset 0
```

operation-result的operation是原結果，current是目前狀態；相同要求重送不回退後來狀態。not_recorded表示該保存庫沒有此筆，不證明外部未執行。unknown及exit5表示資料不足，不能判安全；非法輸入exit2。pending-requests只發現待確認要求，將其event_id傳入events detail可查看原ID；查閱不重送、不確認GUI回條、不ACK。合成案例加`--namespace test`，不讀主機新資料。

可先以events detail讀payload_hash，再在set-status加`--expected-payload-hash <該hash>`，使交易只接受相同事件內容；不符回event_payload_conflict／exit2，原決定不寫入。hash只檢查保存內容一致性，不是操作者或事件來源的信任證明。

事件頁「查看」後，按「建立／更新保存的調查」。它只讀目前來源 SQLite 的允許 metadata，保存一份案件與時間線；不呼叫模型、不採集、不 ACK、不改人工處置狀態。CLI 使用相同 EventCatalog：

```powershell
.\EventGuard.cmd events list
.\EventGuard.cmd events investigate --event-id <已保存的事件ID>
.\EventGuard.cmd events detail --event-id <同一事件ID>
```

`investigate` 明確建立／更新；`detail` 與 Web 重開只讀已保存調查。合成資料加 `--namespace test`，自訂隔離來源另加 `--event-source <專案內既有source目錄>`；兩端必須讀同一來源，不能把預設 data/test 與 reports 來源混用。

案件最多16件、候選最多256件、時間範圍為錨點前後15分鐘。關聯還必須同 host 範圍、同來源及同穩定程序實例，或同持久項目 reference。PID 需要建立時間，已知 reference／建立時間衝突不能靠 PID 補回；只有時間／port／名稱相似不加入。序號及同時矛盾只比較同一 episode，不把正常多端點或 episode 序號重置當矛盾。這是 metadata 關係，不建立程序樹、ATT&CK 確證或攻擊因果。

頁面與 JSON 列出事實、來源 coverage、過期／未來時間／缺綁定／矛盾／截斷、下一個可批准觀測及限制。既有事件沒有 OS 帳戶 owner 證據，固定顯示 UNKNOWN；案件內 `owner_ref` 僅為 host_id＋synthetic 的不透明範圍雜湊，不是 OS 帳戶。不能宣稱已驗證跨帳戶關聯。新觀測需適用批准，`allowed_actions=[]`，此入口不執行系統處置。

每個錨點只保留最新一份64KiB以內的調查，原子交易保存，預留 pending／ACK 空間；尚無版本歷史。來源事件輪替時一併清理其案件。關聯成員缺失或 payload/hash 改變時保留原快照並標 UNKNOWN；錨點身分不符或案件被改壞則拒讀。新鮮度在讀取時另顯示，不覆寫原保存時間。此功能與真 CLI 收件證據分開，完整驗收範圍見 [EVIDENCE](EVIDENCE.md)。

新建的1.1案件另納入同事件已保存且身分驗證通過的診斷摘要：保存hash、觀測時間、query類型／來源／狀態／列數，不複製rows、不執行 `diagnose`。缺診斷、空結果、partial、過期或未來時間會列缺口；來源診斷其後變更／刪除時，顯示已變／缺失，原案件快照不改寫。跨事件誤綁或保存競態拒絕新案件，保留舊版及原投遞狀態。舊1.0案件仍可讀，不因查看而補造新證據。

## 故障與資料保留

| 觀察 | 查證／恢復 |
| --- | --- |
| partial／denied／unknown | 看逐來源 coverage.errors 的 stage／原因碼；不改權限或把空資料當安全 |
| stopping_pending_query／shutdown_unconfirmed | 看 query_shutdown、Job child exit／剩餘數；未確認時不宣稱 stopped，不強停外部 PID |
| blocked_monitor_gap | 保留同 ID gap marker；解除容量／保存錯誤後重新啟動才補送，不刪 marker 假裝無缺口 |
| outbox／inbox 容量錯誤 | 保留 pending／retry／未 ACK failed；由合法 consumer 完成既有 ACK，讓已完成資料依政策輪替 |
| prior_child_exit_unconfirmed／失敗交付帳本 | 檢視原 attempt 與回條；不刪紀錄重置預算，也不自動重試模型 |
| inbox_state_busy | 另一 mutation owner 正在工作；不要強停 owner 或改鎖檔；正常退出後重試 |

[生命週期](PROCESS_LIFECYCLE.md) 與 [儲存政策](STORAGE_RETENTION.md) 列出具體界線。status 是最後監看報告與目前本機佇列視圖，不是獨立存活偵測或安全結論。

真正 agent CLI 僅在新的明確範圍批准後使用 [可選通路](LIVE_CHANNEL.md)。當前維護不呼叫模型、不改 MCP 設定、不啟用排程；歷史有限成功不延伸成永久批准。排程僅 dry-run，soak 與 Phase 7 仍未執行。

驗證與時間記錄只寫 [EVIDENCE](EVIDENCE.md)，保持 [STATUS](../STATUS.md) 一頁現況；不得上傳原始事件、SQLite、完整 trace 或憑證。
