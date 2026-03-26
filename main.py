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
# 刷卡規則（11張卡）
# ──────────────────────────────────────────
RULES = [
    {
        "keywords": [
            "全家", "familymart", "family mart", "pi錢包", "pi拍錢包",
            "全家咖啡", "全家便利商店", "全家超商", "全家買"
        ],
        "card": "玉山 Pi 拍錢包聯名卡",
        "rate": "5%",
        "how": "打開 Pi 拍錢包 App，綁定玉山 Pi 卡後，在全家直接用 Pi App 掃碼結帳。月上限 100 P幣（約 2,000 元額度）。",
        "caution": "必須用 Pi 拍錢包 App 掃碼才有 5%，直接刷實體卡只有 1%。"
    },
    {
        "keywords": [
            "foodpanda", "熊貓", "food panda", "熊貓外送", "foodpanda訂餐"
        ],
        "card": "中國信託 foodpanda 聯名卡",
        "rate": "最高 5%",
        "how": "在 foodpanda App 結帳時選擇中信 foodpanda 聯名卡付款，1% 基本 + 加碼 4%，月上限 200 胖達幣。",
        "caution": "5% 只限 foodpanda 平台，Uber Eats 不適用。"
    },
    {
        "keywords": [
            "蝦皮", "shopee", "蝦皮購物", "shopee mall", "蝦皮買", "蝦皮下單"
        ],
        "card": "國泰世華蝦皮聯名卡",
        "rate": "0.5%（平時）/ 6%（超品牌日需登錄）",
        "how": "直接在蝦皮 App 結帳時選擇蝦皮聯名卡付款。超品牌日記得提前去蝦皮 App 登錄活動。",
        "caution": "平時 0.5% 回饋偏低，超品牌日才划算，記得提前登錄。"
    },
    {
        "keywords": [
            "momo", "momo購物", "富邦momo", "momo.com", "momo網購", "momo買"
        ],
        "card": "富邦銀行 momo 聯名卡",
        "rate": "3%（一般）/ 最高 7%（指定品牌）",
        "how": "在 momo 購物網結帳時選擇富邦 momo 卡付款。指定品牌免登錄自動加碼，結帳前可查看是否有 +4% 標示。",
        "caution": "momo 站內 3% 月上限 1,000 mo幣（約 33,333 元），超過後回饋降低。"
    },
    {
        "keywords": [
            "中油", "加油", "cpc", "台灣中油", "加油站", "油錢",
            "加95", "加92", "柴油", "去加油", "加油去"
        ],
        "card": "中國信託中油聯名卡",
        "rate": "最高 6.8%",
        "how": "下載中油 App，綁定中信中油聯名卡，週一在 App 內先儲值 3,000 元，再去中油直營站用中油 Pay 加油。",
        "backup": "永豐大戶卡 3.5%（直接刷卡，最無腦）",
        "caution": "最高 6.8% 需要：週一儲值 + 使用中油 Pay + 中油直營站，條件較多。懶得設定就刷永豐大戶卡。"
    },
    {
        "keywords": [
            "uniqlo", "大創", "daiso", "日系", "優衣庫", "無印良品",
            "muji", "gu", "nitori", "宜得利", "日系品牌", "日系門市",
            "吉鶴"
        ],
        "card": "聯邦銀行吉鶴卡",
        "rate": "5.5%（台灣日系門市）",
        "how": "在台灣 UNIQLO / 大創 / MUJI 等日系品牌門市，直接刷聯邦吉鶴卡或用 Apple Pay / Google Pay 綁吉鶴卡付款。月上限 500 元。",
        "caution": "吉鶴卡是 JCB，部分小店可能不支援。台灣一般消費回饋低，建議只在日系通路使用。"
    },
    {
        "keywords": [
            "uber eats", "ubereats", "餐廳", "吃飯", "台新gogo",
            "gogo卡", "黑狗卡", "gogo黑狗", "台新黑狗", "吃東西", "用餐",
            "早餐", "午餐", "晚餐", "便當", "小吃", "夜市", "飲料",
            "手搖飲", "珍奶", "外帶", "聚餐", "火鍋", "燒肉", "燒烤",
            "拉麵", "牛排", "壽司", "麵食", "快餐", "自助餐"
        ],
        "card": "台新 GOGO 黑狗卡",
        "rate": "最高 5%（餐飲/外送）",
        "how": "在 Uber Eats、餐廳等餐飲消費直接刷台新 GOGO 黑狗卡，享最高 5% 回饋。部分通路需用 Apple Pay / Google Pay 綁卡付款。",
        "caution": "回饋上限及指定通路請以台新官網最新活動為準。"
    },
    {
        "keywords": [
            "netflix", "chatgpt", "steam", "nintendo", "playstation",
            "ps5", "訂閱", "disney", "disney+", "youtube premium",
            "spotify", "apple music", "hbo", "friday影音", "myvideo",
            "線上遊戲", "game", "遊戲課金", "app store", "google play",
            "ubear", "影音平台", "串流"
        ],
        "card": "玉山 UBear 卡",
        "rate": "10%（指定訂閱平台）",
        "how": "直接刷玉山 UBear 卡，於 Netflix、ChatGPT、Steam、Disney+ 等指定平台消費，享 10% 回饋。月上限 100 元回饋。",
        "caution": "僅限指定訂閱平台，不可透過 Google/PayPal 代扣。超商/全聯不適用。"
    },
    {
        "keywords": [
            "日本", "japan", "藥妝", "松本清", "唐吉訶德", "don quijote",
            "bic camera", "電器", "免稅", "熊本熊", "東京", "大阪",
            "京都", "北海道", "沖繩", "日本旅遊", "赴日", "cosme",
            "loft", "animate", "秋葉原", "心齋橋", "新宿", "涉谷",
            "原宿", "銀座", "池袋", "梅田", "難波", "道頓堀"
        ],
        "card": "玉山熊本熊向左走卡",
        "rate": "最高 8.5%（日本指定通路）",
        "how": "去日本前先登錄活動（玉山官網），在指定商店（藥妝/電器/百貨/樂園）直接刷實體卡或綁 Apple Pay 付款。",
        "backup": "聯邦吉鶴卡 最高 8%（唐吉訶德/UNIQLO等，需 Apple Pay QUICPay）",
        "caution": "熊本熊卡 8.5% 月上限 500 元，超過後改刷聯邦吉鶴卡補滿額度。"
    },
    {
        "keywords": [
            "one for all", "oneforall", "玉山one", "unicard", "玉山unicard",
            "超商", "7-11", "711", "全聯", "萊爾富", "ok超商", "hilife",
            "便利商店", "seven eleven", "統一超商", "line pay", "linepay",
            "街口", "百貨", "新光三越", "遠東百貨", "家樂福",
            "簡單選", "任意選", "up選", "pxmart", "全聯福利中心"
        ],
        "card": "玉山 ONE for ALL 卡（玉山 Unicard）",
        "rate": "簡單選 3% / 任意選 3.5% / UP選 4.5%",
        "how": "在玉山Wallet App切換方案：\n🔹 簡單選(3%)：百大特店通通有，月上限1,000點\n🔸 任意選(3.5%)：自選8家特店，月上限1,000點\n⭐ UP選(4.5%)：月訂閱149點，月上限5,000點\n\n推薦選 LINE Pay + 街口 + 常用電商共8家加入任意選。",
        "caution": "非百大特店只有1%基本回饋。月底前在玉山Wallet App切換方案。"
    },
    {
        "keywords": [
            "coupang", "酷澎", "pchome", "yahoo購物", "博客來", "生活市集",
            "樂天", "東森購物", "網購", "網路購物", "線上購物", "電商",
            "官網下單", "app內購買", "網拍", "91app",
            "訂房", "booking", "agoda", "hotels.com", "trivago",
            "airbnb", "住宿", "旅館", "飯店訂房", "民宿",
            "機票", "航空", "訂機票", "買機票", "廉航",
            "tiger air", "虎航", "捷星", "亞航", "airasia",
            "旅遊", "旅行", "出遊", "行程", "出國",
            "klook", "kkday", "旅遊票券", "景點門票",
            "海外", "國外", "歐洲", "美國", "韓國", "泰國",
            "英國", "澳洲", "新加坡", "香港", "澳門", "中國",
            "法國", "德國", "義大利", "西班牙", "土耳其",
            "一般消費", "一般", "其他", "不知道", "隨便",
            "實體消費", "刷卡", "買東西", "消費"
        ],
        "card": "永豐大戶卡",
        "rate": "3.5%（國內）/ 4.5%（海外）",
        "how": "直接刷永豐大戶卡，國內全通路無腦 3.5%，海外消費自動 4.5%，不需切換任何方案。訂房/機票/旅遊平台也適用。",
        "backup": "玉山 Unicard UP選（旅遊特店在百大內可達4.5%）",
        "caution": "需維持帳戶存款 10 萬以上才有大戶等級。日本消費建議改用熊本熊卡回饋更高。"
    },
]

