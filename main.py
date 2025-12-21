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

VERSION = "1.5.0"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

# مسیر دیتابیس روی دیسک لیارا
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
    # جلوگیری از تکرار در یک روز
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
    # بازگرداندن به ترتیب زمانی (قدیم به جدید)
    return data[::-1]

def get_db_count():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM history")
        count = c.fetchone()[0]
        conn.close()
        return count
    except: return 0

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
                
                # ذخیره قیمت طلا در دیتابیس
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
    # نام دکمه‌ها دقیق و ثابت
    markup.row("💰 قیمت لحظه‌ای طلا و ارز")
    markup.row("📊 نمودار تغییرات", "⚪️ حباب طلا")
    markup.row("🧮 ماشین‌حساب طلا", "🧠 تحلیل هوشمند")
    markup.row("🔄 شروع مجدد")
    return markup

# --- هندلر شروع و به‌روزرسانی ---
# این هندلر هم دستور /start و هم متن دکمه را می‌گیرد
@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start_cmd(message):
    sync_market_data()
    db_count = get_db_count()
    
    msg = (f"✨ **دستیار بازار مومو**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"📅 تاریخ: ` {MARKET_DATA['update_date']} `\n"
           f"⏰ ساعت: ` {MARKET_DATA['update_time']} `\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"📂 وضعیت دیسک: متصل\n"
           f"📊 رکوردهای ثبت شده: ` {db_count} `")
           
    bot.send_message(message.chat.id, msg, reply_markup=main_menu(), parse_mode='Markdown')

# --- قیمت لحظه‌ای ---
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

# --- حباب طلا (فرمت اصلاح شده) ---
@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    p_ons = get_p("XAUUSD")
    
    if p_gold == 0 or p_usd == 0:
        bot.reply_to(message, "⚠️ اطلاعات کافی نیست.")
        return

    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_val = p_gold - intrinsic
    bubble_pct = (bubble_val / intrinsic) * 100
    
    status = "🔴 حباب مثبت (گران)" if bubble_val > 0 else "🟢 حباب منفی (ارزان)"

    msg = (
        f"⚪️ **آنالیز حباب طلا ۱۸ عیار**\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📐 **فرمول:**\n"
        f"`(انس × دلار × 0.75) / 31.1035`\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 ارزش ذاتی: ` {intrinsic:,.0f} ` تومان\n\n"
        f"🏪 قیمت بازار: ` {p_gold:,.0f} ` تومان\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📊 مقدار حباب: **` {bubble_val:,.0f} ` تومان**\n\n"
        f"🔢 درصد حباب: **` %{bubble_pct:.2f} `**\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📌 وضعیت: {status}"
    )
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# --- نمودار (با اصلاح دیتا) ---
@bot.message_handler(func=lambda m: m.text == "📊 نمودار تغییرات")
def handle_chart(message):
    sync_market_data()
    history = get_history("IR_GOLD_18K", 7)
    
    # اصلاح: اگر دیتا کم بود، با استفاده از تغییر قیمت امروز، دیتای دیروز را شبیه‌سازی کن
    if len(history) < 2:
        current_p = get_p("IR_GOLD_18K")
        item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
        try:
            change_val = float(str(item.get('change_value', 0)).replace(',', ''))
        except: change_val = 0
        
        yesterday_p = current_p - change_val
        # لیست موقت برای رسم نمودار (دیروز و امروز)
        prices = [yesterday_p, current_p]
        dates = ["دیروز", "امروز"]
    else:
        prices = [x[0] for x in history]
        dates = [x[1][-5:] for x in history] # فقط ماه/روز

    # رسم نمودار
    plt.figure(figsize=(8, 4))
    plt.plot(dates, prices, color='#f1c40f', marker='o', linewidth=2)
    plt.title("Gold Trend (Momo)", color='white')
    plt.grid(True, linestyle='--', alpha=0.3)
    
    # تم مشکی
    plt.gcf().set_facecolor('#1a1a1a')
    plt.gca().set_facecolor('#1a1a1a')
    plt.tick_params(colors='white')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#1a1a1a')
    buf.seek(0)
    plt.close()
    
    # اطلاعات تغییرات
    item = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = item.get('change_percent', 0)
    val = item.get('change_value', 0)
    
    caption = (f"📊 **نمودار تغییرات قیمت طلا**\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"💰 قیمت فعلی: ` {get_p('IR_GOLD_18K'):,.0f} ` تومان\n\n"
               f"📉 تغییر امروز: ` {val} ` تومان\n\n"
               f"🔢 درصد تغییر: ` %{pct} `")

    bot.send_photo(message.chat.id, buf, caption=caption, parse_mode='Markdown')

