# EventGuard 現況

## 2026-10-28 乾淨工作區與原子提交規則（最新）

本單元只落實最新Git工作規則：AGENTS／CLAUDE明定單一目的、約200行先拆、提交前build與相關測試全過、type(scope): summary、明列stage、禁amend／force／no-verify、單元後輸出hash／message／行數／status／shortstat並立即push；取代原「最多累積3個」的節奏。開始時工作樹乾淨，HEAD/upstream/main皆c80a4be。

提交前實跑c80a4be既有來源build於reports/release-prep-policy-check-20261028-01，318檔／兩次ZIP一致／兩Git Job自然退出；這不是包含尚未提交政策文件的新候選。當前來源定向verify-checkpoint-policy-20261028-01：UTC06:53:13–06:53:16（台北14:53:13–14:53:16），31/31、1.388秒、0fail/error/skip、218AST無錯、source_unchanged、原Job自然0／remaining0／無強停。新增文件換行混用曾被diff-check攔下，未commit該狀態，修正後重查；政策內容／連結與變更量另驗。僅四份文件以單一docs(workflow) checkpoint普通push既有開發分支，輸出實際SHA與乾淨狀態，不重寫舊commit、不重新宣稱產品／原生驗收。

## 2026-10-28 main整併終核、完整本機回歸與附件排除（最新）

使用者已明確授權推main並要求整併／測試。fetch後origin/main與開發分支同為a4e13fa75ea0d2d8b455281811114de3efe91844、ahead/behind0/0、tree差異0；五個可分享分支均為main祖先，沒有待合併產品碼。PR #1早於2026-10-22T09:09:47Z合併615f77f，本次依要求移除聊天PR附件，保留GitHub合併歷史。截圖+5368/-39與git diff 4a1a95bced234d75b744537f7507bd9f86235b11 a4e13fa完全相符（58檔已提交歷史），不是未提交數；UI實際基準未直接讀取，不能宣稱畫面已歸零。

依使用者要求實跑當前主線完整驗證：py -3.13 -B scripts/verify.py --run-dir reports/verify-main-integration-20261028-01 --timeout-seconds 1800，UTC06:33:14–06:40:24（台北14:33:14–14:40:24），428.735秒；1636run=expected1636、1633pass／3環境skip（兩symlink建立不可用、一notification icon不可用）、0fail/error，218AST無錯、source_unchanged、stop flags false、原guardian自然0／remaining0／無強停／逐測試殘留0。240來源hash與b534候選包全符；涵蓋本機已安裝SDK，非僅沿用CI47skip，不啟真模型／native掃描。

依最新隱私要求刪除四張已知本機圖片及其空附件目錄，不讀內容；已核對索引／全部已知Git歷史無相關檔案，GitHub main完整tree無相關路徑。圖片與含私人檔名的回條皆不提交；只新增.gitignore對附件／剪貼簿截圖的排除，git check-ignore兩項通過且一般產品圖片不被全面排除。平台聊天附件不在本機刪除範圍，未宣稱已移除。這個checkpoint僅排除規則與結果文件，沿開發分支保存後普通快轉main；產品來源未改，不重跑回歸、不打tag／發布／刪分支，私人main及其他worktree保留。

## 2026-10-28 新候選交付驗收閉合：b53479a（最新）

固定候選b53479a28ea030a92ae23ba50ed24d6aca2be679已普通push／直接核對遠端；來源切片相對8b9cf27為7檔460新增，非未保存修改。新增受版控verify_candidate.py及12個測試，外部commit／ZIP hash必填、完整逐檔manifest比對、純離線預設與可選有界私有Job合成smoke；CHANGELOG與操作命令已保存。

本機定向verify-candidate-tool-20261028-03為31/31、0skip/fail/error、1.193秒、218AST無錯、原Job自然0／remaining0／無強停；240來源hash與新候選包全符。新candidate03實際318檔／兩ZIP一致，SHA256d755a8d85a9fec15343a88b7b0adeb24b003f7d21d6e3322b127df73b3e10605；新工具在candidate-verify-release-20261028-01實跑13/13，四CLI原Job自然0／remaining0／無強停；兩個實際負向CLI在解壓／啟child前拒絕錯誤pin／竄改manifest（exit2、owned空）。新候選回復演練5/5、九個Git Job自然退出，真index／checkout不變。原b57的1624完整結果沒有改標新SHA。

精確新SHA CI run40642090530於UTC06:14:47（台北14:14:47）completed/success：Windows1636run=expected、1589pass／47可選SDK不可用skip、0fail/error、337.593秒、source_unchanged／stop flags false／原Job自然0／remaining0／無強停／逐測試殘留0；Linux fixture104/104。固定結果在reports/release-prep-candidate-20261028-03/ci-*.json，未安裝依賴或手動觸發CI。真模型／native均0，歷史真04不冒稱重驗。

最新入口docs/RELEASE_PREPARATION.md；只補四份結果文件checkpoint後普通push原開發分支並另存SHA／0/0核對。追蹤檔案應乾淨，兩張未追蹤附件／其他worktree及私人main保留。排程已刪除、不恢復；無main/tag/release／部署／刪分支。此輪交付工具缺口已閉合，原生111缺列／21error仍partial、24h/reboot及桌面喚醒仍未驗，須各自條件與授權；不把準備通過當真實環境全通過。

## 2026-10-28 候選交付增量：驗包／smoke已固化（最新）

接續8b9cf27，追蹤工作樹原乾淨／upstream0/0，未追蹤附件保留。使用者明確續做準備；排程已刪除，本次不建立／恢復。實際缺口是repo只有打包器，解壓smoke依賴reports臨時腳本；新增scripts/verify_candidate.py及tests/test_verify_candidate.py，必填外部commit與ZIP SHA256、有界輸入快照、完整manifest／逐檔比對、重複key／型別／路徑與舊目錄拒絕；預設離線不啟子程序，--smoke才在新reports副本跑合成CLI，事先私有Job與原退出回條，無模型／native／ACK／系統變更。

py -3.13 -B scripts/verify.py --run-dir reports/verify-candidate-tool-20261028-03 --timeout-seconds 180 --module test_verify_candidate --module test_package_candidate --module test_verify_completion --module test_verify_portability：UTC06:07:49–06:07:51（台北14:07:49–14:07:51），31/31、1.193秒、0fail/error/skip、218檔AST無錯、source_unchanged、原Job自然0／remaining0／無強停／逐測試殘留0。01/02亦31/31；02移除不必要os.name mock並確認拒絕原因，03再拒絕remaining的bool假零，才是最後來源。新工具先前已對原b57 ZIP實跑reports/candidate-verify-historical-20261028-01，完整manifest與13/13 smoke、四個CLI原Job皆自然0／remaining0／無強停；最後來源接續新候選實跑。

此切片先commit／普通push原開發分支，再實際建新commit候選、外部pins驗包／smoke、來源綁定及精確CI。舊本機1624回歸仍只屬b57，不套用新SHA；其餘native partial／24h/reboot等限制不變。界線與可重現命令見docs/RELEASE_PREPARATION.md；runtime不提交，無main/tag/release／分支刪除。

## 2026-10-28 發布前準備全數完成；尚未發布（最新）

使用者指定「不用release，做完所有準備」。固定候選b57b43be8333327584ef05af4e71740b5b80d621已普通推到origin/feat/local-codex-acceptance；公開main及所有可分享分支皆為候選祖先，無語意衝突，私人本機main祖先不可達。其他worktree及兩張未追蹤圖片保留。候選對公開main615f77f的285檔／55340新增／1961刪除是已提交歷史合計，不是未保存修改；此後僅四份結果文件補記。

修後完整guardian02已自然退出：UTC05:43:35–05:50:36（台北13:43:35–13:50:36），419.655秒，1624run=expected1624、1621pass、3環境skip、0fail/error，stopped_early與stop_requested皆false；216檔AST無錯、238來源hash與候選ZIP全符、source_unchanged，原Job自然0／remaining0／無強停／逐測試殘留0。三skip是兩項symlink建立不可用、一項notification icon不可用；不是略過失敗。原01的提前停止假綠已修且原回條保留、不作完整驗收。

實際candidate02包316檔，兩次build位元組一致，SHA256為2d5ae6a55a24aebd344a630a53b61abc075cfb9af3b62664afb1d9582a8f62d5；包內CLI合成smoke14/14、五個Job自然0／無殘留。獨立index回復5/5、九個Git Job自然0，反向patch所得tree等於公開main、真index／checkout不變。精確候選CI run40639767342 completed/success：Windows1577pass／47可選SDKskip，Linux fixture104/104；本機SDK範圍則如上1621pass。全部native scan/model0，runtime不提交。

