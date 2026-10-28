# Phase 4：容量、ACK 保留與恢復

## 處置歷程備份的唯讀身分預檢

明確備份後，可由操作者自行將備份檔內容送入 CLI，例如合成範圍：

```powershell
Get-Content -Raw reports/history-backup-example.json | .\EventGuard.cmd --format text events preview-history --namespace test
```

備份含本機敏感識別資料，不要提交或分享。CLI 只接有界標準輸入，不自行挑選或讀取路徑；回傳身分衝突、已存在／缺失操作計數及目標是否為備份的完全前綴，不輸出個別 ID。舊版無 namespace 或跨 namespace 直接拒絕。雜湊非簽章；即使零衝突且順序一致，也不驗來源真實性、備份是否涵蓋全部歷程、容量或還原能力。此命令不還原、不刪除或釋放容量。


核心仍為 Python 3.13 標準庫。以下只變更本工具的資料檔，不修改 Windows 設定、不啟動模型、服務或排程。實測命令與精確測試數見 [EVIDENCE](EVIDENCE.md)；24 小時 soak 僅有 [計畫](SOAK_PLAN.md)，尚未執行。

## 政策與操作

在 `config/default.json` 設定有限上限；`storage_policy.py` 集中驗證，拒絕 bool、未知欄位、負數與超過硬上限。舊設定缺少新欄位時使用預設值。

| 區域 | 預設／可設定硬上限 | 清理與恢復 |
| --- | --- | --- |
| outbox | 1,000 件、8 MiB；ACKed payload 7 天；receipt 30 天／4,000 件 | TTL、筆數或位元組壓力只清 ACKed payload／其 review；receipt 另有保留窗及壓力輪替 |
| inbox | 1,000 active、1,000 completed、合計 8 MiB；completed 30 天 | ACK 後合併成一份完成回條；先耐久保存，再清重複 triple；滿載輪替舊 completed |
| dispatcher | 128 active、128 completed、合計 256 KiB；completed 30 天 | active／completed 各用一半 byte 預算，先存 compact proof 再移除 active entry |

數量／位元組上限可以調小，不能改成無限。保留秒數可為 0–31,536,000；0 表示下一次清理即可到期，不代表停用上限。TTL 是最長保留目標，壓力與筆數限制可提前輪替已完成資料；清理採惰性執行，不新增背景計時器。

outbox 政策保存在 SQLite `meta.storage_policy`，ACK 使用的預設 EventStore opener 會繼承，不會擅自放寬已設定上限。monitor 啟動及後續 evaluation 會清理。`status` 的 namespaces 顯示實際政策、大小、receipt 數及輪替計數；CLI 與可選 agent 的共用 status 都可讀到，不會因查 status 啟動模型。

inbox 政策由 dispatcher 從專案設定套用，保存於專用 state 的 `inbox-limits.json`，其 stdio child 沿用；直接使用 QueueInbox 可傳入同一 `limits` 字典。修改既有 quota 不刪 pending；縮小到低於現有占用量時先阻擋新工作，讓既有工作完成後恢復。outbox 主檔已大於新 byte cap 時拒絕開啟，不偷偷放寬；應恢復原政策，再依既有政策清理。SQLite free pages 可重用；本階段不自動 VACUUM，因此主檔不一定縮小。

## 處置歷程（合成寫入與唯讀顯示已驗）

純 record 驗證已設每事件 256 筆、全庫 4096 筆的硬界線；識別與來源只作冪等及操作通道 metadata，不代表已驗證的操作者。滿載時目標行為為明確拒絕新狀態及新歷程並維持原狀，不刪 pending、ACK 或既有紀錄；容量恢復方式尚待後續明確設計與驗證，不宣稱能永久寫入。已在 EventStore 處置交易內延遲建表及寫入，事件詳情與 Web 可唯讀顯示歷程；未來對舊處置應顯示「此前未記錄」，不能補造。

已以 synthetic 測試同交易、ACK byte reserve、頁面容量、重建 Application 重播／衝突與回滾；舊版 DB 唯讀相容及 GET 不遷移仍須在讀取實作時核對。新紀錄以事件 payload hash 綁定身分；舊版未綁定紀錄保持未知，不依現有事件回填。已有合成測試的明確 CLI 不覆寫備份入口，但尚未驗證還原或釋放容量；不能用它刪除來源紀錄。固定筆數本身不保證磁碟可用，也不代表歷程防竄改。這是待實作契約，非已完成持久化。

## 永不自動丟棄的資料

pending、retry 與未 ACK failed 不因年齡、筆數或 byte 壓力清除。舊版「failed 七天後清除」已移除。滿載新增失敗時，evaluation 的事件與 detector state 一起回滾；先前 event ID／hash 保留。consumer 恢復並有真正耐久接收 ACK 後，已 ACK 資料才可讓出容量。

未確認 child exit、只有失敗 trace、用完嘗試預算、沒有有效交付／ACK 證據的 dispatcher entry 都不輪替，也不重置三次上限。這些情況需要查明既有證據，不能靠清帳本重新啟動模型。沒有 consumer 或全是未解決資料時，持續背壓是正確行為，不能宣稱總能自動排空。

## inbox 收尾與重播

新 receive admission 先預留 query、result、completed 各 4 KiB，總共 12 KiB，再保存 snapshot；因此 byte cap 可能先於 active count cap 到達。型別化固定輸出超過預留大小則明確失敗。舊 triple 未預留空間，仍可在實際 byte 預算內完成 query／ACK，但不能再接收超額事件。

