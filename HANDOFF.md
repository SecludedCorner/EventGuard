# EventGuard 接手


## 單次通訊實測：2026-10-24（最新）

本次未能通訊。真正原生 CLI 已啟動一次。載入設定時退出：
`Error loading config.toml: invalid transport`，位置為 `mcp_servers.eventguard_test`。
CLI exit 1。驗收 exit 2。耗時 17.55 秒。未進入 provider turn，沒有模型回覆。
同一合成事件生成／入列各 1；receive、query、結果、ACK 均 0。事件仍 pending，無重複。
CLI、supervisor 與 host 已退出。無強停、無殘留。不自動重試；單次授權已消耗。

最新人類指示取消 App 的每日預算限制。通訊路徑不再讀取或改寫歷史預算。
歷史 bootstrap 與帳本保留，前後 SHA256 相同。舊 waiting_budget_day 已被取代。
正常無事件不呼叫模型。這次驗收仍限定最多一個 CLI 任務及 180 秒。

修正停用 MCP entry 的 transport 定義，並新增無模型契約測試。
修正後的真模型通訊未重驗。後續受支援的 native mcp get 設定解析 exit 0；舊 exit 2 查核保留。
後續唯讀 test App 的真 SDK MCP status 與 GUI 已對上同 event/attempt、CLI失敗及pending1。這是顯示失敗證據，不是收件。
App已自然exit0，無殘留；source/inbox位元組未變。新增模型任務0，總CLI測試仍1。
證據：`reports/service-acceptance-eventguard-single-test-20261024-01/communication-result.json`。
原 stderr、CLI JSONL、SQLite、intent、各層退出回條與歷史失敗均保留。
只提交程式、測試與文件。不提交執行資料。完整歷史見 docs/EVIDENCE.md。

先讀 AGENTS、README、STATUS。目前優先交付可獨立使用的無模型產品閉環，再銜接模型。一般使用者。核心只用標準庫。

目前 active goal 已擴為獨立產品、耐久事件與公開事件入口研究。本批基底 `9903ad5574e80666eb379652e7f4154d111c14b3`。
不要因舊 MCP 階段完成而把整個目標標 complete。

- Application 是唯一 owner。`run --idle` 開閒置應用；`run` 明確開始採集。
- stdio 一律 Remote observer。冷啟動只列工具，沒有 App 時 blocked。不再讓 EOF 關閉 App。
- CLI `app status/start/pause/resume/stop/shutdown`、GUI 與十個 MCP 工具共用同一實例。
- status/capabilities 可重新核對同 root/namespace 的新 instance；mutation 不自動轉往新 instance。舊 operation ID 仍 fenced。
- 通知先保存 prepared，再呼叫 sink，再保存 accepted。回條不明保留 prepared，顯示 unknown，不自動重送。這不 ACK 事件。
- NVIDIA CSAF 範例預設 disabled。partial 不覆蓋完整快取，後續304不能提升成功。版本標籤不當通用SemVer。
- 公開公告投影接入 status、GUI及公告事件詳情。原始 inventory/facts/path/PID/evidence 不進投影。七欄自動模型profile不變。
- 十類自寫對抗文字只作資料。來源與模型文字不能變成操作授權。
- 公開 Codex 入口研究見 [AGENT_EVENT_DRIVEN](docs/AGENT_EVENT_DRIVEN.md)。桌面閒置喚醒仍未驗證。
- OpenOctopus 協定見 [OPENOCTOPUS_EVENT_PROTOCOL](docs/OPENOCTOPUS_EVENT_PROTOCOL.md)。是可拆工提案，不是外專案已實作。

本批整合測試結果與命令只見 EVIDENCE。不得把 AST檢查或未執行測試算通過。
舊 `reports/application-mcp-001` 是前版九工具/owner語義的歷史證據；本批生命週期以新程式與新測試為準。
本批沒有啟用正式監看、模型、預算bootstrap、排程、proxy或新登入。不要求使用者重開Codex。
保留 .codex-remote-attachments/ 與 docs/research/；不提交執行資料、不推送。

## 本輪完成稽核與下一個批准邊界

七項必做已對上程式與實際證據。索引在本機 `reports/application-lifecycle-001/product-requirements.json`。
事件/篩選、五規則及熱重讀、四處置狀態、七來源原因、通知、單一run、普通程式公告追蹤皆有對應證據。
規則/來源歷史核心位元組不變；保留逐項原紀錄，不把歷史整輪失敗寫成成功。不再重跑已驗全套。
中文app摘要另有定向驗證。一般使用者通知OS接受且重開不重送；不是人已看見的證明。

原Goal仍不可冒稱已完成真模型喚醒。以下分清：

