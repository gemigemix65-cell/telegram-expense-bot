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
import io
import sqlite3

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

VERSION = "1.4.1"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 

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
#           *** ۳. موتور واکشی دیتا ***
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
        if isinstance(price, str):
            return float(price.replace(',', ''))
        return float(price)
    except: return 0

# ----------------------------------------
#           *** ۴. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    # تعریف دقیق دکمه‌ها برای اطمینان از مطابقت
    btn1 = telegram_types.KeyboardButton("💰 قیمت لحظه‌ای طلا و ارز")
    btn2 = telegram_types.KeyboardButton("📊 نمودار و تحلیل تغییرات")
    btn3 = telegram_types.KeyboardButton("🧠 تحلیل هوشمند")
    btn4 = telegram_types.KeyboardButton("🧮 ماشین‌حساب طلا")
    btn5 = telegram_types.KeyboardButton("⚪️ حباب طلا")
    btn6 = telegram_types.KeyboardButton("📉 تحلیل تکنیکال")
    btn7 = telegram_types.KeyboardButton("🔄 به‌روزرسانی")
    
    markup.row(btn1)
    markup.row(btn2, btn3)
    markup.row(btn4, btn5)
    markup.row(btn6, btn7)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    sync_market_data()
    bot.send_message(message.chat.id, "✨ به دستیار بازار مومو خوش آمدید!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    text = message.text
    sync_market_data()

    if "قیمت لحظه‌ای" in text:
        msg = (f"💰 **قیمت‌های لحظه‌ای**\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"🥇 طلا ۱۸ عیار: ` {get_p('IR_GOLD_18K'):,.0f} `\n"
               f"💵 دلار آزاد: ` {get_p('USD'):,.0f} `\n"
               f"👑 سکه امامی: ` {get_p('IR_COIN_EMAMI'):,.0f} `\n"
               f"🌐 انس جهانی: ` {get_p('XAUUSD'):,.0f} `\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"⏰ به‌روزرسانی: ` {MARKET_DATA['update_time']} `")
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

    elif "حباب طلا" in text:
        p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
        intrinsic = (p_ons * p_usd * 0.75) / 31.1035
        bubble_val = p_gold - intrinsic
        bubble_pct = (bubble_val / intrinsic) * 100
        msg = (f"⚪️ **آنالیز حباب طلا**\n"
               f"💰 ارزش ذاتی: ` {intrinsic:,.0f} `\n"
               f"📊 میزان حباب: ` {bubble_val:,.0f} `\n"
               f"🔢 درصد حباب: ` %{bubble_pct:.2f} `")
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

    elif "نمودار" in text:
        history = get_history("IR_GOLD_18K", 7)
        if len(history) < 2:
            bot.send_message(message.chat.id, "⚠️ دیتا کافی نیست.")
            return
        plt.figure(figsize=(8, 4))
        prices = [x[0] for x in history]; dates = [x[1][-5:] for x in history]
        plt.plot(dates, prices, color='#f1c40f', marker='o')
        plt.gcf().set_facecolor('#1a1a1a'); plt.gca().set_facecolor('#1a1a1a')
        plt.tick_params(colors='white')
        buf = io.BytesIO(); plt.savefig(buf, format='png', facecolor='#1a1a1a'); buf.seek(0); plt.close()
        bot.send_photo(message.chat.id, buf, caption="📊 روند تغییرات ۷ روزه")

    elif "تحلیل هوشمند" in text:
        p_gold = get_p("IR_GOLD_18K")
        history = get_history("IR_GOLD_18K", 7)
        if not history:
            bot.send_message(message.chat.id, "🧠 دیتا موجود نیست.")
            return
        avg = sum([x[0] for x in history]) / len(history)
        diff = ((p_gold - avg) / avg) * 100
        bot.send_message(message.chat.id, f"🧠 **تحلیل هوشمند**\nمیانگین هفته: `{avg:,.0f}`\nفاصله از میانگین: `% {diff:.2f}`", parse_mode='Markdown')

    elif "ماشین‌حساب" in text:
        msg = bot.send_message(message.chat.id, "⚖️ وزن طلا را به **گرم** وارد کنید:")
        bot.register_next_step_handler(msg, calc_step_2)

    elif "به‌روزرسانی" in text:
        sync_market_data()
        bot.send_message(message.chat.id, "🔄 اطلاعات با موفقیت به‌روزرسانی شد.")

    elif "تحلیل تکنیکال" in text:
        bot.send_message(message.chat.id, "📉 این بخش در حال آماده‌سازی است.")

# --- منطق ماشین حساب ---
def calc_step_2(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 درصد اجرت و سود را وارد کنید:")
        bot.register_next_step_handler(msg, calc_final, weight)
    except: bot.send_message(message.chat.id, "❌ عدد وارد کنید.")

def calc_final(message, weight):
    try:
        price = get_p("IR_GOLD_18K")
        fee = float(message.text)
        total = (price * weight) * (1 + fee/100)
        bot.send_message(message.chat.id, f"💵 مبلغ نهایی: **{total:,.0f}** تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "❌ خطا.")

# ----------------------------------------
#           *** ۵. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo Bot v{VERSION} is Running", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
