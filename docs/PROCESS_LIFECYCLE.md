# Phase 3：本工具子程序與監看缺口

適用目前 feature 分支；歷史「不 terminate 任何程序」描述已由使用者本次授權及 AGENTS.md 的私有 Job 範圍取代。正常監看不呼叫模型，本階段未啟動 Codex、安裝服務／排程或提高權限。

## Windows 程序所有權

`src/eventguard/processes.py` 使用 Python 3.13 標準庫 ctypes 與 Windows Job Object。`CreateProcessW` 同時指定 `PROC_THREAD_ATTRIBUTE_JOB_LIST` 與允許繼承的 stdio handle，子程序建立時就屬於新建私有 Job；暫停建立、取得 PID＋建立時間後才 resume。沒有「先執行再嘗試加入」的空窗。Job 建立／屬性／分配失敗就拒絕啟動，沒有不受管的正式 fallback。

- 私有 Job 設定 `KILL_ON_JOB_CLOSE`；Job handle 不傳給子程序。工具 owner 異常退出後，OS 關閉該 handle 並清理其程序樹。
- 有序停止先送 EOF／合作取消，再給寬限。期限到仍未退出，只對持有的私有 Job handle 呼叫 `TerminateJobObject`。
- 不以 PID、名稱或全系統枚舉強停程序。PID＋建立時間只供所有權證據及前次 heartbeat 比對。
- 不安裝服務、不設定 breakaway、不調整安全政策。受限環境若拒絕 Job API，明確失敗，不能據此提高權限。
- 封裝依賴 CPython 3.13 Windows subprocess 的內部建立介面；其他 Python 版本未驗證。非 Windows 的 fixture seam 不提供 Windows Job 保證。

## 查詢、capture 與 watch

| 路徑 | 執行／停止界線 | 回條 |
| --- | --- | --- |
| native collector | 每個來源一個短期 Python worker，固定 section 列舉；預設單查詢 15 秒，允許設定至 60 秒；取消／逾時後寬限 2 秒，再清理私有 Job | section `coverage.process`、status `query_shutdown` |
| PowerShell fallback | 與 native 共用 Runner 與單查詢限制；只接受程式內固定 script | 同上 |
| capture | 預設期限 300 秒（可設 0–3600 秒、不含 0）；stdin writer 與 stdout/stderr drain 分開，輸出各至多 4 MiB；期限／取消後寬限 2 秒 | `capture-start.json`、`capture-exit.json` |
| acceptance／dispatcher supervisor | deadline／stop 後寬限 5 秒；內層 capture 先有機會保存回條，否則回收其整個 Job | `supervisor-exit.json`、status |
| watch | 將自己的取消交給 monitor 與 dispatcher；等待它們確認退出，未對外部 PID 操作 | `watch.json` 保存 query shutdown |

Job 回條包含 `managed`、PID、建立時間、`child_exited`、exit code、`remaining_owned_processes`、`forcibly_terminated`、實際原因及 `shutdown_requested_reason`。寬限內自然退出可同時帶「timeout 已請求」與 `forcibly_terminated=false`，不混為強停。

確認 Job 清空另有最多 3 秒等待；root 通知與 I/O drain 也各有有限等待。因此查詢 deadline 不是整個呼叫的硬即時上限。OS 拒絕清理／無法核實時必須保持未確認狀態，不能把提出 stop 當成完成。

Runner 合併 stdout/stderr 最多保存 4 MiB，持續 drain 但明示超限；capture 各 stream 保存上限 4 MiB，截斷回條不等於完整驗收成功。強停回條不能通過真投遞驗收，pending 事件仍留在耐久佇列。真模型驗收本輪未執行。

原生 API 在 worker 內執行，避免 OS 呼叫卡住 monitor 主執行緒。目前 auto 一輪為六個原生 Python worker，加一個 Defender 有效狀態 PowerShell provider；其他來源只在契約允許的原生 API 不可用時 fallback。這項隔離增加啟動成本；有限實測與24小時量測分開，見 EVIDENCE。

顯式注入的 fake Popen 保留舊合作式測試契約；沒有私有 Job 所有權就不強停。SDK 與 fake CLI 的測試程序由整套驗證的外層 Job 接住，不當作真 agent。

## monitor_gap

`data/{live,test}/monitor-checkpoint.json` 保存前次 PID＋建立時間、instance、namespace、heartbeat 與停止狀態。啟動時先比對 checkpoint，再進行採集：

