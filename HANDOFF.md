# EventGuard 接手

以最新使用者決定為準。讀 AGENTS、README、STATUS 與維護目標。

必做範圍是本機產品。CLI／Web 事件檢視、可設定規則、耐久處置狀態、七來源頁、本機通知與單一 run 入口。

MCP 接線、閒置喚醒及開機自啟均為選配。它們不再阻擋工作。不要要求重開 Codex、proxy 探測、登入任務或排程。本輪全部不做。

本批基底為 `98968ba4435fa178a4b8d05cc721150440f46186`。分支沿用 `feat/local-codex-acceptance`。保留原有 research 與附件。

## 主要入口

- `EventGuard.cmd run`：CLI → application → 既有 application-owned supervisor；同時開本機 Web 與通知。
- `events/catalog.py`：全庫篩選、分頁、詳情。查閱不建資料庫。
- `events/store.py`：event_dispositions 保存四種處置狀態。與 delivery／ACK 分開。
- `rules/configured.py`：讀 config/rules.json。Monitor 每輪重讀。只分類，不執行命令。
- `source_status.py`：只讀保存觀察。顯示七來源、時間、原因與建議。
- `notifications.py`：本機高嚴重度通知。保存成功回條。失敗可重試。
- `web.py`：只綁 127.0.0.1。固定路由。來源核對與 CSRF 檢查。事件只作文字顯示。

按 Ctrl+C 關閉 Web，並合作收尾本應用新啟動的監看。只清理本工具持有的 Job。不收養其他 client 的程序。不啟動模型。

## 驗證與提交

先完成功能，再統一測試。新功能測試在 test_event_catalog、test_configured_rules、test_product_sources、test_local_notifications、test_local_product。

本批唯一新 reports 批次為 local-product-001。它對應本輪產品功能。具體命令、結果及限制見 EVIDENCE。fixture／HTTP／合成 Job／Windows 通知 API 與真實主機採集分開。

文件與功能集中在同一個 commit。不提交執行資料。不做文件單獨提交。不推送。

既有七來源實機與真工具接收證據保留在歷史 EVIDENCE。不得重寫為本批新碼已通過 24 小時、重開機或真漏洞驗證。
