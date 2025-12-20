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

VERSION = "1.1.2"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه موقت ربات
MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی و عیب‌یابی ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    try:
        # درخواست ساده و مستقیم بدون پیچیدگی
        response = requests.get(url, timeout=15)
        
        # بررسی وضعیت پاسخ سرور
        if response.status_code != 200:
            return False, f"خطای سرور مقصد (کد {response.status_code})"
            
        res_json = response.json()
        temp_items = {}
        
        # استخراج بر اساس نمونه خروجی ارسالی شما
        # پیمایش لیست‌های gold و currency و ذخیره بر اساس symbol
        for cat in ['gold', 'currency']:
            if cat in res_json and isinstance(res_json[cat], list):
                for item in res_json[cat]:
                    sym = item.get('symbol')
                    if sym:
                        temp_items[sym] = item
            else:
                return False, f"کلید {cat} در پاسخ API یافت نشد یا لیست نیست."

        if not temp_items:
            return False, "دیتای استخراج شده خالی است (ساختار JSON تغییر کرده؟)"

        # ذخیره در حافظه در صورت موفقیت
        MARKET_DATA["items"] = temp_items
        now = jdatetime.datetime.now()
        MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
        MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
        return True, "OK"
        
    except requests.exceptions.ConnectionError:
        return False, "قطع اتصال شبکه (Connection Reset/Timeout)"
    except Exception as e:
        return False, f"خطای سیستمی: {str(e)}"

def get_p(symbol):
    """استخراج قیمت عددی از دیتای ذخیره شده"""
    item = MARKET_DATA["items"].get(symbol, {})
    # در دیتای جدید شما، قیمت به صورت عدد یا رشته بدون کاما است
    price = item.get('price', 0)
    try:
        if isinstance(price, str):
            return float(price.replace(',', ''))
        return float(price)
    except:
        return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات بازار")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("📉 تحلیل تکنیکال", "🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    # اجرای همگام‌سازی و دریافت گزارش وضعیت
    success, report = sync_market_data()
    
    status_icon = "🟢" if success else "🔴"
    
    msg = (f"✨ **وضعیت ربات مومو (v{VERSION})**\n\n"
           f"اتصال به بازار: {status_icon}\n"
           f"گزارش وضعیت: `{report}`\n\n"
           f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
           f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
           f"لطفاً یک گزینه را انتخاب کنید:")
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    # قبل از نمایش قیمت، یک بار تلاش برای به‌روزرسانی
    sync_market_data()
    
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    
    if p_gold == 0:
        bot.reply_to(message, "⚠️ خطا: دیتای قیمت در حافظه موجود نیست. دکمه «شروع مجدد» را بزنید.")
        return

    msg = (f"💰 **قیمت‌های زنده بازار**\n\n"
           f"🥇 **طلا ۱۸ عیار:**\n`{p_gold:,.0f}` تومان\n\n"
           f"💵 **دلار:**\n`{p_usd:,.0f}` تومان\n\n"
           f"👑 **سکه امامی:**\n`{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 **انس جهانی:**\n`{get_p('XAUUSD'):,.0f}` دلار\n\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0 or p_ons == 0:
        bot.reply_to(message, "❌ دیتا برای محاسبه حباب کامل نیست.")
        return
    
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"💎 ارزش واقعی: `{intrinsic:,.0f}`\n"
           f"📊 قیمت بازار: `{p_gold:,.0f}`\n"
           f"📈 درصد حباب: `{bubble_pct:.2f}%` ")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات بازار")
def handle_changes(message):
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    if not item:
        bot.reply_to(message, "⚠️ دیتایی یافت نشد.")
        return
        
    msg = (f"📊 **تغییرات طلا ۱۸ عیار**\n\n"
           f"نوسان: `{item.get('change_value', 0):,.0f}` تومان\n"
           f"درصد: `{item.get('change_percent', 0)}%` \n"
           f"آخرین تغییر: `{item.get('time', '---')}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا (گرم):**")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        w = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **درصد سود و اجرت:**")
        bot.register_next_step_handler(msg, calc_final, w)
    except: bot.send_message(message.chat.id, "⚠️ عدد وارد کنید.")

def calc_final(message, w):
    try:
        p = get_p("IR_GOLD_18K")
        total = (p * w) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"💰 **مبلغ فاکتور:**\n`{total:,.0f}` تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    p = get_p("IR_GOLD_18K")
    if p == 0:
        bot.reply_to(message, "❌ دیتا در دسترس نیست.")
        return
    msg = (f"📉 **تحلیل تکنیکال**\n\n"
           f"🛡 حمایت: `{p*0.985:,.0f}`\n"
           f"🚀 مقاومت: `{p*1.015:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo v{VERSION} Debug Mode Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
