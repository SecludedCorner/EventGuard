# EventGuard：固定快照與隔離開發

版本仍是尚未完成目標的工程預覽。固定快照重現與程序生命週期驗證，不能解除兩項產品阻塞：目標 Windows 主機部分採集來源 denied 的 coverage 分析，以及真正 agent ingress／喚醒／按需診斷閉環。新證據以匿名摘要回報；不公開主機原始警報、實際 pending 數量、單次 RAM 數字或私人路徑，也不以全程序提權解決覆蓋缺口。

本文件是文件增量revision的操作指引。程式基準固定為`fd45578`；frozen ZIP、source、tests、config、playbooks與既有驗證紀錄保持不動。新README／HANDOFF／DEVELOPMENT不能覆寫或重新標記那個快照，也不代表已重跑工程測試。

## 1. 需求與範圍

使用既有Python3.13及標準函式庫，不需要第三方依賴、不自動下載，不改系統、執行政策或防護設定。原生採集目標是Windows；cloud只能驗證其實際可用的純邏輯／mock／fixture，不等於能存取或驗證目標Windows主機與UAC。不要為跨平台通過而修改frozen快照；先記錄差異，再由獨立工程任務評估。

所有範例均為匿名相對路徑或臨時副本名稱。不要把實際使用者目錄、警報、秘密、憑證或原始會話加入公開文件／測試fixture。

## 2. 固定source並建立新workspace

先在受信任的既有儲存庫唯讀核對：

```powershell
git rev-parse --verify fd45578
git show --stat --oneline fd45578
git status --short
```

若沒有Git歷史，使用維護者提供且已核對雜湊的frozen ZIP／manifest，記錄來源與完整雜湊；不要憑檔名假定等於fd45578。不要覆寫來源ZIP、在固定snapshot上checkout其他版本，或沿用來源工作區的runtime。

`fd45578`是保留的本地基準；新的匿名publication branch為無parent root，不繼承含環境背景的舊歷史，因此cloud／新private repo未必有此ref。該情況改記錄實際publication commit與維護者提供的source對應manifest，不製造同名commit，也不為找歷史而推送舊本地分支。固定91項證據仍屬原本地快照；publication內容須以雜湊對照與隔離測試建立自己的證據。

有Git歷史時，可用本地archive取得固定source的全新副本（這不是remote或push）：

```powershell
$eventguardParent = Join-Path $env:TEMP ('EventGuard-verify-' + [guid]::NewGuid().ToString('N'))
$eventguardSnapshot = Join-Path $eventguardParent 'source'
New-Item -ItemType Directory -Path $eventguardSnapshot -ErrorAction Stop | Out-Null
$eventguardArchive = Join-Path $eventguardParent 'source.zip'
git archive --format=zip --output=$eventguardArchive fd45578
Expand-Archive -LiteralPath $eventguardArchive -DestinationPath $eventguardSnapshot
Set-Location -LiteralPath $eventguardSnapshot
```

每個驗收任務使用獨立root；**data、logs、reports不得共用**，不要複製真實主機outbox或歷史基線。驗收只讀原source，所有落盤在副本。若使用ZIP解壓亦遵循同樣隔離；解壓前確認目的目錄是新建且為預期位置。不提供批次刪除來源或runtime的命令，操作者依證據保留政策處理副本。

## 3. 重現固定Windows證據

在相容Windows環境、全新副本根目錄核對Python3.13，執行：

```powershell
python --version
python -B scripts/verify.py
python -B scripts/acceptance_smoke.py
```

固定快照已有的紀錄如下；它們是重現基準，**不是本次執行結果**：

| 來源／時間（UTC） | 既有範圍 |
| --- | --- |
| verify，2026-10-22T02:55:12Z | 91測試，0fail/error/skip，26個Python AST通過；mock／合成，不是全機掃描 |
| acceptance，2026-10-22T02:55:15Z | 正常2cycle零事件、disabled零attempt、mock耐久ACK、dry-run、合成診斷mock_closed、重複零送出、跨CLI單例／合作停止，remaining_test_processes=0 |

