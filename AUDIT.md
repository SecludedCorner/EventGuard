# EventGuard Phase 0 稽核

日期：2026-10-22（Asia/Taipei）。本報告只涵蓋目前 checkout，不涵蓋其他對話、其他工作副本、舊 MVP 或尚未合併的背景模式改動。

## 範圍、版本與證據等級

- **已驗證／Git（E0）**：分支 `feat/local-codex-acceptance`，稽核基準 commit `9576b13a6773ce81c3a01799743d30094a48449a`；開始及寫報告前的 `git status --short` 均無輸出。沒有 fetch、reset、clean、push 或修改既有程式。
- **已驗證／靜態（E1）**：讀取指定五個目錄全部 68 個檔案；64 個 Python 檔通過 AST 解析，4 個 JSON 通過解析。逐項檢查函式、測試斷言、內嵌 PowerShell／fake CLI；沒有 import 執行專案入口。
- **已驗證／本機檔案 metadata（E2）**：只對固定專案目錄與設定、SQLite 檔讀取 ACL 摘要；沒有讀取資料庫事件內容。摘要不含帳號、私人 SID 或原始 ACL。
- **推測**：從控制流程推導的風險，尚未用故障注入或 Windows 來源實測重現。下文沒有把靜態檢查寫成測試通過。
- **本輪未執行**：單元測試、fixture/mock/fake CLI、MCP SDK client、Windows 七來源採集、真正 Codex／模型、網路、服務／排程安裝與任何程序終止。既有驗收結果不構成本輪實測。

E0 命令及實際輸出：

```text
git status --short                 # 無輸出
git branch --show-current          # feat/local-codex-acceptance
git rev-parse HEAD                 # 9576b13a6773ce81c3a01799743d30094a48449a
git ls-files .github               # 無輸出（目前沒有追蹤中的 CI workflow）
```

E1：本輪 `python -B -` 的盤點輸出（Python 3.13.3，2026-10-22 09:38 UTC）：

```json
{"files":68,"python_ast_parsed":64,"test_methods":269,"scope_sha256":"f634f5eef8deb16e4c10536e834537a4698ec684e600e33437eeb7b3aeb860fd","python":"3.13.3"}
```

重現 E1 的 PowerShell 指令；只讀檔、解析，不載入專案或執行測試：

```powershell
@'
from pathlib import Path
import ast, hashlib, json, sys
files = sorted(p for d in ('src/eventguard','scripts','config','playbooks','tests')
               for p in Path(d).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts)
digest = hashlib.sha256()
python_files = test_methods = 0
for p in files:
    raw = p.read_bytes()
    digest.update((p.as_posix()+'\0'+hashlib.sha256(raw).hexdigest()+'\n').encode())
    source = raw.decode('utf-8-sig')
    if p.suffix == '.py':
        tree = ast.parse(source)
        python_files += 1
        if p.parts[0] == 'tests':
            test_methods += sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))
                                and n.name.startswith('test_') for n in ast.walk(tree))
    elif p.suffix == '.json':
        json.loads(source)
print(dict(files=len(files), python_ast_parsed=python_files,
           test_methods=test_methods, scope_sha256=digest.hexdigest(),
           python=sys.version.split()[0]))
'@ | python -B -
```

## 主要結論

| 等級 | 發現 | 證據 |
| --- | --- | --- |
| 已驗證／靜態，高優先 | 拒讀分類沒有輸出 stage、異常類型、HRESULT／Win32；collector 還丟掉 runner 的固定原因碼，monitor 再丟掉 section coverage 原因。 | `src/eventguard/collectors/windows.py:30`、`:229`、`:234`；`src/eventguard/monitor.py:158` |
| 已驗證／靜態，高優先 | 現行 agent 通道只看保存的七欄摘要；query 不執行診斷，固定提示要求回報 `reviewed_metadata`。 | `src/eventguard/queue_inbox.py:83`、`:313`、`:356`；`src/eventguard/agent_dispatch.py:36` |
| 已驗證／靜態，高優先 | 逾時不等於子程序退出；OS 查詢永不返回時，monitor／watch 的收尾沒有期限。 | `src/eventguard/collectors/runner.py:60`、`:97`；`src/eventguard/monitor.py:61`；`src/eventguard/watch.py:173` |
| 已驗證／靜態，高優先 | inbox 與 dispatcher 帳本保留所有已完成紀錄，沒有輪替；核心 outbox 則可清除超過七天的未 ACK failed 紀錄。 | `src/eventguard/queue_inbox.py:196`、`:294`；`src/eventguard/agent_dispatch.py:234`、`:399`；`src/eventguard/events/store.py:159`、`:199` |
| 已驗證／靜態 | 正常 monitor 走確定性規則與 disabled transport；dispatcher 無事件時由 Python 等待，不啟動模型。這不代表已具備不中斷、跨登出／重啟的背景能力。 | `src/eventguard/monitor.py:160`、`:165`、`:194`；`src/eventguard/agent_dispatch.py:381`；`Start-EventGuard.cmd:5` |

## 1. 拒讀分類與 section 證據