result 先保存，才寫 outbox ACK；ACK 成功後，以 fsync＋原子 no-replace link 保存 `completed-<hash>.json`，內含原 snapshot／query／result，再清除三份重複檔案。其後重播沿用同一 event/query/result，不再寫第二次 ACK；不同 receipt ID 會被核心拒絕，既有 ACK 時間不改寫。

ACK 交易同時為接收器尚未完成的原 receipt 設 `pending_finalization`。完成回條寫入失敗時保留 triple 與原 ACK proof；payload 仍可清理，但 TTL、count、byte 輪替都不能刪這張 proof。完成檔耐久成功後才解除保護，再清 triple；重啟 maintenance 可核對原 event／payload hash／query／result 後補完。解除保護失敗仍留可恢復資料，不以已寫 result 推定 ACK。

保護中的 receipt 仍受 `receipt_limit` 與 SQLite byte cap 限制；達上限時明確回滾新的 ACK，原 pending／result 保留。解除既有保護後可重試，不換目錄清用量。舊 DB 自動增加預設未保護欄位，舊 ACK caller 介面仍可用；既有長駐 GUI／MCP 需正常重新載入新版，舊程式不提供此保護。新版不能重建升級前已遺失的原 ACK proof，該情況仍明確 blocked。

共用 status／overview 的事件儲存區顯示 `pending_receiver_finalizations` 數量；舊 schema 尚無此欄時回 null，不因讀狀態遷移或改寫資料庫。該值只表示接收器收尾，與漏洞修復／案件結束無關。

已清理的 outbox receipt 可由 inbox 已驗證的完成回條提供本機歷史接收證據；若來源同 ID 再度成為 pending，明示衝突，不用舊完成檔把新 pending 隱藏。已超出所有保留窗的歷史無法還原，不能宣稱無限期去重或 exactly-once。

mutation 使用專用跨程序 FileLease，和 stdio owner lock 分開；busy 立即回報，不等待模型、不強停 owner。清理只選已完成、通過 schema／ID／ACK 對照的檔案；損壞檔案不自動當垃圾刪除。

## dispatcher 帳本

`dispatcher-attempts.json` 保存 active／不確定的 attempts。成功交付須所有 attempts 已終止、至少一次交付通過且 ACK 已核實，才以 passed=true 移到 `dispatcher-completed.json`。新紀錄在完成交付核對後保存 `ack_verified`；舊紀錄缺此欄位時須查原 inbox ACK。

人類／共用接收者可在 agent 失敗後明確 receive/query/ACK。同 ID 已合法 ACK，且各 capture 與 supervisor 子樹均證明退出，允許以 `completion=received_without_agent_proof` 歸檔；passed 仍 false，最多三份 attempt_refs 保留原 run/attempt 位置。這不是 agent 通路通過，不清每日用量、事件次數或 unknown-exit。缺樹退出證據仍保留 active；若 inbox 完成證據已先輪替而無法重證 ACK，也保持 active／明確容量背壓，不能以核心 receipt 存在就猜成功。

先原子保存 compact archive，再改寫 active；若兩步間失敗，重跑仍讀得到原 active，重複壓縮同 ID 不增加嘗試。archive 只有已完成摘要，可依 TTL／count／byte 輪替；pending、未知退出與未 ACK 失敗嘗試不受影響。開始 child 前預留 terminal update 的 byte 大小，不以子程序已啟動後才發現無法寫帳本。

idle 只 poll 佇列；維護在啟動／有候選事件時執行，archive 未改變時不反覆 fsync。這不是長時 CPU／RAM 保證，仍待 soak 量測。

## 證據與容量界線

- 本輪保存的五個 probe：outbox count／bytes、inbox count／bytes、dispatcher ledger；`reports/phase4-capacity-001/probe/manifest.json` 包含產生／接受／ACK／恢復 ID、前後 pending hashes、真 SQLite receipt／實際回傳及缺漏核對，資料庫與完成檔一併保留。
- 帳本 probe 的 child exit／交付通過欄位是明示 synthetic fixture；沒有啟動 child／模型，不能稱真 agent 接收。其餘為真本機 SQLite／檔案操作的 synthetic 事件，沒有 provider 採集。
- 新測試另外涵蓋 64 KiB 下 100 次循環、TTL、同 ID ACK、跨 opener 政策、未 ACK failed 保留、FileLease busy、完成檔與 archive 寫入失敗／中斷恢復。完整結果見本輪 verified 目錄。
- receipt／completed／archive 的去重都是有限時間及容量窗；更舊歷史不保證仍可查證。壓力輪替 receipt 會計數並保留最近回條，不冒充永久去重。
- byte cap 是主檔／狀態檔的邏輯位元組。SQLite DELETE journal、原子替換暫存、檔案系統配置／目錄開銷另計。沒有全磁碟容量保證；真寫入失敗仍明示保留 pending。
- 完整 capture／CLI JSONL／既有 reports 不在本次清理範圍，未刪除或上傳。dispatcher mutable 帳本有界不代表所有歷史驗收資料有界；soak 計畫另限制測試 reports 總量。
- 同使用者可篡改 SQLite／JSON 的既有限制仍在；不是簽章、不可變鑑識或安全結論。沒有 24 小時、主機重啟或新真模型驗收證據。