入口docs/RELEASE_PREPARATION.md／CHANGELOG.md；本機證據reports/release-prep-candidate-20261028-02與reports/verify-release-preparation-full-20261028-02。PREP-1–5已完成，最後純文件checkpoint依原分支commit/push並另存遠端SHA核對；本聊天15分鐘接續在保存核對後暫停，原跨專案暫停排程不動。未push main、打正式tag、發布、部署或刪分支。真04歷史交付已通過；native111缺列／21error仍partial，24h/reboot、既有桌面聊天喚醒未驗，須依原界線另授權／驗收，不將準備完成冒充產品所有環境完成。

下一個人類決策是何時正式發布及tag/changelog，或另批准原生診斷；兩者均不屬本次「只做準備」。不新增無關工程以延長執行。

## 2026-10-28 發布準備實跑修復與固定來源重驗（最新）

整合checkpoint3ed82a8已推；首次實際ZIP build在新01目錄失敗，私有Job launcher不替applicationName短名稱git查PATH。改先解析並驗證既有完整git.exe路徑，不執行wrapper／不下載；新增兩個fixture。原失敗目錄與固定原因保留，未將其稱build成功。

為修正build而合作停止原完整01，原worker自然0／remaining0／無強停，跑1533項／1530pass／3skip；原驗證器卻給passed_checks=true，確認另一實際缺陷。原回條保持原樣，acceptance-classification.json明示取消／不得作完整PASS。修worker與parent雙閘道：必須非空、expected_tests等於tests_run、stopped_early=false、stop_requested=false；新增完整／中斷／末項取消／空suite／缺或bool計數fixture，避免乾淨exit洗綠。

定向verify-release-prep-repairs-20261028-01為19/19、expected19、0fail/error/skip、.681秒、source_unchanged／原Job自然0／remaining0／無強停，native/model0。修後完整02已啟動於reports/verify-release-preparation-full-20261028-02，原01不重用；來源再次固定，僅文件可增量更新。接續新commit的實際ZIP02／包內合成smoke／恢復演練，全部證據閉合才稱準備完成。

## 2026-10-28 全部發布前準備已啟動（最新）

最新使用者明確改為「不用release，但完成全部release準備、安排連續任務」。不再以分支／版本未選阻擋準備：沿用現有開發候選、納入所有可分享分支及公開main既有紀錄，私人本機main祖先、其他worktree與圖片保留；不push main／tag／正式發布或刪分支，語意衝突仍停止。

同聊天15分鐘接續已建立，原跨專案暫停排程未動；完成後暫停，不並啟runner。新增scripts/package_candidate.py與6個合成ZIP安全測試，使用已安裝Git與Python、私有Job建立兩份同commit ZIP、檔案hash／路徑／容量／必要檔案檢查。初版5/5定向通過；追加Windows別名與私人檔案邊界後，完整guardian已執行於reports/verify-release-preparation-full-20261028-01，來源固定，結果未出前不記PASS。

CHANGELOG為Unreleased草稿；完整佇列、build、包內smoke、恢復演練及未來發布閘道在docs/RELEASE_PREPARATION.md。本checkpoint先保存整合／打包前置，再接實際候選包與結果，不將準備成功冒充native coverage、24h/reboot或正式發布。

## 2026-10-28 P0-LISTENER-COUNTS-003：修正baseline可誤判完整的缺陷（最新）

依使用者要求實際修bug、不能只隱藏UI或解除PR連結，從47af11f接續。發現project_baseline只查四項table status/count欄位存在，沒有核對返回列數；缺列／多報、TCP與UDP或IPv4與IPv6錯表，即使自有query自然exit0也可能判完整。先以guardian新回歸重現5個failure entries（18方法／13pass，無error），保留reports/verify-listener-count-regression-20261028-01；原正向fixture四表各1但只有1列，亦修正為TCP4=1、其他=0。

修復按每列protocol及實際IP family分組，逐表核對固定四項count，新增table_counts_consistent；不只查總和，不放寬零錯誤／身分／退出標準。三個新測試含缺列與錯表拒絕、乾淨exit不能洗綠，以及四表／完整空表仍有效。命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-count-regression-20261028-02 --timeout-seconds 180 --module test_windows_listener_validation --module test_listener_error_summary --module test_listener_identity --module test_collector_contract：UTC05:11:45–05:11:55（台北13:11:45–13:11:55+08:00），52/52、8.699秒、0fail/error/skip、source_unchanged、原Job自然0／remaining0／無強停／無逐測試殘留，native scan/model均0。不是release合併後完整回歸或原生重驗，原235列／缺111列／error21的partial不變。

gh api唯讀核實PR #1 title為Publish bounded Codex event delivery with MIT license，closed／merged=true、merge SHA615f77f、2026-10-22T09:09:47Z已合併；它是舊PR，未以解除附件代替處理。新release依使用者流程仍待指定分支、merge方式、版本號與changelog，沒有合入main／打tag／刪分支。修復按原checkpoint規則commit/push現有開發分支並另存回條。

本次script變更使既有windows-listener-diagnostics-20261028-01的source hash過期；保留原manifest／未批准template與NEXT_DIAGNOSTIC，標記superseded，不覆寫或執行。後續若要真診斷須依當時版本重新prepare及取得新精確批准；本輪不新增批准問項或native查詢。

## 2026-10-28 既有11份研究文件保存 checkpoint（最新）

依最新使用者明確授權，接續0ea26cb；本機／upstream／直接ls-remote均相同，ahead/behind0/0、追蹤檔案原乾淨，未見其他協作writer或index.lock。本次範圍為docs/research/agent-event-ingress五份與major-vulnerability-response六份既有10/23–24研究，逐檔審查後保存；不是新待推產品碼、PR發布或新研究。

最小處理：移除OpenOctopus來源的聊天識別／deep link及標題，重大漏洞README不公開cached health原始時間／狀態，保留「未獨立驗證程序存活」。11份均標明歷史基準優先／不當現況，所有reports連結逐一標明本機證據、不隨repo提供；公開來源與當時失敗／unknown／未驗證語義保留，不讀取或提交原reports。舊「未單獨commit」與每日五次等段落只保留為當時歷史，不改寫成現行要求或已驗收能力。

檢查只限檔名／內容／相對連結／歷史語義／固定秘密及私人ID模式、git diff --cached --check；命令、原／後文件hash與結果在reports/research-checkpoint-20261028-01，不是產品回歸或原生驗收。只暫存明列11份研究＋STATUS/HANDOFF，純文件checkpoint以[skip ci]普通push原origin/feat/local-codex-acceptance並直接核對遠端，實際SHA見Git及本機remote回條。兩張.codex-remote-attachments圖片保留未追蹤，不讀取、不提交；P2-OS-DIAG-002仍未批准，無新模型／native診斷／部署／主線合併或tag。

## 2026-10-28 P2-OS-DIAG-002：身分錯誤分類保存已完成，原生未重跑（最新）

接續a7bdfc0、原開發分支；追蹤工作樹原乾淨，兩個他人未追蹤目錄保留。窄讀發現NativeBackend／WindowsCollectors已有typed原因碼／階段／操作，但原baseline投影只保存總數。只改scripts/validate_windows_listener.py，加入有上限的error_summary及winapi.py來源hash綁定；不改native採集、規則或complete標準。分組只允許固定碼，未知維持unknown，保留／未保留／分類數分列；沒有新增PID、命令列、路徑、帳戶、端點或身分一致性資料。舊111缺列／21錯誤仍不可回推根因。

新增6個注入／合成測試，命令 py -3.13 -B scripts/verify.py --run-dir reports/verify-listener-error-summary-20261028-01 --timeout-seconds 180 --module test_listener_error_summary --module test_windows_listener_validation --module test_listener_identity：UTC03:56:35–03:56:44（台北11:56:35–11:56:44+08:00），27/27、7.506秒、0fail/error/skip、source_unchanged、原guardian自然0／remaining0／無強停／無逐測試殘留。native scan/model均0，未手動觸發CI，也未重跑真04／長測試；普通push可能觸發既有CI，其結果尚未另核實。新切片不是原1e8f7e0受測CI或真主機通過。

唯一下一診斷方案只prepare於reports/windows-listener-diagnostics-20261028-01，query_started=false、未批准、無intent/result/outer-start；run/hash與完整有界決策在docs/WINDOWS_VALIDATION_PLAN及該目錄NEXT_DIAGNOSTIC.json。沿用原一次native baseline範圍5秒／30秒與私有Job收尾，只新增固定分類數保存；本輪不開新批准問題，不執行、不沿用舊批准。拒讀／物件不可用／建立時間晚於捕捉／API不可用／一般失敗可分列，仍不能證明程序退出競態或逐owner根因。checkpoint按原規則commit/push；runtime／批准template不提交，遠端結果另存回條。

## 2026-10-27 P2-OS-001 已批准並實跑：partial，未通過完整基線（最新）