| 路徑 | 現行分類 | 是否可從 section 區分 | 等級與定位 |
| --- | --- | --- | --- |
| Python 啟動 PowerShell 失敗 | `PermissionError` → denied／`query_launch_access_denied`；找不到 executable → not_applicable；其他 OSError → error | **不可可靠區分**；collector 只複製 status，未複製 note | 已驗證／靜態：`src/eventguard/collectors/runner.py:85`、`:88`；`src/eventguard/collectors/windows.py:234` |
| PowerShell／provider 失敗 | 走 InnerException；UnauthorizedAccessException、HRESULT -2147024891（0x80070005）、StatusCode AccessDenied → denied | 只有 denied，無 provider／namespace／object 階段 | 已驗證／靜態：`src/eventguard/collectors/windows.py:30` |
| SecurityError／PermissionDenied | CategoryInfo 對應上述分類也 → denied | 不能由 denied 推定為執行政策、UAC、provider 或 token 根因 | 已驗證／靜態：`src/eventguard/collectors/windows.py:41` |
| 單物件／欄位不可見 | Defender 欄位缺值 unknown；process path／creation time 缺值 unknown／partial；部分來源整段 catch | 沒有逐欄錯誤類型、數字錯誤碼或拒絕 stage | 已驗證／靜態：`src/eventguard/collectors/windows.py:72`、`:100`、`:255` |
| 非零退出、讀取／JSON 錯誤 | 固定 error／note | 未保留原始錯誤全文是合理最小化；但也沒有安全的結構化根因替代 | 已驗證／靜態：`src/eventguard/collectors/runner.py:103`；`src/eventguard/collectors/windows.py:273` |

**已驗證／靜態**：`Write-Result` 只輸出 status、rows、truncated；成功與失敗混合時 partial。非預期空 rows 仍可能是 ok，不能由空清單推定主機無物件；真正列舉可見性尚待實測。`src/eventguard/collectors/windows.py:44`；`tests/test_collectors_diagnostics.py:108`。

**已驗證／靜態**：目前 `status` 的 health 中已有逐來源 status、observed_at、last_success；缺的是拒絕原因、階段與可讀欄位的證據，並非完全沒有逐來源 coverage。DiagnosticAPI 的 health 只回 runner 狀態，與 monitor health 又是另一份契約。`src/eventguard/monitor.py:158`；`src/eventguard/cli.py:76`；`src/eventguard/diagnostics/api.py:92`。

## 2. 七來源、呼叫成本與原生路徑

以下是**已驗證／靜態**的實作與上限；「候選」是**推測／待 Phase 1 驗證**，不代表已可用。七來源本輪一般權限實測結果均為 **未測**，不能填 success／partial／denied／n-a。

| 來源 | 現行呼叫與資料界線 | Python section 列數上限／預設間隔 | 不經 PowerShell／CIM 的候選；未驗證事項 | 定位 |
| --- | --- | --- | --- | --- |
| defender | Get-MpComputerStatus，七個防護／簽章 metadata 欄位；不讀威脅 Message | 20／120 秒 | winreg 設定鍵及 Security Center 狀態；各欄語意不能直接等同 MpComputerStatus，須逐項標記來源／缺口 | `src/eventguard/collectors/windows.py:72`；`config/default.json:4` |
| listeners | Get-NetTCPConnection Listen ＋ Get-NetUDPEndpoint；不做連線探測 | **合計 1000**／120 秒；腳本先各截 1000 | iphlpapi GetExtendedTcpTable／GetExtendedUdpTable OWNER_PID；IPv4／IPv6、buffer 重試與截斷契約待測 | `src/eventguard/collectors/windows.py:85`、`:24`、`:244`；`config/default.json:5` |
| processes | Win32_Process CIM，PID／Name／ExecutablePath／CreationDate；OperationTimeoutSec 8 | 2000／120 秒 | Toolhelp snapshot＋OpenProcess 限定查詢權＋image name／process times；逐 PID／欄位 denied 與 PID 重用待測 | `src/eventguard/collectors/windows.py:100`、`:259`；`config/default.json:6` |
| startup | .NET Registry 的 HKCU／HKLM × 32／64 view × Run／RunOnce，及兩個 Startup 目錄；只讀名稱，不讀啟動命令值 | 1000／600 秒 | winreg＋本機目錄 metadata；維持不存在可選鍵與拒讀不同、避免 redirect／遠端路徑 | `src/eventguard/collectors/windows.py:115`；`config/default.json:7` |
| services | Win32_Service CIM，只讀 Name／State／StartMode；OperationTimeoutSec 8 | 500／600 秒 | SCM enumerate service API；EnumServicesStatusExW 沒有直接提供 StartMode，補查所需成本／權限或將欄位列 unknown 須決定 | `src/eventguard/collectors/windows.py:149`；`config/default.json:8` |
| tasks | Get-ScheduledTask 的 name／task_path／state；不讀 Actions | 300／600 秒 | 比較 schtasks /query 與 COM；低負載／本地化／欄位契約目前沒有量測，不能先宣稱哪條較好 | `src/eventguard/collectors/windows.py:159`；`config/default.json:9` |
| versions | 固定 Python executable 的 FileVersionInfo；非產品掃描 | 10／21600 秒 | ctypes version API／既有固定檔案 metadata；固定路徑可攜性與 reparse 防護待整理 | `src/eventguard/collectors/windows.py:169`；`config/default.json:10` |

