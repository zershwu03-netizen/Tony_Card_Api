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
# 刷卡規則（僅限以下11張卡）
# ──────────────────────────────────────────

RULES = [
    {
        "keywords": [
            "全家", "familymart", "family mart", "pi錢包", "pi拍錢包",
            "全家咖啡", "全家便利商店", "全家超商"
        ],
        "card": "玉山 Pi 拍錢包聯名卡",
        "rate": "5%",
        "how": "打開 Pi 拍錢包 App，綁定玉山 Pi 卡後，在全家直接用 Pi App 掃碼結帳。月上限 100 P幣（約 2,000 元額度）。",
        "caution": "必須用 Pi 拍錢包 App 掃碼才有 5%，直接刷實體卡只有 1%。"
    },
    {
        "keywords": [
            "foodpanda", "熊貓", "外送", "熊貓外送", "food panda"
        ],
        "card": "中國信託 foodpanda 聯名卡",
        "rate": "最高 5%",
        "how": "在 foodpanda App 結帳時選擇中信 foodpanda 聯名卡付款，1% 基本 + 加碼 4%，月上限 200 胖達幣。",
        "caution": "5% 只限 foodpanda 平台，Uber Eats 不適用。"
    },
    {
        "keywords": [
            "蝦皮", "shopee", "蝦皮購物", "shopee mall"
        ],
        "card": "國泰世華蝦皮聯名卡",
        "rate": "0.5%（平時）/ 6%（超品牌日需登錄）",
        "how": "直接在蝦皮 App 結帳時選擇蝦皮聯名卡付款。超品牌日記得提前去蝦皮 App 登錄活動。",
        "caution": "平時 0.5% 回饋偏低，超品牌日才划算，記得提前登錄。"
    },
    {
        "keywords": [
            "momo", "momo購物", "富邦momo", "momo.com", "momo網購"
        ],
        "card": "富邦銀行 momo 聯名卡",
        "rate": "3%（一般）/ 最高 7%（指定品牌）",
        "how": "在 momo 購物網結帳時選擇富邦 momo 卡付款。指定品牌免登錄自動加碼，結帳前可查看是否有 +4% 標示。",
        "caution": "momo 站內 3% 月上限 1,000 mo幣（約 33,333 元），超過後回饋降低。"
    },
    {
        "keywords": [
            "中油", "加油", "cpc", "台灣中油", "加油站", "油錢", "加95", "加92", "柴油"
        ],
        "card": "中國信託中油聯名卡",
        "rate": "最高 6.8%",
        "how": "下載中油 App，綁定中信中油聯名卡，週一在 App 內先儲值 3,000 元，再去中油直營站用中油 Pay 加油。",
        "backup": "永豐大戶卡 3.5%（直接刷卡，最無腦）",
        "caution": "最高 6.8% 需要：週一儲值 + 使用中油 Pay + 中油直營站，條件較多。懶得設定就刷永豐大戶卡。"
    },
    {
        "keywords": [
            "吉鶴", "聯邦吉鶴", "聯邦", "uniqlo", "大創", "daiso", "日系",
            "優衣庫", "無印良品", "muji", "GU", "nitori", "宜得利"
        ],
        "card": "聯邦銀行吉鶴卡",
        "rate": "5.5%（台灣日系門市）",
        "how": "在台灣 UNIQLO / 大創 / MUJI 等日系品牌門市，直接刷聯邦吉鶴卡或用 Apple Pay / Google Pay 綁吉鶴卡付款。月上限 500 元。",
        "caution": "吉鶴卡是 JCB，部分小店可能不支援。台灣一般消費回饋低，建議只在日系通路使用。"
    },
    {
        "keywords": [
            "海外", "國外", "出國", "歐洲", "美國", "韓國", "泰國",
            "一般", "其他", "不知道", "隨便", "英國", "澳洲", "新加坡",
            "實體消費", "刷卡", "一般消費"
        ],
        "card": "永豐大戶卡",
        "rate": "3.5%（國內）/ 4.5%（海外）",
        "how": "直接刷永豐大戶卡，國內全通路無腦 3.5%，海外消費自動 4.5%，不需切換任何方案。",
        "caution": "需維持帳戶存款 10 萬以上才有大戶等級。日本消費建議改用熊本熊卡回饋更高。"
    },
    {
        "keywords": [
            "uber eats", "ubereats", "外帶", "餐廳", "吃飯", "台新gogo",
            "gogo卡", "黑狗卡", "gogo黑狗", "台新黑狗", "吃東西", "用餐",
            "dinner", "lunch", "breakfast", "早餐", "午餐", "晚餐",
            "便當", "小吃", "夜市", "飲料", "手搖飲", "珍奶"
        ],
        "card": "台新 GOGO 黑狗卡",
        "rate": "最高 5%（餐飲/外送）",
        "how": "在 Uber Eats、餐廳等餐飲消費直接刷台新 GOGO 黑狗卡，享最高 5% 回饋。部分通路需用 Apple Pay / Google Pay 綁卡付款。",
        "caution": "回饋上限及指定通路請以台新官網最新活動為準。"
    },
    {
        "keywords": [
            "one for all", "oneforall", "玉山one", "unicard", "玉山unicard",
            "超商", "7-11", "711", "全聯", "萊爾富", "ok超商", "hilife",
            "便利商店", "seven eleven", "統一超商",
            "line pay", "linepay", "街口", "百貨", "新光三越", "遠東百貨",
            "家樂福", "簡單選", "任意選", "up選"
        ],
        "card": "玉山 ONE for ALL 卡（玉山 Unicard）",
        "rate": "簡單選 3% / 任意選 3.5% / UP選 4.5%（百大特店，需在玉山Wallet切換方案）",
        "how": "這張卡有三種方案，在玉山Wallet App月底前切換，以當月最後一天的方案計算整月回饋：\n\n🔹 簡單選（3%）：百大100家特店通通有回饋，月上限1,000點（約刷50,000元封頂）。適合懶得設定的人。\n\n🔸 任意選（3.5%）：從百大特店中自選8家，月上限1,000點（約刷40,000元封頂）。推薦選 LINE Pay + 街口支付 + 常用電商/百貨共8家。\n\n⭐ UP選（4.5%）：需每月支付149點e point訂閱（或上月刷滿3萬/存款30萬免費升級），月上限5,000點。\n\n百大特店包含：LINE Pay、街口支付、台灣中油、高鐵、momo、蝦皮、Uber Eats、foodpanda、新光三越、遠東百貨、家樂福、屈臣氏、中華航空等100+家。",
        "caution": "切換方式：玉山Wallet App → 我的 → 玉山Unicard-我的方案，月底前切換即可。整月消費以當月最後一天方案計算。非百大特店只有1%基本回饋。月底前記得取消UP選自動續訂以免下月被扣149點。"
    },
    {
        "keywords": [
            "ubear", "netflix", "chatgpt", "steam", "nintendo", "playstation",
            "ps5", "訂閱", "disney", "disney+", "youtube premium", "spotify",
            "apple music", "hbo", "friDay影音", "myVideo", "線上遊戲",
            "game", "遊戲課金", "app store", "google play"
        ],
        "card": "玉山 UBear 卡",
        "rate": "10%（指定訂閱平台）",
        "how": "直接刷玉山 UBear 卡，於 Netflix、ChatGPT、Steam、Disney+ 等指定平台消費，享 10% 回饋。月上限 100 元回饋。",
        "caution": "僅限指定訂閱平台，不可透過 Google/PayPal 代扣。超商/全聯不適用。"
    },
    {
        "keywords": [
            "日本", "japan", "藥妝", "松本清", "唐吉訶德", "don quijote",
            "bic camera", "電器", "免稅", "熊本熊", "東京", "大阪", "京都",
            "北海道", "沖繩", "日本旅遊", "赴日", "cosme", "loft",
            "animate", "秋葉原", "心齋橋", "新宿"
        ],
        "card": "玉山熊本熊向左走卡",
        "rate": "最高 8.5%（日本指定通路）",
        "how": "去日本前先登錄活動（玉山官網），在指定商店（藥妝/電器/百貨/樂園）直接刷實體卡或綁 Apple Pay 付款。",
        "backup": "聯邦吉鶴卡 最高 8%（唐吉訶德/UNIQLO等，需 Apple Pay QUICPay）",
        "caution": "熊本熊卡 8.5% 月上限 500 元，超過後改刷聯邦吉鶴卡補滿額度。"
    },
]

