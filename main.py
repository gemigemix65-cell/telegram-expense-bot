import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import jdatetime 
import time
import matplotlib
matplotlib.use('Agg') # برای جلوگیری از خطای گرافیکی در سرور
import matplotlib.pyplot as plt
import io
import sqlite3

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

VERSION = "1.3.9"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

# مسیر دیتابیس بر روی دیسک متصل شده در لیارا
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
                
                # ثبت خودکار در دیتابیس
                p_gold = get_p("IR_GOLD_18K")
                if p_gold > 0: save_to_history("IR_GOLD_18K", p_gold)
                return True
        return False
    except: return False

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try: return float(str(price).replace(',', ''))
    except: return 0

# ----------------------------------------
#           *** ۴. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای طلا و ارز")
    markup.row("📊 نمودار و تحلیل تغییرات", "🧠 تحلیل هوشمند")
    markup.row("🧮 ماشین‌حساب طلا", "⚪️ حباب طلا")
    markup.row("📉 تحلیل تکنیکال", "🔄 به‌روزرسانی")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 به‌روزرسانی")
def start(message):
    sync_market_data()
    msg = (f"✨ **دستیار بازار مومو (v{VERSION})**\n"
           f"📅 تاریخ: ` {MARKET_DATA['update_date']} `\n"
           f"⏰ ساعت: ` {MARKET_DATA['update_time']} `\n"
           f"📂 وضعیت دیتابیس: ` متصل `")
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای طلا و ارز")
def handle_price(message):
    sync_market_data()
    msg = (f"💰 **قیمت‌های لحظه‌ای**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"🥇 طلا ۱۸ عیار: ` {get_p('IR_GOLD_18K'):,.0f} `\n"
           f"💵 دلار آزاد: ` {get_p('USD'):,.0f} `\n"
           f"👑 سکه امامی: ` {get_p('IR_COIN_EMAMI'):,.0f} `\n"
           f"🌐 انس جهانی: ` {get_p('XAUUSD'):,.0f} `\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"⏰ به‌روزرسانی: ` {MARKET_DATA['update_time']} `")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0:
        bot.reply_to(message, "⚠️ خطا در دریافت اطلاعات.")
        return

    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_val = p_gold - intrinsic
    bubble_pct = (bubble_val / intrinsic) * 100
    status = "📈 حباب مثبت" if bubble_val > 0 else "📉 حباب منفی"

    msg = (
        f"⚪️ **آنالیز حباب طلا ۱۸ عیار**\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📏 **فرمول:** `(انس × دلار × 0.75) / 31.1035`\n\n"
        f"💰 ارزش ذاتی: ` {intrinsic:,.0f} ` تومان\n"
        f"🏪 قیمت بازار: ` {p_gold:,.0f} ` تومان\n"
        f"--------------------------\n"
        f"📊 میزان حباب: **` {bubble_val:,.0f} ` تومان**\n"
        f"🔢 درصد حباب: **` %{bubble_pct:.2f} `**\n"
        f"📌 وضعیت: {status}\n"
        f"➖➖➖➖➖➖➖➖➖➖"
    )
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 نمودار و تحلیل تغییرات")
def handle_chart(message):
    sync_market_data()
    history = get_history("IR_GOLD_18K", 7)
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct, val = item.get('change_percent', 0), item.get('change_value', 0)
    
    msg = (f"📊 **تحلیل تغییرات (هفتگی)**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"💰 قیمت فعلی: ` {get_p('IR_GOLD_18K'):,.0f} `\n"
           f"📉 مقدار تغییر: ` {val} ` تومان\n"
           f"🔢 درصد تغییر: ` %{pct} `\n"
           f"➖➖➖➖➖➖➖➖➖➖")
    
    if len(history) < 2:
        bot.send_message(message.chat.id, msg + "\n⚠️ در حال جمع‌آوری دیتا...")
        return

    plt.figure(figsize=(8, 4))
    prices = [x[0] for x in history]
    dates = [x[1][-5:] for x in history]
    plt.plot(dates, prices, color='#f1c40f', marker='o', linewidth=2)
    plt.gcf().set_facecolor('#1a1a1a')
    plt.gca().set_facecolor('#1a1a1a')
    plt.tick_params(colors='white')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#1a1a1a')
    buf.seek(0)
    plt.close()
    bot.send_photo(message.chat.id, buf, caption=msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب طلا")
def calc_start(message):
    msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا را به گرم وارد کنید:**", parse_mode='Markdown')
    bot.register_next_step_handler(msg, calc_step_2)

def calc_step_2(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 **مجموع درصد سود و اجرت را وارد کنید (فقط عدد):**")
        bot.register_next_step_handler(msg, calc_final, weight)
    except:
        bot.send_message(message.chat.id, "❌ لطفا فقط عدد وارد کنید. دوباره روی دکمه ماشین‌حساب بزنید.")

def calc_final(message, weight):
    try:
        sync_market_data()
        price = get_p("IR_GOLD_18K")
        fee_pct = float(message.text)
        total = (price * weight) * (1 + fee_pct/100)
        res = (f"🧮 **نتیجه محاسبات:**\n"
               f"⚖️ وزن: `{weight}` گرم\n"
               f"💰 قیمت واحد: `{price:,.0f}`\n"
               f"🛠 سود+اجرت: `{fee_pct}%` \n\n"
               f"💵 مبلغ نهایی: **` {total:,.0f} ` تومان**")
        bot.send_message(message.chat.id, res, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def smart_analysis(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    history = get_history("IR_GOLD_18K", 7)
    
    if not history:
        bot.send_message(message.chat.id, "🧠 در حال حاضر دیتای کافی برای تحلیل هوشمند ندارم.")
        return

    avg_price = sum([x[0] for x in history]) / len(history)
    diff = ((p_gold - avg_price) / avg_price) * 100
    
    advice = "✅ قیمت در محدوده میانگین است."
    if diff > 2: advice = "⚠️ قیمت نسبت به میانگین هفته بالاست؛ احتیاط کنید."
    elif diff < -2: advice = "📉 قیمت نسبت به میانگین هفته پایین است؛ فرصت بررسی خرید."

    msg = (f"🧠 **تحلیل هوشمند مومو**\n"
           f"📊 میانگین ۷ روزه: ` {avg_price:,.0f} `\n"
           f"📍 فاصله از میانگین: ` %{diff:.2f} `\n\n"
           f"💡 **پیشنهاد:**\n{advice}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def technical_analysis(message):
    bot.send_message(message.chat.id, "🛠 این بخش در نسخه‌های آینده با اندیکاتورهای RSI و MACD تکمیل می‌شود.")

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