- **已驗證／靜態**：每個 collect 呼叫一次 Runner；七來源全部到期、且前面的子程序都結束時，一輪最多成功啟動 **7 個循序 PowerShell 子程序**。首次全部到期，之後依間隔；不是一次 PowerShell 同時查七來源。`src/eventguard/collectors/windows.py:229`；`src/eventguard/monitor.py:124`、`:133`。
- **已驗證／靜態**：每次 collect 的等待 timeout 寫死 15 秒；runner 合計 stdout＋stderr 保存／接受上限 4 MiB，超過後繼續排空，不代表強制停止。CIM 的 8 秒只套在 processes／services。`src/eventguard/collectors/runner.py:15`、`:32`；`src/eventguard/collectors/windows.py:104`、`:153`、`:229`。
- **已驗證／靜態**：round budget 45 秒在下一來源開始前檢查；超過者 busy、30 秒後再排。**推測**：最後一個查詢可跨過 45 秒，磁碟／建立程序／OS 不返回也不受該數字硬性約束；本輪沒有測得一輪實際耗時。`src/eventguard/monitor.py:140`；`src/eventguard/collectors/runner.py:85`。
- **已驗證／靜態**：若一個 runner 子程序卡住，後續查詢 busy，不再累積同一 runner 的子程序；其餘來源可能因此長時間失去 coverage。一般失敗仍更新 last，下一次通常等完整來源間隔。`src/eventguard/collectors/runner.py:78`；`src/eventguard/monitor.py:144`。
- **已驗證／靜態**：config 的 query_timeout_seconds／max_events_per_evaluation 有欄位，但採集與 detector 用各自常數，調 config 不會改變這兩個實際限制。尚無原生／fallback 共同契約測試。`config/default.json:12`；`src/eventguard/collectors/windows.py:229`；`src/eventguard/rules/detector.py:22`；`tests/test_collectors_diagnostics.py:33`。

### COVERAGE_PLAN H1–H5

| 假說 | 本輪結論 | 等級與證據 |
| --- | --- | --- |
| H1 啟動上下文／token 不等價 | 未證實、未排除；沒有比較兩個執行 token | 推測／待測：`docs/COVERAGE_PLAN.md:54`；`src/eventguard/collectors/runner.py:85` |
| H2 CIM／provider／namespace 限制 | 未證實、未排除；只有靜態分類分支，沒有本輪 provider 回傳 | 推測／待測：`docs/COVERAGE_PLAN.md:55`；`src/eventguard/collectors/windows.py:36` |
| H3 物件 ACL／政策 | 未證實、未排除；專案目錄 ACL 不等於來源物件 ACL | 推測／待測：`docs/COVERAGE_PLAN.md:56`；`src/eventguard/collectors/windows.py:108` |
| H4 binary／位元數／模組差異 | 未證實、未排除；已確認固定 PowerShell／Python 路徑，但沒有對照執行 | 已驗證／靜態＋推測：`docs/COVERAGE_PLAN.md:57`；`src/eventguard/collectors/runner.py:21`；`src/eventguard/collectors/windows.py:171` |
| H5 分類／封裝缺陷 | **封裝丟失原因已確認**；「原生成功被工具誤標 denied」仍未證明，不能把兩者畫等號 | 已驗證／靜態＋推測：`docs/COVERAGE_PLAN.md:58`；`src/eventguard/collectors/windows.py:234`；`src/eventguard/monitor.py:158` |

## 3. Agent 的實際資訊與 reviewed_metadata

| 入口 | agent 實際能拿到什麼／是否新增診斷 | 等級與定位 |
| --- | --- | --- |
| QueueInbox.receive_event | 固定七欄：event_id、event_type、transition、severity、synthetic、observed_at、coverage_status，加 received_at；沒有 PID／port／來源 evidence／缺口細節 | 已驗證／靜態：`src/eventguard/queue_inbox.py:83`、`:286` |
| QueueInbox.query_evidence | 同一份七欄 snapshot＋穩定 query_id；snapshot_only=true、system_query_executed=false | 已驗證／靜態：`src/eventguard/queue_inbox.py:304`、`:313` |
| QueueInbox.ack_event | 限定 decision；先寫結果，再 ACK 同 event／query；結果固定 incident_conclusion=not_assessed、wake_verified=false；重試同結果不重複結案 | 已驗證／靜態：`src/eventguard/queue_inbox.py:326`、`:356`；對應測試 `tests/test_queue_inbox.py:99`、`:113` |
| LocalWait 舊合成入口 | wait／query 回合成事件的白名單 evidence，可有 protocol／port；query 仍只讀保存 snapshot，decision 為 reviewed_synthetic | 已驗證／靜態：`src/eventguard/local_wait.py:148`、`:290`、`:303`；`src/eventguard/mcp/protocol.py:307` |
| 停用 bridge tools | get_event／query_snapshot／record_result；也是保存的合成 evidence，沒有當前系統查詢 | 已驗證／靜態：`src/eventguard/mcp/service.py:118`；`src/eventguard/mcp/protocol.py:307` |
| DiagnosticAPI／CLI query | 另有白名單型別化查詢，會重新 collect 一整個 section 再依 PID／建立時間、port 等過濾；未接到上述 agent query_evidence | 已驗證／靜態：`src/eventguard/diagnostics/api.py:58`、`:99`、`:117`；`src/eventguard/cli.py:124` |