收到 dot 轉達的人類原問答：2026-10-27 03:00 UTC「同意1、2、3」，本案僅第3項單次 native listeners baseline。於原 reports/windows-listener-baseline-20261026-01 寫 human-approval.json，保守以 03:00:00–03:30:00 UTC 綁定原 root/run/manifest hash/scope；執行前確認 HEAD edc088c、原11檔 source hash 相符、無 intent/result/outer 回條，沒有重複執行。此新具名批准已取代下方歷史「尚未答覆」，一次授權現已使用。

實際命令：py -3.13 -B reports/windows-listener-preparation-20261026-01/run-owned.py --root reports/windows-listener-baseline-20261026-01。查核 UTC 03:04:36.844483–03:04:37.668540（台北 11:04:36.844483–11:04:37.668540+08:00），query elapsed 0.739012 秒，無逾時／取消。TCP IPv4／IPv6 分別28／13列，UDP IPv4／IPv6分別132／62列，四項 status=ok，共235列、未截斷；必要程序身分缺111列、error_count=21，process_identity_status=unknown。因此 source partial、complete=false，驗收 status=blocked／reason=baseline_incomplete；不能把四表成功當完整 native 驗收通過，更不能判主機安全。

原 HANDLE／Job 回條：內層 query 自然 exit 0、外層 validator 自然 exit 2，兩者 remaining_owned_processes=0、forcibly_terminated=false；外層 wrapper_error=false／deadline=false，命令返回1如實保留。只落盤固定狀態計數與自有 Job 回條，raw facts／socket／registry／system change／model 均無。本次未改產品碼或重跑 CI／全庫／真04；受測產品仍1e8f7e0。

獨立收據一致性核對13/13（不是 baseline PASS）：原 run/批准時窗/scope、四表計數守恆、退出與原11檔 hash 均相符。證據為同目錄 result.json、execution-intent.json、outer-start.json、outer-exit.json、acceptance-crosscheck.json。只憑固定計數無法區分拒讀、程序退出競態或其他身分讀取失敗，根因維持未知；沒有再查、提權或降低完整標準。P2-OS-001 現為已執行但不完整，不再等待這次批准，也不自動換目錄重跑；後續 native 診斷／重驗須另有精確必要範圍。既定離線切片已完成，未辨識出可直接修復的新離線 regression；先按 checkpoint commit/push 保存，不新增 fixture 代替真來源。

## 2026-10-27 接續核對與 soak 時區修正（最新）

接續 HEAD d922f48，分支 feat/local-codex-acceptance、upstream origin 同名；接手時追蹤檔案乾淨、ahead/behind 0/0，原兩個未追蹤目錄保留。受測產品仍為 1e8f7e0；既有 CI success、真04及調查證據沿用原 scope，不重跑全套。

原 soak summary 的實際 UTC 起訖為 2026-10-25T17:12:21.291029+00:00 至 2026-10-25T17:44:01.298238+00:00，等於台北 2026-10-26 01:12:21.291029–01:44:01.298238+08:00。下方 10/26 標題是本地日期，不能把 UTC 17:12 誤配成 10/26；1900.017392 秒 wall 及既有量測結論不變，未重跑 soak、未改原收據。

P2-OS-001 仍缺原具名單次批准：是否批准 reports/windows-listener-baseline-20261026-01 的一次 native TCP/UDP、IPv4/IPv6 listeners baseline 及必要 owner 建立時間查核（query 5 秒、總預算 30 秒，只保存狀態／計數與自有 Job 退出回條；不開 socket、不改 registry／系統、不啟模型或其他來源）？此處記錄原待決問題，沒有重新建立請求。此次轉達不代答；現有目錄無 human-approval.json、execution-intent.json、result.json 或 outer-start.json，未執行採集。有直接有效批准後才依同 root/run/hash/scope 執行一次；無已辨識的新離線缺陷，不用擴 fixture 或重跑驗證替代真來源驗收。

本次只修正文件與核對原收據；命令為 PowerShell Get-Content／ConvertFrom-Json、DateTimeOffset UTC→+08:00、Get-FileHash 及 git diff --check。證據 reports/soak-time-correction-20261027-01/state-verified.json 與 validation.json；提交／推送仍依既有 checkpoint 規則，遠端結果另留回條，不把文件 SHA 當新受測產品。

## 2026-10-26 固定Git保存規則（最新）

依直接使用者要求，AGENTS新增Git checkpoint與遠端保存規則，CLAUDE.md作簡短入口：每個可保存checkpoint立即commit/push，連續小commit最多3個未推送；恢復／交接時補推，失敗保留本機與待推SHA，推後直接核對遠端。僅原origin/feat/local-codex-acceptance，不改產品、安全或資料界線，也沒有建立背景排程。文字驗證8/8與git diff --check；證據reports/git-push-policy-20261026-01/validation.json（2026-10-26T16:00:08.752770+00:00）。本次純文件以[skip ci]保存，不重跑已通過CI／測試；受測產品版本仍1e8f7e0。


## 2026-10-26 精確版本遠端CI已成功（最新）

受測可用產品版本為1e8f7e0e74f2018849b44cb02e2052d2fe817da4，分支feat/local-codex-acceptance。獨立GET核實Offline verification run40345960922／attempt1／push，head_sha完全相同，UTC2026-10-26T15:11:02Z（台北23:11:02）已completed/success。Windows job121652823962：1603項、1556pass／47可選SDK及相關transport/SSE依賴skip，0failure/error；原Job自然exit0／remaining0／無強停。Linux mock job121652824391：104/104、無skip/fail/error，僅自身worker exit0，creation/job/tree/remaining未知，仍明示無Linux native。

新終結收據reports/ci-head-bc56e37-20261026-01/repair-ci-terminal.json；兩次pending與bc56e37原failure各自保留，latest回條已指向成功。完整47個skip名單保存在repair-windows-summary.json，不把skip當實際執行，也不借本機SDK或其他SHA綠燈補足。這輪只讀遠端metadata及必要結果摘要，沒有CI rerun/dispatch、本機全庫／九案例重跑、workflow／權限變更或新模型／主機採集。

本次只更新STATUS/HANDOFF/EVIDENCE，以[skip ci]提交／普通push保存狀態，避免純觀察形成CI循環。這個文件checkpoint的SHA不是另一個受測SHA；產品程式與1e8f7e0相同，CI成功只綁定1e8f7e0。下一既定里程碑P2-OS-001仍是原單次listeners baseline，需原具名問題的直接批准；不重問、不擴範圍。正常收件／調查與CI閉環已交付，不宣稱真主機防護、既有聊天喚醒、24h/reboot、Linux native或已超越競品。


## 2026-10-26 精確CI失敗已核對與修復（最新）

已唯讀核對bc56e37b4cfb63ed3e0a9caf98d11a66b140372d的push CI：Offline verification run40339572814／attempt1，結論failure；Windows job121630253841及mock job121630254549都失敗，不能用空legacy statuses或本機綠燈代用。Windows摘要為9個failure entries／1error，mock因非Windows Popen無created_at在驗證器137行中斷，原run無artifacts，沒有更細unit trace。原CI狀態保持failure。

已在隔離合成條件重現全部9個Windows失敗名稱及RustSec CRLF TOMLDecodeError。修正：desktop/schedule/service測試根目錄先canonical resolve、損壞pending測試明示fixture SDK前置；產品安全閘道不改。RustSec解析正規化CRLF。驗證器非Windows僅保留原Popen worker的退出碼、合作取消／有界自有child收尾，creation/job/tree缺證據維持None/false；只有mock scope可接受worker-only證據，timeout/owner failure即使exit0也不得pass。Windows原privateJob finish不變，workflow／權限未改。

本機受影響127/127；相同短路徑＋缺SDK重現6方法／原9failure entries現為0，CRLF accepted、兩次Job均自然0/無殘留。最後guardian邊界7/7、mock範圍104/104，皆source_unchanged、自然0/Job0、model0/scanfalse；不同範圍不加總成全庫，也不是Linux實跑或遠端CI通過。修復提交依既有規則普通push同分支後，另查新SHA的既有CI，不手動dispatch/re-run、不新增workflow或權限。證據在reports/ci-head-bc56e37-20261026-01及verify-ci-*。


## 2026-10-26 已確認遠端保存並接續golden量測（最新）

已普通fast-forward推至origin/feat/local-codex-acceptance；git ls-remote實查遠端與本機同為548efe8bbfc7548b5b2d530db2c9203295583bce，ahead/behind=0/0。先前57個待推commit及本checkpoint已保存，不是正式發布；未推main／其他保留refs，不force、不改歷史。推前累積264檔/+52654/-1961是9576b13→cd117f9的比較，548efe8本身只有5檔/+106。其他兩個未追蹤目錄仍保留。

