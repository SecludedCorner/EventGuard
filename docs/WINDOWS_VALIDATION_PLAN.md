# Phase 7：Windows 可逆狀態與故障恢復驗證計畫

## 2026-10-29 新包已執行／目前授權與partial結果

使用者已授權本專案必要的一般權限唯讀開發診斷，同範圍不再逐次問；每次保留scope/hash/time與授權依據、私有Job／最小資料及退出回條，詳AGENTS／CLAUDE最新節。這不擴充提權、系統／安全設定、新模型、敏感處置或未指定長時運行。

reports/windows-listener-diagnostics-20261029-01已單次執行，四表250列且計數一致，身分缺122，error23筆均ListenerOpenProcess access_denied；source partial、baseline_incomplete，不能稱PASS／安全。內自然0、外validator自然2，均remaining0／無強停；13/13只是回條一致。本次typed分類完整不代表已定位owner／必需管理員／sandbox根因。源碼已使用最小QUERY_LIMITED_INFORMATION，不能靠放寬或提權洗綠。其他六來源的單次有界開發查核另存source-coverage-readonly-20261029-01，不將診斷範圍混作此listeners單次批准。

## 2026-10-29 現行來源已重新prepare（尚未批准／執行）

新的專用目錄為`reports/windows-listener-diagnostics-20261029-01`，綁7ef2c7b來源、12檔hash及本次manifest，query_started=false，template approved=false；執行程序保存在該目錄AUTHORIZATION_REQUEST與NEXT_DIAGNOSTIC。舊20261028包維持superseded，不改歷史或重用已用完的單次批准。

只申請一次listeners native baseline：TCP/UDP、IPv4/IPv6及既有必要程序建立時間查核，query最多5秒、總工作預算30秒；只存固定狀態／計數／既有錯誤分類與自有Job退出摘要，不存PID／名稱／路徑／位址／port原始facts，不新增來源／socket／registry／系統變更／模型或持續權限。具名直接答覆獲准後才記同run的human-approval.json與有效時間、核hash並由私有Job執行；尚未執行、不把準備或合成測試當完整baseline成功，更不代表安全或防守完成。

## 2026-10-28 計數完整性修復與舊準備包失效（最新）

P0-LISTENER-COUNTS-003已修正四表status=ok但返回列數不足／錯protocol／錯IP family仍可能complete的缺陷。新增逐表table_counts_consistent，不降低身分或退出要求；原重現5failure entries保留，修後52/52定向通過，無native/model。這不解釋或消除舊111列身分缺失。

因script來源改變，下節reports/windows-listener-diagnostics-20261028-01及其舊hash現在已superseded，不能再按其指令執行。原manifest／template／NEXT_DIAGNOSTIC保留作歷史，未獲批准也未執行。後續若有必要真診斷，須先依當時版本另prepare、核對source/hash再取得一次精確批准；本輪不另問或採集。

## 2026-10-28：最小身分錯誤診斷切片與唯一後續決策（尚未實跑）

P2-OS-DIAG-002 沿用 collector 已有的 typed evidence；只補 baseline 保存時的 `error_summary`，不新增採集或身分關聯層。固定 stage／operation／reason_code／status 分組計數，最多保留64筆既有 error prefix，任意文字／未知值正規化為 unknown；不保存 exception、PID、名稱、命令列、路徑、位址、port、建立時間或帳戶。新增 winapi.py 到準備 manifest 的來源 hash，將既有身分讀取依賴一併綁定。沒有改 NativeBackend、完整性標準或 query/scope。

| 下次真查詢可分辨的既有碼 | 最多能支持的結論 | 仍不能支持的結論 |
| --- | --- | --- |
| access_denied＋stage／operation | 該 API／階段回報拒讀類別 | 不證明必需管理員、sandbox根因或哪個owner；不授權提權 |
| object_unavailable | 物件／欄位當下不可用 | 不證明程序已退出、PID重用或競態 |
| listener_pid_reused／ListenerProcessIdentity | 既有檢查觀察到建立時間晚於捕捉時點（或無時區） | 不證明完整程序生命史或已觀察到退出→重用 |
| api_unavailable、query_failed／其他固定碼 | 原始分類、階段及操作的聚合數量 | 不把一般失敗補成具體根因 |
| unknown、unretained_count或count_consistent=false | 分類／保留／計數證據缺口 | 不按已知樣本比例外推缺失原因，不把缺資料填成0或安全 |

計數單位是 error records，不是端點列數或唯一owner；`retained_count=classified_count+unknown_count`，只在報告總數可核對時給 `unretained_count=reported_count-retained_count`，否則null。`error_summary.complete`只代表分類證據完整；`baseline.complete`仍要求零錯誤、零身分缺口、四表完整及原自有退出標準。舊235列／缺111列／21錯誤收據沒有原因碼，不能用這次fixture或新函式回填舊根因。沒有新增任何PID一致性或跨輪關聯資訊。

