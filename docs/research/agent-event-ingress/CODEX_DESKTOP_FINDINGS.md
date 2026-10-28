# Codex 桌面事件入口研究

> 保存註（2026-10-28）：以下「目前／本輪／未提交」與政策均指原研究日期及固定基準，不是現行能力、授權或驗收。現況以 [STATUS](../../../STATUS.md) 與 [HANDOFF](../../../HANDOFF.md) 為準。本頁 reports 連結是「本機證據、不隨repo提供」；本次未讀取或上傳 reports 內容。

查核時間：2026-10-23T18:11:13Z（台北 2026-10-24 02:11:13）。

範圍：官方文件、公開 CLI help、已提供的本會話工具契約。沒有發送事件。沒有模型驗收。
未啟動 app-server。未連 control socket。未讀 auth 或 sessions。未改設定或啟用背景。

## 結論

Codex 有受程式控制的任務入口。不能說它在技術上無法被事件喚醒。
但「本機 EventGuard 事件 → 這個既有桌面聊天的閒置新回合」仍未實測。

目前最值得核對的入口是公開的 `codex queue`。其次是應用自己管理的 app-server thread。
一般 MCP 工具可提供事件資料。它本身不能證明閒置新回合已啟動。

## 官方能力與證據

| 入口 | 官方資料／本機證據 | 對現有桌面聊天的結論 |
| --- | --- | --- |
| Codex MCP 工具 | 文件列 STDIO、Streamable HTTP；桌面、CLI、IDE 共用設定。 | 能接工具，不等於能啟動新回合。未建立本機外部事件入口保證。 |
| MCP Events | 官方列 Work web、桌面選 Cloud 的 Work、dots。需 MCP 2.0、耐久訂閱、HTTPS callback。 | 有官方事件喚醒流程。但不能套稱本機 Codex 已支援。 |
| `codex queue` | CLI reference 標 Stable。可用 UUID 或精確名稱指定 session。支援 remote。原生 CLI help 實際存在。 | 是有力候選。文件未直接證明可送到目前桌面後端並從閒置啟動。 |
| app-server | 有 `thread/start`、`thread/resume`、`turn/start`、事件串流。`turn/start` 開始生成。 | 適合由自己的產品管理 thread。不能用任意 thread ID 推定有控制權。 |
| Hooks | 背景 hook 完成時，閒置則等下一個使用者回合。它不會自行開始回合。 | 不可用它宣稱已完成外部事件喚醒。 |
| `codex exec`／SDK | 官方支援腳本任務與程式啟動、繼續、恢復 thread。 | 適合專用有限任務。不能冒稱續接同一桌面聊天。 |
| `codex://` deep link | 開聊天或預填 composer。官方明說不自動送出。 | 可供人工導航，不是無人事件入口。 |
| 本會話 `send_message_to_thread` | 已提供的 host 工具契約可向指定聊天送 follow-up。必須有使用者授權。 | 證明 host 有控制面。沒有證明普通本機程式能使用此內部能力。未呼叫。 |

資料來源：

- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp)，已實開。
- [MCP Events](https://developers.openai.com/plugins/build/mcp-events)，已實開。
- [CLI reference](https://learn.chatgpt.com/docs/cli/reference)，已實開。
- [App-server](https://learn.chatgpt.com/docs/app-server)，已實開。
- [Hooks](https://learn.chatgpt.com/docs/hooks)，已實開。
- [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)，已實開。
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)，已實開。
- [Desktop commands](https://learn.chatgpt.com/docs/app/commands)，已實開。

## 重要細節

### queue 需要實測的不是命令名稱

官方命令是 `codex queue --thread <UUID> --message <TEXT>`。
這可排入既有 session 的文字。
不能只憑 exit 0 就判斷已開始模型處理。

必須另外證明：

1. 指定 UUID 由目標桌面所使用的後端管理。
2. 閒置後真的產生新的 turn。
3. 活動回合中不破壞操作者的互動。
4. 客戶端離線、關閉或重開後，有清楚且耐久的交付結果。
5. 重送同一事件不造成重複付費任務。
6. host 收件、模型開始、工具收件、結果保存、ACK 分開記錄。

現階段未送任何 queue 訊息。未探測私人 socket。

### app-server 可以控制自己管理的 agent

官方流程是 initialize → thread/start 或 resume → turn/start。
等待事件可放在普通程式。它收到事件後才呼叫 turn/start。
`thread/inject_items` 只加資料，不會自行開始新回合。
`turn/steer` 需要活動 turn，不能當閒置喚醒。

官方將 app-server 與 WebSocket 路徑標為實驗性；不保證正式生產工作負載。
stdio 免去新增網路監聽，但不會因此變成桌面聊天的公開附接保證。
default Unix control socket 是文件中的傳輸形式，不是對任意聊天的授權。

### MCP Events 已有標準方向，但有表面限制

官方提供 events/list、subscribe、unsubscribe，以及簽章 webhook。
HTTP 2xx 是 webhook 收件，不是調查完成。
需保留事件 ID、cursor、訂閱狀態；重送要冪等。
本機程式若走此路，就新增 HTTPS 外送、訂閱及 secret 管理。
本輪沒有建立它們。

### Hooks 與通知有方向性

同步 Stop hook 可延續正在結束的回合。這不是任意閒置後的外部事件入口。
背景 hook 閒置完成時，只等下個使用者回合。
`notify` 是 Codex 向外通知已完成回合，方向相反。
不能用永久等候的 hook 或 Stop 迴圈取代耐久事件排程。

`notify` 來源：[Advanced Configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)，已實開。

## 本機 help 實測

只讀原生執行檔的版本及 help。新子程序使用既有 `eventguard.processes.spawn`，執行前加入私有 Job。

```text
codex.exe --version
stdout: codex-cli 0.163.0-alpha.11.2
stderr: 空

codex.exe queue --help
stdout: Queue a message for an existing session
Usage: codex queue [OPTIONS] --thread <THREAD> --message <TEXT>
--thread: Session UUID or exact session name
--remote: ws://, wss://, unix://, unix://PATH
stderr: 空

codex.exe app-server proxy --help
stdout: Proxy stdio bytes to the running app-server control socket
--sock <SOCKET_PATH>
stderr: 空
```

三次均 `exit_code=0`、`child_exited=true`、`remaining_owned_processes=0`、`forcibly_terminated=false`。
它們在 2026-10-23T18:11:06Z 至 18:11:07Z 執行。
原生路徑位於 `%LOCALAPPDATA%\OpenAI\Codex\bin\37f54d68e5533a51\codex.exe`。
PATH 首項另是 npm wrapper；其公開 package metadata 是 0.158.0。
本輪沒有執行 wrapper。不能將兩者版本混用。
另由整合 agent 在台北 2026-10-24 約 02:15 呼叫 `codex_app.check_app_update`，取得唯讀回傳：

```json
{"installedVersion":"26.1016.62342","installedBuildVersion":"21477","installedReleaseChannel":"prod","status":"up_to_date"}
```

這是桌面 app 版本，與上述原生 CLI 版本分開。
`up_to_date` 只表示目前設定更新通道沒有合資格更新。
查核未下載、安裝或重啟。這個版本值不證明 queue 喚醒已支援或驗證。

## 建議順序

1. 保留 EventGuard 的耐久 outbox、七欄 snapshot、預算與 ACK 契約。
2. 先為公開 queue 入口設計一次有限、使用者批准的合成驗收。
3. 若 queue 無法安全識別或控制該桌面 thread，使用專用有限 exec 任務。
4. OpenOctopus 若管理完整互動，可提供自己的 app-server adapter。事件契約不要綁死 Codex。
5. Work／dot 的 MCP Events 作另一 adapter。不要為本機產品強加雲端前置。

不能使用 UI 自動按 Enter、讀寫 session、掃 socket、重複模型 polling 作保底。
無 ingress 能力時顯示 blocked，保留 pending，讓人類仍可從本機產品處理。

## 本輪未證實

- 外部事件可自動喚醒這個現有桌面聊天。
- queue 的排隊回條是否耐久，以及是否提供事件級冪等鍵。
- 桌面與 CLI 的 thread ID、daemon、版本及權限是否完全相同。
- 桌面關閉後是否能處理事件，以及重開後補收語意。
- MCP Events 對本機 Codex 的支援或可用權限。
- 任何真模型、真正接收／query／保存結果／ACK 與自然退出。

本文件是研究。它沒有完成或啟用上述功能。
