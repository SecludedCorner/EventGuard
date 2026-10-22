# 可選 agent：共用耐久預算與退出證據

正常監看不需要這份帳本，不會呼叫模型。每日額度也不是模型啟動授權；真 CLI 執行仍須當次有效範圍。人類與 agent 共用 `OperatorAPI.status`，可讀 `agent_budget`，不會自動初始化或重置帳本。

預算 status 不扣額度、不啟動程序，但會以交易更新耐久時鐘檢查點並使用 authority lock；不是帳本位元組唯讀。Windows 感測與已保存事件的唯讀界線不變。

## 唯一 authority 與扣帳

同一安裝的固定位置是 `data/agent-budget/authority.sqlite3`，旁有 opaque installation marker；不依 source、run、state、cwd、環境變數或 CLI 參數切換。不使用 Codex home、憑證、私人 sessions 或帳戶用量 API。這是 EventGuard 受管入口的應用程式限制，不是帳戶級或同使用者防竄改邊界；另一份 checkout 不能據此宣稱共用帳戶總額。

UTC+08 日界，每日最多 5 次，跨 dispatch、acceptance、retry。同一 namespace/event ID 保留 payload hash 與最多 3 次計數，來源路徑不參與主鍵。先在同一 SQLite 交易保存 charge、attempt 及 global active，才可建立 worker。capture 在真正建立 CLI 前，核對一次性 intent 與 argv/prompt digest；synthetic 標籤不能豁免真正啟動。準備、等待、status、verify-only 不扣模型任務數。

扣帳後的失敗、取消、崩潰、不確定啟動及驗收均計入，不退款。換目錄／日期、釋放 OS lease、ACK、模型文字成功，都不能解除未知退出。無事件或額度耗盡不啟新模型，pending 不因這些狀態被清除。

## 明示初始化與人工查看

以下是操作說明，這批開發不在正式資料目錄執行初始化或模型：

```powershell
py -3.13 -B scripts/eventguard.py budget status
py -3.13 -B scripts/eventguard.py budget initialize
```

初始化只允許不存在 marker 與 DB 的安裝。預設當日歷史用量未知，標 `budget_bootstrap_usage_unknown`，不發放當日新額度；合理次日才可用。只有人類已核實當日受管歷史數時，才可明示 `initialize --known-used N`（0..5）。不得以「測試目錄是新的」推定正式當日用量為零。

已存在的 marker/DB 任一缺失、損壞、身分／政策不符、redirect、busy 或容量不足都阻擋，不建立空帳本替代。這時 status 明示 `blocked` 與固定原因碼，不顯示主機安全。

## 啟動窗口與停止

capture 的 installation launch lease 序列化最後 gate、intent、OS create 與程序身分保存。它不同於 SQLite 交易鎖與 run/capture lease；鎖釋放不是退出證據。一般 prelaunch gate 失敗可以保存「未啟動」，保留已扣次數。intent 已保存但最後 gate 失敗時，僅原 owner 持續持有的記憶體 permit 能在尚未呼叫 OS create 前中止；重啟／假票／lease 過期不能重建此證據。已呼叫 OS create 後的錯誤／崩潰，缺少匹配退出證據就保留 active/unknown。

真正收條須比對 attempt、三處 PID、建立時間、Job managed、root exit code、child_exited=true、remaining_owned_processes exact 0。「確定退出」允許強停／非零失敗以解除 active，但不能通過投遞驗收。投遞自然成功另需完整 capture、不截斷、不強停、自然退出理由與 exit 0，並通過實際工具返回及 SQLite ACK 核對。dispatcher 不補造 child_exited=true。

若已保存原 attempt 的完整收條，可顯式核對：

```powershell
py -3.13 -B scripts/eventguard.py budget reconcile --attempt-dir reports/實際原任務目錄
```

只接受本安裝 data/logs/reports 內的回條，且須匹配帳本的 started PID+建立時間。不因 PID 現在不存在就推定該 owned tree 已退出；證據不足維持 blocked。這個操作不呼叫模型、不停止程序、不退款。

## 保留與時間限制

- SQLite 及 marker 有 1 MiB 邏輯／頁面政策、1,024 admissions 上限；開始前預留 terminal 更新空間。status 顯示 DB、邏輯佔用與摘要數；不宣稱檔案系統 journal／metadata 瞬時總量完全等於邏輯額度。
- 只輪替完成／確定未啟動的 admission 明細。daily、event 使用量及 retired attempt tombstone 保留；pending、active、未知退出不刪。刪明細不能重播同一 token 或重置事件次數；彙總／tombstone 也計入容量。
- 最多 366 個日彙總；不提供自動清空或永久無限歷史。無法保留必要證據時明確背壓，待明示維護策略，不能默默丟棄。
- 時鐘回退、早於 high-water day 或相對上次觀察前跳超過 36 小時，回 `budget_clock_uncertain`。長期未使用也可能進入此狀態；目前不提供任意 reset／調時豁免，需人工核對後續維護範圍，不應刪帳本解禁。

## 狀態與驗證界線

`status.last_report`/相容 `health` 是保存回報；`current_monitor` 另核對該 owner 單一 PID+建立時間及 heartbeat。future、naive、過期、拒讀或缺資料為 unknown。逐來源 coverage 保留原狀態與 observed_at，依 interval+query timeout 顯示 freshness；逐 namespace DB 故障不遮蔽其他可讀 scope。沒有獨立 watchdog，monitor_gap 仍於下次啟動辨認。

匯出報告只讀保存事件，標 total/exported/truncated/limit；不因匯出執行 OS 採集。ACK 只表示收到，不是診斷、漏洞修補或案件結束。

測試以 fake clock、合成 SQLite、Python fake CLI 與明示 Windows Job API 分列。正式帳本未初始化、沒有真模型／採集掃描／Phase 7 注入／24 小時 soak。實際命令、數字、source hashes、退出回條及 commit 對照統一見 [EVIDENCE](EVIDENCE.md)。
