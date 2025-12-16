import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import jdatetime # ⬅️ اضافه شده برای تاریخ شمسی
import matplotlib.pyplot as plt
from matplotlib import rcParams
from pydantic import BaseModel, Field
from typing import List

# 🚀 ابزارهای Gemini
import google.genai as genai 
from google.genai import types 

# ----------------------------------------
#           *** ۱. تنظیمات عمومی و API ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")

# 🚨 پورت ۳۰۰۰ لیارا
PORT = int(os.environ.get('PORT', 3000))
WEBHOOK_URL_PATH = f"/{TOKEN}" 
server = Flask(__name__)

DATA_FOLDER = "/app/data" 
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER, exist_ok=True)

if not TOKEN or not WEBHOOK_URL_BASE:
    print("خطا: BOT_TOKEN یا WEBHOOK_URL تنظیم نشده‌اند.")
    exit()

bot = telebot.TeleBot(TOKEN)
# تنظیمات فونت فارسی
rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False 

# --- Gemini Client ---
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini Client initialized successfully for market analysis.")
    except Exception as e:
        print(f"Error initializing Gemini Client: {e}")

# ----------------------------------------
#           *** ۲. واکشی داده‌ها (Scraping Tgju.org) ***
# ----------------------------------------

def clean_and_convert(price_text, is_float=False, is_rial_price=False):
    """پاکسازی متن قیمت از کاما و ریال و تبدیل به عدد صحیح/تومان."""
    if not price_text: return 0
    cleaned_text = price_text.replace(',', '').replace('ریال', '').replace('تومان', '').strip()
    try:
        if is_float:
            return float(cleaned_text)
        else:
            value = int(float(cleaned_text))
            if is_rial_price:
                # 🚨 تبدیل از ریال به تومان (تقسیم بر 10)
                return value // 10
            return value
    except ValueError:
        return 0

