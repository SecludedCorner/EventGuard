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

## NAS-002來源確認與候選CSV解析（2026-10-30）

與NAS聊天依既有紀錄協作；沒有重新連設備或取新log。來源確認如下：

| 來源 | 既有依據 | 尚未確認 |
| --- | --- | --- |
| DSM | Log Center UI曾見時間／服務／結果／帳戶／來源類別 | 無實際CSV／HTML／syslog樣本、標頭、語系、時區與record ID模板 |
| SSH | 既有auth.log讀取被拒 | 無可解析樣本／格式；不提權補讀 |
| WebStation | 已知有套件 | 各站access/error格式、來源與轉送映射未知 |
| EBG15 | 官方手冊有System Log等頁 | 本機韌體遠送／匯出格式未知 |

[官方Log Sending](https://kb.synology.com/en-us/DSM/help/LogCenter/logcenter_client?version=6)說明RFC3164／5424選項，不定義DSM登入payload；[EBG15手冊](https://dlcdnets.asus.com/pub/ASUS/wireless/EBG15/E23348_ExpertWiFi_EBG15_UM_WEB.pdf?model=EBG15)亦不能證明本機遠送已接通。無真模板時不猜欄位或標DSM-compatible。

`nas_csv.parse_fixture_csv(raw, context, profile='nas-csv-fixture-v1')`只處理本專案定義的合成候選交換格式：UTF-8（可BOM），固定CSV標頭`record_ref,subject_ref,event_time,outcome,evidence_ref`。context必含synthetic=True、已綁source、received_at與clock_uncertainty_seconds；CSV不可覆寫設備身分。空subject/time表示未知；缺record或無時區日期拒絕。不用時間分桶／內容雜湊冒充穩定紀錄ID。

輸入上限64KiB／256列／單列1024字元；支援CSV引號，未知標頭／非法編碼／形狀／語法錯誤使用固定碼。有效列仍保留，語法截斷後不猜測剩餘列；input_complete僅代表CSV已讀完，不代表無errors、來源完整或健康。證據hash綁UTC正規化後的最小化欄位投影，不是原始log bytes。下游需另核去重／衝突與coverage。

隱私範圍：目前只用全合成fixture，無真樣本批准／收集。真實樣本若日後另行批准，帳戶／來源IP等須在受控邊界先去識別，EventGuard只接opaque參照、不接HMAC secret。原文、cookie/token/session、hostname、query/body/path與無關私人內容不落盤／回傳／上模型；來源／時間窗／目的地／保留期限與刪除方式須另定，不默認30天。解析器不保證Python記憶體安全抹除，不提供真資料入口或檔案讀寫。

## NAS-002批次核對與coverage接線

`nas_csv_import.inspect_fixture_csv(raw, context, profile=..., now=..., max_age_seconds=..., coverage=None)`在記憶體中呼叫候選解析器後，按已驗dedup_key分組。相同內容選擇確定性代表並計duplicate_rows；同key不同content_hash整群排除、計identity_conflict_rows，其他有效紀錄保留，不first-wins。錯誤計數是解析器固定分類，不冒充上游遺失數。

parser_status、transport_coverage及總status分開：CSV讀完仍可有errors／partial事件；缺transport coverage時heartbeat／last_success／parse_errors／dropped全部未知，不由匯入時間或列數補0。提供的coverage須與device/source/epoch/service/trust完全相同，窗口須涵蓋本次received_at；不符來源拒絕，不涵蓋窗口／時間矛盾／截斷為unknown。任一明確部分失敗至少partial，unknown優先；原transport計數不被本批parser錯誤覆寫，兩者分別保留。

驗證：`py -3.13 -B scripts/verify.py --run-dir reports/verify-nas-import-NEW --timeout-seconds 90 --module test_nas_csv_import --module test_nas_csv --module test_nas_contract --module test_nas_coverage`。目前verify-nas-csv-import-20261030-01為17/17／0skip、347語法／來源編譯，含CSV→正規化→衝突核對→coverage離線整合。

NAS-002已完成來源／隱私協作確認與可離線的候選CSV解析／批次測試；實際DSM export及SSH/WebStation/EBG15的adapter／相容性仍待去識別樣本、語系、時間與record identity定義。不是已完成真樣本取證或設備接線；未建立receiver、原文保存、HMAC秘密或模型路徑。
