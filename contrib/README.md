# 可選及 legacy 程式

- `mcp_bridge/` 是原 `src/eventguard/mcp/` 的停用 synthetic-only 雲端 bridge；核心不 import。原協定、安全、SQLite 與 in-process transport 測試保留，未建立網路、憑證或 listener。
- `legacy_delivery_validation.py` 只作舊 LocalWait 證據相容入口；新驗收使用 `scripts/validate_delivery.py`。舊 fixture 測試與格式保留，未轉寫原 runtime。

能力、授權、相容差異與唯一建議路徑見 [Phase 5](../docs/DELIVERY_CONSOLIDATION.md)。本目錄不是正常監看的前置條件；不要為查看證據啟動模型或服務。
