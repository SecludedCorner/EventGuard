# EventGuard 狀態與驗收缺口

更新：2026-10-22 UTC。本檔只記錄工程事實，不包含真實主機的警報、路徑或安全結論，也不授予操作權限。

**目前是工程預覽，產品目標尚未完成。正式監看未啟動；真正 agent ingress 未接通，沒有已驗證的真實喚醒。** Mock 僅用於測試，不是可替代的產品功能。

## 目前唯一優先：本機 stdio MCP 等待

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
