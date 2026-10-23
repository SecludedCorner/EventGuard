# 接通人類、聊天工具與事件觸發 agent

最後核對：2026-10-23。先讀 [STATUS](../STATUS.md) 的實測界線；本頁是設定方法，不是新一輪模型／正式資料授權。

## 兩種連接，分開設定

| 用途 | 誰等待事件 | 何時使用模型 | 能力 |
| --- | --- | --- | --- |
| 聊天中手動使用 MCP | 使用者或正在工作的 agent | 聊天正在執行時 | 列表、查看、接收、ACK；註冊工具本身不喚醒閒置聊天 |
| 有事件才啟動專用 agent | EventGuard 的 Python dispatcher | 有 pending、開關開啟、預算允許時 | 每個事件開一個短期 Codex CLI 任務；完成後回到 Python 等待 |

人類 GUI／CLI 始終可獨立操作。agent ACK 只表示看過最小摘要，不表示事件已處理、主機安全或案件結束。專用 CLI 不續接任意既有桌面對話。

## 日常使用

1. 雙擊 `EventGuard.cmd`。預設未開自動模式時，按「開始」只有本機採集；若之前已保存自動選擇，開始也會恢復純程式待命。
2. 「允許 agent 接收事件」只開放 live 工具讀取，不啟動模型。
3. 要自動處理，先選擇已安裝的原生 `codex.exe`，再勾「自動交給專用 agent（會使用模型額度）」。這是另一個明確開關；原本接收勾選不會自動升格成模型授權。
4. 自動模式要求接收開關、既有 MCP SDK、既有 Codex 登入及已初始化的每日預算。缺少任一條件時顯示原因，pending 保留。
5. 「暫停」合作停止採集與 dispatcher；「暫停並結束」須核對本工具子程序退出。X 只縮小，程式仍等待。

自動選擇與原生執行檔路徑保存於忽略的 `data/agent-automation.json`。單純開視窗或讀設定不啟動模型；之後明確按開始才沿用已保存選擇。不要將此檔或執行資料提交 Git。

應用保持執行時，不因一小時或每日五件而退出。每日五次是模型任務上限，不是採集上限；用完由程式等到下一日，期間不叫模型。關機／登出會結束應用；登入自動啟動仍需另行批准排程，不能由本功能推論已完成重開機恢復。

## 一次前置檢查

在本專案的一般權限 PowerShell，沿用原本正常登入，不設定或搬移 `CODEX_HOME`、auth 或 runtime：

```powershell
py -3.13 --version
py -3.13 -B -c "import mcp; print('installed MCP SDK available')"
$codexExe = (Get-Command codex.exe -CommandType Application -ErrorAction Stop).Source
& $codexExe --version
& $codexExe login status
py -3.13 -B scripts/eventguard.py budget status
```

若 PATH 指到 `.cmd`／`.bat`／`.ps1`，在同一既有安裝找原生 `codex.exe`，用其完整路徑；不要下載替代品。本機這次找到的版本路徑在 `AppData/Local/OpenAI/Codex/bin/<版本目錄>/codex.exe`，版本目錄會改，不能永久照抄。

預算第一次建立須遵守 [AGENT_BUDGET](AGENT_BUDGET.md)：先核實今日已啟動數，再用 `budget initialize --known-used N`。不知道就用預設保守初始化，當日不新增任務。不得換 run/source/state 目錄或刪 DB 重置。既有登入成功不代表事件接收成功。

## 不經 GUI 的持續 dispatcher

以下只示範啟動已存在的來源，**不會啟動採集器**。執行真模型之前須確認資料及模型授權。合成驗收使用自己的既有 source；正式來源還必須明示 `--allow-live` 且接收開關開啟。

```powershell
py -3.13 -B scripts/eventguard_agent.py watch --run-dir reports/agent-watch-NEW --source-dir reports/your-synthetic/source --state-dir reports/your-synthetic/inbox --codex-executable $codexExe --max-seconds 180 --execute
```

`watch` 的 `--max-seconds` 是每次 CLI 任務期限，不是整個等待程式壽命。此時 terminal 要保留；GUI 版本由應用持有。舊 `run` 是有限驗收相容入口。檢視／合作停止：

```powershell
py -3.13 -B scripts/eventguard_agent.py status --run-dir reports/agent-watch-NEW
py -3.13 -B scripts/eventguard_agent.py stop --run-dir reports/agent-watch-NEW
```

| 狀態 | 意義與下一步 |
| --- | --- |
| `waiting` | 沒有可交付事件，Python 等待，沒有新模型任務 |
| `running` | 一個事件正在專用 CLI 處理 |
| `waiting_budget` | 當日用量或首次歷史未知；保留 pending，程式繼續等待 |
| `waiting_disabled` | 接收開關關閉，沒有新任務 |
| `waiting_attention` | 失敗、權限、預算證據等需人類檢查；同事件不自動重試模型 |
| `pending_child_exit` | 尚不能證明子樹退出，不重啟；查原始退出回條 |
| `stopped` | 合作停止；同時核對 `child_exited=true` |

