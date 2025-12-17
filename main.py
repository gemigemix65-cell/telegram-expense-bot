import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
from bs4 import BeautifulSoup
import jdatetime 
from pydantic import BaseModel
import time
import re

# 🚀 استفاده از کتابخانه استاندارد گوگل
import google.generativeai as genai

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه کش برای قیمت‌ها
CACHE = {
    "data": {
        "gold_18k_gram": 0,
        "sekeh_emami": 0,
        "usd_rial": 0,
        "ounce_usd": 0.0,
        "time": "در حال بروزرسانی...",
        "source": "None"
    }
}

# --- تنظیمات هوش مصنوعی Gemini ---
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # استفاده از مدل 1.5-flash که بسیار پایدار و سریع است
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ اتصال به Gemini برقرار شد.")
    except Exception as e:
        print(f"❌ خطا در پیکربندی Gemini: {e}")
        ai_model = None
else:
    ai_model = None
    print("⚠️ GEMINI_API_KEY یافت نشد!")

# ----------------------------------------
#           *** ۲. استخراج داده از منابع ***
# ----------------------------------------

def clean_val(text):
    if not text: return 0
    p_nums = "۰۱۲۳۴۵۶۷۸۹"
    e_nums = "0123456789"
    table = str.maketrans(p_nums, e_nums)
    clean = text.translate(table).replace(',', '')
    clean = "".join(filter(str.isdigit, clean))
    return int(clean) if clean else 0

def fetch_tgju():
    try:
        res = requests.get("https://www.tgju.org/", timeout=7)
        soup = BeautifulSoup(res.text, 'html.parser')
        d = {"gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, "ounce_usd": 0}
        targets = {"price_dollar_rl": "usd_rial", "geram18": "gold_18k_gram", "sekeh": "sekeh_emami", "ons": "ounce_usd"}
        for k, f in targets.items():
            row = soup.select_one(f'tr[data-market-row="{k}"]')
            if row:
                val = row.select_one('.info-price').text
                if f == "ounce_usd": d[f] = float(val.replace(',', ''))
                else: d[f] = clean_val(val)
        return d if d['gold_18k_gram'] > 0 else None
    except: return None

def get_final_data():
    global CACHE
    data = fetch_tgju() # اولویت اول TGJU
    if data and data['gold_18k_gram'] > 0:
        data['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
        data['source'] = "TGJU"
        data['is_live'] = True
        CACHE['data'] = data
        return data
    cached = CACHE['data'].copy()
    cached['is_live'] = False
    return cached

# ----------------------------------------
#           *** ۳. بخش تحلیل هوشمند ***
# ----------------------------------------

def get_ai_analysis(market_data):
    if not ai_model:
        return "❌ کلید API هوش مصنوعی در متغیرهای لیارا ست نشده است.", None

    prompt = (
        f"تحلیلگر طلا: طلای ۱۸ عیار {market_data['gold_18k_gram']} تومان، "
        f"دلار {market_data['usd_rial']} تومان، سکه {market_data['sekeh_emami']} تومان. "
        "پاسخ را فقط به صورت یک JSON فارسی با این کلیدها بده: summary, advice, reason"
    )

    try:
        response = ai_model.generate_content(prompt)
        # استخراج JSON از پاسخ (حتی اگر گوگل آن را در کد بلاک قرار داده باشد)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
            return None, analysis
        return "⚠️ پاسخ هوش مصنوعی قالب درستی نداشت.", None
    except Exception as e:
        # اگر خطا مربوط به منطقه جغرافیایی باشد، اینجا چاپ می‌شود
        print(f"DEBUG AI ERROR: {str(e)}")
        if "User location is not supported" in str(e):
            return "❌ گوگل آی‌پی سرور ایران را برای هوش مصنوعی مسدود کرده است. باید از پروکسی استفاده شود یا سرور خارج تهیه شود.", None
        return f"⚠️ خطای فنی در تحلیل: {str(e)[:50]}", None

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
    bot.send_message(message.chat.id, "🥇 ربات هوشمند طلا آماده است.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    data = get_final_data()
    if data['gold_18k_gram'] == 0:
        bot.reply_to(message, "❌ خطا در دریافت قیمت.")
        return
    msg = (f"💰 **قیمت لحظه‌ای**\n\n"
           f"🥇 طلا ۱۸ عیار: {data['gold_18k_gram']:,.0f}\n"
           f"💵 دلار: {data['usd_rial']:,.0f}\n"
           f"👑 سکه: {data['sekeh_emami']:,.0f}\n"
           f"🌐 انس: {data['ounce_usd']:,.2f}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    data = get_final_data()
    try:
        theo = (data['ounce_usd'] * (data['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((data['gold_18k_gram'] - theo) / theo) * 100
        msg = f"⚪️ **تحلیل حباب**\n\n📊 حباب: {percent:.2f}%"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')
    except: bot.reply_to(message, "خطا در محاسبه حباب.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل...")
    data = get_final_data()
    err, analysis = get_ai_analysis(data)
    if err: bot.send_message(message.chat.id, err)
    else:
        msg = f"✨ **تحلیل AI**\n\n💡 **پیشنهاد:** {analysis.get('advice')}\n🧐 **علت:** {analysis.get('reason')}"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۵. وب‌هوک ***
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