# --- ماشین حساب (دو حالته) ---
@bot.message_handler(func=lambda m: m.text == "🧮 ماشین‌حساب طلا")
def calc_menu(message):
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("1️⃣ محاسبه قیمت (خرید)", "2️⃣ محاسبه سود فروشنده")
    markup.row("بازگشت به منوی اصلی")
    msg = bot.send_message(message.chat.id, "🧮 لطفاً نوع محاسبه را انتخاب کنید:", reply_markup=markup)
    bot.register_next_step_handler(msg, calc_router)

def calc_router(message):
    if message.text == "بازگشت به منوی اصلی":
        bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu())
        return

    if "1️⃣" in message.text: # محاسبه قیمت
        msg = bot.send_message(message.chat.id, "⚖️ **وزن طلا** را به گرم وارد کنید:", reply_markup=telegram_types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, calc_price_step1)
        
    elif "2️⃣" in message.text: # محاسبه سود (قابلیت جدید)
        msg = bot.send_message(message.chat.id, "💰 **مبلغ کل پرداختی** (تومان) را وارد کنید:", reply_markup=telegram_types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, calc_profit_step1)
    else:
        bot.send_message(message.chat.id, "گزینه نامعتبر.", reply_markup=main_menu())

# --- حالت ۱: محاسبه قیمت ---
def calc_price_step1(message):
    try:
        weight = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 درصد **سود + اجرت + مالیات** را وارد کنید (مثلاً 18):")
        bot.register_next_step_handler(msg, calc_price_final, weight)
    except:
        bot.send_message(message.chat.id, "❌ عدد نامعتبر. بازگشت.", reply_markup=main_menu())

def calc_price_final(message, weight):
    try:
        sync_market_data()
        price = get_p("IR_GOLD_18K")
        fee = float(message.text)
        total = (price * weight) * (1 + fee/100)
        
        res = (f"🧮 **نتیجه محاسبه قیمت**\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"⚖️ وزن: `{weight}` گرم\n"
               f"💰 قیمت واحد: `{price:,.0f}` تومان\n"
               f"🛠 درصد اعمال شده: `{fee}%`\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"💵 **مبلغ نهایی:** `{total:,.0f}` تومان")
        bot.send_message(message.chat.id, res, reply_markup=main_menu(), parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ خطا در محاسبه.", reply_markup=main_menu())

# --- حالت ۲: محاسبه سود فروشنده (جدید) ---
def calc_profit_step1(message):
    try:
        total_paid = float(message.text)
        msg = bot.send_message(message.chat.id, "⚖️ حالا **وزن طلا** (گرم) را وارد کنید:")
        bot.register_next_step_handler(msg, calc_profit_final, total_paid)
    except:
        bot.send_message(message.chat.id, "❌ عدد نامعتبر.", reply_markup=main_menu())

def calc_profit_final(message, total_paid):
    try:
        sync_market_data()
        price_raw = get_p("IR_GOLD_18K")
        weight = float(message.text)
        
        # فرمول معکوس: قیمت واقعی طلا چقدر بوده؟ تفاوتش میشه سود
        real_value = weight * price_raw
        diff = total_paid - real_value
        profit_pct = (diff / real_value) * 100
        
        res = (f"🕵️ **آنالیز سود فروشنده**\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"💵 مبلغ کل پرداختی: `{total_paid:,.0f}` تومان\n"
               f"⚖️ وزن طلا: `{weight}` گرم\n"
               f"💰 ارزش خام طلا: `{real_value:,.0f}` تومان\n"
               f"➖➖➖➖➖➖➖➖➖➖\n"
               f"🛠 **سود گرفته شده:** `{diff:,.0f}` تومان\n"
               f"📊 **درصد سود:** `%{profit_pct:.2f}`")
               
        bot.send_message(message.chat.id, res, reply_markup=main_menu(), parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ خطا در محاسبه.", reply_markup=main_menu())

# --- تحلیل هوشمند ---
@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند")
def handle_smart(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    history = get_history("IR_GOLD_18K", 7)
    
    if not history:
        # اگر هیچی نبود، با قیمت الان یه دیتای ساختگی درست میکنیم که ارور نده
        avg_price = p_gold
    else:
        prices = [x[0] for x in history]
        avg_price = sum(prices) / len(prices)
        
    diff = ((p_gold - avg_price) / avg_price) * 100
    
    advice = "تثبیت نسبی"
    if diff > 1: advice = "بالاتر از میانگین (احتیاط)"
    elif diff < -1: advice = "پایین‌تر از میانگین (بررسی خرید)"

    msg = (f"🧠 **تحلیل هوشمند**\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"📈 میانگین (هفتگی): ` {avg_price:,.0f} ` تومان\n\n"
           f"📍 فاصله از میانگین: ` %{diff:.2f} `\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"💡 وضعیت: {advice}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۵. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return f"Momo v{VERSION} Running", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
