# Windows collector 契約 2.0（Phase 1）

此契約只處理既有七來源的本機唯讀 metadata。核心使用 Python 3.13 標準函式庫；沒有模型、任意命令、遠端來源、處置或新登入。`AUDIT.md` 是修改前 commit 的稽核，本文件描述 Phase 1 的實作。

## 介面與選擇規則

`collectors.contract.CollectorBackend` 定義 `name` 與 `collect(section_id, cancel=None) -> dict`。`NativeBackend` 與 `PowerShellBackend` 交由 `WindowsCollectors` 做同一套白名單、限制、正規化與 coverage 封裝；測試注入 fixture 不會觸發實機 API。

```python
from eventguard.collectors.windows import WindowsCollectors

collector = WindowsCollectors()                  # auto：六來源原生；Defender有效狀態provider
section = collector.collect("listeners")          # 同步唯讀；不是啟動 agent
fallback = WindowsCollectors(backend="powershell") # 明確比較／原生 API 不可用時的 fallback
```

專案入口會傳入`WindowsCollectors(query_admission=runtime.query_launch)`，由共用Runner在spawn前保存確切私有Job計畫；取得lease／保存失敗或舊Job退出未確認，回busy、policy／`query_admission_*`且零啟動。這不是provider denied。Monitor綁定namespace／instance，CLI query及事件診斷綁定同安裝root。上面的rootless library例子不自帶全域仲裁；library整合需明確傳hook，顯式fixture注入也不能據此聲稱真Job保護。完整順序、spawn後錯誤與恢復證據見[生命週期](PROCESS_LIFECYCLE.md)。

- auto對Defender使用既有本機Get-MpComputerStatus七欄，因原生登錄／WSC不提供規則所需的有效防護布林值；該provider拒讀就保留denied，不用登錄設定代替。這是單一來源的主路徑選擇，不是通用partial重試。
- 其餘六來源先做一次native。僅當native是not_applicable、原因含api_unavailable、且沒有可用資料列時，才做一次同身分PowerShell fallback；兩次結果及各自安全process回條留在coverage.attempts。fallback被閘道拒絕不能抹去前一個native已執行的事實；舊多attempt結果缺process證據時不推定整來源零啟動。
- denied、partial、unknown、timeout、cancelled、busy、error 不自動重試或轉另一身分。原生有部分資料時，不用 fallback 的單一結果覆蓋已觀察事實。
- 注入 `runner` 的舊測試預設走 powershell fixture；可明確指定 backend，避免單元測試意外採集主機。
- 正常 monitor 使用 auto，transport 仍 disabled，不啟動模型。沒有新增命令列／MCP 診斷操作。

## 回傳與分類

公開 section 包含 `id, status, rows, observed_at, elapsed_ms, coverage`。coverage 包含 `contract_version, status, backend, scope, row_limit, truncated, errors, error_count, errors_truncated, checks, attempts`。backend payload 的 errors/checks/count 可省略，封裝器補上安全預設。

| status | 意義 |
| --- | --- |
| ok（矩陣中的 success） | 列明範圍完成且未截斷；空清單只代表這次列舉結果，不證明整機安全或所有 ACL 下均可見 |
| partial | 有資料或部分觀察，但有欄位／物件缺口、未觀察的必要資料或截斷 |
| denied | 有拒絕證據；必附 reason_code。不能直接推定需要管理員 |
| not_applicable（n-a） | 指定 API／允許的物件不存在或不適用；不是 denied |
| unknown | 已執行但證據不足以分類為完整、拒絕或不適用。例如排程根物件不可見，不能改寫成「沒有排程」 |
| error | 啟動、契約或查詢失敗；不等同 denied |
| timeout/cancelled/busy | 查詢結果分類；是否強停、退出或仍未確認，另查 coverage.process 的實際回條，不能由狀態字樣推定 |

每個錯誤的白名單欄位：

```json
{
  "stage": "object",
  "reason_code": "access_denied",
  "exception_type": "Win32Error",
  "win32_error": 5,
  "hresult": null,
  "operation": "OpenProcess",
  "status": "denied",
  "provider_code": null,
  "category": null
}
```

