# EventGuard 現況

更新：2026-10-24，UTC+08。分支：`feat/local-codex-acceptance`。本批基底：`9903ad5`。

EventGuard 可獨立採集、比對、保存及顯示。正常等待與查閱不呼叫模型。
CLI、Web及十個選配MCP工具共用Application與事件庫。MCP斷線不關閉應用。

## 使用

`.\EventGuard.cmd run` 前景啟動採集、Web與通知。
`.\EventGuard.cmd run --idle` 只開控制介面。預設 `http://127.0.0.1:8765`；埠被占用可指定 `--port 8877`。

已開啟應用後，使用 `app status/start/pause/resume/stop/shutdown` 或GUI/MCP操作。
stop只停採集，介面仍可查詢及再次開始。shutdown提出關閉要求，實際退出另核對。
GUI顯示真實狀態、最近動作、CLI/GUI/MCP來源與失敗原因。

stdio固定為observer。沒有App也能列工具，但回blocked，不建立第二owner。
明確讀status/capabilities可重新核對同root/namespace。變更不自動轉新instance；舊操作ID仍受保護。
設定、工具載入、收到事件、閒置喚醒分開。操作指南見 [APPLICATION_MCP](docs/APPLICATION_MCP.md)。

## 本批功能

- 通知先耐久保存意圖。回條不明時顯示未知，不盲目重送。事件仍pending。
- 公告頁、App status與公告事件詳情顯示有界公開來源、時間、新鮮度與適用性。
- 不公開本機inventory/facts/path/PID/原始evidence。自動派送仍只有既定七欄。
- 新增NVIDIA CSAF停用範例。壞子項與好子項隔離；partial不洗成success，不覆寫完整cache。
- 公告及十類對抗文字都只作資料。未知不變安全。處置狀態不ACK。
- 專用有限agent派送明確停用完整App MCP，避免擴大七欄profile。

## 實際驗證

相關測試、真SDK stdio/SSE、真Windows自有Job、原收件/ACK恢復與真瀏覽器均已執行。
瀏覽器確認同一instance、MCP處置同步、GUI改已處理後刷新保存；兩事件仍pending、ACK零。
通知中斷與滿載恢復、重連、舊operation fencing及預算政策已定向驗證。
通知圖示不可用的skip及先前示範失敗均保留。沒有把fixture升格為主機安全或真agent驗收。
測試數、命令、時間、Python及證據只見 [EVIDENCE](docs/EVIDENCE.md)。
本機新功能證據在 `reports/application-lifecycle-001`、`reports/notification-intent-001`及`reports/nvidia-advisory-001`。
本批測試/示範程序均有退出證據。未強停、未啟用正式長期監看、未改正式控制或預算。

## 選配與未驗證

公開Codex入口研究見 [AGENT_EVENT_DRIVEN](docs/AGENT_EVENT_DRIVEN.md)。普通本機桌面任務閒置喚醒仍未驗證。
OpenOctopus提案與工作包見 [OPENOCTOPUS_EVENT_PROTOCOL](docs/OPENOCTOPUS_EVENT_PROTOCOL.md)，尚未在外專案實作。
本批沒有重註冊聊天MCP；先前載入的工具不能當成最新十工具熱載入證明。
真模型驗收需另核定一次有界範圍；本批產品模型為零。既有dot追蹤未停用。
未做七來源當前主機掃描、24小時soak或重開機。不宣稱全天候通過。
不建立服務、排程、自啟、proxy或新登入。不下載安裝、不提權、不推送。
