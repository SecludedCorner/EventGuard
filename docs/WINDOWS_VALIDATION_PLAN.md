# Phase 7：Windows 可逆狀態與故障恢復驗證計畫

狀態：**計畫已提出，尚未執行；實際注入、長時間監看、登出或重啟都須當次批准**。本文件不啟動程序、不寫登錄或安全設定。先讀 [現況](../STATUS.md)、[生命週期](PROCESS_LIFECYCLE.md) 及 [soak 計畫](SOAK_PLAN.md)。不呼叫模型、不連外、不提權、不停止非本工具程序。

## 批准前可審查的範圍

一台已指定 Windows 主機、一般使用者、專用新 reports 目錄、一次前景 monitor；只觀測 listeners/startup 及必要 health/owner，不擴大全機掃描。人類先選本輪案例與總時限。保持 transport disabled，不啟動 dispatcher 或 Codex；這是採集／規則／恢復驗證，不是真 agent 驗收。

不得重用 live 的基線、outbox 或既有測試 ID。保存程式 commit、來源 hashes、Python/OS 的匿名版本、固定 argv、每次動作與觀測 UTC、單調時鐘差、collector coverage、baseline/source、同 event/episode IDs、SQLite hash/receipt 及 owned Job 退出回條。私人 runtime 不提交。

| 案例 | 有界注入與回復（批准後） | 查核與通過標準 |
| --- | --- | --- |
| 本機 listener | 私有 Job 內的 Python 以 `127.0.0.1`／OS 指派 port 綁定 TCP listener；不接受／傳送應用資料。保存 PID+建立時間及 port，先合作關閉 socket，再等待本工具 Job 退出 | 基線成功後才注入；同一 PID+時間+port 有新事件，連續三輪相同觀察不得重複 new；關閉後要有完整成功觀測才可 resolved。loopback 不推導 Internet 可達 |
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
