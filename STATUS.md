# EventGuard 狀態與驗收缺口

## 目前：Phase 4 容量／保留已實作（2026-10-23 03:11 台北）

基底 `677fe2a6b78e7f961be45693c8e95d00a5f2a88f`，同一 feature 分支。ACKed payload／review 的 TTL 與壓力清理、有限 receipt 去重窗、inbox 完成回條合併／輪替、dispatcher 已核實 terminal 帳本壓縮及上限已接入；設定見 `config/default.json` 與 [STORAGE_RETENTION](docs/STORAGE_RETENTION.md)。pending／retry／未 ACK failed 都不清除，移除舊七天 failed 自動清除邏輯。上限存在 SQLite／inbox 專用政策，ACK opener 沿用；status 顯示 outbox 實際政策及輪替數。inbox admission 預留收尾空間；帳本開始 child 前預留終態更新大小。

唯一完整測試數來源：`reports/phase4-capacity-001/verified/verification-summary.json`。命令 `C:\Python313\python.exe -B scripts/verify.py --run-dir reports/phase4-capacity-001/verified --timeout-seconds 600`；Windows／Python **3.13.3**，2026-10-22T19:11:31.019298Z：**343 discovered、341 passed、0 failure/error、2 symlink 權限 skip、80 AST**，131.775 秒，exit **0**。`passed_checks=true`、`source_unchanged=true`、`per_test_residuals=[]`；guardian `child_exited=true`、exit **0**、`remaining_owned_processes=0`、`forcibly_terminated=false`。scope 含 fixture／SDK／fake CLI 與分開標示的真 Windows Job API，沒有模型或七來源全機採集。

新增 17 項容量測試覆蓋：count／byte 失敗回滾、ACK 後恢復、TTL 與 review 清理、未 ACK failed 保留、政策跨 opener、ACK 不改寫／衝突拒絕、inbox 同 query／result 重播及 mutation busy、completion 寫入失敗修復、來源 pending 與完成檔衝突、帳本 archive 前後寫入／中斷恢復、byte／count／TTL 輪替，以及 **64 KiB 下 100 次入列／ACK 循環仍保留指定 pending hash**。首次 targeted 測試的唯一錯誤是新 review fixture 缺少既有 API 必需的 payload_hash；補齊 fixture 後 17 項通過，未放寬來源比對。另有既有 73 項相關測試通過；不能與完整數重複相加。

保留實體證據的命令 `python -B reports/phase4-capacity-001/capacity_probe.py` exit **0**：`probe/manifest.json` 的 **5 個案例全部 passed、missing=[]**，涵蓋 outbox count／bytes、inbox count／bytes 與 dispatcher 帳本。manifest 核對原始 offered／accepted／ACK／恢復 event ID、前後 pending hashes、同 query、實際回傳與真 SQLite receipts；各 source DB／inbox 完成檔／帳本均保存在相鄰 probe 子目錄。沒有直接讀取或清理正式 data。帳本的 terminal child／交付成功欄位是明示的合成 fixture，不能升格成真 agent 或真 child exit 證據。

完整 suite 輸出、source hashes、每案例 lifecycle evidence、guardian 退出回條都在 verified 子目錄；提交後 `source-commit.json` 對照本次提交與所有受測來源位元組。執行資料／manifest／DB／完整 trace 仍在 Git 忽略目錄，未提交或推送。

**尚未驗證與限制：** [24 小時 soak 計畫](docs/SOAK_PLAN.md) 已寫，**尚未執行**；也未跑長時 provider、登出／重啟、Phase 7 注入或新真 agent。去重與已完成歷史有有限保留窗，壓力可提前輪替；不承諾永久 exactly-once。SQLite free pages 重用而不自動縮檔，journal／原子寫入暫存／檔案系統開銷及完整 reports 另計。全是未解決資料時維持明確背壓，不能藉清 pending 假裝恢復。本輪未啟動模型、長期背景程序或排程，未提權、下載安裝、改安全設定、處理其他程序或推送。Phase 5 收斂尚未開始。

## 前一階段：Phase 3 已實作並驗證（2026-10-23 02:32 台北）

本批基底 `c09f396745fe835df45b3986ae704c0213054c43`，同一 `feat/local-codex-acceptance` 分支；保留既有歷史與執行資料。新增 Windows 私有 Job Object：子程序在建立時原子加入，協作寬限後只回收本工具 Job，保存 PID＋建立時間、強停原因、退出碼與剩餘數。native 查詢改成固定 section 的 Python worker，與 PowerShell fallback 共用 Runner；monitor、capture、dispatcher／驗收 supervisor、watch、smoke 入口已接入。AGENTS 的強停限制已限縮為不得處理非本工具啟動的程序。契約及界線見 [PROCESS_LIFECYCLE](docs/PROCESS_LIFECYCLE.md)。

啟動先核對前次 checkpoint／heartbeat／PID 建立時間，建立 unknown coverage 的 `monitor_gap`。滿佇列或保存失敗時保留同 ID marker、停止新採集並顯示 `blocked_monitor_gap`；恢復後再耐久入列。查詢無法確認退出時顯示 `shutdown_unconfirmed`，不宣稱 stopped。ACK 與診斷的原有語義保留，強停樹不能通過投遞驗收。

**本輪唯一完整測試數來源：** `reports/phase3-process-005/verification-summary.json`。命令 `C:\Python313\python.exe -B scripts/verify.py --run-dir reports/phase3-process-005 --timeout-seconds 600`；Windows／Python **3.13.3**，2026-10-22T18:32:43.540422Z：**326 discovered、324 passed、0 failure/error、2 symlink 權限 skip、78 AST**，87.502 秒，exit **0**，`passed_checks=true`、`source_unchanged=true`、`per_test_residuals=[]`。guardian PID＋建立時間及實際回條在 `guardian-exit.json`：`child_exited=true`、exit **0**、`remaining_owned_processes=0`、`forcibly_terminated=false`。此數字不可與歷史測試數相加。

證據留本機忽略目錄：同目錄 `source-manifest.json`、`unit-tests.txt`、`worker-summary.json`、`lifecycle-evidence.json`、worker stdout/stderr、guardian 回條；提交後的 `source-commit.json` 核對測試 source hashes 與實際提交。實測分界：一般 token 的真 Windows Job／孫程序／巢狀 Job／owner 異常退出／外部於目標 Job 的合成 sentinel；hanging Python fixture 的 Runner、capture stdin、monitor stop 與全域期限；固定 Python executable 版本 worker smoke。`monitor_gap` 的 stale／identity／時鐘／損壞 checkpoint、滿載與同 ID 恢復是 **fixture＋SQLite**，不是登出／重開機實測。

排程命令 `python -B scripts/eventguard_schedule.py install --dry-run` 與 `uninstall --dry-run` 都 exit **0**、`executed=false`；`install --execute` 仍 exit **2**、`approval_required`、`executed=false`。輸出與三個乾淨退出回條在 `reports/phase3-schedule-001/manifest.json` 及鄰接 stdout/stderr。沒有執行 schtasks 或建立／刪除排程。

