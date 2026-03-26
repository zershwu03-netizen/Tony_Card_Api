import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from google import genai

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# ──────────────────────────────────────────
# 刷卡規則判斷邏輯
# ──────────────────────────────────────────

RULES = [
    {
        "keywords": ["netflix", "chatgpt", "gemini", "steam", "nintendo", "playstation", "ps5", "訂閱"],
        "card": "玉山 UBear 卡",
        "rate": "10%",
        "how": "直接刷玉山 UBear 卡，於原平台消費（不可透過 Google/PayPal 代扣）。月上限 100 元回饋。",
        "caution": "超商/全聯不適用此回饋，僅限指定訂閱平台。"
    },
    {
        "keywords": ["全家", "familymart", "family mart"],
        "card": "玉山 Pi 拍錢包聯名卡",
        "rate": "5%",
        "how": "打開 Pi 拍錢包 App，綁定玉山 Pi 卡後，在全家直接用 Pi App 掃碼結帳。月上限 100 P幣（約 2,000 元額度）。",
        "backup": "聯邦吉鶴卡（不適用）/ 台新Richart卡切換「Pay著刷」用台新Pay結帳 3.8%",
        "caution": "必須用 Pi 拍錢包 App 掃碼才有 5%，直接刷實體卡只有 1%。"
    },
    {
        "keywords": ["7-11", "711", "seven", "全聯", "px", "pxmart", "萊爾富", "hilife", "ok超商", "超商"],
        "card": "台新 Richart 卡",
        "rate": "3.8%",
        "how": "在 Richart Life App 切換「Pay著刷」方案，結帳時用台新Pay（或 Apple Pay / Google Pay 綁台新卡）掃碼付款。",
        "backup": "永豐大戶卡 3.5%（無腦刷，不需切換）",
        "caution": "萊爾富可改刷聯邦吉鶴卡享 5% 折扣（直刷或 Apple Pay）。"
    },
    {
        "keywords": ["蝦皮", "shopee"],
        "card": "國泰世華蝦皮聯名卡",
        "rate": "0.5%（平時）/ 6%（超品牌日需登錄）",
        "how": "直接在蝦皮 App 結帳時選擇蝦皮聯名卡付款。超品牌日記得提前去蝦皮 App 登錄活動。",
        "backup": "台新 Richart 卡切換「數趣刷」3.3% / 玉山 UBear 卡 3%（月上限 7,500 元）",
        "caution": "平時 0.5% 回饋偏低，建議蝦皮一般購物優先用台新數趣刷或 UBear 卡。"
    },
    {
        "keywords": ["momo", "momo購物", "富邦momo"],
        "card": "富邦 momo 聯名卡",
        "rate": "3%（一般）/ 最高 7%（指定品牌）",
        "how": "在 momo 購物網結帳時選擇富邦 momo 卡付款。指定品牌免登錄自動加碼，結帳前可查看是否有 +4% 標示。",
        "backup": "台新 Richart 卡切換「數趣刷」3.3% / 玉山 UBear 卡 3%",
        "caution": "momo 站內 3% 月上限 1,000 mo幣（約 33,333 元），超過後回饋降低。"
    },
    {
        "keywords": ["foodpanda", "熊貓", "外送", "uber eats", "ubereats"],
        "card": "中信 foodpanda 聯名卡",
        "rate": "最高 5%",
        "how": "在 foodpanda App 結帳時選擇中信 foodpanda 聯名卡付款，1% 基本 + 加碼 4%，月上限 200 胖達幣。",
        "backup": "台新 Richart 卡切換「好饗刷」3.3%（Uber Eats / foodpanda 都適用）",
        "caution": "中信 foodpanda 卡的 5% 只限 foodpanda 平台，Uber Eats 請用台新好饗刷。"
    },
    {
        "keywords": ["中油", "加油", "cpc"],
        "card": "中信中油聯名卡",
        "rate": "最高 6.8%",
        "how": "下載中油 App，綁定中信中油聯名卡，週一在 App 內先儲值 3,000 元，再去中油直營站用中油 Pay 加油。",
        "backup": "永豐大戶卡 3.5%（直接刷卡，最無腦）",
        "caution": "最高 6.8% 需要：週一儲值 + 使用中油 Pay + 中油直營站，條件較多。懶得設定就刷永豐大戶卡。"
    },
    {
        "keywords": ["日本", "japan", "藥妝", "松本清", "唐吉訶德", "don quijote", "bic camera", "電器", "免稅"],
        "card": "玉山熊本熊向左走卡",
        "rate": "最高 8.5%",
        "how": "去日本前先登錄活動（玉山官網），在指定商店（藥妝/電器/百貨/樂園）直接刷實體卡或綁 Apple Pay 付款。",
        "backup": "聯邦吉鶴卡 最高 8%（指定通路含唐吉訶德/UNIQLO等，需 Apple Pay QUICPay）",
        "caution": "熊本熊卡 8.5% 月上限 500 元，超過後改刷聯邦吉鶴卡補滿額度。"
    },
    {
        "keywords": ["uniqlo", "大創", "daiso", "日系"],
        "card": "聯邦吉鶴卡",
        "rate": "5.5%（台灣門市）",
        "how": "在台灣 UNIQLO / 大創門市，直接刷聯邦吉鶴卡實體卡或用 Apple Pay / Google Pay 綁吉鶴卡付款。月上限 500 元。",
        "backup": "台新 Richart 卡切換「大筆刷」3.3%（UNIQLO/ZARA 均適用）",
        "caution": "聯邦吉鶴卡是 JCB，部分小店可能不支援，建議備用台新大筆刷。"
    },
    {
        "keywords": ["百貨", "新光三越", "sogo", "遠東", "漢神", "微風", "誠品"],
        "card": "台新 Richart 卡",
        "rate": "3.8%（新光三越）/ 3.3%（其他百貨）",
        "how": "新光三越：在 Richart Life App 切換「Pay著刷」，用台新Pay結帳享 3.8%。其他百貨：切換「大筆刷」享 3.3%。",
        "backup": "玉山 Unicard UP選 4.5%（月底前在玉山Wallet選 UP選，並將該百貨加入特店）",
        "caution": "玉山 Unicard UP選需先訂閱（149點/月），但月上限 5,000 點，大額消費划算。"
    },
    {
        "keywords": ["保費", "保險", "壽險", "車險", "產險"],
        "card": "台新 Richart 卡",
        "rate": "1.3%",
        "how": "直接刷台新 Richart 卡繳保費，免切換、免登錄，自動享 1.3% 台新Point 回饋，無上限。",
        "backup": "玉山 Pi 拍錢包卡 1.2%（選一次付清，不分期）",
        "caution": "保費回饋普遍偏低，台新 1.3% 已是你手上最高的了。"
    },
    {
        "keywords": ["海外", "國外", "出國", "歐洲", "美國", "韓國", "泰國"],
        "card": "永豐大戶卡",
        "rate": "4.5%（大戶等級）/ 6%（Plus等級）",
        "how": "直接刷永豐大戶卡，不需切換、不需登錄，全通路海外消費自動 4.5% 回饋。",
        "backup": "台新 Richart 卡切換「玩旅刷」3.3%（含機票/訂房）",
        "caution": "日本消費請改用熊本熊卡或吉鶴卡，回饋更高。"
    },
    {
        "keywords": ["一般", "其他", "不知道", "隨便"],
        "card": "永豐大戶卡",
        "rate": "3.5%",
        "how": "直接刷永豐大戶卡，國內全通路無腦 3.5%，不需切換任何方案。",
        "backup": "台新 Richart 卡假日切換「假日刷」2%（假日不限通路）",
        "caution": "永豐大戶卡需維持帳戶存款 10 萬以上才有大戶等級。"
    },
]

