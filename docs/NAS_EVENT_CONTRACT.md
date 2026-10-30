# NAS-001 離線合成事件與來源契約

本契約只驗證已結構化的自有fixture，不是DSM原始log解析器、syslog receiver、live事件接線或現場防護。沒有I/O、網路、模型或處置；不更改核心event 2.0的隱私白名單。

- `events.nas_contract.normalize`接受嚴格欄位的`nas-security-fixture-v1`，只准`synthetic=True`與DSM登入`success`／`failure`。缺少必要欄位拒絕；明確未知event_time／subject_ref／clock uncertainty可用null並產生gap。
- source含device_ref、source_ref、epoch_ref、service、trust；參照皆64位小寫hex，trust固定unverified。service可描述dsm／ssh／website／router，但此版登入事件只接受dsm；其他service僅可表達coverage來源。epoch必須在來源重啟／紀錄ID重用時區分，並非本模組自動發現的身分。
- record_ref表示來源epoch內唯一紀錄；subject_ref僅匿名參照。evidence_ref與evidence_sha256只做格式與內容綁定，不讀檔／核實原始證據，不證明來源真實。禁止將真NAS資料偽標synthetic。
- event_time與received_at要求有時區並正規化UTC，保留原offset秒數；received_at不可未知。clock uncertainty是null或0–86400整數秒，bool／NaN拒絕；事件超前收件時間且超出誤差時標event_clock_ahead。欄位complete不是時間可信、來源可信或安全結論。
- dedup_key綁版本／source（含epoch）／record_ref，不依到達次序或時間字串offset；content_hash綁正規化事件內容，排除received_at與原offset。`reconcile`最多256筆、同key不同content拒絕，不吞同秒不同record；重複選最早收件，平手採確定性內容排序。輸出依key排序，不代表事件發生先後或攻擊鏈。
- 原始message、帳戶名稱、密碼、token、request body／query string、私人路徑及任何額外欄位拒絕；不把它們藏進其他欄位。惡意log文字不會被解譯為命令或授權。

`events.nas_coverage.assess`接受`nas-source-fixture-v1`，同樣只准synthetic與unverified source，回傳一次snapshot的純評估，不寫入歷史或自動合併跨設備資料。

- window_start／observed_at限定計數區間與來源epoch；parse_errors／dropped是區間計數，null不等於0，整數上限2^31−1。缺窗口／計數即unknown；接收器未實作，不能聲稱已量測全部漏件。
- heartbeat_at與last_success_at分別保留並計算fresh／stale／unknown；時間依傳入now判斷，max_age_seconds為1–86400整數。這是collector時間新鮮度，不驗證NAS事件時鐘。
- 新鮮心跳不能蓋過parse_errors／dropped／truncated／interrupted／storage_error；disk_full、write_failed、unavailable等固定分類形成partial。缺值、過期、未來時間或窗口錯序為unknown；unknown優先於partial，全部gap保留。
- 歷史last_success不因目前失敗改寫；ok僅代表這份synthetic snapshot未報缺口，不代表有完整真日誌或主機安全。輸出固定incident_conclusion=not_assessed、allowed_actions=[]。

驗證入口：`py -3.13 -B scripts/verify.py --run-dir reports/verify-nas-NEW --timeout-seconds 90 --module test_nas_contract --module test_nas_coverage`。
現有證據：verify-nas-coverage-20261030-02，8/8／0skip、343語法／編譯；磁碟滿與中斷僅輸入fixture，未填滿磁碟或操作設備。

下一階段須另做格式adapter、實際來源註冊／身份驗證、受控收件及持久化／重啟／缺漏量測；取得明確設備／資料範圍前不連線。live NAS調查不在03合成模型包範圍，且新增src已使03原source綁定失效，須另備新範圍。
