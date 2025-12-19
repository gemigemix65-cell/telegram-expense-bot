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
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه موقت برای ذخیره دیتا
MARKET_DATA = {
    "items": {}, # تمام نمادها را اینجا تخت (Flat) ذخیره می‌کنیم
    "update_time": "به‌روزرسانی نشده"
}

# ----------------------------------------
#           *** ۲. موتور هوشمند واکشی ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency_Pro.php?key={BRS_TOKEN}&section=gold,currency"
    
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            
            new_items = {}
            
            # ۱. استخراج طلا (بر اساس ساختار جدیدی که فرستادید)
            gold_sections = res_json.get('gold', {})
            # پیمایش تمام زیرمجموعه‌ها: ounce, type, coin, coin_parsian
            for sec_name in gold_sections:
                for item in gold_sections[sec_name]:
                    symbol = item.get('symbol')
                    if symbol:
                        new_items[symbol] = item
            
            # ۲. استخراج ارزها (بخش free)
            currency_sections = res_json.get('currency', {})
            for item in currency_sections.get('free', []):
                symbol = item.get('symbol')
                if symbol:
                    new_items[symbol] = item

            MARKET_DATA["items"] = new_items
            MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return True
    except Exception as e:
        print(f"Sync Error: {e}")
    return False

def get_val(symbol, field='price'):
    """استخراج مقدار عددی فیلد از یک نماد خاص"""
    item = MARKET_DATA["items"].get(symbol, {})
    val = item.get(field, 0)
    try:
        return float(str(val).replace(',', ''))
    except:
        return 0

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات")
    markup.row("⚪️ حباب طلا", "🧠 مشاوره")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    bot.send_message(
        message.chat.id, 
        "✅ **ربات با ساختار جدید API آپدیت شد.**\nآماده واکشی اطلاعات...", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    if not sync_market_data():
        bot.reply_to(message, "⚠️ خطا در ارتباط با سرور قیمت.")
        return

    # استخراج بر اساس سمبل‌های دقیق موجود در JSON ارسالی شما
    p_gold = get_val("IR_GOLD_18K") 
    p_sekeh = get_val("IR_COIN_EMAMI")
    p_usd = get_val("USD") # این مقدار به ریال است
    p_ons = get_val("XAUUSD")

    if p_gold == 0:
        bot.send_message(message.chat.id, "❌ دیتایی دریافت نشد. پارامترهای API را چک کنید.")
        return

    msg = (f"💰 **نرخ‌های بازار (آپدیت شده)**\n"
           f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold/10:,.0f}` تومان\n"
           f"👑 سکه امامی: `{p_sekeh/10:,.0f}` تومان\n"
           f"💵 دلار آمریکا: `{p_usd/10:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات")
def handle_changes(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = item.get('change_percent', 0)
    val = get_val("IR_GOLD_18K", "change_value") / 10
    
    arrow = "📈" if float(pct) >= 0 else "📉"
    bot.send_message(message.chat.id, f"📊 **تغییرات طلا ۱۸ عیار:**\n\n{arrow} مقدار: `{val:,.0f}` تومان\nدرصد: `{pct}%`")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_val("IR_GOLD_18K") / 10
    p_usd = get_val("USD") / 10
    p_ons = get_val("XAUUSD")
    
    if p_gold > 0 and p_usd > 0:
        intrinsic = (p_ons * (p_usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\n\n💰 ارزش واقعی: `{intrinsic:,.0f}`\n🎈 حباب: `{bubble:.2f}%`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره")
def handle_advice(message):
    bot.send_message(message.chat.id, "🧠 تحلیل بر اساس حباب طلا و انس جهانی انجام می‌شود.")

# ----------------------------------------
#           *** ۴. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return "Bot is Active with New JSON Structure!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
