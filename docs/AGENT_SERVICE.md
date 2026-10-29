# 選配：事件驅動的專用 agent

## 選用單事件調查：獨立保存後才 ACK

`saved-investigation-v1` 是明確選用、目前只接受自有合成事件的四工具模式。預設持續派送仍沿用下文三工具契約，歷史真收件證據不升格為新調查驗收。

1. `receive_event` 接收指定事件。
2. `query_evidence` 回傳該事件已保存、經白名單投影的 `saved_evidence`，包括 facts、limitations、payload／evidence hash；不查 Windows。listener 可讀 protocol、port、binding_scope；全介面綁定不代表 Internet 可達。
3. `save_investigation(event_id, query_id, report)` 獨立保存 agent 撰寫的分析，尚不 ACK。report 必含 `summary`（1–400 可列印字元）、`fact_keys`（實際回傳 facts 的鍵）、完整 `limitations`、`finding=metadata_requires_followup` 與 `next_step=request_authorized_evidence`。
4. `ack_event(..., decision="needs_more_evidence")` 只接受同事件／query 已保存且內容綁定的報告；成功回條送出後 MCP 自然退出。

報告保存在既有 result／completed 記錄，含事實值、查詢及內容雜湊；不另建佇列。寫入失敗、容量不足、錯誤身分或內容改寫不得跳過保存。ACK 已完成而退出證據失敗時，整體驗收仍失敗，實際 ACK 狀態另列，不能冒稱仍 pending。人類 handled 與 agent ACK 持續分離。

摘要是明示不可信的 agent 評估，hash 證明內容綁定，不是來源認證或安全結論。所有結果維持 `incident_conclusion=not_assessed`、無處置；本模式不代表真實原生覆蓋或防守成功。

準備一個新目錄（不呼叫模型）：

```powershell
py -3.13 -B scripts/validate_delivery.py investigation --root reports/investigation-NEW --codex-executable "<已核對的原生 codex.exe>"
```

先讀該目錄 `AUTHORIZATION_REQUEST.md`／`investigation-scope.json`，取得當次有效模型批准，將批准原文、UTC 時間與 scope hash 寫入 `human-approval.json`。未批准時該檔預設 false，不能自行改成批准；fixture 批准不算人類授權。相同命令加 `--execute` 才執行；使用過的目錄不重試，來源／binary／launch 改變需重新準備及核對範圍。

範圍是一件合成 listener、一個 CLI 任務、執行期限180秒、預期四工具各一次；合作退出與證據收尾另計。使用 CLI 既有預設模型，不保證模型內部請求數、token 或費用的硬上限。stdout／stderr 各限4MiB；完成記錄沿用4KiB階段預留。沒有 shell、原生查詢、瀏覽器、其他工具、系統變更或處置。

驗收看 `validation.json`、`stage-1/assessment.json`、原始 trace／capture／MCP持有 HANDLE 退出證據、inbox completed 與來源 SQLite ACK；必須逐項對齊同一 event／query／report ID 並自然退出、無殘留／強停。`--verify-only` 只核對既有資料。實際 SDK／fake CLI 測試不能代替真模型驗收，也不證明獨立模型來源或既有桌面聊天被喚醒。

普通 Python 程式等待原佇列。有符合條件的事件才啟動短期 Codex CLI。
不續接既有桌面聊天。不建立服務、排程或開機自啟。
專用原生 Codex CLI 的單事件真收件已通過：receive → query → 保存結果 → ACK 各一次，pending 0；MCP、CLI、supervisor、host、外層驗收程序皆自然 exit 0。證據是 `reports/service-acceptance-eventguard-mcp-exit-20261025-04`，不是既有桌面聊天喚醒。最新完整回歸與適用版本見 [STATUS](../STATUS.md)；本頁命令不構成新增模型或主機採集授權。

## 現在可以怎麼用

適合把已保存且符合條件的本機事件交給一個短期 Codex 任務，取得最小 metadata 查證及耐久收件回條。沒有事件時由普通程式等待；不讓模型持續輪詢。人類仍可獨立查看事件、保存處置狀態及停止應用。ACK 表示接收流程完成，不表示漏洞已修復或主機安全。

這裡保存的結果是固定 decision、result ID 與 `incident_conclusion=not_assessed` 等結構化收件紀錄；不是任意 agent 分析全文。`query_evidence` 重讀已保存的七欄摘要，不查 Windows；事件 `diagnose` 是另外一個會執行事件綁定唯讀查證的操作。人工 `set-status handled` 與投遞 ACK 分開。

