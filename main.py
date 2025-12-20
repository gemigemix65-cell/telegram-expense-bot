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

VERSION = "1.1.5"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
ADMIN_ID = "8221583925"
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "به‌روزرسانی نشده", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        res_json = response.json()
        temp_items = {}
        for category in ['gold', 'currency']:
            data_list = res_json.get(category, [])
            if isinstance(data_list, list):
                for item in data_list:
                    symbol = item.get('symbol')
                    if symbol: temp_items[symbol] = item
        MARKET_DATA["items"] = temp_items
        now = jdatetime.datetime.now()
        MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
        MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
        return True, "OK"
    except:
        return False, "Error"

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        return float(str(price).replace(',', ''))
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
    success, _ = sync_market_data()
    status = "🟢 آنلاین" if success else "🔴 خطا"
    welcome_text = (
        f"✨ **ربات تحلیل بازار طلای شخصی مومو**\n"
        f"👤 مومو من در خدمتم\n"
        f"--------------------------\n"
        f"📡 وضعیت اتصال: {status}\n"
        f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
        f"⏰ ساعت: `{MARKET_DATA['update_time']}`"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

# --- بخش جدید: تحلیل تکنیکال (Pivot Points) ---
@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_technical(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    high = float(item.get('max', p_gold))
    low = float(item.get('min', p_gold))
    
    # محاسبه نقاط کلیدی روزانه
    pivot = (high + low + p_gold) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    
    msg = (f"📉 **تحلیل تکنیکال مومو (طلا ۱۸)**\n\n"
           f"🎯 نقطه چرخش (Pivot): `{pivot:,.0f}`\n\n"
           f"🚀 **مقاومت‌ها (اهداف صعودی):**\n"
           f"مقاومت ۱: `{r1:,.0f}`\n\n"
           f"🛡 **حمایت‌ها (سطوح بازگشتی):**\n"
           f"حمایت ۱: `{s1:,.0f}`\n\n"
           f"💡 *مومو:* اگر قیمت بالای نقطه چرخش بماند، بازار تمایل به صعود دارد.")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# --- بخش جدید: تقویم اقتصادی ---
@bot.message_handler(func=lambda m: m.text == "📅 تقویم اقتصادی")
def handle_calendar(message):
    events = (
        "📅 **رویدادهای مهم پیش‌رو:**\n\n"
        "🏛 **نشست فدرال رزرو (آمریکا):** تعیین نرخ بهره که مستقیماً روی انس جهانی تاثیر دارد.\n"
        "🇮🇷 **نرخ تورم داخلی:** تاثیر بر قیمت تتر و دلار آزاد.\n"
        "📊 **آمار بیکاری ماهانه:** نوسان‌دهنده اصلی قیمت طلا.\n\n"
        "🔔 *مومو:* در روزهای اعلام خبر، بازار به شدت نوسانی است؛ احتیاط کنید!"
    )
    bot.send_message(message.chat.id, events, parse_mode='Markdown')

# --- بخش ماشین‌حساب (مشابه قبل) ---
@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا** را وارد کنید (گرم):")
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **درصد اجرت یا سود** را وارد کنید:")
        bot.register_next_step_handler(msg, calc_final, weight)
    except:
        bot.send_message(message.chat.id, "⚠️ عدد اشتباه!")

def calc_final(message, weight):
    try:
        sync_market_data()
        wage_pct = float(message.text)
        p_gold = get_p("IR_GOLD_18K")
        total = (p_gold + (p_gold * wage_pct / 100)) * weight
        res = (f"🧮 **نتیجه محاسبات مومو**\n"
               f"💰 مبلغ کل: **`{total:,.0f} تومان`**")
        bot.send_message(message.chat.id, res, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "⚠️ خطا!")

# --- سایر بخش‌ها ---
@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    msg = (f"💰 **قیمت لحظه‌ای**\n"
           f"🥇 طلا ۱۸: `{p_gold:,.0f}`\n"
           f"💵 دلار: `{get_p('USD'):,.0f}`\n"
           f"👑 سکه امامی: `{get_p('IR_COIN_EMAMI'):,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_chart(message):
    sync_market_data()
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = float(item.get('change_percent', 0))
    bar = ("✅" if pct >= 0 else "🔻") * (min(abs(int(pct * 3)), 10) or 1)
    bot.send_message(message.chat.id, f"📊 **تغییرات امروز:**\n`{pct}%` \n{bar}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble = ((p_gold - intrinsic) / intrinsic) * 100
    bot.send_message(message.chat.id, f"⚪️ **حباب طلا:** `{bubble:.2f}%`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def handle_ai(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble = ((p_gold - intrinsic) / intrinsic) * 100
    ans = "✅ خرید پله‌ای" if bubble < 1 else "❌ صبر کنید"
    bot.send_message(message.chat.id, f"🧠 **سیگنال مومو:**\n{ans}", parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Momo Bot Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
