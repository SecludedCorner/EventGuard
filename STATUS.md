# EventGuard 現況

更新：2026-10-23。分支：`feat/local-codex-acceptance`。本批基底：`bb6ecff`。

EventGuard 是本機程式。採集、規則、保存、CLI／Web 與通知不需要模型。

## 新增：公告追蹤與適用性

- 普通背景程序定時擷取。提供 `advisories start / status / stop`。不建立服務、排程或開機自啟。
- 18 個可設定官方來源。支援 JSON、RustSec TOML、RSS／Atom 及有界 HTML。
- 條件請求、快取、退避、速率限制、解析失敗與新鮮度。失敗不當成沒有漏洞。
- 只讀允許的 lockfile、manifest 或人工 facts。不執行工具鏈、套件或 build.rs。
- 版本、feature、TLS roots、部署、backport、核心模組與可達性分開判讀。缺證據保留未知。
- SQLite 保存來源、別名、分元件證據與待送變化。重啟去重。滿載明示阻擋，不丟 pending。
- `advisory.changed` 沿用原 EventStore、QueueInbox 與 ACK。snapshot 仍為七欄。
- CLI／Web 可篩選資安公告事件。`advisories cases --event-id <ID>` 查本機完整證據。

操作與事件處理表見 [ADVISORY_TRACKER](docs/ADVISORY_TRACKER.md)。官方查核與未知映射見 [ADVISORY_SOURCES](docs/ADVISORY_SOURCES.md)。

## 本批驗證

命令、測試數、失敗與修復只列 [EVIDENCE](docs/EVIDENCE.md)。唯一新證據批次是 `reports/advisory-tracker-001`。程式、測試與文件集中提交。不提交執行資料或私人研究。

有限實抓：ZDI 六 ID 齊全，32005 為 ConnMan。RustSec 三案、Rust feed、uv 與 CVE API 可讀。LKML／kernel git TLS 驗證失敗；Debian 本次逾時。未繞過。

實抓公告加合成本機資產重播：8 案件、10 事件。生成／收件／query／ACK ID 集合相同。第二輪無新事件。這是後端契約驗證，不是真模型或主機適用性證明。

Windows 隔離背景 start／status／stop 已驗證。私有 Job 自然退出。正式公告背景未啟用。既有監看停止設定不變。沒有呼叫模型或變更 dot 追蹤。

## 限制與待批准

預設盤點路徑為空。正式主機適用性未知。Linux 資料目前由操作者提供，標 `user_asserted`。HTML 只證明 ID 出現；不能自行確認修補 commit 或發行版套件映射。

七欄摘要可供 agent 收件。它不足以診斷完整漏洞。完整證據留本機。未擴大 agent 查詢授權。

agent 本輪未啟用。固定預算 status 目前回 `budget_unavailable`，剩餘用量未知。沒有初始化或重置。每日上限仍為五個任務，含驗收與失敗。

正式背景 start 與真模型驗收仍待批准。需要指定允許盤點路徑、來源頻率及有限任務數。無需 Codex 重啟、proxy、登入任務或排程。

公告 emitted 帳本沒有足夠 ACK 完成與退出保留證據前不自動刪除。滿載 blocked，可核對後調整上限。pending 始終保留。

24 小時 soak、正式長期 HTTP、實際部署版本與 dot 交接尚未驗證。原 dot 追蹤保留。ACK 不是漏洞修補或案件結束。

Codex 主聊天 MCP、閒置喚醒及開機自啟仍是選配。它們不阻擋本機產品。
