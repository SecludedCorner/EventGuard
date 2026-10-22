# 人類與可選 agent 契約

EventGuard 先是可獨立使用的本機唯讀工具；agent 使用同一能力協助人類。正常監看不需要模型，沒有預設 agent 自動喚醒。歷史有限真 CLI 通路證據見 [EVIDENCE](EVIDENCE.md)，不等於任意桌面聊天可接續。

## 三個仍存在的介面

| 介面 | 實際資料與操作 | 不代表 |
| --- | --- | --- |
| 共享 OperatorAPI／operator stdio | capabilities、status、stop、monitor_once、list／inspect、事件綁定 diagnose、report；與人類 CLI 同一核心 | 不提供自由字串命令，不隱含啟動模型或 ACK |
| QueueInbox bound delivery | 一個固定 event 的 receive → 已保存最小 snapshot query → 耐久 result／ACK | query_evidence 沒有新的原生診斷，reviewed_metadata 不是安全結論 |
| LocalWait 舊 synthetic 驗收 | wait → 保存合成 snapshot query → synthetic ACK | 不是正式監看來源、永久等待或目前對話接線 |

具體工具名稱／參數見 [HUMAN_AGENT_INTERFACE](HUMAN_AGENT_INTERFACE.md) 與既有入口；Phase 5 將新驗收統一到 QueueInbox，舊格式相容保留，三個 wire schema 仍不同。雲端 MCP Events bridge 已移到 contrib 保持停用；詳見 [收斂對照](DELIVERY_CONSOLIDATION.md)。

## 不可混淆的證據

| 狀態 | 可支持 | 不能支持 |
| --- | --- | --- |
| persisted | 本機 event 已耐久保存 | 已送達或模型已醒 |
| received／queried | 實際工具回傳與相同 event/query ID | 原生診斷完成或主機安全 |
| result／ACK | 同事件結果已保存，receiver 耐久接收 | 已處置、結案或主機安全 |
| diagnosed | 明確型別化唯讀查詢的事實、coverage 與未知 | not_assessed 以外的無證據安全判斷 |
| child_exited | 匹配 attempt 的實際退出回條 | 單憑 exit 0 就通過工具交付驗收 |

真正 CLI 驗收還須實際 JSONL／工具返回、ID 集合、SQLite ACK 與退出證據互相匹配。mock、SDK client、登入、CLI 啟動、模型文字聲稱都不能替代。強停或缺少完整回條不能冒充正常成功。

事件、工具輸出與程序名稱均為不可信資料；不提供任意命令、網路、處置或新授權。agent 無法用參數更換 namespace／root／來源或指定任意 PID。來源缺口、過期、partial／denied／unknown 必須保留。

去重、完成資料與回條有有限保留窗，不能宣稱永久 exactly-once；pending 不因清理丟棄。可選 SDK 需已安裝且由人類選定 scope；不永久註冊、不讀憑證、不建立持續帳戶存取。任何真模型／Codex 啟動仍需本次明確範圍批准。