下一次方案僅prepare於 `reports/windows-listener-diagnostics-20261028-01`，run `6dd82da8fcd84d72ace2fd6689bc20e7`，manifest SHA256 `a0a3d93cebe3c71b874dd638d7dfb9e79e9b74fda16fec29b030ec88e9282477`；12檔hash、未批准template及 `NEXT_DIAGNOSTIC.json` 綁定現行切片。唯一後續人類決策是是否另批准這一目錄的一次同範圍 native baseline：TCP/UDP、IPv4/IPv6與原必要程序建立時間，query5秒／總工作預算30秒；只保存固定分類計數及自有Job回條，無其他來源、socket、registry、模型、系統變更、持久存取或額外身分資訊。本輪不提出新批准問項、不執行；舊批准已用完。

若之後有新的精確批准，先核對HEAD／12檔來源與manifest、runner hash `a895b8f4518a4efd944ac6368aa5cd1dd4388512cb76711b458eb594dc8612d9`、同root/run/scope及無任何執行回條，將當次原文與時間寫入human-approval.json（最長30分鐘）。只用既有 `reports/windows-listener-preparation-20261026-01/run-owned.py --root reports/windows-listener-diagnostics-20261028-01` 一次；私有Job在執行前加入，20秒合作stop／3秒grace，保留內外原HANDLE退出／remaining／force／deadline。partial/denied/unknown/truncated／逾時／強停均如實不通過，不換目錄重試。若已存在intent或result先讀結果，不重跑。

驗證僅新分類、計數守恆、隱私與原閘道：`reports/verify-listener-error-summary-20261028-01` 定向27/27，source_unchanged、原Job自然0／remaining0／無強停，native scan/model均0；不是這份新方案的原生驗收。取得新結果後才依聚合原因決定必要最小下一步；沒有原因變化就不追加掃描或反覆fixture。

## 2026-10-27：單次 baseline 已執行，完整驗收仍不通過（最新）

P2-OS-001 已獲原具名單次批准，並在 reports/windows-listener-baseline-20261026-01 執行一次。四表ok共235列，但必要程序身分缺111列／error21，source partial、baseline_incomplete；query elapsed0.739012秒，內query原Job自然exit0、外validator原Job自然exit2，兩者remaining0／無強停。13/13是收據一致性，不是完整baseline PASS；result與原回條保留。沒有注入、模型、系統修改或額外查詢，一次批准現已用完。

本次不能定位身分失敗的具體原因；後續精確診斷／重驗需另批准，不以提權或降低完整性標準解決。下方注入／長時／恢復計畫仍未執行，「尚未執行」不包含這次已保存的baseline。最新接續見STATUS/HANDOFF。

狀態：**計畫已提出，尚未執行；實際注入、長時間監看、登出或重啟都須當次批准**。本文件不啟動程序、不寫登錄或安全設定。先讀 [現況](../STATUS.md)、[生命週期](PROCESS_LIFECYCLE.md) 及 [soak 計畫](SOAK_PLAN.md)。不呼叫模型、不連外、不提權、不停止非本工具程序。

## 2026-10-26：可執行前置與規則界線

新增 `scripts/validate_windows_listener.py`，預設只準備專用 reports/windows-listener-*、source hashes、批准請求及未批准 template；不建立 native collector。`--execute` 只接受同一 run/root/hash、嚴格固定 scope 及當次人類授權：一次 native listeners、query 5 秒、總工作預算 30 秒，無 socket、registry、模型或其他來源。不保存其他 listener 的 address/port/PID/name/path/raw facts。成功僅代表這次 baseline 完整，不代表主機安全或完整生命週期通過。

原計畫的 loopback→陽性 new/resolved 期待與產品不符：`rules/detector.py` 明確只讓 unspecified address 成為候選，127.0.0.1 按設計被忽略；恢復另需兩次完整缺席觀測。不得偽造 wildcard facts、改綁全介面或為測試改規則。下列 loopback 案例應作負向驗收；陽性實機案例仍須另訂必要且安全的範圍。既有 fixture 可驗 wildcard new／三輪去重／兩輪 resolved，但不是實機證據。

執行時須由私有 Job launcher 保留原 HANDLE，先用該 root 的 stop.request 合作取消，再有限 grace/自有 Job 收尾；單看 elapsed 的後驗檢查不等於硬截止保證。準備及 fixture 通過不構成原生採集授權，結果與限制記在 STATUS/EVIDENCE。

