# EventGuard 接手

先讀 AGENTS、README、STATUS。最新目標是事件驅動的專用 agent 通路。一般使用者。核心只用標準庫。

分支 `feat/local-codex-acceptance`。本批基底 `9640df6581b996126137dd4e7066023c3950cf20`。
保留未追蹤的 `docs/research/` 與附件。不 reset、clean、推送或提交執行資料。

## 本批事件派送

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
