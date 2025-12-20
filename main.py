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

VERSION = "1.1.1"

TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "به‌روزرسانی نشده"}

# ----------------------------------------
#           *** ۲. موتور واکشی نسخه v1.1.1 ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return False, f"HTTP Error: {response.status_code}"

        res_json = response.json()
        temp_items = {}

        for category in ['gold', 'currency', 'cryptocurrency']:
            data_list = res_json.get(category, [])
            if isinstance(data_list, list):
                for item in data_list:
                    symbol = item.get('symbol')
                    if symbol:
                        temp_items[symbol] = item
        
        if not temp_items:
            return False, "دیتای قیمت در لیست‌ها یافت نشد."

        MARKET_DATA["items"] = temp_items
        MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
        return True, "OK"

    except Exception as e:
        return False, f"Internal Error: {str(e)[:40]}"

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
    markup.row("⚪️ حباب طلا", "🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, msg_result = sync_market_data()
    status = "🟢 آنلاین" if success else f"🔴 خطا: {msg_result}"
    
    welcome_text = (
        f"🤖 **ربات تحلیلگر بازار**\n"
        f"📦 ورژن استقرار: `{VERSION}`\n"
        f"--------------------------\n"
        f"وضعیت اتصال: {status}\n\n"
        f"آخرین آپدیت: `{MARKET_DATA['update_time']}`"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    bot.send_chat_action(message.chat.id, 'typing')
    success, error_msg = sync_market_data()
    
    if not success:
        bot.reply_to(message, f"⚠️ **خطا در دریافت قیمت:**\n`{error_msg}`")
        return

    p_gold = get_p("IR_GOLD_18K")
    p_sekeh = get_p("IR_COIN_EMAMI")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    
    msg = (f"💰 **نرخ‌های بازار (تومان)**\n"
           f"📦 Ver: `{VERSION}` | ⏰ `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}`\n"
           f"👑 سکه امامی: `{p_sekeh:,.0f}`\n"
           f"💵 دلار آمریکا: `{p_usd:,.0f}`\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات")
def handle_changes(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = item.get('change_percent', 0)
    val = get_p("IR_GOLD_18K") * (float(pct)/100)
    
    status = "📈 صعودی" if float(pct) >= 0 else "📉 نزولی"
    bot.send_message(message.chat.id, f"📊 **تغییرات طلا ۱۸ عیار:**\n\nوضعیت: {status}\nمقدار: `{abs(val):,.0f}` تومان\nدرصد: `{pct}%`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    
    if p_gold > 0 and p_usd > 0:
        intrinsic = (p_ons * p_usd * 0.75) / 31.1035
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n💰 ارزش ذاتی: `{intrinsic:,.0f}` تومان\n🎈 حباب: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ دیتا برای محاسبه حباب ناقص است.")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Bot v{VERSION} is running smoothly.", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
