# 24 小時 soak 計畫（尚未執行）

## 2026-10-26：自身 worker 的長窗 idle 已驗證（最新）

`reports/soak-idle-30m-20261026-01` 原收據起訖為 UTC 2026-10-25 17:12:21.291029–17:44:01.298238，等於台北 2026-10-26 01:12:21.291029–01:44:01.298238+08:00（2026-10-27 依原收據補正時區，未重跑）。實跑1900.017392秒，16件synthetic事件全部唯一ACK、pending0；475筆有效資源樣本，原HANDLE自然exit0／Job0／無強停、7個來源檔hash不變。獨立32/32核對的末段實際1802.489810秒窗：CPU0.343275%單核心、private峰增73728B（72KiB）、handle增0，符合這個自身idle窗的三項目標。沒有插值冒充恰1800秒。

此切片僅排空後的foreground synthetic worker；不是整Job、production monitor、steady四窗趨勢、OS重啟、真agent或下方完整24h背景流程。採樣間隔3.8671875秒，完整idle_after1874.956124秒；短窗與長窗不是控制host負載的因果實驗。

observer每秒全樹usage的已量測成本，已改為排空後單writer的已驗其他檔總量＋自身append bytes；每筆仍guard、核對檔案大小及兩層byte cap，mutation／phase／final全樹核對保留。外部其他檔／同大小突變不是即時防篡改保證。詳見最新STATUS/EVIDENCE與measurement-crosscheck.json；下方舊短窗未達標是保留歷史，不是這輪結果。

## 2026-10-26 已執行的有限增量（不等於本頁24h計畫通過）

scripts/soak.py 已能以專用reports執行有界synthetic恢復流程。--duration-seconds是上限，--min-wall-seconds是獨立最小總wall，--pacing-seconds是ACK間合作等待；總wall包含工作時間，不能當成同長idle。啟動後異常先耐久stop.request再grace/自有Job，未知或保存失敗維持未確認。

只從本worker GetCurrentProcess pseudo-HANDLE取 CPU／private bytes／working set／handles，未知=null，JSONL有byte/sample cap。兩輪60秒總wall／16ACK／pending0皆自然退出；獨立集合/SQL/hash/原HANDLE核對及有效59樣本保存於reports/soak-measured-20261026-01/-02。未量整Job、OS重啟或24h。

短窗idle CPU 4.393%／4.069%單核心，尚未達<1%目標；輪詢20Hz→4Hz未消除此成本，不能繼續盲調參洗綠。下一步profiling只診斷本harness的observer overhead。30分鐘idle、工作窗趨勢、完整24h及下方背景host流程仍未執行；保存的harness proof不能當成真agent或正式主機驗收。


Phase 4 先提交計畫；尚未執行完整24小時。使用者後續已授權一般權限背景監看實作與驗證，見 [背景契約](BACKGROUND.md)；這不等於24小時、實際登入排程、模型、提權、狀態注入或登出／重開機已通過。完整 soak 仍須先固定開始時間、隔離目錄與範圍，使用既有 Python 3.13 標準庫及本工具 Job。

## 範圍與隔離

- 全新 `reports/soak-NEW/source`，只放 synthetic 事件與 fixture 設定，不沿用正式 data、Codex home 或既有證據。
- consumer 以 QueueInbox 的 receive/query/ACK 操作，明示 synthetic harness，不能宣稱 agent 收到。dispatcher 帳本只使用已標示的合成退出／交付 fixture，不啟動 CLI 或模型。
- 使用同一背景 start/status/stop/serve 控制及保留策略；至少跨午夜，確認每日 agent 額度／日期不停止 Monitor。測試 guardian 約束的有限 host 不冒充獨立常駐；不得用 breakaway 逃離外部 Job。
- 以提交碼與 source hashes 固定版本；保存 Python／Windows 版本、政策設定、起訖 UTC／monotonic 時間、manifest、容量錯誤、ACK 與每個 Job 的退出回條。
- 不讀取系統其他程序或完整命令列；只測試本工具程序／其 Job 的 CPU、RAM、handle。OS provider 長時採集另屬未執行的實機驗證範圍。

## 預算與負載

總上限 24 小時；一般每 30 秒生成 1 件，最多 2,880 件；壓力階段改成同樣總量內的有界批次。每件先把 ID／hash／sequence 耐久寫入 producer manifest，入列被拒絕則保留 producer 待重試，不改 ID、不把未接受事件算作已入列。只使用公開合成 enum／數值／ID。

