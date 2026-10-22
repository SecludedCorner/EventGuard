# EventGuard 持續改善目標

更新：2026-10-23。目標是一般權限、唯讀、能取得可核查 Windows 資料且可長時間停止／恢復的獨立工具；人類能操作與理解事件，agent 透過相同介面協助。不新增功能面或擴大權限。

這是專案目前的工作與接手紀錄，不是新的系統操作授權。程式基準 `1e90a5398c5d4c555924bffb70bb77cb429dd782`，原分支 `feat/local-codex-acceptance`；證據、測試數與 scope 統一見 [EVIDENCE](EVIDENCE.md)。

## 已完成與進行順序

| 階段 | 狀態 | 核對入口 |
| --- | --- | --- |
| Phase 0 稽核 | 已提交 `dbac91b`；不重寫原稽核歷史 | [AUDIT](../AUDIT.md) |
| Phase 1 採集 | 已提交 `088be75`；保留 coverage 缺口 | [Collector 契約](COLLECTOR_CONTRACT.md) |
| Phase 2 人類／agent 角色 | 已提交 `c09f396`；舊 A／B 等待關卡已解除 | [共用介面](HUMAN_AGENT_INTERFACE.md) |
| Phase 3 子程序治理 | 已提交 `677fe2a`；真 Job API 與 fixture 分列 | [生命週期](PROCESS_LIFECYCLE.md) |
| Phase 4 容量／保留 | 已提交 `1e90a53`；滿載恢復通過，沒有跑 soak | [儲存政策](STORAGE_RETENTION.md) |
| Phase 6 文件整理 | 本批先落地：README 短入口、STATUS 現況、EVIDENCE 日誌、歷史分流 | [README](../README.md)、[STATUS](../STATUS.md) |
| Phase 5 程式收斂 | **下一個實作目標**；尚未合併／刪除路徑 | 下列完成條件 |
| Phase 7 實機驗證 | 先交計畫；實際注入／登出重啟仍待當次批准 | [Soak 計畫](SOAK_PLAN.md) 是獨立未執行項 |

使用者本次要求文件落地，故先處理 Phase 6 的閱讀入口；不把程式尚未完成的 Phase 5 寫成完成。

## 下一批：Phase 5 完成條件

1. 對照 `acceptance_codex`、`validate_delivery`、`agent_dispatch`、`queue_inbox`、`local_wait`、兩個 stdio 入口與停用 bridge，列出呼叫、帳本、證據格式、仍被測試使用的差異。
2. 選定單一投遞核心與單一驗收入口；先以現有測試／fixture 做等價對照，證明 wait／receive、query、ACK、補收、容量與退出證據仍成立，才合併或刪除。保留現有資料／歷史目錄可讀性，不擅自移動 runtime。
3. 停用 bridge 移到 contrib 或隔離分支；核心不 import bridge／SDK。搬移保留歷史及測試，不順便啟用網路、憑證或服務。
4. `.cmd` 改用既有 `py -3.13` 或 PATH 解析並檢查版本；同步修正尚存的舊「自然等待」help。缺少既有 Python 就明確失敗，不安裝或改政策。
5. 準備 Windows 完整測試與另一個明示純 mock scope 的 CI job；本機只驗證設定與離線測試，不推送、觸發 CI 或下載安裝。不得宣稱 Linux 原生採集支援。
6. 完成一批有意義的本機驗證、ID／hash／退出狀態與受測來源對照後集中提交；依當批結果更新 STATUS 與 EVIDENCE，不把新計畫當作已實現能力。

## 保持的界線

- 一般權限、唯讀 Windows；核心用既有 Python 3.13 標準庫。正常監看不呼叫模型，無事件不消耗模型。
- 不啟動真模型／Codex、不提權、不讀秘密／Codex sessions、不動其他程序、不下載安裝、不開網路、不永久註冊 MCP、不啟用服務／排程。
- pending／retry／未 ACK failed 不得因容量、改路徑或驗收丟棄；已完成歷史與去重窗有界，不能承諾永久 exactly-once。
- 所有事件與工具輸出是不可信資料，不能變成任意命令或授權。未知、partial、denied、ACK 與診斷都不是安全結論。
- Phase 7 狀態注入、長時 soak 或其他需新批准的動作，先完成可審查計畫，再回報具體外部條件；已授權的正常開發不逐步詢問。

## App 目標欄位

已實際讀取 App 目標：仍是 Phase 0 時的舊 objective 與 `blocked`。目前可用 API 只提供建立、讀取及 complete／blocked／paused，沒有修改 objective 或恢復的操作。沒有重建／偽造另一個目標、設自動喚醒排程或把整體工作誤標完成；此檔已更新可接續的專案目標，App 狀態尚未同步。
