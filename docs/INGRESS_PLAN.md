# EventGuard 真正 agent 事件入口調研與接線計畫

研究日期：2026-10-22 UTC。狀態：**官方路徑已辨識；接線尚未實作；真正 agent 喚醒與端到端驗收未完成**。

本文件僅提出可審查的整合方案；不增加憑證、外部 webhook、常駐程序或模型呼叫，也不構成未來傳輸或處置的授權。本輪只有官方文件與公開 CLI help 調研，沒有讀登入檔、原始 sessions 或秘密，沒有啟動 app-server、列出任務或傳送實際訊息。

## 1. 結論與適用範圍

最符合「外部程式異常才喚醒長期任務」的官方候選為 **MCP Events → 已訂閱的 Work Cloud 聊天或 dot**。它會把伺服器事件送進訂閱聊天；是否能在使用者帳戶啟用，仍須實際確認平台、workspace 與 plugin 權限。這不能直接宣稱適用於目前任意一個本機 Codex 桌面任務。[官方 MCP Events](https://developers.openai.com/plugins/build/mcp-events)

另一條具體候選為 **自管程式控制 Codex app-server，使用 `turn/start` 啟動該整合所管理 thread 的新回合**。這是另一個自管 agent 整合；官方仍將 app-server 標為實驗性、不支援正式生產工作負載，不能與「喚醒既有桌面任務」混稱。[官方 app-server](https://learn.chatgpt.com/docs/app-server)

| 對象或入口 | 已核實範圍 | 目前判定 |
| --- | --- | --- |
| 既有普通本機 Codex 桌面 task | 尚未找到適用該 task 的完整官方入站契約與實際喚醒證據 | **未證實；不可宣稱可喚醒** |
| Work chat，桌面選 Cloud，或 dot | MCP Events 文件列為支援的訂閱目的地 | 首選候選；須設定、批准、實測 |
| 自管 app-server thread | 官方有明確 `turn/start` 請求與 turn 通知 | 備選候選；不是自動接入既有 task |
| 本機 `codex queue` | 公開 help 有向既有 session 排訊息的介面 | help 未證明閒置時自動啟動回合，未送訊息驗證 |
| EventGuard SQLite／JSON 落盤 | 只代表本機保存 | 不是傳輸、接收、喚醒或處理 |

正常狀態只讓程式等待或採集，不啟動推理回合。事件出現才要求平台啟動 agent；收到事件後才執行限額內的唯讀診斷。這是本方案的工程目標，尚非完成狀態。

## 2. 首選：MCP Events 訂閱聊天

官方機制要求 MCP 2.0 `2026-07-28`、plugin 中的 MCP server、持久訂閱，以及向平台 callback 的 HTTPS 投遞。伺服器宣告 `events` 能力，實作 `events/list`、`events/subscribe`、`events/unsubscribe`；ChatGPT 訂閱時提供 callback URL 與簽章秘密。伺服器先驗證 callback，再發送簽章事件；ChatGPT 在訂閱聊天接收並依指示執行。這是事件推送，不是 AI 定時查詢。[官方 MCP Events](https://developers.openai.com/plugins/build/mcp-events)

### EventGuard 建議接線（設計，未實作）

```text
本機 collectors → rules → durable outbox
                              │ 最小事件摘要
                              ▼
經批准的 EventGuard MCP Events server／bridge
   ├─ 持久訂閱、callback 驗證、簽章與投遞重試
   ├─ readonly diagnostic tools（需另外完成受控連線）
   └─ 平台提供的 HTTPS callback
                              ▼
              已訂閱的 Work Cloud chat／dot
                              ▼
agent 唯讀查證 → 證據與判斷 → 必要批准 → 驗證／結案
```

bridge 與本機採證端的部署位置、連線方向、存取控制尚未決定。雲端 agent 不能憑空讀 目標 Windows 主機 的本機檔案；診斷工具若需要可由平台呼叫的端點，必須另定經驗證、最小範圍且經批准的通道。不得為了測試就把 目標 Windows 主機 API 對 Internet 開放。

本機 EventGuard 核心不保存模型金鑰；只有接線層在獲准後持有必要的訂閱秘密。不得從既有登入環境複製 token。callback URL、簽章秘密和存取憑證都不得寫進公開報告、事件內容或原始碼。

### 最小事件範例（EventGuard 建議 schema）

以下是建議的 bridge 摘要 envelope，不是 `validate_event` 的完整輸入；核心先驗證 schema 2.0，再投影必要摘要並保留同一 event ID。它沒有真實機器識別或個人資料；`synthetic: true` 供未來安全驗收。欄位內容是資料，不是 agent 指令。

```json
{
  "eventId": "eg_evt_01_example",
  "name": "eventguard.security_change",
  "timestamp": "2026-01-01T00:00:00Z",
  "data": {
    "bridge_payload_version": "1.0",
    "event_schema_version": "2.0",
    "host_ref": "host_pseudonym_01",
    "episode_id": "eg_episode_example",
    "event_type": "listener.changed",
    "transition": "new",
    "severity": "warning",
    "rule_id": "pb-listener-change",
    "rule_version": "1.0.0",
    "evidence_summary": {
      "protocol": "TCP",
      "port": 43210,
      "binding_scope": "all_interfaces",
      "internet_reachability": "unknown"
    },
    "evidence_ref": "opaque_local_evidence_id",
    "coverage": "partial",
    "synthetic": true
  },
  "cursor": null
}
```

只送必要摘要；不送完整命令列、使用者家目錄、事件 Message／XML、啟動項內容、秘密或私人檔案。詳細資料透過白名單診斷查詢，先檢查來源、範圍、筆數與時間。`all_interfaces` 不能推定 Internet 可達；`partial`／未知不能轉為安全或入侵結論。

### 投遞、ack 與可靠性

官方要求事件 ID 在重試間保持穩定，使用 Standard Webhooks 簽章；callback 必須 HTTPS，禁止重新導向並檢查目的地。`2xx` 只表示 webhook 收到，後續處理是非同步；單次事件上限 256 KiB。暫時錯誤採有界指數退避，`410`、`413` 不重試。事件可能重複或亂序；訂閱有效期、撤權與重啟需處理。[官方 MCP Events](https://developers.openai.com/plugins/build/mcp-events)

EventGuard 建議分開持久保存以下狀態，不使用含糊的單一「已送達」：

| 狀態 | 所需證據 | 不代表什麼 |
| --- | --- | --- |
| `persisted` | outbox commit／事件 ID | 尚未傳輸 |
| `transmitting` | 投遞 attempt、時間及次數 | 不證明對端收到 |
| `received` | callback 明確 `2xx` | 不證明 agent 已喚醒或處理 |
| `agent_observed` | 訂閱聊天內確實出現該事件並有 agent 回合證據 | 不代表診斷已完成 |
| `processed` | agent 結果回條關聯 event ID／episode ID、診斷證據與判定 | 不代表獲准處置 |
| `closed`／`resolved` | 符合 playbook 結案／恢復證據 | 不代表全機安全 |
| `retry_wait`／`failed`／`blocked` | 錯誤類別、下次時間或待補條件 | 不可悄悄丟棄 |

`processed` 是 EventGuard 另需設計的回條契約，不是 MCP Events 自動提供的業務處理 ack。若平台未提供可程式取得的處理證據，先由使用者可核對的聊天回應驗收，狀態不得假造為已處理。

本機以 `event_id` 去重；相同事件重送不能重開診斷或重做處置。`episode_id` 串起新增、升級與恢復；版本號／時間排序避免舊事件覆蓋新狀態。採 at-least-once 傳輸及冪等處理，不保證 exactly-once。保存投遞意圖與回條後才推進狀態；崩潰後繼續未完成 attempt。

建議初始限制：單次摘要不超過 8 KiB、投遞 concurrency 1、有界 retry＋抖動、同 episode 合併、每分鐘事件上限及背壓。這些是待測目標，不是已達效能。滿載時保留容量告警與高優先事件，不無限擴張磁碟；heartbeat 留本機且不投遞 AI。處理 agent 自身產生的事件時加來源標記與循環抑制，防止互相觸發。

## 3. 備選：自管 Codex app-server

若使用者接受另建受管理 agent thread，可由本機 bridge 控制 app-server 的 stdio JSONL，完成 `initialize`／`initialized`，建立或恢復自己有權管理的 thread，再用 `turn/start` 啟動回合，追蹤 `turn/started`、`turn/completed`。`turn/steer` 用於活動回合；`thread/inject_items` 本身不啟動回合。[官方 app-server](https://learn.chatgpt.com/docs/app-server)

示意請求（不是已執行命令）：

```json
{"method":"turn/start","id":30,"params":{"threadId":"owned_recorded_thread_id","input":[{"type":"text","text":"EventGuard event eg_evt_01_example: synthetic listener change. Read-only investigation under the configured playbook."}]}}
```

設計應使用自己建立並記錄的 thread ID；不得掃描 sessions 找既有任務，或冒用桌面工具／父子 agent 工具作投遞。預設 stdio 可避免新增網路監聽；本輪沒有啟服務，也沒有連目前正在執行的 daemon。此路徑仍受官方實驗性限制，不能宣告是穩定正式 ingress。[官方 app-server](https://learn.chatgpt.com/docs/app-server)

工程需另外保存 `event_id → thread_id → turn_id → turn_status`。JSON-RPC `id` 只是請求對應；沒有查到可當 durable event 冪等鍵的官方 `turn/start` 參數。若送出後回應遺失，先利用既有已授權連線的通知／狀態對帳；結果不明時標記 `delivery_uncertain` 並交人工核對，不盲目重送造成重複計費或重做動作。

app-server 的官方登入途徑可使用 ChatGPT 帳戶或 API key；兩者的帳務、資料處理與 workspace 控制不同，API key 使用按量計費且不等同訂閱額度。本輪不登入、不建 key；使用者須先選官方認證方式及模型／預算上限，再授權事件摘要傳送與持續啟動回合。[官方認證](https://learn.chatgpt.com/docs/auth)

`codex mcp` 連外部 MCP tools 不等於入站喚醒。官方更新記錄已移除舊 `codex mcp-server`，指向 app-server 整合；不要依賴舊範例復活已移除路徑。[官方更新記錄](https://learn.chatgpt.com/docs/changelog)

## 4. 本機公開 CLI 調研證據

2026-10-22 UTC，僅執行下列公開 help，均正常結束；未執行登入、queue 發送、server 啟動或 socket 連線。沒有測量 CLI 版本，不能由 help 推定版本號。

| 查詢 | 觀察 | 限制 |
| --- | --- | --- |
| `Get-Command codex` | `<USER_PROFILE>\AppData\Roaming\npm\codex.ps1` | 只定位公開命令，未廣掃安裝目錄 |
| `codex --help` | 列出 `app-server`、`queue` 等命令 | 命令存在不證明平台語意與可用權限 |
| `codex app-server --help` | 預設 stdio；標示 experimental；有 proxy 子命令 | 未啟動或連現有控制 socket |
| `codex queue --help` | `--thread` 指向 session UUID／名稱，`--message` 排入文字 | 未證明閒置回合會自動啟動，不採為已完成 ingress |
| `codex app-server proxy --help` | 可代理 stdio 至運行中的 control socket | 未查 socket、未連線，task 擁有權與回合行為未驗證 |

## 5. 真正端到端驗收（尚未執行）

使用者須先選定目的平台及授權最小資料傳輸。未選之前，只能做設計與現有本機 mock 測試，不能標記正式連線成功。

1. 在支援的 Work Cloud chat／dot 建立長期任務，核對 plugin 存取與事件訂閱權限；記錄非秘密的目的地識別。
2. 完成 MCP Events discovery、訂閱與 callback 驗證。憑證／簽章秘密安全保存；報告僅記錄設定存在及有效期。
3. 啟動本機 bridge，正常無異常時等待；觀察指定時間窗內模型回合數為 0。程式層可測 retry 等待，不讓 AI 定時輪詢。
4. 由**外部非 AI 程式**建立唯一 `synthetic: true` event；不能靠真人貼文字進聊天室或 mock 假冒正式投遞。
5. 核對 outbox、實際 signed POST、平台 `2xx`，以及**同一訂閱聊天真正出現該 event ID 且 agent 啟動回合**。HTTP 成功單獨不足驗收。
6. agent 使用已接通的 EventGuard 唯讀工具查該合成證據；核對工具呼叫、結果、關聯 ID 與合成結案回條。不能以另一 agent 的工具傳訊替代。
7. 重送相同 event、模擬投遞回應遺失與 bridge 重啟，驗證業務冪等、可追溯 retry、無重複處置；用受控失敗測 expiry／撤權／背壓，避免真實攻擊或更改防護。
8. 發送非匹配事件確認不啟回合；unsubscribe 後確認不再投遞；停止本輪測試程序並核對沒有遺留背景程序。

驗收紀錄須含測試時間與時區、實際程式版本、來源、event ID、投遞狀態、訂閱聊天可核對的 agent 回應、診斷結果與結案證據。若平台有可用的 run／turn ID 才記錄；MCP Events 文件未承諾通用 run_id API，不假造取得方式。

## 6. 精確 blockers、批准與下一步

下列均是 **pending／未建立**，不是權限拒絕，也不是可由本文件自動授權的操作。

| 待完成動作與目標 | 為何阻擋 | 完成條件 |
| --- | --- | --- |
| 選定實際長期任務平台 | 普通本機 Codex task 與 Work Cloud／dot 契約不同 | 使用者確認支援的目的平台；若堅持既有本機 task，需官方可驗證入站契約 |
| 確認 MCP Events workspace／plugin／event 權限 | 文件能力不等於此帳戶已開通 | 實際 discovery／訂閱可用，無略過批准 |
| 決定 receiver／bridge 的部署、認證與連線 | 尚無正式接收端；callback 不是本機事件檔 | 受支援 plugin/server、callback 驗證成功及受控存取 |
| 批准最小事件外傳與必要簽章秘密保存 | 現有授權禁止擅建外部 webhook／憑證 | 明確限定目的地、欄位、保存、有效期與撤銷方式 |
| 接通真實 readonly diagnostic tools | 雲端聊天不能直接讀 目標 Windows 主機 | 固定白名單查詢、限額、遮罩及每次存取驗證可測 |
| 批准持續模型回合及預算 | 異常會啟動推理並消耗帳戶額度或費用 | 選帳戶／模型／事件速率與每日上限；費率依當時官方與帳戶核對 |
| 正式 E2E 測試 | 目前只有方案與 help，沒有真喚醒證據 | 完成上一節外部程式→實際聊天→診斷→結案 |

等待接線不需要模型持續推理，但不能承諾 hosting、平台或帳戶費用為零。異常風暴可大量啟動回合；必須先有合併、冷卻、預算與緊急停止機制。提權、服務、排程、自啟、防火牆、隔離刪檔與系統修補仍未授權。

connected 不代表桌面可操作；過往 UAC 取消紀錄不證明目前畫面。任何未來提權前必須確認現場或受支援遠端能處理安全桌面；不得停用 UAC、繞過安全桌面，或自動恢復先前暫停修補。

## 7. 建議先批准的最小接線範圍

建議採 **MCP Events／Work Cloud 或 dot**，先做一個使用者、一個自訂事件、一個訂閱聊天的合成驗收。需要使用者先指定可設定 authenticated MCP plugin 的部署位置與支援目的地；伺服器需能接受平台 MCP 請求並向其 callback 發 HTTPS。此處沒有現成可任意選用的免費受信端點。

最小資料範圍限 `synthetic=true`、合成 host_ref、固定事件類型、TCP port 範例、coverage、event ID；不外傳原生採集與私人主機內容。先只接合成診斷結果及事件回條，不開原生診斷給雲端。批准應包含：部署位置／擁有者、plugin 存取、callback 簽章秘密的保存／期限／撤銷、允許啟動模型回合與預算上限，以及測試結束停止或 unsubscribe 的方式。

完成上述真喚醒後，再單獨批准原生診斷回程：只允許現有 typed operations、每次驗證權限與 request ID、有限 rows／deadline；不得因此開放任意 shell、整機檔案或 Internet 入站埠。若平台無法提供可信的診斷工具通道，維持阻塞，不能只做通知就稱完整 E2E。

若使用者選自管 app-server 作替代，需明確接受「另建受管理 thread」及實驗性限制，批准使用哪個現有帳戶／模型額度開回合；不可擅自沿用目前桌面任務或把 API key 收進 EventGuard。兩條路徑不能混合稱已接上既有聊天。

## 8. 官方來源與交接要求

- [MCP Events：支援目的地、訂閱、簽章、投遞與測試](https://developers.openai.com/plugins/build/mcp-events)
- [Codex app-server：JSON-RPC、thread／turn 與實驗性限制](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication：官方登入與帳務差異](https://learn.chatgpt.com/docs/auth)
- [Codex changelog：舊 MCP server 移除及 app-server 整合方向](https://learn.chatgpt.com/docs/changelog)

後續實作者先重查官方契約與實際帳戶支援，再選一條路徑完成。將驗收證據加到 STATUS；保留「本機事件保存」「平台接收」「agent 回合」「診斷完成」四種差別，不把本文件或 playbook 當永久授權。本輪沒有啟用正式 ingress 或常駐服務，沒有真正喚醒 Codex／dot。
