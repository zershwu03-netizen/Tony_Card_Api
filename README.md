# LINE 刷卡顧問 Bot 部署教學

## 需要準備的帳號
- GitHub 帳號（免費）
- LINE Developers 帳號（免費）
- Render 帳號（免費）
- Anthropic API Key（需付費，用多少付多少）

---

## 步驟一：申請 LINE Messaging API

1. 前往 https://developers.line.biz
2. 登入後點「Create a new provider」
3. 點「Create a Messaging API channel」
4. 填入 Channel 名稱（例如：刷卡顧問）
5. 建立完成後，進入 Channel 設定頁面：
   - 記下 **Channel secret**（在 Basic settings）
   - 點「Issue」產生 **Channel access token**（在 Messaging API）
   - 把這兩個值先存起來

---

## 步驟二：上傳程式碼到 GitHub

1. 前往 https://github.com 建立一個新的 repository（名稱例如：line-card-bot）
2. 把這三個檔案上傳進去：
   - `main.py`
   - `requirements.txt`
   - `render.yaml`

---

## 步驟三：在 Render 部署

1. 前往 https://render.com 並用 GitHub 登入
2. 點「New +」→「Web Service」
3. 選擇你剛建立的 GitHub repo
4. 設定如下：
   - Name：line-card-bot
   - Runtime：Python 3
   - Build Command：`pip install -r requirements.txt`
   - Start Command：`gunicorn main:app --bind 0.0.0.0:$PORT`
5. 往下找「Environment Variables」，新增以下三個：

   | Key | Value |
   |-----|-------|
   | LINE_CHANNEL_SECRET | （貼上步驟一的 Channel secret） |
   | LINE_CHANNEL_ACCESS_TOKEN | （貼上步驟一的 Channel access token） |
   | ANTHROPIC_API_KEY | （你的 Anthropic API Key） |

6. 點「Create Web Service」，等待部署完成（約 2-3 分鐘）
7. 部署完成後，記下你的網址，格式像：`https://line-card-bot.onrender.com`

---

## 步驟四：設定 LINE Webhook

1. 回到 LINE Developers，進入你的 Channel
2. 找到「Webhook URL」，填入：
   ```
   https://你的render網址/callback
   ```
   例如：`https://line-card-bot.onrender.com/callback`
3. 點「Verify」，應該會顯示成功
4. 把「Use webhook」打開

---

## 步驟五：加 Bot 為好友並測試

1. 在 LINE Developers 找到 Bot 的 QR code
2. 用 LINE 掃描加好友
3. 傳「你好」測試是否有回應
4. 傳「蝦皮買1000元」看看回覆是否正確

---

## 常見問題

**Q：Render 免費方案可以用嗎？**
A：可以，免費方案夠用，但閒置 15 分鐘後會休眠，第一則訊息回覆會慢 30 秒左右。可以升級付費方案（$7/月）避免這個問題。

**Q：Anthropic API 費用大概多少？**
A：Claude Sonnet 每次對話約 $0.001-0.003 USD，一般使用量每月不超過 $1。

**Q：想更新卡片優惠怎麼辦？**
A：修改 `main.py` 裡的 `CARDS_INFO` 字串，然後重新 push 到 GitHub，Render 會自動重新部署。

---

## 檔案說明

- `main.py`：主程式，包含所有邏輯
- `requirements.txt`：Python 套件清單
- `render.yaml`：Render 部署設定
