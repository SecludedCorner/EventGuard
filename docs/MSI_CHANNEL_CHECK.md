# MSI：從 GitHub 驗證事件真的送達 Codex

本頁只驗證單一事件、連續／批次事件與 ACK 前失敗補收。雲端的模型端點目前被代理以 CONNECT 403 拒絕，未完成真通路驗收。MSI 測試使用本機既有的 Codex 登入，不需要發布雲端環境，也不帶入雲端 CODEX_HOME、憑證、runtime 或報告。

## 取得這次版本

目前內容位於 `feat/local-codex-acceptance`，不是 main。在新的普通目錄執行，保留舊 MVP 與既有未提交檔案：

```powershell
git clone --branch feat/local-codex-acceptance --single-branch https://github.com/SecludedCorner/EventGuard.git EventGuard-channel-check
cd EventGuard-channel-check
git rev-parse HEAD
python --version
python -c "import importlib.metadata; print(importlib.metadata.version('mcp'))"
codex --version
codex login status
$codexExe = (Get-Command codex).Source
$codexExe
```

若 PATH 另有原生入口，可用 `(Get-Command codex.exe -CommandType Application -ErrorAction Stop).Source` 定位，核對其版本與 `login status` 後再指定。若執行環境未選到原本登入的 home，只可在本次 PowerShell 程序指定既有正常目錄：`$env:CODEX_HOME = Join-Path $env:USERPROFILE '.codex'`；不建立新 home、不移植或讀取憑證內容，再以 `& $codexExe login status` 確認。這不是永久設定。

Codex 自身啟動仍可能需要對正常 home 的必要狀態檔作可寫開啟；`sqlite_home`／`log_dir` 覆寫不能保證在外層唯讀 sandbox 下初始化成功。遇 `in-process app-server ... Access denied (os error 5)` 時保留本次退出回條，依當次有效授權處理執行環境限制，不提權、不用 bypass、不搬移登入。CLI 自身也可能執行歷史索引；`--ephemeral` 只表示本次會話不持久化。操作者不讀既有 sessions，不將包含私人路徑的本次 stderr 或 CLI state 上傳。

Python 使用已安裝且能載入 MCP SDK 的 3.13；不自動下載。若 `$codexExe` 是 `.cmd`、`.bat` 或 `.ps1`，請把變數改為同一安裝中既有原生 `codex.exe` 的完整路徑。入口會拒絕 shell 包裝，不會為此改執行政策或安裝程式。缺少 Python／SDK／原生 CLI／既有登入時，先回報該項阻塞，不繼續啟動模型。目錄不能經 symlink／junction 或含 `..`。

若已經 clone，先保留本機修改，再 fetch 並切換這個分支；不使用 reset、clean 或強制覆寫。這次新增的檔案是 `scripts/validate_delivery.py` 與本頁，可靠重試及 capture 相關程式也在同一分支。

## A：先證明一個事件能收到

```powershell
python -B scripts/acceptance_codex.py run --run-dir reports/msi-single-001 --codex-executable $codexExe
```

此命令啟動一次真正 Codex；等本機工具進入等待後，由程式入列唯一合成事件。提示不包含該事件的 ID 或內容。Codex 必須實際 wait → query → ACK 同事件，不能用最後文字回覆代替。

只在 exit 0、`reports/msi-single-001/summary.json` 的 `passed=true` 且 `status.json` 的 `child_exited=true` 時繼續 B。其他情況先停止、保留證據，不反覆重試。狀態與合作停止：

```powershell
python -B scripts/acceptance_codex.py status --run-dir reports/msi-single-001
python -B scripts/acceptance_codex.py stop --run-dir reports/msi-single-001
```

stop 不 kill，active 工具／CLI 自然返回。若回 pending_child_exit，先等退出回條；不要另開重複任務。需要同事件手動重試時，依 [CODEX_ACCEPTANCE](CODEX_ACCEPTANCE.md) 使用 retry，最多三次 attempt，已 ACK 事件不能再次啟動模型。

## B：連續與批次事件

A 真正通過後再執行。每個命令都是一次有限的真 Codex 任務：

```powershell
python -B scripts/validate_delivery.py continuous --root reports/msi-continuous-001 --codex-executable $codexExe --execute
python -B scripts/validate_delivery.py batch --root reports/msi-batch-001 --codex-executable $codexExe --execute
```

continuous 產生 2 個事件；第二個只在第一個已耐久 ACK、且下一次工具等待開始後入列。batch 先將 3 個不同事件原子入列，再啟動 Codex。每個事件都要先 query／ACK，再收下一個；固定數量完成即退出，逾時／錯誤即停止，不空佇列 polling。

各自的 `validation.json` 必須 `passed=true`、`missing=[]`，並且 `generated`、`received`、`queried`、`acked`、`durable_acked` 的 ID 計數完全相同。不是只看 SQLite 中有幾筆。

## C：ACK 前退出，原事件能補收

```powershell
python -B scripts/validate_delivery.py recovery --root reports/msi-recovery-001 --codex-executable $codexExe --execute
```

先入列 1 個事件。第一個真正 Codex 任務只准 wait／query，沒有 ACK 工具，讀取後正常退出。程式確認原事件仍 pending、沒有 result／ACK，才啟動第二個真任務；第二個重新讀取同一 event ID／query ID 並 ACK。`validation.json` 必須 `passed=true` 且 `recovered_same_event_and_query=true`；第一階段證據在 `read-before-ack/pending-proof.json`。這驗證至少一次投遞與 ACK 後結案，不宣稱 exactly-once 或所有故障下絕不遺失。

A、兩種 B、C 合計啟動 5 個真 Codex 任務，各自可能含多次模型請求，使用既有帳戶額度。沒有事件時不循環開模型；這輪也不啟動正式 Windows 採集、常駐服務或 CI。

## 證據與限制

所有執行資料在忽略的 reports 下，每個案例用新目錄，禁止覆寫或共用正式 data/live。每次保存程式生成的 manifest、真 CLI JSONL、MCP 實際回傳、SQLite ACK 與自然退出回條。沒有 `--execute` 時只準備合成資料；`--verify-only` 只核對已有證據，不能拿 prepare 或 SDK 測試代替成功。

先回報 A／B／C 的 passed、missing 與合成 event ID；不要把帳戶憑證、Codex home、原始會話或完整環境 log 上傳 GitHub。若 A 失敗，回報固定錯誤類型與退出碼，先不跑 B／C。

2026-10-22 MSI 已以 Python 3.13.3／MCP SDK 1.6.0／既有 Codex 0.163.0-alpha.11.1 真正通過本頁 A／B1／B2／C：7 個唯一事件、8 次接收／query、7 次 ACK，缺漏與非預期重複為 0。第一輪初始化拒絕與第二輪工具批准失敗均保留，第三輪 A 成功後才執行 B/C；詳見 STATUS。本階段不承諾永久等待、接續任意桌面對話、Windows 原生採集、無限佇列容量或長期低負載達標。完整單事件排障見 [CODEX_ACCEPTANCE](CODEX_ACCEPTANCE.md)。
