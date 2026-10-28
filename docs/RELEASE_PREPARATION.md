# 發布前準備

## 範圍與目前狀態（2026-10-28 已完成準備）

2026-10-28 使用者要求完成所有發布準備、連續接續，但不執行 release。本文件是本次唯一準備佇列；現況／證據沿用 STATUS、HANDOFF、EVIDENCE，不建立另一套產品目標。

候選使用既有 `feat/local-codex-acceptance`。它已包含 quota-test-migration、vulnerability-response-research、publication 的可分享成果；再合入公開 `origin/main` 的615f77f合併紀錄，沒有產品檔案衝突或差異。私人本機main／fd45578祖先保留，不接入公開歷史；其最終tree與公開root已核對相同。其他分支名稱、worktree與未追蹤圖片保留，沒有刪除授權。

| 工作 | 完成條件 | 狀態 |
| --- | --- | --- |
| PREP-1 分支整合 | 所有可分享分支是候選祖先；無語意衝突；私人歷史不可達 | DONE：公開main、handoff、quota、research、publication皆已包含；無衝突 |
| PREP-2 build／測試 | AST與完整guardian回歸；失敗保留後修正，原Job自然退出／remaining0 | DONE：修後完整02為1624/1624 executed，1621pass／3環境skip；216檔AST、精確SHA CI成功 |
| PREP-3 候選包 | 指定commit的source ZIP；逐檔hash／必要檔案／容量／路徑檢查；兩次build位元組一致 | DONE：b57b43b，316檔，兩份ZIP完全相同，兩個Git Job自然0／remaining0 |
| PREP-4 包內操作 | 解壓到新reports副本，以原Job執行合成CLI操作與保存／重開；無native／模型 | DONE：14/14，五個CLI Job自然0／remaining0，僅一件合成事件／一份調查／零ACK |
| PREP-5 保存與恢復 | changelog、未驗範圍、可回復程序、遠端SHA／CI及交付包hash均可核對 | DONE：反向patch恢復公開main tree，真index／checkout不變；changelog及本頁已保存於開發分支 |

這裡的「準備完成」不代表正式環境驗收全過；已知native partial與其他未驗事項必須隨包揭露，不能以測試數或打包成功取代。

## 本次交付與可核對結果

固定受測／打包候選為`b57b43be8333327584ef05af4e71740b5b80d621`，不是之後的純文件checkpoint。238個驗證來源檔案hash全數等於ZIP內該commit檔案；完整回歸來源未變，沒有用舊CI替代。候選相對公開main615f77f的差異是285檔、55340新增／1961刪除，屬已提交歷史合計，不是尚未保存的修改。

本機交付目錄為`reports/release-prep-candidate-20261028-02`，runtime／ZIP／回條不提交、不隨Git提供：

- `candidate.zip`與`reproducibility.zip`：316檔，SHA256均為`2d5ae6a55a24aebd344a630a53b61abc075cfb9af3b62664afb1d9582a8f62d5`。
- `release-manifest.json`／`package-result.json`：來源SHA、逐檔hash、版本0.1.0及兩個原Job退出回條。
- `source-binding.json`及完整回歸目錄的`source-commit.json`：238個受測來源與候選包相同，mismatches為空。
- `smoke-result.json`：14/14；發出、查列、保存調查、原重開與額外唯讀重開。DB仍一件pending、一份調查、零ACK，讀取前後hash相同，五個私有Job皆自然退出／無殘留／無強停。首輪輔助SQL誤用status欄位，已保留分類，改用delivery_status；未重複發事件或保存。
- `rollback-02/rollback-result.json`與`baseline-to-candidate.patch`：5/5；9個私有Git Job自然退出。以獨立index反向套用，tree精確等於公開main的`810eca95236e0e5955446e1689c0c6aca9fdfdc9`；未更動真index／checkout／refs。原演練的2MiB輔助輸出上限不足4.3MiB diff，失敗輸出保留；只把輔助上限改8MiB後完成。這不是runtime／資料庫還原驗收。
- `branch-integration.json`／`ci-result.json`／`ci-windows-summary.json`／`ci-fixture-summary.json`：祖先與遠端精確SHA、CI及skip分類；公開分支均包含，私人main祖先不可達，其他worktree不變。

完整命令`py -3.13 -B scripts/verify.py --run-dir reports/verify-release-preparation-full-20261028-02 --timeout-seconds 1800`於UTC05:43:35啟動guardian、05:50:36產生summary（台北13:43:35–13:50:36），worker419.655秒；1624run=expected1624、1621pass、0fail/error、3skip（兩項無symlink建立能力、一項notification icon不可用），stopped_early/stop_requested皆false，216檔AST無錯、原Job自然0／remaining0／無強停／逐測試殘留0。無native inventory/model。

