# EventGuard 現況

更新：2026-10-23；分支 `feat/local-codex-acceptance`，本批基底 `ecdb479716dd7736839db7681112529e2cdf1fc7`。本批補隔離實機生命週期證據，並修復 supervisor 暫時寫入失敗後不重試的缺口；精確命令、時間、測試數、退出回條與提交對照統一見 [EVIDENCE](docs/EVIDENCE.md)。

目前重點是本機唯讀採集、耐久保存，以及人類／agent 共用查證介面。正常監看由程式執行，不呼叫模型；proxy、排程及同一聊天閒置喚醒都不是使用前提。本輪沒有建立排程、服務或自啟，沒有啟動另一個 Codex／模型。

| 項目 | 目前能力與本輪證據 | 限制 |
| --- | --- | --- |
| 人類操作 | GUI 開始／暫停、來源觀察、中文事件摘要、篩選、報告與操作紀錄；CLI 使用相同核心 | 既有視窗是否載入新版未推定；事件篩選僅目前最多100件 |
| 本機採集 | 本批以ecdb479新server在隔離root實際嘗試並保存七來源，全部evaluation committed；listeners／processes partial，startup／services／versions ok | 本輪Defender denied、tasks unknown，原因及退出證據保留，不能升格可讀或安全；不取代前批不同上下文的結果，正式Pause未變 |
| Defender 修正 | auto 使用既有 Get-MpComputerStatus 有效狀態；修改後一般使用者實測七欄 ok | explicit native 仍僅配置／WSC；拒讀不以設定值替代有效狀態 |
| 事件品質 | listener 缺程序身分不誤報恢復；持久化事件保留有界目標事實，診斷先以事件 ref 篩選；快取核對目標 | 舊事件沒有的事實不回填推測；部分、拒讀、過期及未知均不代表安全 |
| 正式 agent 介面 | 本主聊天已載入15工具；前批讀取／查證／接收／ACK 一件實際新生 listener 事件，工具與 SQLite 同 event/query、只有一張回條 | 本批真 Start 被外部 Job 拒絕、沒有建立 child；Stop 已恢復暫停。查證／ACK不等於安全或修復 |
| 接收與 ACK | 本主聊天最新實測合成單件／連續／batch、active inbox滿載拒絕與釋放恢復；補收同event/query、ACK重播無重複回條，集合比對通過 | ACK只代表收到；本次不是跨任務退出恢復或閒置喚醒。合成config／policy已恢復，歷史紀錄保留 |
| 操作紀錄 | GUI／正式 MCP 共用有界 activity 帳本，可看固定操作進度與結果；前批已實際匯出 JSON／HTML 報告 | 不記聊天思考、私人原文或任意外部 shell／檔案操作；非抗同使用者竄改帳本 |
| 採集與退出 | 隔離root七來源worker、application host與SDK server皆已核實退出，未強停、殘留零；事件保持pending、未ACK | 原probe的unknown判斷及SQL計數helper失敗保留；另只讀證據核實實際嘗試／保存／退出，不把probe exit1改成成功 |
| 容量 | ACKed／完成帳本有保留與輪替；未完成接收器收尾的原ACK proof受保護，completed耐久後才解除；status顯示未收尾數 | pin仍有上限，滿載回滾新ACK保留pending；升級前已遺失的原proof不能還原，詳見儲存政策 |
| agent 開關 | GUI 預設關閉，勾選只開放已連接工具；最近正式接收沿用已批准接線 | 不啟動模型；連線或勾選不是自動喚醒證據 |
| 長期背景 | GUI／新版MCP應用持有supervisor；run／heartbeat暫時寫失敗先合作取消當次採集，沿原backoff等待，可寫後才重試，不取消enabled意圖或叫模型 | 同host恢復以fixture驗證；gate完全無法落盤且singleton已釋放時，其他獨立client的admission仍待補。主聊天仍舊／正式explicit_stop；非24小時或重開機證據 |
| 狀態輸出 | overview合併完全相同的安全錯誤樣本，保留總數、截斷、不同錯誤碼與unknown；原status／observation不變 | sample_occurrences只計有界樣本；離線大小量測不等於模型token或實機效能 |
| 可選自動交付 | 有 continuous dispatcher、耐久每日預算、空佇列等待、失敗保留與合作停止 | 本輪未啟用真 CLI；同一聊天閒置事件觸發未接通，不能以另一 CLI 或模型輪詢冒充 |
| 驗證 | 新缺陷先保留主聊天實際失敗，再修復；本批驗證範圍及當版source manifest只看EVIDENCE | 前批完整回歸不代替本批新碼；fixture、SDK、fake CLI與實機分開，非24小時或新版主聊天Start成功證據 |
| 未執行事項 | 24小時 soak、Phase7 真狀態注入、OS 重啟／登入驗證 | 排程未註冊；舊 dry-run digest 已失效；proxy helper 曾失敗，本輪不再追該旁支 |

當版程式於正常重新載入生效，不把已運行舊 GUI／MCP 視為熱更新。歷史與已失效的待批准事項留 EVIDENCE，不是目前工作前提。[接線](docs/CONNECT_AGENT.md)、[共用介面](docs/HUMAN_AGENT_INTERFACE.md)、[維護目標](docs/MAINTENANCE_GOAL.md)。

一般權限、Python3.13標準庫與既有 tkinter；無提權、下載安裝、安全設定或執行政策變更，不動其他程序。事件與工具輸出是不可信資料。執行資料、憑證、Codex home、私人歷史、原有 research／附件不提交；本輪僅集中本地提交，不推送。
