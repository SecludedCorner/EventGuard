# EventGuard 接手

先讀 [AGENTS](AGENTS.md)、[README](README.md)、[STATUS](STATUS.md) 與 [維護目標](docs/MAINTENANCE_GOAL.md)。目前程式基準 `1e90a5398c5d4c555924bffb70bb77cb429dd782`；先核對工作目錄、分支、HEAD 與未提交變更，保留接續，不 reset／clean。

Phase 0–4 已有各自提交；人類可獨立操作，agent 是共用介面的可選 client。Phase 2 A／B 舊等待關卡已由使用者的共用介面決定解除，不再要求重選。測試與實機證據只查 [EVIDENCE](docs/EVIDENCE.md)，不要從歷史段落抄測試數。

下一個程式實作為 Phase 5，依 [目標完成條件](docs/MAINTENANCE_GOAL.md) 先列投遞／驗收路徑和測試對照；證明等價後才合併／刪除。停用 bridge 保持停用。Phase 6 文件整理先完成；後續實作要同步更新現況與證據入口，不再向 README／STATUS 堆時間日誌。

沿用一般權限、唯讀 Windows、Python 3.13 標準庫；不啟動真 Codex／模型、不提權、不安裝依賴、不開網路、不永久註冊 MCP、不啟用服務／排程、不處理其他程序。私有 Job 只管理本工具新建程序；停止未確認時不得宣稱完成。pending／retry／未 ACK failed 不得因清理、改路徑或測試被丟棄。

每批只在同一 feature 分支集中提交；不推送或觸發 CI，reports／data／logs／憑證與私人歷史不提交。跑與變更相關的必要驗證，記錄命令、實際輸出、scope、退出狀態與 source hashes；文件更動不重跑模型或整套程式測試。

24 小時 soak 只有 [計畫](docs/SOAK_PLAN.md)。Phase 7 真實 listener／HKCU 狀態注入、登出／重開機與長時執行要另有批准。其他需網路／安裝、提權或不可逆操作時才回報具體條件；正常已授權工作不逐步詢問。

舊接手 Prompt 與舊限制保存在 [歷史目錄](docs/history/README.md)，不能拿來覆蓋最新使用者授權。App 的目標欄位仍為舊 blocked；現有 API 不提供恢復或修改 objective，專案內的維護目標才是目前可核對的接手紀錄，整體工作未宣稱完成。