之後已接續原任務，完成reports/investigation-source-golden-20261026-01：9案例全過、錯加0／漏加0，4案例缺實體／來源維持UNKNOWN，18事件仍pending／ACK0，逐案保存與重開一致。獨立9/9 SQLite mode=ro/query_only核對來源hash與case；自有worker原HANDLE自然0／Job0／無強停。每案建案37.255–101.101ms，九來源庫合計405504B；僅這組synthetic來源shape，不是7來源全覆蓋、惡意偵測率或production效能。02定向29/29證據沿用，產品碼未改。

本補記為下一個小checkpoint，同既有分支普通推送並實查遠端；實際最終SHA見Git及reports/git-checkpoint-20261026-01/remote-verified-final.json，不用文件意圖代替推送結果。後續每個可獨立保存階段提交並推送，不再累積。尚缺真來源／OS帳戶owner／跨來源因果、24h/reboot及實際競品同環境評測；原listeners具名批准不重問、不代授權。離線下一實作僅在有具體產品缺陷或契約缺口時進行，不用擴fixture數替代真路徑。


## 2026-10-26 Git遠端保存 checkpoint（最新）

最新直接使用者要求先提交及遠端保存，再接續開發；這是本專案既有開發分支的push授權，取代下方本輪「只本機／不push」限制，但不授權正式發布或推其他分支。位置EventGuard，分支feat/local-codex-acceptance，上游origin同名，remote https://github.com/SecludedCorner/EventGuard.git。推送前遠端實查9576b13a6773ce81c3a01799743d30094a48449a，本機cd117f9已領先57commit；比較遠端→HEAD為264檔、+52654/-1961行，屬歷史累積，不是當前未提交量。

本checkpoint保存9個多來源golden case及其測試。首輪9個subcase同因測試誤讀list_events未公開payload_hash欄位而error，產品碼未改；改用公開schema正規化後計算hash。定向02為29/29，無fail/error/skip、source_unchanged，自有Job自然0／remaining0／無強停，未採集／啟模型／ACK。先保存，再續逐案例成本／錯加／漏加產物。

推送範圍只refs/heads/feat/local-codex-acceptance，不推其他本機保留refs。57commit逐檔路徑及所有新增patch行審查：265路徑／55946新增行，無runtime禁入路徑或高信度secret pattern命中；不等於形式化無秘密保證。reports/data/logs/SQLite/授權及他人未追蹤.codex-remote-attachments/、docs/research/不加入。推送結果以遠端核對回條及後續補記為準，不把意圖當成功。


## 2026-10-26 調查查證脈絡接通（最新）

接續bc5f028，P1-INVEST-002完成：新1.1案件納入同事件已驗證的保存診斷hash／時間／query類型／來源／狀態／列數，rows不複製、不重新diagnose。缺失／過期／未來／空結果／partial列缺口；跨事件誤綁及保存競態拒絕，診斷後續變更／刪除標明且保留原case，1.0仍可讀。CLI／Web均顯示來源脈絡。

新增8 fixture，核心定向160項159pass／1通知skip、0failure/error；之後僅Web／presentation變更的52項增量51pass／1同skip、0failure/error，兩輪source_unchanged，原Job自然0／remaining0／無強停，不相加為全庫。最終reports/investigation-product-20261026-03原來源10檔hash相符，18/18；真IAB保存／重開同case及診斷hash、2項保存query摘要一致，8事件仍pending／ACK0／單case，原worker自然0／Job0／無強停。診斷來自FixtureAPI，明示system_query_executed=false，不是原生主機證據。

原真04與1563pass、30分鐘idle均保留原scope；未重跑模型／全庫或native baseline。兩個調查切片已可用，操作及競品差距在OPERATIONS／MAINTENANCE_GOAL；沒有同環境競品實測，不能宣稱超越或全天候防護。下一可離線切片為P2-INVEST-COVERAGE-003多來源黃金資料集／誤關聯與UNKNOWN量測；listeners原具名批准仍待答覆，只阻擋該次原生觀測。執行資料不提交，本機commit、不push。


## 2026-10-26 事件調查產品切片（最新）

基底124b42c、分支feat/local-codex-acceptance；已新增同SQLite的保存案件、穩定實體關聯時間線、來源／過期／矛盾／截斷限制、CLI events investigate 與Web建立／更新。查看及重開不重算，不採集、不啟模型、不ACK，allowed_actions空；OS帳戶owner未保存，固定UNKNOWN，不把host雜湊當帳戶證據。

最新定向 reports/verify-investigation-20261026-03：152項、151通過／1 notification_icon_unavailable略過、0失敗／error，source_unchanged；guardian自然0／Job0／無強停。這不是重跑全庫；原1563pass與真04原版scope沿用。review發現跨episode序號不可比，最低成本改成同episode檢查，新增正常多端點／序號重置負控制，01/02前版證據保留。

最終產品 reports/investigation-product-20261026-02：CLI→HTTP→CLI→重開同case14/14，8事件全保留pending、ACK0、1最新case，自有worker自然0／Job0／無強停；01有實際瀏覽器保存／重開圖，web.py相同，02是episode修正後的最終來源重核。一次建案89.13ms、DB增8KiB、case2574B；非人類調查時間／production峰值或競品勝負。官方競品差距與量測方法在docs/MAINTENANCE_GOAL.md，操作在docs/OPERATIONS.md。

CURRENT/NEXT：離線P1-INVEST-002可繼續，接同事件已保存的診斷/query來源脈絡與時效，不重新diagnose。listeners具名批准只阻擋該次原生觀測；不是全部離線工程停止條件。真EDR／跨產品優劣、OS owner／跨來源攻擊鏈、24h／reboot／既有桌面喚醒仍未驗。先本機提交，不push。


## 2026-10-26 持續工程：長窗與所有權修復（最新）

操作入口補記（2026-10-26T07:43:13.5264320+00:00）：README／AGENT_SERVICE 已交付當前入口、一次 service 操作、固定 metadata 結果／ACK／五層退出查閱方法及適用情境；CONNECT_AGENT／LIVE_CHANNEL 舊相容流程加現行入口指引。17/17 唯讀核對，五份原真04證據 hash 不變、native baseline 11檔 source hash 相符，無新模型／採集／重跑回歸。紀錄 reports/operator-entry-review-20261026-01/validation.json。原聊天無新增 baseline 答覆，唯一待決點仍為同一目錄的單次批准，不重複提問。

基底4a1a95b，分支feat/local-codex-acceptance；只本機提交、不push。既定真CLI鏈仍通過：真04的一件合成事件 receive→query→result保存→ACK各1、pending0；MCP/CLI/supervisor/host/outer五層自然0。UI/API/CLI真頁面顯示亦已驗證。本增量沒有新模型任務。

P2-IDLE-CPU-003／30M：profile定位本harness每秒全樹usage成本，改為排空後單writer的已驗總量＋自身append delta。每筆仍_guard/實際大小/sample與report cap；mutation／phase／final仍全樹檢查，外部其他檔突變不是即時防篡改。12/12定向通過；恢復語意fixture明示虛擬deadline，不冒充真wall。真03 wall60.012212秒、idle31.411523秒CPU0.945115%，16ACK/pending0、自然0。

長窗 reports/soak-idle-30m-20261026-01：UTC 2026-10-25 17:12:21–17:44:01（台北 2026-10-26 01:12:21–01:44:01+08:00），wall1900.017392秒、16ACK/pending0、475有效樣本；原HANDLE自然0/Job0/無強停，7檔source hash不變。獨立32/32核對：最後實際1802.489810秒窗CPU0.343275%單核心、private峰增73728B（72KiB）、handle增0（111不變），三目標通過。這是自身harness idle，非整Job／production／24h／重啟或主機安全證據。

P0-OWNER-SNAPSHOT-005：已通過對應回歸。背景stop改綁control.lock內已驗selected_owner，避免診斷status瞬斷/舊run_id誤綁scope；App僅對固定unverifiable、無明確foreign identity的快照重觀測一次，第二份必須完整同namespace/run/PID/creation/Job/generation才控制，持續unknown仍阻擋。新增2背景＋3App確定性fixture；不推斷原失敗特定Win32錯碼。最新完整回歸 1566 項／1563 通過／3 略過、0 failure/error；source_unchanged=true，原Job自然0／remaining0／無強停。

P2-OS-001前置已完成：新增scripts/validate_windows_listener.py與15個fixture（guardian15/15），缺批准/過期/hash/scope不符/預存stop/intent fsync失敗不查詢；合作stop即使complete也不得pass。實際reports/windows-listener-baseline-20261026-01僅prepare，query_started=false。範圍一次native listeners／query5秒／30秒工作預算，無socket/registry/模型、只保存狀態計數與自有Job回條。原loopback陽性案例按產品語義不成立，已修正WINDOWS_VALIDATION_PLAN；不改規則或改綁全介面過測。