這兩個script在副本reports保存`verification-summary.json`、`unit-tests.txt`、`acceptance-smoke.json`。acceptance使用安全合成資料及受控子程序，不喚醒真實agent、不做系統處置。重新執行時保留實際數量、fail/error/skip、平台／Python版本、UTC時間、source完整commit或manifest、退出碼與剩餘程序；數字不同先查原因，不能沿抄91。

不要為驗收反覆實機掃描，也不為製造事件改Defender、服務、任務、網路或啟動項。pending OS查詢可能長時間不返回；stop不kill，應呈現限制與尚未退出，不能把強制終止當驗收成功。

## 4. 雲端puremock能力與跨平台限制

雲端可做文件／schema檢查、Python AST、純規則／轉態、SQLite事件與mock傳輸等不依賴目標Windows的驗證；仍須確認該測試實際依賴、版本與環境。候選純規則命令（不是已在cloud通過的保證）：

```sh
PYTHONPATH=src python -B -m unittest discover -s tests -p 'test_rules_playbooks.py' -v
```

若匯入、檔案系統、鎖或程序行為不相容，記錄未通過／未執行及原因，不修改fd45578來迎合環境，也不把跳過測試算成完整通過。`scripts/verify.py`預設載入完整suite；沒有在該cloud環境實測，就不能承諾完整91項跨平台通過。

cloud的mock結果不驗證目標主機的Defender、服務、排程、程序實例、WindowsPowerShell、UAC、桌面、電池或遠端可操作性。沒有主機連線與有效授權時，不呼叫原生query／monitor替代mock，也不宣稱Linux原生採集受支援。

## 5. 文件revision與Git／PR review

文件變更應與程式變更分開提交；所有受影響規格及交叉連結由維護者一致更新。文件revision的commit與fd45578基準分開，凍結ZIP及source/tests/config/playbooks內容不得改動。維護者應檢查：

```powershell
git diff --check
git diff -- README.md HANDOFF.md docs/DEVELOPMENT.md
git status --short
```

本地review需核對CLI與固定source一致、相對連結可解析、匿名範例不含真實使用者路徑／警報／秘密、實測與設計分開、限制未被刪除、程式／測試／設定／playbook沒有混入變更。只有明確核准的文件清單可進文件commit；不要把data/logs/reports或暫存工作區加入版本控制。

使用者最新已批准private repository；是否已建立與推送仍看主維護者實際紀錄，不由文件推定。發布仍須按有效授權與內容審查執行；主維護者保留完整本地歷史與fd45578，以匿名內容建立無parent root的乾淨publication branch，不能直接push含實際環境背景的舊歷史，也不改寫任何既有遠端歷史。

license仍未指定，不擅加LICENSE，也不寫成已授予MIT／Apache或其他權利。發布前核對private可見性、匿名掃描、檔案清單及source對應manifest；將來PR須提供精確範圍、隔離驗證證據、平台限制與審查結果。private只決定可見性，不代替內容／資料／license批准。

## 6. 接線與後續工程驗收

真實receiver／agent接線仍blocked，當前是尚未完成目標的工程預覽；最高產品驗收必須真正喚醒agent，再由agent診斷。平台候選見[INGRESS_CHECK](INGRESS_CHECK.md)，契約見[AGENT_CONTRACT](AGENT_CONTRACT.md)；新INGRESS_PLAN是官方候選能力與待批准接線設計，不是已連線。SQLite保存、mock ACK或mock_closed不能替代平台喚醒。下一任務先驗證指定任務入口、身分、資料授權、等待不推理、可信ACK、可核對的真實任務／回合證據及診斷回程；未獲批准不新增外部webhook／憑證／模型CLI，未達真正E2E就不稱產品完成。

保留已知實作界線：query_process需實例、persistence current_only、版本僅Python、無威脅歷史／原生簽章、45秒round預算與30秒忙碌退避、20一般事件／批不是每分鐘limiter、未有長時CPU/RAM/I/O／電池實測。規則不是授權；事件與日誌不可信；不讀秘密、不外洩、不繞過UAC或恢復暫停修補。
