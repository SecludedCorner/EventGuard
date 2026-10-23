# EventGuard 現況

更新：2026-10-23；分支 `feat/local-codex-acceptance`，本批基底 `3e3692507bceadbd7cd701b612396f7658cb6327`。本批修正正式 MCP 的應用持有監看生命週期；精確命令、時間、測試數、退出回條與提交對照統一見 [EVIDENCE](docs/EVIDENCE.md)。

目前重點是本機唯讀採集、耐久保存，以及人類／agent 共用查證介面。正常監看由程式執行，不呼叫模型；proxy、排程及同一聊天閒置喚醒都不是使用前提。本輪沒有建立排程、服務或自啟，沒有啟動另一個 Codex／模型。

| 項目 | 目前能力與本輪證據 | 限制 |
| --- | --- | --- |
| 人類操作 | GUI 開始／暫停、來源觀察、中文事件摘要、篩選、報告與操作紀錄；CLI 使用相同核心 | 既有視窗是否載入新版未推定；事件篩選僅目前最多100件 |
| 本機採集 | 前批主聊天正式 MCP 實際執行一次七來源，全部有資料並提交；Defender／listeners／processes partial，其餘 ok | 本批不重掃；有限唯讀觀察非安全結論，沒有恢復已暫停背景 |
| Defender 修正 | auto 使用既有 Get-MpComputerStatus 有效狀態；修改後一般使用者實測七欄 ok | explicit native 仍僅配置／WSC；拒讀不以設定值替代有效狀態 |
| 事件品質 | listener 缺程序身分不誤報恢復；持久化事件保留有界目標事實，診斷先以事件 ref 篩選；快取核對目標 | 舊事件沒有的事實不回填推測；部分、拒讀、過期及未知均不代表安全 |
| 正式 agent 介面 | 本主聊天已載入15工具；前批讀取／查證／接收／ACK 一件實際新生 listener 事件，工具與 SQLite 同 event/query、只有一張回條 | 本批真 Start 被外部 Job 拒絕、沒有建立 child；Stop 已恢復暫停。查證／ACK不等於安全或修復 |
| 接收與 ACK | 本主聊天最新實測合成單件／連續／batch、active inbox滿載拒絕與釋放恢復；補收同event/query、ACK重播無重複回條，集合比對通過 | ACK只代表收到；本次不是跨任務退出恢復或閒置喚醒。合成config／policy已恢復，歷史紀錄保留 |
| 操作紀錄 | GUI／正式 MCP 共用有界 activity 帳本，可看固定操作進度與結果；前批已實際匯出 JSON／HTML 報告 | 不記聊天思考、私人原文或任意外部 shell／檔案操作；非抗同使用者竄改帳本 |
| 採集與退出 | 每來源保存 coverage／觀察；子程序執行前加入私有 Job，停止先合作寬限，只清理工具自己的 job | 退出不明就保留阻擋與未知，不能宣稱 stopped；前批正常實機來源全部退出且無殘留，本批未掃機 |
| 容量 | ACKed／完成帳本有保留與輪替；未完成接收器收尾的原ACK proof受保護，completed耐久後才解除；status顯示未收尾數 | pin仍有上限，滿載回滾新ACK保留pending；升級前已遺失的原proof不能還原，詳見儲存政策 |
| agent 開關 | GUI 預設關閉，勾選只開放已連接工具；最近正式接收沿用已批准接線 | 不啟動模型；連線或勾選不是自動喚醒證據 |
| 長期背景 | GUI 應用持有 supervisor；新版 MCP Start 使用相同 application Job 核心，沒有固定採集期限或模型；EOF 僅停止自己新啟動的 host，固定有界回條保存退出證據 | 監看依賴持有應用／MCP server及祖先Job存活；不是獨立／重開機存活。本聊天 capabilities 仍舊，需正常重新載入；正式背景仍explicit_stop |
| 狀態輸出 | overview合併完全相同的安全錯誤樣本，保留總數、截斷、不同錯誤碼與unknown；原status／observation不變 | sample_occurrences只計有界樣本；離線大小量測不等於模型token或實機效能 |
| 可選自動交付 | 有 continuous dispatcher、耐久每日預算、空佇列等待、失敗保留與合作停止 | 本輪未啟用真 CLI；同一聊天閒置事件觸發未接通，不能以另一 CLI 或模型輪詢冒充 |
| 驗證 | 新缺陷先保留主聊天實際失敗，再修復；本批驗證範圍及當版source manifest只看EVIDENCE | 前批完整回歸不代替本批新碼；fixture、SDK、fake CLI與實機分開，非24小時或新版主聊天Start成功證據 |
| 未執行事項 | 24小時 soak、Phase7 真狀態注入、OS 重啟／登入驗證 | 排程未註冊；舊 dry-run digest 已失效；proxy helper 曾失敗，本輪不再追該旁支 |

當版程式於正常重新載入生效，不把已運行舊 GUI／MCP 視為熱更新。歷史與已失效的待批准事項留 EVIDENCE，不是目前工作前提。[接線](docs/CONNECT_AGENT.md)、[共用介面](docs/HUMAN_AGENT_INTERFACE.md)、[維護目標](docs/MAINTENANCE_GOAL.md)。

一般權限、Python3.13標準庫與既有 tkinter；無提權、下載安裝、安全設定或執行政策變更，不動其他程序。事件與工具輸出是不可信資料。執行資料、憑證、Codex home、私人歷史、原有 research／附件不提交；本輪僅集中本地提交，不推送。
