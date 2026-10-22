# EventGuard 現況

更新：2026-10-23。分支 `feat/local-codex-acceptance`；本批基底 `3b0461988c6bc36f13d514e1e5263c91b4715123`。受測來源、commit、測試數與命令統一見 [EVIDENCE](docs/EVIDENCE.md)。

核心可獨立監看、保存事件、檢視與匯出；agent 是可選介面，無事件不啟動模型。本批收斂殘留啟動入口、共用每日耐久預算與未知退出閘道，並補人類可核查的狀態，沒有啟動真模型或長期監看。

| 項目 | 已具備 | 限制／尚未證明 |
| --- | --- | --- |
| 獨立操作 | CLI 與共用 OperatorAPI；保存觀察、事件綁定查證、JSON/HTML 報告 | ACK 只表示收到，不是診斷、修補或結案 |
| 七來源 | native/fallback 契約、結構化拒讀；保留 Phase 1 一般權限證據 | Defender/processes partial、tasks unknown；本批未重掃或重驗 provider |
| 可核查狀態 | last_report 與目前 owner 單 PID+建立時間核對分開；heartbeat/coverage freshness、逐 namespace 故障、報告 total/truncated | 無獨立 watchdog；缺資料、過期、future、拒讀為 unknown，不能證明安全 |
| 投遞入口 | QueueInbox 共用 command/capture/assessor；legacy run/retry、generic capture CLI 退役；舊 status 純讀 | 真 agent 與任意桌面聊天續接不是本批驗收範圍 |
| 耐久預算 | 同安裝 UTC+08 每日五次，涵蓋 dispatch/acceptance/retry；先扣帳、一次性 argv/prompt 綁定、每事件上限、全域 unknown-exit gate | 正式帳本未初始化、沒有真模型；非帳戶級防竄改；時間與容量界線見 [預算契約](docs/AGENT_BUDGET.md) |
| 程序治理 | 私有 Job、寬限／有界清理；統一嚴格退出回條，強停不判自然成功；monitor_gap | gap 為 fixture；沒有真登出／重啟注入；不碰其他程序 |
| 容量與保留 | pending/retry/未 ACK failed 保留；已 ACK 清理、完成帳本輪替及滿載恢復；預算保留用量與 retired-token 摘要 | 有限保留／去重窗；預算日彙總與 token 摘要滿載時明確阻擋，沒有無限歷史保證 |
| 開發／部署 | Python 3.13 stdlib 核心、明示 mock/full scope、排程 dry-run | CI 未遠端執行；沒有服務／自啟／部署或全天候承諾 |

[24 小時 soak](docs/SOAK_PLAN.md) 與 [Phase 7 實機計畫](docs/WINDOWS_VALIDATION_PLAN.md) 尚未執行，仍需當次批准。事件、名稱與工具輸出均為不可信資料。漏洞研究保留於獨立研究目錄，本批不新增感測器。

未提權、下載安裝、改安全設定、啟用排程或執行模型。執行資料、憑證、Codex home、私人歷史及完整會話不上傳；原有 docs/research/ 保留。本批驗證與失敗紀錄見 EVIDENCE，不將 fake CLI、SDK、fixture 升格為真 agent／實機採集或長期可靠性證據。
