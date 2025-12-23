import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import jdatetime 
import time
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io
import sqlite3

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

VERSION = "1.6.6"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
# آپدیت API Key جدید لیارا
LIARA_AI_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiI2OTRhZmQwYzMwZWM5YThmNWMyMjhkM2QiLCJ0eXBlIjoiYWlfa2V5IiwiaWF0IjoxNzY2NTIyMTI0fQ.I1KRX5w-27Os1OUOIGRpVWT_EsBBkjVSy-xJ5Q8HJsA"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))
DB_PATH = '/app/data/market_history.db'

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. مدیریت دیتابیس ***
# ----------------------------------------

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, symbol TEXT, price REAL)''')
    conn.commit()
    conn.close()

def save_to_history(symbol, price):
    today = jdatetime.datetime.now().strftime("%Y/%m/%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE date=? AND symbol=?", (today, symbol))
    c.execute("INSERT INTO history VALUES (?, ?, ?)", (today, symbol, price))
    conn.commit()
    conn.close()

def get_history(symbol, limit=7):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT price, date FROM history WHERE symbol=? ORDER BY date DESC LIMIT ?", (symbol, limit))
    data = c.fetchall()
    conn.close()
    return data[::-1]

init_db()

# ----------------------------------------
#           *** ۳. موتور دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            temp_items = {}
            for category in ['gold', 'currency']:
                if category in res_json:
                    for item in res_json[category]:
                        symbol = item.get('symbol')
                        if symbol: temp_items[symbol] = item
            if temp_items:
                MARKET_DATA["items"] = temp_items
                now = jdatetime.datetime.now()
                MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
                MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
                p_gold = get_p("IR_GOLD_18K")
                if p_gold > 0: save_to_history("IR_GOLD_18K", p_gold)
                return True
        return False
    except: return False

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        if isinstance(price, str): return float(price.replace(',', ''))
        return float(price)
    except: return 0

# ----------------------------------------
#           *** ۴. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای طلا و ارز")
    markup.row("📊 نمودار تغییرات", "⚪️ حباب طلا")
    markup.row("🧮 ماشین‌حساب طلا", "🧠 تحلیل هوشمند")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد" or m.text == "بازگشت به منوی اصلی")
def start_cmd(message):
    sync_market_data()
    msg = "✨ **به دستیار هوشمند مومو خوش آمدید**\nلطفاً یک گزینه را انتخاب کنید:"
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

# --- بخش تحلیل هوشمند با Gemini 2.0 Flash لیارا ---

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def smart_ai_intro(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("بازگشت به منوی اصلی")
    
    msg = (f"🧠 **وارد بخش تحلیل هوشمند شدید**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"من به عنوان یک تحلیل‌گر خبره و باهوش با استفاده از مدل **Gemini 2.0** آماده پاسخگویی هستم.\n\n"
           f"💰 قیمت فعلی طلا: `{p_gold:,.0f}`\n"
           f"💵 قیمت فعلی دلار: `{p_usd:,.0f}`\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"👇 **هر سوالی داری بپرس (مثلاً: الان بخرم یا صبر کنم؟)**")
    
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')
    bot.register_next_step_handler(message, chat_with_gemini)

def chat_with_gemini(message):
    if message.text == "بازگشت به منوی اصلی":
        start_cmd(message)
        return

    bot.send_chat_action(message.chat.id, 'typing')
    
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    
    system_prompt = (
        "تو یک تحلیل‌گر فوق حرفه‌ای، باهوش و خبره بازار طلای ایران هستی. نام تو 'مومو AI' است. "
        "لحن تو صمیمی، دلسوز و در عین حال بسیار دقیق و تخصصی است. "
        f"اطلاعات لحظه‌ای بازار: طلا ۱۸ عیار {p_gold:,.0f} تومان، دلار {p_usd:,.0f} تومان، انس جهانی {p_ons:,.0f} دلار. "
        "باید بر اساس این اعداد و دانش تخصصی اقتصادی خودت، کاربر را راهنمایی کنی. پاسخ‌ها را زیبا و با اموجی‌های مرتبط تزیین کن."
    )

    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.text}
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {LIARA_AI_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post("https://api.liara.ir/v1/ai/chat/completions", json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            ai_reply = res_json['choices'][0]['message']['content']
        else:
            ai_reply = "😔 پوزش می‌خوام، ارتباطم با مرکز تحلیل کمی ضعیف شده. لطفاً دوباره سوالت رو بپرس."
    except:
        ai_reply = "❌ خطایی در پردازش هوشمند رخ داد. احتمالاً کلید دسترسی نیاز به بررسی دارد."

    msg = bot.send_message(message.chat.id, ai_reply, parse_mode='Markdown')
    bot.register_next_step_handler(msg, chat_with_gemini)

# --- بقیه هندلرها (💰 قیمت، 📊 نمودار، ⚪️ حباب، 🧮 ماشین حساب) ---

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای طلا و ارز")
def handle_price(message):
    sync_market_data()
    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"🥇 طلا ۱۸ عیار: ` {get_p('IR_GOLD_18K'):,.0f} ` تومان\n\n"
           f"💵 دلار آزاد: ` {get_p('USD'):,.0f} ` تومان\n\n"
           f"👑 سکه امامی: ` {get_p('IR_COIN_EMAMI'):,.0f} ` تومان\n\n"
           f"🌐 انس جهانی: ` {get_p('XAUUSD'):,.0f} ` دلار\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"📅 تاریخ: ` {MARKET_DATA['update_date']} `\n"
           f"⏰ ساعت: ` {MARKET_DATA['update_time']} `")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_val = p_gold - intrinsic
    bubble_pct = (bubble_val / intrinsic) * 100
    msg = (f"⚪️ **آنالیز حباب طلا**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"📊 مقدار حباب: **` {bubble_val:,.0f} ` تومان**\n"
           f"🔢 درصد حباب: **` %{bubble_pct:.2f} `**\n"
           f"📌 وضعیت: {'🔴 حباب مثبت' if bubble_val > 0 else '🟢 حباب منفی'}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_chart(message):
    sync_market_data()
    history = get_history("IR_GOLD_18K", 7)
    current_p = get_p("IR_GOLD_18K")
    if len(history) < 2:
        prices = [current_p, current_p]
        dates = ["Old", "Now"]
    else:
        prices = [x[0] for x in history]
        dates = [x[1][-5:] for x in history]
    
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, prices, color='#f1c40f', marker='o')
    ax.set_title("Gold Price Trend", color='white')
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')
    ax.tick_params(colors='white')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#1a1a1a')
    buf.seek(0)
    plt.close()
    
    bot.send_photo(message.chat.id, buf, caption=f"📊 نمودار تغییرات ۷ روزه طلا\nقیمت فعلی: {current_p:,.0f}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب طلا")
def calc_menu(message):
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("1️⃣ محاسبه قیمت (خرید)", "2️⃣ محاسبه سود فروشنده")
    markup.row("بازگشت به منوی اصلی")
    msg = bot.send_message(message.chat.id, "🧮 انتخاب کنید:", reply_markup=markup)
    bot.register_next_step_handler(msg, calc_router)

def calc_router(message):
    if message.text == "بازگشت به منوی اصلی":
        start_cmd(message)
        return
    if "1️⃣" in message.text:
        msg = bot.send_message(message.chat.id, "⚖️ وزن (گرم):", reply_markup=telegram_types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, calc_price_step1)
    elif "2️⃣" in message.text:
        msg = bot.send_message(message.chat.id, "💰 مبلغ کل پرداختی:", reply_markup=telegram_types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, calc_profit_step1)

def calc_price_step1(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 درصد مجموع (سود+اجرت+مالیات):")
        bot.register_next_step_handler(msg, calc_price_final, weight)
    except: bot.send_message(message.chat.id, "❌ خطا.", reply_markup=main_menu())

def calc_price_final(message, weight):
    try:
        sync_market_data()
        price = get_p("IR_GOLD_18K")
        total = (price * weight) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"💵 **قیمت نهایی:** `{total:,.0f}` تومان", reply_markup=main_menu(), parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "❌ خطا.", reply_markup=main_menu())

def calc_profit_step1(message):
    try:
        total_paid = float(message.text)
        msg = bot.send_message(message.chat.id, "⚖️ وزن طلا (گرم):")
        bot.register_next_step_handler(msg, calc_profit_final, total_paid)
    except: bot.send_message(message.chat.id, "❌ خطا.", reply_markup=main_menu())

def calc_profit_final(message, total_paid):
    try:
        sync_market_data()
        price_raw = get_p("IR_GOLD_18K")
        weight = float(message.text)
        diff = total_paid - (weight * price_raw)
        pct = (diff / (weight * price_raw)) * 100
        res = (f"🕵️ **آنالیز سود فروشنده**\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"🛠 سود گرفته شده: `{diff:,.0f}` تومان\n"
               f"📊 درصد سود: `%{pct:.2f}`")
        bot.send_message(message.chat.id, res, reply_markup=main_menu(), parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "❌ خطا.", reply_markup=main_menu())

# ----------------------------------------
#           *** ۵. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo v{VERSION} Ready", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