保留失敗證據：`phase3-process-001/002` 是 guardian baseline 尚未辨識 discovery 建立的 conhost 而失敗，改為比對固定 Job 成員 PID＋建立時間；`003` 找出新增事件類型上限、未受管 fake stop 相容性與舊 pending timeout 預期；`004` 只剩新增測試使用低於既有最小值的 duration。修正後才跑 `005`，沒有覆寫前次證據。`003/004` 的逐項殘留都為空、最終 guardian 剩餘 **0**；超短期限實際 runner 的失敗交付與自然退出診斷見 `reports/phase3-timeout-diagnostic-001/`，未冒充真模型驗收。

**尚未驗證／與 AUDIT 差異：** 原先無法停止卡住 OS 查詢的限制已改由 worker Job 隔離並以 hanging fixture 驗證；native 一輪改為七個短期 Python worker，增加的性能成本未量測。沒有重跑七來源 provider 採集、真模型、登出／重開機、Phase 7 狀態注入或長時 soak；兩個 symlink 測試仍略過。沒有啟用長期監看、自啟、服務或排程；沒有提權、網路、下載安裝、修改安全政策、強停非本工具程序或推送。下一階段為 Phase 4 容量／保留；本次交付停在 Phase 3。

以下保留歷史紀錄，其舊限制與舊測試數不代表目前實作。

更新：2026-10-22 UTC。本檔只記錄工程事實，不包含真實主機的警報、路徑或安全結論，也不授予操作權限。

**本機耐久佇列已接通專用 Codex CLI agent；完整產品仍為工程預覽。** 有限合成 A／B1／B2／C，以及新增前景入口的合成與有界實機佇列接收試跑均已有真工具證據；本輪已退出，目前沒有持續監看。完整 coverage、長期可靠性及原生診斷仍未驗收。最新證據見本檔末節與 [LIVE_CHANNEL](docs/LIVE_CHANNEL.md)；以下保留各時間點歷史，不以 mock 或舊測試冒充新結果。

## 歷史協定基準：本機 stdio MCP 等待（04:16 UTC）

雲端部署／host／HTTPS 路線已停止推進，既有程式保留停用。新增 local_wait.py、scripts/eventguard_local_mcp.py 與專用測試：只等待合成事件、查已保存 snapshot、同事件結果先落盤再 ACK。沒有註冊 MCP、寫設定、啟動模型、開網路埠或啟用正式監看。

官方 Codex 預設工具逾時 60 秒，可調整；永久等待、逾時後不恢復推理均無已驗證保證。真實 Codex 一次 wait→query→ACK 的實驗需另有精確批准；[實驗範圍與命令](docs/LOCAL_MCP_EXPERIMENT.md)。本地協定測試結果與真模型驗證必須分開。

2026-10-22T04:16:27Z：`python -B scripts/verify.py` 通過 202 tests（0 failure/error/skip）、44 Python AST，26.808 秒。新增 6 個後端測試與 4 個真正 stdio／SDK 測試：事件返回、查證／ACK、逾時、取消不回覆已取消 request、EOF 自然退出、缺 SDK 失敗方式與外部合成 producer。測試自己啟動的子程序均已自然退出；未使用 kill／terminate。

04:16:35Z 的獨立合成 stdio trace 確認協定協商 `2024-11-05`、等待 0.569 秒後返回、同 event/query 的結果與 ACK、child exit 0；原始證據只在忽略的 reports。本次 client 是已安裝 Python MCP SDK 1.6.0，模型呼叫 0，原生採集 0。不是 Codex 模型接續、長時性能或永久等待的驗證。

## 新接線程式增量（未部署）

- 已加入 `src/eventguard/mcp/` 與 `scripts/eventguard_bridge.py`：authenticated MCP 方法、訂閱保存、驗證 callback、簽章 HTTPS、producer 入口／adapter、限額內合成證據查詢與結果修訂。沒有 OAuth 授權伺服器；固定 Bearer 是 API-key 模式，需平台／自訂 plugin 實際支援與另行批准的 credential。
- 2026-10-22T03:50:53Z：完整 suite **192 tests、0 failure/error/skip，40 AST 通過**，16.508 秒；全部合成／mock，DPAPI 僅公開測試 fixture。舊 91 tests 是基準，不能與新數字重複相加。
- bridge `check` 確認範例停用、不開 listener、不讀 credential；停用設定的 `serve` 拒絕啟動。所有測試沒有開埠、真 DNS／HTTPS、模型或原生安全採集。
- 已覆核並修正 producer Authorization 與 callback 標頭隔離、目前 subscriber／host 授權縮限、非法 JSON-RPC ID、同 key refresh 不重複保存 vault 及短 TTL 輪替。
- 部署與平台互通仍 **pending**。普通本機 Codex task 的外部喚醒沒有被此程式實作或驗證；候選目標為受支援的 Work Cloud／dot 訂閱聊天。

明確容量界線：bridge 1000 個事件、20 個訂閱（含 revoked）、每事件20筆查證／10次不可變結果修訂；DB 主檔8MiB，DELETE journal 可能有額外暫存空間；不自動丟棄 pending，也尚無自動保留清理。DPAPI vault 最多128個加密檔，正常同key刷新重用ref，key更換／重訂閱仍需容量管理。DNS查詢有10秒呼叫端上限，但OS resolver不能kill；每poster僅1未完、全process最多4個daemon resolver，自然退出前可能仍pending。這些限制須在部署前納入維護與長時驗收。

詳細範例與接線條件見 [MCP_BRIDGE_DEPLOYMENT](docs/MCP_BRIDGE_DEPLOYMENT.md)。新原型不解決原生 coverage 缺口，也不滿足「真正 agent 喚醒→診斷→同事件結果」的產品完成定義。

## 已完成及證據

| 項目 | 已驗證範圍 | 不能據此聲稱 |
| --- | --- | --- |
| 無 GUI headless 核心 | 前景執行、分層頻率、單例、合作停止、狀態與本機心跳 | 已安裝長駐、服務、自啟或獨立 watchdog |
| 七類採集與診斷介面 | Defender 設定、監聽端點、程序 metadata、啟動項名稱、服務、排程 metadata、固定 Python runtime 版本 | 所有 Windows 主機均已實測、完整資產盤點、連線流量／事件全文／簽章／威脅歷史已涵蓋 |
| 確定性規則 | baseline/diff、去重、cooldown、升級、兩次完整成功觀察才恢復、coverage 降級 | 沒有事件代表安全、歷史 inactive 代表已清除 |
| 耐久儲存 | detector state 與 outbox 同交易、容量背壓、重試、租約、ACK 與重啟去重 | exactly-once、無限重試、磁碟永不滿 |
| 宣告式 playbook | 四條規則、結構驗證與 dry-run；不執行工具或處置 | 寫入規則就取得權限、agent 已依此完成調查 |
| 輸出 | 本機 JSON 與 escaping／CSP 的 HTML | 已上傳、已被 agent 閱讀 |
| 測試 | Windows／Python 3.13.3：2026-10-22 02:55:12 UTC，91 tests、0 failure/error/skip，26 Python AST 通過 | Linux／雲端全套已過、原生採集全數成功 |
| 合成 smoke | 02:55:15 UTC，正常兩輪零事件、outbox→mock ACK→合成診斷→mock_closed、重複抑制、跨程序單例／停止；殘留測試子程序 0 | 真正 Codex／dot 被喚醒、真實系統處置已完成 |

