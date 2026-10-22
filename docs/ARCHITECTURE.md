# 目前架構

目前受測程式及 commit 見 [EVIDENCE](EVIDENCE.md)；此頁映射已存在模組，不把 [遠期設計](TARGET_DESIGN.md) 當完成能力。核心獨立運作，人類與可選 agent 共用 API，正常監看不呼叫模型。

| 區域 | 實作與邊界 |
| --- | --- |
| 人類／agent 共用 | `operations.OperatorAPI`；CLI 與可選 operator stdio 共享狀態、檢視、事件綁定診斷、報告及控制 |
| 採集 | `collectors.windows` 封裝 native／PowerShell 同一契約；native 在 `collectors.worker`／`eventguard_collect.py` 隔離 |
| 子程序 | `processes.JobPopen` 透過建立屬性原子加入私有 Job；所有權以本工具 handle，沒有依任意 PID 終止的路徑 |
| 監看 | `monitor` 分層頻率、單例、取消與 coverage；`monitor_gap` 先耐久補存未觀測區間 |
| 規則／資料 | `rules` 確定性 baseline／diff；`events.store` 原子保存 detector state＋outbox，ACK／回條／review 有限保留 |
| 查證／報告 | `diagnostics` 從事件綁定型別化查詢，輸出 observations／coverage／uncertainties；固定 not_assessed，不 ACK |
| 可選投遞 | `agent_dispatch` 等待佇列；只有已明確批准執行時才啟動短期 CLI，`queue_inbox` 只提供該事件最小摘要與 ACK |
| 舊驗收／bridge | `local_wait` 僅保留舊格式／測試相容；新驗收使用 QueueInbox；雲端 bridge 已移到 `contrib/mcp_bridge` 且停用 |

核心採集／規則／操作層不依賴 MCP SDK；SDK 只在可選 adapter 使用。共享 operator 的 diagnose 與 bound delivery 的 query_evidence 不同：前者明確查目前唯讀來源，後者只重讀保存摘要，詳見 [介面契約](AGENT_CONTRACT.md)。

outbox 在 data/live 或 data/test；inbox state 與 source 分離；測試／驗收在全新 reports 子目錄。不能共用正式執行資料做合成驗收。原始碼、設定、playbook 與 runtime 分層；原始執行資料不提交。

pending／retry／未 ACK failed 不做 TTL 刪除；已完成資料依有限政策輪替。事件、名稱與輸出都不提供命令或授權。SQLite／JSON 可被相同使用者篡改，不是不可變鑑識。

新驗收和正式派送共用 QueueInbox、command/capture/assessor；相容差異見 [收斂對照](DELIVERY_CONSOLIDATION.md)，下一步與完成條件見 [維護目標](MAINTENANCE_GOAL.md)，驗證與限制見 [EVIDENCE](EVIDENCE.md)。
