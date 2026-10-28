# 發布前準備

## 目前交付候選：b53479a（2026-10-28 最新結果）

固定受測／打包commit為`b53479a28ea030a92ae23ba50ed24d6aca2be679`，已普通推到既有開發分支。此次相對8b9cf27為7檔／460新增，含新的驗包工具與12個測試；產品src/config/playbooks等未變。後續純結果文件checkpoint不改產品來源，不另冒稱產品測試。

- `reports/release-prep-candidate-20261028-03/candidate.zip`：318檔，兩次建置完全一致；SHA256為`d755a8d85a9fec15343a88b7b0adeb24b003f7d21d6e3322b127df73b3e10605`。`release-manifest.json`為完整逐檔清單，兩個Git Job自然0／remaining0／無強停。
- `source-binding.json`與`reports/verify-candidate-tool-20261028-03/source-commit.json`：240個定向受測來源hash與新包全符、零差異；本機31/31（0skip/fail/error，1.193秒）只聲稱定向範圍。
- `reports/candidate-verify-release-20261028-01/verification-result.json`：使用本頁外部commit／ZIP pin，以repo工具實跑manifest核對與13/13隔離smoke；四個原CLI Job自然0／remaining0／無強停。一件合成pending、一份case、零ACK／native／model，重開保存相等與唯讀DB hash不變。
- `candidate-verify-reject-pin-20261028-01`及`candidate-verify-reject-manifest-20261028-01`：實際CLI帶`--smoke`仍在解壓／啟child前拒絕錯誤外部hash與竄改manifest，均exit2／owned_steps空；candidate03的`negative-cli-crosscheck.json`為2/2。
- candidate03的`rollback/rollback-result.json`：新候選反向patch的獨立index演練5/5、九個Git Job自然退出；tree等於公開main615f77f，真index／checkout未變。`artifact-crosscheck.json`為8/8，另以CI及最終保存回條閉合。
- [新候選精確CI run40642090530](https://github.com/SecludedCorner/EventGuard/actions/runs/40642090530)：UTC06:14:47 completed/success；Windows1636run=expected、1589pass／47既有可選SDK不可用skip、0fail/error，337.593秒、218AST、source_unchanged、未提前停止、原Job自然0／remaining0／無強停／逐測試殘留0；Linux fixture104/104、0skip，無Linux原生支援。固定摘要保存candidate03/ci-*.json；不保存完整logs，不手動dispatch或rerun。

受版控工具現可由下方命令重現驗包／smoke，不再依賴舊reports臨時smoke。正式release、main/tag、分支刪除與排程均未執行；原生111缺列／21error仍partial，24h/reboot與桌面喚醒未驗。歷史真04收件只保留原範圍。前一輪b57證據如下保留為歷史，不移植成新候選結果。

## 2026-10-28：repo 內可重現驗包／隔離 smoke（最新增量）

使用者要求繼續補實際交付缺口；不建立／恢復接續排程。原候選的解壓smoke僅在reports臨時腳本，現新增受版控`scripts/verify_candidate.py`與篡改／退出測試。外部必填expected commit與ZIP SHA256，先把輸入有界快照保存到全新目錄，再核對commit comment、逐檔hash／size、必要檔案、版本及完整manifest；manifest不能自行充當信任來源。拒絕重複JSON keys與數字型別替換，不複寫舊結果。

來源ZIP與manifest須放本專案reports內；輸出限全新`reports/candidate-verify-*`，拒絕父路徑逃逸／symlink／junction。離線模式只檢查完整性，不啟子程序、不解壓；`--smoke`另明確執行已核准雜湊的包內CLI，僅Windows私有Job，四個子程序各15秒上限與2秒收尾，保存原退出回條。這是已審查候選的合成操作，不是執行任意外來ZIP的沙箱，雜湊亦不是簽章或來源授權。

```powershell
py -3.13 -B scripts/verify_candidate.py --archive reports/DELIVERY/candidate.zip --manifest reports/DELIVERY/release-manifest.json --expected-commit <TRUSTED_40_HEX_COMMIT> --expected-sha256 <TRUSTED_64_HEX_ZIP_SHA256> --root reports/candidate-verify-NEW --smoke
```

expected值須由已審查checkpoint／可信交付紀錄取得，不能直接照抄待驗manifest。移除`--smoke`即為純離線檢查。成功產生`verification-result.json`、`verified-manifest.json`、輸入快照及（smoke時）逐步合成CLI／原Job回條；失敗留下固定原因，不序列化原始例外。smoke查一件合成事件、一份保存case、重開相等、唯讀DB hash不變、仍pending／零ACK／無live namespace，並核對包內來源未變。

初版定向`reports/verify-candidate-tool-20261028-02`為31/31、0skip/fail/error，1.244秒、218檔AST無錯、source_unchanged、原Job自然0／remaining0／無強停。新工具另實跑原b57候選於`reports/candidate-verify-historical-20261028-01`：manifest核對及13/13 smoke通過，四個私有CLI Job自然0／remaining0／無強停。這只是新驗收工具對原包的操作；下一個候選須以新commit實際重建／驗包並另綁本次範圍，不把下面舊完整1624項或舊CI升格。

最後來源再收緊remaining必須int0，避免False被當零；`reports/verify-candidate-tool-20261028-03`定向31/31、1.193秒、0skip/fail/error與原Job自然退出，才是本切片受測來源。保存後以同commit新包實跑，不重用原b57 smoke當新來源證據。

## 歷史基準：前一輪準備狀態（b57候選）

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

## 前一輪交付與可核對結果（b57歷史）

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

## 接續限制（排程已取消）

先前15分鐘接續任務已依使用者要求刪除，本次不建立或恢復排程；原跨專案暫停排程不動。工程只在目前工作階段內推進。已有build／測試／CI時核對原操作，不另啟第二runner；來源未變且已過的測試直接沿用。只在實質里程碑、失敗或需要人類時回報，不承諾會話結束後自動運行。
