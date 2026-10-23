# EventGuard 現況

最新方向為本機資安情報中心，已依使用者要求建立持續目標，狀態active。共享operator MCP的15工具已出現在**本主聊天**，且正式capabilities／status／activity實際呼叫成功；activity可讀到本輪操作。原eventguard_test保留，未啟動監看／模型或接收／ACK正式backlog。GUI已有「操作紀錄」頁籤；既有視窗是否已載入新版不推定。

最新前置：當版登入恢復dry-run已完成，一般使用者確認專屬任務不存在；方案只註冊、不立即Run，現有explicit_stop保持。`codex queue/proxy`已核對本機help；proxy精確聊天metadata探測被自動核准審查拒絕，尚未執行。需批准的精確範圍與方案見[喚醒／恢復關卡](docs/WAKE_RECOVERY_GATES.md)，不重跑已通過通路取代它。

本輪修正operator終身單連線鎖造成的真啟動exit3：多client可並存，mutation採短期鎖，讀取與Stop可通過；Stop綁定scope及原owner/run，不追停新代。legacy單事件owner仍exclusive；單事件CLI argv明確停用已知正式與測試聊天MCP。相關模組回歸無失敗／殘留，完整回歸及精確證據只看EVIDENCE，不與歷史結果相加。

本主對話本輪再以原生MCP接收一件程式新生的合成事件：補收同event/query、ACK重播不新增回條，SQLite與工具回傳一致，missing／duplicate_receipts皆空。使用隔離test佇列，正式資料未ACK。這是活動回合收取，**閒置時自動喚醒本對話仍未接通**。下述專用CLI未啟用，不能當作同一目標已完成。

更新：2026-10-23；分支 feat/local-codex-acceptance，當前程式基底 af839b36a4f43efbc5e273680ba2f597edb93df1。命令、測試數、來源與提交對照見 [EVIDENCE](docs/EVIDENCE.md)。

前批已實作持續事件等待與獨立自動 agent 開關：同一 Python dispatcher 跨事件／日界待命，空佇列不建立任務，預算用完保留 pending，失敗不自動重試。接線與接手步驟見 [CONNECT_AGENT](docs/CONNECT_AGENT.md)。專用CLI合成驗收因固定預算未初始化而未啟動；最新目標為同一對話接收，暫不續行此替代路徑或索取CLI日額資訊。

已交付可操作的 Tk GUI。雙擊 EventGuard.cmd，按開始持續監看、暫停耐久停止；X 最小化，應用程式→暫停並結束才離開。操作走同一核心，無模型輪詢、每日採集期限或額外事件帳本。見 [GUI](docs/GUI.md)。

前批採納人類摘要／技術資料展開、事件篩選及壞列隔離；本批補讀完整25引擎整合及各上游repo的README／代表入口，見 [盤點](docs/SCANNER_ENGINES.md) 與 [執行邊界](docs/SCANNER_RUNTIME_REVIEW.md)。沒有引入外部掃描器或依賴。本輪實際手動接收找到ACK重播檢查缺口，已修正並驗證。

| 項目 | 現況 | 界線 |
| --- | --- | --- |
| 正式 GUI／監看 | 正式status實際回傳背景stopped／desired_enabled=false，current_monitor無owner且舊heartbeat過期；保留歷史pending | 本批不重啟、不重掃；無owner及過期資料不代表安全，未驗證視窗狀態或24小時／重開機 |
| 操作 | 開始／暫停、七來源、中文事件摘要、原始資料、接收篩選；另有自動agent勾選與原生exe選擇 | 篩選僅目前最多100件；自動選擇預設off，讀GUI不啟動模型，明確Start才沿用保存選擇 |
| 一般權限來源 | 前批 Defender/listeners/processes partial；startup/services/tasks/versions ok，均有資料 | 本批只驗證合成契約，不更新正式可讀性結論；部分／拒讀／過期／未知不代表安全 |
| 採集壞列 | 七來源 native／fallback 均保留合法 sibling，非物件列帶固定原因與計數；有可用列 partial，否則 error | 外層契約錯誤仍拒絕；partial 不清 baseline、不判恢復，壞資料不進錯誤原文 |
| agent 開關 | 預設關閉；本輪唯讀查得enabled_waiting_receiver；勾選只開放live工具，取消阻擋後續工具讀取／ACK | 開關不是MCP連接或喚醒證據；既有pending與query不丟棄，人類不受影響 |
| 自動agent | 已有continuous dispatcher與GUI接線、單次CLI期限、空閒／日額／拒絕等待與合作停止 | 實作及離線測試不等於真CLI驗收；沒有開啟正式auto或接手正式backlog |
| 本聊天接收 | 主agent已用原生MCP list→receive→inspect→再次receive→ACK→重播ACK→inspect；同一合成event/query，SQLite只新增一張回條 | 先前命令工具驗證與這次原生MCP證據分開；不等於閒置聊天會被自動喚醒 |
| 限定專案MCP | eventguard_test四工具已出現在主對話且實際可呼叫；只連已批准的隔離test佇列 | 本次新合成事件已ACK；原生接收通過。沒有接正式事件、改全域／信任設定或啟動模型CLI；先前未載入的精確根因仍未定案 |
| 正式專案MCP | 主對話已實際呼叫capabilities／status／activity；同表紀錄可讀 | 只驗本輪呼叫，未重驗所有15項實機操作；不是閒置自動喚醒 |
| 應用生命週期 | GUI持有私有Global Job；host核對應用PID＋建立時間，意外owner退出後合作停止；X縮小持續運作 | 不detach、不breakaway；應用之外的Job仍可能約束其生命週期 |
| 退出與容量 | 暫停先保存disabled，再核對本工具host／子樹；未知保留視窗。滿載保留pending／baseline且明示背壓 | ACK只表示收到，不是修復或案件結束；有有限保留／去重窗 |
| 登入後恢復 | af839b36當版新dry-run確認專屬任務absent，保留暫停；已備只註冊、不Run的審查方案 | 尚未批准註冊；不等於重開機通過，也不解除明確Pause。建立入口與SHA見喚醒／恢復關卡 |
| 驗證 | 本輪雙client真stdio、scope／owner換代、既有background／CLI契約相關模組通過；完整suite另見EVIDENCE | fixture／SDK／fake CLI／真Windows owned-job與本主聊天原生工具證據分開；真CLI、OS重啟與24小時未在本輪驗證 |

一般權限、Python3.13標準庫與既有tkinter；無下載安裝、提權／UAC、安全設定或執行政策變更、全域MCP變更、其他程序處置。正式專案MCP為另行批准的持續接線；事件與工具輸出是不可信資料。

reports/data/logs、憑證、Codex home、私人歷史與原有docs/research/不提交；同一feature集中本地提交、不推送或觸發CI。接手先讀 [HANDOFF](HANDOFF.md)。
