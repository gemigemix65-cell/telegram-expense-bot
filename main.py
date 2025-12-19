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
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "به‌روزرسانی نشده"}

# ----------------------------------------
#           *** ۲. موتور واکشی نسخه v1.1.0 ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    # استفاده از آدرس مستقیم برای تست پایداری
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    try:
        # شبیه‌سازی دقیق یک مرورگر موبایل برای عبور از فیلترهای احتمالی آی‌پی
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Accept': 'application/json',
            'Referer': 'https://brsapi.ir/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        # اگر کلاً بلاک شده باشیم (مثل کلودفلر)
        if response.status_code == 403 or response.status_code == 406:
            return False, f"آی‌پی سرور لیارا مسدود است (کد {response.status_code})"

        res_json = response.json()
        
        if not res_json.get('successful'):
            # اگر مسیج خالی بود، کل دیتای دریافتی را برای دیباگ نمایش می‌دهیم
            err = res_json.get('message_error')
            if not err:
                return False, "API پاسخ نامعتبر داد (Empty Error Field)"
            return False, err

        temp_items = {}
        for category in ['gold', 'currency']:
            data_block = res_json.get(category, {})
            if isinstance(data_block, dict):
                for sub_list in data_block.values():
                    if isinstance(sub_list, list):
                        for item in sub_list:
                            symbol = item.get('symbol')
                            if symbol:
                                temp_items[symbol] = item
        
        if not temp_items:
            return False, "دیتای قیمت یافت نشد."

        MARKET_DATA["items"] = temp_items
        MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
        return True, "OK"

    except Exception as e:
        return False, f"خطای سیستمی: {str(e)[:50]}"

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
    status = "🟢 متصل" if success else f"🔴 وضعیت: {msg_result}"
    
    welcome_text = (
        f"🤖 **ربات قیمت لحظه‌ای**\n"
        f"📦 نسخه: `{VERSION}`\n"
        f"--------------------------\n"
        f"وضعیت: {status}\n\n"
        f"آخرین آپدیت: `{MARKET_DATA['update_time']}`"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    bot.send_chat_action(message.chat.id, 'typing')
    success, error_msg = sync_market_data()
    
    if not success:
        bot.reply_to(message, f"⚠️ **خطای فنی:**\n`{error_msg}`")
        return

    p_gold = get_p("IR_GOLD_18K") / 10
    p_sekeh = get_p("IR_COIN_EMAMI") / 10
    p_usd = get_p("USD") / 10
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
    pct = item.get('change_percent', '0')
    bot.send_message(message.chat.id, f"📊 تغییرات طلا ۱۸: `{pct}%`")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")
    
    if p_gold > 0 and p_usd > 0:
        intrinsic = (p_ons * (p_usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\nحباب: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ دیتا ناقص.")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Bot v{VERSION} is running.", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
