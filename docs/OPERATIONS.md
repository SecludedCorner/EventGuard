# 本機操作與故障排除

先用 [README](../README.md) 的隔離 fixture，再看 [共用介面](HUMAN_AGENT_INTERFACE.md)。以下使用既有 Python 3.13，一般權限，不安裝依賴、不啟動模型。

## 前景監看與事件

```powershell
py -3.13 -B scripts/eventguard.py capabilities
py -3.13 -B scripts/eventguard.py status
py -3.13 -B scripts/eventguard.py monitor
```

monitor 需要由人類明確啟動；另一同專案終端 `py -3.13 -B scripts/eventguard.py stop` 合作停止自己的 instance。子查詢在私有 Job，寬限後只清理本工具程序樹；是否退出查回條，不能只看 stop 請求。沒有 watchdog、自啟或已執行的長時保證。

`events list --namespace live` 查看已存 ID，`events inspect --namespace live --event-id EVENT_ID` 查看當時事實。只有明確 `events diagnose` 才執行事件綁定唯讀查詢；不接受自由命令。合成資料用 test namespace，不拿 test 結果判真主機安全。`report export` 只寫本機 JSON／HTML。

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
