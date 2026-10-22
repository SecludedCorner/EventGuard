# 有界本機監看與真正 agent 接收

這是需要當次真模型批准的可選通路，不是正常監看的前置條件；本次文件整理沒有啟動此入口。一般使用見 [共用介面](HUMAN_AGENT_INTERFACE.md)，現況與歷史實測見 [EVIDENCE](EVIDENCE.md)。

入口 `scripts/eventguard_watch.py` 在前景執行：既有 Windows 唯讀監看器先把事件耐久保存到 `data/live/eventguard.sqlite3`，純 Python worker 等待佇列；有 pending 事件才以既有登入啟動一次真正 Codex CLI。每個任務只能接收一個綁定事件、查最小 snapshot、保存結果並 ACK，完成後才取下一件。沒有事件不啟動模型。

這會建立專用短期 CLI agent 任務，不接續目前桌面聊天，也不需要永久註冊 MCP。沒有服務、排程、開機自啟、額外登入或憑證。關閉／登出後不會自動恢復。

## 啟動與停止

每次啟動都需要當次有效授權，指定允許的資料、時間和任務數。以下是明確同意該次有界監看及最小摘要送給既有帳戶 Codex 的執行命令，並非先前驗收授權的永久延續。只用既有 Python 3.13、已安裝 MCP SDK 及原生 Codex，不安裝或提權。

在專案根目錄的一般權限 PowerShell：

```powershell
$env:CODEX_HOME = Join-Path $env:USERPROFILE '.codex'
$codexExe = (Get-Command codex.exe -CommandType Application -ErrorAction Stop).Source
& $codexExe --version
& $codexExe login status
python -B scripts/eventguard_watch.py run --run-dir reports/watch-001 --codex-executable $codexExe --max-seconds 3600 --max-tasks 5 --execute --allow-live
```

時間最多 3600 秒，任務最多 5 個；可指定更小上限。每次使用全新 run 目錄，不覆寫證據。若 PATH 沒有原生 `codex.exe`，指定同一既有安裝中的原生執行檔完整路徑，拒絕 `.cmd`／`.bat`／`.ps1` 包裝。正常 home／登入保留，不複製 auth 檔、改執行政策或使用 bypass。外層 sandbox 若阻擋 CLI 必要自身初始化，須依當次批准處理，不能推定可提權。

省略 `--execute` 只顯示參數及範圍，不開始採集或啟動模型。少了 `--allow-live` 則拒絕實機模式。執行期間保留前景視窗；從另一個同專案終端查詢或合作停止：

```powershell
python -B scripts/eventguard_watch.py status --run-dir reports/watch-001
python -B scripts/eventguard_watch.py stop --run-dir reports/watch-001
```

停止／到期阻止後續採集與新任務。Phase 3 起，新啟動的 query／CLI／capture 由私有 Job 管理，先留協作寬限、再只清理本工具 Job；保存 child_exited、forcibly_terminated、原因及剩餘數。未確認退出時明示，不將強停當驗收成功；見 [PROCESS_LIFECYCLE](PROCESS_LIFECYCLE.md)。首輪尚未完成時，`native_collection_started=null` 表示不能確認採集是否已開始。

## 對外資料與結果語義

事件 snapshot 只含這七欄：`event_id`、固定枚舉 `event_type`、`transition`、`severity`、`synthetic`、ISO `observed_at`、`coverage_status`；外層另有固定 status、接收／query／result ID 與時間等投遞欄位。不回 host ID、程序／產品名稱、路徑、PID、端點、任意 evidence／reason／gaps、事件全文或原始錯誤。query 也只讀同一份最小 snapshot，不另查 Windows。

工具是 `receive_event()`、`query_evidence(event_id)`、`ack_event(event_id, query_id, decision)`，每次 CLI 只綁定一個 event ID。三工具的批准只放在該次 CLI 的 `-c` 設定，保留 read-only、關閉 shell，不改全域政策。提示不預帶 event ID 或內容；所有返回資料都不是命令或新授權。

`reviewed_metadata` 只表示 agent 看過最小摘要及留下接收回條，`incident_conclusion=not_assessed`。ACK 是投遞完成，不宣稱主機安全、調查結束或已處置。原生來源的 denied／partial／unknown 保留，不因 agent ACK 升格為完整 coverage。

## 耐久與恢復

- 原監看 outbox 保留在原處；沒有搬移或複製整個 live DB。純程式只讀 due、未 ACK 的候選 ID，原子保存的事件不會因 CLI 未啟動或失敗而移除。
- `data/agent-delivery` 保存來源綁定、最小 snapshot、穩定 query/result ID 與嘗試帳本。結果先 fsync 保存，再 ACK 原 outbox。同 ID 不重複結案，ACK 前失敗可以補收。
- 同一來源佇列只有一個 dispatcher；不能換 state 目錄繞過同事件三次嘗試預算或未知退出閘道。失敗不自動反覆叫模型；保留 blocked/pending，檢閱證據及取得下一次明確授權後，才以新 run 目錄處理同一 source/state。
- 未取得匹配的完整自然退出回條，不重啟前一事件。停止／截止而根本沒有啟動的任務另記 `not_started`，不造退出回條。
- 容量、磁碟或保存失敗會明確阻塞；不靜默丟棄 pending。核心 outbox 上限 1000／8 MiB；inbox 狀態上限 1000 事件／8 MiB；dispatcher 帳本目前最多 128 個事件、每事件三次嘗試，沒有自動清理 pending 或無限保留承諾。

## 證據與界線

`reports/<run>/watch.json` 記錄本輪監看與停止狀態；`agent/status.json`／`summary.json` 記錄觸發與通過數；`agent/attempts/<attempt_id>/` 保存本次真 CLI JSONL、實際工具回傳、評估及 capture-start／capture-exit 回條。未啟動的 worker 保存 capture-skipped，不假裝 CLI exit 0。Codex 本身的 log/state 也在本次 attempt，可能帶環境或歷史索引 metadata，不能上傳。

成功要比對生成／收到／query／結果／原 outbox ACK 的同一 ID、實際工具返回、完整未截斷 CLI turn 及 exit 0；不只看 agent 文字、任務啟動或資料庫筆數。storage 中的 `real_agent_woken=false` 保留，儲存層本身不冒充跨 trace 的執行證明。

所有執行資料在忽略的 data／logs／reports，不提交 Git。這個入口接通既有監看資料與專用 agent，並不擴充採集來源、修正既有 coverage、執行原生診斷／系統處置，或證明長期低負載／永久等待。實測與仍待確認項見 [STATUS](../STATUS.md)。