# 語意通路分類（幫助 Gemini 推理）
CATEGORY_GUIDE = """
【通路語意分類指南】請用以下分類判斷使用者的消費情境：

1. 網路購物 / 電商平台
   → 包含：momo、蝦皮、PChome、coupang、酷澎、amazon、亞馬遜、博客來、friDay、
            樂天、yahoo購物、東森購物、生活市集、91APP、網拍、線上購物、電商、
            官網下單、app內購買
   → 推薦：富邦momo聯名卡（momo平台）/ 國泰蝦皮聯名卡（蝦皮）

2. 外送平台
   → 包含：foodpanda、熊貓、外送、Uber Eats、叫外賣
   → 推薦：中信foodpanda聯名卡（foodpanda）/ 台新GOGO黑狗卡（Uber Eats）

3. 餐飲 / 實體用餐
   → 包含：餐廳、吃飯、早午晚餐、便當、小吃、飲料、手搖飲、夜市、火鍋、燒肉
   → 推薦：台新GOGO黑狗卡

4. 訂閱服務 / 數位內容
   → 包含：Netflix、Disney+、Spotify、YouTube Premium、ChatGPT、Steam、
            遊戲課金、App Store、Google Play、線上遊戲
   → 推薦：玉山UBear卡

5. 日本消費
   → 包含：日本旅遊、藥妝、唐吉訶德、免稅店、東京/大阪等城市、日本電器
   → 推薦：玉山熊本熊向左走卡（月上限500元後改聯邦吉鶴卡）

6. 加油
   → 包含：加油、中油、油費、加95/92
   → 推薦：中信中油聯名卡

7. 超商
   → 包含：7-11、全聯、萊爾富、全家（改用Pi錢包）
   → 推薦：玉山ONE for ALL卡（7-11/全聯）/ 玉山Pi拍錢包卡（全家）

8. 日系品牌實體門市
   → 包含：UNIQLO、大創、MUJI、GU、宜得利
   → 推薦：聯邦吉鶴卡

9. 海外 / 一般消費（以上都不符合時）
   → 推薦：永豐大戶卡
"""

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

