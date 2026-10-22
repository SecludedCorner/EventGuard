# MSI：單次真實 Codex 合成驗收

目前新驗收一律使用 [QueueInbox 收斂入口](DELIVERY_CONSOLIDATION.md) 的 single/continuous/batch/recovery，預設不開模型。以下是舊 LocalWait 歷史格式及回條說明；舊 run 入口已轉送新 single，retry 不再執行。

此入口驗證一次本機 stdio 的真 agent 等待 → 事件 → 查證 → 結果／ACK；不是常駐監看、桌面任務續接或 Windows 原生採集驗收。它需要當次明確模型範圍批准，本次維護不執行。完整產品仍為工程預覽，現況與歷史證據見 [EVIDENCE](EVIDENCE.md)。核心正常監看不呼叫模型，沒有永久 MCP 設定或新憑證。

## 最短操作

在 MSI 的 EventGuard 根目錄，一般權限 PowerShell 執行。使用原有 Python 3.13 與已安裝的 MCP SDK；以下不安裝任何東西，也不登入或修改執行政策。

```powershell
python --version
python -c "import importlib.metadata; print(importlib.metadata.version('mcp'))"
codex --version
codex login status
python -B scripts/acceptance_codex.py run --run-dir reports/msi-codex-001
```

`python` 必須是能載入 SDK 的既有 Python 3.13；若不是，改用其完整路徑。`codex` 必須是可從 PATH 啟動的原生執行檔；若 PATH 找到的是 npm `.cmd`、`.bat` 或 `.ps1` 包裝，入口會在模型啟動前拒絕。可加 `--codex-executable "既有原生 Codex 執行檔完整路徑"` 指定已安裝的二進位檔，不經 shell、不自動安裝。缺少 SDK／CLI／有效登入時停止，先處理該項前置條件，不自行安裝或建立憑證。命令會使用目前帳戶進行一次真實模型任務（可能多次模型請求，不能保證 token／費用），只處理公開合成資料。

執行器自動啟動一次 `codex exec --ignore-user-config --ephemeral -s read-only --json`，單次覆寫三個本機 MCP 工具、停用 shell 工具。執行 `run`／`retry` 或有限驗收的 `--execute`，代表已批准該次公開合成 wait／query／ACK；入口只對曝光白名單中的工具設定 `tools.<tool>.approval_mode="approve"`。非互動 exec 的總批准政策維持不變，沒有全域／專案 MCP 設定或繞過旗標。C 的 read-before-ack 階段只曝光及批准 wait／query，完全省略 ACK。這不是完整工具隔離；受管理工具與政策仍有效。工具不執行原生查詢或系統處置。Codex 的 SQLite 與 log 路徑單次指向此 run 目錄；帳戶登入仍走原有官方機制，不複製 auth 檔。先確認 agent 已寫入 `waiting`，在程式內閒置 3 秒後才產生唯一合成事件，沒有人工搬運事件回覆。

僅有 `enabled_tools` 不構成工具批准。若真 trace 顯示 `MCP tool call requires approval, but approval policy is never`，不能把 CLI exit 0 當成功；須有實際工具回傳、durable 結果與 ACK。上述逐工具單次設定依[官方 MCP 文件](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)，不改總批准政策，也不批准其他工具。

另一個終端可查狀態／要求停止：

```powershell
python -B scripts/acceptance_codex.py status --run-dir reports/msi-codex-001
python -B scripts/acceptance_codex.py stop --run-dir reports/msi-codex-001
```

`status` 讀取有界狀態及擷取回條，不以 PID 存在猜測模型或 MCP 存活。`stop` 先合作停止 producer；Phase 3 起，正式 Windows 子程序由私有 Job 管理，期限／取消後留寬限、再只回收本工具程序樹並保存實際回條，不能據此宣稱取消遠端模型請求。強停不能通過交付驗收；缺少完整回條或鎖仍被持有時不重試。顯式注入的 unmanaged fake／非 Windows fixture 仍保留舊 pending 等自然退出契約，不可當正式 Job 行為。清理與失敗狀態詳見 [PROCESS_LIFECYCLE](PROCESS_LIFECYCLE.md)；`status` 不會啟動模型。

## 證據與判定

第一次 `run` 必須使用全新專用目錄，禁止覆寫、共用或指定正式 data/live。失敗後若要處理**同一事件**，使用下列 `retry`；不要建立新 run 代替原事件重試。每次 `retry` 都是使用者明確要求的一次真模型任務，整個 run 最多三次 attempt（含前置條件失敗），沒有自動模型重試。

```powershell
python -B scripts/acceptance_codex.py status --run-dir reports/msi-codex-001
python -B scripts/acceptance_codex.py retry --run-dir reports/msi-codex-001
```

`retry` 沿用原 runtime、event ID、query ID 與已保存結果；包含「結果落盤後 ACK 失敗」的恢復，不重新產生既有事件；若上一輪在前置檢查就失敗、尚無事件，則會在首次等待時產生第一個合成事件。原事件已 ACK 時會拒絕再次啟動模型。每次只核對自己的新增 wait，歷史 waits 保留。停止請求亦只作用於該 attempt，不會污染重試。沒有退出回條、鎖仍被持有、未知／損壞 metadata、超出三次上限都會拒絕，不能手改狀態或假 ACK 繞過。

這次使用 v2 的 `acceptance.json` 標記；前版未標記的 run 目錄保留原樣供唯讀檢閱，不自動匯入或重試。