WELCOME_MSG = """👋 你好！我是你的刷卡顧問。

告訴我你要在哪裡消費，我幫你決定刷哪張卡、怎麼刷最划算！

範例：
・蝦皮買東西
・在 foodpanda 訂晚餐
・去全家買咖啡
・去日本藥妝店
・訂 Netflix
・去中油加油
・新光三越百貨

直接輸入你的消費情境就好 👇"""


def build_rules_text() -> str:
    lines = []
    for rule in RULES:
        lines.append(f"【關鍵字】{', '.join(rule['keywords'])}")
        lines.append(f"  最佳卡片：{rule['card']}，回饋：{rule['rate']}")
        lines.append(f"  怎麼刷：{rule['how']}")
        if rule.get("backup"):
            lines.append(f"  備選：{rule['backup']}")
        if rule.get("caution"):
            lines.append(f"  注意：{rule['caution']}")
        lines.append("")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""你是一位專業的信用卡刷卡顧問，使用者會告訴你他要在哪裡消費，你要根據以下規則表給出最佳建議。

規則表：
{build_rules_text()}

回覆規則：
1. 根據使用者的消費情境，從規則表中找出最適合的卡片
2. 用親切口語的繁體中文回覆，不要太正式
3. 回覆格式：
   🏆 最佳選擇：[卡片名稱]
   💰 回饋：[回饋率]

   📋 怎麼刷：
   [說明]

   🥈 備選：[備選卡片]（如果有的話）

   ⚠️ 注意：[注意事項]（如果有的話）
4. 如果情境不明確，請追問使用者
5. 回覆要簡潔，不要超過 300 字
6. 如果完全找不到對應規則，建議刷永豐大戶卡 3.5%"""


def get_advice(text: str) -> str:
    try:
        prompt = f"{SYSTEM_PROMPT}\n\n使用者說：{text}"
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return get_advice_fallback(text)


def get_advice_fallback(text: str) -> str:
    text_lower = text.lower()
    for rule in RULES:
        for keyword in rule["keywords"]:
            if keyword in text_lower:
                msg = f"🏆 最佳選擇：{rule['card']}\n"
                msg += f"💰 回饋：{rule['rate']}\n\n"
                msg += f"📋 怎麼刷：\n{rule['how']}\n"
                if rule.get("backup"):
                    msg += f"\n🥈 備選：{rule['backup']}\n"
                if rule.get("caution"):
                    msg += f"\n⚠️ 注意：{rule['caution']}"
                return msg
    return (
        "🤔 我不太確定這個消費情境，建議直接刷：\n\n"
        "🏆 永豐大戶卡\n"
        "💰 回饋：3.5%（國內全通路）\n\n"
        "📋 怎麼刷：\n直接刷卡，不需切換任何方案，最無腦。"
    )


# ──────────────────────────────────────────
# LINE Webhook
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

    if user_text.lower() in ["你好", "hi", "hello", "開始", "help", "說明", "?"]:
        reply = WELCOME_MSG
    else:
        reply = get_advice(user_text)

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