- stage 為 launch／provider／object／field／policy，表示已知失敗位置；不是根因推定。PowerShell 的 SecurityError 類別保留為 category／security_error_category，不據此宣稱某個 OS 政策已確認。
- 異常類型／操作／原因碼限制為最多 96 字元的 ASCII 識別字。HRESULT 是有號 32-bit 或對應數值；Win32 碼只在實際取得時填入，否則 null。本工具的路徑／容量政策不偽造 OS 錯誤碼。
- CIM NativeErrorCode／StatusCode 另作 provider_code，例如 AccessDenied；**不是 Win32 錯誤 2**。通用 HRESULT 0x80131500 本身也不能當成 AccessDenied，須看 provider_code／CategoryInfo 證據。
- errors 最多 64 筆，error_count 保留實際錯誤總數，errors_truncated 明示省略。資料列上限亦明示；超限不變成完整成功。
- 外層必須有合法 status 及 rows list；外層錯誤仍回 error。有界前綴內的非物件列個別略過，記 object／ContractError／invalid_collector_row、invalid_row_count；保留合法列，有可用觀察則 partial，否則 error。attempt 保留 source_status、收斂後 status 與錯誤計數，滿64筆也保留此契約原因；不記壞列原文，不從上限後補撿資料。auto 不以 fallback 掩蓋壞列或截斷。partial 不用來清空 baseline 或確認恢復。
- section／health／status／DiagnosticAPI 不放原始例外全文、stderr、帳號或錯誤路徑。只有明確啟用的本機驗收 evidence_sink 另存原始輸出／OS FormatMessage；正常監看不記 raw text。
- monitor 的 health 保留上述安全 coverage；健康檔讀寫上限同為 2 MiB，其他 runtime/config JSON 原有上限維持不變。CLI status 的唯讀 SQLite 連線會明確 close。

## 七來源的等價範圍與差異

| 來源／列上限 | native 路徑 | PowerShell 路徑 | 共用欄位／限制 |
| --- | --- | --- | --- |
| listeners／1000 | iphlpapi GetExtendedTcpTable TCP OWNER_PID_LISTENER、GetExtendedUdpTable UDP OWNER_PID，IPv4/IPv6 | Get-NetTCPConnection Listen、Get-NetUDPEndpoint | protocol/address/port/pid/scope/status；總上限含 TCP＋UDP；scope 不代表網際網路可達 |
| processes／2000 | Toolhelp snapshot；OpenProcess 僅 PROCESS_QUERY_LIMITED_INFORMATION；image name／process times | 限定 Win32_Process CIM 欄位 | PID/name/path/path_status/created_at/process_instance_ref/status；不讀命令列。單 PID 或欄位拒讀不抹去可列舉 PID/name |
| services／500 | SCM ENUMERATE_SERVICE；EnumServicesStatusExW；只讀服務登錄 Start DWORD | 限定 Win32_Service CIM 欄位 | name/state/start_mode/status；不呼叫 QueryServiceConfig 以免取得 binary command／account；Start 讀不到則 partial |
| startup／1000 | winreg 開鍵，RegEnumValueW 的 lpData/lpcbData 均 NULL，只取 value 名稱；SHGetKnownFolderPath＋scandir 名稱 | Registry.GetValueNames 與固定本機 Startup 目錄名稱 | source/name/registry_view/kind/status；HKCU/HKLM、32/64 view、Run/RunOnce；不讀 value 命令或捷徑內容 |
| tasks／300 | 本機 Task Scheduler COM，Connect 無 server/account/password；只取 Name/Path/State | Get-ScheduledTask 限定欄位 | name/task_path/state/status；task_path 統一為資料夾路徑，避免和完整 task path 混用；不讀 XML/Definition/Actions |
| defender／20 | 明確native模式：五項設定DWORD＋WSC antivirus彙總 | auto預設：Get-MpComputerStatus七欄 | item/value/status/authority；兩者觀察能力不相等，不互相代換 |
| versions／10 | 固定目前 Python interpreter 的版本資源 ProductVersion 字串；缺字串時才用 fixed version tuple | 同一 interpreter 檔案的 FileVersionInfo.ProductVersion | product/version/path/status；只讀既有固定檔案 metadata；不掃產品、簽章或漏洞 |

