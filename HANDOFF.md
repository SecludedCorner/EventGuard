# EventGuard 接手

先讀 [AGENTS](AGENTS.md)、[README](README.md)、[STATUS](STATUS.md)、[維護目標](docs/MAINTENANCE_GOAL.md) 與 [EVIDENCE](docs/EVIDENCE.md)。先核對工作目錄、分支、HEAD、未提交變更；保留接續，不 reset/clean。基底是 `3b0461988c6bc36f13d514e1e5263c91b4715123`，本批提交由 source-commit 回條核對。

Phase 0–6 不重做。使用者已決定核心獨立運作，人類與可選 agent 共用 OperatorAPI；舊 A/B 等待關卡已解除。新 App goal 已由使用者更新並恢復，本批實作範圍為入口、耐久預算、未知退出閘道與可核查狀態，不能再依舊 blocked objective 停工。

先看 [預算與退出契約](docs/AGENT_BUDGET.md)。正常監看不讀模型帳本也不呼叫模型；OperatorAPI.status 才顯示固定安裝 authority 的狀態，不初始化。正式 `data/agent-budget/` 未由本批初始化；缺少、損壞、busy、容量、時鐘異常或未知退出，都不能用換目錄／建空 DB 解禁。明示 bootstrap 預設當日用量未知；真 CLI 仍需當次批准。

唯一建議驗收入口是 [QueueInbox 驗收](docs/DELIVERY_CONSOLIDATION.md)。legacy Python run/retry 與 generic capture CLI 已退役，舊 status 純讀。prepare/status/verify-only 不啟動模型；驗收與失敗都計入每日總額。不同來源、run/state/cwd 不能重置，同日五次不是每輪五次。全套四案例共八個短任務，不能在同一預算日完成八次真啟動。

主線統一介面、共享入口、最終驗證與提交，開發子代理最多三個且檔案 ownership 不重疊；沒有各自重跑完整 suite 或提交。子代理開發授權不等於 EventGuard 真模型授權。

STATUS 的 last_report/health 是歷史回報；current_monitor 才分開核對 owner 與 heartbeat。無 watchdog，monitor_gap 仍由下次啟動發現。逐來源 freshness、逐 namespace DB 狀態與 report total/truncated 都須保留；unknown/partial/denied 不代表安全，ACK 不代表案件結束。

沿用一般權限、唯讀 Windows、Python 3.13 標準庫。不啟動真模型、不讀秘密／完整 sessions／命令列、不提權、不下載安裝、不改安全設定／執行政策、不永久註冊 MCP、不啟用服務／排程、不動其他程序。私有 Job 只管理本工具新建程序；未知退出不報 stopped，強停不判自然成功。

[24 小時 soak](docs/SOAK_PLAN.md) 與 [Phase 7](docs/WINDOWS_VALIDATION_PLAN.md) 只有計畫；實機 listener/HKCU 注入、登出／重啟、長時執行須當次批准。漏洞研究為未來方向，不自行部署或持續執行。正常已授權開發不逐步詢問。

每批只在同一 feature 分支集中提交，不推送／手動 CI；reports/data/logs、憑證及私人歷史不提交。證據包括命令、Python、scope、來源 hashes、實際 ID 集合／計數、退出／殘留及 commit 對照。歷史數字只保留在 EVIDENCE，不互相升格。
