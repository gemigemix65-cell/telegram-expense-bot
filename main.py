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
# استفاده از توکن شما
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

# ----------------------------------------
#           *** ۲. دریافت داده (طبق آموزش BrsApi) ***
# ----------------------------------------

def fetch_market_data():
    global CACHE
    # آدرس استاندارد طبق مستندات سایت
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    # تنظیم هدرها برای جلوگیری از Connection Reset (طبق آموزش سایت)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://brsapi.ir/',
        'Connection': 'keep-alive'
    }

    try:
        # استفاده از سشن برای پایداری بیشتر
        with requests.Session() as session:
            response = session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                
                # استخراج و تبدیل ریال به تومان
                if 'gold' in data:
                    for item in data['gold']:
                        name = item.get('name', '')
                        p_toman = int(item.get('price', 0)) / 10
                        
                        if "18 عیار" in name:
                            CACHE['data']['gold_18k_gram'] = p_toman
                        elif "سکه امامی" in name:
                            CACHE['data']['sekeh_emami'] = p_toman
                        elif "انس طلا" in name:
                            CACHE['data']['ounce_usd'] = float(item.get('price', 0))

                if 'currency' in data:
                    for item in data['currency']:
                        if item.get('name') == 'دلار':
                            CACHE['data']['usd_rial'] = int(item.get('price', 0)) / 10

                CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
                return CACHE['data']
            else:
                print(f"BrsApi HTTP Error: {response.status_code}")
                
    except Exception as e:
        print(f"❌ خطای نهایی BrsApi: {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی ***
# ----------------------------------------

def get_logic_analysis(d):
    if d['gold_18k_gram'] < 1000:
        return "⚠️ خطا در دریافت اطلاعات.", "لطفاً لحظاتی دیگر تلاش کنید."

    # فرمول محاسبه حباب
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    
    if bubble > 2.5:
        summary = f"حباب مثبت ({bubble:.1f}%). طلا گران‌تر از ارزش جهانی است."
        advice = "❌ ریسک خرید بالا."
    elif -1 <= bubble <= 2.5:
        summary = "بازار در تعادل است."
        advice = "⚖️ مناسب برای خرید پله‌ای."
    else:
        summary = f"حباب منفی ({bubble:.1f}%). طلا ارزان‌تر از ارزش جهانی است."
        advice = "✅ فرصت خرید مناسب."
        
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
    bot.send_message(message.chat.id, "🥇 ربات هوشمند طلا (نسخه بهینه BrsApi) فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ خطای ارتباط با منبع داده. لطفاً دوباره دکمه را بزنید.")
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
        bot.reply_to(message, "❌ خطا در محاسبه داده‌ها.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال واکشی اطلاعات از BrsApi...")
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
