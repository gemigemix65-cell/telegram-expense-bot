import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
from bs4 import BeautifulSoup
import jdatetime 
from pydantic import BaseModel, Field
from typing import List
import matplotlib.pyplot as plt
from matplotlib import rcParams

# 🚀 ابزارهای Gemini
import google.genai as genai 
from google.genai import types 

# ----------------------------------------
#           *** ۱. تنظیمات عمومی و API ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")

# پورت ۳۰۰۰ مخصوص لیارا
PORT = int(os.environ.get('PORT', 3000))
WEBHOOK_URL_PATH = f"/{TOKEN}" 
server = Flask(__name__)

if not TOKEN or not WEBHOOK_URL_BASE:
    print("خطا: BOT_TOKEN یا WEBHOOK_URL تنظیم نشده‌اند.")
    exit()

bot = telebot.TeleBot(TOKEN)

# تنظیمات فونت برای نمودارها (در صورت استفاده)
rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False 

# --- Gemini Client ---
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini Client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Gemini: {e}")

# ----------------------------------------
#           *** ۲. توابع کمکی واکشی داده ***
# ----------------------------------------

def clean_and_convert(price_text):
    """پاکسازی کامل متن، تبدیل اعداد فارسی به انگلیسی و استخراج عدد (تومان)."""
    if not price_text: return 0
    
    # نگاشت اعداد فارسی به انگلیسی
    persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
    english_numbers = "0123456789"
    translation_table = str.maketrans(persian_numbers, english_numbers)
    
    cleaned = price_text.translate(translation_table)
    # حذف هر چیزی که عدد نیست
    cleaned = "".join(filter(str.isdigit, cleaned))
    
    try:
        return int(cleaned)
    except ValueError:
        return 0