| 項目 | 下一步 | 批准/阻塞 |
| --- | --- | --- |
| 短期專用agent真驗 | 同一安裝authority預算可用後，`scripts/validate_delivery.py service`的一事件/一任務/180秒，真receive/query/結果/ACK/退出比對 | 需具名批准真模型。未知歷史用量不假設0、不初始化/重置；若預算unavailable則不啟動 |
| 本聊天MCP操作面 | 已自動載入十工具，真status與CLI/Web metadata同instance，原生shutdown與實際exit已驗 | 已完成此客戶端操作面。未要求重開；不把它當事件收件或閒置喚醒 |
| 桌面閒置喚醒 | 官方queue列為候選；指定目的地與真turn/工具證據仍需有界驗證 | 未驗證。設定或SDK不能代替。不可自行發queue或啟動模型 |
| 正式背景、soak、重開機 | 待使用者核定範圍。既有dot保留 | 不屬本輪已啟用能力；不建立排程或自啟 |

無模型必要工程沒有新的已知缺口。不要靠新增周邊功能維持active。
維持原Goal完整範圍與未驗證項目，由下一個有效批准或明確決策推進；不自行縮小後假結案。

## 前版資料保存與來源修正

已補 `run` 本機頁的監看暫停／恢復／停止，並統測事件、處置與 pending 保留。
只控制本應用實際捕捉的 Job。外部 owner、未知退出或控制世代變更時不可盲目恢復。
本輪不呼叫模型、不啟用正式 agent host、不初始化或重設預算。模型介面保留選配。
本批已完成實際瀏覽器操作。證據、截圖、CLI／SQLite 與退出回條位於 `reports/browser-controls-001`。
`ui-validation.json` 為 true：同一事件跨刷新／應用重啟仍 handled＋pending，兩個應用及三個 monitor 均自然退出。
修正停止頁首、合成標示與篩選名稱。Web／CLI 新增耐久最後成功時間。
Runtime observations 沿原 JSON 原子保存 last_success_at；失敗或不完整採集不更新成功歷史。
公告 case_status/current_assessment 是當前投影；原 assessment 標 historical，舊資料不改寫。
來源綁定、來源期限及靜態盤點期限都有效，才可支持目前排除。人工 facts 讀檔與 304 不刷新日期。
原測試 WinError 32 是新測試未關 SQLite；改 closing 後只重跑該模組。命令、數字與限制只見 EVIDENCE。
上批 `reports/local-controls-001` 的失敗、中斷與修正證據保留，不與本批加總。
沒有宣稱七來源當前實機、長期背景、24 小時或真模型收件成功。

分支 `feat/local-codex-acceptance`。前版基底 `54d231c896a5c865e4838025ae5b2d86d872d90e`。
保留未追蹤的 `docs/research/` 與附件。不 reset、clean、推送或提交執行資料。

`Application.monitor_control` 固定 start／pause／resume／stop／shutdown。Web 與九工具 MCP 共用此控制器，不另建 owner。
pause 由 OperatorAPI 關閉實際捕捉的子程序；確認退出與回條後才標 paused。Web 與資料保留。
resume 檢查原 namespace／run／停止後 generation，重讀規則，再由 background.start 在控制鎖內比對 generation。
舊 owner 永久關閉；新 owner 只持有明確開始／恢復所建立的子程序。不接管外部 host。
stop 只停止採集並確認退出；shutdown 才要求主迴圈關閉控制服務。
EventStore 既有空檔／缺表／缺必要欄位不再自動建空庫。初始化與已知 legacy migration 同一交易；失敗回滾。

## 既有事件派送契約

- `agent_service.py`：手動背景 start/status/pause/resume/stop。沿用原 dispatcher，不建立服務或排程。start/resume 預設不執行。
- `dispatch_policy.py`、`config/agent-dispatch.json`：純程式枚舉篩選。未選或已處理事件仍 pending。
- `agent_dispatch.py`：重查耐久 pause gate，保留已扣額度；缺 supervisor 回條維持未知。status(read_only=True) 不建鎖。
- `event_ingress.py`：七欄 CloudEvents profile、唯讀匯出及分階段證據。沒有 provider 證據時不聲稱已啟動。
- `processes.stop_persistent`：只有已核對且 signalled 的 owned HANDLE 才讀取 OS exit code。失去證據則 null。
- CLI `agent` 與 Web 派送頁共用 API。Web 只有 pause/stop，不能啟動或恢復模型。
- 原 `validate_delivery.py service`：一件高嚴重度合成事件；先等候再加入；重驗 trace/工具/SQLite/Job；相同 intent 不重跑。

