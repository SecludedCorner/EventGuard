# EventGuard 狀態與驗收缺口

更新：2026-10-22 UTC。本檔只記錄工程事實，不包含真實主機的警報、路徑或安全結論，也不授予操作權限。

**MSI 本機有限合成事件真通路 A／B1／B2／C 已通過；完整產品仍為工程預覽。** 正式監看未啟動，長期 ingress／原生診斷仍未驗證。最新本機證據見本檔末節；以下保留各時間點歷史，不以 mock 或舊測試冒充真通路。

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
| 真 ingress | 無事等待不推理，只有事件開啟必要回合 | **blocked，尚無實際接收端** |

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
