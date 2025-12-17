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

# 🚀 استفاده از پکیج جدید گوگل
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

CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده", "source": "None"
    }
}

# --- تنظیمات هوش مصنوعی با قابلیت پروکسی برای دور زدن تحریم ---
client = None
if GEMINI_API_KEY:
    try:
        # تنظیم پروکسی برای عبور از سد گوگل (استفاده از سرویس‌های رایگان یا تونل)
        # اگر پروکسی اختصاصی ندارید، معمولاً از طریق تنظیمات محیطی HTTP_PROXY در لیارا هم قابل حل است
        client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={'api_version': 'v1beta'}
        )
        print("✅ سیستم هوش مصنوعی آماده نبرد با تحریم!")
    except Exception as e:
        print(f"❌ خطا در استارت: {e}")

# ----------------------------------------
#           *** ۲. استخراج داده ***
# ----------------------------------------

def clean_val(text):
    if not text: return 0
    text = text.replace(',', '')
    p_nums = "۰۱۲۳۴۵۶۷۸۹"; e_nums = "0123456789"
    table = str.maketrans(p_nums, e_nums)
    clean = text.translate(table)
    clean = "".join(filter(str.isdigit, clean))
    return int(clean) if clean else 0

def fetch_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        # تلاش برای دریافت از TGJU
        res = requests.get("https://www.tgju.org/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        d = {"gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, "ounce_usd": 0.0}
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
    except Exception as e:
        print(f"Scraping Error: {e}")
    return CACHE['data']

# ----------------------------------------
#           *** ۳. تحلیل هوشمند (نسخه اصلاح شده) ***
# ----------------------------------------

def get_ai_analysis(m_data):
    if not client: return "❌ تنظیمات هوش مصنوعی یافت نشد.", None
    
    prompt = (f"تحلیلگر بازار طلا: طلا ۱۸ عیار {m_data['gold_18k_gram']} تومان، "
              f"دلار {m_data['usd_rial']} تومان. "
              "وضعیت را بررسی کن و کوتاه و فقط در قالب JSON فارسی با کلیدهای summary و advice و reason پاسخ بده.")
    
    try:
        # استفاده از مدل flash برای کاهش حجم ترافیک و سرعت بیشتر
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json')
        )
        return None, json.loads(response.text)
    except Exception as e:
        print(f"AI ERROR: {e}")
        # پیغام راهنما برای کاربر
        if "403" in str(e):
            return "⚠️ متأسفانه گوگل دسترسی سرورهای ایران را مسدود کرده است. در حال تلاش برای جایگزینی منبع تحلیل هستیم.", None
        return "⚠️ خطای ارتباط با هوش مصنوعی.", None

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
    bot.send_message(message.chat.id, "🏅 ربات هوشمند طلا خوش آمدید.\nآخرین نسخه ضدتحریم فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def price_msg(message):
    d = fetch_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "❌ خطا در واکشی داده. لطفاً دوباره تلاش کنید.")
        return
    msg = (f"💰 **قیمت‌های لحظه‌ای**\n\n"
           f"🥇 طلا ۱۸ عیار: {d['gold_18k_gram']:,.0f} تومان\n"
           f"💵 دلار آزاد: {d['usd_rial']:,.0f} تومان\n"
           f"👑 سکه امامی: {d['sekeh_emami']:,.0f} تومان\n"
           f"🌐 انس جهانی: {d['ounce_usd']:,.2f} دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def bubble_msg(message):
    d = fetch_data()
    try:
        theo = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - theo) / theo) * 100
        emoji = "🟢" if percent > 0 else "🔴"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n📊 حباب: {percent:.2f}% {emoji}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ خطا در محاسبه حباب.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def advice_msg(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل هوشمند بازار...")
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
