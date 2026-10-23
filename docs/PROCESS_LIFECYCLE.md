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

## MCP 應用持有監看

正式operator adapter明確選`OperatorAPI(background_lifetime_owner="application")`；CLI預設仍independent。Start沿用`background.start`及私有application Job，不經DesktopController、不恢復其自動agent選擇。capabilities明示owner與限制，status／launch_intent／後續run亦保留application lifetime。監看沒有固定期限，但依賴此MCP server及祖先Job存活，不能當成獨立、登出或重開機持續運作。

只收下本API Start回呼的新child及run/generation/namespace/job/PID/建立時間，job名另與實際owned handle核對；回報already_running的他人host不收養。EOF先封鎖新Start，等已接受Start完成，再於控制鎖內比對原scope，換代不改新intent；寬限後只finish保留的自身Job，不走全域cleanup或PID強停。單純觀察者EOF不發Stop。

有實際owned child收尾時，atomic/fsync更新固定有界`data/background/operator-stop-receipt.json`，保留scope、Stop與process回條、forced來源、退出及截斷。它不是每connection一檔、不覆寫新host的control／stop-receipt；同使用者可改寫，並非完整防竄改歷史。未知退出保留child與未確認結果；EOF／中斷收尾回條若顯示強停、退出未確認或保存失敗，server回exit2，不能宣稱clean退出。explicit Stop的強停顯示於工具回傳，不因此即時關閉server；意外被結束則未必來得及保存回條。成功空觀察者不覆寫此檔。

本輪Windows SDK／合成fixture驗證與主聊天實測分開；舊server不會隨source檔案自動換版，實際Start被拒絕、恢復暫停及capability仍舊的證據見EVIDENCE。沒有為接線重試proxy、提權或安裝排程。

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

supervisor的run／heartbeat暫時寫失敗會合作取消當次Monitor，沿原backoff等待，可寫後才准許新採集，保留enabled意圖。如果Monitor收尾未確認query退出且shutdown gate也因儲存故障寫失敗，supervisor仍保留原Monitor／Runner及首次捕獲的Job證據；「marker不存在」不能清除此記憶體閘道。先恢復同一既有marker，經Runtime核實同Job empty／missing，再由原Runner.shutdown釋放其自身handle且回條確認exit/remaining0，才放行新Monitor。拒讀、錯Job或不完整回條都繼續等待，Stop／generation變更先於此檢查，不以未知當成安全退出。

### 查詢啟動前保存與跨 client 仲裁

新版的專案入口使用`Runtime.query_launch`：在同安裝根目錄的固定`data/query-admission.lock`取得短期OS lease，先核實舊Job，再將新查詢的確切`Global\\EventGuard-<uuid>`及`phase=launch_intent`原子保存、fsync到既有`monitor-shutdown-gate.json`，最後才建立私有Job子程序。lease涵蓋保存到spawn返回；另一client不能把「尚未spawn所以Job不存在」誤認成退出並清除計畫。native與PowerShell共用同一Runner hook，沒有新增查詢佇列或控制器。

建立／取得lease、保存計畫或舊Job核實失敗，就回busy及policy／`query_admission_*`固定原因碼，不啟動查詢、不偽裝provider拒讀。spawn後才發生lease釋放錯誤則保留原child、managed／PID及收尾責任，不宣稱零執行。所有gate寫入、核實與清除使用同一lease；恢復須先確認確切Job空／已銷毀，再耐久保存recovered回條，最後才移除gate。owner退出只會釋放lease，不是Job已退出的證據。

同process若還持有該Job的原child handle，只在原Job已空、原process已退出時收尾並釋放；另一process不收養handle、不依PID停止或查找其他程序。已完成回條供原Runner讀取，避免它永遠pending。固定gate／recovered／lease檔不隨查詢次數增加，不是抗同使用者竄改的邊界。

保護範圍是**新版專案入口**的預設Monitor、CLI query與OperatorAPI事件診斷（GUI／新載入MCP共用）。單獨使用`WindowsCollectors`／`Runner`的library呼叫必須明確傳入root-bound hook；任意注入collector／fake library不被默認升格為全域保護。舊server不會熱更新。Monitor對零啟動的admission拒絕不扣來源的長間隔，保留baseline，走既有保存背壓及短期defer；事件診斷仍保存busy／unknown，但`system_query_executed=false`。實際已spawn的失敗不套用此零執行判定；各backend attempt保留安全process回條，不能讓fallback的零啟動覆蓋先前native已執行。舊多attempt缺process證據時亦不宣稱零啟動。

精確測試數、時間、命令、失敗修正與證據目錄統一見 [EVIDENCE](EVIDENCE.md)；本文件不是新授權或全天候承諾。
