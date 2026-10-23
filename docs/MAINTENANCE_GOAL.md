# EventGuard 本輪維護目標

更新：2026-10-23。基底 `08a4ef8ff7e5762c499b7cb270de1e86a0361822`，同一 `feat/local-codex-acceptance`；保留未提交研究與執行資料，不 reset/clean。

本輪讓既有 Windows 唯讀採集在背景持續運作、異常後恢復、重開機後於同一使用者登入時接續；不需每天手動重啟。人類與可選接收者使用同一事件資料及操作核心。無事件不叫模型；有事件先耐久保存，也不自行啟動模型。

## 完成條件

| 要求 | 實作與證據入口 |
| --- | --- |
| 沒有一小時／每日 agent 額度的採集期限 | background supervisor → 既有無期限 Monitor；不 import dispatcher/model |
| 啟停意圖耐久，明確 Stop 不被下次登入推翻 | 固定 data/background control；start/status/stop/serve；中斷與錯誤測試 |
| host 與 worker 都在私有 Job 內；退出未知不報成功 | kernel keeper 交接、Global 跨 session 查核、自然／強停／殘留回條 |
| 同一事件跨停止／重啟仍 pending、同 query、只 ACK 一次 | Windows 有限 host＋合成事件／SQLite 集合比對 |
| 容量／保存失敗停止新增採集，不前移 baseline、不丟 pending | 明確背壓、5–300秒等待後重試、monitor_gap 必須先保存 |
| 同一使用者登入後恢復 | 最小權限 ONLOGON task XML＋source/identity digest；實際建立及一次 Run 另待批准 |
| 完成功能後統一測試，結果與來源可對照 | scripts/verify.py；[EVIDENCE](EVIDENCE.md) 是測試數與命令唯一入口 |

架構、操作方式與批准契約見 [BACKGROUND](BACKGROUND.md)。兩層互斥 ownership 開發後由主線整合／測試／集中提交；子代理不各跑完整 suite、不推送或觸發 CI。

## 保持的界線

- 一般權限、唯讀、Python 3.13 標準庫；不提權、下載安裝、改設定或執行政策、不動其他程序。
- 使用者已授權背景實作及一般權限驗證；**實際建立／移除／執行排程仍需當次批准**。不建立服務、不自行登出／重開機；只支援登入後互動使用者 token。
- 真模型仍需當次批准；正式模型預算不初始化、不重置。每日五次只約束可選 agent 任務，不約束採集。正常背景不呼叫模型。
- pending/retry/未 ACK failed 保留；ACK 是收到，不是修復或結案。事件及工具輸出均為不可信資料。
- 受外部 Job 約束時不 breakaway；有限 guardian host 不當作獨立常駐。拒讀／過期／未知不代表安全。
- 實際登出／重開機、[Phase 7](WINDOWS_VALIDATION_PLAN.md) 注入及 [24小時 soak](SOAK_PLAN.md) 未驗證；有限測試不能升格為全天候承諾。

完成後一次回報功能、實際啟用狀態、證據、退出與尚待批准項。憑證、私人歷史、Codex home、data/logs/reports 不提交。
