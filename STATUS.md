# EventGuard 現況

更新：2026-10-23。分支 `feat/local-codex-acceptance`，本批基底 `08a4ef8ff7e5762c499b7cb270de1e86a0361822`。測試數、實際命令、時間、限制與 commit 對照統一見 [EVIDENCE](docs/EVIDENCE.md)。

本批完成背景 supervisor、耐久啟停與登入後恢復入口；採集不受每日 agent 預算或一小時期限限制。無事件不呼叫模型，有事件先保存同一 SQLite，交人類或已連接的可選接收者處理。契約及操作見 [BACKGROUND](docs/BACKGROUND.md)。

| 項目 | 已具備 | 實際狀態／限制 |
| --- | --- | --- |
| 背景生命週期 | start/status/stop/serve、固定耐久 enabled/disabled、單一 host lease、普通程式 backoff | 正式 start 已嘗試：執行端外部 Job 使獨立常駐無法證明，回 blocked；沒有正式 host 殘留 |
| 登入後恢復 | 當前使用者 ONLOGON／InteractiveToken／LeastPrivilege XML；無期限、同安裝同資料；source/identity digest 批准 | 正常使用者唯讀查詢：專用 task 不存在；已產生審查計畫，尚未獲批准／建立或 Run。不支援登入前監看 |
| 程序治理 | 原子私有 Global Job、真 kernel keeper 交接、PID＋建立時間、寬限後只清理本工具 Job、真實停止回條 | 受外部 Job 限制不 breakaway；Local 歷史跨 session 保持未知，沒有假裝重開機已驗證 |
| 保存與恢復 | 滿載／保存失敗停止新採集、不前移 baseline；pending 保留；恢復前先保存 monitor_gap | 無法保存期間的變化不能完全重建；ACKed 保留及去重仍有容量／時間窗 |
| 人類／可選 agent | 可讀 CLI/cmd、共用 OperatorAPI、七來源保存觀察、diagnose/receive/query/ACK/retry、JSON/HTML 報告 | ACK 是收到，不是修補或結案；沒有真模型／目前聊天載入／自動喚醒證明 |
| Windows 可見性 | 原生優先、白名單唯讀 fallback、逐來源進度／筆數／拒讀／freshness | 本批沒有再掃七來源；前批受限環境實測 Defender/listeners/processes partial、tasks unknown，不能當正常使用者長期覆蓋證明 |
| 模型預算 | 可選任務每日耐久五次、unknown-exit gate 保留 | 正式預算未初始化、本批零真模型；不限制背景採集，也不因換目錄重置 |
| 驗證界線 | 有限真 Windows Job＋synthetic host／SQLite；完整與 mock scope 分列 | 沒有實際登出／重開機、真實狀態注入或24小時 soak，沒有全天候承諾 |

實際排程啟用需要一次集中批准；使用者一般權限背景實作／驗證已授權，正常步驟不逐步詢問。部署前的測試修正及原始失敗均留 EVIDENCE。未提權、UAC、下載安裝、改設定／執行政策、永久 MCP、服務或其他程序處置。

執行資料、憑證、Codex home、私人歷史及完整會話不上傳；原有 docs/research/ 保留。本批集中本機提交，不推送或觸發 CI。長時與實機注入依 [SOAK_PLAN](docs/SOAK_PLAN.md)、[WINDOWS_VALIDATION_PLAN](docs/WINDOWS_VALIDATION_PLAN.md) 另驗證。
