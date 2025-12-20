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

VERSION = "1.1.0"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه موقت برای ذخیره قیمت‌ها
MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور دریافت دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        res_json = response.json()
        
        temp_items = {}
        # استخراج طلا و ارز بر اساس ساختار ارسالی شما
        for category in ['gold', 'currency']:
            if category in res_json:
                for item in res_json[category]:
                    symbol = item.get('symbol')
                    if symbol:
                        temp_items[symbol] = item
        
        if temp_items:
            MARKET_DATA["items"] = temp_items
            now = jdatetime.datetime.now()
            MARKET_DATA["update_time"] = now.strftime("%H:%M")
            MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
            return True
        return False
    except:
        return False

def get_p(symbol):
    """تبدیل قیمت به عدد برای محاسبات"""
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
    sync_market_data()
    welcome = (f"✨ **به ایستگاه قیمت مومو خوش آمدید**\n\n"
               f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
               f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
               f"برای دریافت اطلاعات از دکمه‌های زیر استفاده کنید:")
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "❌ خطا در دریافت قیمت. مجدداً تلاش کنید.")
        return

    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"🥇 **طلا ۱۸ عیار:**\n\n`{p_gold:,.0f}` تومان\n\n"
           f"💵 **دلار آمریکا:**\n\n`{get_p('USD'):,.0f}` تومان\n\n"
           f"👑 **سکه امامی:**\n\n`{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 **انس جهانی طلا:**\n\n`{get_p('XAUUSD'):,.0f}` دلار\n\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0:
        bot.reply_to(message, "⚠️ دیتا برای محاسبه حباب ناقص است.")
        return
    
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    icon = "🔴" if bubble_pct > 0 else "🟢"
    
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"💎 **ارزش واقعی:**\n\n`{intrinsic:,.0f}` تومان\n\n"
           f"📊 **قیمت بازار:**\n\n`{p_gold:,.0f}` تومان\n\n"
           f"{icon} **درصد حباب:**\n\n`{bubble_pct:.2f}%` ")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات بازار")
def handle_changes(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = item.get('change_percent', 0)
    val = item.get('change_value', 0)
    
    msg = (f"📊 **تغییرات امروز طلا**\n\n"
           f"🥇 طلا ۱۸ عیار:\n\n"
           f"میزان نوسان: `{abs(float(val)):,.0f}` تومان\n\n"
           f"درصد تغییر: `{pct}%` \n\n"
           f"وضعیت: {'📈 صعودی' if float(pct) >= 0 else '📉 نزولی'}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا (گرم) را وارد کنید:**")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        w = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **درصد سود و اجرت را وارد کنید:**")
        bot.register_next_step_handler(msg, calc_final, w)
    except:
        bot.send_message(message.chat.id, "⚠️ عدد معتبر وارد کنید.")

def calc_final(message, w):
    try:
        sync_market_data()
        p = get_p("IR_GOLD_18K")
        pct = float(message.text)
        total = (p * w) * (1 + pct/100)
        bot.send_message(message.chat.id, f"💰 **مبلغ فاکتور:**\n\n`{total:,.0f}` تومان", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "⚠️ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال (حمایت و مقاومت)**\n\n"
           f"🛡 کف حمایتی: `{p*0.985:,.0f}`\n\n"
           f"🚀 سقف مقاومتی: `{p*1.015:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return "Momo v1.1.0 Stable Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
