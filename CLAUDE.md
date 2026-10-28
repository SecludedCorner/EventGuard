# EventGuard 工作提醒

先讀 [AGENTS.md](AGENTS.md)，遵守專案界線、Continuous Execution Policy 及「Git checkpoint 與遠端保存」。

## 既有授權與不重複詢問（2026-10-29）

使用者已再次確認：既有存取權限適用本 EventGuard 專案範圍；相同範圍、相同操作不必重複請求授權。此節記錄目前授權，不自行擴大至其他專案或敏感操作。

- 可自主讀取與修改本專案程式、測試及工程文件，使用既有環境執行 fixture／合成測試、來源 build、隔離本機 Web 介面驗收與必要的有界修復。
- 已允許使用瀏覽器驗證本專案介面；不需再詢問是否允許開啟專用合成頁面、操作元件、鍵盤或縮放。執行仍須遵守既有程序管理及資料界線。
- 每個單元通過 build／相關測試並審查差異後，可指定檔案 stage、普通 commit／push 至 `origin/feat/local-codex-acceptance` 並核對遠端 SHA，不需逐次請示。
- 工具無法存取時，先記錄實際錯誤並有界修復，繼續其他可執行工作；不能把工具錯誤當成使用者未授權，也不能反覆要求已給過的同一授權。
- 使用者提供的畫面顯示內建瀏覽器控制已開啟；工具仍回報 `Local browser use is disabled in Work settings`。目前原因未確認，應記為設定畫面與工具狀態不一致，不斷言使用者關閉設定或工作區政策必然禁止。
- 既有授權不等於工具能力已恢復；瀏覽器驗收仍需實際執行證據。不得改設定檔或繞過平台限制來假造可用性。
- 下載依賴、新模型／原生掃描、系統／帳戶變更、長時間實機運行、重開機、敏感處置、推 main、tag／release、部署、刪分支及不可逆操作，仍依最新有效的具體授權；不得從本節推定新增權限。
- 私人圖片、截圖、秘密、runtime 與具體單次授權回條不得提交；本節僅保存專案操作規則，測試與執行回條留在忽略的 reports。

**每個邏輯單元立即 commit／push，不累積修改。** 先確認工作區乾淨；每次 commit 前 build 與相關測試必須通過，約 200 行以上先拆分。單一目的、指定路徑 stage，訊息採 `type(scope): summary`；禁止 `git add -A`、amend、force push、`--no-verify`。

每單元輸出 hash、message、相對父 commit 的變更行數，以及 `git status --short`／`git diff --shortstat` 的實際結果；完整規則、允許 type、遠端核對及失敗保存方式以 AGENTS.md「乾淨工作區與原子提交」為準。不要等整個專案完成才保存。

僅使用既有授權的 EventGuard 開發分支；保留他人修改，不提交 runtime／秘密，不 force push。恢復工作先核對 Git 與最新 STATUS／HANDOFF，歷史段落不能覆蓋最新人類授權。