def fetch_gold_data():
    """واکشی داده‌های لحظه‌ای طلا، سکه، و دلار با Scraping از Tgju.org."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get("https://www.tgju.org/", headers=headers, timeout=10)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. استخراج قیمت‌های کلیدی
        # برای جلوگیری از خطا در صورت تغییر ساختار، از find استفاده می کنیم
        price_18k_element = soup.find('span', {'id': 'l-geram18'})
        price_18k_text = price_18k_element.text if price_18k_element else None
        
        price_sekeh_element = soup.find('span', {'id': 'l-sekee'})
        price_sekeh_text = price_sekeh_element.text if price_sekeh_element else None
        
        price_usd_element = soup.find('span', {'id': 'l-price_dollar_rl'})
        price_usd_text = price_usd_element.text if price_usd_element else None
        
        price_ounce_element = soup.find('span', {'id': 'l-ons'})
        price_ounce_text = price_ounce_element.text if price_ounce_element else None
        
        data = {
            # ⬅️ نمایش تاریخ و زمان به شمسی
            "time": jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M"), 
            
            # 🚨 قیمت‌های داخلی (ریال) به تومان تبدیل می‌شوند
            "gold_18k_gram": clean_and_convert(price_18k_text, is_rial_price=True), 
            "sekeh_emami": clean_and_convert(price_sekeh_text, is_rial_price=True), 
            "usd_rial": clean_and_convert(price_usd_text, is_rial_price=True),      
            
            # 🚨 انس جهانی به دلار است و نباید تبدیل شود
            "ounce_usd": clean_and_convert(price_ounce_text, is_float=True, is_rial_price=False), 
            
            # برای مقایسه هفتگی/روزانه (فعلا Mock شده‌اند، نیاز به پیاده‌سازی تاریخچه است)
            "yesterday_18k": clean_and_convert(price_18k_text, is_rial_price=True), 
            "week_ago_18k": clean_and_convert(price_18k_text, is_rial_price=True),
        }
        
        print(f"✅ Scraping successful: 18K Gold Price: {data['gold_18k_gram']} Toman")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network/Request Error during Scraping: {e}")
        return None
    except Exception as e:
        print(f"❌ Scraping/Parsing Error: {e}")
        return None

def calculate_bubble(data):
    """محاسبه حباب طلای ۱۸ عیار بر اساس فرمول تئوریک."""
    if not data: return None
    gold_18k_now = data.get("gold_18k_gram", 0)
    usd_rial_now = data.get("usd_rial", 0) # این قیمت دلار اکنون به تومان است
    ounce_usd_now = data.get("ounce_usd", 0)

    # 🚨 اصلاح فرمول: اگر usd_rial_now به تومان است، باید دوباره در 10 ضرب شود 
    # تا به ریال برگردد یا مستقیماً از داده‌های سایت (بدون تقسیم بر 10) استفاده شود.
    # اما چون ما قیمت نهایی تومان را نمایش می‌دهیم، در اینجا باید از نرخ ریالی استفاده شود
    # برای جلوگیری از پیچیدگی، فرض می‌کنیم USD_RIAL_NOW قیمت دلار به ریال است که از سایت گرفته شده.
    # برای استفاده در محاسبات تئوریک (که بر پایه ریال است) باید قیمت تومانی دلار * 10 شود
    usd_rial_for_calc = usd_rial_now * 10 
    
    if ounce_usd_now > 0 and usd_rial_for_calc > 0:
        # قیمت تئوریک هر گرم طلای ۱۸ عیار
        theoretical_gold_18k_rial = (ounce_usd_now * usd_rial_for_calc * 0.75) / 31.1035 
        # تبدیل به تومان
        theoretical_gold_18k_toman = theoretical_gold_18k_rial // 10
    else:
        theoretical_gold_18k_toman = 0
        
    bubble_18k_amount = gold_18k_now - theoretical_gold_18k_toman
    if theoretical_gold_18k_toman > 0:
        bubble_18k_percent = (bubble_18k_amount / theoretical_gold_18k_toman) * 100
    else:
        bubble_18k_percent = 0

    return {
        "gold_18k_price": gold_18k_now,
        "theoretical_18k_price": int(theoretical_gold_18k_toman),
        "bubble_18k_percent": bubble_18k_percent,
    }

def format_comparison(now, past, name):
    """مقایسه قیمت فعلی با قیمت گذشته."""
    diff = now - past
    percent = (diff / past) * 100 if past else 0
    
    if diff > 0:
        indicator = "🔺"
        trend = f"افزایش {percent:.2f}%"
    elif diff < 0:
        indicator = "🔻"
        trend = f"کاهش {abs(percent):.2f}%"
    else:
        indicator = "➖"
        trend = "بدون تغییر"
        
    # 🚨 نمایش همه قیمت‌ها به تومان است
    return f"**{name}**: {now:,.0f} تومان {indicator} ({trend})"


# ----------------------------------------
#           *** ۳. Agent تحلیل بازار (Gemini) ***
# ----------------------------------------

# 🌟 اسکیما برای تضمین خروجی Agent
class AnalysisSchema(BaseModel):
    summary: str = Field(description="خلاصه وضعیت فعلی بازار طلا (صعودی، نزولی یا خنثی).")
    advice: str = Field(description="مشاوره نهایی: 'خرید', 'فروش', یا 'صبر و تماشا'.")
    reason: str = Field(description="دلیل اصلی مشاوره (بر اساس نرخ دلار، انس و حباب).")

MARKET_ANALYSIS_PROMPT = """
شما یک مشاور سرمایه‌گذاری هستید که در بازار طلای ایران تخصص دارید.
داده‌های قیمت لحظه‌ای طلا، سکه، نرخ دلار (به تومان)، نرخ انس جهانی، و حباب محاسبه شده به شما داده می‌شود.
تحلیل شما باید شامل پیش‌بینی نوسان‌گیری (اصلاح قیمت) باشد.
خروجی باید منحصراً یک JSON باشد که دقیقاً با Schema زیر مطابقت داشته باشد. از اضافه کردن هرگونه مقدمه یا توضیح خارج از JSON خودداری کنید.