[精確候選CI run40639767342](https://github.com/SecludedCorner/EventGuard/actions/runs/40639767342)為completed/success：Windows1624run／1577pass／47項既有可選SDK不可用skip；Linux fixture104/104，沒有Linux原生支援。沒有安裝依賴、手動dispatch或rerun。原完整01合作停止後的1533項部分結果與假綠保留並明示不接受；修worker及parent完整性閘道後才產生本次完整02。

本次修正包括四表count不能誤洗綠、owned launcher須解析既有完整git.exe、空suite／提前停止不能被驗證器判通過。正式發布仍有已知接受前置：native listener身分111缺列／21error仍partial，24h/reboot、既有桌面聊天喚醒及同環境競品比較未驗；真04歷史receive→query→保存→ACK證據沿用，這次沒有再啟模型或新native查詢。詳見[CHANGELOG](../CHANGELOG.md)與[最新證據](EVIDENCE.md)。

後續純文件checkpoint僅補記以上結果；固定包內是當時已提交的文件，最新本頁與changelog作為包外候選說明，不把文件補記冒充另一輪產品測試。準備完成後不憑持續執行政策擴大native／模型或發布授權。

## 可重現 source candidate

使用已安裝 Python 3.13 與 Git，不下載依賴、不產生安裝程式。先commit已審查的來源，再以完整40位SHA執行：

```powershell
py -3.13 -B scripts/package_candidate.py --root reports/release-prep-NEW --commit <FULL_CANDIDATE_SHA>
```

root必須是全新reports/release-prep-*目錄。兩個git archive都在執行前加入私有Job；每個30秒工作上限、2秒收尾寬限，保存原HANDLE退出／remaining／force。逾時、強停或退出不明皆失敗，不依PID／名稱停止其他程序。

產物是candidate.zip、第二次reproducibility.zip、release-manifest.json與package-result.json。ZIP內頂層為EventGuard，只含該commit的tracked檔案，不含.git歷史、data/logs/reports、local settings／憑證或附件。檢查固定commit comment、source version、必要入口／設定／playbook／MIT license、檔案數與大小上限；拒絕逃逸路徑、大小寫碰撞、Windows別名、symlink及私人檔案。ZIP最多16MiB、展開合計32MiB／1024 entries；hash清單保存在包外，不是簽章或無秘密的形式化保證。

source版本沿用0.1.0，正式tag尚未指定；檔案版本不等於已發布。MCP SDK不打包，不自行安裝。正常監看不呼叫模型；真agent、native診斷及系統變更仍各依原授權。

## 候選包驗證

只在全新reports內解壓經audit_archive通過的候選包。核對每個包內檔案SHA後，使用副本的CLI及合成事件測試發出／查閱／保存調查／重開，執行資料僅在這份副本。子程序均事先進私有Job，保存實際退出。這個smoke不是新的真agent或原生來源驗收。

完整回歸用既有入口：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/verify-release-preparation-full-NEW --timeout-seconds 1800
```

將source-manifest與實際candidate commit綁定。可選依賴／平台skip須列明，不能當實際執行。純文件結果補記不重跑未受影響的產品測試；普通push的既有CI依精確受測SHA核對，不以舊CI綠燈代替。

## 發布與恢復程序（本次不執行）

未來人類明確要求release後，先決定tag與changelog，重查遠端main與tag不存在，確認main是候選祖先、候選CI／包hash與來源都相同。若有新分歧或語意衝突，停止並回報。使用公開origin/main作基準，不能直接push保留私人祖先的本機main。可以把已批准候選SHA以fast-forward更新遠端main，並在同一SHA建立annotated tag；發布前再確認遠端支援與最終指令，不force、不改寫歷史。GitHub release／部署若需要另明確指定。

恢復保留目前遠端main基準615f77f及候選SHA、完整binary diff與hash。準備階段可用獨立臨時index反向套用該diff並核對所得tree等於基準，不改checkout或遠端。未來真回復用新revert commit與重新驗證，不reset／force。分支刪除須另列本地／遠端清單並等使用者確認。

## 連續接續

本聊天已安排15分鐘接續。已有build／測試／CI時核對原操作，不另啟第二runner；來源未變且已過的測試直接沿用。只在實質里程碑、失敗或需要人類時回報。全部準備完成後暫停本次接續，不執行release，也不恢復原跨專案暫停排程。需電腦開機且桌面app保持運作；不是Windows服務或開機自啟。