process created_at 統一為 UTC、六位微秒再產生 instance_ref；同一 PID＋相同時刻的不同時區／精度字串會得到同一 ref。DiagnosticAPI 比較實際時刻，仍拒絕 PID 重用。無建立時間者不製造 instance_ref。

PowerShell 的 interpreter 路徑以 UTF-8 base64 **資料字串**嵌入固定腳本後解碼，只用於版本 metadata；不拼成可執行命令，仍經固定本機／reparse 檢查。native DLL 僅從 System32 載入固定八種系統庫並快取，不從 cwd／PATH 載入。

### Defender 不能互相升格的部分

native 讀取的設定為 DisableAntiSpyware、DisableAntiVirus、DisableRealtimeMonitoring、DisableBehaviorMonitoring、TamperProtection DWORD。值是 configuration_only；缺鍵／值依實際錯誤標 n-a，不假定為 0。TamperProtection 數字不轉成即時啟用／停用判斷。

SecurityCenterAntivirusHealth 是 aggregate_antivirus，可能包含其他防毒產品，不等於 Defender 狀態。AMServiceEnabled、AntivirusEnabled、RealTimeProtectionEnabled、BehaviorMonitorEnabled、IsTamperProtected、AntivirusSignatureVersion、AntivirusSignatureLastUpdated 七個有效狀態在此 native 路徑均為 null／unknown／not_observed。有設定資料仍是 partial；不以設定值製造 protection.changed 的啟用／停用事實。fallback 若實際可讀才提供其觀察結果，歷史 provider 拒讀如實保留。

