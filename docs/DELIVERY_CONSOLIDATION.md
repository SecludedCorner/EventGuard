# Phase 5：投遞／驗收收斂

程式起點 `fa572ca`（程式位元組同 `1e90a53`），分支 `feat/local-codex-acceptance`。本批只做已授權的離線程式工作：沒有真模型、原生資產重掃、部署、排程、網路或遠端 CI。本輪測試數及回條統一見 [EVIDENCE](EVIDENCE.md)。

## 一條目前路徑

```text
正式／合成 EventStore → QueueInbox → eventguard_inbox_mcp
                                 ↑             ↑
                     agent_dispatch／delivery_validation
                         共用 command、capture、assess_delivery
```

沒有事件時，dispatcher 由 Python 等佇列；新驗收先由程式耐久 enqueue 才開短任務，不讓模型等事件。人類／agent 共用 OperatorAPI 的操作與查證仍獨立存在，未改成必須使用模型。

| 模組／入口 | 本批前的用途 | 本批後及保留理由 |
| --- | --- | --- |
| `agent_dispatch` | 正式來源的有界事件派送 | 仍是唯一監看派送器；QueueInbox、帳本、每事件三次上限與未知退出閘道保留 |
| `queue_inbox` | 七欄 snapshot、耐久 query/result/ACK | 新合成驗收也直接使用；不再以另一個 backend 的成功冒充此路徑 |
| `scripts/validate_delivery.py` | LocalWait 的 continuous/batch/recovery | 新的唯一建議驗收入口；`single/continuous/batch/recovery` 都用 QueueInbox |
| `delivery_validation` | 無 | 只協調有限合成案例，重用 dispatcher 的 command、assessor 與 capture；不另造接收帳本 |
| `scripts/acceptance_codex.py` | 單一合成驗收，run 會開模型 | `run` 轉到新入口的 single；預設只準備，必須明確 `--execute`。舊 status/stop 仍讀原證據；舊 retry 不再啟動模型 |
| `contrib/legacy_delivery_validation.py` | 原 validate_delivery 實作 | 保留舊 manifest／trace 的 `--verify-only`，原測試搬到該讀取入口；重複 producer/capture 迴圈已移除，CLI 拒絕執行；不在目前路徑 import |
| `codex_acceptance`、`local_wait`、`eventguard_local_mcp` | 舊 synthetic 等待協定／重試／SDK 工具 | 保留舊格式、失敗／退出及 SDK 相容測試；僅 legacy 相容，不再是新驗收／監看的依賴 |
| `acceptance_control/process/evidence` | 共用鎖、JSON、capture 及舊 trace reader | 保留共用基礎；path guard 與例外抽到 `local_paths`，一般派送不再 import LocalWait |
| `src/eventguard/mcp/` | 停用的 HTTP／雲端 bridge | 整包移到 `contrib/mcp_bridge/`；原測試全保留，固定 synthetic projection 抽到純函式模組；沒有啟用 |

## 等價範圍與不能混稱的差異

搬移前已保存十二組合成 projection；搬移後比較完整輸出相等。兩 backend 以同一個事件核對 wait/receive、query 穩定性、ACK 前 pending、重播同 ACK 及 SQLite receipt 數；另保留所有舊測試。這些證明共同的 ID／耐久語義，不表示兩份 wire schema 相同。

LocalWait 的舊 query 有白名單合成 evidence、decision=`reviewed_synthetic`；QueueInbox 只有七欄、decision=`reviewed_metadata`。因此不把舊 ledger 強制轉寫成 inbox，不搬移 live／reports，也不刪掉讀取舊失敗證據所需程式。legacy reader 以 SQLite mode=ro/query_only 讀原資料，不執行 schema 或 policy 初始化；測試核對原 marker／ledger／DB 位元組不變。重新核對可以更新 validation 摘要，不改原來源。legacy reader 保留不代表另外部署一套投遞。

