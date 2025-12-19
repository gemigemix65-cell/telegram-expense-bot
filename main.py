import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import jdatetime 
import time

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

VERSION = "1.1.8"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
# کلید هوش مصنوعی شما از لیارا
LIARA_AI_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiI2OTQ1Y2M1NzM2MzY3MzU2MWRhMWM1YzgiLCJ0eXBlIjoiYWlfa2V5IiwiaWF0IjoxNzY2MTgxOTc1fQ.aMxk_ih1L050h5HzYFUHVxnDudltKMepHw_jOiiPKvc"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        res_json = response.json()
        temp_items = {}
        for category in ['gold', 'currency']:
            data_list = res_json.get(category, [])
            if isinstance(data_list, list):
                for item in data_list:
                    symbol = item.get('symbol')
                    if symbol: temp_items[symbol] = item
        MARKET_DATA["items"] = temp_items
        now = jdatetime.datetime.now()
        MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
        MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
        return True, "OK"
    except:
        return False, "Error"

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        return float(str(price).replace(',', ''))
    except:
        return 0

# --- تابع جدید: ارتباط با هوش مصنوعی لیارا ---
def ask_liara_ai(prompt):
    url = "https://api.liara.ai/v1/chat/completions" # آدرس استاندارد لیارا
    headers = {
        "Authorization": f"Bearer {LIARA_AI_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-70b-8192", # مدل قدرتمند و رایگان در اکثر پنل‌ها
        "messages": [
            {"role": "system", "content": "تو 'مومو' هستی، یک تحلیلگر خبره بازار طلای ایران. پاسخ‌هایت کوتاه، صمیمی، فارسی و بر اساس منطق اقتصادی باشد. به کاربر بگو بخرد یا بفروشد."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return None # اگر خطا داد، نال برگردان تا از روش دستی استفاده کنیم
    except:
        return None

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 نمودار تغییرات")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("🧠 تحلیل هوشمند (AI)", "📉 تحلیل تکنیکال")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    welcome_text = (
        f"✨ **ربات هوشمند بازار طلا (مومو)**\n\n"
        f"👤 سلام! من مومو هستم. با هوش مصنوعی جدیدم در خدمتم.\n\n"
        f"--------------------------\n\n"
        f"📡 وضعیت شبکه: 🟢 آنلاین\n\n"
        f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
        f"⏰ ساعت: `{MARKET_DATA['update_time']}`"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    p_coin = get_p("IR_COIN_EMAMI")
    
    msg = (f"💰 **تابلو قیمت لحظه‌ای**\n\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
           f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
           f"〰〰〰〰〰〰〰〰\n\n"
           f"🥇 طلا ۱۸ عیار:\n"
           f"`{p_gold:,.0f}` تومان\n\n"
           f"💵 دلار آزاد:\n"
           f"`{p_usd:,.0f}` تومان\n\n"
           f"👑 سکه امامی:\n"
           f"`{p_coin:,.0f}` تومان\n\n"
           f"🌐 انس جهانی طلا:\n"
           f"`{p_ons:,.2f}` دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا** را وارد کنید (گرم):\n(مثال: 4.5)")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "➕ **درصد اجرت/سود** را وارد کنید:\n(عدد خالی)")
        bot.register_next_step_handler(msg, calc_final, weight)
    except: bot.send_message(message.chat.id, "⚠️ عدد انگلیسی وارد کنید.")

def calc_final(message, weight):
    try:
        sync_market_data()
        wage_pct = float(message.text)
        p_gold = get_p("IR_GOLD_18K")
        total = (p_gold * weight) + ((p_gold * weight) * (wage_pct / 100))
        res = (f"🧮 **فاکتور مومو**\n\n"
               f"1️⃣ فرمول:\n"
               f"(`{weight} g` × `{p_gold:,.0f}`) + `{wage_pct}%`\n\n"
               f"2️⃣ مبلغ نهایی:\n"
               f"💰 **`{total:,.0f}` تومان**")
        bot.send_message(message.chat.id, res, parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا.")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    status = "🔴 حباب مثبت (گران)" if bubble_pct > 0 else "🟢 حباب منفی (ارزان)"
    
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"🧮 فرمول:\n"
           f"(انس × دلار × ۰.۷۵) ÷ ۳۱.۱۰\n\n"
           f"💎 ارزش ذاتی: `{intrinsic:,.0f}` تومان\n\n"
           f"🏷 قیمت فعلی: `{p_gold:,.0f}` تومان\n\n"
           f"📊 مقدار حباب: `{abs(p_gold - intrinsic):,.0f}` تومان\n\n"
           f"وضعیت: **{status}**\n"
           f"درصد: `{bubble_pct:.2f}%`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_changes(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = float(item.get('change_percent', 0))
    val = float(item.get('change_value', 0))
    curr = get_p("IR_GOLD_18K")
    yesterday = curr - val
    bar = "🟩" * min(int(pct*4), 10) if pct >=0 else "🟥" * min(abs(int(pct*4)), 10)
    
    msg = (f"📊 **گزارش نوسانات طلا**\n\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
           f"💵 امروز: `{curr:,.0f}` تومان\n\n"
           f"🗓 دیروز: `{yesterday:,.0f}` تومان\n\n"
           f"📉 تغییرات:\n"
           f"{'🔺' if pct>=0 else '🔻'} `{abs(val):,.0f}` تومان ({pct}%)\n\n"
           f"📊 نمودار:\n{bar or '⬜️ بدون تغییر'}\n\n"
           f"⏳ هفته/ماه پیش: (نیازمند سابقه)")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# --- بخش هوش مصنوعی پیشرفته ---
@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند (AI)")
def handle_ai(message):
    bot.send_chat_action(message.chat.id, 'typing') # نمایش "در حال تایپ..."
    sync_market_data()
    
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    
    # ۱. ساخت متن درخواست برای هوش مصنوعی
    prompt_text = (
        f"قیمت طلای ۱۸ عیار ایران: {p_gold} تومان.\n"
        f"قیمت دلار بازار آزاد: {p_usd} تومان.\n"
        f"انس جهانی طلا: {p_ons} دلار.\n"
        f"حباب قیمت طلا: {bubble_pct:.2f} درصد.\n"
        f"با توجه به اینکه اگر حباب بالای ۳ درصد باشد خطرناک است و اگر منفی باشد فرصت خرید است، "
        f"یک تحلیل کوتاه ۳ خطی بنویس و صریح بگو الان وقت خرید است یا فروش؟ "
        f"لحن تو دوستانه و با اسم 'مومو' باشد."
    )
    
    # ۲. ارسال به هوش مصنوعی لیارا
    ai_response = ask_liara_ai(prompt_text)
    
    # ۳. نمایش نتیجه
    if ai_response:
        final_msg = f"🧠 **تحلیل اختصاصی هوش مصنوعی مومو**\n\n{ai_response}"
    else:
        # اگر هوش مصنوعی قطع بود، از روش دستی استفاده کن
        fallback_advice = "❌ **حباب بالاست!**" if bubble_pct > 3 else "✅ **فرصت خرید!**"
        final_msg = (f"🧠 **تحلیل هوشمند (حالت آفلاین)**\n\n"
                     f"ارتباط با مغز هوشمند برقرار نشد، اما طبق فرمول:\n"
                     f"حباب فعلی: `{bubble_pct:.2f}%`\n"
                     f"پیشنهاد: {fallback_advice}")
                     
    bot.send_message(message.chat.id, final_msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال ساده**\n\n"
           f"📍 قیمت فعلی: `{p:,.0f}` تومان\n\n"
           f"🛡 **کف حمایتی:** `{p*0.985:,.0f}`\n"
           f"(قیمت معمولا از اینجا پایین‌تر نمی‌رود)\n\n"
           f"🚀 **سقف مقاومتی:** `{p*1.015:,.0f}`\n"
           f"(قیمت برای رد شدن از این عدد کار سختی دارد)")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Momo Bot AI v{VERSION} Running.", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