2026-10-23一般使用者實測既有[Get-MpComputerStatus](https://learn.microsoft.com/en-us/powershell/module/defender/get-mpcomputerstatus)七欄可讀，故auto改採這條來源特定主路徑。修改前native-only與歷史provider拒讀證據仍保留，不能改寫成當時已讀到有效狀態；修改後auto實測與fixture分見EVIDENCE。未改Defender設定、未提權，其他六來源的fallback政策不變。

### Tasks 路徑評估

Phase 1 已比較 COM 與一次固定 `schtasks /query /fo csv /nh`：COM 呼叫本身不需 schtasks 子程序，可取型別化 state；CSV 需子程序與本地化文字解析，且不加 /V 才能避免取得任務命令等其他內容。當次兩者都無法讀取排程根，COM 有 HRESULT／object 階段證據，保留為主路徑；**不是已證明 COM 在所有主機比較快**。Phase 3 起 COM 與其他 native 來源一起在 Python worker 隔離；本機比較證據仍是原 Phase 1 範圍。

COM 遞迴最多 4096 個可見資料夾、深度 32，含可見的 hidden tasks，300 列以後明示 truncated。無權限的隱藏物件是否存在仍未知；不從「未列出」推定不存在。

## 成本、取消與尚未具備的保證

所有native API handle／COM reference在finally釋放。每個native section在短期Python worker／私有Job內執行；目前auto正常七來源為六個Python worker加一個Defender PowerShell子程序。其餘來源的必要fallback最多再一次，同一Runner只有一個in-flight查詢。原有間隔不變，query_timeout_seconds範圍為(0,60]秒。

單一 OS／COM 呼叫卡住時，父 Runner 可在期限或取消後留寬限，再只清理私有 Job；coverage.process 包含實際 child exit／強停／殘留證據。詳見 [PROCESS_LIFECYCLE](PROCESS_LIFECYCLE.md)。這項行為以真 Job API 與 hanging fixture 驗證，不等於每種 provider 故障或全天候驗證。排程仍 dry-run、soak 尚未執行。

## 測試與本機證據

- `tests/test_collector_contract.py`：同一份七來源 fixture 通過 native／fallback 封裝，涵蓋 success、denied、partial、截斷、無 fallback 的失敗、必要 fallback 的歷史保留、PID 時間正規化、錯誤最小化、ABI、HRESULT 格式化與大型 coverage 經真 health/status 保存。fixture 不代表實機 provider 成功。
- `tests/test_collector_rows.py`：七來源 native／fallback 混合壞列、全壞列、錯誤上限、列前綴上限、fallback 不掩蓋、外層錯誤仍拒絕、partial 不判 listener 恢復或清 baseline。皆為合成契約，不代表主機已產生同類故障。
- 既有 collector／diagnostics、core、rules 測試保留。最新命令、discovered/pass/skip 與 source hashes 只看 [EVIDENCE](EVIDENCE.md)；`reports/phase1-collectors-001/full-summary.json` 是原Phase1的歷史數字，不累加或替代本批結果。
- 實機 source JSON、原始 stdout/stderr／OS 訊息、命令、時間、source hashes、程序退出回條位於 `reports/phase1-collectors-001`，受 Git 忽略。`monitor-final` 是一般權限下一輪真實七來源，`powershell-final` 是同上下文的一次逐來源 fallback 對照；其餘目錄保留初輪、修正與 schtasks 對照。
- `monitor-final/status.json` 是實際 CLI status 回傳；不是手寫矩陣。隔離 runtime 下的 monitor 已 stopped、runner_pending=false、singleton 可重新取得。helper exit 0 表示量測完成及正常退出，**不表示所有來源 status=ok**。

重現本機驗證命令（檔案在本機忽略目錄，重跑須換新的 label／runtime，避免覆蓋證據）：

```powershell
python -B reports/phase1-collectors-001/monitor_probe.py
python -B reports/phase1-collectors-001/probe.py --backend powershell --label powershell-final
python -B reports/phase1-collectors-001/verify.py
```

本機 source 結果：listeners/startup/services/versions success；processes partial（部分 OpenProcess 被拒）、Defender partial（設定／彙總可讀、有效防護未觀察）、tasks unknown（object HRESULT 0x80070003，排程根在此上下文不可讀）。fallback 五個 provider denied、startup/versions success。這些是本次上下文的結果，不保證其他使用者或主機等價；實際數值／原始資料不放版本控制。

## H1–H5 對照

操作流程補強後，listener 原生查詢對本次四個 OWNER_PID 表中的有限 PID 讀建立時間；只有建立時間早於表開始取得時刻才綁定 process_instance_ref。PID 重用、拒讀或缺時間皆未知；不補讀完整程序清單，也不以未來程序冒充事件當時身分。PowerShell fallback 沒有此身分則明示缺口。processes 與 listeners 共用同一 UTC 微秒身分正規化。

collector 可回報固定 launch／waiting／completed progress；舊注入 fixture 的無 progress 簽名仍可使用，但 provider 的 TypeError 不得重跑呼叫。每來源完成即保存最多 200 列／1 MiB 的安全 row_view 投影供 sources show／stdio observation 共用；完整採集列數與截斷、coverage／原因碼另列，保存投影不等於完整原始證據或即時重新採集。

| 假說 | 本次證據可支持／排除的範圍 |
| --- | --- |
| H1 token／上下文差異 | 已讀取本工具 token 的匿名 metadata：非 elevated、has_restrictions、非 AppContainer；未比較一般桌面 shell 的 token，不能宣稱兩者相同或確認所有限制的根因 |
| H2 CIM/provider/namespace | 五個實際 fallback 明確 provider_code=AccessDenied；native 多來源可讀，證明不能把 CIM 拒絕概括成所有 Windows 讀取都需管理員；namespace ACL 的根因仍未驗證 |
| H3 物件／欄位 ACL／政策 | OpenProcess 有逐物件 Win32 5 證據，其他程序可讀；未讀／改 ACL，不能定案是哪個 ACL 或政策。Tasks 0x80070003 不能改標 access denied |
| H4 路徑／模組／環境 | 七個 PowerShell 子程序皆實際啟動並正常退出，排除本輪「完全無法啟動 PowerShell」；不排除 provider／模組／環境差異。schtasks 與 COM 根目錄問題一致，仍不代表主機無排程 |
| H5 分類／封裝缺陷 | 原先理由遺失已修正並有 fixture＋實機 status 證據；版本字串／時間身分差異亦修正。沒有把原 provider 的拒絕改成成功，未證明其原本誤標 |
