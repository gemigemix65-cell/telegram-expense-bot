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

VERSION = "1.2.1"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
LIARA_AI_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiI2OTQ1Y2M1NzM2MzY3MzU2MWRhMWM1YzgiLCJ0eXBlIjoiYWlfa2V5IiwiaWF0IjoxNzY2MTgxOTc1fQ.aMxk_ih1L050h5HzYFUHVxnDudltKMepHw_jOiiPKvc"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. توابع کمکی و هوش مصنوعی ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    try:
        response = requests.get(url, timeout=10)
        res_json = response.json()
        temp_items = {}
        for category in ['gold', 'currency']:
            for item in res_json.get(category, []):
                symbol = item.get('symbol')
                if symbol: temp_items[symbol] = item
        MARKET_DATA["items"] = temp_items
        now = jdatetime.datetime.now()
        MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
        MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
        return True
    except: return False

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try: return float(str(price).replace(',', ''))
    except: return 0

def ask_liara_ai(user_query):
    """
    ارسال متن به هوش مصنوعی لیارا (پلن رایگان - فقط متن)
    """
    url = "https://api.liara.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {LIARA_AI_KEY}", "Content-Type": "application/json"}
    
    data = {
        "model": "llama3-70b-8192", 
        "messages": [
            {"role": "system", "content": "تو مومو هستی، دستیار هوشمند طلا. پاسخ‌ها کوتاه، صمیمی و فارسی باشد. از دیتای قیمتی که بهت داده میشه استفاده کن."},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.7
    }
    
    try:
        # رعایت محدودیت ۱ درخواست در ثانیه
        time.sleep(1) 
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return "ببخشید، الان نمی‌تونم به خوبی فکر کنم. بعداً امتحان کن!"
    except:
        return "ارتباط من با مغز هوشمندم کمی ضعیف شده. لطفاً از دکمه‌ها استفاده کن."

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 نمودار تغییرات")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("🧠 تحلیل هوشمند (AI)", "📉 تحلیل تکنیکال")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    sync_market_data()
    welcome = (f"✨ **مومو، دستیار هوشمند شما**\n\n"
               f"من آماده‌ام تا به سوالات شما درباره بازار طلا جواب بدم. "
               f"می‌تونید از دکمه‌ها استفاده کنید یا سوالتون رو مستقیم از من بپرسید.\n\n"
               f"📅 `{MARKET_DATA['update_date']}`\n"
               f"⏰ `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    msg = (f"💰 **قیمت‌های لحظه‌ای**\n\n"
           f"🥇 طلا ۱۸ عیار:\n`{p_gold:,.0f}` تومان\n\n"
           f"💵 دلار آزاد:\n`{get_p('USD'):,.0f}` تومان\n\n"
           f"👑 سکه امامی:\n`{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 انس جهانی:\n`{get_p('XAUUSD'):,.2f}` دلار\n\n"
           f"⏰ `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    icon = "🔴" if bubble_pct > 0 else "🟢"
    msg = (f"⚪️ **تحلیل حباب**\n\n"
           f"💎 ارزش ذاتی: `{intrinsic:,.0f}`\n\n"
           f"📊 قیمت بازار: `{p_gold:,.0f}`\n\n"
           f"{icon} حباب فعلی: `{bubble_pct:.2f}%` ")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند (AI)")
def handle_ai_btn(message):
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    p_usd = get_p("USD")
    prompt = f"قیمت طلا ۱۸ عیار الان {p_gold:,.0f} تومان و دلار {p_usd:,.0f} تومان است. با توجه به شرایط بازار ایران، یک تحلیل کوتاه و صمیمی برای خرید یا فروش بنویس."
    res = ask_liara_ai(prompt)
    bot.send_message(message.chat.id, f"🧠 **تحلیل مومو:**\n\n{res}")

# --- هندلر متون آزاد (چت با هوش مصنوعی) ---
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    # نادیده گرفتن متون دکمه‌ها که هندلر اختصاصی ندارند
    if message.text in ["🧮 ماشین‌حساب", "📊 نمودار تغییرات", "📉 تحلیل تکنیکال"]:
        if message.text == "🧮 ماشین‌حساب":
            msg = bot.send_message(message.chat.id, "⚖️ وزن طلا (گرم) را وارد کنید:")
            bot.register_next_step_handler(msg, calc_step_2)
        return

    # چت با هوش مصنوعی
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    context_query = f" (اطلاعات بازار: طلا {get_p('IR_GOLD_18K')} - دلار {get_p('USD')}) \n سوال کاربر: {message.text}"
    ans = ask_liara_ai(context_query)
    bot.reply_to(message, ans)

def calc_step_2(message):
    try:
        w = float(message.text)
        msg = bot.send_message(message.chat.id, "🛠 درصد سود/اجرت را وارد کنید:")
        bot.register_next_step_handler(msg, calc_final, w)
    except: bot.send_message(message.chat.id, "⚠️ عدد وارد کنید.")

def calc_final(message, w):
    try:
        sync_market_data()
        p = get_p("IR_GOLD_18K")
        total = (p * w) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"🧮 **نتیجه فاکتور:**\n\nقیمت نهایی: `{total:,.0f}` تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا در محاسبه.")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return "Momo AI Free Plan Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
