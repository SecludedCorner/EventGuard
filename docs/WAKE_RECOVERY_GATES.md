# 歷史研究：同一聊天喚醒與登入恢復

**2026-10-23最新方向：本機資安監測、耐久資料與agent讀取／查證優先；本頁不是日常監看的前置關卡。** 使用者已批准一次metadata探測，但沒有批准登入任務註冊；不再為此阻擋產品開發或重問排程。

批准後的proxy helper因收尾原因碼不符enum而exit1，沒有保存連線結論／child退出回條；原失敗保留於本機reports，不能宣稱成功或自然收尾。依最新方向不再重試這項旁支。當前程式已有變更，下列舊排程SHA失效，僅作歷史審查紀錄，不得據此安裝。

查核：2026-10-23；程式基準`af839b36a4f43efbc5e273680ba2f597edb93df1`。本頁不啟用監看、模型、排程或服務。正常操作方法見[接線指南](CONNECT_AGENT.md)，測試與原始證據入口見[EVIDENCE](EVIDENCE.md)。

## 同一聊天：先證明目的地，再發事件

本主聊天已能實際呼叫正式MCP，隔離合成事件的receive／ACK亦有證據；這是活動回合取用。剩餘要求是：程式空閒等待、事件先耐久保存、只有事件才讓**目前同一聊天**開始處理，不需要使用者再發訊息。

| 入口 | 已核實 | 尚缺什麼 |
| --- | --- | --- |
| 普通stdio MCP | 目前聊天的工具與實際回傳可用 | 未查到足以證明其通知會啟動閒置聊天回合的契約 |
| `codex queue --thread UUID --message TEXT` | 官方文件與現有原生CLI help均支援既有session | 是否連到目前桌面實例、是否喚醒idle回合、事件與回條關聯均未實測；送出會涉及模型批准 |
| `codex app-server proxy` | 既有CLI help寫明連到已運行的control socket，可指定`--sock` | 需先以唯讀metadata確認是正確聊天；沒有另起app-server或daemon |
| `turn/start` | 官方明確開始generation | 要先有已驗證的目的地、範圍與模型批准；不是可直接套用到任意桌面聊天的證據 |
| 定時heartbeat／新CLI／新聊天 | 各有不同用途 | 不符合本次同一聊天、無事件零模型的完成條件，不作替代 |

依據：[官方CLI commands](https://learn.chatgpt.com/docs/developer-commands)、[app-server協定](https://learn.chatgpt.com/docs/app-server)、[排程與支援事件](https://learn.chatgpt.com/docs/automations)。文件存在與本機help均不證明目前桌面control socket可用。普通hook、雲端MCP Events也沒有在本專案接成此聊天入口；不新增代理層、HTTPS服務或憑證。

本機已備妥單次探測`reports/wake-queue-research-001/proxy_probe.py`：只啟動受私有Job管理的proxy client，使用既有預設control socket；發initialize及精確目前thread/read，`includeTurns=false`，不resume、不列其他聊天、不送queue／turn、不啟動server、不讀憑證或原始session檔。只保留ID是否匹配、runtime state、是否無turn內容與退出回條；無事件內容或對話歷史。

**該探測尚未執行。** 自動核准審查認定thread metadata仍屬私人Codex session存取，超出既有授權，因此拒絕執行。需人類明確批准這個精確唯讀範圍；不以其他程序或間接讀檔繞過。審查與未執行證據留本機`proxy-approval-block.json`。

metadata探測成功後，仍需先完成有界合成驗收設計與模型批准，不能直接送正式backlog：先觀察idle，程式入列一件synthetic，最多送一次固定通知，從MCP取事件；核對同chat／event／query、ACK及來源receipt。外部訊息／事件仍是不可信資料，不當成系統指令；傳輸接受或文字宣稱成功不代替工具與SQLite證據。回應遺失時保持uncertain，不自動重送；每日耐久預算與未知退出閘道不能因新入口或換目錄重置。

## 登入恢復：只註冊，不解除暫停

一般使用者真查詢已確認本安裝專屬任務不存在：已確認根資料夾，GetTask得到HRESULT80070002。sandbox身分的GetFolder失敗另保留unknown，沒有混作一般使用者的不存在證據。沒有建立、Run或修改任務。

當版可審查方案位於本機忽略目錄：

- `reports/recovery-gate-001/schedule-review-normal-user/plan.json`
- `reports/recovery-gate-001/schedule-review-normal-user/task.xml`
- SHA256：`03b312cd6e08df1517c908956d0c38864c7bc2e715a4f144ab290311d04b35c6`

批准範圍僅一個目前使用者ONLOGON任務；InteractiveToken、LeastPrivilege、PT0S，`start_now=false`，不使用密碼、UAC或服務。來源／設定／playbook與Python執行檔均綁定，變動即須新計畫；Create無覆寫旗標，外來同名任務不覆蓋。唯讀dry-run和離線契約已驗證，不能升格為實際註冊或重開機通過。

**目前保存的是explicit_stop／enabled=false。註冊本身不解除暫停。** 未來人類明確Start並保留enabled後，登入觸發才恢復監看；若Pause，之後登入仍維持停止。登入前監看不在此範圍。實際登出／OS重開機由人類另行安排，需比對monitor_gap、來源freshness、pending／ACK與Job退出；不能只看排程存在。

建立排程仍需人類批准本SHA。本輪不使用`--start-now`；若將來要立即啟動，需另外明確授權且不自動沿用舊暫停前設定。24小時soak與真狀態注入依既有[soak](SOAK_PLAN.md)及[Windows驗證計畫](WINDOWS_VALIDATION_PLAN.md)另行核實。
