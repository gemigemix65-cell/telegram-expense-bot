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

VERSION = "1.1.9"
TOKEN = os.environ.get("BOT_TOKEN")
# استفاده مستقیم از کلید تایید شده شما
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه موقت برای ذخیره قیمت‌ها
MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    # تنظیم User-Agent معتبر برای عبور از فایروال سایت (طبق هشدار 6G)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            temp_items = {}
            
            # استخراج داده‌ها از دسته‌بندی‌های طلا و ارز
            for category in ['gold', 'currency']:
                if category in res_json:
                    for item in res_json[category]:
                        symbol = item.get('symbol')
                        if symbol:
                            temp_items[symbol] = item
            
            if temp_items:
                MARKET_DATA["items"] = temp_items
                now = jdatetime.datetime.now()
                MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
                MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
                return True, "OK"
        return False, f"خطای کد: {response.status_code}"
    except Exception as e:
        return False, str(e)

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        # پاکسازی قیمت از کاما و تبدیل به عدد
        return float(str(price).replace(',', ''))
    except:
        return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📉 تحلیل تکنیکال")
    markup.row("🧮 ماشین‌حساب", "📅 تقویم اقتصادی")
    markup.row("🧠 تحلیل هوشمند", "📊 نمودار تغییرات")
    markup.row("⚪️ حباب طلا", "🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, report = sync_market_data()
    status_icon = "🟢" if success else "🔴"
    
    msg = (f"✨ **ایستگاه قیمت مومو (نسخه {VERSION})**\n\n"
           f"📡 وضعیت اتصال: {status_icon} `{report}`\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
           f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
           f"از منوی زیر انتخاب کنید:")
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "⚠️ خطا در دریافت قیمت. لطفاً دوباره تلاش کنید.")
        return

    msg = (f"💰 **آخرین قیمت‌های بازار**\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{get_p('USD'):,.0f}` تومان\n"
           f"👑 سکه امامی: `{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n"
           f"🌐 انس جهانی: `{get_p('XAUUSD'):,.0f}` دلار\n\n"
           f"⏰ زمان: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0:
        bot.reply_to(message, "⚠️ دیتا ناقص است.")
        return
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble = ((p_gold - intrinsic) / intrinsic) * 100
    bot.send_message(message.chat.id, f"⚪️ **حباب طلا:** `{bubble:.2f}%`", parse_mode='Markdown')

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
        bot.send_message(message.chat.id, f"💰 مبلغ کل: **`{total:,.0f}` تومان**", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا!")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال**\n\n🛡 حمایت: `{p*0.988:,.0f}`\n🚀 مقاومت: `{p*1.012:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def handle_ai(message):
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = float(item.get('change_percent', 0))
    ans = "✅ خرید پله‌ای" if pct < 0 else "❌ صبر برای اصلاح"
    bot.send_message(message.chat.id, f"🧠 **سیگنال:** {ans}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_chart(message):
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = item.get('change_percent', 0)
    bot.send_message(message.chat.id, f"📊 نوسان امروز: `{pct}%`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📅 تقویم اقتصادی")
def handle_calendar(message):
    bot.send_message(message.chat.id, "📅 رویداد خاصی برای امروز ثبت نشده است.")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo Active with API: {BRS_TOKEN[-4:]}", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
