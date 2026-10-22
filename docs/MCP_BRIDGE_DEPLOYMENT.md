# EventGuard MCP bridge 部署與接線

Phase 5 已將停用 bridge 移至 `contrib/mcp_bridge/`；正常核心不 import。以下保留原部署候選供審查，不是本機前置或新授權；目前使用 [單一 QueueInbox 路徑](DELIVERY_CONSOLIDATION.md)。

文件更新：2026-10-22 UTC。版本定位：**尚未完成目標的工程預覽**。本輪提供 synthetic-only bridge 的程式介面與離線測試接縫；**沒有部署公開端點、建立新憑證、訂閱平台、啟動常駐程序或真正喚醒 agent**。程式／測試的實際結果以本版本 [STATUS](../STATUS.md) 為準，不能沿用舊版測試數。

本文可供下一位維護者審查與選擇部署方式，不是部署授權。原生主機資料外傳、跨機診斷、任何新 TLS／防火牆／服務／排程／自啟設定都不包含在本輪。預設設定維持 disabled。

## 1. 可用能力與證據層次

本輪介面為 Python 3.13 標準函式庫的 authenticated WSGI 應用；資料保存在 `data/bridge`。它接受已驗證的 synthetic core event、持久保存訂閱與投遞狀態、實作 HTTPS callback 驗證與 Standard Webhooks HMAC，並提供合成證據工具及結果回條。沒有在遠端平台驗證成功之前，這些是程式能力，不能寫成已接通。

| 層次 | 本輪範圍 | 不能推定 |
| --- | --- | --- |
| 靜態／in-process | 假 HTTP transport、合成證據、認證與故障案例；不 bind、不 connect、不呼叫模型 | 不是 Internet HTTPS 或平台相容性驗證 |
| 本機 listener | 預設關閉；另行明確啟用才綁 `127.0.0.1:8765` | 不提供 TLS、不自建公開入口 |
| 平台 MCP Events | 官方契約已核對，實際帳戶／plugin／訂閱未接通 | 不能宣稱 Work Cloud、dot 或現有 Codex task 已收到 |
| 原生診斷 | 本 bridge 本輪只讀已儲存 synthetic evidence | 不查目標 Windows 主機、無跨機原生診斷通道 |

主維護者本輪能力盤點回報：`codingEnvironments=[]`，事件來源只有既有 Gmail／GitHub，沒有 EventGuard。這只描述盤點時間，不能證明永久不可用，也不構成可部署主機。需另確認自有且可用的 host、平台權限與資料傳輸批准。

## 2. 官方契約與認證定位