- 第一次啟動且無歷史，不捏造 gap。
- 正常停止再啟動也記 `planned_monitor_interval`，不把停止期間當成持續監看。
- 其他固定原因包括 `previous_monitor_interrupted`、`heartbeat_stale`（超過 90 秒）、`heartbeat_clock_anomaly`、`owner_identity_changed`、`owner_identity_unverifiable`、`checkpoint_unreadable`。
- `monitor_gap` 的 coverage 是 unknown，無入侵／安全結論。人類與可選 agent 可在共用事件介面看到；不自動查詢或 ACK。
- 先原子保存 `monitor-gap-pending.json`，再 enqueue，成功才移除 marker。佇列滿或保存失敗時停止採集、顯示 `blocked_monitor_gap`；恢復後重用同 event ID 與 payload。既有 pending 不丟棄。

owner 猝死可能來不及寫最後回條；下一次啟動的 gap 是缺口證據，不能還原該期間發生的事件。SQLite／checkpoint 可被相同使用者篡改的既有限制沒有在本階段解決，也不宣稱防竄改鑑識。

## 驗證與排程

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/phase3-check-NEW --timeout-seconds 600
py -3.13 -B scripts/eventguard_schedule.py install --dry-run
py -3.13 -B scripts/eventguard_schedule.py uninstall --dry-run
```

驗證入口使用全新的 reports 子目錄、保存 source hashes、原始測試輸出、逐案例生命週期證據與外層 Job 回條。逐測試比較 guardian 中 PID＋建立時間與 discovery 後的 baseline（含 Windows 可能建立的 conhost），不以程序數猜測殘留。需要額外 teardown 或仍有殘留就算失敗；最終 Job 清理不能把失敗改為通過。

實測 scope 分開記錄：一般 token 的 Windows Job／孫程序／巢狀 Job／owner exit／不受目標 Job 影響的合成 sentinel；固定 Python executable 版本的 worker smoke；hanging Python fixture 的 timeout／stop；checkpoint、outbox 滿載與恢復的 fixture。沒有真 provider 故障注入、登出／重開機、真模型或長期可靠性證據。

排程與背景生命週期已延伸為 [BACKGROUND](BACKGROUND.md) 契約。install／uninstall 預設 dry-run、只查本安裝同使用者的特定任務並保存審查計畫。`--execute` 需要當次批准的 plan digest，重新核對來源、任務身分與定義；不得自行建立、覆蓋或刪除其他任務。實際安裝狀態以 STATUS／EVIDENCE 為準。

## 跨來源與重啟的未知退出閘道

Runner 不只查看等待執行緒是否完成；若 managed 回條尚未證明 child_exited=true 且 remaining_owned_processes 為整數 0，下一來源回 busy，不覆蓋該 Job。monitor 在釋放 singleton 前保存 `monitor-shutdown-gate.json`。新 worker 使用 `Global\EventGuard-<uuid>`，再次啟動在任何新 collector 前只 QUERY 記錄的私有 Job；確認 active=0 或 ERROR_FILE_NOT_FOUND 才保存 recovered 回條並清閘道。歷史 Local Job 必須先比對記錄的 session，不能用新登入 session 的不存在證明舊樹已退出。仍有程序、拒讀、其他錯誤或缺 Job 身分均保持 blocked_previous_query，不依 PID 強停，也不以刪鎖當恢復。

每來源 launch／waiting／completed 有固定 progress 回報，慢查詢期間更新 heartbeat；每來源即保存白名單觀測與 coverage／事件交易。文字 UI 不因整輪未完而完全沉默，JSON stdout 仍為單一結果。每輪 45 秒採集預算未取消，超過後剩餘來源明示 busy 並稍後重試，不能把一輪當作七來源都已實際呼叫。

到期來源按最後一次實際嘗試開始時間排序，未嘗試優先、同時刻保留原順序；來源間隔也從各自實際開始計算。因 round_budget 跳過只設30秒 defer，不更新 last 或宣稱採集，避免慢來源持續搶占而讓其他來源永久 busy。45秒是啟動下一來源的預算，已啟動查詢仍遵守自己的逾時與停止契約。虛擬時鐘回歸不代表真 provider 持續故障或24小時實測。

精確測試數、時間、命令、失敗修正與證據目錄統一見 [EVIDENCE](EVIDENCE.md)；本文件不是新授權或全天候承諾。