CARDS_LIST = """1. 玉山 Pi 拍錢包聯名卡
2. 中國信託 foodpanda 聯名卡
3. 國泰世華蝦皮聯名卡
4. 富邦銀行 momo 聯名卡
5. 中國信託中油聯名卡
6. 聯邦銀行吉鶴卡
7. 永豐大戶卡
8. 台新 GOGO 黑狗卡
9. 玉山 ONE for ALL 卡
10. 玉山 UBear 卡
11. 玉山熊本熊向左走卡"""

WELCOME_MSG = f"""👋 你好！我是你的刷卡顧問 💳

我只推薦以下11張卡的最佳使用方式：
{CARDS_LIST}

告訴我你要在哪裡消費，我幫你決定刷哪張最划算！

範例：
・去全家買咖啡 → Pi拍錢包卡 5%
・在蝦皮買東西 → 蝦皮聯名卡
・訂 Netflix → UBear卡 10%
・去日本藥妝店 → 熊本熊卡 8.5%
・在 momo 網購 → momo聯名卡 3~7%
・去中油加油 → 中油聯名卡 6.8%
・coupang/訂房/機票 → 永豐大戶卡 3.5~4.5%
・Uber Eats/餐廳 → GOGO黑狗卡 5%

直接輸入消費情境就好 👇"""


