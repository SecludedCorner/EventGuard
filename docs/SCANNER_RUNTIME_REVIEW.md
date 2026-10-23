# ai-security-scanner 執行與證據邊界讀碼

查核時間：2026-10-23（UTC+8）。固定上游 commit：`654dd7165112c38da4e7bf894fdccb9a251d2c1d`，PR #86；本地基底 `d46236fdd20d59ff4c9ff1c7c7091bfd497f484d`。本頁是唯讀原始碼研究，沒有執行上游、下載引擎、安裝容器、呼叫模型或重新採集正式主機。本輪只新增文件。

## 25 個如何執行

**已驗證（讀碼）**：registry 固定25個ID；25個均有 adapter 註冊，並共用容器 run-plan。這不代表25個 Windows 本機感測器，也不代表已在本機成功執行。catalog／包裝方案逐項盤點另見 [引擎清單研究](SCANNER_ENGINES.md)。

| 路徑 | 引擎 | 讀碼證據 |
| --- | --- | --- |
| 共用 cloud launcher | CloudQuery、Steampipe、Prowler、ScoutSuite、Cloudsplaining | [main.go:126–235](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/images/cloud-launcher/main.go#L126-L235)；固定路徑、供應者身分及權限檢查後分流 |
| 共用 M365 launcher | ScubaGear、Maester | [main.go:112–185](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/images/m365-launcher/main.go#L112-L185)；固定腳本與參數 |
| 共用 external launcher | Naabu、httpx、Nuclei | [main.go:445–452](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/images/external-launcher/main.go#L445-L452)；[授權與目標檢查:1489–1532](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/images/external-launcher/main.go#L1489-L1532) |
| 共用 local launcher | Semgrep、TruffleHog、Trivy、Grype、Kubescape、kube-bench | [main.go:287–403](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/images/local-launcher/main.go#L287-L403)；只接受各引擎指定的輸入 profile |
| 專用 launcher | Greenbone、Gitleaks、garak、Agentic Radar、MCP Armor | 分別為 `engines/images/greenbone-launcher/main.go:279–291`、`gitleaks/launcher/main.go:59–114`、`garak/launcher/main.py:193–223`、`agentic-radar/launcher/main.go:107–154`、`mcp-armor/launcher/main.go:113–162`（均於同一固定 commit 讀取） |
| 直接固定容器命令 | ZAP、Checkov、KICS、Syft | [catalog.json](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/catalog.json) 的 `command`；主機仍共用下述 run-plan，沒有共用 launcher 不等於未整合 |

計數為5+2+3+6+5+4=25；[registry.rs:13–39](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/registry.rs#L13-L39) 與 [adapters/mod.rs:525–601](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/adapters/mod.rs#L525-L601) 可相互核對。本頁沒有閱讀25個獨立 upstream repo 的全部原始碼，不能稱「所有 repo 全部看完」。

## 可借鑑的實際機制

| 機制與原始碼證據 | 對 EventGuard 的取捨 |
| --- | --- |
| run-plan 在執行前檢查 image digest、固定命令、路徑與網路契約；建立 read-only rootfs、cap-drop、no-new-privileges、CPU／RAM／PID／檔案上限與明確掛載。[container_runtime.rs:1259–1464](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/container_runtime.rs#L1259-L1464) | 保留「型別化輸入及單一執行邊界」觀念，不引入容器或25個引擎。EventGuard 已有固定查詢、私有 Job、deadline、4 MiB 合計輸出上限（`collectors/runner.py:16,56–71,123–191`）。 |
| stdout／stderr 共用原子位元組預算；執行期間偵測超量便中止本次樹，而非只於退出後才拒收；讀管線也有 drain deadline。[container_runtime.rs:2156–2235](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/container_runtime.rs#L2156-L2235) | **待採納候選**：本地 `_drain` 已限制保存量，但 `Runner.run` 到循環結束才檢查 oversize；可提早合作停止本工具 Job 並留退出回條，縮短已確定失敗的等待。尚未實作／測試。 |
| 先保存原始 artifact，normalize 失敗時保留待重解析狀態；同一 opened handle 驗證大小與 SHA256，避免驗一份再重開另一份。[artifact_store.rs:282–327](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/artifact_store.rs#L282-L327)、[orchestrator.rs:893–988](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/orchestrator.rs#L893-L988) | 可用於將來可選匯入資料的完整性；目前 EventGuard 用受控 SQLite 事件，沒有理由增加另一套 artifact 管線。hash 只能驗完整性，不代表來源可信。 |
| 解析限制 artifact／總位元組／列／字串／JSON 深度；省略資料明示 omitted，仍驗證跳過的 JSON 語法；重複 key 被省略時移除較早 verdict。[adapters/bounded_json.rs:34–130](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/adapters/bounded_json.rs#L34-L130)、[adapters/mod.rs:66–83](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/adapters/mod.rs#L66-L83) | 已採納的合法 sibling 保留／partial 原則應維持；不為4 MiB固定查詢立即引入串流解析架構。可另補深層 JSON、重複狀態 key 的 fail-closed 契約測試。未實作新解析器。 |
| findings、inventory observations、未評估目標、人工查核控制與 complete 分開；不因有輸出而聲稱完整。[adapter.rs:112–146](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/adapter.rs#L112-L146) | EventGuard 既有觀察、coverage、`incident_conclusion=not_assessed` 與 ACK 語義已相容；不把 inventory 升為漏洞或ACK升為已修。 |
| cancellation 先stop exact immutable container ID，ID須由本次cidfile＋完整ownership labels證明；cleanup未完成另存checkpoint，不假稱乾淨退出。[container_runtime.rs:2906–3038](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/container_runtime.rs#L2906-L3038)、[orchestrator.rs:640–742](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/orchestrator.rs#L640-L742) | 保留精確 ownership＋未確認就 blocked 的觀念。本地只以私有 Job 處理自身程序，不增加容器管理或 PID／名稱強停。 |

## 不照搬及未驗證

- **已驗證（讀碼）**：上游 Windows `CommandProcessTree` 先 `spawn` 再 `AssignProcessToJobObject`，不是 EventGuard 要求的執行前原子 Job 加入。不可拿來替換現有更嚴格做法。[container_runtime.rs:3278–3291](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/container_runtime.rs#L3278-L3291)、[2371–2380](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/container_runtime.rs#L2371-L2380)。
- **已驗證（讀碼）**：M365 容器 launcher 的固定 PowerShell 參數包含 ExecutionPolicy Bypass；EventGuard 明確禁止此旗標，不能採納。[m365-launcher/main.go:173–182](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/engines/images/m365-launcher/main.go#L173-L182)。
- **已驗證（讀碼）**：garak 實際啟動 native Python 並向批准模型端點送測試；MCP Armor 是指定設定快照的靜態檢查，不是 EventGuard 的事件接收器。兩者都不應為了「agent 收到 event」而被引入。見上列 launcher 及 catalog 的對應描述。
- **已驗證（讀碼）**：發行驗證程式核對 checksums、平台 digest、SBOM、來源 revision 與 GitHub attestation，含呼叫 `gh attestation verify`。[verify-publication-artifact.mjs:240–253](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/scripts/release/verify-publication-artifact.mjs#L240-L253)、[423–479](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/scripts/release/verify-publication-artifact.mjs#L423-L479)。本輪沒有執行它，沒有重新驗簽或拉取映像。
- **上游保存的聲稱／本輪未獨立重現**：[2026-10-23-publication.json:56–122](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/docs/engines/updates/2026-10-23-publication.json#L56-L122) 記錄 Trivy、Nuclei 的 Linux amd64 自有 fixture 執行與限制。這不等於25引擎跨平台全驗，也不是 EventGuard 或 Windows 實測。

結論：先完成當前專案 MCP 的真工具接收；本研究沒有擴充監看來源。後續最小候選是超量輸出的提早停止與小型 fail-closed 解析測試，須沿用既有 runner／Job／coverage 契約。既有前輪採納與測試仍見 [SCANNER_LESSONS](SCANNER_LESSONS.md)，不能把本輪讀碼充當新的功能驗收。