CURRENT/NEXT：下一個必需關卡是已準備的一次native listeners基線；非同步批准尚未回覆，沒有human-approval.json，不可執行。 其他實機來源/負向socket案例、既有桌面喚醒、24h及發布仍未驗或缺範圍，不自行排程、擴權、推送或承諾會話外喚醒。證據與完整命令見EVIDENCE；runtime／授權／SQLite不提交。

## 2026-10-26 持續工程：產品狀態、分頁與有界量測（最新）

基底 9a34a5b，分支 feat/local-codex-acceptance；依既有授權繼續，未 push、未改系統／帳戶設定。AGENTS 的 Continuous Execution Policy 已在 a34e466 逐字加入，繼續有效。

- P2-MCP-STATUS-001：CLI／Web／Tk 加入有界 MCP 退出摘要，從當次 attempt 原始 marker／HANDLE 證據重讀；舊資料、缺檔、外來 run 或非零皆維持 unknown，不信任快取的 verified。實際閒置 test App 的 API／CLI／瀏覽器一致顯示「MCP退出已驗證、退出碼0、ACK flush」。GUI 關閉後原 HANDLE 自然0／Job0／無強停，collection/model/新增CLI 均0。真04原64檔hash全不變；只新增App descriptor/lock。
- P1-SOAK-GUARD-002：spawn後任何有界異常先嘗試耐久 stop.request，再 grace／原自有Job收尾；保存失敗維持 unconfirmed。P2-SOAK-MEASURE-001：獨立 minimum wall、pacing、僅本worker pseudo-HANDLE的 CPU/private bytes/working set/handle 採樣，未知=null，JSONL有界。兩輪真有限harness各16 accepted/16唯一ACK/pending0，wall 60.037116／60.045564秒，皆自然0／Job0，非模型、OS重啟或24h。
- P2-GH-PAGES-001：GitHub有界分頁，預設5／最多8頁；一次固定metadata驗證 canonical repository ID，最多max_pages+1 GET，共用bytes/deadline；僅forward after或連續page，固定origin/path/filters/page-size，拒redirect／循環／混用／錯誤mapping。partial保留last-good、304不得洗完整；完整success才清舊單頁validators；max_pages屬resource policy，不使legacy cache換binding。

定向14模組253項252過／1通知圖示略過；首輪完整1534項1530過／3略過／1舊dict斷言失敗，已補新增unknown欄位後77/77。真canonical/after與soak增量定向201/201。最新完整回歸 1543 項：1540 通過、3 略過、0 failure/error，source_unchanged=true，guardian自然0／remaining0／無強停，model_calls0、machine_scan=false。原失敗不覆寫。

真公開分頁04：兩公告頁＋一次metadata GET，uv repo id699532645，17369/65536 bytes，1.305084秒；正確partial/github_pagination_page_limit，兩頁smoke及27項獨立核對通過。追加05按預設5頁上限仍partial，完整來源要求未達；只寫隔離test cache，未改正式cache，不再加大cap洗綠。早期01 transport_denied及wrapper無效finish reason缺退出回條、02/03 canonical不相容均保留。

資源實測：降低harness輪詢20Hz→4Hz後，短窗idle CPU 4.392866%→4.069045%單核心，仍未達<1%目標；兩次不是受控主機負載實驗，不能認定因果，更不代表產品monitor性能。下一項 P2-IDLE-CPU-003 只診斷自身harness observer成本，根因有證據才修。30分鐘idle／24h／全Job資源與實機來源仍未驗。

證據目錄：reports/verify-product-pagination-metrics-20261026-01、verify-agent-status-compat-20261026-01、verify-github-cursor-soak-20261026-01、verify-full-20261026-01/-02、soak-measured-20261026-01/-02、mcp-status-product-20261026-01、public-fetch-github-pages-20261026-01…05。原先 receive→query→result→ACK 及五層退出真證據仍是 reports/service-acceptance-eventguard-mcp-exit-20261025-04；本切片沒有重跑模型。執行資料不提交。


## 持續工程 checkpoint：MCP 自身退出與有限恢復流程通過（最新）

基底 a34e466，分支 feat/local-codex-acceptance。本輪依持續工程授權繼續實作，沒有將前次 commit 或單事件通過當停止條件。

P2-MCP-EXIT-001 已完成：event-bound 專用入口新增 ACK 成功回應真正 write＋flush 後合作退出；既有 observer／readonly 不自動關閉。新增 query-only 所屬 Job member HANDLE 觀測，先核對 PID／creation／本次 CLI 私有 Job，再在活體時保留同 HANDLE，未授予 terminate 權限；缺失／unknown 不升格成功。capture 保存 start/exit，額外 --require-mcp-exit 重讀原始證據，舊驗收契約仍可讀。

新真驗收 reports/service-acceptance-eventguard-mcp-exit-20261025-04：一件合成事件、三工具各 1、pending 0／receipts 1；MCP、CLI、supervisor、host、outer 五層 exit 0。四個原有 Job remaining 0／無強停，MCP 有 ACK flush、正常 stdio-exit 與活體綁定 HANDLE 的 OS exit 0 證據。外層 43.442485 秒；獨立 SQL／hash／時序核對及 --verify-only --require-mcp-exit 重驗通過，已補上前輪 MCP 自身退出缺口。仍不是桌面喚醒或完整 IO 隔離證明。

P1-SOAK-001 已完成有限整合：新增 scripts/soak.py／eventguard.soak，以純 synthetic producer／EventStore／QueueInbox 演練滿載拒絕保留、原 ID/hash 恢復、completion 保存故障 pin 保護、重建 consumer 同 query、冪等 ACK 與排空守恆。reports/soak-finite-20261025-02 接受 64／唯一 ACK 64／pending 0，實際 81.881672 秒，guard 自然 exit 0／remaining 0／無強停。這是 harness，不是真 agent、OS 重啟或 24h。

失敗與修復：首輪 10 模組 117 測試，116 過／1 error（soak 的 SQLite read-only 連線僅交易 context 未 close，Windows temp 收尾鎖檔）；改用 closing 後 test_soak guardian 3/3 通過。其餘 114 項 MCP／transport／Job 測試來源未變，沿用逐測試通過證據，未冒充同輪全綠。真流程首輪 64 件／60 秒工作上限在 52 件 ACK 後到期，保留原失敗與 12 件未入列 producer；集合守恆重驗無丟失。第二輪同 64 件改採 180 秒有界 profile，未宣稱 60 秒通過。

證據：reports/verify-mcp-exit-soak-20261025-01、reports/verify-soak-close-20261025-01；真04的 communication-result.json／mcp-exit-validation.json／五份 mcp marker/process 回條；兩個 soak 目錄的 validation.json／conservation-recheck.json。執行資料不提交。

CURRENT/NEXT：保存本切片後直接處理 P1-SOAK-GUARD-002 的異常收尾、P2-SOAK-MEASURE-001 的真 wall-time／自有資源採樣，以及 P2-GH-PAGES-001 的公告來源有界分頁。完整工作佇列在 docs/MAINTENANCE_GOAL.md。實機來源與 24h 的未驗範圍不變，未 push。

## 2026-10-25：加入 Continuous Execution Policy（最新文字變更）

依使用者提供原文，將持續工程推進政策加入 AGENTS.md；原有專案與安全界線保留。台北 23:18，以 Python 文字比對驗證整段逐字一致、只出現一次、既有內容位元組不變，並執行 git diff --check。證據 reports/continuous-execution-policy-20261025-01/validation.json。純文件變更，未重跑程式回歸或真 CLI，不新增產品驗收結論。

## 2026-10-25：真 Codex 收件鏈通過（最新）

最新直接人類指示「解除額度限制，與各種阻擋限制，請全力開發」已撤銷前輪兩次真 CLI 上限與暫停接線要求；下方「額度用完／不得第三次」均為歷史。本輪基底 `836d0df`，分支 `feat/local-codex-acceptance`，保留 AGENTS 安全界線。本輪新授權後實際只啟動 1 個真 CLI 任務；未 push。

**既定收件目標已通過**：新目錄 `reports/service-acceptance-eventguard-development-20261025-03`，一件合成事件，由 service 在空佇列等待後入列並啟動專用原生 Codex。台北 22:45:35–22:46:24，外層 49.314 秒；receive→query→保存結果→ACK 各 1，pending 0、receipts 1、無重複。CLI JSONL 真工具回傳、durable event/query/result、SQLite、結果先存再 ACK 時序均一致；`--verify-only` 重讀原始證據仍 passed=true，另有獨立 mode=ro 核對。

CLI、capture worker／supervisor、host、outer validation 原 HANDLE／Job 回條均自然 exit 0、remaining 0、無強停。CLI owned tree 已空。這是專用 CLI agent 真收件，不是既有桌面聊天／dot 閒置喚醒或主機安全結論。

