import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import jdatetime 
import time

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

VERSION = "1.2.7"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
LIARA_AI_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiI2OTQ1Y2M1NzM2MzY3MzU2MWRhMWM1YzgiLCJ0eXBlIjoiYWlfa2V5IiwiaWF0IjoxNzY2MTgxOTc1fQ.aMxk_ih1L050h5HzYFUHVxnDudltKMepHw_jOiiPKvc"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# دیتای حافظه ربات
MARKET_DATA = {"items": {}, "update_time": "---", "update_date": "---"}

# ----------------------------------------
#           *** ۲. موتور واکشی دیتا ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    session = requests.Session()
    # تنظیم استراتژی تلاش مجدد برای جلوگیری از Connection Reset
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = session.get(url, headers=headers, timeout=20)
        res_json = response.json()
        
        temp_items = {}
        # استخراج بر اساس ساختار ارسالی شما (gold, currency, cryptocurrency)
        for cat in ['gold', 'currency', 'cryptocurrency']:
            if cat in res_json:
                for item in res_json[cat]:
                    symbol = item.get('symbol')
                    if symbol:
                        temp_items[symbol] = item
        
        if not temp_items:
            return False, "دیتای معتبری یافت نشد"

        MARKET_DATA["items"] = temp_items
        # استفاده از زمان خود سیستم برای دقت بیشتر در ایران
        now = jdatetime.datetime.now()
        MARKET_DATA["update_time"] = now.strftime("%H:%M")
        MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
        return True, "OK"
    except Exception as e:
        return False, str(e)

def get_p(symbol):
    """استخراج قیمت عددی از حافظه"""
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        # تبدیل قیمت به عدد (حذف کاما اگر وجود داشت)
        return float(str(price).replace(',', ''))
    except:
        return 0

def ask_liara_ai(user_query, system_context="تو مومو هستی، دستیار هوشمند طلا."):
    url = "https://api.liara.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {LIARA_AI_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama3-70b-8192", 
        "messages": [
            {"role": "system", "content": system_context},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.7
    }
    try:
        time.sleep(1) # محدودیت پلن رایگان
        response = requests.post(url, headers=headers, json=data, timeout=25)
        return response.json()['choices'][0]['message']['content']
    except:
        return None

# ----------------------------------------
#           *** ۳. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات بازار")
    markup.row("🧮 ماشین‌حساب", "⚪️ حباب طلا")
    markup.row("🧠 تحلیل هوشمند (AI)", "📉 تحلیل تکنیکال")
    markup.row("🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, error_msg = sync_market_data()
    icon = "🟢" if success else "🔴"
    
    welcome = (f"✨ **مومو، دستیار هوشمند شما فعال شد**\n\n"
               f"وضعیت اتصال: {icon}\n"
               f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n"
               f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
               f"سوالت رو بپرس یا از دکمه‌ها استفاده کن.")
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    gold_18 = get_p("IR_GOLD_18K")
    if gold_18 == 0:
        bot.reply_to(message, "⚠️ خطای شبکه. لطفاً دوباره روی 'شروع مجدد' بزنید.")
        return

    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"🥇 **طلا ۱۸ عیار:**\n\n`{gold_18:,.0f}` تومان\n\n"
           f"💵 **دلار آمریکا:**\n\n`{get_p('USD'):,.0f}` تومان\n\n"
           f"👑 **سکه امامی:**\n\n`{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 **انس جهانی طلا:**\n\n`{get_p('XAUUSD'):,.0f}` دلار\n\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات بازار")
def handle_changes(message):
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    prompt = f"امروز {MARKET_DATA['update_date']} است و طلا {p:,.0f} تومان است. قیمت‌های هفته و ماه قبل را پیدا کن و تحلیل کن."
    res = ask_liara_ai(prompt)
    bot.send_message(message.chat.id, f"📊 **گزارش تحلیل تاریخچه:**\n\n{res or 'خطا در ارتباط با هوش مصنوعی'}")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold, p_usd, p_ons = get_p("IR_GOLD_18K"), get_p("USD"), get_p("XAUUSD")
    if p_gold == 0 or p_usd == 0:
        bot.reply_to(message, "❌ دیتا ناقص است.")
        return
    intrinsic = (p_ons * p_usd * 0.75) / 31.1035
    bubble_pct = ((p_gold - intrinsic) / intrinsic) * 100
    icon = "🔴" if bubble_pct > 0 else "🟢"
    msg = (f"⚪️ **آنالیز حباب طلا**\n\n"
           f"💎 **ارزش واقعی:**\n\n`{intrinsic:,.0f}` تومان\n\n"
           f"📊 **قیمت بازار:**\n\n`{p_gold:,.0f}` تومان\n\n"
           f"{icon} **میزان حباب:**\n\n`{bubble_pct:.2f}%` ")
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
    except: bot.send_message(message.chat.id, "⚠️ عدد معتبر وارد کنید.")

def calc_final(message, w):
    try:
        sync_market_data()
        p = get_p("IR_GOLD_18K")
        total = (p * w) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"💰 **مبلغ فاکتور:**\n\n`{total:,.0f}` تومان", parse_mode='Markdown')
    except: bot.send_message(message.chat.id, "⚠️ خطا")

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند (AI)")
def handle_ai(message):
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    res = ask_liara_ai(f"طلا {get_p('IR_GOLD_18K')} تومان است. تحلیل کوتاه ۳ خطی بده.")
    bot.send_message(message.chat.id, f"🧠 **تحلیل مومو:**\n\n{res}")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال**\n\n🛡 حمایت: `{p*0.985:,.0f}`\n\n🚀 مقاومت: `{p*1.015:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_chat(message):
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    ans = ask_liara_ai(message.text)
    bot.reply_to(message, ans or "مومو فعلاً در دسترس نیست.")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index(): return "Momo v1.2.7 Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
