# Phase 2：agent 角色比較與選案

狀態：**比較已完成，等待使用者選 A／B；兩案皆未實作。** 建議 A：確定性 playbook＋本機報告，agent 接收降為可選。原因是目前能核查的增益來自唯讀查詢，尚無 agent 本身增加診斷價值的證據。這不是對未實測模型能力的否定。

程式基準 `088be7561c5ead1bb4e289ad3b4ef6ce03748398`，分支 `feat/local-codex-acceptance`。2026-10-22 21:53（UTC+8），Python 3.13.3。此輪只讀碼及離線 synthetic／fixture 元件比較，沒有真 Codex、模型請求、原生來源查詢、網路或系統變更。Phase 1 七來源結果沿用其證據，未因重新開機而重新採集或宣稱 coverage 改善。

## 1. 程式目前能證明什麼

以下「已驗證／靜態」指指定 commit 原始碼；「已驗證／離線」指本輪執行結果，均不等於真 agent 診斷。

| 結論 | 證據與等級 |
| --- | --- |
| receive 只提供 event_id、event_type、transition、severity、synthetic、observed_at、coverage_status 七欄 | 已驗證／靜態：`src/eventguard/queue_inbox.py:83`、`:286`；已驗證／離線：current-tool-responses.json |
| query 重讀同一 snapshot，不呼叫原生診斷；query_id 是與事件 payload hash 綁定的回條 | 已驗證／靜態：`src/eventguard/queue_inbox.py:304`、`:313`；已驗證／離線：兩個 snapshot 相等，新觀察欄位 0 |
| 正常 prompt 明確要求 decision=reviewed_metadata；不是 agent 得到新證據後才選出的案件判定 | 已驗證／靜態：`src/eventguard/agent_dispatch.py:36`；ACK 介面另接受 needs_more_evidence，見 `src/eventguard/queue_inbox.py:30` |
| result_id 由事件、payload、query、decision 決定；incident_conclusion 固定 not_assessed；ACK 只證明回條保存 | 已驗證／靜態：`src/eventguard/queue_inbox.py:356`；已驗證／離線：重播同結果、SQLite 一筆 receipt；real_agent_wake_verified=false |
| idle 的 dispatcher 由 Python 查 pending，沒有事件就等候；不是模型常駐輪詢 | 已驗證／靜態：`src/eventguard/agent_dispatch.py:379`、`:390`、`:433`；本輪沒有啟動 dispatcher 做長期測量 |
| playbook 現在只有驗證／選圖／dry-run，不執行圖中的工具或 agent_decision | 已驗證／靜態：`src/eventguard/rules/playbooks.py:266`；已驗證／離線：tools_executed=[]、actions_executed=[] |
| 既有 DiagnosticAPI 真的可呼叫 collector，但還沒接入 queue MCP；先列舉來源再過濾，不是所有操作都有低成本單物件 API | 已驗證／靜態：`src/eventguard/diagnostics/api.py:12`、`:99`；已驗證／離線：只注入 fixture，沒有本輪 OS 查詢 |
| listener 事件有 protocol／address／port／PID，沒有程序建立時間；不能安全地由 PID 直接追到原程序 | 已驗證／靜態：`src/eventguard/rules/detector.py:291`、`:293`、`:295`；Phase 1 process collector 的建立時間不會自動補入該事件 |
| 現有 DiagnosticAPI 會傳 name/path 等字串；redact 去控制字元及遮罩使用者目錄，不會消除指令式名稱 | 已驗證／靜態：`src/eventguard/diagnostics/api.py:110`、`src/eventguard/collectors/windows.py:208`；已驗證／離線：惡意語氣的合成程序名仍在結果中，控制字元已移除 |

文件差異：`docs/AGENT_CONTRACT.md` 開頭仍稱接收端未接通；當前 README／HANDOFF 已記錄歷史有限 CLI 接收成功。前者不能覆蓋已存在的通路證據，後者也不能升格為診斷成功。全面整理歷史留 Phase 6；本報告以當前程式和本輪證據為準。

## 2. 同一事件的離線比較

指令：`python -B reports/phase2-role-001/compare.py`，exit 0。專用忽略目錄內由程式產生一件 synthetic listener 事件，未讀或改正式 outbox。原始 event ID 及相同事件關聯留在本機，不放公開文件。