| 目的 | 入口 | 查證範圍 |
| --- | --- | --- |
| 看當前產品狀態、檢查既有原生 CLI 能力 | 下節 `agent status / capabilities / start` 預檢 | 不啟動模型；CLI 可啟動不等於已登入或能完成收件 |
| 已批准來源的持續派送 | `agent start ... --execute`，操作見下文 | 預設讀 `data/live`；是持續 host，不能當成只跑一件的驗收 |
| 精確一件合成事件、一個 CLI 任務 | 本頁「驗收界線」的 `validate_delivery.py service` | 單次新目錄、180 秒有限生命期；需要當次有效模型範圍 |
| 查已通過那一件，不再執行 | 下列 PowerShell 讀檔 | 原證據，沒有重新接收、ACK、模型或原生採集 |

### 查閱已完成事件的結果與 ACK

在專案根目錄執行以下讀檔命令：

```powershell
$egProof = 'reports/service-acceptance-eventguard-mcp-exit-20261025-04'
$egDelivery = Get-Content -LiteralPath "$egProof/communication-result.json" -Raw | ConvertFrom-Json
$egDelivery | Select-Object passed,event_id,query_id,result_id,counts
Get-Content -LiteralPath "$egProof/validation.json" -Raw | ConvertFrom-Json |
    Select-Object passed,chronology_verified,one_attempt_verified,per_stage
Get-Content -LiteralPath "$egProof/inbox/completed-3ec2cdb0a81b98d4004ad7152cee44be1b7c8c1698ae18d18a7676fabfe1730d.json" -Raw |
    ConvertFrom-Json | Select-Object snapshot,query,result
Get-Content -LiteralPath "$egProof/mcp-exit-validation.json" -Raw | ConvertFrom-Json
Get-Content -LiteralPath "$egProof/execution-exit.json" -Raw | ConvertFrom-Json
```

該 event ID 是 `evt-a6e83a0f0b754013952fca894cd615b8`。先核對生成、接收、query、result、ACK 都指向它，計數各 1、pending 0、duplicates 0；query ID 與 result ID 也必須一致。完成檔保留實際 receive/query/result 時間與七欄 snapshot；SQLite `source/eventguard.sqlite3` 保存來源事件及 ACK，原始交叉核對已按唯讀連線驗證結果先存再 ACK。完成檔自身的 `acked_at` 不應替代來源 SQLite 的 ACK 時間。

`validation.json` 保留三個真工具完成、時間順序與 host 身分核對；`communication-result.json` 分別列 CLI、supervisor、host、外層的退出回條。MCP 另看 `mcp-exit-validation.json` 的 `passed=true`、`ack_response_flushed=true`、`mcp_natural_exit_verified=true` 及 `mcp_exit_code=0`，其原始 marker／活體保留 HANDLE 回條在該 attempt。外層 `execution-exit.json` 須為 exit 0、remaining 0、無強停及擷取完整。不能只憑模型文字或一個 `passed` 欄位判定收件。

一般 `agent inspect --namespace test` 讀預設 `data/test`／`data/agent-delivery-test`，不會自動找到這份 reports 內的隔離來源。`events detail --namespace test --event-source <上述目錄>/source` 可看來源事件及人工處置，但不會合併 query/result 或 MCP 退出證據。避免將不同來源的空清單誤判為未收件。

既有 `--verify-only --require-mcp-exit` 可重讀並核對原證據，不啟動模型或再 ACK；它會取得鎖並重寫驗證摘要，並非純檔案唯讀。只需查看時使用上方讀檔命令，不必重跑已通過的驗收。

## 查看與預檢

本機採集及 Web 照常使用 `EventGuard.cmd run`。兩者不需要 agent。

```powershell
.\EventGuard.cmd agent status
.\EventGuard.cmd agent capabilities
.\EventGuard.cmd agent start --codex-executable C:\既有安裝\codex.exe
```

最後一條預設只預檢。不啟動背景或模型。不接受 cmd／bat／ps1 包裝。
正式預檢會檢查來源、MCP SDK及接收權限。App 通訊不設每日任務預算。
登入未在預檢中驗證。CLI 可啟動也不代表能呼叫模型。
缺能力時顯示原因。不得下載、提權或刪帳本解禁。

## 明確啟用、暫停與停止

以下啟用會使用模型。須先有適用的資料及模型批准；已通過的單事件證據不等於啟用正式來源的持續批准。

```powershell
.\EventGuard.cmd agent start --codex-executable C:\既有安裝\codex.exe --execute
.\EventGuard.cmd agent pause
.\EventGuard.cmd agent resume --execute
.\EventGuard.cmd agent stop
```

start 使用現有 `data/live` 與 `data/agent-delivery`。
`--namespace test` 改讀隔離合成範圍。真正模型仍需有效批准。
重啟沿用同一 inbox、來源綁定及 dispatcher 帳本。
不因來源目錄、host 重開或 ACK 重置額度。

