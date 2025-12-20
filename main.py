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

VERSION = "1.1.3"
TOKEN = os.environ.get("BOT_TOKEN")
# استفاده از منبع مستقیم و بدون واسطه برای پایداری بیشتر
PRIMARY_API = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key=BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6"
# منبع پشتیبان (در صورت قطع بودن منبع اول)
BACKUP_API = "https://raw.githubusercontent.com/naviddev/persian-gold-api/main/latest.json"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی چند مرحله‌ای ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    
    # هدرهای پیشرفته برای جلوگیری از Connection Reset
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    # تلاش برای اتصال به منبع اصلی
    try:
        response = requests.get(PRIMARY_API, headers=headers, timeout=12)
        if response.status_code == 200:
            res_json = response.json()
            temp_items = {}
            for cat in ['gold', 'currency']:
                if cat in res_json:
                    for item in res_json[cat]:
                        sym = item.get('symbol')
                        if sym: temp_items[sym] = item
            
            if temp_items:
                MARKET_DATA["items"] = temp_items
                now = jdatetime.datetime.now()
                MARKET_DATA["update_time"] = now.strftime("%H:%M")
                MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
                return True, "متصل به منبع اصلی ✅"
    except:
        pass # اگر منبع اول خطا داد، برو سراغ منبع دوم

    # تلاش برای اتصال به منبع پشتیبان (Github Mirror)
    try:
        response = requests.get(BACKUP_API, headers=headers, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            # فرمت دیتای گیت‌هاب کمی متفاوت است، اینجا تبدیلش می‌کنیم
            temp_items = {}
            for cat in ['gold', 'currency']:
                if cat in res_json:
                    for item in res_json[cat]:
                        sym = item.get('symbol')
                        if sym: temp_items[sym] = item
            
            MARKET_DATA["items"] = temp_items
            MARKET_DATA["update_time"] = "پشتیبان"
            MARKET_DATA["update_date"] = jdatetime.datetime.now().strftime("%Y/%m/%d")
            return True, "متصل به منبع پشتیبان 🔄"
    except Exception as e:
        return False, f"خطای کامل شبکه: {str(e)}"

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
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات بازار")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("📉 تحلیل تکنیکال", "🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, report = sync_market_data()
    icon = "🟢" if success else "🔴"
    
    msg = (f"✨ **مومو (نسخه پایدار v1.1.3)**\n\n"
           f"وضعیت اتصال: {icon} `{report}`\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`\n\n"
           f"آماده پاسخگویی به شما هستم:")
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "❌ متأسفانه در حال حاضر امکان دریافت قیمت وجود ندارد.")
        return

    msg = (f"💰 **قیمت‌های لحظه‌ای**\n\n"
           f"🥇 **طلا ۱۸ عیار:**\n`{p_gold:,.0f}` تومان\n\n"
           f"💵 **دلار آمریکا:**\n`{get_p('USD'):,.0f}` تومان\n\n"
           f"👑 **سکه امامی:**\n`{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 **انس جهانی:**\n`{get_p('XAUUSD'):,.0f}` دلار\n\n"
           f"⏰ آخرین آپدیت: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0:
        bot.reply_to(message, "⚠️ اطلاعات ناقص است.")
        return
    
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"💎 ارزش واقعی: `{intrinsic:,.0f}`\n"
           f"📊 قیمت بازار: `{p_gold:,.0f}`\n"
           f"📈 درصد حباب: `{bubble_pct:.2f}%` ")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات بازار")
def handle_changes(message):
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    if not item:
        bot.reply_to(message, "⚠️ دیتایی یافت نشد.")
        return
    msg = (f"📊 **تغییرات طلا**\n\n"
           f"نوسان: `{item.get('change_value', 0):,.0f}` تومان\n"
           f"درصد تغییر: `{item.get('change_percent', 0)}%` ")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا (گرم):**")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        w = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **درصد سود و اجرت:**")
        bot.register_next_step_handler(msg, calc_final, w)
    except: bot.send_message(message.chat.id, "⚠️ عدد وارد کنید.")

def calc_final(message, w):
    try:
        p = get_p("IR_GOLD_18K")
        total = (p * w) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"💰 **مبلغ فاکتور:**\n`{total:,.0f}` تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال**\n\n🛡 حمایت: `{p*0.985:,.0f}`\n🚀 مقاومت: `{p*1.015:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo v{VERSION} Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
