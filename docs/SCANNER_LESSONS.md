# ai-security-scanner 研究與採納

查核日：2026-10-23。兩個子 agent 分別讀採集架構與結果操作介面，主線整合。公開來源固定於 [46b7d1900fc25ef8ae4e4b568b638c915f28d130](https://github.com/TED-H-com/ai-security-scanner/tree/46b7d1900fc25ef8ae4e4b568b638c915f28d130)，避免把日後 main 的變動混入本輪結論。這是讀碼研究，未執行上游掃描器或測試。

## 已採納

| 學習點與上游證據 | EventGuard 的實際改動 | 驗收與界線 |
| --- | --- | --- |
| [摘要與下一步優先](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/src/pages/FindingsPage.tsx#L3245-L3295)、[技術資料按需展開](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/src/pages/FindingsPage.tsx#L3962-L3985) | gui_presenter.event_summary 把既有 guidance 呈現為觀察事實、未知與限制、建議的唯讀查證；原始 JSON 另勾選展開 | 真 Tk 元件＋合成控制器核對預設摘要、展開／收合、不另查詢／ACK。首次盤點不稱新攻擊，恢復轉換不稱已修復；沒有新增診斷能力 |
| [本地結果篩選](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/src/pages/FindingsPage.tsx#L2557-L2581)、[無符合結果與清除](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/src/pages/FindingsPage.tsx#L3663-L3669) | 嚴重度／接收狀態篩選與清除；顯示符合、已載入、儲存總數及截斷；修正事件時間讀取 observed_at | 只篩目前最多 100 件，較早事件仍保存，不宣稱搜尋全庫。零符合不等於沒有事件或安全；晚到 inspect 回覆不顯示到錯誤選取事件下 |
| [不完整與合法觀察分開保存](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/src-tauri/src/adapters/mod.rs#L760-L819)、[壞列不抹除合法列的案例](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/src-tauri/tests/adapter_fixtures.rs#L1998-L2045) | WindowsCollectors 對有界前綴中的非物件列記 object／ContractError／invalid_collector_row，保留其餘合法觀察；有可用列則 partial，否則 error | 七來源 native／PowerShell 同契約合成測試；原因與計數有界，壞資料原文不入錯誤。錯誤外層仍拒絕，不能用 fallback 掩蓋；partial 不清 baseline 或判恢復 |
| [執行中共用輸出預算](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/container_runtime.rs#L2156-L2235) | Runner一偵測stdout與stderr合計超過4MiB，就先合作停止，再按原Job政策清理本工具子樹；保留output_limit與退出證據 | 非本工具Job不能強停；超量輸出不進正常解析，不等待原查詢期限。含真Windows私有Job合成flood測試，非安全事件採集 |
| [有界解析與重複欄位處理](https://github.com/TED-H-com/ai-security-scanner/blob/654dd7165112c38da4e7bf894fdccb9a251d2c1d/src-tauri/src/adapters/bounded_json.rs#L34-L130) | 標準庫JSON解碼前限制32層容器，解碼後拒絕重複key；Runner與PowerShell字串入口共用，防止後面的status覆蓋前面的拒讀 | 括號在字串中不算巢狀；Unicode逃脫後同名key仍拒絕。沒有引進上游串流解析器或新依賴 |

程式位置：[呈現](../src/eventguard/gui_presenter.py)、[Tk 操作](../src/eventguard/gui.py)、[視窗快照](../src/eventguard/desktop.py)、[採集邊界](../src/eventguard/collectors/windows.py)。對應測試：[呈現](../tests/test_gui_presenter.py)、[真 Tk 元件](../tests/test_gui.py)、[採集列隔離](../tests/test_collector_rows.py)、[總數契約](../tests/test_desktop.py)。實際命令、結果與提交綁定只記 [EVIDENCE](EVIDENCE.md)。

## 保持簡單的取捨

- 上游 [README](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/README.md#L12-L18) 描述首次使用下載工具；另有網路、雲端及可選模型測試範圍。這些是上游文件宣稱，本輪未執行；不帶入 EventGuard 的一般權限、標準庫、唯讀本機監看。
- 不搬入完整掃描引擎工作台、前端框架或跨版本掃描帳本。現有 SQLite／OperatorAPI／guidance 已足以支援這批改善，沒有再加代理層或持續雲端服務。
- 不搬用泛化漏洞影響、自動修復或「沒有發現問題即安全」的敘述。EventGuard 繼續以保存觀察、coverage 與 incident_conclusion=not_assessed 表示證據界線。
- 上游 [LICENSE](https://github.com/TED-H-com/ai-security-scanner/blob/46b7d1900fc25ef8ae4e4b568b638c915f28d130/LICENSE#L1-L5) 是 Apache 2.0。本輪只參考設計概念，EventGuard 程式獨立實作，沒有複製上游程式／資產、安裝依賴或更動本專案 MIT 授權。

最初採納那輪未重啟既有正式GUI／監看或接新receiver。後續正式MCP接線由使用者另行批准，狀態見STATUS；沒有重掃七來源、呼叫模型或建立排程。新介面於下次正常開啟時載入，不宣稱熱更新。這批合成及元件測試不能替代正式壞資料注入、長時soak或重開機驗收。
