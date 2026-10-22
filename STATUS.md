# EventGuard 現況

更新：2026-10-23。當前程式提交 `1e90a5398c5d4c555924bffb70bb77cb429dd782`，分支 `feat/local-codex-acceptance`；本次先整理文件，程式未改。

本批文件與目標已落地，README 的隔離 fixture 快速開始已實際通過；原始回傳與相對連結檢查見 [EVIDENCE](docs/EVIDENCE.md) 的文檔節。沒有重跑或變更 Phase 4 完整程式驗證。

| 項目 | 已具備 | 尚未證明 |
| --- | --- | --- |
| 獨立使用 | 人類 CLI、確定性監看、事件檢視／查證／報告；共用 OperatorAPI | 無須 agent 即能運作，不代表全天候驗證完成 |
| 七來源 | native／fallback 契約、結構化拒讀；Phase 1 一般權限實測 | Defender／processes partial、tasks unknown；未重驗重開機後 coverage |
| 程序治理 | 原子加入私有 Job、寬限及 Job 內清理、退出回條、monitor_gap | gap 為 fixture 驗證，未做真登出／重啟故障注入 |
| 容量 | ACKed 保留／清理、inbox 完成回條、dispatcher 輪替、滿載恢復 | 有限保留／去重窗；長時資源與全部歷史檔案總量未驗證 |
| agent 介面 | 可選 SDK stdio 共用操作；舊有限 CLI 通路證據保留 | 本輪沒有真模型；不承諾續接任意桌面聊天 |
| 部署 | 前景啟停，排程 dry-run | 沒有服務、自啟或正在執行的長期監看 |

測試數、Python、命令、commit、scope 與本機證據路徑統一見 [EVIDENCE](docs/EVIDENCE.md)。歷史時間日誌已移出本頁；不將 fixture／SDK／fake CLI 與 Windows provider、真 agent 結果互相升格。

[24 小時 soak 計畫](docs/SOAK_PLAN.md) 尚未執行。事件、名稱及工具輸出均為不可信資料；未知或 partial 不代表安全，ACK 不代表診斷／結案。

下一個程式實作是 **Phase 5 收斂**：先做路徑及測試對照，再整併；Phase 6 文件整理已先落地。具體完成條件見 [維護目標](docs/MAINTENANCE_GOAL.md)，接手方式見 [HANDOFF](HANDOFF.md)。

本輪不呼叫模型、不提權、不開網路、不下載安裝、不動其他程序、不啟用排程；Phase 7 真實狀態注入與長時執行仍須先提出計畫並取得批准。執行資料、憑證、Codex home 與私人歷史不上傳。
