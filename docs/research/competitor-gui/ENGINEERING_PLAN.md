# EventGuard 競品研究對照與開工規格

日期：2026-10-28（台北）；產品來源基準 `f86254bb0393b606b1202b370efa18b35f649e8e`。
`f1ed1e07f884e961e96aaffa3cbf9cf51544578d` 只新增研究文件，產品來源 240 個 hash 未變。
本頁是 [MAINTENANCE_GOAL](../../MAINTENANCE_GOAL.md) 既有佇列的規格附件，不建立第二個工作追蹤器。
廠商結論及 F／S／G 來源編號見 [公開研究](README.md)；以下所有切片均為 **未實作提案**。

## 現況核對：可重用的基礎與真缺口

| 面向 | 目前實作／測試證據 | 缺口與可借鏡來源 |
| --- | --- | --- |
| 首屏 | [web.py](../../../src/eventguard/web.py) `refreshNotice` 已查 new/high、new/critical 各自 total，已有醒目提示；不是完全沒有摘要。 | 兩次獨立讀取，不是共同 snapshot；提示不能直接進入對應合併清單，來源缺口留在另一頁。借鏡 F2／S1 的逐層縮小。 |
| 清單 | [catalog.py](../../../src/eventguard/events/catalog.py) `list` 先對全庫套 severity/source/status，再 COUNT、LIMIT/OFFSET；穩定以 created_at/event_id 排序。`test_event_catalog` 已測跨頁、implicit new、namespace、ACK 分離。 | Web 每頁 50 筆；無時間區間／多選／URL 導航還原。顯示 observed_at 與排序 created_at 不是同一時間；新增時間篩選須明定語意。S1 分組不是現有能力。 |
| 詳情 | Web 同頁 detail、guidance、renderInvestigation 與獨立 delivery 查詢已存在；原始 JSON 放 details。 | 多組內容仍是長段文字／JSON；回清單與鍵盤焦點、五秒更新下選取穩定性需實測。F1／S1 支持「保留記錄上下文」。 |
| 關聯 | [investigation.py](../../../src/eventguard/events/investigation.py)：同 host scope、同來源、穩定程序或持久項身分，前後 900 秒；候選 256、成員 16；缺口／截斷明示。`test_event_investigation`／`test_investigation_diagnostics` 有負控制及 hash／race 拒絕。 | OS 帳戶 owner UNKNOWN；跨來源因果、程序樹、攻擊鏈未建立。不能仿 F4／S1 圖形來宣稱具備 Storyline 或 ThreatGraph。 |
| 七來源 | [source_status.py](../../../src/eventguard/source_status.py) 回傳 last_collected_at、last_success_at/state、saved_status、status、freshness、reasons；`test_source_success_history` 驗證失敗保留歷史成功及唯讀。 | **Web `sources()` 未呈現 last_success_at/state 或明列 freshness**；只有公告 `advisorySource()` 顯示最後成功。README／操作指南宣稱七來源可見，與本基準程式不一致。先做 G01。 |
| 操作歷程 | [activity.py](../../../src/eventguard/activity.py) 已有固定 actor／operation、結果、耗時、截斷與 unavailable；最多 256 列／2 MiB。Tk [gui.py](../../../src/eventguard/gui.py) 已呈現 activity；Web 有最近一次 last_action。 | 不應宣稱完全沒有歷程；現有 activity 不是防竄改或已認證使用者稽核，也不含每次人工處置與案件修訂。借鏡 G4A／S4，另定事件歷程契約。 |
| 保存 | [store.py](../../../src/eventguard/events/store.py) 的 event_dispositions／event_investigations 是每事件最新一列，更新覆蓋；有 pending／ACK 容量預留。 | 不能回看舊處置／案件版本；新增歷史會影響容量、原子性與保留政策。不可無界 append。 |
| 介面並存 | Web 是目前 README 主入口；Tk 的 [gui_presenter.py](../../../src/eventguard/gui_presenter.py) 對已載入 view 做 severity／delivery 篩選。 | Tk 與 Web 篩選語意不同，不把 Web 全庫分頁證據套到 Tk；本期先改 Web，之後逐介面驗收。 |

目前驗收只支持既有範圍：[EVIDENCE](../../EVIDENCE.md) 的本機全庫 1636 run／1633 pass／3 skip 是先前來源紀錄；本研究新跑 74/74 與 29/29 是重疊定向，不相加。served UI 測試不執行 JS，不是瀏覽器競態證明。
[WINDOWS_VALIDATION_PLAN](../../WINDOWS_VALIDATION_PLAN.md) 保留原生 listeners partial／111 身分缺列／21 error；先前診斷準備包已 superseded。研究、GUI 或 fixture 通過均不能改寫此結果。

## 優先順序與可獨立驗收切片

每列是下一輪工程規格，完成後逐單元 build／相關測試／普通 commit push；預估 diff 若超過約 200 行，按列內 A/B 分拆，不把完整功能塞進一次提交。
「一般本機工程」只指既有授權可做的離線實作／synthetic 驗證；敏感前置仍需精確授權。本輪沒有實作這些切片。

