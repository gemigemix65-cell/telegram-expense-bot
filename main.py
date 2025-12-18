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

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه کش برای قیمت‌ها
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "last_update": "بروزرسانی نشده"
    }
}

# ----------------------------------------
#           *** ۲. دریافت داده (بر اساس جدول نمادهای سایت) ***
# ----------------------------------------

def fetch_market_data():
    global CACHE
    # آدرس API رایگان طبق مستندات صفحه وب ارسالی
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            
            # ۱. استخراج طلا و سکه از بخش 'gold' بر اساس symbol
            if 'gold' in data:
                for item in data['gold']:
                    sym = item.get('symbol', '')
                    price = int(item.get('price', 0))
                    
                    if sym == "IR_18K_GOLD": # طلای 18 عیار
                        CACHE['data']['gold_18k_gram'] = price / 10
                    elif sym == "IR_COIN_EMAMI": # سکه امامی
                        CACHE['data']['sekeh_emami'] = price / 10
                    elif sym == "XAU_USD": # انس طلا (قیمت جهانی به دلار)
                        CACHE['data']['ounce_usd'] = float(item.get('price', 0))

            # ۲. استخراج دلار از بخش 'currency' بر اساس symbol
            if 'currency' in data:
                for item in data['currency']:
                    if item.get('symbol') == "USD": # دلار آمریکا
                        CACHE['data']['usd_rial'] = int(item.get('price', 0)) / 10

            # تنظیم تاریخ شمسی و ساعت
            now = jdatetime.datetime.now()
            CACHE['data']['last_update'] = now.strftime("%Y/%m/%d ساعت %H:%M")
            return CACHE['data']
            
    except Exception as e:
        print(f"Fetch Error: {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی ***
# ----------------------------------------

def get_logic_analysis(d):
    if d['gold_18k_gram'] < 1000:
        return "⚠️ داده‌های بازار هنوز کامل دریافت نشده است.", "لطفاً دقایقی دیگر دوباره تلاش کنید."

    # فرمول ارزش ذاتی طلا ۱۸ عیار
    # (انس * قیمت دلار به ریال * ۰.۷۵) / ۳۱.۱۰۳۵ / ۱۰ (برای تومان)
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    
    if bubble > 2.5:
        summary = f"حباب مثبت طلا: `{bubble:.1f}%`"
        advice = "❌ در حال حاضر قیمت داخلی حباب دارد. خرید در این سطح پرریسک است."
    elif -1 <= bubble <= 2.5:
        summary = "بازار در وضعیت تعادل (بدون حباب)"
        advice = "⚖️ قیمت‌ها با انس جهانی هماهنگ است. مناسب برای پس‌انداز."
    else:
        summary = f"حباب منفی طلا: `{bubble:.1f}%`"
        advice = "✅ قیمت داخلی ارزان‌تر از ارزش جهانی است. فرصت خرید عالی!"
        
    return summary, advice

# ----------------------------------------
#           *** ۴. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "⚪️ حباب طلا")
    markup.row("🧠 مشاوره بازار")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        "🏅 **تحلیلگر هوشمند بازار طلا و ارز**\nداده‌ها با دقت نمادهای سیستمی BrsApi تنظیم شدند.", 
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ خطای سیستمی در دریافت قیمت. لطفاً لحظاتی دیگر مجدد تلاش کنید.")
        return
    
    msg = (f"💰 **آخرین وضعیت بازار**\n"
           f"📅 بروزرسانی: `{d['last_update']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{d['gold_18k_gram']:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{d['usd_rial']:,.0f}` تومان\n"
           f"👑 سکه امامی: `{d['sekeh_emami']:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{d['ounce_usd']:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_market_data()
    try:
        intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
        emoji = "🔴" if percent > 0 else "🟢"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n📊 میزان حباب: `{percent:.2f}%` {emoji}\n\n*نکته: حباب مثبت یعنی گران‌تر از قیمت جهانی و حباب منفی یعنی ارزان‌تر.*", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ خطا در محاسبه. لطفاً قیمت لحظه‌ای را چک کنید.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل داده‌های زنده بازار...")
    d = fetch_market_data()
    summary, advice = get_logic_analysis(d)
    msg = f"✨ **تحلیل اختصاصی ربات**\n\n📝 {summary}\n\n💡 **پیشنهاد:** {advice}"
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۵. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
