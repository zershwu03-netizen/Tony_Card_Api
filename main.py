import os
import json
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import anthropic

app = Flask(__name__)

# 從環境變數讀取金鑰
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ──────────────────────────────────────────
# 你的信用卡資料（可自行更新）
# ──────────────────────────────────────────
CARDS_INFO = """
你的11張信用卡（2026上半年現行優惠）：

1. 永豐大戶卡（DAWHO）
   - 大戶等級（帳戶存10萬）：國內3.5%、國外4.5%，全通路無腦刷，無月上限
   - 大戶Plus等級（存100萬）：國內5%、國外6%，月上限500元
   - 悠遊卡自動加值：大戶3%、Plus 5%
   - 特色：不限通路、不需切換，最無腦

2. 台新黑狗卡（台新 Richart 卡）
   ★ 使用前須在 Richart Life APP 切換方案（每日可切換一次）
   需設定台新帳戶自動扣繳才享最高回饋
   - Pay著刷：台新Pay 3.8%（7-11/全家/新光三越等11萬家）；LINE Pay 2.3%
   - 天天刷 3.3%：超商/量販/藥妝/交通/加油充電
   - 大筆刷 3.3%：百貨（新光三越/SOGO/遠東）/UNIQLO/ZARA/IKEA等
   - 好饗刷 3.3%：全台餐廳/Uber Eats/foodpanda/KTV/指定飯店
   - 數趣刷 3.3%：蝦皮/momo/酷澎/PChome/Apple台灣官網
   - 玩旅刷 3.3%：海外消費/機票/訂房
   - 假日刷 2%：假日不限通路（含LINE Pay/街口）
   - 保費：免切換1.3%無上限

3. 玉山 Unicard（one for all）
   ★ 每月底前在玉山Wallet APP切換方案
   - 基本1%（需帳單e化+玉山帳戶自動扣繳）
   - 簡單選：百大特店合計3%，月上限1,000點
   - 任意選：自選8家特店合計3.5%，月上限1,000點
   - UP選：百大特店合計4.5%，月上限5,000點（需149點訂閱費）
   - 百大特店含LINE Pay/蝦皮/momo/Uber Eats/家樂福/各大百貨等
   - 注意：不支援LINE Pay/街口間接刷卡享特店回饋

4. 玉山 UBear 卡
   - 網購/行動支付（LINE Pay/街口/蝦皮/momo/線上消費）：3%，月上限150元（約7,500元）
   - 訂閱服務（Netflix/ChatGPT/Gemini/Steam/Nintendo/PS）：10%，月上限100元
   - 超商/全聯/速食：不適用，僅1%

5. 玉山熊本熊向左走卡（日圓雙幣卡）
   - 日本一般消費：2.5%無上限
   - 日本指定商店：最高8.5%（需登錄，月上限500元）
   - 日本PayPay：3.5%+免手續費，季上限100元

6. 玉山 Pi 拍錢包聯名卡
   - 一般消費：基本1%，月滿3萬享3%（月上限1,000P）
   - 全家（綁Pi App結帳）：5%，月上限100P
   - 保費：1.2%無上限，或最高12期0利率

7. 中信 foodpanda 聯名卡
   - foodpanda平台：最高5%胖達幣（月上限200元）
   - 國內一般：1%；海外實體：2%

8. 國泰世華蝦皮購物聯名卡
   - 蝦皮站內：0.5%；超品牌日：6%（需登錄）
   - 指定站外通路：最高7%（需每波登錄，上限3,000蝦幣）
   - LINE Pay/街口不適用

9. 富邦 momo 聯名卡
   - momo站內：3%（月上限1,000點）；指定品牌：最高7%（免登錄）
   - 站外一般：1%；捷運（一卡通）：2%無上限

10. 中信中油聯名卡
    - 中油直營站：VIP點數約0.5%
    - 配合中油Pay週一儲值：總計最高6.8%

11. 聯邦吉鶴卡（JCB晶緻卡）
    - 日幣計價消費：2.5%無上限
    - 日本實體+Apple Pay QUICPay（前月帳單滿3萬）：合計最高5%
    - 日本指定通路：合計最高8%（活動期上限600元）
    - 萊爾富超商（台灣直刷）：5%無上限
    - 台灣日系名店（UNIQLO/大創等）：合計5.5%，月上限500元
    - 國內一般：1%
"""

SYSTEM_PROMPT = f"""你是一個台灣信用卡刷卡顧問，幫用戶從他持有的信用卡中找出最划算的刷法。

{CARDS_INFO}

根據用戶的消費情境，用繁體中文回覆，格式如下：

🏆 最佳選擇：[卡片名稱]
💰 回饋：[回饋率]

📋 怎麼刷：
[2-4句具體說明，包含：要切換什麼方案、用什麼方式付款、有什麼條件]

🥈 備選：[卡片名稱] [回饋率]
[一句說明]

⚠️ 注意：[重要限制，若無則省略此行]

規則：
- 只推薦用戶持有的11張卡
- 台新Richart必須說明切換哪個方案
- 玉山Unicard必須說明選哪個方案
- 回答要簡潔，手機讀起來不費力
- 只回答刷卡建議，不回答其他問題"""


def get_card_advice(user_message: str) -> str:
    """呼叫 Claude API 取得刷卡建議"""
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"消費情境：{user_message}"}
            ]
        )
        return response.content[0].text
    except Exception as e:
        return f"抱歉，分析時發生錯誤，請稍後再試。\n（錯誤：{str(e)[:50]}）"


# ──────────────────────────────────────────
# LINE Webhook 路由
# ──────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()

    # 歡迎訊息
    if user_text in ["你好", "hi", "Hi", "hello", "Hello", "開始", "說明", "help"]:
        reply = (
            "👋 你好！我是你的刷卡顧問。\n\n"
            "告訴我你要在哪裡消費，我幫你決定刷哪張卡、怎麼刷最划算！\n\n"
            "例如：\n"
            "・蝦皮買東西 1000 元\n"
            "・在 foodpanda 訂晚餐\n"
            "・去全家買咖啡\n"
            "・去日本旅遊購物\n"
            "・訂 Netflix\n"
            "・去中油加油"
        )
    else:
        reply = get_card_advice(user_text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


@app.route("/", methods=["GET"])
def index():
    return "LINE 刷卡顧問 Bot 運作中 ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
