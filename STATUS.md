# EventGuard 現況

更新：2026-10-24，UTC+08。分支：`feat/local-codex-acceptance`。本批基底：`d23c7d3`。

EventGuard 可獨立採集、比對、保存及顯示。正常運作不呼叫模型。
本批完成無模型 MCP／GUI 操作閉環。接線不代表閒置喚醒。

## 使用

已有 MCP 應用可直接開啟 `status.local_url`。本次為 `http://127.0.0.1:53573`。
尚無應用時，`.\EventGuard.cmd run --idle` 只開本機控制介面。
預設網址 `http://127.0.0.1:8765`。埠被占用時指定 `--port 8877`。
開始、暫停、恢復及停止採集保留網頁與事件。「關閉程式」才關閉應用。
省略 `--idle` 即開始採集。不另啟第二個 Application。

GUI 與九個 MCP 工具共用 Application、instance ID、namespace 及處置資料。
頁面自動同步後端狀態、顏色、文字、按鈕、操作來源與結果。
操作 ID 防重送；並行要求回 busy。未知、失敗及斷線不預報成功。
處置狀態不 ACK，也不執行安全處置。pending 保留。
接線與生命週期見 [應用 MCP](docs/APPLICATION_MCP.md)。

## 已驗與證據

真 SDK initialize／tools/list／tools/call、真 stdio、同實例 GUI、雙 client 並行、重送、失敗、重連、重啟保存及合作退出已驗。
主要輸入為隔離合成資料，並非主機資安來源實測。
修正 SSE 跨 loop 的退出 Event，以及 stdin 保持開啟時的關閉卡住。
最終統測與補充測試均通過。通知 skip、早期失敗及逾時回條保留。
命令、時間、Python 版本、測試數與範圍只見 [EVIDENCE](docs/EVIDENCE.md)。
本機證據在 `reports/application-mcp-001`，不提交 Git。
舊失敗截圖有快取限制；已標記並另存真紅色／綠色畫面，不覆寫原檔。

## 接線與啟用狀態

一般使用者 Codex 已註冊專用 `eventguard-app` stdio 入口。
已用完整命令實際初始化與查狀態，核對同一 GUI 後端。
隨後本聊天自動載入九工具。原生 capabilities／status 已實際呼叫成功。
正式 instance 為 `a3b57a57573849249ec9c7196ae3c1ad`，目前 stopped、revision 0、model_calls 0。
這次只讀 live 操作 metadata；沒有讀正式事件或採集。未要求使用者重啟。
較早「新工具尚未載入」的 catalog 保留，另存較晚的原生成功證據。

測試應用、採集及入口探測均已合作退出。Codex 載入的正式控制介面保留閒置，供九工具使用；不是監看或 agent host。
正式停止設定未變。模型預算沒有初始化或重置。
未建立服務、排程、自啟、proxy 或新登入；未改系統安全設定或推送。

## 未驗證

本批沒有重做七來源實機採集、24 小時 soak、重開機或真模型收件。
未驗證桌面閒置喚醒或任意既有聊天續接。
七欄 snapshot、結果／ACK、每日五次預算與保留政策不變。
既有 dot 追蹤未停用。閒置喚醒及開機自啟仍為選配。
