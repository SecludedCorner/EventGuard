# EventGuard 開源開發參考庫

查閱日期：2026-11-01（台北）。用途是支持「偵測跡象 → 保存證據 → 授權喚醒 agent → 調查 → 驗證回條與處置」；以下借鏡方向是工程建議，不是第三方功能或 EventGuard 相容性驗收。

使用者指定本機保存位置：`D:\Github Project\Eventguard Reference`。本次選 14 份參考庫：12 份軟體專案、1 份開放偵測規則庫及 1 份公開 EVTX 參考資料庫。只下載 Git 版本控制內容與遞迴子模組，不安裝依賴、不執行第三方程式、不連設備、不啟動模型或 CI。

## 清單與閱讀順序

| 順序 | 官方專案 | EventGuard 可借鏡的具體部分 | 授權初查／界線 | 本機資料夾 |
| --- | --- | --- | --- | --- |
| 1 | [psutil](https://github.com/giampaolo/psutil) | Windows 程序建立時間、程序消失／拒讀分類；改善身分缺口，不把讀取失敗當安全。 | BSD-3-Clause | `giampaolo--psutil` |
| 2 | [osquery](https://github.com/osquery/osquery) | 系統狀態資料表、欄位契約與跨平台查詢；對照現有 collector 的 unknown／partial。 | Apache-2.0 OR GPL-2.0-only；依個別檔案 | `osquery--osquery` |
| 3 | [Fluent Bit](https://github.com/fluent/fluent-bit) | syslog／檔案解析、輸入與輸出分層、緩衝與背壓；供 NAS 接入與斷線恢復設計參考。 | Apache-2.0；第三方內容另核 | `fluent--fluent-bit` |
| 4 | [Sigma 規則](https://github.com/SigmaHQ/sigma) | logsource 前置、偵測條件、誤報與規則狀態；建立合成正反例，避免只有 severity 的斷言。 | Detection Rule License 1.1；是規則資料，不能當作 Apache／MIT 軟體 | `SigmaHQ--sigma` |
| 5 | [pySigma](https://github.com/SigmaHQ/pySigma) | 規則解析、轉換 pipeline、後端輸出與驗證錯誤分離；先比對 schema，不能直接保證規則語意相同。 | LGPL-2.1 | `SigmaHQ--pySigma` |
| 6 | [Hayabusa](https://github.com/Yamato-Security/hayabusa) | Windows 事件日誌、Sigma 映射與時間線輸出；借鏡保留來源欄位、時間與可見缺口。 | AGPL-3.0；rules 子模組另核 | `Yamato-Security--hayabusa` |
| 7 | [Velociraptor](https://github.com/Velocidex/velociraptor) | 調查任務生命週期、VQL、ACL 與證據收集；對照 EventGuard 的 receive/query/save/ACK、取消及資源預算。 | AGPL-3.0；個別第三方內容另核 | `Velocidex--velociraptor` |
| 8 | [Wazuh](https://github.com/wazuh/wazuh) | agent／manager 分層、解碼、偵測規則與來源健康狀態；研究架構，不在本機安裝服務。 | 混合：主要 GPLv2；engine AGPLv3+；部分 shared modules 雙授權，見 README | `wazuh--wazuh` |
| 9 | [Wazuh Dashboard Plugins](https://github.com/wazuh/wazuh-dashboard-plugins) | 安全事件、端點總覽及完整性監控的實際介面；借鏡總覽→篩選→詳情→上下文返回。 | GPL-2.0 家族，README 與具體檔案另核 | `wazuh--wazuh-dashboard-plugins` |
| 10 | [Timesketch](https://github.com/google/timesketch) | 調查時間線、查詢、標籤與註解資料模型；同時保留來源與推論，不能按時間接近就斷言攻擊鏈。 | Apache-2.0 | `google--timesketch` |
| 11 | [DFIR-IRIS](https://github.com/dfir-iris/iris-web) | 案件、人工處置、調查紀錄與證據分層；人工狀態仍須與 EventGuard agent ACK 分開。 | LGPL-3.0；backend／frontend 子模組各自核對 | `dfir-iris--iris-web` |
| 12 | [Chainsaw](https://github.com/WithSecureOpenSource/chainsaw) | Windows forensic artefact 搜尋、欄位映射及離線輸出測試；新版已取消 Sigma／EVTX 子模組，配套資料改獨立保存。 | GPL-3.0；獨立規則／資料庫各自授權 | `WithSecureOpenSource--chainsaw` |
| 13 | [Shuffle](https://github.com/Shuffle/Shuffle) | 自動化工作流程、執行狀態、輸入輸出及整合契約；可對照失敗處理，不自動取得敏感處置權限。 | 本體 AGPLv3；README 另列 MIT 模組，逐目錄核對 | `Shuffle--Shuffle` |
| 14 | [EVTX Attack Samples](https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES) | Chainsaw 官方推薦的 Windows 事件參考資料，供未來離線解析案例對照；包含輔助腳本，本次全部只保存，不執行或匯入監看。 | GPL-3.0；較舊的參考樣本，不代表目前完整威脅覆蓋 | `sbousseaden--EVTX-ATTACK-SAMPLES` |

授權表是官方根目錄／README 的識別，不是所有子模組或相依套件的統一授權。後續若要複用程式碼，先對具體檔案與版本核對條件；本次下載不新增 EventGuard 依賴或變更其授權。

## 選擇理由與未納入項目

- 優先補目前可驗證的缺口：來源身分與錯誤分類、NAS 日誌契約、可追溯調查與明確的工作流程狀態。
- [wazuh-dashboard](https://github.com/wazuh/wazuh-dashboard) 是 OpenSearch Dashboards 底座；本次優先下載較直接相關的安全應用 plugins，未把底座另列下載。
- Chainsaw 的 `.gitmodules` 留有舊 URL，但目前 HEAD 沒有對應 gitlink；實際 README 明示 v2 已移除子模組。Sigma 已在本清單獨立下載，EVTX 資料另列第 14 庫，不能用過時 `.gitmodules` 宣稱已自動下載。
- Chainsaw 使用目前官方 `WithSecureOpenSource/chainsaw`，不再使用會重導的舊組織名稱。
- 不把廠商專有 GUI、只有公開 SDK 的商業產品、一般 GitHub 高星清單當成可直接使用的開源 EDR。

## 下載與驗證範圍

每庫基本命令：`git clone --recurse-submodules --jobs=4 <官方HTTPS URL> <指定子目錄>`。不使用 depth、filter 或 single-branch；Git 長路徑選項僅限本次指令與新下載庫，未改全域或系統設定。下載子程序放入自有 Windows Job，保留退出回條。

「完整」在此指 Git 預設 clone 的完整歷史、遠端分支 refs、目前 checkout，以及目前 commit 綁定的遞迴子模組。Git 子模組按父庫指定 commit，不能自行更新至各子庫最新版。README 超連結、獨立 wiki、release 二進位與所有歷史 LFS payload 並不是 recurse-submodules 的內容；本次不宣稱網站鏡像或全站備份。

下載後記錄官方 remote、HEAD、非 shallow、遞迴子模組狀態、工作樹、頂層 Git 物件檢查、子模組連通性、目前 checkout 的 LFS 狀態與程序退出。任何未初始化／不符／衝突、不可用來源或 Windows checkout 限制都要保留，不刪檔或放寬 NTFS 保護假造成功。

本機 `selection.json` 保存官方 metadata；`download-manifest.json` 保存逐庫驗證；`_download-audit-20261101/` 保存實際命令、輸出與 Job 回條。第三方原始碼與這些執行產物不納入 EventGuard Git。下載驗收不是第三方 build／測試通過，也不代替 EventGuard 真 agent、真 DSM 或真實防守驗收。

## 接續開發方式

1. 每次選一個 EventGuard 實際缺口，先讀本清單對應的固定 SHA 與具體測試，記錄可採用／不適用的部分。
2. 先用現有 Python 標準函式庫與合成資料做最小切片，不因參考庫可下載就直接引入服務或套件。
3. 對未知、拒讀、時間偏差、重送、容量及取消保留失敗案例；不以參考產品的宣稱代替本專案證據。
4. 每單元本機 build／相關測試後 commit、普通 push 並整合 main；維持 500 行上限，不觸發 GitHub CI。

## 2026-11-01 實際下載結果

14份Git參考資料與269個遞迴子模組已保存；13份checkout完整。osquery本體及264個遞迴子模組的Git資料完整，但3個Linux子模組在Windows無法完整展開：libdevmapper、libudev有保留檔名，libiptables有大小寫重名；未把這3處工作樹差異偽裝成乾淨。完整歷史與父庫指定SHA另存於本機_windows-checkout-bundles，三份bundle皆驗證自包含且保存SHA256。

osquery原clone因深層metadata路徑過長失敗，保留原exit128；缺件改用_git短metadata目錄並固定父gitlink SHA，未刪檔、reset、force或關閉NTFS保護。419份自有Git Job回條已退出／無殘留，含5次保留的歷史失敗、0強停。兩個空checkout已正常補齊；現有Git/LFS證據按未改變的SHA沿用，不用重跑製造通過。

本機DOWNLOAD_STATUS.md及download-manifest.json列完整結果；_download-audit-20261101保存命令、錯誤與修復回條。請保留_git、bundle與原工作樹的完整目錄結構；搬移整體目錄時仍須核對gitdir指向。Git資料保存不代表3個子模組已在Windows成功checkout，也不代表第三方build／功能或EventGuard產品驗收。

| 參考庫 | 本次固定 HEAD | 遞迴子模組數 |
| --- | --- | --- |
| dfir-iris/iris-web | `37c5521ac009bd018a2fac7bc01d70735d130c6c` | 2 |
| fluent/fluent-bit | `ad9867358257123c34b529860fe984e92a69844c` | 0 |
| giampaolo/psutil | `c24bae0a977d31f79ac820f3d18cfb33e1465a32` | 0 |
| google/timesketch | `ea3d2ddabb91f096da596d0959adad5925a58446` | 0 |
| osquery/osquery | `99ea20493a2614eab939cbc02ebfaa114a3caecb` | 264 |
| sbousseaden/EVTX-ATTACK-SAMPLES | `4ceed2f4706daf601c212a8f91c113dd85349a2c` | 0 |
| Shuffle/Shuffle | `c439ab39ee3780d629219fa3cd0e08aec795cb3b` | 0 |
| SigmaHQ/pySigma | `2555624e3689e82824e7f2710397ae0c7c5adfd3` | 0 |
| SigmaHQ/sigma | `05d1031f537e830b76da53bae2400c5814c89165` | 0 |
| Velocidex/velociraptor | `61daa5f66b8bbaf946ab5d57dd8b087e07663762` | 1 |
| wazuh/wazuh | `59702124a367223acbead1f382a95a82b5381d78` | 1 |
| wazuh/wazuh-dashboard-plugins | `eacb9e361bd4bb90cf90e2902588823aba5d6d92` | 0 |
| WithSecureOpenSource/chainsaw | `b746255fa76a09be982f97ee973a9dea2c73bc60` | 0 |
| Yamato-Security/hayabusa | `6622a790d8ea3492dd15a9e08bfe174755c661cb` | 1 |
