# EventGuard 現況

更新：2026-10-23。分支 `feat/local-codex-acceptance`；本批 Phase 5 的程式／來源 commit 對照與測試數統一見 [EVIDENCE](docs/EVIDENCE.md)。

本批讓新驗收與正式派送共用 QueueInbox、command/capture/assessor，bridge 已隔離至 contrib；舊資料格式及測試保留，舊批次 CLI 只核對既有證據。原生 coverage 與長時能力沒有在這批升格。

| 項目 | 已具備 | 尚未證明 |
| --- | --- | --- |
| 獨立使用 | 人類 CLI、確定性監看、事件檢視／查證／報告；共用 OperatorAPI | 無須 agent 即能運作，不代表全天候驗證完成 |
| 七來源 | native／fallback 契約、結構化拒讀；Phase 1 一般權限實測 | Defender／processes partial、tasks unknown；未重驗重開機後 coverage |
| 程序治理 | 原子加入私有 Job、寬限及 Job 內清理、退出回條、monitor_gap | gap 為 fixture 驗證，未做真登出／重啟故障注入 |
| 容量 | ACKed 保留／清理、inbox 完成回條、dispatcher 輪替、滿載恢復 | 有限保留／去重窗；長時資源與全部歷史檔案總量未驗證 |
| agent 介面 | 可選 SDK stdio 共用操作；舊有限 CLI 通路證據保留 | 本輪沒有真模型；不承諾續接任意桌面聊天 |
| 開發／部署 | 單一建議驗收入口、既有 Python 3.13 解析；CI 雙 scope 設定，前景啟停、排程 dry-run | CI 未遠端執行；沒有服務／自啟，本批未啟動長期監看 |

測試數、Python、命令、commit、scope 與本機證據路徑統一見 [EVIDENCE](docs/EVIDENCE.md)。歷史時間日誌已移出本頁；不將 fixture／SDK／fake CLI 與 Windows provider、真 agent 結果互相升格。

[24 小時 soak 計畫](docs/SOAK_PLAN.md) 尚未執行。事件、名稱及工具輸出均為不可信資料；未知或 partial 不代表安全，ACK 不代表診斷／結案。

Phase 5 的 [路徑對照及相容界線](docs/DELIVERY_CONSOLIDATION.md) 已落地，Phase 6 閱讀入口已整理。下一步是 [Phase 7 計畫](docs/WINDOWS_VALIDATION_PLAN.md) 的當次範圍批准；未執行注入或重啟。每日五次耐久總額仍是缺口，不能把一輪最多五次寫成每日預算。

本輪不呼叫模型、不提權、不開網路、不下載安裝、不動其他程序、不啟用排程；Phase 7 真實狀態注入與長時執行仍須先提出計畫並取得批准。執行資料、憑證、Codex home 與私人歷史不上傳。