本輪修改：單次 MCP 配置顯式 enabled=true；新增可選 startup-evidence-dir 與有界安全 phase markers，記錄 server 啟動／工具清單，保留 required／20 秒啟動／60 秒工具期限與三工具 allowlist。移除每次全新 sqlite_home override，保留 ephemeral、history.persistence=none 與專用 log_dir，不移植認證或修改全域／帳戶設定。CLI 有效配置與本機 public features/help 先以無模型 metadata 核對；沒有使用 removed 的 SQLite 功能旗標。本次組合修正成功，不能歸因單一改動。

定向 guardian：`py -3.13 -B scripts/verify.py --run-dir reports/verify-inbox-startup-evidence-20261025-01 --timeout-seconds 300 --module test_inbox_startup_evidence --module test_agent_dispatch --module test_queue_inbox --module test_delivery_consolidation`。台北 22:43:37–22:44:41，Python 3.13.3，54/54 通過、0 failure/error/skip，source_unchanged=true、guardian 自然 exit 0／remaining 0／無強停、model_calls 0。新增 5 項測試含真 SDK JSON-RPC list_tools、EOF 及 marker scope／redirect／失敗路徑。

完整回歸：`py -3.13 -B scripts/verify.py --run-dir reports/verify-full-20261025-05 --timeout-seconds 1800`，台北 22:48:26–22:55:41。1477 項：1474 通過、3 略過、0 failure/error；兩項 symlink 不可用、一項 notification_icon_unavailable。passed_checks=true、source_unchanged=true；guardian 自然 exit 0／remaining 0／無強停、無逐測試殘留，model_calls 0、machine_scan_executed=false。證據 `reports/verify-full-20261025-05/verification-summary.json`；提交後 source-commit.json 綁定本版受測來源。

證據：[真通訊結果](reports/service-acceptance-eventguard-development-20261025-03/communication-result.json)、[原始證據重驗](reports/service-acceptance-eventguard-development-20261025-03/validation.json)、[獨立交叉核對](reports/service-acceptance-eventguard-development-20261025-03/acceptance-crosscheck.json)、[定向測試](reports/verify-inbox-startup-evidence-20261025-01/verification-summary.json)。reports、SQLite、CLI 輸出與授權紀錄只留本機，不提交。

限制：本次有同 instance 的 server-started／tools-listed marker，沒有 mcp-stdio-exit marker。MCP PID 後查為 missing，CLI Job 已空，但 MCP server 自身 OS 退出碼／自然退出沒有獨立證明，不能把四層回條泛化。當次 legacy metadata／invalid transport／WSA 10013 警告布林均 false；未手動開啟原始 sessions，亦不以無警告宣稱完整 IO 隔離。上述額外證明、長期運行與桌面喚醒列 DEFERRED；不阻擋原先明列 CLI／worker／host 的收件驗收。

## 2026-10-25：第二次真任務完成回合但未收件；兩次額度已用完（最新）

本節優先於下方「第二次未執行／仍保留一次」的歷史文字。本輪基底 `c5401e9`，分支 `feat/local-codex-acceptance`。三個里程碑已完成證據收尾；真 receive→query→保存結果→ACK **仍未通過**。原授權兩次真 CLI 任務已用完，不得再啟動第三次或重用任一目錄。未 push。

1. **連線診斷完成**：同一個無認證 HEAD 探針在工具沙箱內重現 WSA 10013；經自動批准審查允許單次工具沙箱例外後，一般 Windows 使用者環境回 HTTP 403，支持連線可達。探針模型任務 0、兩個 Job 自然 exit 0／remaining 0；未改系統／帳戶／網路設定、未觸發 UAC。403 不證明帳戶或模型存取。
2. **退出回條補驗完成**：只在本機 reports 保存專用 wrapper，直接使用既有 Python 3.13、合法 finish reason、原 HANDLE 與有界輸出。無模型自測 4/4：自然 exit 0、自然 exit 2、輸出截斷、合成逾時隔離。逾時案例明示 expected forced，僅終止自己的 Job；另一 Job sentinel 自然退出。外層 guardian 自然 exit 0、remaining 0。
3. **第二次真驗收已完成但失敗**：新目錄 `reports/service-acceptance-eventguard-single-test-20261025-02`，執行前另記 `human-approval.json`。台北 16:31:27–16:33:33，外層 125.921 秒。此次 provider turn 完成、CLI 自然 exit 0，但 agent 回報未提供 eventguard_inbox 工具，JSONL 沒有任何 MCP tool call。固定失敗類別 `required_mcp_tools_unavailable`；生成／入列各 1，receive/query/result/ACK 各 0，pending 1、receipts 0、無重複。CLI／worker／host 自然 exit 0，外層驗收自然 exit 2；均有原 HANDLE／Job 回條、remaining 0、無強停。此次沒有 WSA 10013 或 invalid transport，不沿用前次失敗原因。

最小修正：`src/eventguard/agent_dispatch.py` 的單次 inbox MCP 配置新增 `required=true`、`startup_timeout_sec=20`，保留原工具 allowlist／60 秒工具期限；`tests/test_agent_dispatch.py` 增補 TOML／transport／live-test 與 ACK-readonly 契約斷言。此修正意圖是在必要 server 初始化失敗時停止，**沒有證據證明工具缺失根因已修復**，也尚未真 CLI 重驗。

驗證：`py -3.13 -B scripts/verify.py --run-dir reports/verify-required-inbox-20261025-01 --timeout-seconds 300 --module test_agent_dispatch --module test_delivery_consolidation --module test_delivery_validation`。台北 16:37:47–16:38:51，Python 3.13.3，60/60 通過、0 failure/error/skip；source_unchanged=true、guardian 自然 exit 0／remaining 0／無強停、model_calls 0。未重跑完整回歸。

證據：[連線比較](reports/connection-diagnostic-20261025-01/comparison.json)、[wrapper 自測](reports/invocation-proof-20261025-01/selftest-summary.json)、[第二次真通訊](reports/service-acceptance-eventguard-single-test-20261025-02/communication-result.json)、[定向測試](reports/verify-required-inbox-20261025-01/verification-summary.json)。第二次實測執行來源是 `c5401e9`；其後才改 required 契約，`source-state-note.json` 區分執行來源快照與收集時工作樹差異。reports 不提交。

補充無模型交叉檢查：以相同第二次 root／source／inbox／event，透過標準庫 JSON-RPC 呼叫已安裝 SDK server 的 initialize／tools/list，成功列出 receive_event、query_evidence、ack_event；不呼叫事件工具，前後 events 1／pending 1／receipts 0 不變，server 自然 exit 0、remaining 0、無強停。證據：[同範圍 SDK discovery](reports/sdk-inbox-discovery-20261025-01/result.json)。這把剩餘問題縮小到原生 CLI 的 MCP 載入／工具曝光，仍不能判定根因。

**BLOCKERS**：兩次真通訊額度已耗盡；MCP 工具缺失根因未知；原生 CLI 當次 stderr 自帶歷史 rollout metadata 索引警告，操作者未另行開啟那些檔案，但 CLI 內部歷史隔離尚未證明，因此不再新增任何 CLI 命令。後續真驗收需先釐清此界線，並取得新授權。
**DEFERRED**：通用 wrapper 產品化、完整回歸、長期運行及既有桌面聊天／dot 喚醒。舊、新兩件未 ACK 的合成事件原樣保留，不改成已收件或安全結論。

## 2026-10-25：真 CLI 單事件驗收失敗，已修正失敗早停（最新）

本節取代下方「真通訊未執行／仍須重新確認」的現況。基底 `ea00c70`，分支 `feat/local-codex-acceptance`。本輪使用者已明確授權最多兩次、每次一件合成事件／一個 CLI 任務／180 秒；授權與時間已在執行前寫入該次 `human-approval.json`。本輪實際啟動真 CLI 任務 **1 次**，第二次未執行，未 push。

真通訊 **失敗，尚未收件**。執行既有 `reports/service-acceptance-eventguard-single-test-20261025-01`，台北 14:55:19–14:57:01（UTC 06:55:19–06:57:01），102.62 秒內收尾。CLI 自然 exit 1：WebSocket 連線遭 WSA 10013 存取拒絕，轉 HTTPS 後仍連線失敗；沒有舊的 `invalid transport` 錯誤。這只能確認連線受拒，未確認是主機政策、sandbox 或其他來源；未修改網路／系統／帳戶設定，也未提權。

- 同一事件生成／入列各 1；receive／query／結果保存／ACK 各 0；source pending 1、receipts 0、無重複。JSONL 有 thread.started／turn.started，沒有 MCP 工具呼叫或完成回合。模型請求數未量測。
- CLI 自然 exit 1、capture worker／supervisor 自然 exit 0、host 自然 exit 0；各層 Job remaining 0、無強停。host 為 stopped／exited_verified。不是喚醒既有桌面聊天或 dot 的證據。
- 外層包裝器先因相對 `py` 路徑而在啟動驗收前失敗（CLI 0 次），改用同一 launcher 的絕對路徑後才執行上面唯一一次真通訊。包裝器收尾又使用不支援的 finish reason，缺少外層 launcher 的原 HANDLE 退出回條；退出碼記 unknown，未補造。之後對已記錄 launcher／驗收 interpreter PID 的唯讀核對均為 missing。這不替代原 HANDLE 證據；CLI／worker／host 的原回條完整。

