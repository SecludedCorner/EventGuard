# Codex 桌面事件入口：有限驗收計畫

> 保存註（2026-10-28）：以下「目前／本輪／未提交」與政策均指原研究日期及固定基準，不是現行能力、授權或驗收。現況以 [STATUS](../../../STATUS.md) 與 [HANDOFF](../../../HANDOFF.md) 為準。本頁 reports 連結是「本機證據、不隨repo提供」；本次未讀取或上傳 reports 內容。

日期：2026-10-24，UTC+08。狀態：計畫。尚未執行。
本文件不授權呼叫模型、建立聊天或啟用背景。

## 需要回答的問題

`codex queue` 是否能讓已綁定的桌面聊天，從真正閒置狀態開始一個新回合？
不要把「命令成功排隊」當成「模型收到事件」。
也不要把另外開一個 CLI 任務當成原聊天被喚醒。

官方入口已存在，本機版本及 help 已核對。未送任何 queue 訊息。
官方對照：[CLI](https://learn.chatgpt.com/docs/cli/reference)、[app-server](https://learn.chatgpt.com/docs/app-server)。

## 明確範圍

- 使用者指定一個測試目的聊天 UUID。不能用名稱猜測或自動找最新 session。
- 只用一件公開合成事件。原事件先耐久保存。
- 初次至多一個自動啟動 attempt。不得在沒有診斷變化時反覆重送。
- 只傳固定 host 通知。事件 ID／內容不預填 prompt。資料由既有工具取得。
- 不讀原始 session、不探測私人 socket、不做 proxy、不改 MCP 或安全設定、不建立排程。
- 不收正式 backlog。原 dot 追蹤不變。

如果公開介面無法核對目的地，停止該候選。記為 `unverified_destination`。
不要因此要求放寬私人 session 或 proxy 權限。改評估自管任務路徑。

## 先完成的程式工作

這些是下一階段實作，不是本研究已完成的功能：

1. 普通 producer 先等待指定閒置窗口，再只產生一次合成事件。
2. 喚醒 adapter 只接受人類設定的目的 UUID 與固定 prompt。外部事件不能改它們。
3. 明確辨認「送到既有桌面後端」與「CLI 自己啟動另一個後端」。能力不能確認則阻擋。
4. 在送出前保存 admission、事件 hash、目的 binding 及 attempt。保存失敗不送。
5. queue 失敗或回覆遺失，保存 uncertain。先核對，不直接再送。
6. 接收端保持 receive → query → 保存結果 → ACK。不得直接寫 ACK 冒充模型工具執行。
7. 觀察真正 thread／turn、工具返回與來源 SQLite 回條。只保存必要 ID、時間及結果。
8. 將喚醒任務納入耐久預算。不得利用「不是專用 CLI」繞過每日上限。

現有 EventGuard authority 的啟動／退出驗證偏向自管 CLI 程序樹。
queue 的程序退出只證明送訊息工具結束，不能解除模型 turn 的 active admission。
新 adapter 需要 provider 級回合完成證據。不能把短暫 queue CLI 的 exit 0 充當模型自然退出。
若目前 authority 不能表達此證據，先完成相容設計及遷移測試，再作真驗。
不得刪帳本或初始化未知用量為零。既有 `budget_unavailable` 仍是待診斷狀態。

## 證據階段

| 階段 | 必要證據 | 不能代替的結果 |
| --- | --- | --- |
| 目的地 | 精確 UUID、已批准 scope、公開介面的後端身分對照 | 只有 UUID 字串或視窗標題 |
| 閒置 | 來源尚無事件、目的沒有活動回合；普通程式在等候 | agent 正在呼叫 wait 工具 |
| 事件保存 | 程式生成 ID、hash、時間及 SQLite pending | 手工貼事件 |
| 通知提交 | 一次 queue 呼叫、實際回傳及退出 | exit 0 當作模型啟動 |
| agent 啟動 | 指定 thread 的新 turn ID 與開始時間，起因可對照該通知 | 其他聊天出現文字 |
| 工具收件 | 真正 receive／query 返回，同 event/query，接收時間 | SDK 代收或 Python API 直接呼叫 |
| 結果與 ACK | 結果先落盤，再 ACK；唯一來源回條 | 模型文字自稱完成 |
| 結束 | 該 provider turn 已完成；另外核對本工具 sender 子程序退出 | 只看 sender PID 消失 |
| 再閒置 | 沒有新事件時無新增模型任務／請求 | 定時模型自稱無事 |

對專用 CLI 路徑，仍需既有自然 exit 0、child_exited=true、Job remaining=0 及無強停。
對桌面 turn，不應結束或強停整個 Codex 桌面程序。只核對目標回合完成。
兩種生命週期證據不可混用。

## 成功與失敗

成功需同時符合：

- 無人工後續訊息，事件才使精確目的聊天產生新回合。
- 生成、receive、query、結果與 ACK 的 ID 集合一致。
- 一個事件只有一個自動 attempt，重複投遞不新增模型任務。
- 無事件期間，adapter 發起的模型請求數為零。
- sender 自然退出；模型 turn 正常完成；沒有未知執行者或未說明背景程序。

以下都不得記為通過：

- 只排入 composer 或等使用者按送出。
- 只有 queue 收條，沒有新 turn。
- 送至新的 CLI／其他聊天，卻稱原聊天醒來。
- 必須持續跑模型去讀 MCP。
- 回條遺失後盲目重送，無法排除重複付費。
- 目的 thread、資料 scope、預算或退出仍未知。

若 queue 只支援排隊且不能滿足上述條件，保留原事件並記錄失敗條件。
OpenOctopus 自管 host 的方案仍可獨立實作。不能把單一路徑未通當成整類應用不可能。

## 授權與後續

本輪沒有執行此計畫。未建立或喚醒測試聊天。
真驗前須集中核定目的 UUID、一件事件、一個自動 attempt、資料範圍與預算。
先交付可審查的 sender／receiver 及預算變更，再作此批准。
若日後需要 ACK 前退出／恢復，再另計兩個有限任務，不混在初次成功內。
