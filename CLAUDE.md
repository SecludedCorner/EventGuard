# EventGuard 工作提醒

先讀 [AGENTS.md](AGENTS.md)，遵守專案界線、Continuous Execution Policy 及「Git checkpoint 與遠端保存」。

**每個邏輯單元立即 commit／push，不累積修改。** 先確認工作區乾淨；每次 commit 前 build 與相關測試必須通過，約 200 行以上先拆分。單一目的、指定路徑 stage，訊息採 `type(scope): summary`；禁止 `git add -A`、amend、force push、`--no-verify`。

每單元輸出 hash、message、相對父 commit 的變更行數，以及 `git status --short`／`git diff --shortstat` 的實際結果；完整規則、允許 type、遠端核對及失敗保存方式以 AGENTS.md「乾淨工作區與原子提交」為準。不要等整個專案完成才保存。

僅使用既有授權的 EventGuard 開發分支；保留他人修改，不提交 runtime／秘密，不 force push。恢復工作先核對 Git 與最新 STATUS／HANDOFF，歷史段落不能覆蓋最新人類授權。
