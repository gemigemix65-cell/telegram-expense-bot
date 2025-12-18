import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
import jdatetime 
import time
import re
from groq import Groq # هوش مصنوعی رایگان و سریع

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
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

# --- تنظیمات هوش مصنوعی Groq (رایگان) ---
ai_client = None
if GROQ_API_KEY:
    try:
        ai_client = Groq(api_key=GROQ_API_KEY)
        print("✅ هوش مصنوعی رایگان Groq فعال شد.")
    except Exception as e:
        print(f"❌ خطا در Groq: {e}")

# ----------------------------------------
#           *** ۲. دریافت قیمت (متد ضد خطا) ***
# ----------------------------------------

def fetch_market_data():
    """استخراج قیمت با استفاده از متد API داخلی TGJU (بسیار پایدار)"""
    global CACHE
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # فراخوانی API مستقیم سایت بجای اسکرپ کردن ظاهر سایت
        res = requests.get("https://api.tgju.org/v1/market/indicator/summary-table-data/live", headers=headers, timeout=10)
        
        if res.status_code == 200:
            raw_data = res.json().get('data', [])
            for item in raw_data:
                key = item[0] # نام نماد
                val = str(item[1]).replace(',', '') # قیمت
                
                if key == "geram18": CACHE['data']['gold_18k_gram'] = int(val)
                elif key == "price_dollar_rl": CACHE['data']['usd_rial'] = int(val)
                elif key == "sekeh": CACHE['data']['sekeh_emami'] = int(val)
                elif key == "ons": CACHE['data']['ounce_usd'] = float(val)
            
            CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return CACHE['data']
    except Exception as e:
        print(f"Price Fetch Error: {e}")
    return CACHE['data']

# ----------------------------------------
#           *** ۳. تحلیل با هوش مصنوعی رایگان ***
# ----------------------------------------

def get_ai_analysis(m_data):
    if not ai_client: return "❌ کلید Groq تنظیم نشده است.", None
    
    prompt = (f"تحلیلگر طلا: طلا ۱۸ عیار {m_data['gold_18k_gram']} تومان، "
              f"دلار {m_data['usd_rial']} تومان. "
              "وضعیت بازار را تحلیل کن و پاسخ را فقط در قالب JSON فارسی با کلیدهای summary و advice بده.")
    
    try:
        chat_completion = ai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a market analyst. Always respond in Persian JSON format."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile", # یکی از بهترین مدل‌های رایگان Groq
            response_format={"type": "json_object"}
        )
        return None, json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        print(f"Groq AI Error: {e}")
        return "⚠️ هوش مصنوعی موقتاً پاسخگو نیست.", None

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
    bot.send_message(message.chat.id, "🥇 ربات هوشمند طلا با موتور Groq فعال شد.\n(کاملاً رایگان و پرسرعت)", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ سرویس دریافت قیمت موقتاً قطع است.")
        return
    msg = (f"💰 **قیمت لحظه‌ای**\n\n"
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
        theo = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - theo) / theo) * 100
        status = "🔴 گران‌فروشی" if percent > 0 else "🟢 ارزانی"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n📊 حباب: {percent:.2f}%\n🔍 وضعیت: {status}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل با Llama 3...")
    d = fetch_market_data()
    err, analysis = get_ai_analysis(d)
    if err: bot.send_message(message.chat.id, err)
    else:
        msg = f"✨ **تحلیل AI (رایگان)**\n\n📝 {analysis.get('summary')}\n\n💡 **پیشنهاد:** {analysis.get('advice')}"
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