| 順序／ID | 使用者價值與具體範圍 | 檔案／契約觸點 | 依賴、風險與必要授權 | 驗收出口 |
| --- | --- | --- | --- | --- |
| 1 / P1-GUI-001（G01，READY） | 七來源卡片補最後成功與新鮮度，修正文檔與畫面落差。 | web.py `sources()`；source_status 1.0 只讀現成欄位；test_application_ui_state；LOCAL_UI_ACCEPTANCE。 | 無新 API／DB／採集；風險是歷史成功蓋過目前 denied/stale。一般本機工程。 | 下節六條必過；不靠搜尋全 JS 的「最後成功」字串作驗收。 |
| 2 / P1-GUI-002A/B | 先顯示事件頁來源缺口，再把現有 new/high、new/critical 提示變成可點的清單入口。 | web.py；A 共用 `/api/sources` projection；B 沿用兩個單 severity 篩選入口，不先新增複合 API。 | 依 G01；HTTP 失敗／舊回覆不能留綠或清掉事件；不在 GET 觸發採集。一般本機工程。 | 7 個唯一來源／缺項／重複／空／錯誤／過期 fixture；全正常也只稱觀測成功；點數字後 filter、total、首列吻合，分頁回 0。 |
| 3 / P1-GUI-003A/B | A 保存可分享的三篩選及頁碼；B 事件詳情返回原清單與焦點，保留調查上下文。 | web.py URLSearchParams/history、events/detail；catalog 既有 filter allowlist；test_event_catalog／UI vectors。 | 依 G02；URL 只放列舉篩選與有界頁碼，不放原事件內容／私密搜尋。一般本機工程。 | reload/back/forward 恢復；壞值固定錯誤；跨頁選取、快速切事件與慢回覆不串資料；鍵盤可往返。 |
| 4 / P1-INVEST-004A/B | A 改善已保存調查呈現；B 把每條關聯理由與缺口放在相關觀測旁。 | web.py `renderInvestigation`；investigation.py 固定 schema／limits；兩組 investigation tests。 | 可與 G03 後段分開；不放寬關聯規則。來源缺失仍 UNKNOWN；一般本機工程。 | 同 event/hash/as_of 重開一致；PID 重用／異來源／缺 entity 不連線；超限可見；本階段用時間線，不新增推論攻擊圖。 |
| 5 / P2-HISTORY-001A/B/C | A 定義有界處置歷史與容量；B 原子保存 old/new 狀態；C Web 展示事件歷程。 | store.py `set_disposition`、catalog.py、application.py operation/source；storage_policy.py；STORAGE_RETENTION；test_event_catalog。 | 依事件語意穩定；新增 DB 層，需遷移／回復規格先審。一般本機工程；無新系統處置。 | 狀態與歷史同交易、失敗全部 rollback；重複 request 不增列；保留限額／pending／ACK reserve；舊資料顯示「此前未記錄」，actor 未認證明示。 |
| 6 / P2-INVEST-REV-001A/B | 案件修訂可回看「何時按哪些證據變更」，不覆蓋歷史。 | store.py `save_investigation`、catalog saved view、investigation schema/hash、storage_policy；test_event_investigation。 | 依 G04／歷史容量決策；與處置歷史分表、分用途。一般本機工程；不補造舊版本。 | A 只完成有界 schema／read compatibility；B 再接寫入／呈現。member 消失或 hash 變更顯示 UNKNOWN，不能洗掉舊 revision；容量不足保持舊案與 pending。 |
| 7 / P2-UX-001 | 衡量上述 GUI 是否更容易理解，建立可重複任務結果。 | LOCAL_UI_ACCEPTANCE、tests/fixtures、reports 新專用驗收目錄。 | 依 G01–G04；合成瀏覽器工程可做；邀人／廠商租戶比較另有授權。 | 六情境完成率、時間、誤判安全次數、點擊／返回數；800/1280px、200% zoom、鍵盤焦點；保存匿名結果，不保存私人截圖。 |

G02 的聚合先避開不必要的新後端；未來需要同一時點多分類總數時，另做 catalog 單一唯讀交易與 as_of／count_state 契約，不能把兩次 HTTP total 包裝成原子快照。
時間區間／任意文字搜尋／bulk actions 暫不納入 G03，避免一個切片同時改 schema、查詢與敏感操作。

## 第一個可直接開工的規格：P1-GUI-001

問題：`source_status()` 已保存歷史成功，但 `web.py:sources()` 沒有把它渲染出來。相關文檔說可核對，不足以證明畫面已具備。
完成定義：七來源每張卡片可讀出最後採集、最後成功、原始結果、目前有效狀態與新鮮度，且歷史成功不掩蓋缺口。

實作邊界：