## 批准前可審查的範圍

一台已指定 Windows 主機、一般使用者、專用新 reports 目錄、一次前景 monitor；只觀測 listeners/startup 及必要 health/owner，不擴大全機掃描。人類先選本輪案例與總時限。保持 transport disabled，不啟動 dispatcher 或 Codex；這是採集／規則／恢復驗證，不是真 agent 驗收。

不得重用 live 的基線、outbox 或既有測試 ID。保存程式 commit、來源 hashes、Python/OS 的匿名版本、固定 argv、每次動作與觀測 UTC、單調時鐘差、collector coverage、baseline/source、同 event/episode IDs、SQLite hash/receipt 及 owned Job 退出回條。私人 runtime 不提交。

| 案例 | 有界注入與回復（批准後） | 查核與通過標準 |
| --- | --- | --- |
| 本機 loopback listener（負向，尚未執行） | 另行批准後，才以私有 Job 內 Python 綁定 `127.0.0.1`／OS 指派 port；不接受／傳送應用資料。只保存本工具 PID+建立時間及 port，先合作關閉 socket，再核對原 Job 退出 | 完整 baseline 後才注入；來源應觀測到本工具端點，規則按設計不產生 listener.changed，不能宣稱陽性 new/resolved 通過。不得推導 Internet 可達或主機安全 |
| HKCU Run 名稱 | 只建本輪唯一值名稱，型別 REG_SZ、內容空字串，不放可執行命令。先證明同名不存在，碰撞就中止，不覆寫；測完只刪同名稱且仍為原型別/空值的測試值，不刪 Run key | 新增／移除各自有事件且共用可追溯 episode；三輪不變無重複。父程序另記清理義務，即使 child 例外也查證值已不存在；不一致停止並報告，不刪其他值 |
| monitor 正常停止／重開 | 先 stop，核對該 instance 的真退出與 Job active=0，再由人類明確啟動下一次 | 單例釋放、沒有殘留；gap 若存在須保存為未觀測區間，不能變成無事件／安全 |
| 本工具 monitor 失敗 | 專用啟動器保存自己 Job handle、PID+建立時間；先合作停止，需模擬非正常中止時只關閉本工具 Job，記 forcibly_terminated，不能當自然退出通過 | 下次啟動從先前 checkpoint／heartbeat 產生耐久 monitor_gap；保存失敗則阻擋採集，同 gap ID 可恢復；不碰 Job 外程序 |
| 人類登出／重開機 | 先完成 listener／Run 清理並停止其他本輪工作；由人類操作系統，本工具不發起 logout/reboot。登入後由人類手動啟動監看 | 核對舊 PID+建立時間、heartbeat 新鮮度、boot/時間資訊可讀性與 gap；沒有自啟授權，不要求自動恢復，也不宣稱已驗證排程 |

每案例在注入前先確認該來源的完整成功觀測；denied/unknown/timeout 則該案例 **blocked**，不為使測試通過提權或關掉 coverage 閘道。注入在變更前等待就緒回條，回復在停止後保留查證，不能只看 DB 筆數。

## 延遲與去重驗收

1. 記錄動作 `t0`、第一筆包含該狀態的採集完成 `t1`、事件 commit `t2`、人類 status/inspect 可見 `t3`。分列採集排程延遲、採集耗時與事件保存／呈現延遲，不填估計值。
2. 上限按本輪設定的來源 interval、query timeout、排程抖動容許量預先計算；listener 120 秒、startup 600 秒的預設不可拿秒級即時保證代替。未事先訂上限只報實測，不寫 passed。
3. 相同觀察至少三輪；比對 generated/observed/persisted IDs、episode、transition 與計數，列 missing/duplicates。恢復必須是新的 resolved transition，不能拿 ACK 當恢復。
4. 降級期間保留原狀態、標未知；重新完整成功觀測後才判恢復。重啟後同一缺口不重複建立不同 gap IDs。
5. 每次退出驗 owned Job active=0，協作與強停分列。清理失敗／未確認時保留原始證據及精確殘留，不自動擴權、不宣稱全部成功。

## 輸出與停止條件

交付本輪 manifest、動作／回復紀錄、來源 coverage、event ID 表、延遲明細、退出與殘留回條。先交一個案例結果，沒有診斷變化不反覆注入。超出時限、磁碟／佇列滿、碰撞、權限不足或清理不符就停止新增動作、完成已批准的精確回復並報告。

這些案例即使通過，仍不是漏洞可利用性、全天候防護、任意聊天喚醒或長期可靠性證明。24 小時 CPU/RAM/handle/SQLite 量測是獨立 soak，另按既有計畫與批准執行；本輪計畫不啟用服務、排程或開機自啟。