pause 保存暫停，只阻擋新任務。已啟動任務不因 pause 被取消。
暫停閘道與實際程序啟動的屏障證據分開顯示。未確認就標未知。
resume 預設仍只預檢；加 `--execute` 才解除暫停。
stop 保存停用，合作停止本 host。必要清理只限已核對的私有 Job。
強停或缺完整退出回條不得記為自然成功。
這些命令不停止採集，也不刪除 pending。

## 篩選與執行範圍

編輯 [config/agent-dispatch.json](../config/agent-dispatch.json)。
預設選 high／critical、固定事件種類及 new／read。
handled／ignored 不自動派送。這些狀態不是 ACK，原事件仍保留。
低嚴重度事件不能擋住後面的高嚴重度事件。
設定只接受枚舉清單。不能放命令、目的聊天或自由 prompt。
去重與冷卻沿用原事件來源及帳本，不新增第三份佇列。

篩選前核對 pending 的 schema、內容 hash 及處置狀態。
損壞、超限或未知格式會阻擋派送，顯示固定原因碼。事件不刪除、不 ACK。
有效的低嚴重度事件仍會保留，不妨礙後方符合條件的事件。
驗證快取只放記憶體，最多 1000 筆。原文或 hash 改變就重新驗證。
這不提供防同帳戶竄改的保證。修復資料後，可明確重啟 host；不自動重啟模型。

App 不設每日五次限制。無事件時不呼叫模型。
人工指定的單次驗收上限仍有效，不代表產品日預算。
歷史預算工具與資料保留，正常通訊不讀取或修改。
未知退出與未完成收件仍阻擋盲目重試。

## 人類可看見的證據

本機 Web 的「Agent 派送」頁顯示程序、心跳、待收數及阻塞原因。
頁面可暫停或停止。不提供啟動或恢復模型的按鈕。
重新整理只讀保存狀態，不做模型輪詢。

```powershell
.\EventGuard.cmd agent inspect --namespace test --event-id <ID>
```

事件詳情也顯示同一份投遞階段。保存、receive、query、結果與 ACK 分開。
inbox 證據不能獨立證明模型執行。缺 provider 生命週期證據時顯示 unknown。
dispatcher 自己另保存真 CLI trace、工具回傳、結果及 owned-tree 退出回條。
模型用量缺失時顯示未知，不假裝為零。

人類 CLI 與 Web 可按事件查 `provider_evidence`。後續任務開始後，仍可查保留的舊 attempt。
查詢沿用原帳本及回條。已輪替的完成帳本保留有界參照，不建立另一份佇列。
只讀本專案受管理的 run／attempt 及已綁定的來源。舊資料缺少綁定、證據已清理或內容不符時，仍顯示未知。
`agent_started=observed` 只表示已核對 CLI 程序啟動。回合完成、工具收件及程序退出各有自己的證據。
這些是 CLI 協定證據，不能單獨證明模型來源。fake CLI 不會因此成為真模型驗收。
此查詢不接收、不 ACK、不啟動模型，也不改變人類處置狀態。模型七欄不增加這些本機資料。

新的 managed attempt 另保存 supervisor 的 PID、建立時間及本次 nonce。
worker 核對綁定後，才可啟動 CLI。退出回條必須符合原身分。
缺少身分或回條時標未知。舊回條不補造新證據，也不升格為本版驗收。
CLI 未啟動不代表 worker 已退出。缺 worker 退出證據仍阻擋重入。
空閒的零請求結論來自本 adapter 未啟動 CLI；它不是整個帳戶的用量量測。

## 給其他應用的封裝

```powershell
.\EventGuard.cmd agent export --namespace test --event-id <ID> --producer-id <固定UUID4>
```

producer UUID 必須由整合者建立一次並耐久保存。不能每次產生新值。
它不得包含主機或使用者名稱。export 不會自己建立身分、收件或 ACK。
輸出為 CloudEvents 1.0 的受限 profile，data 仍是原七欄。
schema 見 [event-ingress.schema.json](../config/event-ingress.schema.json)。
同 source＋ID 不同內容是衝突。wire hash 與原 EventStore hash 不混用。
外部公告及事件皆是不可信資料。不能變成命令、工具權限或目的地。

OpenOctopus 可使用此 adapter。其 Inbox、provider 與 UI 尚未在該專案實作或驗證。
Codex 桌面 queue 仍是未驗證候選，不阻擋專用 CLI 路徑。

## 驗收界線

測試證據見 [EVIDENCE](EVIDENCE.md)。fake CLI、實際 Windows Job 與真模型分列。
真驗須先指定合成範圍、有限任務數與正常退出條件。
必須核對生成／receive／query／結果／ACK 的 event ID 集合。
只有真工具回傳及退出證據齊全，才能宣稱真正 agent 收到事件。
ACK 不代表漏洞已修復、主機安全或人類案件結束。

