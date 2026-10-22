> 歷史文件：由 `README.md`（提交 `1e90a5398c5d4c555924bffb70bb77cb429dd782`）移存；保留原文，只加此標記及調整相對連結。當時的限制、數字與接手指令不是現況或新授權。

# EventGuard

**Phase 4 容量與保留：** ACKed payload／接收回條與 dispatcher 完成帳本可依有限政策清理、輪替；pending／retry／未 ACK failed 保留。設定、滿載恢復及去重保留窗見 [儲存政策](../STORAGE_RETENTION.md)；[24 小時 soak 計畫](../SOAK_PLAN.md) 尚未執行。

**Phase 3 子程序治理：** Windows 查詢改由啟動時即加入私有 Job 的 worker 隔離，停止／逾時先寬限、再只清理本工具程序樹；重新啟動會保存 `monitor_gap`。排程僅 dry-run，尚未啟用長駐或驗證真實重開機恢復；介面與證據界線見 [程序生命週期](../PROCESS_LIFECYCLE.md)。

**目前方向：不依賴 agent 的本機監看與查證，人類與可選 agent 工具共用操作核心。** 無模型的 fixture 快速開始、事件檢視／查證／報告及可選 stdio 接口見 [人類與 agent 共用介面](../HUMAN_AGENT_INTERFACE.md)；下列真 Codex 結果是歷史有限通路驗收，不是正常監看的必要步驟。