上述測試對應本機保留的驗收快照 `fd45578`。發布用原始碼／測試／設定／playbook 應逐檔核對與該快照相同；文件可另行演進。測試原始輸出只保存在本機忽略目錄，未作為公開範例或上傳主機報告。重現方式見 [DEVELOPMENT](docs/DEVELOPMENT.md)。

## 獨立原生驗收摘要

後續獨立驗收確認固定快照、91 tests 與 26 AST 一致；工具可啟動、接受合作停止並退出。但部分原生來源回傳 denied，整體結論仍為 **BLOCKED**，且沒有真正 agent 喚醒。這不是安全或入侵結論。單次程序 RAM 峰值不包含所有子程序，不能當作長時資源驗收。原始實機報告、警報與執行資料不納入 Git；公開協作只保留此工程摘要。下一步依 [COVERAGE_PLAN](docs/COVERAGE_PLAN.md) 分來源核實執行身份／API 可用性，不提高整個程序權限、不繞過拒絕。

## 已知限制與風險

- `query_persistence_diff` 目前回傳 `current_only`，不實作診斷基線比對；名稱不能取代回應中的 coverage。
- 版本查詢僅固定 Python runtime；無一般產品更新判斷。未提供 Authenticode、威脅歷史、原始事件內容或網路探測。
- 監聽範圍區分 localhost／LAN／all interfaces，不能由此推定 Internet 可達。
- 每輪採集預算 45 秒，預算跳過來源以 30 秒短退避重試。單查詢期限 15 秒／輸出上限 4 MiB；已開始的 OS 查詢不 kill，pending 時保留單例鎖，自然退出前 stop 可能等待無限久。
- 每次 evaluation 最多交付 20 事件，延後事件保留原 ID；這不是獨立每分鐘速率限制。pending 不被容量輪替偷偷丟棄；滿載時明示降級並保留舊基線。
- 最多 8 次傳輸嘗試、有限去重保留窗及 ACK 儲存預算；超窗或不確定投遞須核對收據，不可猜測成功。DisabledAdapter 不增加 attempts。
- 程序／主機全停無法自我告警。`status` 是最後報告，不能證明目前程序存活或主機安全。
- 停止或重啟後不會自行恢復；服務、排程、開機自啟及獨立 watchdog 均未安裝。

## 資源預算：目標與實測分開

| 指標 | 驗收目標或實際機制 | 實測狀態 |
| --- | --- | --- |
| 一般採集 | Defender／監聽／程序 120 秒，啟動／服務／任務 600 秒，版本 21600 秒 | 設定與排程邏輯已測；未做長時主機負載量測 |
| 並行／優先序 | 單原生查詢，監看程序嘗試 below-normal；增量規則，不做 AI heartbeat | 邏輯已測；整體 CPU／I/O 效果未量測 |
| CPU／RAM／I/O／電池 | 完整目標在 TARGET_DESIGN，需 idle 與高負載基準、電池／插電情境及分位數 | **未量測，不聲稱達標** |
| 儲存 | outbox 1000 事件／8 MiB 等預設，日誌輪替與背壓 | 容量／失敗案例已測；長時／磁碟故障實機驗收未做 |
| 真 ingress | 無事等待不推理，只有事件開啟必要回合 | 有界 CLI 接收已通過，見末節；長期運作未驗收 |

## 下一步與完成定義

1. 依 [INGRESS_PLAN](docs/INGRESS_PLAN.md) 選定受官方支援的接收端與任務語義，確認憑證、有效授權、持續權限與成本；不能把建立 GitHub 儲存庫或雲端開發環境視為接線完成。
2. 實作可信 adapter 與 receiver；僅在明確批准的最少合成資料範圍先測。ACK、agent run／turn、診斷與結案各自保存可核對證據。
3. 同一合成事件經真正 receiver 喚醒真 agent，agent 按白名單完成按需診斷並回存結果；離線／重啟／重複事件仍冪等，正常心跳不開模型回合。全部通過才可稱真 E2E 完成。
4. 完成目標 Windows 主機之低負載原生 smoke、長時資源／休眠／崩潰恢復與失敗注入驗收；測試後明確停止自己程序。

每次更新保留 UTC、revision、命令／輸入類型、實際結果及未驗證範圍；禁止把設計值、舊測試數或 mock 狀態改寫成實測成功。新增真實主機證據只留經批准的本機忽略目錄，不寫入此文件或 Git 歷史。

## 2026-10-22：雲端接續與可執行 MSI 驗收入口

來源 `359a771539fe652b18a2a5469689c3d986b49611`；開始時 work 分支乾淨，fetch 確認 origin/main 相同，未倒退或覆寫既有提交。新增工作分支 `feat/local-codex-acceptance`。

實作：`scripts/acceptance_codex.py` 與 `src/eventguard/codex_acceptance.py` 協調一次官方 Codex exec，等真正 server wait 紀錄後由程式注入唯一 synthetic 事件，核對三個實際 MCP tool items、同 event/query 結果、SQLite ACK 及 child exit。run/status/stop 使用專用新目錄；不重試模型、不永久註冊、不改安全設定，合作停止不 kill。server single-wait 拒絕第二次等待。另修正 SDK 1.29 SessionMessage 包裝與取消 request ID 正規化；舊 SDK 路徑保留，本輪未重新取得 SDK 1.6。

測試命令與證據（皆為本輪，不沿抄交接 202/44）：

- Python 3.13.5，`python3.13 -B scripts/verify.py`，2026-10-22T05:13:15Z：210 tests，200 passed，0 failure/error，10 skipped（5 無可選 SDK、5 Windows-only），47 AST 通過，exit 0。忽略證據 `reports/cloud-python313-final.json`。
- Python 3.12.14 / 已安裝 MCP 1.29.0，`python -B scripts/verify.py`：210 tests，205 passed，0 failure/error，5 Windows-only skipped，47 AST 通過，exit 0；最終時間見本輪 `reports/verification-summary.json`。其中 5 項真正 stdio/SDK 測試包含 wait/query/ACK、取消無回覆、EOF 自然退出、單次等待逾時後拒絕再等。7 項 runner 測試含明示 fake CLI 的協調、ACK、停止及 pending-child-exit；fake CLI 絕非真模型證據。
- `python3.13 -B scripts/acceptance_smoke.py`，2026-10-22T05:08:27Z：passed=true，正常零事件、disabled 零 attempt、mock ACK、mock_closed、去重、跨程序單例與合作停止；remaining_test_processes=0。`reports/acceptance-smoke.json`；不是正式 agent／原生採集。
- `python3.13 -B scripts/eventguard_bridge.py --config config/bridge.example.json check`：有效但 enabled/network_enabled/listener_started/credentials_read 均 false。bridge 保持停用。
- `git -c core.whitespace=cr-at-eol diff --check` 通過；reports、runtime、帳戶內容不納入提交，舊 MVP 不動。

