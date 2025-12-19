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

# حافظه موقت (RAM Cache)
MARKET_DATA = {
    "items": {}, 
    "update_time": "به‌روزرسانی نشده"
}

# ----------------------------------------
#           *** ۲. موتور واکشی اصلاح شده ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    # استفاده از آدرس نسخه رایگان که با کلید شما سازگارتر است
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            
            temp_items = {}
            
            # استخراج طلا (بر اساس ساختار JSON ارسالی شما)
            gold_data = res_json.get('gold', {})
            for section in gold_data: # پیمایش ounce, type, coin
                if isinstance(gold_data[section], list):
                    for item in gold_data[section]:
                        symbol = item.get('symbol')
                        if symbol:
                            temp_items[symbol] = item
            
            # استخراج ارزها
            currency_data = res_json.get('currency', {})
            for section in currency_data: # پیمایش free, sana, nima
                if isinstance(currency_data[section], list):
                    for item in currency_data[section]:
                        symbol = item.get('symbol')
                        if symbol:
                            temp_items[symbol] = item

            MARKET_DATA["items"] = temp_items
            MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return True
        else:
            print(f"API Error: Status Code {response.status_code}")
    except Exception as e:
        print(f"Connection Error: {e}")
    return False

def get_p(symbol):
    """استخراج قیمت از حافظه و تبدیل به عدد"""
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        # حذف کاما و تبدیل به عدد
        return float(str(price).replace(',', ''))
    except:
        return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات")
    markup.row("⚪️ حباب طلا", "🧠 مشاوره")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    bot.send_message(
        message.chat.id, 
        "✅ **ربات با موفقیت متصل شد.**\nآماده دریافت نرخ‌های بازار...", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    if not sync_market_data():
        bot.reply_to(message, "⚠️ خطا در ارتباط با سرور BrsApi. لطفاً لحظاتی دیگر تلاش کنید.")
        return

    # استخراج سمبل‌ها طبق JSON شما
    p_gold = get_p("IR_GOLD_18K") / 10
    p_sekeh = get_p("IR_COIN_EMAMI") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")

    if p_gold == 0:
        bot.send_message(message.chat.id, "❌ متاسفانه دیتای بازار در این لحظه در دسترس نیست.")
        return

    msg = (f"💰 **آخرین نرخ‌های بازار**\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n"
           f"👑 سکه امامی: `{p_sekeh:,.0f}` تومان\n"
           f"💵 دلار آمریکا: `{p_usd:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات")
def handle_changes(message):
    sync_market_data()
    g = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = g.get('change_percent', 0)
    val = float(str(g.get('change_value', 0)).replace(',','')) / 10
    
    status = "📈 صعودی" if float(pct) >= 0 else "📉 نزولی"
    bot.send_message(message.chat.id, f"📊 **تغییرات طلا ۱۸ عیار:**\n\nوضعیت: {status}\nمقدار: `{abs(val):,.0f}` تومان\nدرصد: `{pct}%`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")
    
    if p_gold > 0 and p_usd > 0:
        # فرمول دقیق حباب
        intrinsic = (p_ons * (p_usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n💰 ارزش ذاتی: `{intrinsic:,.0f}`\n🎈 حباب: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ دیتا ناقص است.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره")
def handle_advice(message):
    bot.send_message(message.chat.id, "🧠 بر اساس حباب فعلی، استراتژی خود را تنظیم کنید.")

# ----------------------------------------
#           *** ۴. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return "Bot is Online!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
