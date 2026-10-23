# EventGuard 現況

更新：2026-10-24，UTC+08。分支：`feat/local-codex-acceptance`。本批基底：`008a931`。

EventGuard 是本機程式。採集、規則、事件保存、CLI／Web 與通知不需要模型。
主聊天接線、桌面閒置喚醒及開機自啟仍是選配，不阻擋產品。

## 事件驅動的專用 agent

- 新增 `agent start / status / pause / resume / stop`。start、resume 預設只預檢；加 `--execute` 才允許模型。
- 普通背景 host 沿用原 dispatcher、QueueInbox、帳本及固定安裝預算。沒有第三份佇列或代理服務。
- 可設定嚴重度、事件種類及人類狀態。預設選 high／critical、new／read；低事件不擋後方高事件。未選事件仍保留。
- 暫停只擋新派送，不停止採集、不刪 pending、不取消已啟動任務。准入屏障未確認時明示 unconfirmed。
- Web 新增派送頁與事件投遞階段。可暫停或停止。頁面不能啟動或恢復模型。
- 分開記錄工具收件、query、結果、ACK、回合及程序退出。模型用量缺失時顯示未知。
- 新增唯讀 CloudEvents 七欄匯出、嚴格驗證及同 ID 衝突檢查。它不是新接收服務，也不是喚醒證據。
- 原驗收腳本新增 `service` 單事件案例。先等空佇列，再由程式加入事件。預設只準備；真驗尚未執行。

操作見 [AGENT_SERVICE](docs/AGENT_SERVICE.md)。測試數、命令、失敗與修復只記於 [EVIDENCE](docs/EVIDENCE.md)。

## 已驗證與目前啟用狀態

fixture、fake CLI、真本機 HTTP 及 Windows 私有 Job 已分範圍驗證。
隔離空佇列的 host 啟動、暫停、恢復、合作停止與實際 OS exit 0 已通過；無 provider 啟動及殘留。
這不是模型收件或長期背景驗收。最後來源雜湊及退出證據位於 `reports/event-ingress-001`。

正式 agent host 為 `not_started`，未保存啟用。正式監看的停止設定與先前雜湊相同。
固定預算 DB 與 marker 尚未建立；status 回 `budget_unavailable`。沒有初始化、重置或假設當日用量為零。
模型真驗需要有限批准及有效預算。首次歷史未知時，既有保守初始化不發當日新額度。

## 公告追蹤及限制

既有公告背景提供 `advisories start / status / stop / check / cases`。
普通程式擷取、快取、比對、保存與重啟去重。只讀允許的靜態盤點；預設路徑空白，主機適用性未知。
既有實抓、來源失敗及合成後端重播見 EVIDENCE。正式公告背景與 dot 交接仍未啟用。

七欄摘要不足以診斷完整漏洞。完整證據留本機，未擴大 agent 查詢授權。
ACK 只代表收到，不是漏洞已修復、主機安全或案件結束。
預算耗盡、離線、容量滿及保存失敗保留 pending。未知退出不自動再啟動。
24 小時 soak、正式長期背景、真模型 receive→query→結果→ACK→自然退出均未驗證。
OpenOctopus 僅完成 EventGuard 端契約與交接規格；沒有修改另一專案或向其聊天發送指令。
