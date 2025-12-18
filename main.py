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
# توکن مستقیم شما برای اطمینان از کارکرد
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده"
    }
}

# ایجاد یک Session برای پایداری در درخواست‌ها و جلوگیری از Connection Reset
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json'
})

# ----------------------------------------
#           *** ۲. دریافت داده از BrsApi ***
# ----------------------------------------

def fetch_market_data():
    global CACHE
    url = f"https://brsapi.ir/Free7/Api/Live?token={BRS_TOKEN}" 
    
    try:
        # استفاده از session بجای requests ساده برای جلوگیری از ارور 104
        response = session.get(url, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            
            # استخراج طلا و سکه
            if 'gold' in data:
                for item in data['gold']:
                    name = item.get('name', '')
                    price = item.get('price', 0)
                    
                    if "18 عیار" in name:
                        CACHE['data']['gold_18k_gram'] = int(price)
                    elif "سکه امامی" in name:
                        CACHE['data']['sekeh_emami'] = int(price)
                    elif "انس طلا" in name:
                        CACHE['data']['ounce_usd'] = float(price)

            # استخراج دلار
            if 'currency' in data:
                for item in data['currency']:
                    if item.get('name') == 'دلار':
                        CACHE['data']['usd_rial'] = int(item.get('price', 0))

            CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return CACHE['data']
        else:
            print(f"❌ خطای سرور BrsApi: {response.status_code}")
            
    except Exception as e:
        print(f"❌ خطای ارتباطی (Connection Error): {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی ***
# ----------------------------------------

def get_logic_analysis(d):
    if d['gold_18k_gram'] < 1000:
        return "⚠️ داده‌های بازار دریافت نشد.", "لطفاً مجدد تلاش کنید."

    # فرمول ارزش ذاتی طلا ۱۸ عیار
    # (اونس * دلار * 0.75) / 31.1035 / 10
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    
    if bubble > 2.5:
        summary = f"بازار دارای حباب مثبت ({bubble:.1f}%) است."
        advice = "❌ قیمت داخلی گران‌تر از ارزش جهانی است. فعلاً صبر کنید."
    elif -1 <= bubble <= 2.5:
        summary = "بازار در وضعیت تعادل قرار دارد."
        advice = "⚖️ قیمت‌ها منطقی است. مناسب برای خرید پله‌ای."
    else:
        summary = f"بازار دارای حباب منفی ({bubble:.1f}%) است."
        advice = "✅ قیمت طلا ارزان‌تر از ارزش جهانی است. فرصت خرید!"
        
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
    bot.send_message(message.chat.id, "🥇 ربات هوشمند طلا (نسخه BrsApi) فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ سرویس موقتاً پاسخگو نیست. لطفاً چند لحظه دیگر امتحان کنید.")
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
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n📊 حباب: `{percent:.2f}%` {emoji}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل داده‌ها...")
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
