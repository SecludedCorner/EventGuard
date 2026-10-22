# EventGuard 現況

更新：2026-10-23。分支 `feat/local-codex-acceptance`；本批基底 `d4257437757a701874c6f00de6022340bff2bc94`。受測來源、commit、測試數與命令統一見 [EVIDENCE](docs/EVIDENCE.md)。

本批由上而下完成操作流程：逐來源進度與保存觀察、可讀 CLI、overview/sources、事件查證與明確 receive/ACK/retry、報告、合作停止與重啟閘道。核心獨立，agent 可選；一般權限七來源各呼叫一次，沒有啟動模型或持續監看。架構／盤點見 [USABILITY_IMPLEMENTATION](docs/USABILITY_IMPLEMENTATION.md)。

| 項目 | 已具備 | 限制／尚未證明 |
| --- | --- | --- |
| 獨立操作 | 文字／JSON CLI、cmd 與共用 OperatorAPI；保存來源、查證、receive/query/ACK、單事件 retry、JSON/HTML 報告 | ACK 只表示收到，不是診斷、修補或結案；不自動啟用背景監看 |
| 七來源 | 固定七來源一般權限實測；原生 listener 當次程序身分、結構化拒讀 | listeners/processes/Defender partial、tasks unknown；細節／筆數見 EVIDENCE，不繞過權限 |
| 可核查狀態 | 逐來源進度／heartbeat／筆數；安全來源投影與 freshness；namespace 隔離、報告 total/truncated | 保存最多每來源 200 列／1 MiB；無 watchdog，過期／拒讀／未知不代表安全 |
| 共用工具 | stdio 十三工具與 CLI 共用相同核心、固定 launcher scope；合成資料實際 request/response 與 EOF exit | 尚未在本次真 agent/client 載入；不宣稱已接上目前聊天 |
| 投遞入口 | QueueInbox 共用 command/capture/assessor；legacy run/retry、generic capture CLI 退役；舊 status 純讀 | 真 agent 與任意桌面聊天續接不是本批驗收範圍 |
| 耐久預算 | 同安裝 UTC+08 每日五次，涵蓋 dispatch/acceptance/retry；先扣帳、一次性 argv/prompt 綁定、每事件上限、全域 unknown-exit gate | 正式帳本未初始化、沒有真模型；非帳戶級防竄改；時間與容量界線見 [預算契約](docs/AGENT_BUDGET.md) |
| 程序治理 | 私有 Job、寬限／有界清理；同輪與跨重啟未知退出閘道；Windows 共享替換有界重試；monitor_gap | gate／gap 故障為 fixture；未做真登出／重啟；缺 Job 身分保持阻擋 |
| 容量與保留 | pending/retry/未 ACK failed 保留；人類合法接手可記 received_without_agent_proof，保留 attempts／預算與失敗語意 | 有限保留／去重窗；接收證據先輪替而無法重證時保持背壓，不猜成功 |
| 開發／部署 | Python 3.13 stdlib 核心、明示 mock/full scope、排程 dry-run | CI 未遠端執行；沒有服務／自啟／部署或全天候承諾 |

[24 小時 soak](docs/SOAK_PLAN.md) 與 [Phase 7 實機計畫](docs/WINDOWS_VALIDATION_PLAN.md) 尚未執行，仍需當次批准。事件、名稱與工具輸出均為不可信資料。漏洞研究保留於獨立研究目錄，本批不新增感測器。

未提權、下載安裝、改安全設定、啟用排程或執行模型。執行資料、憑證、Codex home、私人歷史及完整會話不上傳；原有 docs/research/ 保留。本批驗證與失敗紀錄見 EVIDENCE，不將 fake CLI、SDK、fixture 升格為真 agent／實機採集或長期可靠性證據。