來源與 inbox 只綁定一次。不要刪鎖、換 inbox 或並開多個 dispatcher。錯誤後可由人類查看／接收，或在檢查證據與授權後明確重試。詳見 [LIVE_CHANNEL](LIVE_CHANNEL.md)。

## 讓目前聊天看到四個工具

本次已批准的 `.codex/config.toml` 是專案本機設定，忽略、不提交。新環境先建立自己的隔離合成 operator root（已存在時改新名稱，不覆寫）：

```powershell
$operatorRoot = Join-Path (Get-Location) 'reports/chat-MCP-NEW'
New-Item -ItemType Directory -Path $operatorRoot -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Path "$operatorRoot/config", "$operatorRoot/playbooks" | Out-Null
Copy-Item -LiteralPath 'config/default.json' -Destination "$operatorRoot/config/default.json"
Copy-Item -LiteralPath 'playbooks/default.json' -Destination "$operatorRoot/playbooks/default.json"
py -3.13 -B -c 'import sys; from pathlib import Path; sys.path.insert(0,"src"); from eventguard.events.store import EventStore; from eventguard.synthetic import make_synthetic; EventStore(Path(sys.argv[1])/"data/test").enqueue(make_synthetic("coverage")); print("synthetic queued")' $operatorRoot
```

這只是程式入列，尚未接收，也不呼叫模型。以下是可移植範本；`<...>` 必須換成該主機已核對路徑及上面 `$operatorRoot`：

```toml
[mcp_servers.eventguard_test]
command = "<既有 Python 3.13 的 python.exe>"
args = ["-B", "<專案>/scripts/eventguard_inbox_mcp.py", "--operator-root", "<專案>/reports/<合成驗收>/operator", "--namespace", "test"]
enabled_tools = ["list_events", "inspect_event", "receive_event", "ack_event"]
startup_timeout_sec = 20
tool_timeout_sec = 30
```

使用 TOML 合法字串；Windows 路徑可用 `/`。`operator root` 是含 config/playbooks/data 的根目錄，不是 SQLite 檔；其他操作見 [共用介面](HUMAN_AGENT_INTERFACE.md)。專案必須已獲 client 信任；不要自動改信任或全域設定。

client 載入設定後，核對**當前 agent 工具清單**是否出現四工具，接著實際 list／receive／inspect／ACK，不能只看設定檔存在或 `/mcp` 名稱。若沒出現，記錄 client 版本、專案位置及錯誤，使用 client 提供的重新載入方式；找不到入口時不要假裝已接通。

本主對話於 2026-10-23 確實完成四工具呼叫、同 event/query 補收及冪等 ACK，見 [EVIDENCE](EVIDENCE.md)。先前清單延遲出現的精確原因尚未確定，不能宣稱某個 Restart 動作已解決。這份專案設定只接合成資料，沒有接正式 live 事件。

## 接手 agent 必讀

若要讓agent使用日常完整操作介面，operator adapter現有14工具：capabilities、status、overview、observation、start_monitor、stop、monitor_once、list_events、inspect_event、diagnose_event、receive_event、ack_event、retry_event、report。開始／停止共用既有背景核心，不啟用模型；工具能力表見 [HUMAN_AGENT_INTERFACE](HUMAN_AGENT_INTERFACE.md)。現行eventguard_test仍只批准四工具及合成資料，完整正式接線需另外核對scope，不能把下列工作方式當成已取得正式資料權限。

- 先讀 AGENTS、README、STATUS、HANDOFF，核對分支／HEAD／未提交工作與當前程序；不要重做舊驗收或碰正式 backlog。
- 核心順序：`Monitor → EventStore → QueueInbox → agent_dispatch → 單次 CLI/MCP → query/result → 原來源 ACK`。事件先落盤；提示不含事件 ID／內容，工具才提供最小七欄。
- dispatcher 用單次 `-c` 設定綁定一個事件，read-only、shell 關閉，關閉此專案的 `eventguard_test`，不寫全域 MCP、不複製登入。
- 要稱自動通路成功，必須有「先無事件等待 → 程式入列 → 實際 CLI receive/query/ACK → ID 集合相同 → 自然退出」證據。fixture、SDK、fake CLI、手動聊天及真 CLI 各自記錄。
- 執行資料含本次 JSONL／內部記錄，不上傳；文件只放必要摘要。無事件不啟動模型，錯誤不能拿其他來源／新目錄重試來遮掩。

官方依據（2026-10-23 查核）：[Codex 非互動執行](https://learn.chatgpt.com/docs/non-interactive-mode)、[MCP 設定](https://learn.chatgpt.com/docs/extend/mcp)。`--ignore-user-config` 跳過使用者 config，不更換登入；`--ephemeral` 不建立可續接會話。實際可用範圍仍以本機版本及工具回傳為準。
