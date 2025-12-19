import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import jdatetime 
import time

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
# کلید شما (چه رایگان باشد چه پرو، این کد با هر دو سازگار است)
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه موقت (RAM Cache) - جایگزین فایل data.json
MARKET_DATA = {
    "gold": {}, 
    "currency": {},
    "update_time": "به‌روزرسانی نشده"
}

# ----------------------------------------
#           *** ۲. موتور واکشی دیتای حرفه‌ای ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    # استفاده از آدرس نسخه Pro طبق درخواست شما برای دقت بالاتر
    url = f"https://brsapi.ir/Api/Market/Gold_Currency_Pro.php?key={BRS_TOKEN}&section=gold,currency"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            
            # استخراج و دسته‌بندی دیتا در حافظه موقت
            if 'gold' in res_json:
                MARKET_DATA["gold"] = {item.get('symbol'): item for item in res_json.get('gold', [])}
            
            if 'currency' in res_json:
                MARKET_DATA["currency"] = {item.get('symbol'): item for item in res_json.get('currency', [])}
            
            MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return True
    except Exception as e:
        print(f"Fetch Error: {e}")
    return False

def extract_price(item):
    """جستجوی هوشمند قیمت در فیلدهای مختلف نسخه رایگان و Pro"""
    if not item: return 0
    # چک کردن تمام نام‌های احتمالی فیلد قیمت در دیتای BrsApi
    for key in ['price', 'last_price', 'current_price', 'value']:
        val = item.get(key)
        if val:
            try:
                # حذف کاما و تبدیل به عدد اعشاری
                return float(str(val).replace(',', ''))
            except:
                continue
    return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات و مقایسه")
    markup.row("⚪️ حباب طلا", "🧠 مشاوره خرید")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    bot.send_message(
        message.chat.id, 
        "✅ **ربات تحلیلگر بازار (نسخه حرفه‌ای) فعال شد.**\nداده‌ها مستقیماً از BrsApi واکشی می‌شوند و نیازی به ذخیره محلی ندارند.", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    
    # واکشی قیمت‌ها با متد جدید و امن
    p_gold = extract_price(MARKET_DATA["gold"].get("IR_18K_GOLD")) / 10
    p_usd = extract_price(MARKET_DATA["currency"].get("USD")) / 10
    p_sekeh = extract_price(MARKET_DATA["gold"].get("IR_COIN_EMAMI")) / 10
    p_ons = extract_price(MARKET_DATA["gold"].get("XAU_USD"))

    if p_gold == 0:
        bot.reply_to(message, "⚠️ منبع BrsApi پاسخی نداد یا لیست قیمت‌ها خالی است. لطفاً ۳۰ ثانیه دیگر تلاش کنید.")
        return

    msg = (f"💰 **آخرین نرخ‌های بازار**\n"
           f"📅 `{jdatetime.datetime.now().strftime('%Y/%m/%d')}` | ⏰ `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n"
           f"👑 سکه امامی: `{p_sekeh:,.0f}` تومان\n"
           f"💵 دلار آمریکا: `{p_usd:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات و مقایسه")
def handle_changes(message):
    sync_market_data()
    g = MARKET_DATA["gold"].get("IR_18K_GOLD", {})
    
    pct = g.get('change_percent', '0')
    change_val = extract_price(g) * (float(str(pct).replace('%','')) / 100) / 10
    status = "📈 افزایش" if float(str(pct).replace('%','')) >= 0 else "📉 کاهش"
    
    msg = (f"📊 **تحلیل تغییرات روزانه طلا**\n\n"
           f"وضعیت بازار: {status}\n"
           f"میزان تغییر: `{abs(change_val):,.0f}` تومان\n"
           f"درصد تغییر: `{pct}` نسبت به روز گذشته")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = extract_price(MARKET_DATA["gold"].get("IR_18K_GOLD")) / 10
    p_usd = extract_price(MARKET_DATA["currency"].get("USD")) / 10
    p_ons = extract_price(MARKET_DATA["gold"].get("XAU_USD"))
    
    if p_gold > 0 and p_usd > 0:
        # فرمول: (انس * دلار * 0.75) / 31.1035 / 10 (تبدیل ریال به تومان)
        intrinsic = (p_ons * (p_usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n💰 ارزش واقعی: `{intrinsic:,.0f}` تومان\n🎈 میزان حباب: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ دیتا برای محاسبه حباب کافی نیست.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره خرید")
def handle_advice(message):
    bot.send_message(message.chat.id, "🧠 **توصیه تحلیلگر:**\nدر بازار طلا، حباب زیر ۲٪ فرصت خرید و حباب بالای ۴٪ ریسک فروش محسوب می‌شود.")

# ----------------------------------------
#           *** ۴. اجرای سرور و وب‌هوک ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return "Bot is Running smoothly!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    
    try:
        bot.send_message(ADMIN_ID, "✅ **ربات با متد Pro و بدون نیاز به فایل مستقر شد.**")
    except: pass
    
    server.run(host="0.0.0.0", port=PORT)