- **已驗證／靜態**：`reviewed_metadata` 由提示明確要求；backend 只驗證 enum、同 event/query 與保存次序，不能驗證模型是否做有價值的判讀。JSONL 驗收能證明工具鏈與 ACK，不能證明診斷增益。`src/eventguard/agent_dispatch.py:36`、`:74`；`src/eventguard/queue_inbox.py:356`。
- **已驗證／靜態**：現行 agent query 新增的 Windows 觀察事實欄位為零；沒有 native query 路徑。**推測／未量測**：這種固定摘要回條可由確定性程式替代；有／無 agent 的品質、延遲與成本尚未做同事件比較，不能填造成本數字。Phase 2 需另交比較並由使用者選 A／B。`src/eventguard/queue_inbox.py:322`；`src/eventguard/agent_dispatch.py:41`。
- **已驗證／靜態**：現有白名單對任意 shell 字串、PID 重用、非法參數有測試；目前最小投影直接刪除程序名。若未來 B 要放回字串，現有測試不等於已涵蓋惡意程序名經 native query 到 agent 的完整新路徑。`tests/test_collectors_diagnostics.py:204`、`:220`；`tests/test_queue_inbox.py:59`；`tests/test_mcp_protocol.py:75`。

## 4. 容量、保存、ACK 與恢復

| 儲存層 | 上限／滿載行為 | 完成資料保留與恢復 | 等級與定位 |
| --- | --- | --- | --- |
| 核心 outbox／detector state | 可設 1–1000 events、64 KiB–8 MiB SQLite；state 4 MiB；預留 ACK 空間。滿載明確錯誤，同批事件／baseline rollback | 壓力下清 ACK；也清 updated_at 超過七天的 failed；不刪 pending/retry。可藉 ACK 後輪替恢復，非一律永久 blocked | 已驗證／靜態：`src/eventguard/events/store.py:22`、`:95`、`:159`、`:199`、`:239` |
| outbox receipt／去重 | 最多 4000 receipts；傳送重試 8 次、lease 60 秒；30 天是事件重送期限，不是永久 receipt 保證 | receipts 超額按最近紀錄截斷；事件與 receipt 都輪替後，沒有永久同 ID 去重保證；failed 手動 retry 有期限 | 已驗證／靜態：`src/eventguard/events/store.py:26`、`:169`、`:334`、`:339`、`:386` |
| QueueInbox | 每記錄 16 KiB、整個 state 8 MiB、1000 snapshots；保存失敗／滿載明確報錯，保留來源 pending | snapshot／query／result 沒有完成清理 API；1000 是累積不同事件數。ACK 不釋放 inbox 容量；8 MiB 計算也包含該目錄內 dispatcher 檔 | 已驗證／靜態：`src/eventguard/queue_inbox.py:26`、`:196`、`:286`；`tests/test_queue_inbox.py:168` |
| dispatcher 帳本 | 128 個不同 event、每 event 3 attempts；JSON metadata 256 KiB 亦可能先滿；滿載拒絕 | 沒有輪替；換新 run-dir 仍用同 state 帳本。單 pending 用完 attempts 會阻擋後續；無退出證據也拒絕新任務 | 已驗證／靜態：`src/eventguard/agent_dispatch.py:31`、`:234`、`:353`、`:395`；`src/eventguard/acceptance_control.py:12` |
| LocalWait 合成帳本 | 64 events、256 KiB，wait 歷史只留最近 128；outbox 也配置 64 | event／結果不清除；不是長期正式佇列 | 已驗證／靜態：`src/eventguard/local_wait.py:35`、`:109`、`:251` |
| bridge SQLite／vault | 預設 1000 events／20 subscriptions、8 MiB、每 event 20 queries／10 result revisions；vault 128 檔 | 沒有完成資料清理；撤銷 subscription 仍占容量；目前停用、僅 synthetic | 已驗證／靜態：`src/eventguard/mcp/store.py:25`、`:138`、`:251`、`:412`、`:428`；`src/eventguard/mcp/vault.py:149` |
| detector deferred／history | 每輪 20、deferred 最多 1000，state 4 MiB；容量例外不回傳新 state | episode history 不輪替。**推測**：足夠多不同身份／episode 可用盡 state，之後持續失敗，須可驗證的保留策略 | 已驗證／靜態＋推測：`src/eventguard/rules/detector.py:328`、`:347`；`tests/test_rules_playbooks.py:189` |