發現並修正 `src/eventguard/delivery_validation.py`：唯一任務已失敗且自有程序樹確認退出、dispatcher 為 waiting_task_limit 時，立即走原有 finally 合作停止 host，不再空等 160 秒工作期限。本次實測使用修正前程式，由操作者在失敗後合作停止；修正後只做無模型驗證。新增 `tests/test_delivery_validation.py` 三項 fixture，覆蓋立即失敗、未確認退出繼續等待、成功正常返回。

驗證命令：`py -3.13 -B scripts/verify.py --run-dir reports/verify-service-failfast-20261025-01 --timeout-seconds 300 --module test_delivery_validation --module test_launch_receipts`。台北 14:59:00–14:59:19，Python 3.13.3，33/33 通過、0 failure/error/skip；source_unchanged=true、guardian 自然 exit 0、remaining 0、無強停、model_calls 0。沒有重跑完整回歸；1467/1469 是上一版既有結果。

證據：[真通訊結果](reports/service-acceptance-eventguard-single-test-20261025-01/communication-result.json)、[定向測試](reports/verify-service-failfast-20261025-01/verification-summary.json)。原 JSONL、stderr、SQLite、授權及程序回條均只留本機 reports，不提交執行資料。詳細 event／attempt 與檔案清單見 EVIDENCE。

目前未建立在授權內可解決 WSA 10013 的修正，因此保留第二次額度，避免在相同條件重跑。不得重用本次已消耗目錄。真 receive→query→保存結果→ACK 仍受阻；若後續在本輪授權仍有效時重試，須先有具體改善證據，使用全新 prepare 目錄並另記授權。超過兩次、push 或更改系統／帳戶設定都需再詢問使用者。

## 2026-10-25：合併worktree分支（最新）

本合併提交把feat/local-codex-acceptance（8176095）與claude/eventguard-quota-test-migration（6456759）合在一起，含c8d42e1、3155297。
主checkout fast-forward到本提交後，下方「主checkout仍在3fe8148」「未整合」「最新程式在worktree」等描述即屬過時。
衝突只在HANDOFF、STATUS、EVIDENCE頂部：兩邊段落全保留，較新段落在上，重複的舊標題行只留一份。程式與測試無衝突。
真通訊仍未執行。eventguard-single-test-20261025-01仍須人類重新確認才可--execute。未push。

## 2026-10-25：目標增量更新（最新閱讀入口）

最新程式在`.claude/worktrees/eventguard-handoff-increment-721d6d`，HEAD3155297；主checkout仍是3fe8148，未整合。
本輪已核對兩處Git與既有驗收證據。預算測試遷移、event_source綁定、背景stop修正均已完成，不重列為待辦。
最新落地目標見[MAINTENANCE_GOAL](docs/MAINTENANCE_GOAL.md)。最新完整交接讀worktree的HANDOFF/STATUS/EVIDENCE；下方較早checkpoint屬歷史。
剩餘順序：確認整合兩提交；重新確認eventguard-single-test-20261025-01；確認後才跑一次真通訊。這次只更新目標，不構成執行授權。
本輪未合併、未啟動模型/測試/背景、未push。交接修改保留未提交，不做文件單獨commit。原App goal仍paused。

## 2026-10-25：目標增量更新（接續04:50交接）

主checkout3fe8148、worktree3155297已增量核對，未整合。新驗收仍prepare-only：manifest無execution、未入列、無capture-start。
預算測試遷移、event_source綁定、stop暫態修正及完整無模型回歸已完成，從剩餘目標移除。
最新目標見[MAINTENANCE_GOAL](docs/MAINTENANCE_GOAL.md)。本輪只更新文件，未重跑測試、未啟動模型、未新建reports、未commit或push。
原App goal仍paused；不新建或假標complete。整合與真驗維持04:50交接的確認關卡，不把使用者貼回交接內容當新模型授權。


## 交接暫停：2026-10-25 04:50（台北時間，最新）

使用者要求交接，停止開發。目標停在blocked，未標complete。
最新程式在worktree分支`claude/eventguard-quota-test-migration`，HEAD 3155297（含c8d42e1）。未push。worktree路徑`.claude/worktrees/eventguard-handoff-increment-721d6d`。
主checkout分支feat/local-codex-acceptance仍在3fe8148，追蹤檔乾淨；未追蹤`.codex-remote-attachments/`、`docs/research/`保留。整合c8d42e1與3155297需人類確認（主checkout乾淨，可fast-forward）。
本交接段在worktree內未提交（HANDOFF、STATUS、EVIDENCE），刻意不做文件單獨commit。
真通訊：使用者曾授權eventguard-single-test-20261025-01，但在啟動前改為要求交接。未執行。manifest無service_execution、未入列、無模型任務。
授權紀錄`human-approval.json`已標execution_started=false；下一位執行前必須請人類重新確認。
沒有本工具程序在執行。正式monitor desired off；正式agent service未啟動；App未執行。

## 無模型工程收尾與真通訊準備：2026-10-25 04:10（台北時間）

依新目標推進。唯讀核對與checkpoint一致：HEAD 3fe8148；舊事件仍pending、receipts0；continuation仍terminal_failed_no_retry；monitor desired off。
完整回歸（3fe8148，主checkout）：1460測試，1458過、0失敗、2略過（symlink不可用）。guardian自然exit0、remaining0、無強停、model_calls0。無失敗需修。
Event範圍一致：App新增明確`event_source`綁定。只限test範圍、`--idle`、不通知；綁定時不採集，開始／恢復回`monitor_outside_bound_event_source`。
CLI `run --event-source`、`events list/detail/set-status --event-source`、Web事件頁、十工具MCP及處置保存都讀同一source。status與capabilities回報`event_scope`。
Agent status另回`event_source_matches_application`，不再讓Agent頁與事件清單默默指向不同source。綁定source的投遞查詢只在agent service指向同一source時讀它的state。
小清理：GUI補`waiting_task_limit`標籤。`operations._budget_status`保留：已無呼叫者，但它是測試圍住歷史預算的單一接縫；刪除需大量改測試，無產品收益。
驗證：新測試8/8；相關22模組284測試中一個CLI參數斷言隨新契約更新後17/17。最終整套（本批原始碼）：verify-full-20261025-03為1468測試，1466過、2略過、0失敗；guardian自然exit0、remaining0。
前一輪-02有1項間歇失敗：test_operator_monitor_owner的SDK stop回background_owner_changed。該模組單獨重跑2次24/24通過，-03整套也通過。根因已查：status讀檔暫時失敗（raw_error_omitted、無run_id）被stop等待迴圈當成owner更換。已改為寬限期內繼續等待；迴圈內本就不送訊號，寬限期後仍保守回busy。
新增測試覆蓋暫態後退出及整段讀不到兩種情況。背景相關5模組101/101；修正後整套verify-full-20261025-04為1469測試1467過、2略過、0失敗，guardian自然exit0、remaining0。
真SDK：已安裝MCP SDK對綁定App呼叫十工具；list_events／inspect_event只見綁定事件，預設範圍事件查不到；start_monitor受阻。
瀏覽器：內建瀏覽器看到綁定source提示、1件綁定事件與MCP操作受阻紀錄。App自然exit0、殘留0。兩者都是合成資料，不是實機或真收件。
真通訊準備：新目錄`reports/service-acceptance-eventguard-single-test-20261025-01`只prepare，未執行。候選CLI SHA256符合，版本codex-cli 0.164.0-alpha.11.1，login status回報已登入；原始輸出未保存。
授權請求在該目錄`AUTHORIZATION_REQUEST.md`。目標停在等待人類授權；不得自行`--execute`。
前批證據也已複製到主checkout `reports/`（verify-budget-baseline-20261025-01、verify-budget-migration-20261025-01〜03），位元組一致。
仍需人類決定：真通訊授權、推送、研究稿與附件、跨source全域阻擋、選配長期驗證、worktree清理。

## 預算測試遷移：2026-10-25 02:30（台北時間）

