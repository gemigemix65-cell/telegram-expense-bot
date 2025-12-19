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

VERSION = "1.1.7"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
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

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 نمودار تغییرات")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("🧠 تحلیل هوشمند", "📉 تحلیل تکنیکال")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    welcome_text = (
        f"✨ **ربات تحلیل بازار طلای شخصی مومو**\n\n"
        f"👤 مومو هستم، دستیار شما.\n\n"
        f"--------------------------\n\n"
        f"📡 وضعیت: 🟢 آنلاین\n\n"
        f"📅 تاریخ امروز: `{MARKET_DATA['update_date']}`\n\n"
        f"⏰ ساعت به‌روزرسانی: `{MARKET_DATA['update_time']}`"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

# --- ۱. قیمت لحظه‌ای (اصلاح فواصل و واحدها) ---
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

# --- ۲. ماشین حساب (نمایش روند محاسبه) ---
@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا** را به گرم وارد کنید:\n(مثال: 4.5)")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "➕ **درصد اجرت/سود** را وارد کنید:\n(عدد خالی، مثلا: 5)")
        bot.register_next_step_handler(msg, calc_final, weight)
    except:
        bot.send_message(message.chat.id, "⚠️ لطفا عدد انگلیسی وارد کنید.")

def calc_final(message, weight):
    try:
        sync_market_data()
        wage_pct = float(message.text)
        p_gold = get_p("IR_GOLD_18K")
        
        # محاسبه
        price_raw = p_gold * weight
        extra_amount = price_raw * (wage_pct / 100)
        total_price = price_raw + extra_amount
        
        res = (f"🧮 **فاکتور محاسبه مومو**\n\n"
               f"1️⃣ فرمول:\n"
               f"(`{weight} گرم` × `{p_gold:,.0f}`) + `{wage_pct}%`\n\n"
               f"2️⃣ مبلغ نهایی قابل پرداخت:\n"
               f"💰 **`{total_price:,.0f}` تومان**")
        bot.send_message(message.chat.id, res, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "⚠️ خطا در محاسبه.")

# --- ۳. حباب طلا (فرمول و رنگ‌بندی) ---
@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    
    # فرمول ارزش ذاتی: (انس * دلار * 0.75) / 31.1035
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_val = p_gold - intrinsic
    bubble_pct = (bubble_val / intrinsic) * 100
    
    # تعیین وضعیت
    if bubble_pct > 0:
        status_icon = "🔴"
        status_text = "حباب مثبت (گران)"
    else:
        status_icon = "🟢"
        status_text = "حباب منفی (ارزان)"
        
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"🧮 فرمول محاسبه:\n"
           f"(انس × دلار × ۰.۷۵) ÷ ۳۱.۱۰\n\n"
           f"💎 ارزش ذاتی (واقعی): `{intrinsic:,.0f}` تومان\n\n"
           f"🏷 قیمت بازار (فعلی): `{p_gold:,.0f}` تومان\n\n"
           f"📊 مقدار حباب: `{abs(bubble_val):,.0f}` تومان\n\n"
           f"{status_icon} وضعیت: **{status_text}**\n"
           f"درصد اختلاف: `{bubble_pct:.2f}%`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# --- ۴. نمودار تغییرات (شبیه‌سازی تاریخچه) ---
@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_changes(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    
    current_price = get_p("IR_GOLD_18K")
    pct_change = float(item.get('change_percent', 0))
    value_change = float(item.get('change_value', 0))
    
    # محاسبه قیمت دیروز (مهندسی معکوس)
    yesterday_price = current_price - value_change
    
    # وضعیت
    trend = "🔺 افزایش" if pct_change >= 0 else "🔻 کاهش"
    
    # نمودار متنی
    bar_count = min(abs(int(pct_change * 4)), 10)
    chart_bar = "🟩" * bar_count if pct_change >= 0 else "🟥" * bar_count
    if bar_count == 0: chart_bar = "⬜️ بدون تغییر"

    msg = (f"📊 **گزارش نوسانات طلا (۱۸ عیار)**\n\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
           f"💵 قیمت امروز: `{current_price:,.0f}` تومان\n\n"
           f"🗓 قیمت دیروز: `{yesterday_price:,.0f}` تومان\n\n"
           f"📉 تغییر نسبت به دیروز:\n"
           f"{trend} `{abs(value_change):,.0f}` تومان ({pct_change}%)\n\n"
           f"📊 نمودار تصویری:\n"
           f"{chart_bar}\n\n"
           f"⏳ قیمت هفته پیش: (در حال جمع‌آوری دیتا...)\n"
           f"⏳ قیمت ماه پیش: (در حال جمع‌آوری دیتا...)")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# --- ۵. تحلیل هوشمند (پیشنهاد خرید/فروش) ---
@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def handle_ai(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    
    if bubble_pct > 3:
        advice = "❌ **الان وقت خرید نیست!**\nحباب قیمت مثبت است و احتمال اصلاح (ارزان شدن) وجود دارد. اگر فروشنده هستید، زمان بدی نیست."
    elif bubble_pct < -0.5:
        advice = "✅ **پیشنهاد خرید جذاب**\nقیمت بازار زیر ارزش واقعی است. خرید در این نقطه کم‌ریسک و منطقی است."
    else:
        advice = "⚖️ **بازار متعادل**\nقیمت منطقی است اما هیجان خاصی ندارد. اگر نیاز دارید بخرید، اما عجله نکنید."

    bot.send_message(message.chat.id, f"🧠 **مشاور هوشمند مومو**\n\n{advice}", parse_mode='Markdown')

# --- ۶. تحلیل تکنیکال (ساده‌سازی شده) ---
@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_technical(message):
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    
    # نقاط فرضی بر اساس نوسان ۱.۵ درصدی
    support = p * 0.985
    resistance = p * 1.015
    
    msg = (f"📉 **تحلیل تکنیکال (به زبان ساده)**\n\n"
           f"📍 قیمت فعلی: `{p:,.0f}` تومان\n\n"
           f"🛡 **کف قیمتی (حمایت):**\n"
           f"`{support:,.0f}` تومان\n"
           f"(یعنی اگر قیمت بریزد، احتمالا تا اینجا پایین می‌آید و دوباره بالا می‌رود)\n\n"
           f"🚀 **سقف قیمتی (مقاومت):**\n"
           f"`{resistance:,.0f}` تومان\n"
           f"(یعنی برای رد شدن از این قیمت کار سختی دارد)")
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
    return f"Momo Bot v{VERSION} Ready.", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