實際 Codex 嘗試：CLI 0.163.0 的 `login status` 顯示已登入，兩次單次驗收皆 CLI exit 1，錯誤 `failed to initialize in-process app-server client: Read-only file system (os error 30)`。第二次已按官方 schema 單次指定可寫 sqlite_home/log_dir，錯誤相同；沒有進入 wait、沒有 event ID、工具呼叫或 ACK。證據僅本機忽略的 `reports/codex-cloud-001`、`reports/codex-cloud-002`，沒有從原始 sessions 取證或複製憑證。真實模型接續、帳戶閒置請求數、真正 Codex timeout/cancel 行為仍 BLOCKED，不能用上述測試替代。

官方核對：Codex 0.163.0 tag 的 DEFAULT_TOOL_TIMEOUT 為 300 秒；新入口明確設 tool_timeout_sec=60、wait=30。完整來源、MSI 最短命令、退出碼與排障見 `docs/CODEX_ACCEPTANCE.md`。MSI Python3.13／SDK／登入／Windows 原生來源與長期低負載尚未驗收，沒有宣稱桌面任務可接續或永久等待。

交付：已將 `28170cb` 推送到 `origin/feat/local-codex-acceptance`，遠端 SHA 已核對。`gh pr create --base main --head feat/local-codex-acceptance` 被 GitHub GraphQL API 拒絕（Forbidden），所以 PR 尚未建立；不是 Git push 或測試失敗。可從 GitHub 的該分支建立 PR，不能把 compare/new-PR 連結稱為已存在的 PR。

## 2026-10-22：同事件重試、退出回條與本機整批驗證

本批接續 `b36cdba`，未重跑遠端 CI、未呼叫模型、未重新嘗試已知受阻的 Codex／GitHub API。完成一批後只建立一個本機提交；本輪不推送，保留遠端 CI 額度。

- 新增手動 `retry`：最多三次 attempt（含前置條件失敗），沿用同一 runtime、event/query/result ID。結果先落盤但 ACK 失敗可重試；已 ACK 事件拒絕再次啟動模型。原始 trace 與 attempt-summary 保留，僅核對當輪新增 wait。
- 新增獨立 capture worker 與有 fsync 的退出回條。runner 逾時或自然退出後 worker 繼續等待自己的 CLI 自然退出；無完整回條時拒絕重試，不靠 PID 猜測。stdout/stderr 各 4 MiB 上限，超量繼續排空但驗收失敗。
- runner、capture、stdio 加跨程序檔案鎖；第二個 stdio process 拒絕同 runtime。停止作用於當輪，舊 stop 不影響 retry。status 可用退出回條補完先前 pending 判定，不呼叫模型。
- metadata 逐檔拒絕 symlink/junction，拒絕 `..` 別名；有界讀取及原子 fsync 寫入。Windows shell 包裝預先拒絕，可指定既有原生 Codex 執行檔，不安裝依賴或更動執行政策。
- 驗收現在核對真實 MCP 回傳內容、wait 起迄、同事件/query、結果/ACK、完整 CLI turn；文字成功或損壞證據不能通過。

本輪實測（本機、合成／fixture，非真 agent／MSI）：

| 命令／runtime | UTC | 結果 | 忽略的證據 |
| --- | --- | --- | --- |
| `python -B scripts/verify.py`，3.12.14 / MCP 1.29.0 | 2026-10-22T05:50:12+00:00 | 227 discovered，222 passed，5 Windows-only skipped，0 failure/error，53 AST 通過 | reports/cloud-sdk-retry-final.json |
| `python3.13 -B scripts/verify.py`，3.13.5 | 2026-10-22T05:51:15+00:00 | 227 discovered，216 passed，11 skipped（6 SDK + 5 Windows-only），0 failure/error，53 AST 通過 | reports/cloud-python313-retry-final.json |

新增／擴充測試涵蓋同事件重試、result-before-ACK 失敗恢復、已 ACK 零重啟、舊 stop 不污染新 attempt、實際 runner 程序退出後回條仍保存、跨程序鎖、拒絕第二個 stdio、損壞 metadata／回傳／trace、輸出上限及路徑重導向。程序 fixture 均自然退出，不使用 kill/terminate。`git -c core.whitespace=cr-at-eol diff --check` 通過。先前真 Codex app-server 唯讀阻塞、真 timeout/cancel、帳戶閒置用量與 MSI 原生／長期監看仍未驗證；本批不提升產品完成度。操作與證據配置見 `docs/CODEX_ACCEPTANCE.md`。

## 2026-10-22T06:15:00+00:00：只驗證真事件通路，網路端點仍受阻

本輪來源 HEAD `e7b50b356a8021165a7f76d14e288927bbeb3bf0`；開始時工作區乾淨。沒有修改產品功能、執行 CI、推送或提交。

先以 file-syscall trace 確認舊錯誤：Codex 0.163.0 對唯讀 CODEX_HOME/installation_id 的 read-write/create open 回 EROFS；sqlite/log 覆寫不能修正。已用專用可寫 runtime 並以符號連結引用既有登入（未讀取或複製憑證內容），`login status` 可辨識帳戶，實際 CLI 成功建立 installation_id、越過先前初始化失敗，但尚無事件接收工具呼叫。

獨立無憑證 HTTPS 連線診斷：chatgpt.com 與 api.openai.com 的 CONNECT 都被既有網路代理以 403 拒絕（curl exit 56 / HTTP 000）。目前只開放 package_managers preset，沒有模型端點。已保存只新增 chatgpt.com 的網路設定草稿，保留原 preset；工具回報 saved、requires_publish=true。草稿不代表目前 runtime 已放行，需在環境設定檢閱、儲存並發布，再重測。沒有要求新憑證或繞過網路政策。

本次真 CLI 嘗試 `reports/channel-probe/run-002` 的 runner 已達 180 秒觀測上限，記為 pending_child_exit；capture worker PID 5895 與 Codex PID 5896 最後檢查仍存在，沒有退出回條，沒有送 process signal，不宣稱已停止。端點通路未建立前不再開新模型任務。不得把這次啟動或已登入當成 agent 已收到事件。

已準備忽略目錄 `reports/channel-probe/validate_delivery.py` 的有限驗收：continuous 2 件、batch 3 件、recovery 在真正 agent wait/query 後先正常退出、確認 pending 再由第二個真任務以同 event/query ACK。預設 prepare-only，真任務必須明確 --execute；比對實際工具回傳與生成／收到／ACK Counter。三種 prepare 命令已執行，均輸出 prepared_only_no_model_invoked；沒有執行 B/C 真模型驗收，也沒有宣稱無缺漏。網路開通後先處理現存 attempt 的退出狀態，再完成 A，才執行 B/C。

證據僅保存於忽略目錄：channel-status.json、file-access.trace、run-001、run-002 及各案例 manifest。A 單事件目前 BLOCKED；B 連續／批次與 C 失敗補收 NOT RUN。MSI、本機長期監看與帳戶閒置用量均不因本輪診斷而提升為通過。

## 2026-10-22T06:23:23+00:00：MSI 從 GitHub 取得有限通路驗收

依使用者最新指示，取消下載包，將驗收入口與操作文件集中推送到 `feat/local-codex-acceptance`。本輪只補通路驗收，不新增監看來源、GUI、原生診斷或雲端服務；不手動觸發 CI，提交使用 [skip ci]。GitHub 的 main 尚不是這批來源，MSI 應取得指定分支。