本次補強：pending schema／hash／處置狀態先驗證，再作篩選。錯誤碼由固定清單投影到 host/status。
驗證快取有界，key 含完整原文、PK 及 stored hash。同帳戶可改檔的限制仍存在。
新 managed worker 在 spawn 前存 identity-required 與 nonce，spawn 後保存實際身分。worker 等待綁定後才可啟動 CLI。
complete 與唯讀 status 共用 supervisor proof。缺開始身分、退出身分不符或缺實際 OS exit 都不能判成功。
service verifier 另核對 SQLite created_at／acked_at、工具時間及同 scope 的 UTC／monotonic 觀察。
舊 fixture 回條保留 legacy 語義，不可當成本版 managed 身分驗收。真驗仍未執行。
capture-skipped 只證明 CLI 未啟動。三個 skip 分支仍須 supervisor proof；缺證據保持 started，不重啟。
定向回歸及修正證據為 proof-delta-001／002；proof-test-index.json 按 test ID 合併。最後來源只重驗相關模組，沒有冒稱完整全套。
host 的舊 Job 已確認退出時，可明確 start。未知 Job 仍阻擋，不取消預算或刪帳本。

按事件查 provider：新 attempt 保存來源／inbox scope 與 event/hash 綁定。原 ledger／archive 保留有界 attempt 參照。
`inspect_delivery(..., root=...)` 只讀本專案受管理的 run／attempt，重驗原始 CLI、capture 及 supervisor 回條。
CLI 與 Web 傳明確 Runtime.root。沒有 root、舊資料無綁定或證據不符時，provider 階段維持未知；獨立 inbox 證據不受影響。
回傳 scope 明示 CLI 協定證據，real_agent_wake_verified 仍 false。只供本機人類查看，沒有擴大模型 snapshot 或 query。
有限 service 真驗入口改用正式 application-owned Job，而非測試 allow_parent_job。driver 保留真 child HANDLE、先合作 stop、再核對整樹退出。
application_owner PID／建立時間與 deadline 在 host 及最終 CLI gate 都會重查。產品獨立 start 預設不變，不逃離外層 Job。
本批統測為 `reports/event-ingress-001/operator-delta-001`，來源不變、無模型、無殘留。實際範圍與唯一通知 skip 見 EVIDENCE。

操作見 [AGENT_SERVICE](docs/AGENT_SERVICE.md)。新證據僅 `reports/event-ingress-001`，完整數字見 EVIDENCE。
完整測試後又修正 resume/preflight、OS exit code 與 service 驗收；最終是全套加定向回歸，不冒稱最終來源全套重跑。
正式 agent 尚未啟用；固定 budget DB/marker 缺失。沒有初始化、推定零用量或呼叫真模型。
真驗前集中批准一件合成事件、最多一個專用任務，並遵守既有未知用量 bootstrap。不要重置帳本。
主聊天 queue 仍未驗證，不是阻塞。OpenOctopus 只交付契約，不操作另一聊天或專案。

## 入口

- `EventGuard.cmd run`：既有七來源採集、Web 與通知。維持可獨立使用。
- `advisories start / status / stop / check / cases`：新增公告入口。正式 start 本批未執行。
- `intelligence/sources.py`：有界擷取與正規化。真官方 URL 及查核見 ADVISORY_SOURCES。
- `intelligence/inventory.py / versions.py / applicability.py`：靜態允許範圍、版本與保守適用性。不執行工具版本。
- `intelligence/store.py`：SQLite FULL、別名合併、分來源與元件斷言、不可變 change、冷卻與容量。namespace／synthetic 耐久綁定。
- `intelligence/engine.py`：單一 cycle lease、來源快取重處理、重要事件送原 EventStore。落盤後才標 emitted。
- `intelligence/service.py`：手動背景私有 Job、身分核對、合作 stop、heartbeat 與失敗退出回條。

同 source ID 換 URL 或 adapter 時不沿用舊條件請求。失敗保留舊證據，但停用舊快取的適用性評估。
同 CVE 多元件分開比較，避免輪流觸發。待送 change 不改寫，避免 outbox 成功而回條失敗後發生 ID 衝突。
公告 emitted 不代表 ACK。沒有完成保留證據時，不自動清理該帳本。滿載 blocked，不刪 pending。

## 驗證與界線

既有公告功能的證據放 `reports/advisory-tracker-001`。本批派送證據另見上節。完整命令、失敗及修復見 EVIDENCE。
離線 SQLite、真公開 HTTP、合成資產重播、Windows Job 與真模型分開記錄。
正式背景、真模型、24 小時及 dot 交接未執行。不要把重播或 backend ACK 寫成真 agent 已收到。

snapshot 仍七欄。只新增 `advisory.changed` 枚舉。不傳產品、路徑、PID、URL 或 evidence。
完整公告與盤點只能由本機 CLI 查看。未擴大 agent 查詢。現有日預算五次、自然退出及 ACK 契約不變。
budget status 目前 unavailable。不得刪帳本、換目錄或假設當日用量為零。

後續正式啟用與真模型驗收需使用者核定具體範圍。本輪不啟用，也不索取排程、proxy 或重開 Codex。
原 dot 追蹤保留至交接確認。文件與功能同一提交。不做文件單獨 commit。
