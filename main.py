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

# حافظه برای ذخیره داده‌ها
MARKET_CACHE = {
    "gold": {}, 
    "currency": {},
    "last_sync": "بروزرسانی نشده"
}

# ----------------------------------------
#           *** ۲. موتور هوشمند واکشی Pro ***
# ----------------------------------------

def sync_pro_data():
    global MARKET_CACHE
    # اصلاح URL: اضافه کردن تمام بخش‌ها طبق مستندات برای جلوگیری از لیست خالی
    url = f"https://brsapi.ir/Api/Market/Gold_Currency_Pro.php?key={BRS_TOKEN}&section=gold,currency"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            
            # بررسی موفقیت‌آمیز بودن پاسخ
            if res_json.get("successful") or "gold" in res_json:
                # استخراج طلا
                gold_list = res_json.get('gold', [])
                for item in gold_list:
                    MARKET_CACHE["gold"][item.get('symbol')] = item
                
                # استخراج ارز
                curr_list = res_json.get('currency', [])
                for item in curr_list:
                    MARKET_CACHE["currency"][item.get('symbol')] = item
                
                MARKET_CACHE["last_sync"] = jdatetime.datetime.now().strftime("%H:%M:%S")
                return True
    except Exception as e:
        print(f"Fetch Error: {e}")
    return False

def get_p(category, symbol):
    """تابع کمکی برای استخراج امن قیمت و تبدیل به عدد"""
    item = MARKET_CACHE.get(category, {}).get(symbol, {})
    # در نسخه پرو ممکن است قیمت در فیلد price یا last_price باشد
    raw_price = item.get('price') or item.get('last_price') or 0
    try:
        return float(str(raw_price).replace(',', ''))
    except:
        return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 مقایسه و تغییرات")
    markup.row("⚪️ حباب طلا", "🧠 مشاوره خرید")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_pro_data()
    bot.send_message(
        message.chat.id, 
        "🥇 **ربات نسخه Pro فعال شد.**\nبرای دریافت آخرین قیمت‌ها روی دکمه زیر بزنید:", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    bot.send_chat_action(message.chat.id, 'find_location')
    if not sync_pro_data():
        bot.reply_to(message, "⚠️ خطا در دریافت اطلاعات. ممکن است ترافیک سرور بالا باشد.")
        return

    # استخراج قیمت‌ها با متد امن جدید
    g18 = get_p("gold", "IR_18K_GOLD") / 10
    sek = get_p("gold", "IR_COIN_EMAMI") / 10
    usd = get_p("currency", "USD") / 10
    ons = get_p("gold", "XAU_USD")

    if g18 == 0:
        bot.send_message(message.chat.id, "❌ قیمت‌ها در پاسخ API یافت نشد. لطفاً لحظاتی دیگر تلاش کنید.")
        return

    msg = (f"💰 **آخرین نرخ‌های بازار (Pro)**\n"
           f"📅 `{jdatetime.datetime.now().strftime('%Y/%m/%d')}` | ⏰ `{MARKET_CACHE['last_sync']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{g18:,.0f}` تومان\n"
           f"👑 سکه امامی: `{sek:,.0f}` تومان\n"
           f"💵 دلار آمریکا: `{usd:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 مقایسه و تغییرات")
def handle_compare(message):
    sync_pro_data()
    g = MARKET_CACHE["gold"].get("IR_18K_GOLD", {})
    d = MARKET_CACHE["currency"].get("USD", {})

    def get_change_text(item):
        val = float(str(item.get('change_value', 0)).replace(',', '')) / 10
        pct = item.get('change_percent', 0)
        emoji = "📈" if float(pct) >= 0 else "📉"
        return f"{emoji} `{abs(val):,.0f}` تومان ({pct}%)"

    msg = (f"📊 **تغییرات نسبت به قیمت بسته شده**\n\n"
           f"🔸 **طلا ۱۸ عیار:**\n{get_change_text(g)}\n\n"
           f"🔸 **دلار آمریکا:**\n{get_change_text(d)}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_pro_data()
    g18 = get_p("gold", "IR_18K_GOLD") / 10
    usd = get_p("currency", "USD") / 10
    ons = get_p("gold", "XAU_USD")
    
    if g18 > 0 and usd > 0:
        intrinsic = (ons * (usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((g18 - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n💰 ارزش واقعی: `{intrinsic:,.0f}`\n🎈 حباب: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "❌ خطا در دریافت دیتای مورد نیاز.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره خرید")
def handle_advice(message):
    bot.send_message(message.chat.id, "🧠 بر اساس تحلیل حباب، در صورت حباب بالای ۳٪ خرید توصیه نمی‌شود.")

# ----------------------------------------
#           *** ۴. وب‌هوک و سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    
    try:
        bot.send_message(ADMIN_ID, "✅ **نسخه v99 Pro با موفقیت مستقر شد.**\nمشکل واکشی قیمت برطرف گردید.")
    except: pass
    
    server.run(host="0.0.0.0", port=PORT)