- `acceptance.json`：專用 run 標記；`status.json` 為最新 attempt，包含 run/attempt ID、起迄及退出狀態；`cli_started` 不代表模型已執行。
- 第一輪證據在 run 根目錄；第二、三輪分別在 `attempts/0002`、`attempts/0003`。每輪的 `attempt-status.json` 與 `attempt-summary.json` 保留該輪證據；根目錄 `summary.json` 是最新判定。
- `codex.jsonl`：只保存這次新 CLI 的原始事件，包含實際 MCP 呼叫；不讀取任何既有 sessions。
- `codex.stderr.txt`：本次啟動錯誤。stdout／stderr 各最多保存 4 MiB，超量仍排空以免子程序阻塞，但標記 truncated 並使驗收失敗；不得把被截斷的成功片段當成完整證據。
- `capture-start.json`、`capture-exit.json`：同 attempt ID 的擷取／自然退出回條。缺少／不完整回條時不猜測子程序已退出。
- `runtime/local-wait-results.json`：wait 起迄、event ID、query ID、同事件結果。
- `runtime/outbox/eventguard.sqlite3`：耐久 outbox 與 ACK。
- `summary.json`：核對當輪恰好一次 wait、query、ACK 的實際回傳內容與順序、同事件／query ID、wait 起迄、reviewed_synthetic 結果、SQLite ACK、完整 CLI turn 及 CLI exit 0。缺項即失敗，agent 的文字「成功」不作證據。

成功需 `summary.passed=true` 且 `status.child_exited=true`。事件儲存層的 `real_agent_wake_verified=false` 不改成 true：它單獨無法證明模型執行。跨 CLI trace 與耐久狀態的驗收結果才是本次合成實驗證據，不能提升為主機安全、既有桌面任務接續或長期喚醒保證。

CLI JSONL 不揭露工具等待期間所有模型後端請求。因此 `idle_model_requests` 明示不可觀測；不能據此稱帳戶零用量。3 秒等待只驗證程式延遲 producer，不是長時低負載測量。要證明實際費用／閒置請求，需要平台本次請求／用量遙測，不能以 SDK 測試替代。

資料全在忽略的 reports 下，不提交、不自動上傳；本次 CLI 也可能產生其自身本機 log/state，保留在同 run 目錄。分享前自行檢閱，僅回報匿名摘要，勿上傳帳戶／環境資訊或真實資安紀錄。

## 逾時、取消與最簡替代方案

2026-10-22 核對已安裝 Codex 0.163.0 官方 tag（commit `83086188ae0614bd882818ff1aa23f3194962012`）：[DEFAULT_TOOL_TIMEOUT](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/codex-mcp/src/rmcp_client.rs) 為 **300 秒**，並非舊交接文件中的 60 秒。版本可能改變，入口明確覆寫 `tool_timeout_sec=60`，server wait 為 30 秒，不依賴預設或永久等待。

官方 [binding](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/codex-mcp/src/binding.rs) 與 [rmcp client](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/rmcp-client/src/rmcp_client.rs) 使用有限工具 timeout；不提供這個專案所需的永久等待／逾時不再推理保證。取消的協定依 [MCP cancellation](https://modelcontextprotocol.io/specification/2025-03-26/basic/utilities/cancellation)：合作取消，不對已取消 request 回覆。現有 SDK 測試已驗取消／EOF，但本次雲端未成功啟動 Codex 回合，**真正 Codex 的 timeout／取消後續行為仍未實測**，不從程式碼推定成功。

遇 `wait_expired` 時要求 agent 結束，禁止模型再等；server 的 `--single-wait` 會拒絕第二次等待，驗收亦拒絕重複 wait，執行器本身不重新啟動 Codex。這仍是短實驗，不是靠 prompt 保證永久待命。若要正式長期運作，最簡本機候選仍是純程式 dispatcher 無限期等耐久佇列，只在事件出現時啟動一次官方 `codex exec`，待同事件結果／ACK 才結案。該架構不會接續任意既有桌面任務，也仍需另行設計跨程序租約、取消、重試預算與模型持續帳戶存取範圍；本 PR 不把它當成已完成服務。

## 本次雲端結果與排障

- Python 3.13.5：核心與合成 smoke 可執行；此 runtime 無 SDK。
- 既有 Python 3.12.14 / MCP SDK 1.29.0：修正 `SessionMessage` 包裝相容性後，5 項真正 stdio SDK 測試通過，取消與 EOF 自然退出。這是相容性額外證據，MSI 仍以 Python 3.13 驗收。
- Codex CLI 0.163.0 可執行且 `login status` 顯示已登入；兩次實際驗收啟動皆 exit 1：`failed to initialize in-process app-server client: Read-only file system (os error 30)`。第二次已使用官方支援的單次 `sqlite_home`／`log_dir` 可寫路徑，結果相同。無 event ID、無 agent 工具呼叫，未證明模型接續，未改權限或搬移／複製憑證。
- 空閒時實際模型後端請求數、真正 Codex 取消／逾時、MSI Windows 原生採集及長期監看仍未驗證。

缺 SDK：換用既有可載入 SDK 的 Python，不自動下載。缺 CLI／登入：回報前置條件，不建立憑證。CLI 初始化失敗：檢查本次 stderr 與 writable state/log 設定，勿提權或繞過。CLI 結束但缺 query／ACK：summary 失敗，保留 outbox，先查 trace；不要人工 ACK 冒充 agent；需要重試時沿用 `retry --run-dir`，不能刪除原始證據。既有 monitor 的 fixture 啟停可用 `python -B scripts/acceptance_smoke.py` 驗證，正式 monitor 需另有 Windows 原生範圍。

## 開發驗證與提交節奏

先完成一批相關程式與文件，再在本機跑受影響測試及一次完整 suite，集中提交。未明確需要時不反覆推送或觸發遠端 CI。本次新增的 fake CLI／程序測試只證明協調、重試與檔案控制，不是新的真 Codex E2E；前述 app-server 雲端阻塞仍保留。