新增 `scripts/validate_delivery.py`：continuous=2 件（前一 ACK 後才入列下一件）、batch=3 件原子入列、recovery=第一個真任務只 wait/query 正常退出，確認 pending 後第二個真任務補收同 event/query 並 ACK。預設 prepare-only，需明確 --execute 才用既有帳戶執行模型；提示不帶事件 ID／內容，不自動重試模型，保存實際工具回傳與 ID Counter 核對。支援 --codex-executable 指定 MSI 既有原生 CLI。操作見 `docs/MSI_CHANNEL_CHECK.md`，先 A 真通過才跑 B/C；使用 MSI 正常登入，禁止帶入雲端 CODEX_HOME／auth／runtime。

本機驗證：`python -B scripts/verify.py`，231 discovered，226 passed，5 Windows-only skipped，0 failure/error，55 AST 通過，exit 0。另以 Python3.13 跑新增4項入口測試，全部通過。這是程式／fixture 檢查，不是 MSI 或真正模型送達證據。reports、憑證、runtime、ZIP 與真 CLI log 都不納入 Git。

雲端重測 ChatGPT CONNECT 仍403；無可用工具可讀取發布失敗詳情，不能推定其原因。已保存的 chatgpt.com 網路草稿不等於目前 runtime 放行。既有 run-002 最後狀態仍 pending_child_exit，未取得退出回條，沒有強制終止或另開重複模型任務。A/B/C 真通路未驗證，等待 MSI 實跑結果，不提升產品完成度。

## 2026-10-22 06:58 UTC／14:58 台北：MSI 有限真通路 A／B1／B2／C 通過

本輪來源核對：工作目錄為本專案，初始 `publication`／`359a771539fe652b18a2a5469689c3d986b49611`，無未提交變更。正常 fetch 後取得並切換 `feat/local-codex-acceptance`，HEAD 與使用者指定 `4ffc86c1b931a8706d26723c676e974dba4fbc1d` 完全相同，沒有更新須保留合併；未 reset、clean、強制覆寫或動舊 MVP。保留原本地分支與私人歷史。

前置檢查：Python 3.13.3 可匯入既有 MCP SDK 1.6.0；PATH 的 codex 為 npm 包裝，另找到既有 npm 原生 0.158.0 與桌面安裝原生 0.163.0-alpha.11.1。本輪選後者為 `$codexExe`。明確以程序環境 `$env:CODEX_HOME = Join-Path $env:USERPROFILE '.codex'` 指向正常本機 home 後，`& $codexExe login status` 回 Logged in using ChatGPT。沒有建立登入、讀取／複製憑證內容、帶入雲端 home 或安裝任何依賴。

先前 sandbox 對 `.git/FETCH_HEAD` 的寫入遭拒，自動核准審查亦依 AGENTS 的不得提權規則拒絕 Git sandbox 例外；使用者之後明確批准限定 Git 例外，再批准本輪有限驗收程式的 sandbox 例外。均使用同一一般使用者，無 UAC／管理員權限或安全設定變更；內層 Codex 保持 read-only、shell 關閉。這些批准僅屬本輪，不是持續存取授權。

A 三次 attempt 全部保留於同一 run，沒有另建目錄繞過 retry 上限：

| attempt／UTC | 結果 | 事件與工具證據 | 自然退出 |
| --- | --- | --- | --- |
| 1，06:39:54–06:40:39 | 初始化 `in-process app-server` Access denied／os5，runner exit 1 | 未進 wait、未生成事件、無 query／ACK | CLI exit 1、child_exited=true、完整回條 |
| 2，06:45:32–06:46:36 | 真 agent 嘗試 wait，被 `MCP tool call requires approval, but approval policy is never` 拒絕；runner exit 1 | 真 CLI turn 已完成，但沒有實際工具返回／事件／ACK，summary 正確拒絕成功 | CLI exit 0、child_exited=true、完整回條 |
| 3，06:49:27–06:50:26 | 修正逐工具單次批准後真正 passed，runner exit 0 | 一次 wait→程式產生事件→query→ACK；實際 wait 3.190 秒、相同 event/query/result 與 SQLite receipt | CLI exit 0、child_exited=true、完整回條 |

第一個錯誤與 Codex 需要可寫開啟正常 home 的 `installation_id` 相符；只覆寫 sqlite_home/log_dir 不能解決。CLI 自身啟動亦產生歷史索引 metadata 警告，操作者未開啟既有 session 檔；包含私人路徑的本次 stderr／Codex state 僅留忽略 reports，不能上傳。未以修改權限、複製憑證或新登入繞過。

