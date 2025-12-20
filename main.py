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

VERSION = "1.1.7"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
ADMIN_ID = "8221583925"
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه برای ذخیره دیتای کامل API
MARKET_DATA = {"items": {}, "update_time": "به‌روزرسانی نشده", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        res_json = response.json()
        temp_items = {}
        
        # پیمایش دقیق لیست‌های gold و currency بر اساس JSON ارسالی شما
        for category in ['gold', 'currency']:
            data_list = res_json.get(category, [])
            if isinstance(data_list, list):
                for item in data_list:
                    symbol = item.get('symbol')
                    if symbol:
                        temp_items[symbol] = item
        
        if temp_items:
            MARKET_DATA["items"] = temp_items
            now = jdatetime.datetime.now()
            MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
            MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
            return True, "OK"
        return False, "Data Empty"
    except Exception as e:
        return False, str(e)

def get_p(symbol):
    """استخراج قیمت ایمن از دیتای JSON"""
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        # مدیریت تبدیل عدد و رشته (حذف کاما در صورت وجود)
        clean_price = str(price).replace(',', '')
        return float(clean_price)
    except:
        return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📉 تحلیل تکنیکال")
    markup.row("🧮 ماشین‌حساب", "📅 تقویم اقتصادی")
    markup.row("🧠 تحلیل هوشمند", "📊 نمودار تغییرات")
    markup.row("⚪️ حباب طلا", "🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, error_msg = sync_market_data()
    status = "🟢 آنلاین" if success else f"🔴 خطا: {error_msg}"
    
    welcome_text = (
        f"✨ **دستیار هوشمند بازار مومو**\n"
        f"👤 در خدمت شما هستم\n"
        f"--------------------------\n"
        f"📡 وضعیت اتصال: {status}\n"
        f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
        f"⏰ ساعت: `{MARKET_DATA['update_time']}`"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "❌ خطا در دریافت دیتا از سرور.")
        return

    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}` تومان\n"
           f"💵 دلار آزاد: `{get_p('USD'):,.0f}` تومان\n"
           f"👑 سکه امامی: `{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n"
           f"🌐 انس جهانی: `{get_p('XAUUSD'):,.0f}` دلار\n\n"
           f"⏰ آخرین آپدیت: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_technical(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0: return
    
    # استفاده از مقادیر فرضی برای حمایت/مقاومت بر اساس قیمت فعلی
    pivot = p_gold
    r1 = p_gold * 1.012  # مقاومت ۱ (۱.۲ درصد بالاتر)
    s1 = p_gold * 0.988  # حمایت ۱ (۱.۲ درصد پایین‌تر)
    
    msg = (f"📉 **تحلیل تکنیکال روزانه**\n\n"
           f"🎯 نقطه چرخش: `{pivot:,.0f}`\n"
           f"🚀 مقاومت مهم: `{r1:,.0f}`\n"
           f"🛡 حمایت مهم: `{s1:,.0f}`\n\n"
           f"💡 مومو: نوسان بالای حمایت نشانگر قدرت خریداران است.")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0 or p_ons == 0:
        bot.reply_to(message, "⚠️ دیتا ناقص است.")
        return
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble = ((p_gold - intrinsic) / intrinsic) * 100
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"💎 ارزش واقعی: `{intrinsic:,.0f}`\n"
           f"📊 قیمت بازار: `{p_gold:,.0f}`\n"
           f"📉 درصد حباب: `{bubble:.2f}%` ")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا (گرم):**")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message, weight=None):
    try:
        w = weight if weight else float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **درصد سود + اجرت:**")
        bot.register_next_step_handler(msg, calc_final, w)
    except: bot.send_message(message.chat.id, "⚠️ فقط عدد وارد کنید.")

def calc_final(message, weight):
    try:
        p_gold = get_p("IR_GOLD_18K")
        wage = float(message.text)
        total = (p_gold * (1 + wage / 100)) * weight
        bot.send_message(message.chat.id, f"💰 مبلغ نهایی: **`{total:,.0f}` تومان**", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def handle_ai(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = float(item.get('change_percent', 0))
    if pct > 1: ans = "❌ بازار پرریسک است؛ دست نگه دارید."
    elif pct < -1: ans = "✅ فرصت خرید پله‌ای در اصلاح قیمت."
    else: ans = "⚖️ بازار رنج (درجا)؛ مناسب برای نظاره."
    bot.send_message(message.chat.id, f"🧠 **سیگنال مومو:**\n\n{ans}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_chart(message):
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = item.get('change_percent', 0)
    val = item.get('change_value', 0)
    bot.send_message(message.chat.id, f"📊 **گزارش نوسان امروز:**\n\nمقدار: `{val:,.0f}` تومان\nدرصد: `{pct}%`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📅 تقویم اقتصادی")
def handle_calendar(message):
    events = "📅 **تقویم اقتصادی:**\n\n🔔 نوسانات به دلیل اخبار نرخ بهره آمریکا پیش‌بینی می‌شود."
    bot.send_message(message.chat.id, events, parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo Bot v{VERSION} Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
