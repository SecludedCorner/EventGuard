# 正式任務事件入口查核

查核日期：2026-10-22。僅閱讀官方公開文件與本輪暴露的工具說明；沒有讀憑證／原始session、逆向服務、借用登入token或實送事件。

目前未取得能由普通背景程式向**這個指定Codex／dot長期任務**送event並喚醒的已驗證endpoint及授權。這是接線blocker，不等於宣稱所有平台都沒有事件能力。agent專用send_message工具與父子任務完成通知，不是背景程式的公開API。

官方 [MCP Events](https://developers.openai.com/plugins/build/mcp-events) 描述plugin的event discovery、subscribe及callback交付，並要求在ChatGPT測試完整訂閱與接收反應。這是候選整合方向；需要受支援plugin、訂閱、目的地與驗證，不能套用成現有任務的任意入口。本輪未建立plugin、訂閱或外部服務。

官方 [Scheduled tasks](https://learn.chatgpt.com/docs/automations) 說明受支援app事件觸發，並區分web/mobile與desktop/CLI的可用範圍。這不足以證明本機任意event可直接喚醒這個桌面任務，也不授權改用郵件／Slack／輪詢繞路。

官方 [Agents API session webhooks](https://developers.openai.com/api/docs/guides/agents-api/sessions/webhooks) 是API session生命週期通知與恢復方式；不是證明目前聊天任務已有可用ingress。本輪沒有API憑證、模型呼叫或外部傳輸。

接線前需核實：平台／task_ref、實際入口、來源驗證、允許資料、訂閱與撤銷、耐久ACK、真正agent_started/run_id、診斷回程與冪等。核實後才可依批准送最少合成資料。本版僅提供DisabledAdapter與synthetic-only本機MockReceiverAdapter；mock_received／ACK／mock_closed都不表示喚醒真實Codex／dot。
