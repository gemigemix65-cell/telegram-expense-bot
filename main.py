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
# کلید شما برای نسخه Pro طبق مستندات
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه برای ذخیره آخرین وضعیت دریافتی از API Pro
MARKET_CACHE = {
    "gold": {}, 
    "currency": {},
    "last_sync": None
}

# ----------------------------------------
#           *** ۲. موتور واکشی از API Pro ***
# ----------------------------------------

def sync_pro_data():
    global MARKET_CACHE
    # آدرس دقیق بر اساس مستندات نسخه Pro سایت BrsApi
    url = f"https://brsapi.ir/Api/Market/Gold_Currency_Pro.php?key={BRS_TOKEN}&section=gold,currency"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            
            if res_json.get("successful"):
                # ذخیره سازی داده‌های طلا
                for item in res_json.get('gold', []):
                    MARKET_CACHE["gold"][item['symbol']] = item
                
                # ذخیره سازی داده‌های ارز
                for item in res_json.get('currency', []):
                    MARKET_CACHE["currency"][item['symbol']] = item
                
                MARKET_CACHE["last_sync"] = jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M:%S")
                return True
    except Exception as e:
        print(f"Pro API Error: {e}")
    return False

# ----------------------------------------
#           *** ۳. هندلرهای دکمه‌ها ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 مقایسه و تغییرات")
    markup.row("⚪️ حباب طلا", "🧠 مشاوره خرید")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_pro_data()
    bot.send_message(
        message.chat.id, 
        "🚀 **ربات تحلیلگر هوشمند (نسخه Pro) فعال شد.**\nداده‌ها مستقیماً از بخش حرفه‌ای BrsApi واکشی می‌شوند.", 
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    if not sync_pro_data():
        bot.reply_to(message, "⚠️ خطا در دریافت اطلاعات از سرور Pro. لطفاً دوباره تلاش کنید.")
        return

    g = MARKET_CACHE["gold"].get("IR_18K_GOLD", {})
    s = MARKET_CACHE["gold"].get("IR_COIN_EMAMI", {})
    d = MARKET_CACHE["currency"].get("USD", {})
    o = MARKET_CACHE["gold"].get("XAU_USD", {})

    msg = (f"💰 **نرخ‌های لحظه‌ای (نسخه Pro)**\n"
           f"⏰ `{MARKET_CACHE['last_sync']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{int(g.get('price', 0))/10:,.0f}` تومان\n"
           f"👑 سکه امامی: `{int(s.get('price', 0))/10:,.0f}` تومان\n"
           f"💵 دلار آمریکا: `{int(d.get('price', 0))/10:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{float(o.get('price', 0)):,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 مقایسه و تغییرات")
def handle_compare(message):
    sync_pro_data()
    g = MARKET_CACHE["gold"].get("IR_18K_GOLD", {})
    d = MARKET_CACHE["currency"].get("USD", {})

    def format_change(item):
        val = int(item.get('change_value', 0)) / 10
        pct = item.get('change_percent', 0)
        arrow = "📈" if float(pct) >= 0 else "📉"
        return f"{arrow} `{abs(val):,.0f}` تومان ({pct}%)"

    msg = (f"📊 **تحلیل تغییرات نسبت به روز قبل**\n\n"
           f"🔸 **طلا ۱۸ عیار:**\n{format_change(g)}\n\n"
           f"🔸 **دلار آمریکا:**\n{format_change(d)}\n\n"
           f"ℹ️ این اعداد نشان‌دهنده میزان گران یا ارزان شدن نسبت به قیمت بسته شده روز قبل است.")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_pro_data()
    try:
        gold_price = int(MARKET_CACHE["gold"]["IR_18K_GOLD"]["price"]) / 10
        usd_price = int(MARKET_CACHE["currency"]["USD"]["price"]) / 10
        ons_price = float(MARKET_CACHE["gold"]["XAU_USD"]["price"])
        
        # فرمول استاندارد حباب
        intrinsic = (ons_price * (usd_price * 10) * 0.75) / 31.1035 / 10
        bubble_pct = ((gold_price - intrinsic) / intrinsic) * 100
        
        msg = (f"⚪️ **تحلیل حباب طلا**\n\n"
               f"💎 ارزش ذاتی: `{intrinsic:,.0f}` تومان\n"
               f"💰 قیمت بازار: `{gold_price:,.0f}` تومان\n"
               f"🎈 میزان حباب: `{bubble_pct:.2f}%` " + ("🔴" if bubble_pct > 2 else "🟢"))
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ خطا در محاسبه حباب.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره خرید")
def handle_advice(message):
    sync_pro_data()
    # تحلیل ساده بر اساس حباب
    gold_price = int(MARKET_CACHE["gold"]["IR_18K_GOLD"]["price"]) / 10
    usd_price = int(MARKET_CACHE["currency"]["USD"]["price"]) / 10
    ons_price = float(MARKET_CACHE["gold"]["XAU_USD"]["price"])
    intrinsic = (ons_price * (usd_price * 10) * 0.75) / 31.1035 / 10
    
    if gold_price > intrinsic * 1.03:
        txt = "❌ **پیشنهاد:** فعلاً دست نگه دارید. بازار دارای حباب است و احتمال اصلاح قیمت وجود دارد."
    else:
        txt = "✅ **پیشنهاد:** قیمت‌ها به ارزش واقعی نزدیک هستند. زمان مناسبی برای خرید پله‌ای (بلندمدت) است."
    
    bot.send_message(message.chat.id, txt, parse_mode='Markdown')

# ----------------------------------------
#           *** ۴. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    
    try:
        bot.send_message(ADMIN_ID, "✅ **ربات نسخه Pro با موفقیت مستقر شد.**\nاتصال به سرویس حرفه‌ای BrsApi برقرار است.")
    except: pass
    
    server.run(host="0.0.0.0", port=PORT)
