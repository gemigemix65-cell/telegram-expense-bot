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
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه کش برای قیمت‌ها
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده"
    }
}

# ----------------------------------------
#           *** ۲. دریافت داده از Prices API ***
# ----------------------------------------

def fetch_from_api():
    global CACHE
    # آدرس پایه طبق مستنداتی که فرستادید
    base_url = "https://prices.readme.io/v1" 
    
    try:
        # دریافت لیست نمادها و قیمت‌های لحظه‌ای
        # نکته: معمولاً برای دریافت قیمت لحظه‌ای از این متد استفاده می‌شود
        response = requests.get(f"https://api.tgju.org/v1/market/indicator/summary-table-data/live", timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json().get('data', [])
            for item in raw_data:
                symbol = item[0]
                price = str(item[1]).replace(',', '')
                
                if symbol == "geram18": CACHE['data']['gold_18k_gram'] = int(price)
                elif symbol == "price_dollar_rl": CACHE['data']['usd_rial'] = int(price)
                elif symbol == "sekeh": CACHE['data']['sekeh_emami'] = int(price)
                elif symbol == "ons": CACHE['data']['ounce_usd'] = float(price)

            CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return CACHE['data']
            
    except Exception as e:
        print(f"API Error: {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی ***
# ----------------------------------------

def get_logic_analysis(d):
    if d['gold_18k_gram'] == 0 or d['usd_rial'] == 0:
        return "⚠️ در حال دریافت اطلاعات...", "لطفاً لحظاتی دیگر مجدد تلاش کنید."

    # فرمول ارزش ذاتی طلا ۱۸ عیار
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    
    if bubble > 2:
        summary = f"بازار دارای حباب مثبت ({bubble:.1f}%) است. قیمت داخلی گران‌تر از ارزش جهانی است."
        advice = "❌ خرید در این قیمت پرریسک است."
    elif -1 <= bubble <= 2:
        summary = "بازار در وضعیت تعادل است."
        advice = "⚖️ زمان مناسب برای خرید پله‌ای."
    else:
        summary = f"بازار دارای حباب منفی ({bubble:.1f}%) است. طلا زیر قیمت واقعی است."
        advice = "✅ فرصت عالی برای خرید."
        
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
        "🏅 **ربات تحلیلگر هوشمند بازار**\nاتصال به API قیمت‌های آزاد برقرار شد.", 
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_from_api()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ سرویس موقتاً در دسترس نیست.")
        return
    
    msg = (f"💰 **قیمت‌های لحظه‌ای (API)**\n\n"
           f"🥇 طلا ۱۸ عیار: `{d['gold_18k_gram']:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{d['usd_rial']:,.0f}` تومان\n"
           f"👑 سکه امامی: `{d['sekeh_emami']:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{d['ounce_usd']:,.2f}` دلار\n\n"
           f"⏰ بروزرسانی: {d['time']}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_from_api()
    try:
        intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
        emoji = "🔴" if percent > 0 else "🟢"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n📊 میزان حباب: `{percent:.2f}%` {emoji}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ دیتا ناقص است.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل داده‌ها...")
    d = fetch_from_api()
    summary, advice = get_logic_analysis(d)
    msg = f"✨ **تحلیل سیستمی**\n\n📝 {summary}\n\n💡 **پیشنهاد:** {advice}"
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
