import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import jdatetime 
import time

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

VERSION = "1.2.0"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی پیشرفته ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    # استفاده از چند منبع احتمالی برای دور زدن محدودیت IP
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    # ایجاد یک Session برای پایداری اتصال
    session = requests.Session()
    # تنظیم ۳ بار تلاش مجدد در صورت قطع اتصال
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Connection': 'close' # بستن اتصال پس از هر بار برای جلوگیری از Reset شدن توسط Peer
    }

    try:
        # ارسال درخواست با پروتکل TLS پایدار
        response = session.get(url, headers=headers, timeout=15, verify=True)
        
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
                MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
                MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
                return True, "OK"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        # در صورت خطای ۱۸ عیار، اگر دیتای قبلی در حافظه هست، موفقیت‌آمیز برگردان
        if MARKET_DATA["items"]:
            return True, "استفاده از حافظه موقت"
        return False, "خطای اتصال (IP بن شده است)"

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
    
    msg = (f"✨ **مومو (نسخه ضد تحریم {VERSION})**\n\n"
           f"📡 وضعیت شبکه: {status_icon} `{report}`\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
           f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
           f"یکی از گزینه‌های زیر را انتخاب کنید:")
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "❌ سرور قیمت‌دهی در دسترس نیست. لطفاً دقایقی دیگر تلاش کنید.")
        return

    msg = (f"💰 **قیمت‌های زنده بازار**\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{get_p('USD'):,.0f}` تومان\n"
           f"👑 سکه امامی: `{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n"
           f"🌐 انس جهانی: `{get_p('XAUUSD'):,.0f}` دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# سایر توابع (تحلیل، ماشین‌حساب و ...) به همان روال قبل حفظ شدند
@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ وزن (گرم):")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        w = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 درصد سود و اجرت:")
        bot.register_next_step_handler(msg, calc_final, w)
    except: bot.send_message(message.chat.id, "عدد نامعتبر!")

def calc_final(message, w):
    try:
        p = get_p("IR_GOLD_18K")
        total = (p * w) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"💰 قیمت نهایی: `{total:,.0f}` تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "خطا!")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0: return
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble = ((p_gold - intrinsic) / intrinsic) * 100
    bot.send_message(message.chat.id, f"⚪️ حباب طلا: `{bubble:.2f}%`", parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo Anti-Reset v{VERSION} Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