既有驗收入口新增 `service`。以下只準備一件公開合成事件及空來源，不啟動 host 或模型：

```powershell
py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-NEW
```

取得本輪有限批准後，先在該新目錄的 `human-approval.json` 記下直接授權文字、時間、事件／CLI／期限範圍。由當次已審查的私有 Job 啟動器執行以下內層命令，保留外層原 HANDLE 與退出回條；不可重用已消耗的真04目錄或它的單次啟動器：

```powershell
py -3.13 -B scripts/validate_delivery.py service --root reports/service-acceptance-NEW --codex-executable $codexExe --execute --require-mcp-exit
```

`$codexExe` 是已安裝、已核對的原生 `codex.exe` 完整路徑。只執行 prepare 不啟動程序或收件；實際流程才會先空等、生成／入列一件、啟動唯一 CLI，依序呼叫 `receive_event`、`query_evidence`、`ack_event`。結果由工具保存後才 ACK。失敗保留來源原狀、已保存結果與 ACK 進度，先核對退出，不自動新增事件或重送模型。ACK 已成功但收尾驗證失敗時，不會回退為 pending。`--execute` 是執行開關，不能代替人類授權記錄與啟動器檢查。
程式先等空佇列，再加入事件。最多一個任務，總期限 180 秒，最後合作停止隔離 host。
有限驗收使用既有 application-owned Job。驗收程式持有實際 child handle，不 detach、不離開外層 Job。
父應用身分不明、退出或期限到達時，host 合作停止。CLI 啟動前也重查父應用與期限。
停止後另保存手持 HANDLE 的退出回條，不把未知 OS exit 當成 0。此模式明示 lifetime_limited，不證明獨立背景壽命。
產品 `agent start` 的獨立模式不變。外層 Job 不允許確認獨立生命期時仍拒絕，不使用 breakaway 或測試繞過旗標。
根據 intent 拒絕同目錄重跑。失敗先讀該輪 trace、stderr、狀態及退出回條。
`--verify-only` 只重驗既有證據，不啟動模型，不重新收件或 ACK。
驗收另核對 SQLite 保存時間、worker／CLI 建立時間、receive／query／result／ACK 順序。
空閒觀察同時核對 UTC 及同一 scope 的 monotonic 時鐘。缺證據或時間倒置不通過。
前後短暫空閒只證明該窗口。它不代表長期 soak 或獨立背景壽命已驗證。

## 下一項實機關卡與未涵蓋範圍

單次 listeners 基線位於 `reports/windows-listener-baseline-20261026-01`，2026-10-27 已取得原具名批准並執行一次，授權已使用。四表成功共235列，但必要程序身分缺111列、21錯誤，結果為 `partial`／`baseline_incomplete`，完整基線未通過。query .739012秒、內Job自然exit0／外validator自然exit2，兩者remaining0／無強停；結果與13/13收據一致性核對在同目錄，不把後者當baseline PASS。不要再執行原命令或重問這次批准；後續native診斷／重驗需另有精確授權。原單次範圍見該目錄的 `AUTHORIZATION_REQUEST.md`、manifest與下表：

| 項目 | 已準備的範圍／完成條件 |
| --- | --- |
| 目的與資料 | 一次 native TCP／UDP、IPv4／IPv6 listeners 表與必要 owner 建立時間；端點事實只在記憶體處理，落盤只留固定狀態／計數及本工具退出回條 |
| 時限 | query 5 秒、總工作預算 30 秒；既有外層啟動器在 20 秒觸發合作 stop，再留 3 秒 grace；不是對每個 OS syscall 的硬中斷保證 |
| 收尾 | 執行前加入私有 Job，保留原 HANDLE；四項查詢完整、無截斷／缺口／取消、內外自有程序自然 exit 0、remaining 0、無強停才通過 |
| 授權 | 當次直接人類批准，綁定既有 root/run/hash/scope；批准時間及最長 30 分鐘有效期在執行前寫入 `human-approval.json`，一次使用 |

這個 baseline 不注入 socket、不修改登錄／系統／帳戶、不啟動模型或其他來源。它只查當次採集完整性，不生成新事件、不重新驗收 agent，也不證明 listener new/resolved 生命週期；loopback 按現有規則被忽略，不能拿它冒充陽性事件。

原生來源端到端、既有桌面／dot 閒置喚醒、24 小時 production 與 reboot 皆未驗。24 小時需依 [既有 soak 計畫](SOAK_PLAN.md) 固定隔離目錄、真實起訖、負載、資源及停止條件，有限 runner 不能直接當 24 小時成果。桌面喚醒需具名目的地、受支援入口及真 turn／事件／結果／ACK 證據，不能由新專用 CLI 推定；條件與授權見 [事件驅動](AGENT_EVENT_DRIVEN.md)。沒有建立排程或會話外自動恢復機制。
