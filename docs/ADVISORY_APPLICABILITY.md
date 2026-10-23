# 公告與本機適用性

本功能只判斷是否值得調查。不判定可利用。不宣稱主機安全。

## 盤點範圍

只讀 `inventory.paths` 指定的檔案或資料夾。預設路徑為空。空清單代表尚未盤點。

資料夾只尋找 `Cargo.lock`、`Cargo.toml`、`rust-toolchain.toml`、`pyproject.toml`、`uv.lock`。預設最多往下兩層。每個資料夾、總檔案與資產都有上限。超限明示錯誤。不默默視為完整。

不讀 `.git`、`.codex`、`.ssh`、雲端憑證目錄、`target`、`node_modules`、`.venv`。拒絕符號連結、junction、reparse point、秘密檔名與超大檔。讀取前後核對檔案身分及大小。這不是對抗同帳戶惡意竄改的隔離邊界。

不執行 `cargo`、`rustup`、`uv`、版本查詢、`build.rs` 或其他程式。不安裝依賴。不讀其他主機。不解析依賴中的執行指令。

```json
{
  "inventory": {
    "paths": [
      "C:/work/approved-project/Cargo.lock",
      "C:/work/approved-project/Cargo.toml",
      {"path": "C:/work/approved-project/linux-facts.json", "kind": "facts"}
    ],
    "max_files": 128,
    "max_file_bytes": 2097152,
    "max_assets": 2048,
    "max_depth": 2
  }
}
```

只有指定 `kind: facts` 的 JSON 才可提供人工事實。每項都標為 `user_asserted`。檔案必須由操作者維護。不是實機採集證明。

```json
{
  "assets": [{
    "ecosystem": "linux",
    "component": "linux-kernel",
    "version": "6.1.2",
    "facts": {
      "observed_at": "2026-10-23T00:00:00Z",
      "distribution": "Debian",
      "module_present": true,
      "module_builtin": true,
      "module_loaded": false,
      "service_enabled": "unknown",
      "reachable": "unknown",
      "running": "unknown",
      "container": false,
      "backport": "unknown"
    }
  }]
}
```

Rust 人工事實可指定 `features` 布林表、`feature_state: observed`、`tls_backend`、`root_source`、`deployed` 與 `running`。只有 manifest 的 features 是「宣告」，不是實際啟用。

## 資產與結果契約

`collect_inventory(config, now)` 回傳 `collected_at`、`assets`、`coverage`、`status`。資產含 `asset_id`、`ecosystem`、`component`、`version`、`origin`、`facts`。同元件多版本分開保存。路徑以雜湊 `file_ref` 參照。不把原始路徑放進結果。

每個檔案 coverage 為 `success`、`denied` 或 `error`。拒讀含固定原因碼及異常類型。沒有原始例外全文。整體為 `success`、`partial` 或 `unknown`。拒讀不推定安全。

`evaluate(record, inventory, now)` 回傳 `status`、`reason_codes`、`asset_refs`、`evidence`、`fix_available`、`conditions`。

| 狀態 | 意義 |
| --- | --- |
| `possible` | 盤點看到符合公告範圍的元件。仍須查證實際部署與利用前提 |
| `not_applicable` | 有明確範圍排除、條件不符、撤回或對應套件修補證據。只對本次證據有效 |
| `unknown` | 無盤點、拒讀、過期、版本語意不支援、backport 不明或前提不足 |

缺少元件不是已證明不存在。inventory 預設 24 小時過期。人工事實可自帶更早 `observed_at`。重新讀取檔案不會更新該事實的時間。

## 版本與前提

- Rust/Cargo 使用 SemVer。處理預發布、build metadata、caret、tilde、部分版號與複合比較。
- OSV 支援 `SEMVER` 與已支援生態的 `ECOSYSTEM` 範圍。Git ancestry 未實作。遇到 GIT 範圍標未知。
- RustSec `patched`、`unaffected` 各清單為 OR。每條 requirement 的逗號為 AND。
- `webpki-roots` 的 `0.26.11` wrapper 需核對父套件依賴圖。只看到 wrapper 版號，或 lockfile 也出現一個父套件，均不足。標未知。
- Debian 版號採 epoch、upstream、revision 與 tilde 語意。Python 支援 canonical PEP 440 版號及 `==`、`!=`、`<`、`<=`、`>`、`>=`、`~=`、前綴 wildcard。uv 的 `< 0.13.4` 可比對。非正規別名及排他界線的預發布政策不明時，標未知。RPM 尚未實作。不能用字串排序代替。[版本規格](https://packaging.python.org/en/latest/specifications/version-specifiers/)。
- 發行版 backport 要有公告 ID、精確安裝套件版號與 vendor HTTPS 證據。單純人工填入網址不算 vendor 確認。還須已擷取的高信心公告提供同套件的已發布修補版號及同來源 URL。比對才可排除該套件範圍。安裝事實仍標 `user_asserted`。它不證明宿主安全，也不證明已運作新版本。缺證據標未知。
- 模組存在、編入核心、已載入、服務啟用及可達性是分開的事實。未載入不排除 built-in。容器不能證明自己的宿主核心狀態。
- Rust lockfile 不證明 optional feature、TLS backend、根憑證來源、已部署產物或目前執行版本。
- Python 的 uv 版號不證明其內嵌 Rust crate 清單。無已部署產物證據時，不將 uv 與某 crate 自動配對。
- 補丁提出、合併、發布、安裝及實際執行分開。`fix_available` 只接受已發布版本／套件階段。不表示主機已修好。

測試為固定資料。測試檔：`tests/test_intelligence_applicability.py`。涵蓋多版本、預發布、wrapper、optional feature、backport、built-in、容器、拒讀、過期、限制及對抗性名稱。它不是 Linux 實機採集或漏洞利用驗證。
