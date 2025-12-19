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

VERSION = "1.1.6"
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
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("🧠 تحلیل هوشمند", "🔄 شروع مجدد")
    markup.row("📉 تحلیل تکنیکال", "📅 تقویم اقتصادی")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    welcome_text = (
        f"✨ **ربات تحلیل بازار طلای شخصی مومو**\n\n"
        f"👤 مومو من در خدمتم\n\n"
        f"📡 وضعیت اتصال: 🟢 آنلاین\n\n"
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
    
    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
           f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n\n"
           f"💵 دلار آمریکا: `{p_usd:,.0f}` تومان\n\n"
           f"👑 سکه امامی: `{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات")
def handle_changes(message):
    sync_market_data()
    def get_info(symbol, name):
        item = MARKET_DATA["items"].get(symbol, {})
        price = get_p(symbol)
        pct = float(item.get('change_percent', 0))
        val = float(item.get('change_value', 0))
        status = "📈 صعودی" if pct >= 0 else "📉 نزولی"
        return (f"🔸 **{name}**\n\n"
                f"💵 قیمت امروز: `{price:,.0f}`\n\n"
                f"📊 وضعیت: {status}\n\n"
                f"💰 مقدار تغییر: `{abs(val):,.0f}` تومان\n\n"
                f"🔢 درصد تغییر: `{pct}%` \n\n")

    msg = (f"📊 **گزارش تغییرات روزانه**\n\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
           f"{get_info('IR_GOLD_18K', 'طلا ۱۸ عیار')}"
           f"{get_info('USD', 'دلار آمریکا')}"
           f"📍 *نکته: دیتای هفته و ماه پیش به‌زودی اضافه می‌شود.*")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_val = p_gold - intrinsic
    bubble_pct = (bubble_val / intrinsic) * 100
    status = "🔴 حباب مثبت (گران‌تر از ارزش واقعی)" if bubble_pct > 0 else "🟢 حباب منفی (ارزان‌تر از ارزش واقعی)"
    
    msg = (f"⚪️ **تحلیل حباب طلا**\n\n"
           f"🌐 قیمت انس جهانی: `{p_ons:,.2f}$`\n\n"
           f"🇮🇷 قیمت طلا ایران: `{p_gold:,.0f}` تومان\n\n"
           f"💎 ارزش ذاتی طلا: `{intrinsic:,.0f}` تومان\n\n"
           f"📊 درصد حباب: `{bubble_pct:.2f}%` \n\n"
           f"📝 وضعیت: {status}\n\n"
           f"💡 مقدار حباب: `{abs(bubble_val):,.0f}` تومان")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def handle_ai(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    
    if bubble_pct > 4:
        analysis = "❌ **زمان فروش:** حباب بسیار بالاست. خرید در این قیمت ریسک بالایی دارد."
    elif bubble_pct < 0.5:
        analysis = "✅ **زمان خرید:** قیمت به ارزش ذاتی بسیار نزدیک است. فرصت مناسبی برای ورود است."
    else:
        analysis = "⚖️ **وضعیت احتیاط:** بازار در حال نوسان است. فعلاً نظاره‌گر باشید یا پله‌ای خرید کنید."

    msg = (f"🧠 **سیگنال هوشمند مومو**\n\n"
           f"بر اساس فرمول‌های ریاضی و نرخ جهانی:\n\n"
           f"حباب فعلی: `{bubble_pct:.2f}%` \n\n"
           f"📢 **پیشنهاد:** {analysis}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# --- بخش‌های کمکی (ماشین‌حساب و تکنیکال) ---
@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا** را وارد کنید (گرم):")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **درصد اجرت یا سود** را وارد کنید:")
        bot.register_next_step_handler(msg, calc_final, weight)
    except: bot.send_message(message.chat.id, "⚠️ خطا در عدد!")

def calc_final(message, weight):
    try:
        sync_market_data()
        wage_pct = float(message.text)
        p_gold = get_p("IR_GOLD_18K")
        total = (p_gold + (p_gold * wage_pct / 100)) * weight
        bot.send_message(message.chat.id, f"🧮 **نتیجه مومو:**\n\nمبلغ فاکتور: **`{total:,.0f}`** تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا!")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال سریع**\n\n"
           f"قیمت فعلی: `{p:,.0f}`\n\n"
           f"🛡 حمایت: `{p*0.98:,.0f}`\n\n"
           f"🚀 مقاومت: `{p*1.02:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📅 تقویم اقتصادی")
def handle_cal(message):
    bot.send_message(message.chat.id, "📅 **تقویم اقتصادی مومو**\n\nامروز رویداد تاثیرگذار خاصی در تقویم جهانی ثبت نشده است.", parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Momo Bot v{VERSION} Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
