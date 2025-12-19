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

TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "نیاز به آپدیت"}

# ----------------------------------------
#           *** ۲. موتور واکشی هوشمند v104 ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    # تست هر دو آدرس (پرو و معمولی) در صورت خطا
    urls = [
        f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}",
        f"https://brsapi.ir/Api/Market/Gold_Currency_Pro.php?key={BRS_TOKEN}"
    ]
    
    last_error = ""
    for url in urls:
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if response.status_code == 200:
                res_json = response.json()
                if not res_json.get('successful'):
                    last_error = f"API Error: {res_json.get('message_error')}"
                    continue

                temp_items = {}
                # استخراج طلا و ارز با متد جدید و امن
                for category_name in ['gold', 'currency']:
                    data_block = res_json.get(category_name, {})
                    if isinstance(data_block, dict):
                        for sub_list in data_block.values():
                            if isinstance(sub_list, list):
                                for item in sub_list:
                                    symbol = item.get('symbol')
                                    if symbol: temp_items[symbol] = item
                
                if temp_items:
                    MARKET_DATA["items"] = temp_items
                    MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
                    return True, "OK"
            else:
                last_error = f"HTTP {response.status_code}"
        except Exception as e:
            last_error = str(e)
            
    return False, last_error

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

@bot.message_handler(commands=['start', 'restart'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, error_msg = sync_market_data()
    status = "✅ متصل" if success else f"❌ خطا: {error_msg}"
    bot.send_message(message.chat.id, f"🤖 وضعیت ربات: {status}", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    bot.send_chat_action(message.chat.id, 'typing')
    success, error_msg = sync_market_data()
    
    if not success:
        bot.reply_to(message, f"⚠️ **خطا در دریافت اطلاعات:**\n`{error_msg}`\n\nلطفاً از صحت API KEY مطمئن شوید یا چند لحظه دیگر تست کنید.")
        return

    # استفاده از سمبل‌های دقیق JSON شما
    p_gold = get_p("IR_GOLD_18K") / 10
    p_sekeh = get_p("IR_COIN_EMAMI") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")

    msg = (f"💰 **نرخ‌های زنده بازار**\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n"
           f"👑 سکه امامی: `{p_sekeh:,.0f}` تومان\n"
           f"💵 دلار آمریکا: `{p_usd:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات")
def handle_changes(message):
    success, _ = sync_market_data()
    g = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = g.get('change_percent', 0)
    bot.send_message(message.chat.id, f"📊 درصد تغییرات طلا ۱۸ عیار: `{pct}%`")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    success, _ = sync_market_data()
    p_gold = get_p("IR_GOLD_18K") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")
    
    if p_gold > 0 and p_usd > 0:
        intrinsic = (p_ons * (p_usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\nحباب فعلی: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ دیتا برای محاسبه کافی نیست.")

# ----------------------------------------
#           *** ۴. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return "Bot is monitoring...", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