新的恢復 read 階段：SDK 不列出 ACK，呼叫驗證也拒絕 ACK；實際 CLI JSONL 須只有 receive/query，正常退出後再保存來源仍 pending、沒有 result 的證據。第二階段沿用同 event/query ID 才可 ACK。新／舊 trace 的 assessor 分開保留；不得互換 decision 或冒充等價資料。

## 唯一建議驗收指令

```powershell
py -3.13 -B scripts/validate_delivery.py single --root reports/queue-single-NEW
py -3.13 -B scripts/validate_delivery.py continuous --root reports/queue-continuous-NEW
py -3.13 -B scripts/validate_delivery.py batch --root reports/queue-batch-NEW
py -3.13 -B scripts/validate_delivery.py recovery --root reports/queue-recovery-NEW
```

以上只準備合成 manifest，不啟動 agent、不做原生查詢。已有當次有限真模型批准時，才另加 `--execute --codex-executable <既有原生執行檔>`；只用既有 MCP SDK，不安裝。Windows 拒絕非 `.exe`；各平台拒絕 `.cmd/.bat/.ps1`。`--verify-only` 只核對既有證據。既有執行目錄不自動重試，失敗保留 pending 與退出回條。

各事件使用一個綁定短任務；single 一個、continuous 兩個、batch 三個、recovery 兩個。四案例合計七個唯一事件、八次接收／query、七次 ACK／八個短任務，和舊 LocalWait 的五個真任務編排不同。本輪只有明示 fake CLI，沒有執行這八個真任務。

每階段保存 manifest、CLI JSONL/stderr、capture-start/exit、實際工具結果與 assessment；來源 SQLite/inbox 保留於同一目錄。需要相符 attempt/PID、完整不截斷輸出、exit 0、自然退出且無剩餘 owned child；模型文字成功不能替代工具／ACK 證據。`validation.json` 比對 generated/received/queried/ACK ID 計數、missing/duplicates；恢復另需 pending-proof 與 `recovered_same_event_and_query`。

## 容量、預算與安全界線

outbox/inbox/dispatcher 的 Phase 4 保留及背壓政策未放寬。新驗收只用專用 synthetic source，不接正式 DB；不清 pending、不刪未知退出／失敗記錄，也不藉新目錄重啟同一正式事件。ACK 仍只代表接收，不代表診斷、修補或案件結束。

**尚缺的是跨所有入口的每日耐久任務總額。** 現有 `max_tasks=5` 是每一輪上限，每事件三次是跨 run 的耐久限制；不能把它們寫成每日五次。研究任務提出的每日五次政策，本批沒有偷偷實作，也不啟動模型驗收；要實作時須將驗收、失敗與各入口接到同一耐久預留帳本。舊目錄及現有資料不因本批清空。

## 啟動與 CI

四個 `.cmd` 共用 `scripts/run-python.cmd`：先檢查既有 `py -3.13`，再嘗試 PATH 的 `python.exe` 並核對 3.13。缺少就 exit 2，不安裝、不改政策。移除硬編碼 `C:\Python313`，各入口傳回真退出碼；測試只呼叫 `--version`，未啟動監看。

`scripts/verify.py --scope full` 保留整套測試；`--scope mock` 明列純 fixture／規則／SQLite／mock protocol/store 模組，沒有 SDK、原生 provider 或真模型。兩者都保存來源 hash 與退出證據；manifest 現在也包含 contrib、`.cmd` 與 workflow。

`.github/workflows/tests.yml` 準備 windows-latest 完整 job 與 ubuntu 的 mock-only job，後者明示不代表 Linux 原生支援。未推送／執行遠端 CI；Windows runner 缺少可選 MCP SDK 時會回報 skips，不能宣稱驗過 SDK。沒有上傳本機 runtime 的 artifact 步驟。長時 soak、重啟／登入恢復、真 agent 及 provider coverage 均沒有在此批重驗。