- **已驗證／靜態**：落盤使用 SQLite synchronous=FULL 或檔案 fsync；QueueInbox 以不可覆寫 snapshot／query／result 與 ID/hash 比對補收。測試含 ACK 前失敗同 query 恢復與滿載 pending 保留，但本輪未執行。`src/eventguard/events/store.py:132`；`src/eventguard/queue_inbox.py:196`、`:356`；`tests/test_agent_dispatch.py:314`；`tests/test_queue_inbox.py:113`、`:159`。
- **已驗證／靜態**：核心 failed 不是已 ACK，也可能代表最後一次嘗試結果不明；七天壓力清理因此不符合「所有 ACK 前失敗永遠可補收」的強保證。須在 Phase 4 明確選擇歸檔／保留，不可沿用泛稱不丟事件。`src/eventguard/events/store.py:164`、`:334`。
- **推測／可重現計畫，尚未執行**：帳本／inbox 完成紀錄累積到上限後，即使來源 pending 全可讀也不能自行釋放容量，可能持續 blocked；不能以重新命名 runtime、刪帳本或換來源綁定冒充恢復。`src/eventguard/queue_inbox.py:294`；`src/eventguard/agent_dispatch.py:277`、`:399`。

## 5. 子程序、停止與測試 teardown

| 層 | 啟動／等待／停止實際行為 | 等級與定位 |
| --- | --- | --- |
| runner | 固定參數、shell=false、stdin DEVNULL、hidden PowerShell；daemon reader／watcher；child.wait 無期限；timeout/cancel 只返回，active 保留 | 已驗證／靜態：`src/eventguard/collectors/runner.py:32`、`:54`、`:85`、`:97` |
| monitor | 保留 singleton 等 runner.pending 清空；等待期間持續 heartbeat，KeyboardInterrupt 不會中斷收尾 | 已驗證／靜態：`src/eventguard/monitor.py:51`；`src/eventguard/runtime.py:147` |
| watch | monitor 在本程序 thread；stop 共用 cancel、只停止後續派送；finally 一直 join monitor。1 小時限制不是程序退出的硬期限 | 已驗證／靜態：`src/eventguard/watch.py:62`、`:117`、`:165` |
| dispatcher | Python supervisor 再啟動 native CLI；到 deadline 回 pending_child_exit，讓 supervisor／CLI 繼續自然退出；下次必須有相符回條／ownership 證據 | 已驗證／靜態：`src/eventguard/agent_dispatch.py:190`、`:433`、`:492` |
| capture worker | 同時排空 stdout/stderr、各最多保存 4 MiB；CLI wait 無期限；reader 各 join 2 秒，不完整就 capture_complete=false | 已驗證／靜態：`src/eventguard/acceptance_process.py:14`、`:36`、`:59`、`:68` |
| 單次／批次驗收 | acceptance 到期可留下等待退出的 owned capture；validate_delivery 在同程序呼叫 capture，外層 producer deadline 不限制 capture.wait | 已驗證／靜態：`src/eventguard/codex_acceptance.py:169`；`scripts/validate_delivery.py:87`、`:122` |

- **已驗證／靜態**：上述路徑沒有 Windows Job Object、統一子程序登記／建立時間核對，也沒有 forcibly_terminated 記錄。stop 成功只證明請求建立，不證明已退出。`src/eventguard/runtime.py:128`、`:168`；`src/eventguard/agent_dispatch.py:508`；`src/eventguard/acceptance_process.py:39`。
- **推測**：capture 在 Popen 成功後、capture-start 落盤失敗時，except/finally 沒有完整回收或接管子程序，可能形成沒有完整退出回條的 owned child。尚未做此故障注入。`src/eventguard/acceptance_process.py:36`、`:39`、`:78`。
- **已驗證／靜態**：stdio 測試有 OWNED_CHILDREN、EOF 後等待與 teardown 斷言；dispatcher／acceptance fake CLI cleanup 也逐一 wait。但遇到永不退出者只會 timeout／fail，**不保證程序實際消失**。QueueInbox EOF 測試與 smoke 沒有等價的失敗路徑集中清理。`tests/test_local_stdio.py:76`、`:140`；`tests/test_agent_dispatch.py:106`；`tests/test_codex_acceptance.py:62`；`tests/test_queue_inbox.py:267`；`scripts/acceptance_smoke.py:68`。
- **已驗證／靜態**：部分測試用 subprocess.run(timeout=5)；本機 Python 3.13.3 標準庫 subprocess.py:557 的逾時分支會 process.kill()，並非所有測試都實作合作停止。這只涉及測試自啟 child，亦未治理 descendants。稽核只讀標準庫，未觸發該分支。`tests/test_acceptance_control.py:31`、`:57`。
- **已驗證／靜態**：smoke 的 remaining_test_processes=0 是成功路徑的常數；verify 沒有全套 child registry。verify.py 頂層 discover/run 沒有 main guard；**推測**：未來 Windows multiprocessing spawn 匯入該入口可重入測試，目前未做重現。`scripts/acceptance_smoke.py:84`；`scripts/verify.py:14`、`:27`。
- **已驗證／靜態**：heartbeat／owner 有 PID、instance UUID、started_at；沒有 OS PID 建立時間＋新鮮度的啟動比較，也沒有 monitor_gap。status 明示 last_report_only。`src/eventguard/runtime.py:168`；`src/eventguard/monitor.py:99`；`src/eventguard/cli.py:85`。

