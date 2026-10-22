# 本機開發與離線驗證

先核對 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`，保留既有變更；讀 [AGENTS](../AGENTS.md) 與 [維護目標](MAINTENANCE_GOAL.md)。現況以 [STATUS](../STATUS.md) 為準，測試數與 scope 只記在 [EVIDENCE](EVIDENCE.md)。

核心用既有 Python 3.13 標準庫，不自行下載安裝。Windows 是原生目標；可選 MCP SDK 需已安裝，缺少時停止該可選路徑。fixture、SDK、fake CLI、Windows API 與真 agent 證據分開，不因登入或啟動成功就判交付成功。

## 安全的預設驗證

README 的隔離 fixture 快速開始不查主機來源、不啟動模型，執行資料留 reports 的新子目錄。

程式變更完成一批後，使用本工具 guardian 驗證入口：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/verify-NEW --timeout-seconds 600
```

只用全新目錄，不覆寫前次失敗或成功證據。Windows 上測試 worker 與其程序樹受私有 Job 保護；逐測試比較既有 Job 成員 PID＋建立時間，收尾核對 active=0。額外 teardown、強停或缺回條不能把失敗改成通過。測試有明示的 synthetic hanging workers 與 fake CLI，不啟動真模型；原生版本 smoke 只讀固定 Python metadata。

保留 `source-manifest.json`、`unit-tests.txt`、`worker-summary.json`、`lifecycle-evidence.json`、`guardian-exit.json`、`verification-summary.json`。提交前後對照受測來源位元組，`source-commit.json` 綁定實際 commit；程式／測試有新變更才重新驗證。

文件變更檢查相對連結、現況／歷史分界與可執行快速開始，不重跑整套測試或模型。歷史快照只保留當時文字，完整測試數不可累加。

## 範圍

不改真 Defender／網路／啟動項來製造測試；不讀事件 Message／XML、完整命令列、登入憑證或 Codex sessions。測試與執行資料只放 data／logs／reports，不能提交。只清理已核實 ACKed 資料，保留所有未解決事件與失敗預算。

當前沒有 CI workflow；Phase 5 才整理 Windows 完整 job 與明示 mock 範圍的另一 job。不得把雲端 mock 通過當 Linux 原生採集支援，沒有本機完整證據也不宣稱遠端 CI 已通過。不得手動觸發或推送以執行 CI。

需要模型、網路下載／安裝、提權、排程啟用、Phase 7 注入或不可逆操作時回報外部條件；否則在既有範圍自主完成。舊固定快照／雲端接線開發說明保存在 [歷史目錄](history/README.md)，不是目前前置條件。