接手後增量推進。只改測試；未改src、設定或runtime。未commit、未push。
位置：worktree `.claude/worktrees/eventguard-handoff-increment-721d6d`，分支`claude/eventguard-quota-test-migration`，基底f5810b5。
已帶入主checkout三份交接文件的未提交修改，位元組一致。主checkout本身未改，HEAD、diff與未追蹤附件／研究稿都照舊。
唯讀核對與交接一致：grant仍consumed；事件仍pending、receipts0；continuation仍terminal_failed_no_retry；正式monitor desired off；交接後無新runtime或reports。未啟動採集、派送、App或模型。
遷移前基線：受影響12模組211測試，148過、3 failures、59 errors。其中56個是patch已移除的`agent_dispatch.open_authority`。
`tests/budget_fixtures.py`改為無額度契約。短OS-create gate移到暫存目錄。本程序及capture worker都圍住歷史預算：讀取即失敗；結束時核對sentinel未變。
過時日額度測試改測新契約。保留耐久、併行與停止覆蓋：
- launch intent先落盤；同目錄不重用；gate busy／unavailable可見。
- pause／stop在各閘門前不啟動；最後pre-spawn暫停留not_started紀錄與skip證據。
- spawn結果不明時保留started紀錄；後續run拒絕；pending不丟。
- 有限max_tasks只等待不再啟動。它是單次run界線，不是日額度。
- 同一watch連續6事件、跨入口6次啟動都無五次上限；每事件三次上限保留。
另修正GUI、operator status、公告status仍斷言`agent_budget`／`daily_remaining`／「每日最多5」的舊測試。
結果：16模組291測試，290過、0失敗、1略過（symlink不可用）。guardian自然exit0、remaining0、無強停、model_calls0、source_unchanged。
範圍只有fixture、fake CLI及真Windows Job。不是全套回歸，也不是真模型或真收件。
證據：worktree內`reports/verify-budget-migration-20261025-03`；基線`reports/verify-budget-baseline-20261025-01`。中途01、02兩輪不作通過證據，原紀錄保留。
仍未完成：真receive→query→結果→ACK與自然退出（需新的人類有限授權）；Event頁自訂source綁定；全套回歸；24小時／重開機；桌面閒置喚醒。
觀察：`operations._budget_status`已無呼叫者。跨source全域阻擋隨authority移除；本批未加測試肯定或否定。

## 交接暫停：2026-10-25 00:50（台北時間）

本專案已收斂至可恢復交接點，goal為paused，未宣稱完成。停止開發，等待交接。
分支feat/local-codex-acceptance；HEAD f5810b52064fbde8f5d59928ff139277867f2165。
核對前追蹤檔乾淨；交接後只留HANDOFF.md、STATUS.md、docs/EVIDENCE.md未提交修改，不做文件單獨commit。
未追蹤2張附件及11份研究Markdown保留，未加入Git。未push、未新建交接資料夾或reports。
正式monitor stopped/exited_verified、desired_enabled=false；正式agent service not_started/not_recorded。
原合成service stopped/exited_verified，單一事件仍pending、receipts0；capture-start回條仍只有1份。
live App與同run test App均application_not_running；主專案test observer為scope_invalid。未停止任何程序。
本輪只有唯讀狀態核對及文件保存。沒有新模型、採集、測試、CLI執行或背景程序。
Python3.13.3/MCP SDK1.6.0可匯入。歷史CLI路徑已消失；新候選bin/2993767bd1dfb009/codex.exe存在，未執行或驗登入。
單次真通訊仍失敗，transport修正只有native metadata及契約證據；不得寫成真收件成功。
已完成/未驗證/阻擋/下一步及完整接手Prompt見HANDOFF.md頂部。該段取代下方所有過時預算/跨日等待/授權描述。
本機忽略的reports/data與設定不能靠Git clone重建；換帳號不移植Codex home或憑證。

## 單次通訊實測：2026-10-24（最新）

本次未能通訊。真正原生 CLI 已啟動一次。載入設定時退出：
`Error loading config.toml: invalid transport`，位置為 `mcp_servers.eventguard_test`。
CLI exit 1。驗收 exit 2。耗時 17.55 秒。未進入 provider turn，沒有模型回覆。
同一合成事件生成／入列各 1；receive、query、結果、ACK 均 0。事件仍 pending，無重複。
CLI、supervisor 與 host 已退出。無強停、無殘留。不自動重試；單次授權已消耗。

最新人類指示取消 App 的每日預算限制。通訊路徑不再讀取或改寫歷史預算。
歷史 bootstrap 與帳本保留，前後 SHA256 相同。舊 waiting_budget_day 已被取代。
正常無事件不呼叫模型。這次驗收仍限定最多一個 CLI 任務及 180 秒。

修正停用 MCP entry 的 transport 定義，並新增無模型契約測試。
修正後的真模型通訊未重驗。後續受支援的 native mcp get 設定解析 exit 0；舊 exit 2 查核保留。
後續唯讀 test App 的真 SDK MCP status 與 GUI 已對上同 event/attempt、CLI失敗及pending1。這是顯示失敗證據，不是收件。
App已自然exit0，無殘留；source/inbox位元組未變。新增模型任務0，總CLI測試仍1。
證據：`reports/service-acceptance-eventguard-single-test-20261024-01/communication-result.json`。
原 stderr、CLI JSONL、SQLite、intent、各層退出回條與歷史失敗均保留。
只提交程式、測試與文件。不提交執行資料。完整歷史見 docs/EVIDENCE.md。

更新：2026-10-24，UTC+08。分支：`feat/local-codex-acceptance`。本批基底：`9903ad5`。

EventGuard 可獨立採集、比對、保存及顯示。正常等待與查閱不呼叫模型。
CLI、Web及十個選配MCP工具共用Application與事件庫。MCP斷線不關閉應用。

## 使用

`.\EventGuard.cmd run` 前景啟動採集、Web與通知。
`.\EventGuard.cmd run --idle` 只開控制介面。預設 `http://127.0.0.1:8765`；埠被占用可指定 `--port 8877`。

已開啟應用後，使用 `app status/start/pause/resume/stop/shutdown` 或GUI/MCP操作。
stop只停採集，介面仍可查詢及再次開始。shutdown提出關閉要求，實際退出另核對。
GUI顯示真實狀態、最近動作、CLI/GUI/MCP來源與失敗原因。

stdio固定為observer。沒有App也能列工具，但回blocked，不建立第二owner。
明確讀status/capabilities可重新核對同root/namespace。變更不自動轉新instance；舊操作ID仍受保護。
設定、工具載入、收到事件、閒置喚醒分開。操作指南見 [APPLICATION_MCP](docs/APPLICATION_MCP.md)。

## 本批功能

- app文字模式以中文顯示採集、來源、原因、版本與可用操作。JSON/API不變。
- 通知先耐久保存意圖。回條不明時顯示未知，不盲目重送。事件仍pending。
- 公告頁、App status與公告事件詳情顯示有界公開來源、時間、新鮮度與適用性。
- 不公開本機inventory/facts/path/PID/原始evidence。自動派送仍只有既定七欄。
- 新增NVIDIA CSAF停用範例。壞子項與好子項隔離；partial不洗成success，不覆寫完整cache。
- 公告及十類對抗文字都只作資料。未知不變安全。處置狀態不ACK。
- 專用有限agent派送明確停用完整App MCP，避免擴大七欄profile。

## 實際驗證

相關測試、真SDK stdio/SSE、真Windows自有Job、原收件/ACK恢復與真瀏覽器均已執行。
瀏覽器確認同一instance、MCP處置同步、GUI改已處理後刷新保存；兩事件仍pending、ACK零。
通知中斷與滿載恢復、重連、舊operation fencing及預算政策已定向驗證。
一般使用者真Windows通知要求已接受，服務重建不重送，自身視窗已關閉；人是否看見未驗。
先前sandbox通知圖示skip及示範失敗均保留。沒有把fixture升格為主機安全或真agent驗收。
測試數、命令、時間、Python及證據只見 [EVIDENCE](docs/EVIDENCE.md)。
本機新功能證據在 `reports/application-lifecycle-001`、`reports/notification-intent-001`及`reports/nvidia-advisory-001`。
本批測試/示範程序均有退出證據。未強停、未啟用正式長期監看、未改正式控制或預算。

## 選配與未驗證

公開Codex入口研究見 [AGENT_EVENT_DRIVEN](docs/AGENT_EVENT_DRIVEN.md)。普通本機桌面任務閒置喚醒仍未驗證。
OpenOctopus提案與工作包見 [OPENOCTOPUS_EVENT_PROTOCOL](docs/OPENOCTOPUS_EVENT_PROTOCOL.md)，尚未在外專案實作。
既有eventguard-app入口已加Python -u，範圍與其他MCP不變。
本聊天隨後自動載入十工具。原生status與CLI/Web metadata核對同一閒置App。
原生shutdown提出要求後，私有Job原生exit0、Web/SDK退出，無殘留。應用關閉後observer回blocked，不自行冷啟動。
目前沒有測試App留存。MCP observer由Codex管理。這不是事件接收或閒置喚醒證據；未要求使用者重開。
真模型驗收需另核定一次有界範圍；本批產品模型為零。既有dot追蹤未停用。
未做七來源當前主機掃描、24小時soak或重開機。不宣稱全天候通過。
不建立服務、排程、自啟、proxy或新登入。不下載安裝、不提權、不推送。