داده‌های بازار:
{market_data}
"""

def get_market_analysis(market_data):
    """تحلیل هوشمند بازار با Gemini."""
    if not gemini_client:
        return "⚠️ Agent AI غیرفعال است (GEMINI_API_KEY تنظیم نشده).", None

    prompt_with_data = MARKET_ANALYSIS_PROMPT.format(market_data=json.dumps(market_data, indent=2))
    
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[prompt_with_data],
            config=types.GenerateContentConfig( 
                system_instruction="شما یک مشاور سرمایه‌گذاری با دقت بالا هستید.",
                response_mime_type="application/json",
                response_schema=AnalysisSchema
            )
        )
        
        # مقاوم‌سازی JSON
        raw_json_text = response.text.strip()
        if raw_json_text.startswith("```json"):
            raw_json_text = raw_json_text[7:]
        if raw_json_text.endswith("```"):
            raw_json_text = raw_json_text[:-3]
        raw_json_text = raw_json_text.strip()
        
        analysis_data = AnalysisSchema.model_validate_json(raw_json_text)
        return None, analysis_data.model_dump()

    except Exception as e:
        print(f"❌ Gemini Market Analysis Error: {e}")
        # لاگ برای تشخیص مشکل Pydantic
        print(f"Raw Gemini Response: {response.text if 'response' in locals() else 'N/A'}")
        return "❌ خطا در تحلیل هوشمند بازار. لطفاً دقایقی دیگر امتحان کنید.", None


# ----------------------------------------
#           *** ۴. Handlers تلگرام ***
# ----------------------------------------

def main_menu():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    buttons = [
        "/price 💰 قیمت لحظه‌ای",
        "/bubble ⚪️ حباب طلا",
        "/advice 🧠 مشاوره بازار", 
    ]
    
    keyboard.row(telegram_types.KeyboardButton(buttons[0]), telegram_types.KeyboardButton(buttons[1]))
    keyboard.row(telegram_types.KeyboardButton(buttons[2]))
    return keyboard


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = main_menu()
    bot.send_message(message.chat.id, "سلام! به ربات تحلیلگر طلا و ارز خوش آمدید.\n"
                                     "از دکمه‌های زیر برای دریافت قیمت‌های لحظه‌ای و مشاوره بازار استفاده کنید.", parse_mode='Markdown', reply_markup=keyboard)


@bot.message_handler(commands=['price'])
def show_price(message):
    data = fetch_gold_data()
    if not data or data['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ در حال حاضر امکان واکشی اطلاعات قیمت وجود ندارد یا Scraping با خطا مواجه شده است.", reply_markup=main_menu())
        return

    report = f"🟡 **قیمت‌های لحظه‌ای طلا و ارز** ({data['time']})\n\n"
    
    # 🚨 نمایش قیمت‌ها به تومان
    report += f"**🥇 طلای ۱۸ عیار (هر گرم):** {data['gold_18k_gram']:,.0f} تومان\n"
    report += f"**👑 سکه امامی (طرح جدید):** {data['sekeh_emami']:,.0f} تومان\n"
    report += f"**💵 دلار آمریکا (آزاد):** {data['usd_rial']:,.0f} تومان\n"
    report += f"**🌐 انس جهانی طلا:** {data['ounce_usd']:,.2f} دلار\n\n"
    
    report += "📊 **تحلیل تغییرات طلای ۱۸ عیار:**\n"
    report += format_comparison(data['gold_18k_gram'], data['yesterday_18k'], "مقایسه با دیروز") + "\n"
    report += format_comparison(data['gold_18k_gram'], data['week_ago_18k'], "مقایسه با هفته قبل") + "\n"
    
    bot.send_message(message.chat.id, report, parse_mode='Markdown', reply_markup=main_menu())


@bot.message_handler(commands=['bubble'])
def show_bubble(message):
    data = fetch_gold_data()
    if not data or data['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ در حال حاضر امکان واکشی اطلاعات قیمت وجود ندارد.", reply_markup=main_menu())
        return
        
    bubble_data = calculate_bubble(data)
    
    report = "⚪️ **تحلیل حباب طلای ۱۸ عیار**\n\n"
    bubble_percent = bubble_data['bubble_18k_percent']
    
    status = "مثبت 🟢 (بیش از ارزش ذاتی)" if bubble_percent >= 0 else "منفی 🔴 (کمتر از ارزش ذاتی)"
    
    # 🚨 نمایش قیمت‌ها به تومان
    report += f"**🥇 قیمت لحظه‌ای (گرم ۱۸):** {bubble_data['gold_18k_price']:,.0f} تومان\n"
    report += f"**📉 قیمت تئوریک (ارزش ذاتی):** {bubble_data['theoretical_18k_price']:,.0f} تومان\n"
    report += f"**🔥 وضعیت حباب:** **{status}**\n"
    report += f"**⚖️ میزان حباب:** **{abs(bubble_percent):.2f}%**\n\n"
    report += "ℹ️ حباب مثبت نشان‌دهنده تقاضای بیشتر از عرضه داخلی است."
    
    bot.send_message(message.chat.id, report, parse_mode='Markdown', reply_markup=main_menu())


@bot.message_handler(commands=['advice'])
def get_advice(message):
    data = fetch_gold_data()
    if not data or data['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ امکان واکشی داده‌های بازار برای تحلیل وجود ندارد.", reply_markup=main_menu())
        return

    # 1. داده‌ها را برای Agent آماده می‌کنیم (شامل حباب)
    bubble_data = calculate_bubble(data)
    full_market_data = data.copy()
    full_market_data.update(bubble_data)
    
    # 2. فراخوانی Agent
    bot.send_message(message.chat.id, "🧠 در حال تحلیل بازار و ارائه مشاوره هوشمند...", reply_markup=telegram_types.ReplyKeyboardRemove())
    
    error_msg, analysis = get_market_analysis(full_market_data)
    
    if error_msg:
        bot.send_message(message.chat.id, error_msg, reply_markup=main_menu())
        return

    # 3. نمایش نتیجه تحلیل
    advice_report = f"✨ **مشاوره هوشمند بازار طلا**\n\n"
    
    advice_report += f"**خلاصه وضعیت:** {analysis['summary']}\n\n"
    
    # تنظیم رنگ پیشنهاد نوسان‌گیری
    advice_text = analysis['advice'].lower()
    if 'خرید' in advice_text:
        indicator = "✅"
    elif 'فروش' in advice_text:
        indicator = "🛑"
    else:
        indicator = "🟡"
         
    advice_report += f"**{indicator} پیشنهاد نوسان‌گیری:** **{analysis['advice']}**\n"
    advice_report += f"**دلیل تحلیل:** {analysis['reason']}\n\n"
    advice_report += "⚠️ این تحلیل بر اساس داده‌های لحظه‌ای و مدل AI است و مسئولیت تصمیم نهایی با شماست."

    bot.send_message(message.chat.id, advice_report, parse_mode='Markdown', reply_markup=main_menu())

# ----------------------------------------
#           *** ۵. اجرای ربات در لیارا (Webhook) ***
# ----------------------------------------

@server.route(WEBHOOK_URL_PATH, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telegram_types.Update.de_json(json_string) 
        
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 400

if __name__ == '__main__':
    
    try:
        # تنظیم وب‌هوک
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
        print(f"✅ ربات در حالت Webhook شروع به کار کرد روی پورت {PORT}...")
        
        server.run(host="0.0.0.0", port=PORT)
        
    except Exception as e:
        print(f"❌ خطای راه‌اندازی ربات: {e}")