| 路徑／元件 | 實際產出 | 新診斷事實 | 本輪狀態 |
| --- | --- | --- | --- |
| 現有確定性 playbook | 選中 pb-listener-change、固定調查計畫、無工具或處置 | 0；只是計畫 | 已執行，不是 A 完整實作 |
| 現有 receive → query → ACK | 七欄 snapshot、query/result ID、耐久接收回條、not_assessed | query 相對 receive 新增 0 | 直接 Python 元件呼叫，沒有 MCP client／CLI／agent |
| 既有型別化 listener＋process 查詢 | fixture 中確認指定 TCP port 的一筆觀察與匹配 PID＋建立時間；保留 coverage | 有 fixture 的後續觀察；不是主機事實 | API 元件已執行，不是 B 實作 |
| 不使用模型的對照 | 對同事件的同一可信參數映射，再呼叫同一組 fixture 查詢 | 排除 request ID／計時後，兩次觀察相同 | 證明取得這些 fixture 事實不需要模型；未量測真 agent 增益 |

probe 的事件額外帶有合成 PID＋建立時間，僅供現有 API 比較；**正式 listener 事件目前沒有該時間**。probe 沒有製造正式 MCP 綁定或修補 detector，不能說 B 的前置缺口已完成。

單次首次呼叫計時（非效能保證）：playbook 載入／驗證／規劃 4.4207 ms；receive/query/ACK 含 SQLite 與 fsync 119.383 ms；兩個 fixture 診斷呼叫共 0.3567 ms。三者工作量不同，**不能當成 A／B 端到端速度比較**；未涵蓋真 provider、MCP、CLI、網路或模型延遲。

## 3. A／B 選擇

下表是候選行為與工程判斷；未實作部分不能視為已驗收能力。

| 比較面 | A：確定性 playbook＋本機報告 | B：agent 取得事件綁定診斷 |
| --- | --- | --- |
| 同事件的價值 | 固定規則列觀察、coverage、未知與後續建議；既有唯讀查詢可由固定流程取得 | 應在相同證據下增加可核查的診斷價值；目前沒有量測到此增益 |
| 需要補的程式 | 將選圖中的已實作操作接成固定受限流程，保存本機結果；沿用現有 JSON／HTML 報告，先不新增通知平台 | 除左欄共同的綁定／結果工作，還要 MCP 事件查詢介面、輸出嚴格 projection、agent 結果驗證、模型限額與失敗恢復 |
| 等待／事件延遲 | 程式等待；事件後是本機保存與允許的查詢成本 | 程式等待；事件後再增加 CLI／MCP／模型回合。增量大小尚未量測，OS 查詢 hang 兩案都受影響 |
| 模型成本 | 主路徑不呼叫模型 | 每件被選中的事件可能多次模型請求；本輪未呼叫，未測 token／帳戶額度或金額，不估價 |
| 共同失敗面 | 採集 partial／denied、過期事件、PID 重用、SQLite／容量、OS hang | 同 A；額外有模型端點、CLI／MCP、工具誤用、指令注入、結果不合 schema、重試與回合成本 |
| 可重現性 | 相同事件／證據／規則版本可得到相同判斷路徑 | 工具事實可重現；模型解釋與選路須另外驗證，不用文字自稱代替證據 |
| 結論邊界 | 固定預設 incident_conclusion=not_assessed；不以 ACK 或空列判安全 | 同 A；agent 文字不能跳過明確證據規則、coverage 或批准 |

**建議選 A。** 本輪顯示既有自動 agent 主要多了一次摘要接收回條，型別化查詢的事實也能由程式取得。先讓確定性結果可用，保留未啟用的 agent 選項；待有量化增益再選 B。依使用者要求，由使用者選案後才改執行路徑；本報告不移除現有通路或更改預設。

如果選 B，先只完成離線事件綁定與對抗性測試；**選 B 不等於批准呼叫真模型**。真 agent 的有限評估仍需當次範圍，沒有批准時不得冒用歷史 A/B/C 的同意。

## 4. 兩案共用的最小契約（候選，未實作）