## 6. 路徑重疊、耦合與核心邊界

```text
核心：cli -> monitor -> collectors + detector -> EventStore -> DisabledAdapter
      cli -> DiagnosticAPI -> collectors（另一路手動唯讀查詢）
合成驗收：acceptance_codex / validate_delivery -> codex_acceptance / capture
          -> eventguard_local_mcp -> LocalWait -> EventStore
                                         \-> mcp.protocol（純 projection）
佇列派送：watch -> agent_dispatch -> capture -> eventguard_inbox_mcp -> QueueInbox
停用 bridge：eventguard_bridge -> mcp.app/service/store/network/security/vault
```

此圖為**已驗證／靜態** import／呼叫關係：`src/eventguard/cli.py:121`、`:124`；`src/eventguard/monitor.py:78`；`src/eventguard/watch.py:153`；`src/eventguard/agent_dispatch.py:23`、`:415`；`scripts/validate_delivery.py:19`；`scripts/eventguard_local_mcp.py:123`；`scripts/eventguard_inbox_mcp.py:58`；`src/eventguard/local_wait.py:32`；`scripts/eventguard_bridge.py:14`。

- **已驗證／靜態**：單次 acceptance 與連續／批次／recovery 共用 LocalWait／舊 command，但另有分組 proof 邏輯；新 QueueInbox 路徑另維護命令、ID/proof、ledger、receipt/recovery。兩者共享 capture／metadata lock，尚未共享同一接收與驗收契約。`src/eventguard/codex_acceptance.py:33`、`:169`；`scripts/validate_delivery.py:77`、`:135`、`:192`；`src/eventguard/agent_dispatch.py:56`、`:74`；`src/eventguard/acceptance_evidence.py:126`。
- **已驗證／靜態**：舊 acceptance 故意先啟動模型 wait，再由程式產生事件；新 dispatcher 則先讀 pending，再啟動模型。不可拿合成等待驗收當作正常 idle 模型成本。token／帳戶請求的零消耗沒有直接計量器。`src/eventguard/codex_acceptance.py:196`、`:207`；`src/eventguard/agent_dispatch.py:381`、`:433`；`src/eventguard/acceptance_evidence.py:222`。
- **已驗證／靜態**：核心 CLI／monitor／collectors／rules／EventStore／DiagnosticAPI 不 import 自有 mcp/ 或第三方 MCP SDK。**但 optional 接線仍依賴自有 mcp/**：LocalWait import mcp.protocol；acceptance_control、agent_dispatch、watch 又重用 LocalWait._guard，形成間接依賴。搬走 bridge 前必須先抽離純 projection／path guard，不能直接刪目錄。`src/eventguard/local_wait.py:32`；`src/eventguard/acceptance_control.py:10`；`src/eventguard/agent_dispatch.py:26`；`src/eventguard/watch.py:14`。
- **已驗證／靜態**：mock receiver、bridge Store、LocalWait、QueueInbox 各自有結果／去重／保存邏輯；bridge HTTP ACK、outbox ACK、agent 接收、模型判讀是不同證據，不能合稱成功。bridge default disabled/synthetic_only。`src/eventguard/transport/adapters.py:50`、`:151`；`src/eventguard/mcp/store.py:306`；`src/eventguard/mcp/service.py:180`；`config/bridge.example.json:2`。
- **已驗證／靜態**：playbook 目前只有驗證／選圖／dry-run；allowed_actions 空，simulate 不跑 tools，也不執行診斷 deadline。validator 支援的候選 operation 比 DiagnosticAPI 實作集合大，不能把圖中節點當已接通功能。`playbooks/default.json:166`、`:358`、`:551`、`:742`；`src/eventguard/rules/playbooks.py:21`、`:178`、`:266`；`src/eventguard/diagnostics/api.py:12`。
- **已驗證／靜態**：四個根目錄 .cmd 都硬編碼 C:\Python313\python.exe；不是 py -3.13／PATH＋版本檢查。當前沒有追蹤中的 CI workflow（E0），所以未具備所要求 windows-latest full suite／另列 mock job。`Run-Tests.cmd:3`；`Start-EventGuard.cmd:5`；`Status-EventGuard.cmd:3`；`Stop-EventGuard.cmd:3`。

## 7. ACL、可篡改性與 baseline 來源

- **已驗證／靜態**：Runtime／EventStore／QueueInbox 建目錄與寫檔沿用 OS ACL；沒有設定或驗證專案專屬 DACL。symlink／junction 拒絕、白名單、hash、atomic replace／fsync 是資料完整性措施，並非對有寫權的同身分程式建立信任邊界。`src/eventguard/runtime.py:15`、`:36`、`:64`；`src/eventguard/events/store.py:57`、`:100`；`src/eventguard/queue_inbox.py:196`。
- **已驗證／本機 metadata（E2）**：對 `.`, `data`, `data/live`, `config`, `config/default.json`, `data/live/eventguard.sqlite3` 執行固定 Get-Acl；六者皆存在、繼承開啟、8 個 ACE；未見 Everyone／Authenticated Users／BUILTIN Users 的寫入 Allow ACE。前五者 owner 與**目前工具執行身分**不同。沒有列出 principal／SID；**未計算有效權限，也未證明工具身分等同桌面登入身分**。程式本身未做此檢查，定位如上一項。
- **推測／界線**：不能由上述六個摘要判定所有帳號不能改 config/SQLite；具寫權者可同時改 payload 與非金鑰 hash／receipt。config／baseline 沒有簽章或 MAC；不能把本地記錄當抗同使用者惡意篡改證據。本輪未做實際篡改。`src/eventguard/events/store.py:53`、`:175`、`:271`；`src/eventguard/runtime.py:90`；`tests/test_queue_inbox.py:190`。
- **已驗證／靜態**：host identity 有 created_at；baseline_version 是 host_id＋初始時刻的 hash，但無可逆的明文建立時間。startup/services/tasks baseline 只存 keys；沒有逐來源 baseline 建立時間、collector backend／版本、權限／coverage provenance。last_evaluated_at 是最近評估，不是初始基線時刻。`src/eventguard/runtime.py:77`；`src/eventguard/rules/detector.py:61`、`:302`、`:349`。
- **已驗證／靜態**：只有完整可接受來源才能建立 persistence baseline；partial 不能宣稱完整恢復，resolved 需兩次完整觀測；baseline 與事件同 transaction。這些是應保留的既有契約，仍不等於正常 Windows 採集已被證實。`src/eventguard/rules/detector.py:202`、`:302`；`src/eventguard/events/store.py:239`；`tests/test_rules_playbooks.py:61`、`:122`。
- **已驗證／靜態**：listener identity 只含 protocol／address／port／PID，沒有 process 建立時間；processes collector 雖產生 instance_ref，detector 沒有把它綁入 listener evidence。B 案若需避免 PID 重用，必須補事件綁定契約。`src/eventguard/rules/detector.py:277`；`src/eventguard/collectors/windows.py:259`；`src/eventguard/diagnostics/api.py:73`。

E2 實際摘要輸出（逐一 Get-Acl，沒有掃描其他目錄；列名是相對專案路徑）：

重現摘要的命令如下；write mask 只包含寫入／刪除／修改權限等旗標，不將唯讀 ACE 誤算寫入。未做 AccessCheck，不能代替有效權限分析。

```powershell
$auditWriteRights = [System.Security.AccessControl.FileSystemRights]0xD0156
foreach ($auditTarget in @('.', 'data', 'data/live', 'config',
                           'config/default.json', 'data/live/eventguard.sqlite3')) {
    $auditAcl = Get-Acl -LiteralPath $auditTarget -ErrorAction Stop
    $auditRules = @($auditAcl.GetAccessRules($true,$true,
                      [System.Security.Principal.SecurityIdentifier]))
    $auditBroad = @($auditRules | Where-Object {
        $_.AccessControlType -eq 'Allow' -and
        $_.IdentityReference.Value -in @('S-1-1-0','S-1-5-11','S-1-5-32-545') -and
        ($_.FileSystemRights -band $auditWriteRights) -ne 0
    })
    [pscustomobject]@{target=$auditTarget; inheritance_enabled=(-not $auditAcl.AreAccessRulesProtected);
        broad_write_allow=($auditBroad.Count -gt 0); ace_count=$auditRules.Count;
        effective_access_not_calculated=$true} | ConvertTo-Json -Compress
}
```

```text
target                          exists  inheritance_enabled  broad_write_allow  ace_count
.                               true    true                 false              8
data                            true    true                 false              8
data/live                       true    true                 false              8
config                          true    true                 false              8
config/default.json             true    true                 false              8
data/live/eventguard.sqlite3     true    true                 false              8
effective_access_not_calculated=true
```

## 8. 測試分布、證據強度與缺口

以下全部為**已驗證／AST 靜態計數**：269 個 test_* 方法，非執行次數、非覆蓋率；skip、subTest、fixture 平台條件不展開。沒有從舊 README 的通過數推算本輪結果。

| 類別 | 方法數 | 檔案／起始定位 |
| --- | ---: | --- |
| runner／collector 解析契約 | 14（5＋9） | `tests/test_collectors_diagnostics.py:45`、`:107` |
| typed diagnostics | 9 | `tests/test_collectors_diagnostics.py:196` |
| detector 規則 | 21 | `tests/test_rules_playbooks.py:29` |
| declarative playbook 驗證／dry-run | 6 | `tests/test_rules_playbooks.py:212` |
| 核心 CLI／monitor／fixture 整合 | 16 | `tests/test_core_cli.py:24` |
| schema／outbox | 20（4＋16） | `tests/test_events_transport.py:24`、`:54` |
| synthetic mock receiver | 6 | `tests/test_events_transport.py:235` |
| 投遞／驗收／接線 harness | 76 | 下表逐檔列出 |
| 停用 bridge protocol/store/security/integration | 101（28＋23＋26＋24） | `tests/test_mcp_protocol.py:29`；`tests/test_mcp_store.py:37`；`tests/test_mcp_security.py:40`；`tests/test_mcp_integration.py:53` |
| 合計 | **269** | E1 AST 計數 |

| 投遞／驗收檔案 | 數量 | 定位 |
| --- | ---: | --- |
| acceptance_control | 7 | `tests/test_acceptance_control.py:18` |
| acceptance_evidence | 7 | `tests/test_acceptance_evidence.py:51` |
| agent_dispatch | 13 | `tests/test_agent_dispatch.py:89` |
| codex_acceptance | 10 | `tests/test_codex_acceptance.py:52` |
| delivery_validation | 4 | `tests/test_delivery_validation.py:16` |
| local_stdio | 6 | `tests/test_local_stdio.py:133` |
| local_wait | 6 | `tests/test_local_wait.py:23` |
| queue_inbox | 18 | `tests/test_queue_inbox.py:30`、`:236` |
| watch | 5 | `tests/test_watch.py:12` |

- **已驗證／靜態**：直接覆蓋 runner／collector／typed diagnostics／detector 共 **44** 個；加 playbook 為 50。投遞／驗收與 bridge 共 **177／269（65.8%）**。數量分布偏向接線，但不能由數量直接判斷品質；CoreTests 另含混合整合測試，未重複計數。定位見上兩表。
- **已驗證／靜態**：collector／diagnostics 測試用 FakeRunner、BytesIO Child、FixtureCollectors；沒有測 GetExtendedTcpTable、Toolhelp、SCM、winreg Defender 等待新增原生採集實作。SDK stdio 是真 SDK＋合成資料，fake CLI 是 Python 模擬 JSONL，均不能升格為 Windows provider／真模型驗收。`tests/test_collectors_diagnostics.py:16`、`:33`、`:184`；`tests/test_local_stdio.py:150`；`tests/test_agent_dispatch.py:43`、`:52`；`tests/test_codex_acceptance.py:20`。
- **已驗證／靜態**：已有 outbox byte/count rollback、inbox 滿載／fsync failure、同事件補收、PID 重用、coverage 不誤判恢復等有價值測試，收斂時應保留語義並證明等價後才刪重複路徑。`tests/test_events_transport.py:68`、`:109`；`tests/test_queue_inbox.py:113`、`:159`、`:168`；`tests/test_collectors_diagnostics.py:220`；`tests/test_rules_playbooks.py:70`。
- **推測／待補驗證**：目前測試不能證明所有來源一般權限可讀、任意 OS hang 有界退出、完整程序樹無殘留、完成帳本可輪替恢復、24 小時資源穩定或跨登出／重啟監看缺口偵測。對應尚缺實作定位：`src/eventguard/collectors/windows.py:222`；`src/eventguard/monitor.py:51`；`src/eventguard/acceptance_process.py:68`；`src/eventguard/agent_dispatch.py:399`；`src/eventguard/runtime.py:106`。

## 決策與下一階段界線

1. **建議／尚未實作**：先做 Phase 1 的拒絕證據端到端保留、collector 契約與七來源原生可讀性矩陣，再決定 fallback；不以刪除 denied 或提高權限讓 coverage 看似成功。依據：`src/eventguard/collectors/windows.py:234`；`src/eventguard/monitor.py:158`。
2. **建議／尚未實作**：Phase 2 比較 A／B 時，以當前 snapshot-only 通道為基準，要求新增可核查事實／判斷品質，不能只多一個 reviewed_metadata 回條。由使用者選案後才接診斷／移除迴圈。依據：`src/eventguard/queue_inbox.py:322`；`src/eventguard/agent_dispatch.py:36`。
3. **建議／尚未實作**：Phase 3 的 Job Object、程序建立時間／heartbeat gap，及 Phase 4 的完成紀錄保留，是長期不卡死的必要工作；目前只能陳述控制流程缺口，不能承諾全天候。依據：`src/eventguard/monitor.py:61`；`src/eventguard/runtime.py:168`；`src/eventguard/queue_inbox.py:294`。
4. **已驗證／靜態，文件差異**：README 180 行、STATUS 229 行，後者仍混有多輪歷史；DEVELOPMENT 仍有 license 未定／private 舊敘述。另有 optional 通道與核心狀態分開的語義，不能一律解讀成 agent 永遠未接通。這些留 Phase 6 收斂，不在 Phase 0 改寫歷史。定位：`README.md:1`；`STATUS.md:78`；`docs/DEVELOPMENT.md:86`、`:88`；`src/eventguard/cli.py:89`。

本次僅新增本報告，等待使用者確認優先序後才修改程式。Phase 1–7、模型、真實狀態注入、建立排程及長時間 soak 均未執行。

交付檢查：指定目錄 SHA-256 與 E1 一致；Python AST／JSON 解析成功；本報告明列的 file:line 均存在；`git diff --check` exit 0。本輪修改範圍僅 `AUDIT.md`，沒有單元／實機測試通過宣稱。
