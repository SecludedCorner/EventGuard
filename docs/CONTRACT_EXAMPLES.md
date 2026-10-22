# 可驗證的契約與合成範例

本檔補充 [AGENT_CONTRACT](AGENT_CONTRACT.md)，以目前程式欄位為準。以下全部是合成資料，不是主機警報。`synthetic=true` 不得轉成真實事件，也不代表模型或處置已執行。正式 ingress 尚未接通；實作候選見 [INGRESS_PLAN](INGRESS_PLAN.md)。

## 事件、狀態與冪等

`events/schema.py::validate_event` 驗證 schema 2.0，保留白名單並最小化 metadata，單事件最多 8192 bytes。它是格式與遮罩機制，不是密碼或任意秘密偵測器；新採集欄位仍需人工隱私審查。未知最上層／metadata 欄位被丟棄，無效身份、時間、深度及大小被拒絕。

```json
{
  "schema_version": "2.0",
  "event_id": "evt-synthetic-listener-001",
  "host_id": "synthetic-host",
  "episode_id": "episode-synthetic-001",
  "correlation_id": "episode-synthetic-001",
  "sequence": 1,
  "event_type": "listener.changed",
  "detector": {"id": "synthetic-listener", "version": "1.0.0"},
  "rule_ref": {"rule_id": "pb-listener-change", "version": "1.0.0"},
  "transition": "new",
  "severity": "warning",
  "synthetic": true,
  "observed_at": "2026-01-01T00:00:00Z",
  "persisted_at": "2026-01-01T00:00:00Z",
  "window": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
  "baseline_version": "synthetic",
  "evidence": {"protocol": "TCP", "port": 18080, "binding_scope": "all_interfaces"},
  "inference": {"summary": "Synthetic only; Internet reachability unknown.", "compromise_conclusion": "undetermined"},
  "coverage": {"status": "ok", "source": "synthetic_fixture"},
  "privacy": {"profile": "minimal-v1", "redacted": true},
  "evidence_refs": []
}
```

同一轉態的重送保留 `event_id` 和不可變 payload；同 ID 不同內容會拒收。升級／恢復建立新 `event_id`，沿用同一 episode 與 correlation，增加 sequence。`new / escalated / resolved` 是偵測轉態，不是投遞狀態。恢復需連續兩次完整成功觀察；缺失、denied、partial 不能充當恢復。

目前 outbox 為 `pending / retry / ack / failed`，不含真正 agent 的處理進度。生產 receiver 須另存 `agent_started`、run／turn ID、診斷回執與案件狀態；這些仍是未實作的正式接線契約。

## Receiver ACK 與 adapter

Python 介面目前為 `adapter.connected` 與 `adapter.send(sanitized_event) -> receipt`。`pump()` 先持久化 lease／attempt 再呼叫 adapter；發送可能重複，因此接收端必須以 event ID 與 payload hash 冪等保存。ACK 僅在接收端完成耐久保存後發出。

下例是**現有本機 mock** 收據，不是生產 receiver 或 agent 的證據：

```json
{
  "ack_type": "receiver_persisted",
  "event_id": "evt-synthetic-listener-001",
  "receiver_receipt_id": "mock-receipt-synthetic-001",
  "received_at": "2026-01-01T00:00:01Z",
  "receiver_kind": "local_mock",
  "task_ref": "local_mock_test_only",
  "wake_state": "mock_only_no_agent",
  "real_agent_woken": false
}
```

`EventStore.acknowledge(event_id, receipt)` 會驗證 ACK 類型、相符 event ID 及收據 ID。格式驗證本身不驗證傳輸對方身份；未來真 adapter 必須實作可信來源、身份、完整性、重放防護及目的地綁定，不能讓不可信事件自行 ACK。HTTP 200、檔案落盤、輸出文字或 CLI 啟動都不能代表 agent 已處理。

傳輸失敗可回 `{"ack":false,"retryable":true}`；永久拒絕可回 `{"ack":false,"retryable":false}`。目前退避約為 30 秒起、倍增至 3600 秒上限，加確定性 jitter，最多 8 次。接收端離線不改事件 ID。DisabledAdapter 未接通時不耗 attempts。超過 30 天去重窗或不確定的最後嘗試須停止自動重送並查收據，不能聲稱 exactly-once。

## 按需診斷

`scripts/eventguard.py query OP --args JSON` 只接受白名單，不接受 shell、任意路徑或任意採集腳本。先用 `capabilities` 讀取目前能力。`request_id` 用於關聯，不能提供權限；每次最多 100 rows、原生查詢期限 15 秒，輸入 JSON 上限 8 KiB。

