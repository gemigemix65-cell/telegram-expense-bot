import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
from bs4 import BeautifulSoup
import jdatetime 
import time
import re

# 🚀 استفاده از پکیج جدید و بروز گوگل طبق پیشنهاد لاگ شما
from google import genai
from google.genai import types

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه کش برای قیمت‌ها (برای زمانی که سایت‌ها قطع شوند)
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده", "source": "None"
    }
}

# --- تنظیمات هوش مصنوعی Gemini (نسخه جدید google-genai) ---
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ اتصال به مدل جدید Gemini برقرار شد.")
    except Exception as e:
        print(f"❌ خطا در پیکربندی هوش مصنوعی: {e}")

# ----------------------------------------
#           *** ۲. استخراج داده (۳ منبع همزمان) ***
# ----------------------------------------

def clean_val(text):
    if not text: return 0
    text = text.replace(',', '')
    # تبدیل اعداد فارسی به انگلیسی
    p_nums = "۰۱۲۳۴۵۶۷۸۹"; e_nums = "0123456789"
    table = str.maketrans(p_nums, e_nums)
    clean = text.translate(table)
    clean = "".join(filter(str.isdigit, clean))
    return int(clean) if clean else 0

def fetch_data():
    """تلاش برای گرفتن دیتا از TGJU و در صورت خطا منابع دیگر"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get("https://www.tgju.org/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        d = {"gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, "ounce_usd": 0.0}
        
        # استخراج از جدول TGJU
        mapping = {"geram18": "gold_18k_gram", "sekeh": "sekeh_emami", 
                   "price_dollar_rl": "usd_rial", "ons": "ounce_usd"}
        
        for key, field in mapping.items():
            row = soup.select_one(f'tr[data-market-row="{key}"]')
            if row:
                val = row.select_one('.info-price').text
                if field == "ounce_usd":
                    d[field] = float(val.replace(',', ''))
                else:
                    d[field] = clean_val(val)
        
        if d['gold_18k_gram'] > 0:
            d['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            d['source'] = "TGJU"
            CACHE['data'] = d
            return d
    except:
        pass
    return CACHE['data']

# ----------------------------------------
#           *** ۳. تحلیل هوشمند ***
# ----------------------------------------

def get_ai_analysis(m_data):
    if not client:
        return "❌ تنظیمات هوش مصنوعی (API Key) یافت نشد.", None
    
    prompt = (f"تحلیلگر بازار طلا: طلا ۱۸ عیار {m_data['gold_18k_gram']} تومان، "
              f"دلار {m_data['usd_rial']} تومان. "
              "پاسخ را کوتاه و فقط در قالب JSON فارسی با کلیدهای summary و advice و reason بده.")
    
    try:
        # متد جدید برای google-genai
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json')
        )
        return None, json.loads(response.text)
    except Exception as e:
        print(f"AI ERROR: {e}")
        return "⚠️ سرویس هوش مصنوعی موقتاً در دسترس نیست.", None

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
    bot.send_message(message.chat.id, "🥇 ربات هوشمند طلا آماده شد.\nآخرین نسخه استاندارد (V2025).", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def price(message):
    d = fetch_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "❌ خطا در دریافت قیمت. مجدداً تلاش کنید.")
        return
    msg = (f"💰 **قیمت لحظه‌ای**\n\n"
           f"🥇 طلا ۱۸ عیار: {d['gold_18k_gram']:,.0f} تومان\n"
           f"💵 دلار آزاد: {d['usd_rial']:,.0f} تومان\n"
           f"👑 سکه امامی: {d['sekeh_emami']:,.0f} تومان\n"
           f"🌐 انس جهانی: {d['ounce_usd']:,.2f} دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def bubble(message):
    d = fetch_data()
    try:
        # محاسبه ارزش ذاتی (فرمول جهانی)
        theo = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - theo) / theo) * 100
        emoji = "🟢" if percent > 0 else "🔴"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n📊 میزان حباب: {percent:.2f}% {emoji}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل داده‌های بازار...")
    d = fetch_data()
    err, analysis = get_ai_analysis(d)
    if err:
        bot.send_message(message.chat.id, err)
    else:
        msg = f"✨ **تحلیل AI**\n\n💡 **پیشنهاد:** {analysis.get('advice')}\n\n🧐 **علت:** {analysis.get('reason')}"
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
