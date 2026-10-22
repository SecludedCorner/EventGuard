# EventGuard 本輪維護目標

更新：2026-10-23。使用者已更新並恢復 App goal。基底 `3b0461988c6bc36f13d514e1e5263c91b4715123`、同一 `feat/local-codex-acceptance`；保留既有工作、docs/research/ 與執行資料，不 reset/clean、不重做 Phase 0–6。

目標是收斂既有入口、共用每日耐久預算、未知退出閘道與人類可核查狀態。核心獨立運作、無事件不啟動模型；agent 可選且與人類共用型別化介面。不新增來源、GUI、Linux 採集、雲端服務或代理平台。漏洞研究保留為未來方向。

## 完成條件與核對入口

| 要求 | 實作／證據入口 |
| --- | --- |
| 封閉 legacy run/retry/generic capture 旁路，舊證據可讀且不改寫 | codex_acceptance、acceptance_process；退休零 spawn 與 legacy reader fixture |
| dispatcher 與 acceptance 共用嚴格退出驗證，矛盾／缺失／未知／強停／截斷不判自然成功 | capture_receipt；test_capture_receipt、test_launch_receipts；強停與已知失敗仍可解除已證實退出的 gate |
| 同安裝、所有受管 CLI 共用 UTC+08 每日五次，先原子扣帳、一擊 launch digest、每事件限制、不退款 | agent_budget、capture、dispatcher、delivery_validation；[預算契約](AGENT_BUDGET.md) |
| 換 run/source/state/cwd、換日、鎖釋放、supervisor 退出或 ACK 不解除 global unknown | 耐久 active 與完整 Job/PID+建立時間 proof；跨來源／次日負測 |
| 未知 bootstrap、缺失／損壞／busy／滿載明確阻擋，不重建空帳本 | budget unit／集成 fixture；正式帳本不初始化 |
| 人類與 OperatorAPI 顯示 coverage、freshness、last report/current owner、monitor_gap、pending、預算及阻塞；逐 scope 錯誤、報告 total/truncated | operations、test_operator_status、test_budget_cli；保持七欄對外 snapshot |
| 合成測並發額度、第六次、崩潰、日界、clock、滿載恢復、未知退出、同 event/query 補收、ACK 前失敗，零事件／耗盡零新啟動 | test_agent_budget、test_budget_integration、test_agent_dispatch、test_delivery_consolidation |
| 局部後由主線完整 Windows 與獨立 mock 驗證、集中提交、不推送 | [EVIDENCE](EVIDENCE.md)：唯一數字／命令／來源 hashes／ID／退出／commit 核對入口 |

本輪先以三個有限唯讀子代理預審，再明示互斥檔案 ownership 實作；主線負責共用入口、review、整合、完整測試及提交。子代理不遞迴擴編、不各自提交或重跑完整 suite。全部開發協作與合成 fake CLI 均不是 EventGuard 真模型授權／驗收。

## 保持的界線

- 一般權限、唯讀 Windows、既有 Python 3.13 標準庫；無模型輪詢。
- 不執行真 Codex、不讀秘密或完整 sessions/命令列、不提權/UAC、不下載安裝、不改安全設定／執行政策、不永久註冊 MCP、不啟用服務／排程、不動非本工具程序。
- pending/retry/未 ACK failed 與未知退出證據不刪；有限保留／去重窗，沒有永久 exactly-once 或帳戶級防竄改承諾。
- 事件、名稱與工具輸出是不可信資料；未知、partial、denied、ACK 與診斷均不是安全結論。
- Phase 7 實機注入、24 小時 soak、真模型、敏感或不可逆處置仍須當次批准；先完成其他可獨立工作，再回報具體阻塞。
- 本輪完成須逐項有當前證據並完成集中提交，才結束本輪；不自行部署、永久執行或擴張目標。已授權正常開發不逐步詢問。

Phase 0–6 的各批提交與 scope 保留在 [EVIDENCE](EVIDENCE.md)，不把舊 mock／fixture 數字當新實機成功。[Phase 7](WINDOWS_VALIDATION_PLAN.md) 與 [24 小時 soak](SOAK_PLAN.md) 尚未執行。