縮小容量以在有限負載下反覆輪替：outbox 32 件／256 KiB；inbox 16 active／16 completed／256 KiB；dispatcher 8 active／8 completed／128 KiB。ACKed payload 保留與完成回條 TTL 用測試設定另行記錄；accelerated clock 測試與真實 24 小時時間分開。每個 JSON／SQLite 主檔都有上限；journal 與原子替換暫存另計，整輪 reports 預算 64 MiB。不能以清理 pending 換取達標。

| 時段 | 負載／故障 | 必須觀測 |
| --- | --- | --- |
| 0–1h | idle，無模型 | 等待程序的資源基準、heartbeat；零接收／ACK |
| 1–4h | 穩定產生及 synthetic ACK | ID 集合一致、無重複結案、完成資料輪替 |
| 4–5h | 暫停 consumer，填滿 outbox／inbox；producer 保留被拒事件 | 明確容量錯誤，pending payload/hash 不變；恢復後補收同 ID |
| 5–12h | 穩定交付，分別填滿帳本及 byte cap | 未確認 child／失敗交付不被輪替；完成證據保存後才能恢復 |
| 12–13h | 專用測試檔案寫入／fsync／replace 故障 fixture | 交易回滾、原資料保留；解除故障後恢復，不改權限或真磁碟 |
| 13–23h | steady＋定時合作停止／重新開啟本工具 | 同 ID／query、ACK 去重、planned monitor_gap；不是主機重開機證據 |
| 23–24h | 停止 producer，排空可交付事件、正常收尾 | manifest／SQLite／inbox／帳本集合核對，Job active=0 |

## 每分鐘採樣

用標準庫 ctypes 對自己的 process handle 讀 `GetProcessTimes`、`GetProcessMemoryInfo`、`GetProcessHandleCount`，加 `time.monotonic()`；整個 Job 的 CPU／峰值另取 Job accounting，不能把 parent RAM 當全程序樹 RAM。記錄 private bytes、working set、handle 數、累積 CPU 秒及區間 CPU；采不到記 unknown，不填 0。

同時記錄 SQLite 主檔／journal／freelist／used pages 大小、outbox 各狀態數、receipt 數及輪替數；inbox active／completed／actual＋reserved bytes；dispatcher active／completed 與兩個檔案大小；producer 未入列清單與最老 pending 年齡。以 JSONL append，定時 flush/fsync；採樣錯誤只存固定原因碼。

## 通過與停止條件

- 任一時間：所有未 ACK 的 pending／retry／failed event ID 與 payload hash 都可在 outbox 或尚未接受的 producer 清單找到；已接受集合＝仍未 ACK＋唯一 ACK，交集為空。輪替後的完整 ACK 證據以本輪 harness manifest 保留，不要求產品無限保存歷史。
- 重收只能是同 event/query；唯一 ACK 集合與成功接收查證集合一致；額外／缺漏／非預期重複為空。每次滿載後至少有一次解除阻塞及後續新事件成功入列／ACK 的證據。
- 主檔與狀態上限不超政策；原子替換／SQLite DELETE journal 暫存另列峰值。每一輪 active 回落且 completed 輪替，不能只看最後筆數。
- idle 最後 30 分鐘 CPU 平均目標 <1%（以單核心比例）、private bytes 相對首個 idle 窗增幅 <32 MiB、handle 增幅 <20；steady 相同工作量窗不得連續四窗單調增加。這些是待測目標，不是現有效能保證；記錄主機背景負載的不確定性。
- 卡住、容量無法恢復、任何 accepted ID/hash 不見、紀錄超額或資源持續上升即停止新產生；合作停止後只清理本工具 Job，保留失敗證據，禁止刪除資料讓測試變綠。
- 每次停止先保存 disabled；以公開 serve 檢查沒有自動重新啟用，再明確 Start。同一 outbox／query ID 不重建。異常恢復另核對 monitor_gap、backoff、來源 freshness 與未知退出閘道，host heartbeat 不能代替成功採集。
- 增加接收器收尾故障窗：原ACK已提交但completed寫入失敗時，先施加TTL／count／byte清理，驗證原proof仍受pending_finalization保護；解除故障後同query收尾一次，後續新事件能接收。pin到達上限應回滾新ACK、保留pending，解除舊pin後恢復，不能靠刪資料通過。慢來源公平性另以虛擬時鐘故障fixture檢查，不把其虛擬秒數算入24小時。
- 最後保存所有子程序 exit code、`forcibly_terminated`、Job 剩餘數、scope 與未驗證項。未跑滿 24 小時只能報有限時長；主機登出／重開機與真 agent 仍不得升格為通過。
