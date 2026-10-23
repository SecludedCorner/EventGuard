# EventGuard 現況

更新：2026-10-23；分支 feat/local-codex-acceptance，本批基底 fd1e874e380512b2566dc2690368c20acd3813cd。命令、測試數、來源與提交對照見 [EVIDENCE](docs/EVIDENCE.md)。

已交付可操作的 Tk GUI。雙擊 EventGuard.cmd，按開始持續監看、暫停耐久停止；X 最小化，應用程式→暫停並結束才離開。操作走同一核心，無模型輪詢、每日採集期限或額外事件帳本。見 [GUI](docs/GUI.md)。

| 項目 | 現況 | 界線 |
| --- | --- | --- |
| 正式 GUI | 本輪已開啟並送出開始；核對 background=running、current_monitor=running_verified，七來源資料新鮮 | 這是當次狀態，使用者可自行暫停；不是24小時或重開機證明 |
| 操作 | 開始／暫停、七來源筆數與原因、事件清單／唯讀內容、接收勾選；背景worker維持UI回應 | 查看不ACK、不執行事件內容、不自動處置 |
| 一般權限來源 | Defender/listeners/processes partial；startup/services/tasks/versions ok，本輪均有資料 | 部分／拒讀／過期／未知不代表安全，不能推論受侵或無風險 |
| agent 開關 | 預設關閉；勾選耐久開放既有live工具，取消阻擋後續讀取／ACK及live dispatcher啟動 | 沒有接收器連線證據、真agent驗收或模型啟動；既有pending與query不丟棄，人類不受影響 |
| 應用生命週期 | GUI持有私有Global Job；host核對應用PID＋建立時間，意外owner退出後合作停止；X縮小持續運作 | 不detach、不breakaway；應用之外的Job仍可能約束其生命週期 |
| 退出與容量 | 暫停先保存disabled，再核對本工具host／子樹；未知保留視窗。滿載保留pending／baseline且明示背壓 | ACK只表示收到，不是修復或案件結束；有有限保留／去重窗 |
| 登入後恢復 | 既有排程入口保留，但本輪未建立、Run、服務或自啟 | 使用者沒有批准前次plan；GUI開始無須等待排程。舊plan因程式變更失效 |
| 驗證 | 真Tk自身元件＋fixturecontroller、真Windows有限Job／父應用退出、SDK函式接收開關及人類接手；一般權限正式GUI監看 | 真模型、OS登出／重啟、狀態注入及24小時soak未驗證 |

一般權限、Python3.13標準庫與既有tkinter；無下載安裝、提權／UAC、安全設定或執行政策變更、永久MCP註冊、其他程序處置。事件與工具輸出是不可信資料。

reports/data/logs、憑證、Codex home、私人歷史與原有docs/research/不提交；同一feature集中本地提交、不推送或觸發CI。接手先讀 [HANDOFF](HANDOFF.md)。