在專案根目錄的 PowerShell 範例：

```powershell
python -B scripts/eventguard.py capabilities
python -B scripts/eventguard.py query health
python -B scripts/eventguard.py query query_listener --args '{"protocol":"TCP","port":18080,"max_rows":20,"request_id":"synthetic-query-001"}'
python -B scripts/eventguard.py query query_defender --args '{"view":"settings","max_rows":20}'
python -B scripts/eventguard.py query query_persistence_diff --args '{"kind":"startup","max_rows":20}'
python -B scripts/eventguard.py query query_version --args '{"product_id":"python_runtime"}'
```

除 `health` 外，上列會查目標 Windows 系統，必須在已授權主機與範圍內使用；雲端 CI 不應執行這些原生查詢。18080 只是例子，不代表實機有此監聽。

程序查詢必須使用上一份可信證據的實例身份，二選一：`{"process_instance_ref":"proc-000000000000000000000001"}` 或 `{"pid":42,"created_at":"2026-01-01T00:00:00Z"}`，不可混用，也不可只給 PID。若實例已過期，保留 `unknown / stale_process_instance`，不要改查另一個程序並沿用結論。

回應 envelope 的**合成**例子如下；原生資料列的 `scope` 以實際 collector 結果為準：

```json
{
  "schema_version": "1.0",
  "request_id": "synthetic-query-001",
  "status": "ok",
  "source": "listeners",
  "observed_at": "2026-01-01T00:00:02Z",
  "coverage": {"status":"ok","source_status":"ok","source_scope":"local_metadata_only"},
  "rows": [{"protocol":"TCP","address":"127.0.0.1","port":18080,"pid":42,"scope":"localhost","status":"ok"}],
  "truncated": false,
  "error_code": null,
  "elapsed_ms": 10
}
```

`query_persistence_diff` 目前另回 `coverage.mode=current_only`、`baseline_comparison=not_implemented`。版本只接受 `python_runtime`；Defender 只有 `settings`，沒有威脅歷史。unknown、partial、denied、not_applicable、timeout、error 必須分開處理，不可改成安全結論。

CLI exit code：`0` 成功；`2` 無效輸入／規則；`3` 單例 busy；`4` 操作／來源錯誤；`5` partial、denied、unknown、timeout 或不健康。`argparse` 用法錯誤也回 2。呼叫者應同時讀取結構化結果，不能只靠 exit code 下安全結論。

## Playbook 契約與完整實例

完整可執行驗證的宣告資料在 [playbooks/default.json](../playbooks/default.json)，包含監聽、防護變更、持久化變更、監看故障四條。每條都有：

| 欄位 | 消費者必須遵守的意義 |
| --- | --- |
| `rule_id / version / enabled / event_type / event_filter / severity` | 固定規則版本與適用事件，不從事件內容任意選工具 |
| `investigation_steps / tool_io / decision_basis` | 白名單採證、結構化輸入輸出及判斷依據 |
| `edges / on_failure / on_unknown` | 成功、失敗、未知與衝突的明確去向 |
| `allowed_actions / approval_gate` | 現有範例 allowed_actions 為空；規則不授權，敏感行為另取有效批准 |
| `timeout_retry / expected_evidence` | 調查時限、有限重試及可核對證據 |
| `completion_conditions / recovery_conditions / audit / supersedes` | 結案與恢復條件、修改紀錄及回復關係 |

目前 `playbook validate` 驗證宣告結構；`playbook simulate` 只回調查計畫與衝突／無匹配結果，**不調用工具、不執行模型、也不做處置**。未來畫布與表格應共用這份版本化資料，不能把節點字串變成任意 shell。

完整安全合成流程：

```powershell
python -B scripts/eventguard.py synthetic emit --scenario listener
python -B scripts/eventguard.py events list --namespace test
python -B scripts/eventguard.py playbook validate
python -B scripts/eventguard.py playbook simulate --namespace test --event-id EVENT_ID
python -B scripts/eventguard.py deliver --adapter mock
python -B scripts/eventguard.py mock process --event-id EVENT_ID
python -B scripts/eventguard.py report export --namespace test
```

將 `EVENT_ID` 換成第一步實際輸出的 ID。`mock process` 只呼叫合成診斷 callback；不查實機、不調模型。接通真 agent 後必須另外通過真 ingress 驗收，不能沿用此流程的成功結果當作產品完成證據。
