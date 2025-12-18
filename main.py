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

# استفاده از پکیج جدید گوگل
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

# --- تنظیمات هوش مصنوعی (بهینه شده برای سرور خارج) ---
client = None
if GEMINI_API_KEY:
    try:
        # استفاده از تنظیمات پیش‌فرض برای سرور آلمان
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ اتصال هوش مصنوعی در سرور آلمان برقرار شد.")
    except Exception as e:
        print(f"❌ خطا در پیکربندی: {e}")

# ----------------------------------------
#           *** ۲. استخراج داده (متد جدید و مقاوم) ***
# ----------------------------------------

def clean_val(text):
    if not text: return 0
    # حذف تمام کاراکترهای غیر عددی بجای جایگزینی تک‌تک
    clean = "".join(re.findall(r'\d+', text.replace(',', '')))
    # تبدیل اعداد فارسی/عربی به انگلیسی
    p_nums = "۰۱۲۳۴۵۶۷۸۹"; e_nums = "0123456789"
    table = str.maketrans(p_nums, e_nums)
    clean = clean.translate(table)
    return int(clean) if clean else 0

def fetch_market_data():
    """استخراج قیمت با چندین متد برای جلوگیری از Scraping Error"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    d = {"gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, "ounce_usd": 0.0}
    
    try:
        # منبع ۱: TGJU (تلاش با انتخابگرهای دقیق‌تر)
        res = requests.get("https://www.tgju.org/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        targets = {
            "geram18": "gold_18k_gram",
            "sekeh": "sekeh_emami",
            "price_dollar_rl": "usd_rial",
            "ons": "ounce_usd"
        }
        
        for row_id, field in targets.items():
            row = soup.find('tr', {'data-market-row': row_id})
            if row:
                price_cell = row.find('td', {'class': 'info-price'}) or row.find('td', {'class': 'info-last'})
                if price_cell:
                    val = price_cell.get_text(strip=True)
                    if field == "ounce_usd":
                        try: d[field] = float(val.replace(',', ''))
                        except: pass
                    else:
                        d[field] = clean_val(val)
    except Exception as e:
        print(f"TGJU Fetch Error: {e}")

    # منبع کمکی اگر منبع اول ناقص بود
    if d['gold_18k_gram'] == 0:
        try:
            res_backup = requests.get("https://www.tala.ir/price/gold", headers=headers, timeout=10)
            soup_b = BeautifulSoup(res_backup.text, 'html.parser')
            text = soup_b.get_text()
            # استفاده از Regex برای استخراج از متن
            gold_price = re.search(r'۱۸ عیار.*?([\d,]{7,15})', text)
            if gold_price: d['gold_18k_gram'] = clean_val(gold_price.group(1))
            
            usd_price = re.search(r'دلار آزاد.*?([\d,]{5,10})', text)
            if usd_price: d['usd_rial'] = clean_val(usd_price.group(1))
        except: pass

    if d['gold_18k_gram'] > 0:
        d['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
        d['source'] = "Live Market"
        CACHE['data'].update(d)
        return d
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. تحلیل هوشمند ***
# ----------------------------------------

def get_ai_analysis(m_data):
    if not client: return "❌ هوش مصنوعی غیرفعال است.", None
    
    prompt = (f"تحلیلگر بازار ایران: طلا {m_data['gold_18k_gram']} تومان، "
              f"دلار {m_data['usd_rial']} تومان. "
              "یک تحلیل کوتاه فارسی در قالب JSON (summary, advice, reason) بده.")
    
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json')
        )
        return None, json.loads(response.text)
    except Exception as e:
        print(f"AI ERROR: {e}")
        # اگر در آلمان هم 403 داد، یعنی آی‌پی دیتاسنتر توسط گوگل بلاک شده
        if "403" in str(e):
            return "⚠️ گوگل دسترسی دیتاسنترهای آلمان را محدود کرده است. لطفاً از مدل‌های جایگزین استفاده کنید.", None
        return f"⚠️ خطای تحلیل: {str(e)[:50]}", None

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
    bot.send_message(message.chat.id, "🥇 ربات هوشمند قیمت طلا (نسخه سرور آلمان)\nآماده خدمت‌رسانی هستم.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ خطا در دریافت قیمت. دقایقی دیگر تلاش کنید.")
        return
    
    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"🥇 طلا ۱۸ عیار: {d['gold_18k_gram']:,.0f} تومان\n"
           f"💵 دلار آزاد: {d['usd_rial']:,.0f} تومان\n"
           f"👑 سکه امامی: {d['sekeh_emami']:,.0f} تومان\n"
           f"🌐 انس جهانی: {d['ounce_usd']:,.2f} دلار\n\n"
           f"⏰ بروزرسانی: {d['time']}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_market_data()
    try:
        theo = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - theo) / theo) * 100
        status = "🔴 حباب مثبت (گران)" if percent > 0 else "🟢 حباب منفی (ارزان)"
        msg = (f"⚪️ **تحلیل حباب طلا**\n\n"
               f"📊 درصد حباب: {percent:.2f}%\n"
               f"🔍 وضعیت: {status}")
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ محاسبه حباب امکان‌پذیر نیست.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال تحلیل هوشمند داده‌های بازار...")
    d = fetch_market_data()
    err, analysis = get_ai_analysis(d)
    if err:
        bot.send_message(message.chat.id, err)
    else:
        msg = f"✨ **تحلیل اختصاصی AI**\n\n📝 {analysis.get('summary')}\n\n💡 **پیشنهاد:** {analysis.get('advice')}\n\n🧐 **علت:** {analysis.get('reason')}"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۵. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telegram_types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 400

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