必要實作修正：`command()` 以同一工具清單產生 `enabled_tools` 與逐工具 `approval_mode="approve"`，僅對本次已授權公開合成工具有效；不改總批准政策或永久設定，不加 bypass。以 `single_wait`／`allow_ack` 參數取代 B/C 的字串替換，C 第一階段的設定完全沒有 ACK 白名單或批准表。測試直接解析 TOML 確認批准範圍及 read-only／shell 關閉均保留。官方語義見 [MCP 文件](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) 及[本機版本實作](https://github.com/openai/codex/blob/680c4ba93ec79c292287fb9e0b627dc7a76e3b5e/codex-rs/core/src/mcp_tool_call.rs#L2467-L2479)。

依序執行的真驗收命令（A 後續兩次使用同參數的 `retry`，沒有自動模型重試）：

```powershell
python -B scripts/acceptance_codex.py run --run-dir reports/msi-single-001 --codex-executable $codexExe
python -B scripts/acceptance_codex.py retry --run-dir reports/msi-single-001 --codex-executable $codexExe
python -B scripts/validate_delivery.py continuous --root reports/msi-continuous-001 --codex-executable $codexExe --execute
python -B scripts/validate_delivery.py batch --root reports/msi-batch-001 --codex-executable $codexExe --execute
python -B scripts/validate_delivery.py recovery --root reports/msi-recovery-001 --codex-executable $codexExe --execute
```

| 案例／驗證完成 UTC | 生成唯一事件 | 真接收／query／ACK | 結果與證據根目錄 |
| --- | --- | --- | --- |
| A，06:50:26 | 1 | 1／1／1 | summary.passed=true；reports/msi-single-001，成功 trace 在 attempts/0003 |
| B1，06:52:16 | 2 | 2／2／2 | validation.passed=true、missing=[]；reports/msi-continuous-001 |
| B2，06:54:35 | 3 | 3／3／3 | validation.passed=true、missing=[]；reports/msi-batch-001 |
| C，06:57:02 | 1 | 2／2／1 | validation.passed=true、missing=[]、recovered_same_event_and_query=true；reports/msi-recovery-001 |

C 第一階段只執行 wait/query，CLI 正常退出；`read-before-ack/pending-proof.json` 於 06:56:05.435Z 記錄 pending、result_present=false，才啟動第二階段。第二次工具回傳相同 event ID／query ID，結果於 06:56:56.885Z 保存再 ACK；SQLite 僅一筆結案 receipt。

集合核對：合計 7 個不同程式生成事件、8 次實際接收／query（C 預期重收一次）、7 次 ACK、7 筆 SQLite ACK／receipt；missing、unexpected、unexpected_duplicates 均為空。逐事件 ID、query ID、接收時間、結果時間、source SHA-256、真 trace 路徑與退出回條核對在 `reports/msi-channel-001/delivery-audit.json`；`python -B reports/msi-channel-001/audit_delivery.py` 於 06:58:05Z exit 0。另有唯讀獨立審查直接解析真 JSONL 與 SQLite mode=ro，未只採信 summary。五個成功真 Codex 任務均 exit 0、完整且未截斷回條，四個 runtime 的 stdio-owner.lock 均已釋放。另保留上述兩個失敗 attempt，所以本輪共七次驗收用 `codex exec` 啟動；未 kill／terminate、未留本輪未知退出狀態。

必要本機測試與限制：

- `python -B -m unittest discover -s tests -p test_local_stdio.py -v`：6 tests 全通過，13.085 秒；僅 SDK／合成協定，不作真 agent 證明。
- `test_delivery_validation.py`：4 tests 全通過，0.417 秒；`test_codex_acceptance.py`：10 discovered、9 passed、1 symlink 權限 skip，13.279 秒。皆以 `python -B -m unittest discover -s tests -p <檔名> -v` 執行，fake CLI 測試明示非真模型。
- 全套以 `python -B -` stdin harness 執行 `unittest.defaultTestLoader.discover('tests')` 與 `ast.parse`，獨立輸出目錄避免覆寫既有 reports 基準。06:53:15Z：231 discovered、229 passed、0 failure/error、2 symlink 權限 skip，55 Python AST 通過，53.809 秒，exit 0。證據 `reports/msi-channel-001/unit-tests.txt`、`unit-summary.json`。未為略過項提權；無模型、網路服務或實機掃描。

以上只完成本階段的有限公開合成事件工具接收、耐久保存及補收 ACK 驗收，不是任意既有桌面對話接續、Windows 原生採集、長期 dispatcher／監看服務、永久等待、帳戶零閒置用量或完整主機安全的驗證。正常監看仍不呼叫模型；既有 bridge 保持停用。所有 manifest、JSONL、工具回傳、SQLite、runtime 與本輪診斷保留本機忽略 reports，不納入 Git。

## 2026-10-22 08:13 UTC／16:13 台北：前景事件入口與有界實機接收通過

本批接續 `f093c2df531c7bbfc732e134cf718f00ebbfd22f`，仍在 `feat/local-codex-acceptance`。初始無未提交變更；集中提交前 fetch 再核對遠端與 HEAD 相同，沒有 reset、clean 或覆寫。使用者要求把事件接上，另明確批准一輪前景試運轉：最多一小時／五個 agent 任務，只送最小摘要。實際採更小的 300 秒／最多兩個實機任務；加上一次公開合成通路，共三個真 CLI 任務，沒有自動重試模型。先前 A／B／C 的結果保留，未重跑或重複計數。

實作可直接使用的 `scripts/eventguard_watch.py`（run/status/stop），整合既有 Monitor 與 `agent_dispatch.py`，不擴充來源、GUI 或原生診斷。Monitor 新增時限與共享合作停止；首輪保存後才交給 dispatcher。純 Python 等待原 live outbox，有 due/pending 事件才啟動專用 CLI；未執行時只是 preflight。停止／截止在實際 native Popen 前再次核對，根本未啟動者另記 capture-skipped；已開始 CLI／查詢自然退出，沒有 kill／terminate。

`queue_inbox.py` 只投影固定七欄 snapshot：event ID／類型／轉態／severity／synthetic／觀測時間／coverage status，不回程序或產品名稱、路徑、PID、事件全文、任意 evidence／reason／gaps。三工具 receive/query/ACK 只綁定一件事件，prompt 不帶 ID／內容；query 僅查同一保存摘要，結果為 `reviewed_metadata`、`incident_conclusion=not_assessed`。MCP 設定與逐工具批准只屬單次 CLI，保留 read-only／shell 關閉，使用正常本機 home 與既有登入，未永久註冊、建立登入、讀取或複製憑證。

耐久 snapshot/query/result ID 與原 outbox ACK 互相核對，結果先保存再 ACK；同 ID 重收沿用同 query/result，已 ACK 不重複結案。來源全域鎖與固定 state 綁定阻止平行 receiver 或換目錄繞過未知退出；每事件最多三次明確嘗試、失敗不自動重開模型。容量／保存失敗明確 blocked，不清除 pending。詳見 [LIVE_CHANNEL](docs/LIVE_CHANNEL.md) 的容量、啟動與恢復限制。

本輪使用既有 Python 3.13.3／MCP 1.6.0／原生 Codex 0.163.0-alpha.11.1，程序環境明確指向正常 home，`$codexExe` 為既有原生執行檔。真執行命令：

```powershell
python -B scripts/eventguard_agent.py run --run-dir reports/msi-queue-synthetic-001/dispatch --source-dir reports/msi-queue-synthetic-001/source --state-dir reports/msi-queue-synthetic-001/inbox --codex-executable $codexExe --max-seconds 180 --max-tasks 1 --execute
python -B scripts/eventguard_watch.py run --run-dir reports/msi-live-001 --codex-executable $codexExe --max-seconds 300 --max-tasks 2 --execute --allow-live
```

第一條為程式生成的一件公開合成事件，source/inbox 均隔離；真工具 receive→query→ACK、三 ID 及 SQLite receipt 匹配，任務上限正常退出，runner／CLI exit 0。合成 source 刻意放入不應傳出的名稱／路徑／指令誘餌，實際工具返回沒有洩出，snapshot 僅七欄。證據 `reports/msi-queue-synthetic-001`，07:51:56–07:53:29 UTC。

第二條為本輪已授權的實機前景試運轉，08:07:15 UTC 開始監看，兩輪後於 08:10:23 UTC 合作停止。達任務上限後 watch=completed、monitor_exited=true、agent=task_limit_reached、child_exited=true，runner／各 CLI exit 0，完整未截斷退出回條及所有本輪 owner 鎖釋放。獨立審查以 SQLite mode=ro 的最小欄位與實際 JSONL 確認事件在本輪觀測／保存，非舊 backlog；收到/query/結果/ACK/receipt ID 集合匹配，交給 agent 的集合無缺漏、額外或非預期重複。任務上限外事件仍耐久 pending，沒有假稱全部佇列已交付；完整實機數量及 ID 只留本機忽略 audit，不納入 Git。部分來源仍 partial，沒有把 ACK 解讀為安全或完整 coverage。

獨立核對命令 `python -B reports/live-channel-evidence-001/audit_live_delivery.py`，08:12:31 UTC exit 0、passed=true，保存 `delivery-audit.json`。審查直接解析三個真 CLI 的工具返回及 receipt，未以 agent 文字或 summary 取代；另核對 watch／Monitor／source dispatcher／stdio inbox／capture 鎖已釋放。沒有讀取原始 native evidence、Codex sessions 或將 stderr／runtime 上傳。

必要測試與問題保留：

- 全套以 `python -B reports/live-channel-evidence-001/verify_source.py` 執行，08:03:39 UTC：269 discovered、267 passed、0 failure/error、2 symlink 建立權限 skip，64 Python AST 通過，84.916 秒，exit 0；逐檔雜湊確認跑測試期間 source 未變動。`final-unit-tests.txt`／`final-unit-summary.json` 留忽略目錄。此 suite 是 fixture／fake CLI／SDK 檢查，模型呼叫與實機掃描均為零，與上述真任務分開。
- 首輪 suite 的 1 failure／1 error 留在 `unit-tests.txt`／`unit-summary.json`：分別為停止閘道改動後的競時 fixture 與 Windows 狀態檔共享衝突。已修正 fixture、在 JSON 原子 replace 加僅限指定 Windows 錯誤的有界重試（最多 190 ms）；持續拒絕仍失敗並保留舊值，未更改權限。
- 較早的一次合成 EOF 測試在關閉 stdin 後，SDK 預設工作群未退出，父測試 exit 1，留一個已核對的 Python 測試程序。修正 stdio 工作群的 EOF 合作取消後，新 EOF 測試自然 exit 0，inbox 18 項測試通過；但舊程序仍存在，且沒有強停批准，未 kill／terminate，不能宣稱所有測試程序皆已退出。身分／啟動時間與檢查證據只留 `reports/live-channel-evidence-001/known-test-orphan.json`。該程序不是本輪實機監看或模型任務，沒有採集系統資料。

本輪前景試跑已結束，目前沒有持續監看；再次執行需當次有效範圍。已接通的是本機事件到專用短期 CLI agent，沒有證明任意桌面對話自動接續、完整 Windows coverage、原生診斷／處置、長期低負載、休眠／崩潰恢復或永久等待。舊 MVP、私人歷史、憑證與 runtime 未推送；集中提交只含審查後 source／tests／操作文件，指定 feature 分支，[skip ci]，不手動觸發 CI。

## 2026-10-22：MIT 與最新驗收摘要發布

使用者明確指定 MIT 並要求公開 `SecludedCorner/EventGuard`。本批以 `cc6e799` 為程式來源，新增 LICENSE、README 驗收結果表，同步 HANDOFF 與 PUBLISHING；沒有修改 Python、模型設定或監看來源，沒有啟動模型／實機採集或重跑原 suite。README 保留 A／B／C 的 7 唯一事件／8 接收與 query／7 ACK、新入口有限真通路及 269 項測試結果，並明列目前一小時／五任務限制及未完成的長期能力。

後續公開合成投遞探針已追加到使用者指定的專用合成佇列，本次只讀核對仍 pending、0 ACK；未證明 dot 收到或回應，不列為成功通路。該探針的 manifest、入列回條與資料庫留在本機忽略 reports；未發布事件 ID、使用者路徑或完整執行資料。

發布前只讀審查涵蓋遠端 main 與 feature 的全部可達內容：9 commits、143 個 unique blobs，均來自與私人舊歷史分離的 publication root；`fd45578` 不在遠端可達祖先中。未發現執行目錄、原始會話、憑證、資料庫或封存檔被追蹤；三處路徑命中均為明示匿名 synthetic 隱私測試 fixture。GitHub 端未有 Actions run／artifact、issue、PR 或 release／附件。本機原始資料與未推送分支保留，不使用 --all／--mirror／force。

本批驗證為既有證據核對、MIT 標準文字比對、Markdown 本地連結與 git diff --check；不把這些文件檢查當成新模型或長時間驗收。Git 作者 metadata 的公開範圍另依 PUBLISHING 檢查，不因原始碼掃描通過而忽略。透過指定 feature 與 PR 更新 main，公開可見性與 MIT 辨識結果以 GitHub API 發布後回讀為準。

## 2026-10-22 18:35 台北：Phase 1 原生採集與拒讀證據

來源基準 `dbac91b`，分支 `feat/local-codex-acceptance`；使用者明確確認 Phase 1、一般權限唯讀實作及逐來源驗證。本節對應的 Phase 1 提交以 Git 記錄及本機 `reports/phase1-collectors-001/source-commit.json` 核對；驗證另存精確 source hashes。不 fetch／push、不啟動真 Codex／模型、不提權／UAC、不下載安裝、不改系統政策、不做 Phase 7 狀態注入。

本批實作：標準庫 ctypes／winreg 的七來源 native backend、同一封裝契約的 PowerShell fallback、stage／exception_type／HRESULT／Win32／provider_code／category 原因碼；錯誤與 coverage 經 monitor 保存後可由 status／DiagnosticAPI 讀取。原生有 partial／denied／unknown 等結果時不自動重試另一途徑。Defender 設定與 Security Center 彙總不升格成即時防護狀態；tasks 只讀 COM Name／Path／State。契約與七來源範圍見 [COLLECTOR_CONTRACT](docs/COLLECTOR_CONTRACT.md)。

實際命令（全在本機忽略 reports；probe 腳本及原始資料不提交）：

```powershell
python -B reports/phase1-collectors-001/monitor_probe.py
python -B reports/phase1-collectors-001/probe.py --backend powershell --label powershell-final
python -B reports/phase1-collectors-001/verify.py
```

第一條在隔離 runtime 做一輪真實七來源，18:33 台北完成：listeners／startup／services／versions 為 ok；processes partial（OpenProcess 有 Win32 5 等逐物件缺口）；Defender partial（設定／彙總可讀，七個有效防護欄位仍 unknown）；tasks unknown，object 階段 COM HRESULT 0x80070003／object_unavailable，OS 原文「系統找不到指定的路徑。」。另一次 `schtasks /query /fo csv /nh` 同樣找不到路徑、exit 1；不把該結果改寫成沒有排程或已證明權限拒絕。

第二條同上下文逐來源一次對照：五個 provider 明確 CimException、provider_code=AccessDenied／category=PermissionDenied／HRESULT 0x80131500；startup／versions 為 ok。七個 PowerShell 子程序均實際啟動並自然 exit 0，CLI 正常退出不等於來源成功。新 native 主路徑因此取得多個原先 CIM 拒讀來源的 metadata；不推定桌面 shell 與本工具 token 等價。匿名 token metadata 為非 elevated／has_restrictions／非 AppContainer，沒有讀帳號或私人 SID。

實機證據：`monitor-final/source-*.json`、`monitor-result.json`、實際 CLI 回傳 `status.json`、`exit-receipt.json`；`powershell-final/*/command.json`、`raw-evidence.jsonl`（真 stdout／stderr）、`process-exit.json`、`manifest.json`；`schtasks-evaluation` 保留比較的 argv／原始輸出與退出。全部在 `reports/phase1-collectors-001`。原始 OS 訊息標記為 FormatMessage 來源，不冒充 provider Exception.Message。隔離 monitor stopped、monitoring=false、runner_pending=false、singleton 可重新取得；probe／monitor／全套測試各程序 exit 0。沒有新常駐監看／模型程序；不宣稱已清理歷史已知 orphan。

測試數單一來源為 `full-summary.json`：Python 3.13.3，全套 287 discovered、285 passed、0 failure/error、2 symlink 建立權限 skip；69 個 Python AST 無錯，86.771 秒，source hashes 全程不變。範圍為 fixture／SDK stdio／fake CLI，與上述真實 Windows 採集分開；沒有真模型。相關 collector／core／rules 的 84 項亦全通過，見 `targeted-final-summary.json`。

本輪修正中保留的失敗：初輪 tasks 的 OS 訊息格式化將有號 HRESULT 轉成超出 C long 的數值，遮住原錯誤；修正後取得真 0x80070003，再加入回歸測試。native 版本初輪拿到 Windows build tuple，已改讀與 fallback 相同的 ProductVersion；PID 時刻亦統一 UTC 微秒。大型 coverage 測試發現原 health 64 KiB 寫入限制不容新安全證據，現 health 讀寫同為 2 MiB；config 等其他限制不變。status 的 SQLite 唯讀連線未明確 close 所造成的測試分享衝突已修正。初輪 source／目標測試失敗證據均保留，不算通過。

尚未做到：tasks 的成功讀取、Defender 七個有效狀態、所有程序欄位可讀；H1–H5 的可支持／未排除範圍見契約。原生／COM 單一 OS 呼叫永不返回的硬性停止、Job Object、monitor_gap、長期容量／soak、背景自啟及 agent 診斷均仍屬後續 phase；本批不證明全天候或整機安全。AUDIT 不覆寫，時間歷史與 README 全面收斂留 Phase 6。

## 2026-10-22 21:53 台北：Phase 2 角色比較，等待選案

使用者說「繼續」後恢復目標，先核對工作目錄、分支 `feat/local-codex-acceptance`、HEAD `088be7561c5ead1bb4e289ad3b4ef6ce03748398` 及乾淨工作樹；保留已完成 Phase 1，不重跑七來源或模型。此批只新增 [AGENT_ROLE_DECISION](docs/AGENT_ROLE_DECISION.md) 與交接紀錄，未修改程式、測試、設定或 playbook，兩候選執行路徑皆未實作。

實際命令 `python -B reports/phase2-role-001/compare.py`，Python 3.13.3，exit 0；程式建立一件專用 synthetic listener 事件，直接呼叫既有 playbook、QueueInbox 與 fixture DiagnosticAPI。receive/query 的七欄 snapshot 相同，query 新增觀察 0；ACK 及重播的 result ID 相同、SQLite receipt 一筆、incident_conclusion=not_assessed、real_agent_wake_verified=false。兩次相同型別化 fixture 查詢的觀察相同，不需要模型取得；不是已完成 B 或真 agent 測量。程序名的指令式文字仍可出現在 DiagnosticAPI 輸出，控制字元會去除；B 不能直接暴露這份結果。

測試數以 `reports/phase2-role-001/summary.json` 為準：相關既有 fixture 18 項通過、0 failure/error/skip，0.9717 秒；另有 18 個探針斷言，不和測試數相加。未重跑全套。原始碼 hashes 前後一致；該探針 model_calls=0、real_codex_tasks=0、native_provider_queries=0、external_attempts=[]。單次元件計時不是完整 A/B 效能評比；模型品質／延遲／token／金額均未測。原始回傳、synthetic event、SQLite 回條與 tests.txt 全留忽略 reports，不提交。

建議 A：確定性 playbook＋本機報告，agent 降為可選；B 的事件綁定、字串 projection 與可量增益要求已寫入比較報告。依原請求等待使用者選 A／B 後才實作；選 B 亦不自動批准真模型。Phase 1 的 tasks／Defender／程序 coverage 限制仍在；Job Object、容量、長期驗證及實機注入尚未進行。本批不啟動背景監看、不建立排程、不提權、不下載安裝、不操作網路、不推送。

## 2026-10-22 22:32 台北：獨立核心與人類／agent 共用操作

使用者已明確改定方向：「不論有沒有 agent 都要能獨立運作，人類要能操控並知道發生了甚麼；也提供 agent 介面，使用同一套操作與可見資訊」。先前 A／B 等待關卡已解除。來源基準 `a130dcef3648330adadfef99875873db0888f22e`、原 feature 分支，原有未提交變更為空；沒有模型／真 Codex、提權、下載安裝、系統政策變更、網路、永久 MCP 註冊、排程、自啟或實機狀態注入。

實作共用 OperatorAPI，CLI 與同一 stdio 入口的 operator mode 共用能力、狀態、事件清單／檢視、事件綁定唯讀查證、報告及合作停止；MCP 另提供固定一輪 monitor_once，長期前景仍用 CLI。核心不依賴 SDK／模型，舊三工具接收／摘要 query／ACK 與驗收契約保留。原有 status／report 邏輯移入共用層，read-only 視圖不初始化或修改 SQLite。新事件表顯示固定說明、具體觀測、coverage 與最近診斷。

查證只從耐久事件綁定 protocol／port、process_instance_ref 或 persistence kind，不接受 agent 的自由查詢參數；缺程序實例留 process_binding_missing。產出 observations、coverage、uncertainties 與固定 incident_conclusion=not_assessed，另保存到同一 SQLite 的最新 event_reviews，不修改 pending／ACK／receipt。資料最小化、字串與快取 schema 驗證、固定錯誤 envelope、容量／ACK reserve 回滾及 ACK 事件輪替清理均有對應測試；介面契約見 [HUMAN_AGENT_INTERFACE](docs/HUMAN_AGENT_INTERFACE.md)。

精確測試數單一來源為本機 `reports/phase2-operator-001/verified/summary.json`：Python 3.13.3，命令 `python -B reports/phase2-operator-001/verify.py --label verified`，304 discovered、302 passed、0 failure/error、2 symlink 建立權限 skip；72 Python AST，來源 hashes 前後不變，92.134 秒，exit 0。含 17 項新操作介面測試與既有 suite，範圍 fixture／已安裝 SDK stdio／fake CLI；沒有真 agent 或本輪 Windows provider 驗收，不與歷史實機／模型數字累加。

`verified/operator-stdio-trace.json` 保留真 Python 子程序的八個 tools/call request／實際 SDK response、child PID、exit 0、reader thread 已退出及該程序 remaining_owned_children=0；不是 Codex agent 接收證據。舊通路測試仍通過。另命令 `python -B reports/phase2-operator-001/demo.py --final` 在隔離 runtime，實際執行人類 CLI main 的 fixture 監看、產生三件 synthetic、list／inspect、阻止 synthetic 原生 query、fixture 注入診斷與 JSON／HTML 報告。`demo-final/manifest.json` 保存命令 argv、真 stdout、同事件關聯、診斷與 source hashes；三件仍 pending、0 receipt，核心未 import MCP，monitor stopped，exit 0。所有原始資料留忽略 reports，不提交。

保留的失敗與修正：第一輪全套發現預先建立診斷表占用小型 outbox 空間，使既有滿載／ACK 輪替測試失敗；改為明確 diagnose 時才在同交易建表，失敗連 DDL 一併回滾。可讀性測試另發現原 schema 會丟棄既有 synthetic Defender 的 property，現在保留此 metadata key、共用 view 僅接受固定防護欄位枚舉。初輪／release 失敗證據及中間 final 成功快照均保留，當前版本只以 verified 為準；沒有放寬原容量或移除既有測試。

尚未驗證：新 agent 介面的真模型操作／效益、重開機後的 Windows coverage、任意 OS hang 的硬性退出、長期控制／自啟、monitor_gap 與 soak。Phase 1 tasks／Defender／程序可讀性缺口未改寫為成功；診斷與 ACK 仍不代表主機安全。Phase 3–7 尚未實作，本輪不宣稱全天候或已將工具載入任意桌面聊天。具體提交由 Git 與本機 source-commit.json 綁定，不推送。
