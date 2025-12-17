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

# تنظیمات فونت برای نمودارها
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
    """پاکسازی متن، تبدیل اعداد فارسی و استخراج عدد صحیح (تومان)."""
    if not price_text: return 0
    persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
    english_numbers = "0123456789"
    translation_table = str.maketrans(persian_numbers, english_numbers)
    cleaned = price_text.translate(translation_table)
    # حذف هر چیزی غیر از عدد
    cleaned = "".join(filter(str.isdigit, cleaned))
    try:
        return int(cleaned)
    except ValueError:
        return 0

def fetch_gold_data():
    """واکشی داده‌ها از سایت Tala.ir."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        # استفاده از صفحه قیمت ۱۸ عیار tala.ir
        url = "https://www.tala.ir/price/18k"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        data_map = {}

        # در سایت tala.ir قیمت‌ها معمولاً در جدول‌هایی با کلاس table قرار دارند
        # یا در ویجت‌های خاص. ما تمام سطرهای جدول را چک می‌کنیم.
        rows = soup.find_all('tr')
        
        for row in rows:
            text = row.text.strip()
            cells = row.find_all('td')
            
            if len(cells) >= 2:
                name = cells[0].text.strip()
                price_val = cells[1].text.strip()
                
                # ۱. طلای ۱۸ عیار
                if "۱۸ عیار" in name or "18 عیار" in name:
                    data_map['gold_18k_gram'] = clean_and_convert(price_val)
                
                # ۲. سکه امامی (معمولاً در سایدبار یا جداول همان صفحه هست)
                elif "سکه امامی" in name:
                    data_map['sekeh_emami'] = clean_and_convert(price_val)
                
                # ۳. دلار آزاد
                elif "دلار" in name and "آزاد" in name:
                    data_map['usd_rial'] = clean_and_convert(price_val)
                
                # ۴. انس جهانی
                elif "انس" in name and "طلا" in name:
                    raw_ounce = price_val.replace(',', '')
                    try:
                        # استخراج عدد اعشاری برای انس
                        data_map['ounce_usd'] = float("".join(c for c in raw_ounce if c.isdigit() or c == '.'))
                    except:
                        data_map['ounce_usd'] = 0.0

        # اگر مقادیر از جداول پیدا نشدند، از کلاس‌های مستقیم (Selectors) استفاده می‌کنیم
        if not data_map.get('gold_18k_gram'):
            # تلاش برای پیدا کردن قیمت در باکس اصلی صفحه ۱۸ عیار
            price_box = soup.select_one(".price") or soup.select_one(".info-price")
            if price_box:
                data_map['gold_18k_gram'] = clean_and_convert(price_box.text)

        # تکمیل مقادیر در صورت مفقود بودن (بعضی مقادیر در tala.ir/price/18k ممکن است نباشند)
        # در این صورت یک درخواست به صفحه اصلی می‌زنیم
        if not data_map.get('usd_rial') or not data_map.get('ounce_usd'):
            home_res = requests.get("https://www.tala.ir/", headers=headers, timeout=10)
            home_soup = BeautifulSoup(home_res.text, 'html.parser')
            for r in home_soup.find_all('tr'):
                c = r.find_all('td')
                if len(c) >= 2:
                    n = c[0].text.strip()
                    p = c[1].text.strip()
                    if "دلار" in n and not data_map.get('usd_rial'):
                        data_map['usd_rial'] = clean_and_convert(p)
                    if "انس" in n and not data_map.get('ounce_usd'):
                        try: data_map['ounce_usd'] = float(p.replace(',', ''))
                        except: pass

        data = {
            "time": jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M"), 
            "gold_18k_gram": data_map.get('gold_18k_gram', 0), 
            "sekeh_emami": data_map.get('sekeh_emami', 0), 
            "usd_rial": data_map.get('usd_rial', 0),      
            "ounce_usd": data_map.get('ounce_usd', 0.0), 
            "yesterday_18k": data_map.get('gold_18k_gram', 0), 
            "week_ago_18k": data_map.get('gold_18k_gram', 0),
        }
        
        print(f"✅ Tala.ir Scraping -> Gold: {data['gold_18k_gram']}, Dollar: {data['usd_rial']}")
        return data
        
    except Exception as e:
        print(f"❌ Scraping Error (Tala.ir): {e}")
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
        # قیمت دلار در tala.ir معمولاً به تومان است، پس برای ریال ضربدر ۱۰ می‌شود
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
            model='gemini-2.0-flash', # از آخرین نسخه پایدار استفاده شد
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
    bot.reply_to(message, "به ربات تحلیلگر هوشمند طلا (منبع: Tala.ir) خوش آمدید! 🥇", reply_markup=main_menu())

@bot.message_handler(commands=['price'])
def show_price(message):
    data = fetch_gold_data()
    if not data or data['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ خطا در واکشی قیمت از Tala.ir. لطفاً لحظاتی دیگر تلاش کنید.")
        return
    
    msg = (f"🟡 **قیمت‌های لحظه‌ای (Tala.ir)**\n"
           f"⏰ {data['time']}\n\n"
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
        bot.send_message(message.chat.id, "❌ محاسبه حباب به دلیل عدم دریافت نرخ دلار یا انس میسر نشد.")
        return
    
    status = "مثبت 🟢" if bubble['bubble_18k_percent'] >= 0 else "منفی 🔴"
    msg = (f"⚪️ **تحلیل حباب طلای ۱۸ عیار**\n\n"
           f"✅ قیمت بازار: {bubble['gold_18k_price']:,.0f} تومان\n"
           f"💎 ارزش ذاتی: {bubble['theoretical_18k_price']:,.0f} تومان\n"
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
    print(f"🚀 Bot started on port {PORT} with source: Tala.ir")
    server.run(host="0.0.0.0", port=PORT)
