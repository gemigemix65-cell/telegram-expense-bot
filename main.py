import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
import jdatetime 
import time
import re

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# کش برای ذخیره آخرین قیمت‌ها
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده"
    }
}

# ----------------------------------------
#           *** ۲. دریافت قیمت (سورس جدید و مستقیم) ***
# ----------------------------------------

def fetch_market_data():
    """استخراج قیمت با استفاده از API مستقیم (بسیار پایدار)"""
    global CACHE
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # فراخوانی منبع مستقیم دیتای لایو
        res = requests.get("https://api.tgju.org/v1/market/indicator/summary-table-data/live", headers=headers, timeout=10)
        
        if res.status_code == 200:
            raw_data = res.json().get('data', [])
            for item in raw_data:
                key = item[0]
                val = str(item[1]).replace(',', '')
                
                if key == "geram18": CACHE['data']['gold_18k_gram'] = int(val)
                elif key == "price_dollar_rl": CACHE['data']['usd_rial'] = int(val)
                elif key == "sekeh": CACHE['data']['sekeh_emami'] = int(val)
                elif key == "ons": CACHE['data']['ounce_usd'] = float(val)
            
            CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return CACHE['data']
    except Exception as e:
        print(f"Fetch Error: {e}")
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی (Logic AI) ***
# ----------------------------------------

def get_expert_analysis(d):
    """جایگزین هوش مصنوعی: تحلیل بر اساس الگوریتم‌های اقتصادی"""
    if d['gold_18k_gram'] == 0 or d['ounce_usd'] == 0:
        return "⚠️ داده‌های بازار ناقص است.", "صبر کنید تا قیمت‌ها بروز شوند."

    # محاسبه حباب طلای ۱۸ عیار
    # فرمول: (انس * دلار * ۰.۷۵) / ۳۱.۱۰۳۵ / ۱۰
    intrinsic_value = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble_percent = ((d['gold_18k_gram'] - intrinsic_value) / intrinsic_value) * 100
    
    # موتور تصمیم‌گیری
    if bubble_percent > 3:
        summary = "بازار در حال حاضر دارای حباب مثبت شدیدی است. قیمت داخلی بسیار بالاتر از ارزش واقعی جهانی است."
        advice = "❌ در این سطح قیمت، خرید پرریسک است. پیشنهاد می‌شود منتظر تخلیه حباب باشید."
    elif 0 < bubble_percent <= 3:
        summary = "بازار در وضعیت نسبتاً متعادلی قرار دارد اما همچنان کمی حباب مثبت دیده می‌شود."
        advice = "⚖️ برای خرید پله‌ای بلندمدت مناسب است، اما برای نوسان‌گیری خیر."
    elif bubble_percent <= 0:
        summary = "طلا در بازار داخلی زیر ارزش ذاتی خود معامله می‌شود (حباب منفی)."
        advice = "✅ فرصت استثنایی برای خرید! طلا در حال حاضر ارزان‌تر از ارزش جهانی آن است."
    
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
    bot.send_message(message.chat.id, "🏅 ربات تحلیلگر حرفه‌ای طلا\nنسخه فوق‌پایدار و ضدتحریم فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ خطا در دریافت قیمت. دوباره تلاش کنید.")
        return
    msg = (f"💰 **قیمت لحظه‌ای بازار**\n\n"
           f"🥇 طلا ۱۸ عیار: {d['gold_18k_gram']:,.0f}\n"
           f"💵 دلار آزاد: {d['usd_rial']:,.0f}\n"
           f"👑 سکه امامی: {d['sekeh_emami']:,.0f}\n"
           f"🌐 انس جهانی: {d['ounce_usd']:,.2f}\n\n"
           f"⏰ بروزرسانی: {d['time']}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_market_data()
    try:
        intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
        emoji = "🔴" if percent > 0 else "🟢"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n📊 حباب: {percent:.2f}% {emoji}\n(نسبت به قیمت انس جهانی و دلار)", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🧐 در حال تحلیل متغیرهای اقتصادی...")
    d = fetch_market_data()
    summary, advice = get_expert_analysis(d)
    msg = f"✨ **تحلیل کارشناسی**\n\n📝 {summary}\n\n💡 **پیشنهاد:** {advice}"
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