def fetch_gold_data():
    """واکشی داده‌ها با جستجوی هوشمند در جدول سایت ایران‌جیب."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # آدرس بخش قیمت‌های لحظه‌ای ایران‌جیب
        url = "https://www.iranjib.ir/showgroup/23/realtime_price/"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        data_map = {}

        # بررسی تمام سطرهای جدول (tr)
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                name = cells[0].text.strip()
                price = cells[1].text.strip()
                
                # جستجوی هوشمند بر اساس کلمات کلیدی (فارسی و انگلیسی)
                if "18 عیار" in name or "۱۸ عیار" in name:
                    data_map['gold_18k_gram'] = clean_and_convert(price)
                elif "سکه امامی" in name:
                    data_map['sekeh_emami'] = clean_and_convert(price)
                elif "دلار" in name and ("آزاد" in name or "تهران" in name):
                    data_map['usd_rial'] = clean_and_convert(price)
                elif "انس" in name:
                    # استخراج عدد اعشاری برای انس جهانی
                    raw_ounce = price.replace(',', '')
                    try:
                        data_map['ounce_usd'] = float("".join(c for c in raw_ounce if c.isdigit() or c == '.'))
                    except:
                        data_map['ounce_usd'] = 0.0

        # آماده‌سازی خروجی نهایی
        data = {
            "time": jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M"), 
            "gold_18k_gram": data_map.get('gold_18k_gram', 0), 
            "sekeh_emami": data_map.get('sekeh_emami', 0), 
            "usd_rial": data_map.get('usd_rial', 0),      
            "ounce_usd": data_map.get('ounce_usd', 0.0), 
            # مقادیر فرضی برای مقایسه (در نسخه‌های بعد از دیتابیس خوانده شود)
            "yesterday_18k": data_map.get('gold_18k_gram', 0), 
            "week_ago_18k": data_map.get('gold_18k_gram', 0),
        }
        
        print(f"✅ Scraping result -> Gold: {data['gold_18k_gram']} Toman, Dollar: {data['usd_rial']} Toman")
        return data
        
    except Exception as e:
        print(f"❌ Scraping Error: {e}")
        return None

def calculate_bubble(data):
    """محاسبه حباب بر اساس فرمول جهانی."""
    if not data or data.get('gold_18k_gram', 0) == 0: return None
    
    gold_18k_now = data['gold_18k_gram']
    usd_toman = data['usd_rial']
    ounce_usd = data['ounce_usd']
    
    if ounce_usd <= 0 or usd_toman <= 0:
        theoretical_toman = 0
    else:
        # فرمول: (انس * قیمت دلار (ریال) * 0.75) / 31.1035
        theoretical_rial = (ounce_usd * (usd_toman * 10) * 0.75) / 31.1035
        theoretical_toman = theoretical_rial // 10
        
    bubble_amount = gold_18k_now - theoretical_toman
    bubble_percent = (bubble_amount / theoretical_toman * 100) if theoretical_toman > 0 else 0

    return {
        "gold_18k_price": gold_18k_now,
        "theoretical_18k_price": int(theoretical_toman),
        "bubble_18k_percent": bubble_percent,
    }

# ----------------------------------------
#           *** ۳. منطق تحلیل AI ***
# ----------------------------------------

class AnalysisSchema(BaseModel):
    summary: str
    advice: str
    reason: str

def get_market_analysis(market_data):
    """تحلیل هوشمند بازار توسط Gemini."""
    if not gemini_client or market_data['gold_18k_gram'] == 0:
        return "❌ داده کافی برای تحلیل وجود ندارد.", None

    prompt = f"تحلیل وضعیت بازار طلا در ایران بر اساس این داده‌ها:\n{json.dumps(market_data, indent=2)}"
    
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction="شما یک تحلیلگر خبره بازار طلای ایران هستید. پاسخ را به زبان فارسی و در قالب JSON برگردانید.",
                response_mime_type="application/json",
                response_schema=AnalysisSchema
            )
        )
        return None, json.loads(response.text)
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return "❌ خطا در برقراری ارتباط با هوش مصنوعی.", None

# ----------------------------------------
#           *** ۴. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("/price 💰 قیمت لحظه‌ای", "/bubble ⚪️ حباب طلا")
    markup.row("/advice 🧠 مشاوره بازار")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "به ربات تحلیلگر هوشمند طلا خوش آمدید! 🥇", reply_markup=main_menu())

@bot.message_handler(commands=['price'])
def show_price(message):
    data = fetch_gold_data()
    if not data or data['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ خطا در دریافت قیمت. لطفاً کمی بعد امتحان کنید.")
        return
    
    msg = (f"🟡 **قیمت‌های لحظه‌ای** ({data['time']})\n\n"
           f"🔸 **طلای ۱۸ عیار:** {data['gold_18k_gram']:,.0f} تومان\n"
           f"🔸 **سکه امامی:** {data['sekeh_emami']:,.0f} تومان\n"
           f"🔸 **دلار آزاد:** {data['usd_rial']:,.0f} تومان\n"
           f"🔸 **انس جهانی:** {data['ounce_usd']:,.2f} دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['bubble'])
def show_bubble(message):
    data = fetch_gold_data()
    bubble = calculate_bubble(data)
    if not bubble:
        bot.send_message(message.chat.id, "❌ محاسبه حباب در حال حاضر امکان‌پذیر نیست.")
        return
    
    status = "مثبت 🟢" if bubble['bubble_18k_percent'] >= 0 else "منفی 🔴"
    msg = (f"⚪️ **تحلیل حباب طلای ۱۸ عیار**\n\n"
           f"✅ قیمت بازار: {bubble['gold_18k_price']:,.0f}\n"
           f"💎 ارزش ذاتی: {bubble['theoretical_18k_price']:,.0f}\n"
           f"📊 درصد حباب: {bubble['bubble_18k_percent']:.2f}% ({status})")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['advice'])
def show_advice(message):
    data = fetch_gold_data()
    if not data or data['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ داده‌ای برای تحلیل یافت نشد.")
        return
    
    bot.send_message(message.chat.id, "🧠 در حال تحلیل هوشمند بازار... لطفاً شکیبا باشید.")
    
    bubble = calculate_bubble(data)
    data.update(bubble)
    err, analysis = get_market_analysis(data)
    
    if err:
        bot.send_message(message.chat.id, err)
    else:
        res = (f"✨ **تحلیل هوش مصنوعی**\n\n"
               f"📋 **خلاصه:** {analysis['summary']}\n"
               f"💡 **پیشنهاد:** {analysis['advice']}\n"
               f"🔍 **دلیل:** {analysis['reason']}")
        bot.send_message(message.chat.id, res, parse_mode='Markdown')

# ----------------------------------------
#           *** ۵. اجرای سرور ***
# ----------------------------------------

@server.route(WEBHOOK_URL_PATH, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telegram_types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 400

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    print(f"🚀 Bot started on port {PORT}")
    server.run(host="0.0.0.0", port=PORT)
