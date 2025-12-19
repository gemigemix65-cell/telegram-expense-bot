import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
import jdatetime 
import time

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925" # شناسه شما برای دریافت پیام فعال سازی

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "last_update": "بروزرسانی نشده"
    },
    "raw": None
}

# ----------------------------------------
#           *** ۲. دریافت داده از API ***
# ----------------------------------------

def fetch_market_data():
    global CACHE
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            CACHE['raw'] = data # ذخیره برای دکمه مقایسه
            
            if 'gold' in data:
                for item in data['gold']:
                    sym = item.get('symbol', '')
                    price = float(item.get('price', 0))
                    if sym == "IR_18K_GOLD": CACHE['data']['gold_18k_gram'] = price / 10
                    elif sym == "IR_COIN_EMAMI": CACHE['data']['sekeh_emami'] = price / 10
                    elif sym == "XAU_USD": CACHE['data']['ounce_usd'] = price

            if 'currency' in data:
                for item in data['currency']:
                    if item.get('symbol') == "USD":
                        CACHE['data']['usd_rial'] = float(item.get('price', 0)) / 10

            CACHE['data']['last_update'] = jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M")
            return CACHE['data']
    except Exception as e:
        print(f"Error: {e}")
    return CACHE['data']

# ----------------------------------------
#           *** ۳. هندلرهای دکمه‌ها ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "⚪️ حباب طلا")
    markup.row("📊 مقایسه و تغییرات", "🧠 مشاوره")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    bot.send_message(
        message.chat.id, 
        "🚀 **ربات با موفقیت راه‌اندازی شد.**\nآماده دریافت دستورات شما هستم.", 
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "❌ خطا در اتصال به BrsApi. لطفاً لحظاتی دیگر تلاش کنید.")
        return
    
    msg = (f"💰 **آخرین نرخ‌های بازار**\n"
           f"📅 `{d['last_update']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{d['gold_18k_gram']:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{d['usd_rial']:,.0f}` تومان\n"
           f"👑 سکه امامی: `{d['sekeh_emami']:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{d['ounce_usd']:,.2f}` دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 مقایسه و تغییرات")
def handle_compare(message):
    fetch_market_data()
    data = CACHE['raw']
    if not data:
        bot.reply_to(message, "⚠️ دیتایی یافت نشد.")
        return

    msg = "📊 **مقایسه تغییرات قیمت (نسبت به دیروز)**\n\n"
    # استخراج تغییرات برای طلا و دلار
    sources = data.get('gold', []) + data.get('currency', [])
    for item in sources:
        if item.get('symbol') in ["IR_18K_GOLD", "USD"]:
            name = "طلا ۱۸ عیار" if item.get('symbol') == "IR_18K_GOLD" else "دلار"
            change_val = float(item.get('change_value', 0)) / 10
            change_pct = item.get('change_percent', '0')
            status = "📈 گران‌تر" if float(change_pct) > 0 else "📉 ارزان‌تر"
            msg += f"🔹 **{name}:**\n{status} شده به مقدار `{abs(change_val):,.0f}` تومان (`{change_pct}%`)\n\n"
    
    msg += "_تغییرات بر اساس آخرین بسته شدن بازار محاسبه شده است._"
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_market_data()
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    percent = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    emoji = "🔴" if percent > 0 else "🟢"
    bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n📊 حباب فعلی: `{percent:.2f}%` {emoji}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره")
def handle_advice(message):
    d = fetch_market_data()
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    advice = "✅ خرید پله‌ای" if bubble < 2 else "❌ فعلاً صبر کنید"
    bot.send_message(message.chat.id, f"🧠 **مشاوره هوشمند:**\n\nبر اساس محاسبات، پیشنهاد می‌شود: **{advice}**", parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. وب‌هوک و استقرار ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    
    # ارسال پیام فعال‌سازی به ادمین برای اطلاع از استقرار جدید
    try:
        bot.send_message(ADMIN_ID, "✅ **استقرار جدید با موفقیت انجام شد.**\nربات نسخه نهایی فعال و آماده به کار است.")
    except: pass
    
    server.run(host="0.0.0.0", port=PORT)