def build_rules_text() -> str:
    lines = []
    for rule in RULES:
        lines.append(f"【關鍵字】{', '.join(rule['keywords'][:8])}...")
        lines.append(f"  最佳卡片：{rule['card']}，回饋：{rule['rate']}")
        lines.append(f"  怎麼刷：{rule['how'][:100]}...")
        if rule.get("backup"):
            lines.append(f"  備選：{rule['backup']}")
        if rule.get("caution"):
            lines.append(f"  注意：{rule['caution'][:80]}...")
        lines.append("")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""你是一位專業的信用卡刷卡顧問，擅長語意理解。

【重要限制】你只能從以下11張卡中給建議：
{CARDS_LIST}

【通路對應】
- 全家超商 → 玉山Pi拍錢包卡 5%（需用Pi App掃碼）
- foodpanda外送 → 中信foodpanda聯名卡 5%
- 蝦皮購物 → 國泰蝦皮聯名卡 6%（超品牌日）
- momo購物 → 富邦momo聯名卡 3~7%
- 加油/中油 → 中信中油聯名卡 6.8%
- UNIQLO/大創/MUJI/日系品牌台灣門市 → 聯邦吉鶴卡 5.5%
- Uber Eats/餐廳/外食 → 台新GOGO黑狗卡 5%
- Netflix/Disney+/Spotify/Steam/訂閱 → 玉山UBear卡 10%
- 日本旅遊/藥妝/電器/免稅 → 玉山熊本熊向左走卡 8.5%
- 7-11/全聯/LINE Pay/街口/百貨 → 玉山ONE for ALL卡 3~4.5%
- coupang/酷澎/訂房/agoda/機票/旅遊/海外/一般消費 → 永豐大戶卡 3.5~4.5%

【語意擴展範例】
- "酷澎"="coupang"=網購平台 → 永豐大戶卡
- "訂房"="booking"="agoda"=住宿訂購 → 永豐大戶卡
- "買機票"="航空"=機票訂購 → 永豐大戶卡
- "東京"="大阪"=日本城市 → 熊本熊卡
- "珍奶"="手搖飲"=飲料店=餐飲 → GOGO黑狗卡
- "便當"="自助餐"=外食 → GOGO黑狗卡

回覆格式（簡潔，不超過250字）：
🏆 最佳選擇：[卡片名稱]
💰 回饋：[回饋率]

📋 怎麼刷：
[說明]

🥈 備選：[備選卡片]（如果有的話）

⚠️ 注意：[注意事項]（如果有的話）

如果情境完全不明確，請追問使用者。絕對不能說「沒有特別優惠」，一定要給出最接近的建議。"""


def get_advice(text: str) -> str:
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n請確認你理解以上規則。"}]},
                {"role": "model", "parts": [{"text": "明白！我會根據語意判斷消費情境，只推薦指定的11張卡，並且一定給出最接近的建議。請問您要在哪裡消費？"}]},
                {"role": "user", "parts": [{"text": text}]},
            ]
        )
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return get_advice_fallback(text)


def get_advice_fallback(text: str) -> str:
    text_lower = text.lower()

    # 先做精確關鍵字匹配
    for rule in RULES:
        for keyword in rule["keywords"]:
            if keyword and keyword in text_lower:
                msg = f"🏆 最佳選擇：{rule['card']}\n"
                msg += f"💰 回饋：{rule['rate']}\n\n"
                msg += f"📋 怎麼刷：\n{rule['how']}\n"
                if rule.get("backup"):
                    msg += f"\n🥈 備選：{rule['backup']}\n"
                if rule.get("caution"):
                    msg += f"\n⚠️ 注意：{rule['caution']}"
                return msg

    # 沒有匹配到 → 預設給永豐大戶卡
    default = RULES[-1]
    msg = f"🏆 最佳選擇：{default['card']}\n"
    msg += f"💰 回饋：{default['rate']}\n\n"
    msg += f"📋 怎麼刷：\n{default['how']}\n"
    msg += f"\n⚠️ 注意：{default['caution']}\n\n"
    msg += "💡 如果你有更具體的消費情境（例如：全家、蝦皮、日本、加油），告訴我可以推薦更高回饋的卡！"
    return msg


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

    if user_text.lower() in ["你好", "hi", "hello", "開始", "help", "說明", "?", "？", "選單", "menu"]:
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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