MCP Events 的受支援目的地是 Work web chat、桌面 Work 且選 Cloud，以及 dot；需要 MCP 2.0 `2026-07-28`、持久訂閱及 outbound HTTPS。`server/discover` 宣告 events，同一 authenticated MCP 端點提供 list／subscribe／unsubscribe。帳戶是否開通仍待實測。[官方 MCP Events](https://developers.openai.com/plugins/build/mcp-events)

本版使用**固定 Bearer 的 API-key 認證**，不是 OAuth。套件 `mcp.json` 的宣告為 `auth.type="api_key"`、`headerScheme="bearer"`；設定只描述認證方式，不含 token。官方 submission portal 連線表單不支援 API-key declaration；不能因 manifest 合法就宣稱可提交公用目錄，或假造 OAuth discovery。若目的平台要求 OAuth 2.1 provider，須另立工程實作、審查及測試。[官方封裝與認證](https://developers.openai.com/plugins/build/plugins#fixed-bearer-tokens-and-api-keys)

[integration/mcp.example.json](../integration/mcp.example.json) 是套件連線範例，不是已註冊 plugin，也不是憑證。使用 `.invalid` 網域防止被誤認為可用服務。自訂 plugin 連線流程、帳戶支援及 workspace controls 都須現場確認；不能保證任意 Codex 桌面 task 接受此種事件。

## 3. 兩種待選的部署方案

兩種方案都要求**已存在且經使用者確認可用的自有 Windows 主機與 HTTPS 入口**，本輪沒有提供或採購 host、proxy、網域或憑證。主機能跑程式不等於它已具備下列條件。

### A. 原目標 Windows 主機已有自有 HTTPS 反向代理

```text
支援的 Work Cloud／dot
       │ HTTPS 443，authenticated /mcp
       ▼
已批准、已存在的 HTTPS 反向代理
       │ 同機 loopback；只轉送必要路由
       ▼
127.0.0.1:8765 WSGI bridge
       ├─ 同一 Windows 使用者的 DPAPI vault
       ├─ data/bridge：synthetic evidence／訂閱／outbox／回條
       └─ HTTPS 443 outbound → 驗證過的平台 callback
```

適用條件：既有 TLS 憑證、DNS、443 路由、防火牆與 proxy 已可用；proxy 管理者可設定必要轉送、請求大小與逾時，並保留 Bearer header。需要新增或修改任何設定時，先核對有效授權；這份文件不授權開 port、建立 tunnel、安裝服務或提權。

若需要 UAC，先確認現場或受支援遠端可以處理安全桌面。connected 不代表桌面可操作，舊 UAC 取消紀錄不證明當前畫面；不得關閉 UAC／繞過安全桌面，也不恢復之前暫停的修補。沒有既有可用入口就保持 blocked，不把 loopback listener 改成 `0.0.0.0`。

### B. 已有自有且可用的遠端 Windows 主機

bridge、DPAPI vault 及 stored synthetic evidence 都部署在該遠端 Windows 主機，仍由既有 HTTPS proxy 對外、bridge 維持 loopback。先完成**同一 host 的 synthetic 接線驗收**；不能把遠端 host 的 evidence 說成目標電腦的實測。

本輪沒有本機→遠端 producer 長期上傳客戶端，也沒有遠端→原目標主機的原生診斷回程。若未來要接原生資料，需另批准經認證、限額與最少資料的通道，並獨立驗收；agent 不能因遠端 bridge 可見就讀取原目標主機檔案。

### 平台差異

Production signing-secret vault 本版採 Windows DPAPI current-user。一般而言資料需由相同使用者、相同電腦解密；不把 `CRYPTPROTECT_LOCAL_MACHINE` 當預設。更換執行帳戶、移轉主機或還原備份前須驗證可解密與重新訂閱策略，不複製明文秘密。[Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

Linux 可做實際可用的純邏輯／假 HTTP 測試；**本版沒有 Linux production secret vault**。如要 Linux 部署，必須另外接入已批准的 secure store、完成實作與驗收，不能降級存明文或將 fake vault 當可部署解法。

## 4. 網路、路由與身分界線

| 方向／路由 | 身分與資料 | 本輪限制 |
| --- | --- | --- |
| 平台→proxy HTTPS 443→`POST /mcp` | subscriber Bearer；MCP events 與 typed tools | 僅 authenticated POST，無任意 shell／檔案讀取 |
| 已批准 producer→`POST /events` | producer Bearer；core schema `2.0` 且 `synthetic=true` | producer 不代表 subscriber；不接原生事件 |
| `/status` | subscriber 認證；最少狀態計數 | 不回傳 callback URL、秘密或 secret refs |
| bridge→平台 callback HTTPS 443 | 每次 Standard Webhooks 簽章 | 僅允許確認過的 callback host；無 redirect |

`/status` 的 HTTP method 以 server route 與本版測試為準，不靠猜測探測平台。不要為排錯記錄 Authorization、token、callback URL path 或簽章秘密。proxy access log 必須有相同遮罩與保留政策；未確認前不得拿實際秘密測試。

Bearer token 只從明確指定的環境變數名稱讀取，不搜尋現有登入、瀏覽器、Codex sessions 或其他程式 token。subscriber 與 producer 使用不同秘密，按 principal／host_ref／role 限定權限；知道 `event_id` 不等於能讀取其他 principal 的資料。不要把 producer token 交給平台訂閱端。

## 5. 範例設定與安全預設

[config/bridge.example.json](../config/bridge.example.json) 僅含非秘密設定：

| 欄位 | 範例值與意義 |
| --- | --- |
| `enabled`、`network_enabled` | 均 `false`；文件與 check 不啟用網路 |
| `synthetic_only` | `true`；不接受原生 event |
| `listen_host`、`listen_port` | `127.0.0.1`、`8765`；不公開綁定 |
| `public_origin` | `https://eventguard.example.invalid`；待批准後替換成真實自有入口 |
| `allowed_callback_hosts` | `[]`；未確認目的地時拒絕 callback，不用萬用字元 |
| `principals[].principal_id` | 匿名例 `example-owner`，表示同一擁有者的兩個受限身分入口 |
| `host_refs` | 只允許 `synthetic-host` |
| `roles` | 分別 `subscriber`／`producer`，不因相同 owner 合併 token 權限 |
| `token_env` | 只有 `EVENTGUARD_MCP_TOKEN`／`EVENTGUARD_PRODUCER_TOKEN` 名稱，無秘密值 |

部署時由已授權維護者在私有的 `config/bridge.local.json` 設定實際值；不要修改受版本控制的 example 為含秘密設定。檔案忽略規則不是權限控制，須人工確認本機 ACL、備份與執行帳戶均符合範圍。`data/`、`logs/`、`reports/` 及 vault 自有檔案均不可 push；密文也不是公開資料。

token 的來源、建立、保管、輪替與平台輸入方式仍需另行批准。本輪不產生新 token，不提供把 token 寫進 shell 歷史／命令列的範例，也不讀出任何既有秘密。ChatGPT 在未來合法 `events/subscribe` 時提供的 signing secret，僅交 vault 保存；不寫入此 JSON、事件 evidence 或報告。

## 6. CLI 與生命週期

在專案根目錄，可執行不啟服務、不讀 native collector 的設定檢查：

```powershell
python -B scripts/eventguard_bridge.py --config config/bridge.example.json check
```

check 顯示設定啟用狀態、network flags 與 DPAPI 平台相容資訊。disabled example 不能用來 serve；check 通過也不證明 TLS、DNS、平台帳戶、憑證或 callback 已可用。

**以下僅是未來已具備 host、秘密與範圍批准後的前景啟動命令，本輪未執行：**

```powershell
python -B scripts/eventguard_bridge.py --config config/bridge.local.json serve --enable-server
```

serve 需要設定 `enabled=true` 及明確 `--enable-server`；投遞網路另受 `network_enabled` 與 callback allowlist 控制。它只提供本機 loopback listener，不替代 TLS proxy、不安裝服務、排程或自啟。依本版本 CLI 的正常中斷／退出路徑合作停止，核對自己的程序已結束；不使用 taskkill、kill 或 terminate 來宣稱停止通過。

本輪未提供 bridge `emit` CLI。原有核心 `synthetic emit` 只建立本機測試事件，**不會自動 POST 至 bridge 或喚醒 agent**。正式驗收需再確認已批准的外部 producer 程式如何向 `/events` 發送核心 schema，不能用人工貼訊息或其他 agent 傳訊冒充程式觸發。

## 7. 訂閱、秘密與投遞

允許訂閱前，伺服器驗證 principal、host_ref、事件篩選、簽章秘密格式及 HTTPS callback。驗證與正式投遞都重新解析 DNS、拒絕非公開目的 IP／redirect，連線鎖定已驗證地址並保留原 hostname 做 TLS 驗證，防止 DNS rebinding。空 callback allowlist 保持拒絕；不得為讓測試過關而放寬到任意 host。

平台 `2xx` 只表示 webhook 收到，不能證明 agent 已啟動。每次重試保留 event ID，重新簽章；訂閱、pending attempt、回條與去重資料持久保存，採 at-least-once 及冪等，不保證 exactly-once。具體 retry／容量／期限常數以本版程式與測試為準。[官方投遞與測試](https://developers.openai.com/plugins/build/mcp-events#handle-delivery-responses)

| 狀態／證據 | 可作結論 | 不可作結論 |
| --- | --- | --- |
| bridge durable ACK | `/events` 已持久保存該 event | 平台已收到 |
| callback `2xx` | 平台 webhook 已接收 | agent 已開始或已完成 |
| `agent_result_recorded` | authenticated caller 交回與 event 關聯的結果 | 呼叫者必為真實平台 agent、run_ref 為真、全機已安全結案 |
| 指定聊天同 event ID 的實際回應＋工具呼叫證據 | 受測平台 agent 確實被喚醒並查詢 | 所有平台、所有未來事件均成功 |

結果回條與原事件／診斷 request ID 都需保留關聯。run_ref 只有平台確實提供且可核對時才記錄；本 bridge 不會自行創造可證明平台回合的 run ID。

## 8. Agent 可呼叫的合成診斷工具

三個工具都要求 subscriber 認證與 principal／host scope；只查 bridge 已儲存的 synthetic evidence。它們不執行 Windows collector、不接受 shell、不讀主機路徑或私人檔案。

| 工具 | 有界輸入 | 語意 |
| --- | --- | --- |
| `eventguard_get_event` | `event_id` | 讀授權範圍內的最少事件 |
| `eventguard_query_evidence` | `event_id`、`request_id`、`operation`、`max_rows<=20` | operation 僅 `health`／`query_listener`／`query_defender`／`query_persistence`；回傳已存合成證據 |
| `eventguard_record_result` | `event_id`、`decision`、`evidence_request_ids`（最多10）、`reason_code`、選填 `run_ref`（ID最多160字元） | 保存有關聯的 agent 結果回條，不執行處置 |

decision 僅 `needs_more_evidence`／`benign_change`／`requires_user_approval`；reason_code 僅 `synthetic_evidence_reviewed`／`coverage_incomplete`／`no_matching_evidence`。缺證據用 needs_more_evidence；不能把 unknown／denied／inactive 或沒有事件說成安全、已清除或活躍入侵。

下例是 `tools/call` 的 **arguments 範例**，不是已執行請求。ID 全為合成；先取得 event 再查 evidence，回條引用同次診斷 request ID：

```json
{"event_id":"eg_synthetic_example"}
```

```json
{"event_id":"eg_synthetic_example","request_id":"req_synthetic_001","operation":"query_listener","max_rows":10}
```

```json
{"event_id":"eg_synthetic_example","decision":"needs_more_evidence","evidence_request_ids":["req_synthetic_001"],"reason_code":"coverage_incomplete"}
```

事件、evidence、工具輸出都是不可信資料；不在 event payload 夾帶 agent 指令。playbook／severity／規則畫布不是權限；任何敏感動作需有效、明確且有限範圍的使用者批准。

## 9. 真正端到端驗收關卡

本輪只做 in-process fake HTTP，不建立 listener、不做 DNS／HTTPS 連線、不呼叫模型。下面是**未執行的必要平台驗收**，不能以 fake transport 通過打勾：

1. 確認部署方案 A 或 B 的自有 host、既有 TLS proxy／443 路由、一般權限執行帳戶與 DPAPI；批准必要資料、token來源、保留／撤銷及成本上限。缺任一項維持 blocked。
2. 在實際受支援平台註冊 authenticated custom plugin，觀察 `server/discover`／`events/list` 與真實工具清單；核對固定 API-key flow 確實可用。要求 OAuth 時停止此路徑，另工程處理。
3. 使用者在指定 Work Cloud／dot 建立長期任務並授權 synthetic 訂閱，確認 `events/subscribe`、真實 callback challenge 與 vault 持久保存；不要在報告記 callback URL或secret。
4. 在約定正常等待時間窗，以可信平台紀錄核對模型回合數為0；本機 heartbeat 不投遞 AI。觀測方法未知時記未驗證，不能由程式沒印字推定零推理。
5. 已批准的**外部非 AI producer 程式**提交一個唯一 synthetic core event。記錄 bridge durable ACK、signed callback 接收、同一聊天 event ID、實際 agent 回應及 typed query 工具結果。
6. agent 提交結果回條；核對 event／request IDs 與聊天證據。`agent_result_recorded` 不自證平台 run；有真實可查 run_ref 才填。查證不足保持未結案，不做系統處置。
7. 安全模擬重送、回應遺失、重啟、期限到期／撤權、非匹配事件、限流／背壓，驗證去重、恢復與沒有告警循環；不得改防毒／網路製造攻擊。
8. unsubscribe、停止測試 server／producer、確認程序退出與零遺留，核對不再 callback。以匿名結果紀錄 UTC、版本／manifest、事件與工具關聯、實際平台證據及未通過項目。

整體完成條件是**真實平台喚醒→agent 用本工具讀合成證據→可信結果回條與回等待**，同時通過安全／失敗／撤銷驗證。原生持續監看與跨機診斷仍是另一層批准及驗收，synthetic E2E 不代表它們已完成。

## 10. 停止、撤銷、保留與故障排除

| 現象 | 安全檢查／下一步 |
| --- | --- |
| example 無法 serve | 預設正確；先核對批准與本機設定，不移除 disabled 防線 |
| 401／403 | 核對明確 env ref 是否存在、role與host scope；不輸出秘密、不抄其他程式登入token |
| callback 被拒絕 | 核對批准的精確host、HTTPS與DNS公網地址；不放行私網、redirect或萬用字元 |
| DPAPI 不可用／解密失敗 | 核對Windows、同使用者／主機與vault檔案權限；不降級明文或切 machine scope |
| 平台顯示成功但沒 agent 回應 | 分開檢查 callback receipt、訂閱聊天與平台權限；HTTP成功不足真喚醒驗收 |
| 工具沒有原生診斷資料 | 本版僅stored synthetic，屬功能界線；不要自動開跨機shell或檔案API |
| DB／outbox容量或重試停滯 | 保存匿名狀態，按版本限額查原因；不刪檔掩蓋丟失，也不無限重試觸發模型 |

日常停看先 unsubscribe，再依 server 正常退出路徑停止自己程序。緊急撤銷 Bearer 的方式是停止 server、由已授權維護者撤換／移除對應 token 並重新核對設定；停 server 不等於平台訂閱已刪除，重啟前必須確認撤銷效果。token輪替、proxy設定、vault刪除／匯出與資料保留都需既定授權，不在本輪自動執行。

本工具不會自動備援或自我監督：整個程序死亡、主機斷電、休眠或網路中斷可能完全無法投遞；沒有獨立 watchdog。保留 DB 與 vault 的備份不得共用至原始碼repo，恢復需按同一身份／主機條件測試；未有復原證據前不承諾可恢復所有訂閱或事件。

## 11. 成本與待決事項

已存在 host／網域／TLS／proxy 也可能有維運成本；平台異常回合會消耗帳戶額度或費用，具體計價與可用性未知，須依實際帳戶在部署前核對。先約定事件速率、合併／冷卻、每日回合／費用上限與緊急停止方式；不要承諾零費用或把正常程式等待等同平台永遠免費。

尚未完成：指定且驗證 host與HTTPS入口、取得平台customplugin／events權限、批准秘密與最少外傳、真實callback／喚醒驗收、原生producer和跨機診斷設計、Linux securestore、長時負載與故障復原實測。本文件與範例不會自行部署、常駐或提供防護。

後續參考：[INGRESS_PLAN](INGRESS_PLAN.md)、[AGENT_CONTRACT](AGENT_CONTRACT.md)、[OPERATIONS](OPERATIONS.md)、[AGENTS](../AGENTS.md)。

## 整合驗證、producer 與容量補充

2026-10-22T03:50:53Z：完整192tests／40AST通過，未bind／外連／模型／原生採集。程式的 producer 為 `eventguard.mcp.producer.BridgeProducerAdapter`，必須由呼叫端明確提供已批准的 producer bearer、`BridgeHTTPSPoster` 與 `enabled=True`，不會由目前 monitor 自動選用。`BridgeHTTPSPoster` 僅允許一個明確HTTPS host的 `/events`，與 callback 的 `SafeHTTPSPoster` 分開標頭政策，後者不允許Authorization。不要把bearer放原始碼或CLI參數。

producer durable ACK、平台callback的2xx、authenticated agent結果回條是三個狀態。`eventguard_record_result` 支援可選 `expected_result_id` 作CAS及最多10次不可變revision；舊結果重播不倒退current。`benign_change` 至少引用一筆成功且同owner／event的查證；run_ref只是呼叫者聲稱，`platform_run_verified=false`，仍須平台可核對證據。

bridge最多20訂閱（含revoked）／1000事件、每事件20查證／10結果revision，DB主檔8MiB另有DELETE journal暫存；目前不自動保留輪替，滿載明確拒收。DPAPI vault最多128密文檔，同key refresh重用原ref；key輪替與重訂閱後的安全清理仍待維護流程。DNS resolver不能強制終止，雖呼叫端有10秒上限，最多4個process內daemon查詢可能pending；所有此輪測試都釋放自己的fixture gate，未留服務或測試子程序。

HTTP `/status` 為 authenticated subscriber GET，僅回counts及固定worker狀態；不回URL／secretref或可信的agent存活結論。Bearer設定在啟動時載入，撤銷／縮限後要停用並重啟採用新設定，投遞逐次檢查目前subscriber角色及host；修改shell環境本身不會改既有process中的digest。標準庫foreground WSGI僅作受控loopback入口，正式public HTTPS必須交由另行批准的既有TLS反向代理、request limits與部署審查；未宣稱標準庫server足以直接公開。
