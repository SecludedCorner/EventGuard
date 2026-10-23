# EventGuard 現況

最新方向為本機資安情報中心：共享operator MCP有15工具（含操作紀錄），GUI新增「操作紀錄」頁籤。操作先保存再執行，可看入口、開始時間、待結果及完成狀態。正式MCP已獲使用者批准，專案eventguard設定已加入，原eventguard_test保留；註冊未啟動監看或模型。當前聊天能否使用15工具仍須看client實際載入，不能以寫入設定代替證明。

GitHub盤點的後續兩項已實作：stdout/stderr超過4MiB提早停止本工具Job；JSON超32層或重複key拒絕，Runner與PowerShell字串入口共用。最後完整回歸有一項MCP冷啟動測試逾時，修正後operator補驗通過；dispatcher另一個啟動時序測試修正後全模組通過。最終變動模組均有通過案例，但未再重跑整套，精確數字與原失敗見EVIDENCE。

最新澄清：目前任務要求**本對話**接收。2026-10-23 13:52本主對話已再次以原生MCP接收新合成事件並ACK，生成／接收／查證／ACK各1、同ID、1張回條；沒有另開CLI。這是活動回合收取，**閒置時自動喚醒本對話仍未接通**。下述專用CLI為可選能力，沒有啟用，不能當作此目標已完成。

更新：2026-10-23；分支 feat/local-codex-acceptance，本批基底 befeed79d4ec8c5d5541ff473e11c5cf3b8af872。命令、測試數、來源與提交對照見 [EVIDENCE](docs/EVIDENCE.md)。

前批已實作持續事件等待與獨立自動 agent 開關：同一 Python dispatcher 跨事件／日界待命，空佇列不建立任務，預算用完保留 pending，失敗不自動重試。接線與接手步驟見 [CONNECT_AGENT](docs/CONNECT_AGENT.md)。專用CLI合成驗收因固定預算未初始化而未啟動；最新目標為同一對話接收，暫不續行此替代路徑或索取CLI日額資訊。

已交付可操作的 Tk GUI。雙擊 EventGuard.cmd，按開始持續監看、暫停耐久停止；X 最小化，應用程式→暫停並結束才離開。操作走同一核心，無模型輪詢、每日採集期限或額外事件帳本。見 [GUI](docs/GUI.md)。

前批採納人類摘要／技術資料展開、事件篩選及壞列隔離；本批補讀完整25引擎整合及各上游repo的README／代表入口，見 [盤點](docs/SCANNER_ENGINES.md) 與 [執行邊界](docs/SCANNER_RUNTIME_REVIEW.md)。沒有引入外部掃描器或依賴。本輪實際手動接收找到ACK重播檢查缺口，已修正並驗證。

| 項目 | 現況 | 界線 |
| --- | --- | --- |
| 正式 GUI | 前批已開啟並核對 running_verified；本批不重啟、不重掃，已開視窗不熱更新 | 使用者可自行暫停；新介面下次正常開啟載入，不是24小時或重開機證明 |
| 操作 | 開始／暫停、七來源、中文事件摘要、原始資料、接收篩選；另有自動agent勾選與原生exe選擇 | 篩選僅目前最多100件；自動選擇預設off，讀GUI不啟動模型，明確Start才沿用保存選擇 |
| 一般權限來源 | 前批 Defender/listeners/processes partial；startup/services/tasks/versions ok，均有資料 | 本批只驗證合成契約，不更新正式可讀性結論；部分／拒讀／過期／未知不代表安全 |
| 採集壞列 | 七來源 native／fallback 均保留合法 sibling，非物件列帶固定原因與計數；有可用列 partial，否則 error | 外層契約錯誤仍拒絕；partial 不清 baseline、不判恢復，壞資料不進錯誤原文 |
| agent 開關 | 預設關閉；本輪唯讀查得enabled_waiting_receiver；勾選只開放live工具，取消阻擋後續工具讀取／ACK | 開關不是MCP連接或喚醒證據；既有pending與query不丟棄，人類不受影響 |
| 自動agent | 已有continuous dispatcher與GUI接線、單次CLI期限、空閒／日額／拒絕等待與合作停止 | 實作及離線測試不等於真CLI驗收；沒有開啟正式auto或接手正式backlog |
| 本聊天接收 | 主agent已用原生MCP list→receive→inspect→再次receive→ACK→重播ACK→inspect；同一合成event/query，SQLite只新增一張回條 | 先前命令工具驗證與這次原生MCP證據分開；不等於閒置聊天會被自動喚醒 |
| 限定專案MCP | eventguard_test四工具已出現在主對話且實際可呼叫；只連已批准的隔離test佇列 | 本次新合成事件已ACK；原生接收通過。沒有接正式事件、改全域／信任設定或啟動模型CLI；先前未載入的精確根因仍未定案 |
| 正式專案MCP | 已依使用者批准加入eventguard，提供15個共用操作工具 | 設定已保存；本主對話目前工具清單仍只有eventguard_test四工具，不能以子agent清單代替正式呼叫成功 |
| 應用生命週期 | GUI持有私有Global Job；host核對應用PID＋建立時間，意外owner退出後合作停止；X縮小持續運作 | 不detach、不breakaway；應用之外的Job仍可能約束其生命週期 |
| 退出與容量 | 暫停先保存disabled，再核對本工具host／子樹；未知保留視窗。滿載保留pending／baseline且明示背壓 | ACK只表示收到，不是修復或案件結束；有有限保留／去重窗 |
| 登入後恢復 | 既有排程入口保留，但本輪未建立、Run、服務或自啟 | 使用者沒有批准前次plan；GUI開始無須等待排程。舊plan因程式變更失效 |
| 驗證 | 最後完整suite自然退出但有一項握手逾時；修正後operator、GUI、activity、hardening及dispatcher已有通過案例，輸出保留EVIDENCE | 不把局部結果改寫成修正後重新全套；自動真CLI、OS重啟與24小時尚未驗證 |

一般權限、Python3.13標準庫與既有tkinter；無下載安裝、提權／UAC、安全設定或執行政策變更、全域MCP變更、其他程序處置。正式專案MCP為另行批准的持續接線；事件與工具輸出是不可信資料。

reports/data/logs、憑證、Codex home、私人歷史與原有docs/research/不提交；同一feature集中本地提交、不推送或觸發CI。接手先讀 [HANDOFF](HANDOFF.md)。
