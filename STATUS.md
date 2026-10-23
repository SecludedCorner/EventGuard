# EventGuard 現況

更新：2026-10-23；分支 feat/local-codex-acceptance，本批基底 32f9975182e189ad3b9723d8df78e3db022cdd4e。命令、測試數、來源與提交對照見 [EVIDENCE](docs/EVIDENCE.md)。

已交付可操作的 Tk GUI。雙擊 EventGuard.cmd，按開始持續監看、暫停耐久停止；X 最小化，應用程式→暫停並結束才離開。操作走同一核心，無模型輪詢、每日採集期限或額外事件帳本。見 [GUI](docs/GUI.md)。

本批依兩個子 agent 的上游讀碼研究，採納人類摘要／技術資料展開、事件篩選及壞列隔離，均已獨立實作並統一驗證。來源固定版本與取捨見 [SCANNER_LESSONS](docs/SCANNER_LESSONS.md)；沒有引入外部掃描器、依賴、模型或權限。

| 項目 | 現況 | 界線 |
| --- | --- | --- |
| 正式 GUI | 前批已開啟並核對 running_verified；本批不重啟、不重掃，已開視窗不熱更新 | 使用者可自行暫停；新介面下次正常開啟載入，不是24小時或重開機證明 |
| 操作 | 開始／暫停、七來源筆數與原因、中文事件摘要／未知／唯讀建議、原始資料展開、嚴重度／接收篩選、接收勾選 | 篩選僅目前最多100件，總數及截斷明示；查看不ACK、不執行事件內容、不自動處置 |
| 一般權限來源 | 前批 Defender/listeners/processes partial；startup/services/tasks/versions ok，均有資料 | 本批只驗證合成契約，不更新正式可讀性結論；部分／拒讀／過期／未知不代表安全 |
| 採集壞列 | 七來源 native／fallback 均保留合法 sibling，非物件列帶固定原因與計數；有可用列 partial，否則 error | 外層契約錯誤仍拒絕；partial 不清 baseline、不判恢復，壞資料不進錯誤原文 |
| agent 開關 | 預設關閉；勾選耐久開放既有live工具，取消阻擋後續讀取／ACK及live dispatcher啟動 | 沒有接收器連線證據、真agent驗收或模型啟動；既有pending與query不丟棄，人類不受影響 |
| 應用生命週期 | GUI持有私有Global Job；host核對應用PID＋建立時間，意外owner退出後合作停止；X縮小持續運作 | 不detach、不breakaway；應用之外的Job仍可能約束其生命週期 |
| 退出與容量 | 暫停先保存disabled，再核對本工具host／子樹；未知保留視窗。滿載保留pending／baseline且明示背壓 | ACK只表示收到，不是修復或案件結束；有有限保留／去重窗 |
| 登入後恢復 | 既有排程入口保留，但本輪未建立、Run、服務或自啟 | 使用者沒有批准前次plan；GUI開始無須等待排程。舊plan因程式變更失效 |
| 驗證 | 本批完整suite與真Tk自身合成視窗檢查通過；逐項測試含既有真Windows有限Job與SDK函式契約 | 不冒充正式壞資料注入或新實機採集；真模型、OS登出／重啟、狀態注入及24小時soak未驗證 |

一般權限、Python3.13標準庫與既有tkinter；無下載安裝、提權／UAC、安全設定或執行政策變更、永久MCP註冊、其他程序處置。事件與工具輸出是不可信資料。

reports/data/logs、憑證、Codex home、私人歷史與原有docs/research/不提交；同一feature集中本地提交、不推送或觸發CI。接手先讀 [HANDOFF](HANDOFF.md)。
