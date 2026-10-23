# 選配：事件驅動的專用 agent

普通 Python 程式等待原佇列。有符合條件的事件才啟動短期 Codex CLI。
不續接既有桌面聊天。不建立服務、排程或開機自啟。
本批只執行無模型測試。真實投遞驗收尚未完成。

## 查看與預檢

本機採集及 Web 照常使用 `EventGuard.cmd run`。兩者不需要 agent。

```powershell
.\EventGuard.cmd agent status
.\EventGuard.cmd agent capabilities
.\EventGuard.cmd agent start --codex-executable C:\既有安裝\codex.exe
```

最後一條預設只預檢。不啟動背景或模型。不接受 cmd／bat／ps1 包裝。
正式預檢會檢查來源、MCP SDK、接收權限及固定預算。
登入未在預檢中驗證。CLI 可啟動也不代表能呼叫模型。
缺能力時顯示原因。不得下載、提權或刪帳本解禁。

## 明確啟用、暫停與停止

以下啟用會使用模型。須先有適用的資料及模型批准。本批未執行。

```powershell
.\EventGuard.cmd agent start --codex-executable C:\既有安裝\codex.exe --execute
.\EventGuard.cmd agent pause
.\EventGuard.cmd agent resume --execute
.\EventGuard.cmd agent stop
```

start 使用現有 `data/live` 與 `data/agent-delivery`。
`--namespace test` 改讀隔離合成範圍。它不豁免真正模型的預算或批准。
重啟沿用同一 inbox、來源綁定、dispatcher 帳本及安裝預算。
不因來源目錄、host 重開或 ACK 重置額度。

pause 保存暫停，只阻擋新任務。已啟動任務不因 pause 被取消。
暫停閘道與實際程序啟動的屏障證據分開顯示。未確認就標未知。
resume 預設仍只預檢；加 `--execute` 才解除暫停。
stop 保存停用，合作停止本 host。必要清理只限已核對的私有 Job。
強停或缺完整退出回條不得記為自然成功。
這些命令不停止採集，也不刪除 pending。

## 篩選及預算

編輯 [config/agent-dispatch.json](../config/agent-dispatch.json)。
預設選 high／critical、固定事件種類及 new／read。
handled／ignored 不自動派送。這些狀態不是 ACK，原事件仍保留。
低嚴重度事件不能擋住後面的高嚴重度事件。
設定只接受枚舉清單。不能放命令、目的聊天或自由 prompt。
去重與冷卻沿用原事件來源及帳本，不新增第三份佇列。

每日最多五個任務。失敗、驗收及不確定啟動也計入。
額度耗盡時普通 host 等待。無事件及等待額度時不呼叫模型。
帳本缺失、壞檔或未知退出會阻擋啟動，不能默認剩餘五次。
首次初始化及退出核對見 [AGENT_BUDGET](AGENT_BUDGET.md)。

## 人類可看見的證據

本機 Web 的「Agent 派送」頁顯示程序、心跳、待收數、預算及阻塞原因。
頁面可暫停或停止。不提供啟動或恢復模型的按鈕。
重新整理只讀保存狀態，不做模型輪詢。

```powershell
.\EventGuard.cmd agent inspect --namespace test --event-id <ID>
```

事件詳情也顯示同一份投遞階段。保存、receive、query、結果與 ACK 分開。
inbox 證據不能獨立證明模型執行。缺 provider 生命週期證據時顯示 unknown。
dispatcher 自己另保存真 CLI trace、工具回傳、結果及 owned-tree 退出回條。
模型用量缺失時顯示未知，不假裝為零。

## 給其他應用的封裝

```powershell
.\EventGuard.cmd agent export --namespace test --event-id <ID> --producer-id <固定UUID4>
```

producer UUID 必須由整合者建立一次並耐久保存。不能每次產生新值。
它不得包含主機或使用者名稱。export 不會自己建立身分、收件或 ACK。
輸出為 CloudEvents 1.0 的受限 profile，data 仍是原七欄。
schema 見 [event-ingress.schema.json](../config/event-ingress.schema.json)。
同 source＋ID 不同內容是衝突。wire hash 與原 EventStore hash 不混用。
外部公告及事件皆是不可信資料。不能變成命令、工具權限或目的地。

OpenOctopus 可使用此 adapter。其 Inbox、provider 與 UI 尚未在該專案實作或驗證。
Codex 桌面 queue 仍是未驗證候選，不阻擋專用 CLI 路徑。

## 驗收界線

測試證據見 [EVIDENCE](EVIDENCE.md)。fake CLI、實際 Windows Job 與真模型分列。
真驗須先指定合成範圍、有限任務數、固定預算與正常退出條件。
必須核對生成／receive／query／結果／ACK 的 event ID 集合。
只有真工具回傳及退出證據齊全，才能宣稱真正 agent 收到事件。
ACK 不代表漏洞已修復、主機安全或人類案件結束。

既有驗收入口新增 `service`。以下只準備一件公開合成事件及空來源，不啟動 host 或模型：

```powershell
py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-NEW
```

取得本輪有限批准及有效預算後，才在同一目錄加 `--codex-executable $codexExe --execute`。
程式先等空佇列，再加入事件。最多一個任務，總期限 180 秒，最後合作停止隔離 host。
根據 intent 拒絕同目錄重跑。失敗先讀該輪 trace、stderr、狀態及退出回條。
`--verify-only` 只重驗既有證據，不啟動模型，不重新收件或 ACK。
前後短暫空閒只證明該窗口。它不代表長期 soak 或獨立背景壽命已驗證。
