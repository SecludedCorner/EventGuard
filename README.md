# EventGuard

Windows 一般權限的唯讀監看工具。核心能獨立採集、記錄變化、查看事件與匯出報告；人類 CLI 與可選 agent 介面共用操作核心。正常監看不呼叫模型。

目前是 [MIT](LICENSE) 工程預覽。目前受測程式與 commit 見 [EVIDENCE](docs/EVIDENCE.md)，最新狀態見 [STATUS](STATUS.md)，實測範圍與數字見 [EVIDENCE](docs/EVIDENCE.md)。

## 如何運作

```mermaid
flowchart LR
    B[背景 supervisor / 耐久啟停] --> M
    W[Windows 唯讀來源] --> J[私有 Job 內的 collector worker]
    J --> M[Monitor 與確定性規則]
    M --> S[SQLite 耐久事件與 ACK]
    H[人類 CLI] --> O[共用 OperatorAPI]
    A[可選 stdio agent 工具] --> O
    O --> S
    O --> Q[事件綁定唯讀查證]
    Q --> S
    O --> R[本機 JSON / HTML 報告]
```

## 五分鐘 fixture 快速開始

在專案根目錄，用既有 Python 3.13。這段建立全新隔離資料目錄，只讀合成 fixture，不查 Windows 來源、不啟動 agent；`quickstart-NEW` 已存在時換新名稱。

```powershell
py -3.13 --version
$eventguardDemo = Join-Path (Get-Location) 'reports/quickstart-NEW'
New-Item -ItemType Directory -Path $eventguardDemo -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Path "$eventguardDemo/config", "$eventguardDemo/playbooks", "$eventguardDemo/tests/fixtures" | Out-Null
Copy-Item -LiteralPath 'config/default.json' -Destination "$eventguardDemo/config/default.json"
Copy-Item -LiteralPath 'playbooks/default.json' -Destination "$eventguardDemo/playbooks/default.json"
Copy-Item -LiteralPath 'tests/fixtures/normal.json' -Destination "$eventguardDemo/tests/fixtures/normal.json"
$eventguardCli = 'import sys; from pathlib import Path; sys.path.insert(0,"src"); from eventguard.cli import main; r=Path(sys.argv.pop(1)); raise SystemExit(main(root=r))'
py -3.13 -B -c $eventguardCli $eventguardDemo --format text monitor --fixture tests/fixtures/normal.json --max-cycles 1
py -3.13 -B -c $eventguardCli $eventguardDemo --format text overview --namespace test
py -3.13 -B -c $eventguardCli $eventguardDemo --format text sources show --source-id defender --namespace test
$eventguardItem = py -3.13 -B -c $eventguardCli $eventguardDemo synthetic emit --scenario listener | ConvertFrom-Json
py -3.13 -B -c $eventguardCli $eventguardDemo events inspect --namespace test --event-id $eventguardItem.event_id
$eventguardReceipt = py -3.13 -B -c $eventguardCli $eventguardDemo --format json events receive --namespace test --event-id $eventguardItem.event_id | ConvertFrom-Json
py -3.13 -B -c $eventguardCli $eventguardDemo events ack --namespace test --event-id $eventguardItem.event_id --query-id $eventguardReceipt.query_id
py -3.13 -B -c $eventguardCli $eventguardDemo report export --namespace test
```

預期顯示監看已停止、七來源保存狀態及筆數；合成 Defender 有兩筆可讀觀察。事件先 pending，明確 receive 後取得 query ID，再 ACK；ACK 只代表收到，不是修復／結案。報告提供 JSON／HTML 路徑。全程沒有模型，核心只用標準庫。

## 人類操作與可選 agent

一般權限明確啟動背景監看；採集不受每日 agent 額度或一小時期限限制：

```powershell
py -3.13 -B scripts/eventguard.py background start
py -3.13 -B scripts/eventguard.py overview --namespace live
py -3.13 -B scripts/eventguard.py sources show --source-id listeners --namespace live
py -3.13 -B scripts/eventguard.py stop
```

也可執行 Start／Status／Stop-EventGuard.cmd。Stop 先保存 disabled，登入排程不會推翻手動停止；再次 Start 才啟用。監看逐來源回報進度／筆數，無模型也能運作。終端預設文字，管線預設 JSON，可用 `--format text|json` 固定。

重開機後於同一使用者登入時恢復，使用 [背景監看契約](docs/BACKGROUND.md) 的低權限 ONLOGON 排程；建立／立即執行仍需批准。若啟動端受外部 Job 約束，回報 `independent_background_unverifiable`，不繞過它；排程可直接執行同步 host。前景除錯仍可用 `monitor`。

`events list/inspect/diagnose/receive/ack/retry` 與報告操作見 [共用介面](docs/HUMAN_AGENT_INTERFACE.md)。inspect／sources 只讀保存觀察；diagnose 才執行事件綁定查詢。可選 stdio 需既有 MCP SDK及 client 明確連接，不永久註冊、不自行啟動模型或接續桌面聊天。

## 現況與限制

- 原生 API 優先、同身分 PowerShell fallback；七來源的可讀範圍與拒讀原因見 [採集契約](docs/COLLECTOR_CONTRACT.md)。Defender／程序／監聽身分仍 partial，tasks unknown；不因缺資料提權。
- 子程序從建立時加入私有 Job；停止先寬限，逾時只清理本工具程序樹。啟動保存 `monitor_gap`，未確認退出不報 stopped；見 [生命週期](docs/PROCESS_LIFECYCLE.md)。
- 每來源即時保存有界觀察；過期、截斷與拒讀均顯示。退出未確認會耐久阻擋新 worker，僅能以該私有 Job 已空／銷毀的證據恢復；不靠刪鎖或重開目錄繞過。
- ACKed 資料與完成帳本有保留、輪替及有限上限；pending／retry／未 ACK failed 保留。去重有時間與容量窗；見 [儲存政策](docs/STORAGE_RETENTION.md)。
- 背景 supervisor 對異常／保存背壓以程式等待後重試；事件先落 SQLite。沒有事件不叫模型，有事件也由人類或已連接的可選接收者接手。
- [24 小時 soak](docs/SOAK_PLAN.md) 尚未執行，真實狀態注入／登出重開機仍未驗證。排程實際安裝狀態見 STATUS，沒有服務、登入前監看或全天候承諾。
- 不提供 EDR／鑑識、自動處置、GUI 或 Linux 原生採集。沒有事件、ACK 或診斷都不能證明主機安全。
- 執行資料與憑證不入 Git。歷史有限 Codex 通路驗收見 [歷史入口](docs/history/README.md)；不是正常使用的前置條件或新的模型授權。
- 可選 CLI 共用[每日耐久預算與未知退出閘道](docs/AGENT_BUDGET.md)；未初始化或證據不足就阻擋，不因換目錄重置。接收失敗可由人類接手；不把人類 ACK 升格為 agent 驗收成功。

目前投遞／驗收已使用 [同一 QueueInbox 路徑](docs/DELIVERY_CONSOLIDATION.md)；Phase 7 [實機驗證計畫](docs/WINDOWS_VALIDATION_PLAN.md) 尚未執行。下一階段的範圍、完成條件與停止關卡見 [維護目標](docs/MAINTENANCE_GOAL.md)。離線開發與驗證見 [DEVELOPMENT](docs/DEVELOPMENT.md)。