以 [MIT 授權](../../LICENSE)釋出的 Windows 本機唯讀事件監看與 Codex agent 接收工具：[SecludedCorner/EventGuard](https://github.com/SecludedCorner/EventGuard)。目前為工程預覽。

**本機事件已接到專用 Codex CLI agent；完整產品仍為工程預覽。** 2026-10-22 MSI 的有限合成 A／B1／B2／C 已通過：7 個唯一事件、8 次接收／查證、7 次耐久 ACK。新增前景入口亦完成一次合成事件及有界實機佇列試運轉，真正 agent 經工具接收、query、ACK 並自然退出。完整 Windows 採集覆蓋、長期可靠性與原生診斷閉環仍待驗證；實測範圍與證據見 [STATUS](../../STATUS.md)。

EventGuard 提供無 GUI 的本機唯讀監看核心：一般權限程式採集有限 metadata，以確定性規則判斷變化，僅異常轉態建立耐久事件；正常週期不呼叫模型。可選有界 worker 等待佇列，有事件才啟動專用 CLI agent。原生診斷及案件處理仍屬後續產品驗收，不能由接收 ACK 推定完成。

**有界實機試運轉已結束，目前沒有持續監看。** 新入口使用既有登入、正常 Codex home 與本次 CLI 的 MCP 設定，只傳七欄事件 snapshot。事件落盤、接收 ACK、agent 開始與案件結案各有證據和語義；這不代表既有桌面聊天會自動接續或已建成長期監看。

本機固定基準 `fd45578` 與 frozen ZIP 保留不變；目前 `main` 已另加 MCP Events 接線程式，新增結果以當前 commit 與測試為準。這不修改舊 MVP，也不把歷史測試升格為平台接通證據。

## 最新驗收結果（2026-10-22）

以下結果對應程式版本 `cc6e799`，本次只整理文件與 MIT 授權，未重跑模型或實機採集。receive/query/ACK 均須有實際工具返回、相同 event/query/result ID、SQLite receipt 與 CLI 退出證據；agent 文字宣稱或單純落盤不算通過。

| 案例 | 事件與結果 | 狀態 |
| --- | --- | --- |
| A：單件合成事件 | 1 件，真正 wait → query → ACK，CLI exit 0 | 通過 |
| B1：連續合成事件 | 2 件，生成／接收／query／ACK ID 集合一致，missing=[] | 通過 |
| B2：批次合成事件 | 3 件，生成／接收／query／ACK ID 集合一致，missing=[] | 通過 |
| C：ACK 前退出後補收 | 1 件，首次只 wait/query 正常退出且仍 pending；第二次取得同 event/query，再 ACK 一次 | 通過 |
| 新佇列入口：合成測試 | 1 件，真正 receive → 保存摘要 query → ACK，CLI exit 0 | 通過 |
| 新佇列入口：有界實機試跑 | 上限 300 秒／最多 2 任務，實際工具 ID 與原 outbox receipt 一致，CLI 與監看自然退出 | 通過，限本輪範圍 |
| 單元／SDK／fake CLI 測試 | 269 項：267 通過、0 failure/error、2 項因 symlink 權限略過；64 個 Python AST 通過 | 通過，非模型或實機證明 |
| 後續 dot 合成投遞探針 | 已耐久入列；本次查證仍 pending、0 ACK，尚無 dot 實際接收證據 | 待確認 |

A／B／C 合計 **7 個唯一合成事件、8 次接收／query、7 次 ACK**。C 預期重收一次；缺漏、額外事件及非預期重複均為空。達任務上限後尚待交付的事件保留在原 outbox，沒有假稱整個佇列已清空。

目前可證明的是本機事件送達專用短期 Codex CLI agent。**尚未完成全天候背景版、長時資源與故障恢復驗收、任意 dot／桌面對話續接、完整 Windows coverage 或原生診斷／處置閉環。** query 僅查保存的最小摘要，ACK 不代表主機安全或案件已處置。現有入口仍限每次最多一小時／五個任務；沒有每日自動刷新預算或開機自啟。

公開內容僅含匿名工程摘要、原始碼、測試與設定範例。manifest、真 CLI JSONL、實際工具回傳、SQLite、憑證、Codex home、私人歷史及原始執行資料留在本機，不隨儲存庫發布。詳細時間、命令及已知限制見 [STATUS](../../STATUS.md)，操作見 [LIVE_CHANNEL](../LIVE_CHANNEL.md)。

## 可使用的前景事件入口

依 [本機監看與真正 agent 接收](../LIVE_CHANNEL.md) 在當次有效授權內執行：

```powershell
$env:CODEX_HOME = Join-Path $env:USERPROFILE '.codex'
$codexExe = (Get-Command codex.exe -CommandType Application -ErrorAction Stop).Source
python -B scripts/eventguard_watch.py run --run-dir reports/watch-001 --codex-executable $codexExe --max-seconds 3600 --max-tasks 5 --execute --allow-live
```

純 Python 等候原耐久佇列，有 pending 事件才啟動模型；每個任務只接收一件、query 保存的最小摘要並 ACK。最多一小時／五個任務，可縮小上限。每次使用全新 run 目錄，沒有服務或自動恢復；另有 `status`、`stop`。到期或停止只阻止後續工作，已開始操作自然退出。ACK 表示摘要已接收，沒有主機安全或處置結論。

## MSI 單次合成 Codex 驗收入口

依 [從 GitHub 取得並驗收 A／B／C](../MSI_CHANNEL_CHECK.md) 使用有限驗收入口。MSI 本輪 A／B1／B2／C 已真正通過；雲端發布不是本機驗收的前置條件。

`python -B scripts/acceptance_codex.py run --run-dir reports/msi-codex-001 --codex-executable <既有原生路徑>` 自動協調 agent 等待後的合成 producer、查證與耐久結果／ACK，提供 status／stop、同事件手動 retry、跨程序鎖、有界輸出與分次保存的證據。三工具批准只作用於本次執行，不永久註冊 MCP。詳見 [MSI 最短操作、逾時與故障排查](../CODEX_ACCEPTANCE.md)。雲端先前的網路與初始化阻塞保留為該環境紀錄，不影響本輪 MSI 已核實的有限成功。

## 歷史合成實驗：直接本機 MCP 等待

使用者目前選定本機方案。`scripts/eventguard_local_mcp.py` 提供本機 stdio 三個工具 `wait_for_event`、`query_evidence`、`ack_event`。server 本身只處理專用目錄中的合成事件，沒有網路服務、proxy、憑證或模型呼叫；有限驗收由外層明確啟動真正 Codex。真實等待後續跑及 ACK 前補收已有本輪證據，永久等待仍無保證。入口明設工具 timeout 60 秒、server wait 30 秒；不得用模型重複等待代替事件驅動。

讀 [最小實驗與單次批准範圍](../LOCAL_MCP_EXPERIMENT.md)。此舊入口仍限合成事件；新的有界 live 入口另見 [LIVE_CHANNEL](../LIVE_CHANNEL.md)。只使用已安裝的可選 Python MCP SDK；缺少時報錯退出，不下載。本輪批准不延伸為持續模型權限。

## 歷史候選：雲端 MCP Events 接線程式（停用，不是前置需求）

目前新增 authenticated WSGI `/mcp`、durable 訂閱／事件投遞、callback 驗證、Standard Webhooks HMAC、獨立 producer HTTPS adapter，以及只讀取已保存合成證據的工具與 CAS 結果回條。**僅接受 synthetic 事件**；不執行原生採集、模型或系統處置。`received` 只代表 callback 收到，`agent_result_recorded` 只代表已驗證呼叫端提交回條，不自證平台回合或主機安全。

安全檢查不開埠、不讀憑證：

```powershell
python -B scripts/eventguard_bridge.py --config config/bridge.example.json check
```

範例設定 `enabled=false`、`network_enabled=false`、callback allowlist 為空，不能啟動 listener。完整啟用條件、兩個自有 Windows host 部署選項與撤銷方式見 [MCP_BRIDGE_DEPLOYMENT](../MCP_BRIDGE_DEPLOYMENT.md)。此停用雲端 bridge 沒有部署、建立憑證、外連 callback 或喚醒模型；本機 CLI 的成功驗收另見上表。

2026-10-22T03:50:53Z：192 個合成／mock 測試通過、0 failure/error/skip，40 個 Python AST 通過。包含實際 handler／durable store／producer adapter 整合及 fake socket 上的真傳輸標頭政策；不是與平台連線的 E2E。Windows DPAPI 測試只加解密公開合成 fixture。

## 用途與非目標

適合有界本機觀測、基線差異、異常轉態去重、事件保存與重試，以及 agent 日後按需唯讀查證。它不是完整 EDR／鑑識系統，不保證防止入侵，不以未知、沒有事件、簽章或防護開關宣告主機安全。

本版不提供自動隔離刪檔、停止其他程序、系統修補、提權、防火牆／服務／啟動項修改，也不建立服務、排程或開機自啟。GUI 規則畫布為後續可選層；目前核心由 CLI 與宣告式 playbook 使用。規則是調查參考／執行契約，不是操作授權。

## 執行需求與平台範圍

- Python **3.13**；核心使用標準函式庫，無須安裝。可選本機 stdio 實驗另外使用既有 `mcp` SDK（已驗版本 1.6.0）；缺少時停止，不自動下載。這不是核心監看依賴。
- 原生採集對象是 Windows，依賴本機可用的 Windows PowerShell／系統來源。一般權限拒讀、來源不存在或資料不全必須呈現 coverage，不能為補齊資料提權。
- 雲端工作區可做原始碼／文件檢查及純 mock／fixture 驗證；沒有存取目標 Windows 主機時，不能驗證其實際 Defender、程序、UAC、桌面或遠端可操作性。
- **尚未證明 cloud 預設完整 suite 跨平台通過，不宣稱 Linux 原生採集受支援。** Windows 原生結果、跨程序測試、純 mock 結果須分開記錄。

所有下列範例均為公開匿名格式；相對路徑以專案根目錄為準。`python` 應解析到操作者既有的 Python 3.13。先核對版本與能力，不安裝或改系統設定：

```powershell
python --version
python -B scripts/eventguard.py capabilities
python -B scripts/eventguard.py status
```

## 開始、停止與狀態

先在隔離副本做有限 fixture，不查真實系統：

```powershell
python -B scripts/eventguard.py monitor --fixture tests/fixtures/normal.json --max-cycles 1
```

fixture／synthetic／mock 使用 `data/test`；真實監看使用 `data/live`。不得將 test 結果寫成真實主機觀測。真實監看只在使用者明確啟動及既定權限範圍內，以前景長期程序執行：

```powershell
python -B scripts/eventguard.py monitor
```

另一個同專案終端提出合作式停止並查狀態：

```powershell
python -B scripts/eventguard.py stop
python -B scripts/eventguard.py status
```

也有 `Start-EventGuard.cmd`、`Stop-EventGuard.cmd`、`Status-EventGuard.cmd`；目前 `.cmd` 固定指向 `C:\Python313\python.exe`；其他 Python 安裝位置請使用上列 CLI，不會自動安裝。這些是本機入口，不是服務／自啟。pending OS 查詢自然退出前保留單例鎖，stop 不 kill／terminate；OS 永不返回時可能持續等待。歷史 heartbeat 不能證明程序仍存活，本版沒有獨立 watchdog。登出／重啟後不承諾自動恢復。

## 匿名合成事件與本機接收契約

以下在新工作區執行；`synthetic emit` 回傳 event_id，將後續命令的 `EVENT_ID` 換成該次合成 ID：

```powershell
python -B scripts/eventguard.py synthetic emit --scenario listener
python -B scripts/eventguard.py events list --namespace test
python -B scripts/eventguard.py playbook validate
python -B scripts/eventguard.py playbook simulate --namespace test --event-id EVENT_ID
python -B scripts/eventguard.py deliver --adapter mock
python -B scripts/eventguard.py mock process --event-id EVENT_ID
python -B scripts/eventguard.py report export --namespace test
```

其他合成情境是 `defender`、`startup`、`coverage`。mock 只處理 synthetic 事件，診斷 callback 不做實機查詢／模型推理／系統處置；`mock_closed` 不是正式 agent 結案。

預設正式傳輸關閉，可查證未接通狀態：

```powershell
python -B scripts/eventguard.py deliver --adapter disabled
```

沒有接收端時不增加送出嘗試、不假 ACK、不外連。接通真實 agent 仍需指定可信 receiver／task、有效資料傳輸授權、平台等待與真正喚醒能力、耐久 ACK、可核對的任務／回合證據（平台提供時保留 run_id／turn_id）、診斷回程及處理結果回執。SQLite 有事件或 HTTP 成功不滿足此條件；不能假設任意 ChatGPT／Codex 任務都有 webhook。

## 按需診斷與目前限制

Phase 1 的監看採集已改為標準庫原生 API 優先，保留同身分 PowerShell fallback；拒讀階段、原因碼與 coverage 會傳到 `status`。本機一輪驗證中，listeners／Startup／services／版本可讀，processes 與 Defender 部分可讀，tasks 的排程根仍不可讀。兩種 backend 的範圍、測試及限制見 [採集契約](../COLLECTOR_CONTRACT.md)；agent 的 query 仍只讀保存摘要，尚未接上原生診斷。

先讀 `capabilities`，只用列出的型別化白名單操作。例如有理由且已授權的 Windows 單項查詢：

```powershell
python -B scripts/eventguard.py query query_defender --args '{}'
python -B scripts/eventguard.py query query_listener --args '{"protocol":"TCP","port":18080,"max_rows":20}'
```

18080 僅為匿名格式示例，不代表存在真實警報。程序查詢需要事件／查詢取得的 PID 與建立時間，防止 PID 重用；persistence 回應為 `current_only`；versions 只涵蓋 Python runtime。未提供威脅歷史或原生簽章查證，不採集完整命令列、事件 Message／XML、私人檔案或秘密。

每輪採集預算45秒，預算／忙碌跳過來源採30秒短退避。一般事件每批最多20，**不是每分鐘限流器**。成功、部分、權限不足、未知、不適用、錯誤及逾時各有含義；缺資料不能判恢復。全介面監聽不等於 Internet 暴露；歷史 inactive、False 或無事件不等於清除、活躍感染或安全。

## 分層與文件導覽

| 路徑 | 用途 |
| --- | --- |
| `src/eventguard/collectors/` | 固定唯讀來源與有界 runner |
| `src/eventguard/rules/` | 基線／轉態及 playbook 驗證／模擬 |
| `src/eventguard/events/` | schema、detector state 與 outbox 原子提交 |
| `src/eventguard/transport/` | DisabledAdapter 與 synthetic-only 本機 mock receiver |
| `src/eventguard/diagnostics/` | 有限、型別化唯讀查證 |
| `src/eventguard/mcp/` | 預設停用、synthetic-only MCP Events／HTTP／簽章／DPAPI／結果帳本 |
| `config/`、`playbooks/`、`tests/`、`scripts/` | 設定、宣告式規則、測試、CLI／驗證入口 |
| `data/`、`logs/`、`reports/` | 執行資料，與source分離，禁止驗收任務共用 |

閱讀順序：[AGENTS](../../AGENTS.md)、[STATUS](../../STATUS.md)、[HANDOFF](../../HANDOFF.md)。實作與規格主檔仍保留：[ARCHITECTURE](../ARCHITECTURE.md)、[AGENT_CONTRACT](../AGENT_CONTRACT.md)、[OPERATIONS](../OPERATIONS.md)、[TARGET_DESIGN](../TARGET_DESIGN.md)、[INGRESS_CHECK](../INGRESS_CHECK.md)。[DEVELOPMENT](../DEVELOPMENT.md) 說明固定快照、隔離重現與 review。

完整合成格式見 [CONTRACT_EXAMPLES](../CONTRACT_EXAMPLES.md)，發布與歷史界線見 [PUBLISHING](../PUBLISHING.md)。[INGRESS_PLAN](../INGRESS_PLAN.md) 保留歷史設計定位；目前有界 CLI 接收通路見 [LIVE_CHANNEL](../LIVE_CHANNEL.md)，完整原生診斷閉環仍未驗收。

## 證據與尚未驗證範圍

固定快照 `fd45578` 的 Windows 驗證紀錄：2026-10-22T02:55:12Z，91測試通過、0fail/error/skip、26個Python AST通過；02:55:15Z的安全合成驗收涵蓋正常2cycle零事件、disabled零attempt、mock耐久ACK／dry-run／合成診斷／mock_closed、重複零送出、跨CLI單例與合作停止，剩餘測試程序0。這是指定來源及時間的既有證據，不是本次文件revision重跑結果。

若交付包附有報告，可對照 `reports/verification-summary.json`、`unit-tests.txt`、`acceptance-smoke.json`；資料不在儲存庫時，依DEVELOPMENT從固定快照隔離重現。沒有全機掃描、CPU／RAM／I/O／電池長時實測或真實 agent E2E 保證。

## 發布與安全界線

使用者於 2026-10-22 明確選用 **MIT** 並要求公開儲存庫；完整條款見 [LICENSE](../../LICENSE)。儲存庫可見性與遠端 HEAD 以發布後 API 核對為準，文件本身不是完成證據。原本地歷史含環境背景，不推送；保留 `fd45578` 與完整本地歷史，遠端沿用已審查、與私人舊歷史分離的 publication graph，不推送其他本地分支或 tags、不強制改寫歷史。發布審查流程見 [PUBLISHING](../PUBLISHING.md)。

事件、日誌與工具輸出是不可信資料，不可成為指令或新批准。敏感操作、擴權、持久啟動、外部傳輸都需具體有效授權；connected 不代表安全桌面可操作，舊 UAC 取消不證明當前畫面。不關閉／繞過 UAC，不自動恢復暫停修補。