WELCOME_MSG = f"""👋 你好！我是你的刷卡顧問。

我只推薦以下11張卡的最佳使用方式：
{CARDS_LIST}

告訴我你要在哪裡消費，我幫你決定刷哪張最划算！

範例：
・去全家買咖啡
・在蝦皮買東西
・訂 Netflix
・去日本藥妝店
・在 momo 網購
・去中油加油
・在 coupang 買東西

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


SYSTEM_PROMPT = f"""你是一位專業的信用卡刷卡顧問，擅長語意理解，能判斷使用者描述的消費情境屬於哪種通路類別。

【重要限制】你只能從以下11張卡中給建議，絕對不能推薦其他任何卡片：
{CARDS_LIST}

{CATEGORY_GUIDE}

詳細規則表：
{build_rules_text()}

回覆規則：
1. 先判斷使用者的消費屬於哪個通路類別，再對應推薦最適合的卡片
2. 即使使用者用的詞不在關鍵字內，也要用語意判斷（例如「酷澎」=「coupang」=網購平台=推薦momo聯名卡）
3. 只從上面11張卡中推薦，絕對不推薦其他卡片
4. 用親切口語的繁體中文回覆，不要太正式
5. 回覆格式：
   🏆 最佳選擇：[卡片名稱]
   💰 回饋：[回饋率]

   📋 怎麼刷：
   [說明]

   🥈 備選：[備選卡片]（如果有的話）

   ⚠️ 注意：[注意事項]（如果有的話）
6. 如果情境不明確，請追問使用者
7. 回覆要簡潔，不要超過 300 字"""


def get_advice(text: str) -> str:
    try:
        # 多輪對話方式，讓 Gemini 更好地遵循角色設定
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n請確認你理解以上規則，並只推薦指定的11張卡。"}]},
                {"role": "model", "parts": [{"text": "我明白了！我會根據語意判斷消費情境，並且只推薦您指定的11張卡片。請問您要在哪裡消費呢？"}]},
                {"role": "user", "parts": [{"text": text}]},
            ]
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
        "🤔 這11張卡在您描述的消費情境沒有特別優惠。\n\n"
        "可以換個消費情境試試看，例如：\n"
        "全家、蝦皮、momo、日本、加油、Netflix 等 😊"
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
