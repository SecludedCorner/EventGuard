# EventGuard 本輪維護目標

更新：2026-10-23。依使用者「全面盤點後實踐、由上而下、兩層子代理、功能完整後統一測試」執行。本批基底 `d4257437757a701874c6f00de6022340bff2bc94`，沿用 `feat/local-codex-acceptance`，保留研究與執行資料，不 reset/clean。前批預算／入口目標已完成，本批以實際使用流程補缺口。

人類能啟動監看、看到來源進度與資料、了解事件、明確查證／接收／ACK、匯出報告、合作停止及再啟動。agent 使用同一核心，是可選介面；沒有 agent 或事件時不呼叫模型。架構、盤點與 ownership 見 [USABILITY_IMPLEMENTATION](USABILITY_IMPLEMENTATION.md)。

## 本批完成條件

| 要求 | 實作與驗證入口 |
| --- | --- |
| 慢來源有進度、heartbeat；已返回資料不因後續停止消失 | monitor／collectors progress；test_monitor_progress、test_collector_progress |
| 七來源保存資料可直接看，列數／截斷／拒讀／過期／unknown 分明 | Runtime.observation、overview／sources；CLI workflow 與獨立七來源唯讀 probe |
| 人類完成事件檢視、固定查證、receive/query/ACK、retry 與報告 | 共用 OperatorAPI；實際 CLI 子程序與 SQLite ID 集合核對 |
| persistence／resolved／listener 正確查證綁定，PID 重用不補歷史 | rules／diagnostics／native binding；test_diagnostic_guidance、test_listener_identity |
| 文字與 JSON 都可用，保留 namespace，控制字元不影響終端 | presentation／CLI／cmd；test_cli_workflow |
| stdio 使用相同核心並守 launcher scope | SDK adapter；真 Python stdio＋合成資料的十三工具與 EOF exit；不是 agent 驗收 |
| 未確認子樹不覆蓋、不重開；僅 Query 私有 Job 證明退出後恢復 | Runner／耐久 shutdown gate；test_monitor_progress、test_runtime_atomic |
| 人類接手不冒充 agent 成功、不清預算、不歸檔未知退出 | dispatcher／QueueInbox；test_dispatch_takeover、test_storage_retention |
| 完成功能後統一 Windows/full/mock，ID／退出／commit 可對照 | scripts/verify.py；[EVIDENCE](EVIDENCE.md) 為數字／命令唯一入口 |

兩層互斥 ownership 開發已獲使用者授權。子代理只實作與寫案例，不各自跑整套或提交；主線整合、交叉審查、統一測試、處理實際失敗後集中提交，不推送／手動 CI。不自行建立自動喚醒或永久執行。

## 保持的界線

- 一般權限、唯讀 Windows、既有 Python 3.13 標準庫；沒有真 Codex／模型、UAC、下載安裝、改安全設定或其他程序處置。
- 不永久註冊 MCP、不啟用服務／排程／自啟；stdio 協定測試不代表目前聊天已載入工具或 agent 已收到。
- 每日五次／全域 unknown-exit／每事件限制保留；正式預算不初始化。ACK 只代表收到，不等於修復或結案。
- pending/retry/未 ACK failed 與未知證據保留；容量／去重／接收證據有有限窗，沒有永久 exactly-once 或防同使用者竄改承諾。
- [Phase 7](WINDOWS_VALIDATION_PLAN.md) 注入、登出／重開機、[24 小時 soak](SOAK_PLAN.md) 與真模型未執行，需當次批准。不新增來源、GUI、Linux 原生採集、雲端服務或漏洞平台。

有限流程完成後回報實際能力、證據 scope 與未驗證，不以舊測試或 synthetic 冒充實機安全／長期可靠性。