1. 可信本機流程按已耐久保存的 event_id 讀事件、核對 payload；從固定事件型別映射到已實作操作。事件裡的任意文字、rule_ref 或外來 tool output 不提供授權，不讓 event 自行指定命令／工具。
2. listener 參數由事件 protocol／port 綁定；process 只能用事件當時的 PID＋建立時間或可靠 instance_ref。舊事件缺建立時間，明示 process_binding_missing／unknown，不能用現在查到的建立時間補成「同一程序」。後續 listener 觀察也不能單憑 port 等同原程序。
3. persistence 的 kind 僅 startup／services／tasks；Defender 僅既有 settings；版本僅固定 python_runtime。來源不可讀、未實作的 baseline diff／signature／threat history 不擴成功能，不從 playbook 候選 operation 自動取得執行能力。
4. 結果分開保存 observations、coverage（含來源／時間／錯誤碼／截斷）、uncertainties、incident_conclusion。ACK 是接收，診斷完成是另一狀態；ACK 前失敗仍保留 pending，不假結案。保留去重與既有回條證據。
5. 本地 HTML 報告沿用 escape；可見名稱只是資料。沒有新處置、外傳、通知服務、背景安裝或長期保證。長期不卡死仍需 Phase 3／4，不能由本階段報告提前宣稱。

## 5. B 額外必要的閘道（候選，未實作）

- MCP 僅接受已綁定 event_id 與固定 query_kind 枚舉；PID、時間、port、來源均由 server 取可信事件，agent 不能提供命令、路徑、自由字串查詢或替換來源。單任務不得讀其他事件。
- 輸出以枚舉／數值／ID 為主；預設不把程序名稱或路徑傳給模型。確實需要字串時，逐欄限定用途、長度及字元集，禁止控制字元；不能把「redact 過」當成可信或無指令注入。
- 至少測試指令式程序名、CR/LF／ESC、超長值、Unicode 混淆、額外參數、跨事件／query ID、PID 重用、缺建立時間、partial／denied／stale／截斷、同事件重試。不執行事件文字，也不以 fixture 判斷模型已抵抗注入。
- agent 的 diagnosed 回條必須引用這次事件的工具證據，列實際觀察、coverage、不確定性。未知或純解釋維持 incident_conclusion=not_assessed；不得把 reviewed_metadata 改名就當診斷。
- 未獲真模型批准前，B 的額外判讀品質、延遲與成本均為未測。後續評估需同一匿名 synthetic 事件／證據集與確定性控制組，預先定義可核查新發現數、錯誤結論數、保留未知的正確性、工具／回合數及完成延遲。沒有增益即採 A、agent 可選。

## 6. 本輪驗證與證據

本機單一來源：`reports/phase2-role-001/summary.json`。**18 項既有相關 fixture 測試通過，0 failure/error/skip**，測試 0.9717 秒；另外 18 個 probe 斷言均通過，兩者不同、不得相加稱為測試數。範圍為 DiagnosticTests 9、PlaybookTests 6、QueueInbox 指定 3；未重跑全套或 Phase 1 Windows 採集。

實際輸出摘要：

```text
source_commit=088be7561c5ead1bb4e289ad3b4ef6ce03748398
scope=offline synthetic and fixture components only
snapshot_observation_fields_added_by_query=0
model_calls=0; real_codex_tasks=0; native_provider_queries=0
tests: run=18; passed=18; failures=0; errors=0; skipped=0
source_bytes_unchanged=true; external_attempts=[]; passed=true
process exit=0
```

其餘本機證據：compare.py（精確執行方法）、synthetic-event.json、deterministic-plan.json、current-tool-responses.json（同事件及 SQLite receipt）、typed-fixture-results.json、tests.txt；驗證器保留原始碼 hashes，禁止該程序建立 subprocess／網路／DLL／registry 查詢。這只是離線探針防誤呼叫，不是產品 sandbox 或對所有程序的外部稽核。執行資料均受 Git 忽略，不提交或推送。

與 AUDIT 的差異：Phase 1 已改善採集及 coverage 證據，但 AUDIT 所指出 snapshot-only／prompt 固定 reviewed_metadata、listener 缺程序建立時間、playbook dry-run、停止與容量缺口仍成立。本輪對抗性 fixture 另確認「目前資料最小化不等於可直接把 DiagnosticAPI 字串公開給模型」。

尚未驗證：A／B 完整執行器、真 agent 增益／成本／延遲、重新開機後七來源可讀性、任意 OS hang 的退出、長期容量與 soak、monitor_gap、實機注入。未開始 Phase 3–7。下一步只需使用者選 A 或 B。
