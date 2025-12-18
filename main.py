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

# حافظه کش برای قیمت‌ها
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده"
    }
}

# ----------------------------------------
#           *** ۲. دریافت داده (نسخه ضد تحریم دیتاسنتر) ***
# ----------------------------------------

def fetch_market_data():
    global CACHE
    # استفاده از منبع داده منعطف که با سرورهای خارج از ایران مشکلی ندارد
    # این آدرس یک Gateway پایدار برای دریافت نرخ‌های ایران است
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # تلاش اول: استفاده از منبع دیتای زنده TGJU (با متد شبیه‌سازی مرورگر)
        url = f"https://api.tgju.org/v1/market/indicator/summary-table-data/live?_={int(time.time())}"
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json().get('data', [])
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
        print(f"Primary Source Failed: {e}")
        
    # تلاش دوم: اگر منبع اول بلاک بود، از یک اسکرپر متن‌محور مقاوم استفاده کن
    try:
        res_backup = requests.get("https://www.tala.ir/price", headers=headers, timeout=10)
        content = res_backup.text
        gold = re.search(r'طلا ۱۸ عیار.*?<span class="price">([\d,]+)', content)
        usd = re.search(r'دلار.*?<span class="price">([\d,]+)', content)
        ons = re.search(r'انس طلا.*?<span class="price">([\d,.]+)', content)
        
        if gold: CACHE['data']['gold_18k_gram'] = int(gold.group(1).replace(',', ''))
        if usd: CACHE['data']['usd_rial'] = int(usd.group(1).replace(',', ''))
        if ons: CACHE['data']['ounce_usd'] = float(ons.group(1).replace(',', ''))
        
        CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        print(f"Backup Source Failed: {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی ***
# ----------------------------------------

def get_logic_analysis(d):
    if d['gold_18k_gram'] < 1000:
        return "⚠️ فعلاً امکان دریافت قیمت از سرور وجود ندارد.", "احتمالاً محدودیت موقت آی‌پی رخ داده است."

    # فرمول ارزش ذاتی طلا ۱۸ عیار
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    
    if bubble > 2.5:
        summary = f"بازار دارای حباب مثبت ({bubble:.1f}%) است."
        advice = "❌ خرید در این قیمت‌ها ریسک بالایی دارد."
    elif -1 <= bubble <= 2.5:
        summary = "بازار در وضعیت تعادلی و منطقی قرار دارد."
        advice = "⚖️ زمان مناسب برای خرید پله‌ای."
    else:
        summary = f"بازار دارای حباب منفی ({bubble:.1f}%) است."
        advice = "✅ قیمت داخلی زیر ارزش جهانی است. فرصت خرید!"
        
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
    bot.send_message(message.chat.id, "🏅 ربات هوشمند طلا (نسخه ضدبلاک لیارا) فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ منبع قیمت موقتاً در دسترس نیست. ۵ دقیقه دیگر دوباره تلاش کنید.")
        return
    
    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"🥇 طلا ۱۸ عیار: `{d['gold_18k_gram']:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{d['usd_rial']:,.0f}` تومان\n"
           f"👑 سکه امامی: `{d['sekeh_emami']:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{d['ounce_usd']:,.2f}` دلار\n\n"
           f"⏰ بروزرسانی: {d['time']}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_market_data()
    try:
        intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
        emoji = "🔴" if percent > 0 else "🟢"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n📊 میزان حباب: `{percent:.2f}%` {emoji}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ دیتا ناقص است.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل داده‌های بازار...")
    d = fetch_market_data()
    summary, advice = get_logic_analysis(d)
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
