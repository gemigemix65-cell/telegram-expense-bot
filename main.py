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
from openai import OpenAI # DeepSeek از کتابخانه OpenAI استفاده می‌کند

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") 
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

# --- تنظیمات هوش مصنوعی DeepSeek ---
ai_client = None
if DEEPSEEK_API_KEY:
    try:
        ai_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        print("✅ هوش مصنوعی DeepSeek فعال شد.")
    except Exception as e:
        print(f"❌ خطا در اتصال به DeepSeek: {e}")

# ----------------------------------------
#           *** ۲. استخراج داده (متد کاملاً جدید) ***
# ----------------------------------------

def fetch_market_data():
    """استخراج مستقیم و ساده برای جلوگیری از خطای NoneType"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0'}
    d = {"gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, "ounce_usd": 0.0}
    
    try:
        # استفاده از سایت Nobitex یا منابع مشابه برای نرخ تتر/دلار اگر TGJU بسته بود
        # اما فعلاً تلاش مجدد روی ساختار متنی TGJU
        res = requests.get("https://www.tgju.org/", headers=headers, timeout=10)
        content = res.text
        
        # استخراج با Regex (بسیار مقاوم‌تر از BeautifulSoup در برابر تغییر ساختار)
        gold = re.search(r'data-market-row="geram18".*?class="info-price">(.*?)<', content, re.DOTALL)
        usd = re.search(r'data-market-row="price_dollar_rl".*?class="info-price">(.*?)<', content, re.DOTALL)
        sekeh = re.search(r'data-market-row="sekeh".*?class="info-price">(.*?)<', content, re.DOTALL)
        ons = re.search(r'data-market-row="ons".*?class="info-price">(.*?)<', content, re.DOTALL)

        if gold: d['gold_18k_gram'] = int(re.sub(r'\D', '', gold.group(1)))
        if usd: d['usd_rial'] = int(re.sub(r'\D', '', usd.group(1)))
        if sekeh: d['sekeh_emami'] = int(re.sub(r'\D', '', sekeh.group(1)))
        if ons: d['ounce_usd'] = float(ons.group(1).replace(',', ''))
        
        if d['gold_18k_gram'] > 0:
            d['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            CACHE['data'].update(d)
            return d
    except Exception as e:
        print(f"Fetch Error: {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. تحلیل هوشمند با DeepSeek ***
# ----------------------------------------

def get_ai_analysis(m_data):
    if not ai_client: return "❌ کلید DeepSeek ست نشده است.", None
    
    prompt = (f"تحلیلگر بازار ایران هستی. قیمت طلا {m_data['gold_18k_gram']} و دلار {m_data['usd_rial']}. "
              "یک تحلیل کوتاه فارسی به صورت JSON با کلیدهای summary, advice, reason بده.")
    
    try:
        response = ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={'type': 'json_object'}
        )
        return None, json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"DeepSeek Error: {e}")
        return f"⚠️ خطای هوش مصنوعی: {str(e)[:50]}", None

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
    bot.send_message(message.chat.id, "🏅 ربات هوشمند با موتور DeepSeek فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ منبع قیمت موقتاً در دسترس نیست.")
        return
    msg = (f"💰 **قیمت لحظه‌ای**\n\n"
           f"🥇 طلا ۱۸ عیار: {d['gold_18k_gram']:,.0f}\n"
           f"💵 دلار آزاد: {d['usd_rial']:,.0f}\n"
           f"👑 سکه امامی: {d['sekeh_emami']:,.0f}\n"
           f"🌐 انس جهانی: {d['ounce_usd']:,.2f}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال استعلام از DeepSeek...")
    d = fetch_market_data()
    err, analysis = get_ai_analysis(d)
    if err: bot.send_message(message.chat.id, err)
    else:
        msg = f"✨ **تحلیل هوش مصنوعی**\n\n📝 {analysis.get('summary')}\n\n💡 **پیشنهاد:** {analysis.get('advice')}"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
