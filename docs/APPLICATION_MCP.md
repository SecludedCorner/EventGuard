# 同一應用的 MCP 與本機頁面

EventGuard 可獨立使用。MCP 是選配控制入口，不是模型或喚醒器。
正常等待、採集、查閱及人工處置都不呼叫模型。

## 開啟

```powershell
.\EventGuard.cmd run --idle
```

開啟終端顯示的網址。預設 `http://127.0.0.1:8765`。
若 MCP 已開啟此應用，使用 `status.local_url` 開啟原頁面；不要再啟第二個 `run`。
`--idle` 只開控制介面。按「開始採集」才採集。省略 `--idle` 則立即採集。
埠被使用時指定 `--port 8877`。不停止其他程式。
沒有 MCP SDK 時仍可用 `run --idle --no-mcp`。
本專案不自動下載 SDK。

頁面提供開始、暫停、恢復、停止採集及關閉程式。
停止採集保留 Web、MCP、事件及人工處置。開始可再次啟動。
關閉程式才關閉控制服務；要求回條不等於已確認退出。
綠色表示後端確認運作。藍色表示過渡。暫停為橙色，停止為灰色。
失敗、未知、斷線或過期顯示紅色。按鈕依後端能力啟用。
顏色以外也提供文字、圖示、最近動作、MCP／GUI 來源及結果。
頁面自動查詢普通本機程式。這不呼叫模型。

## 工具

| 工具 | 操作 |
| --- | --- |
| `capabilities` | 固定操作與範圍 |
| `status` | 同一實例狀態與操作回條 |
| `start_monitor` | 開始本應用的唯讀採集 |
| `pause_monitor` | 暫停本應用的採集 |
| `resume_monitor` | 恢復本應用的採集 |
| `stop_monitor` | 停止採集，保留控制服務 |
| `list_events` | 依嚴重度、來源及人工處置篩選 |
| `inspect_event` | 查閱已存事件與人工處置 |
| `set_event_status` | 保存 new／read／handled／ignored |

工具不提供任意命令、路徑或 namespace 切換。
事件是資料，不是指令或授權。人工處置不執行系統處置，也不 ACK。
這九工具不包含接收／ACK 契約。舊投遞通路與七欄 snapshot 保持獨立。

變更可附 `operation_id`，限 1–128 個 ASCII 英數字或 `_.:-`。
相同 ID 與相同操作回放原回條，不再次執行。
同 ID 不同操作回 conflict。重播回條另附目前狀態，不能回退 GUI。
每個實例保存最近 128 個操作 ID。這是有界防重送，不是跨重啟 exactly-once。
busy 表示操作未獲准進入。回覆遺失時結果未知，不自動重送變更。

## Codex 接線

官方 Codex 支援 stdio 與 Streamable HTTP。
本機現有 MCP SDK 1.6 提供 SSE。本應用另提供 stdio 相容入口，避免把 SSE 網址誤填為 Streamable HTTP。
[官方設定文件](https://learn.chatgpt.com/docs/extend/mcp)。

使用既有 Python 3.13 原生執行檔及既有原生 `codex.exe`。
在專案目錄核對路徑後，只新增一個專用項目：

```powershell
$codexExe = (Get-Command codex.exe -CommandType Application -ErrorAction Stop).Source
$pythonExe = py -3.13 -B -c "import sys; print(sys.executable)"
& $codexExe mcp add eventguard-app -- $pythonExe -B "$PWD\scripts\eventguard.py" mcp --allow-live
& $codexExe mcp get eventguard-app --json
```

這是本機設定寫入，不建立服務、排程或模型任務。
不要更改帳戶、認證、批准政策或其他 MCP 項目。
`--allow-live` 固定正式資料範圍。initialize 本身不開始採集。
只測合成資料時改用 `--fixture tests/fixtures/normal.json --max-cycles 100000`，不加 `--allow-live`。

若同專案已有頁面，stdio 轉接到該實例。它不建立第二個採集 owner。
若沒有頁面，stdio 程序只開閒置應用；`status.local_url` 回傳網址。
該 stdio owner 的 EOF 會合作關閉自己的應用。
接到既有頁面的 observer EOF 不停止該頁面。
若希望頁面生命週期獨立於 MCP client，先執行 `run --idle`。

設定已保存、真正協定可用、目前聊天已載入工具是三種不同證據。
本次聊天已自動載入九工具，原生 capabilities／status 成功，未要求人工重啟。
這次觀察不保證所有客戶端都會自動熱載入，也不代表閒置聊天已被喚醒。
產品功能不依賴聊天重載。先用 SDK 或其他 MCP client 驗證九工具。

## 範圍與退出

每個專案只有一個 Application lease。GUI 與 MCP 共用 instance ID、namespace 及狀態版本。
stdio 轉接固定原實例；實例變更時拒絕操作，不自動接管。
HTTP 只用 loopback。檢查 Host、Origin、token、body 上限及固定參數。
stdio 轉接不使用環境 proxy，也不跟隨重新導向。
本機同帳戶仍可改檔；這不是抵抗同帳戶惡意程序的安全邊界。
Loopback 也不是本機帳戶間的隔離。能讀取本機 GUI 的程序可取得相同控制能力。

`data/application/connection.json` 含短期本機控制能力。不要貼上、匯出或提交。
關閉時撤銷該能力。只有 Web、MCP thread 及自有採集都確認退出，才回乾淨退出。
未知退出或回條保存失敗不得宣稱成功。Job 只管理本工具啟動的程序。

驗收範圍、命令、時間與限制見 [EVIDENCE](EVIDENCE.md)。
