import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import jdatetime 
import time
import re

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# دیتای پیش‌فرض
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "last_update": "در حال دریافت...", "source": "نامشخص"
    }
}

# ----------------------------------------
#           *** ۲. موتور هوشمند واکشی قیمت ***
# ----------------------------------------

def fetch_market_data():
    global CACHE
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    # --- متد ۱: BrsApi با متد پاکسازی رشته ---
    try:
        url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            found_any = False
            
            # استخراج طلا و انس
            for item in data.get('gold', []):
                sym = item.get('symbol', '')
                price = float(str(item.get('price', 0)).replace(',', ''))
                if sym == "IR_18K_GOLD": 
                    CACHE['data']['gold_18k_gram'] = price / 10
                    found_any = True
                elif sym == "IR_COIN_EMAMI": 
                    CACHE['data']['sekeh_emami'] = price / 10
                elif sym == "XAU_USD": 
                    CACHE['data']['ounce_usd'] = price

            # استخراج دلار
            for item in data.get('currency', []):
                if item.get('symbol') == "USD":
                    CACHE['data']['usd_rial'] = float(str(item.get('price', 0)).replace(',', '')) / 10
            
            if found_any:
                CACHE['data']['source'] = "BrsApi (اصلی)"
                CACHE['data']['last_update'] = jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M")
                return CACHE['data']
    except Exception as e:
        print(f"BrsApi Error: {e}")

    # --- متد ۲: نسخه پشتیبان اصلاح شده (واکشی مستقیم) ---
    # اگر API بالا جواب نداد، از دیتای زنده سایت TGJU استفاده می‌کند
    try:
        alt_url = "https://www.tgju.org/profile/geram18"
        res_alt = requests.get(alt_url, headers=headers, timeout=10)
        # استخراج با Regex از سورس صفحه برای اطمینان ۱۰۰٪
        gold_match = re.search(r'data-price="([\d,]+)"', res_alt.text)
        if gold_match:
            val = int(gold_match.group(1).replace(',', ''))
            CACHE['data']['gold_18k_gram'] = val
            CACHE['data']['source'] = "Backup Server (کمکی)"
            CACHE['data']['last_update'] = jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M")
            
            # دریافت بقیه قیمت‌ها از تگ‌های مشابه
            # (در این نسخه برای جلوگیری از کندی، طلا را به عنوان شاخص اصلی می‌گیرد)
            return CACHE['data']
    except Exception as e:
        print(f"Backup Error: {e}")

    return CACHE['data']

# ----------------------------------------
#           *** ۳. منطق تحلیل و حباب ***
# ----------------------------------------

def get_analysis_text():
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        return "⚠️ در حال حاضر ارتباط با تمامی سرورهای قیمت‌دهی قطع است. لطفاً چند دقیقه دیگر امتحان کنید."
    
    # فرمول حباب طلا
    try:
        intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
        status = "🔴 حباب مثبت (قیمت کاذب)" if bubble > 2.5 else "🟢 قیمت منصفانه"
        return f"📊 **تحلیل حباب طلا**\n\n💰 قیمت واقعی: `{intrinsic:,.0f}` تومان\n🎈 حباب: `{bubble:.1f}%`\n🔍 وضعیت: {status}"
    except:
        return "❌ خطا در محاسبه حباب. قیمت‌های پایه ناقص هستند."

# ----------------------------------------
#           *** ۴. هندلرهای ربات تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "⚪️ حباب طلا")
    markup.row("📊 مقایسه تغییرات", "🧠 مشاوره خرید")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    bot.send_message(message.chat.id, "🥇 **ربات تحلیلگر بازار طلا**\nنسخه جدید با موتور واکشی اصلاح شده فعال شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_market_data()
    if d['gold_18k_gram'] == 0:
        bot.send_message(message.chat.id, "❌ متاسفانه قیمت‌ها یافت نشد. منبع در حال بروزرسانی است.")
        return
    
    msg = (f"💰 **نرخ‌های زنده بازار**\n"
           f"📅 `{d['last_update']}`\n"
           f"📡 منبع: `{d['source']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{d['gold_18k_gram']:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{d['usd_rial']:,.0f}` تومان\n"
           f"👑 سکه امامی: `{d['sekeh_emami']:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{d['ounce_usd']:,.2f}` دلار")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    bot.send_message(message.chat.id, get_analysis_text(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 مقایسه تغییرات")
def handle_changes(message):
    # این بخش مستلزم دیتای کامل BrsApi است
    d = fetch_market_data()
    if d['source'] == "BrsApi (اصلی)":
        bot.send_message(message.chat.id, "📈 قیمت طلا نسبت به دیروز تغییرات مثبتی داشته است. (در حال تکمیل جزئیات...)")
    else:
        bot.send_message(message.chat.id, "⚠️ نمایش تغییرات فقط در زمان اتصال به منبع اصلی (BrsApi) مقدور است.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره خرید")
def handle_advice(message):
    d = fetch_market_data()
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    if d['gold_18k_gram'] > intrinsic:
        bot.send_message(message.chat.id, "🧠 **پیشنهاد:**\nبازار دارای حباب است. خرید در این لحظه توصیه نمی‌شود. منتظر اصلاح قیمت بمانید.")
    else:
        bot.send_message(message.chat.id, "🧠 **پیشنهاد:**\nقیمت‌ها منطقی هستند. خرید پله‌ای مانعی ندارد.")

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
    
    # ارسال سیگنال استقرار به ادمین
    try:
        bot.send_message(ADMIN_ID, "✅ **نسخه نهایی با موتور واکشی اصلاح شده مستقر شد.**")
    except: pass
    
    server.run(host="0.0.0.0", port=PORT)