1. 只修改 `sources()` 的 presentation，可抽一個小純函式；沿用 textContent／node，不插入來源 HTML。
2. `last_success_state == known` 且時間有效才顯示該歷史時間；否則明示「未知／尚無成功紀錄」。不能以 last_collected_at 或現在時間補值。
3. 明列 freshness 的 fresh/stale/unknown；保留 saved_status 與目前 status。零列成功只表示本次限定範圍沒有觀測列，不宣稱安全。
4. 首次只改既有來源卡片；不改首頁、catalog、SQLite、collector、通知、模型、ACK、allowed_actions。
5. 新測試指向七來源容器／特定 source card，防止公告卡片既有 `last_success_at` 造成假通過；更新操作指南只寫已實際驗過的呈現。

六項驗收（全部 synthetic，不查主機）：

| 案例 | 必須看見／保持的結果 |
| --- | --- |
| 最近成功後又 denied | 原最後成功時間仍在；目前拒讀與原因仍在，沒有成功覆蓋拒讀。 |
| 舊 ok 但 freshness=stale | 原結果成功與目前過期分列；不得沿用「目前成功」綠色結論。 |
| 從未成功／缺時間／state unknown | 明示未知；不回填本次採集時間，不顯示 1970 或現在時間。 |
| 無效／未來時間 | 使用後端 unknown 語意，前端不把可 parse 的未來日期當成功證據。 |
| 合法成功且 row_count=0 | 可顯示歷史成功與零列，保留「不代表主機安全」。 |
| 來源／原因含 HTML 樣式文字 | 只顯示文字；三次 GET 前後持久檔案 hash 不變、pending／ACK 不變、native/model calls 0。 |

定向命令（實作後，用全新輸出目錄）：

```powershell
py -3.13 -B scripts/verify.py --run-dir reports/verify-gui-source-cards-NEW --timeout-seconds 180 --module test_source_success_history --module test_application_ui_state
```

另依 [LOCAL_UI_ACCEPTANCE](../../LOCAL_UI_ACCEPTANCE.md) 在專用合成 namespace 由私有 Job 啟動本機頁面，真瀏覽器核對上述卡片文字、鍵盤與窄頁；不使用預設會採集的 `run` 製造 fixture。合作停止後核對原 Job 自然退出／remaining=0。靜態測試只能當契約測試，瀏覽器驗收另留回條。
提交前按既有 package_candidate 流程 build 精確來源 SHA；記明 build 是否包含尚未提交檔案，來源 hash 綁定後只 stage 本切片檔案。預估產品／測試 diff 約 80–140 行，超限先拆 presenter 與呈現驗收。

## 原生覆蓋、偵測效果、真環境驗證：各走自己的關卡

| 軸線／優先項 | 必要前置與觸點 | 驗收與權限邊界 |
| --- | --- | --- |
| 原生 / 既有 P2-OS-DIAG-002 | 重新 prepare 當前 source/hash 綁定的最小 listeners 診斷包；scripts/validate_windows_listener.py、collectors/native.py、winapi.py；沿用 WINDOWS_VALIDATION_PLAN。 | 舊批准已耗用、舊包 superseded；另獲一次具名範圍批准才能採集。完整四表／身分／錯誤分類及退出各核對；unknown／partial 不能變成安全。此軸不阻擋離線 GUI。 |
| 偵測 / P2-DETECT-001（先定 corpus） | rules/detector.py、configured.py、schema.py；先對每條規則列可觀測欄位與良性／異常真值。測試資料只用合法合成案例，不新增惡意樣本或主機攻擊。 | 報 TP/FP/FN、未觀測分母、版本與每條規則結果；關聯正確率不得叫惡意偵測率。資料不涵蓋的攻擊保持未驗；安全研究／實機攻擊需要新範圍。 |
| 真環境 / P2-VALIDATE-001 | 先凍結版本與事件範圍，再定 24h／重開機與 GUI 人類任務方案；soak.py、現有驗收文件。 | 真機監看／長跑／重開機各需有效授權；量測事件遺失／重複、p50/p95、CPU／RAM／磁碟及恢復，不拿短 fixture 或舊版證據替代。 |
| 受控回應 / DEFERRED | 如日後要隔離／終止／rollback，先有具名目標、最小動作、批准、可回復及結果驗證；目前 allowed_actions 空。 | UI 按鈕或 severity 不授權；本研究沒有增加系統處置能力。不要為模仿 S1 圖片而加入動作。 |

## 「更好」如何被證明

先比較 EventGuard 變更前後，同版本 fixture、同螢幕尺寸、同任務：找新增高嚴重度、辨識拒讀、找最後成功、追溯一條關聯、辨識證據缺失、區分 handled 與 ACK。
探索性可用 5 位同意參與者、交錯任務順序，記完成／放棄、每題時間與錯誤；目標是降低找資料步數且不增加誤判安全。小樣本只報描述性結果，不作統計優越性宣稱。
只有取得兩家合法租戶及可比資料，才做跨產品測量；固定版本／模組／權限／資料時窗／保留政策／端點資源與 analyst 熟悉度。沒有 access 記 blocked，不能以公開 demo 的秒數當對手測量。
本任務完成的是可查證研究、缺口與規格；上表沒有任何產品切片因文件落地而變成 DONE。
