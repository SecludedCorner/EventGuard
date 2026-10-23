# EventGuard 現況

更新：2026-10-23；分支 `feat/local-codex-acceptance`，本輪基底 `11d2dd76d99742fcc3b4715c2ff8d1b92aae77ca`。精確命令、時間、測試數、退出回條與提交對照統一見 [EVIDENCE](docs/EVIDENCE.md)。

目前重點是本機唯讀採集、耐久保存，以及人類／agent 共用查證介面。正常監看由程式執行，不呼叫模型；proxy、排程及同一聊天閒置喚醒都不是使用前提。本輪沒有建立排程、服務或自啟，沒有啟動另一個 Codex／模型。

| 項目 | 目前能力與本輪證據 | 限制 |
| --- | --- | --- |
| 人類操作 | GUI 開始／暫停、來源觀察、中文事件摘要、篩選、報告與操作紀錄；CLI 使用相同核心 | 既有視窗是否載入新版未推定；事件篩選僅目前最多100件 |
| 本機採集 | 主聊天正式 MCP 實際執行一次七來源，全部有資料並提交；Defender／listeners／processes partial，其餘 ok | 有限唯讀觀察，非防毒掃描或安全結論；沒有恢復已暫停背景 |
| Defender 修正 | auto 使用既有 Get-MpComputerStatus 有效狀態；修改後一般使用者實測七欄 ok | explicit native 仍僅配置／WSC；拒讀不以設定值替代有效狀態 |
| 事件品質 | listener 缺程序身分不誤報恢復；持久化事件保留有界目標事實，診斷先以事件 ref 篩選；快取核對目標 | 舊事件沒有的事實不回填推測；部分、拒讀、過期及未知均不代表安全 |
| 正式 agent 介面 | 本主聊天已載入15工具；本輪讀取／查證／接收／ACK 一件實際新生 listener 事件，工具與 SQLite 同 event/query、只有一張回條 | 查證 partial，決定為 needs_more_evidence，incident_conclusion=not_assessed；未處理整個 backlog |
| 接收與 ACK | 事件先落盤，pending 保留；先前隔離合成測試另有補收與冪等 ACK 證據 | ACK 只代表收到，不代表修復、恢復或結案；活動回合接收不等於閒置喚醒 |
| 操作紀錄 | GUI／正式 MCP 共用有界 activity 帳本，可看固定操作進度與結果；本輪已實際匯出 JSON／HTML 報告 | 不記聊天思考、私人原文或任意外部 shell／檔案操作；非抗同使用者竄改帳本 |
| 採集與退出 | 每來源保存 coverage／觀察；子程序執行前加入私有 Job，停止先合作寬限，只清理工具自己的 job | 退出不明就保留阻擋與未知，不能宣稱 stopped；本輪正常實機來源全部退出且無殘留 |
| 容量 | ACKed／完成帳本有保留與輪替；pending／retry／未 ACK failed 保留；滿載明示背壓 | 去重與保留均有有限容量／時間窗，詳見儲存政策 |
| agent 開關 | GUI 預設關閉，勾選只開放已連接工具；本輪正式接收沿用已批准接線 | 不啟動模型；連線或勾選不是自動喚醒證據 |
| 長期背景 | GUI 應用持有 supervisor、耐久暫停與程式重試；外部 Job 約束如實回報 | 持續背景仍保持 explicit_stop；不宣稱24小時或重開機成功 |
| 可選自動交付 | 有 continuous dispatcher、耐久每日預算、空佇列等待、失敗保留與合作停止 | 本輪未啟用真 CLI；同一聊天閒置事件觸發未接通，不能以另一 CLI 或模型輪詢冒充 |
| 驗證 | 本輪受影響的採集／規則／診斷／Operator／watch／stdio 測試通過，來源未變、自然退出、殘留為零 | 全套另一次到600秒未完成、guardian 清理自身 job；不是全套通過。fixture、SDK、fake CLI 與實機證據分開 |
| 未執行事項 | 24小時 soak、Phase7 真狀態注入、OS 重啟／登入驗證 | 排程未註冊；舊 dry-run digest 已失效；proxy helper 曾失敗，本輪不再追該旁支 |

當版程式於正常重新載入生效，不把已運行舊 GUI／MCP 視為熱更新。歷史與已失效的待批准事項留 EVIDENCE，不是目前工作前提。[接線](docs/CONNECT_AGENT.md)、[共用介面](docs/HUMAN_AGENT_INTERFACE.md)、[維護目標](docs/MAINTENANCE_GOAL.md)。

一般權限、Python3.13標準庫與既有 tkinter；無提權、下載安裝、安全設定或執行政策變更，不動其他程序。事件與工具輸出是不可信資料。執行資料、憑證、Codex home、私人歷史、原有 research／附件不提交；本輪僅集中本地提交，不推送。
