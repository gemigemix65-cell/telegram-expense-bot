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

VERSION = "1.2.4"
TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BkNmf9UQe3W56CbbdBFw7bDV8LzAtGW6" 
LIARA_AI_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiI2OTQ1Y2M1NzM2MzY3MzU2MWRhMWM1YzgiLCJ0eXBlIjoiYWlfa2V5IiwiaWF0IjoxNzY2MTgxOTc1fQ.aMxk_ih1L050h5HzYFUHVxnDudltKMepHw_jOiiPKvc"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# دیتای پیش‌فرض برای جلوگیری از کرش کردن ربات
MARKET_DATA = {
    "items": {}, 
    "update_time": "در حال به‌روزرسانی...", 
    "update_date": "---"
}

# ----------------------------------------
#           *** ۲. توابع کمکی و هوش مصنوعی ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return False, f"خطای سرور قیمت: {response.status_code}"
            
        res_json = response.json()
        temp_items = {}
        
        # استخراج طلا و ارز با بررسی وجود کلیدها
        for category in ['gold', 'currency']:
            data_list = res_json.get(category, [])
            if isinstance(data_list, list):
                for item in data_list:
                    symbol = item.get('symbol')
                    if symbol:
                        temp_items[symbol] = item
        
        if not temp_items:
            return False, "دیتایی دریافت نشد."

        MARKET_DATA["items"] = temp_items
        now = jdatetime.datetime.now()
        MARKET_DATA["update_time"] = now.strftime("%H:%M:%S")
        MARKET_DATA["update_date"] = now.strftime("%Y/%m/%d")
        return True, "OK"
    except Exception as e:
        return False, str(e)

def get_p(symbol):
    item = MARKET_DATA["items"].get(symbol, {})
    price = item.get('price', 0)
    try:
        # پاکسازی قیمت از کاما و تبدیل به عدد
        clean_price = str(price).replace(',', '')
        return float(clean_price)
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
        time.sleep(1) # رعایت محدودیت ۱ درخواست در ثانیه
        response = requests.post(url, headers=headers, json=data, timeout=20)
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
    status_icon = "🟢" if success else "🔴"
    
    welcome = (f"✨ **به ایستگاه هوشمند مومو خوش آمدید**\n\n"
               f"وضعیت اتصال به بازار: {status_icon}\n\n"
               f"📅 تاریخ: `{MARKET_DATA['update_date']}`\n\n"
               f"⏰ ساعت: `{MARKET_DATA['update_time']}`\n\n"
               f"اگه مشکلی در قیمت‌ها بود، دکمه 'شروع مجدد' رو بزن.")
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "❌ متاسفانه در حال حاضر دریافت قیمت‌ها از منبع اصلی با خطا مواجه شده.")
        return

    msg = (f"💰 **قیمت‌های لحظه‌ای بازار**\n\n"
           f"🥇 **طلا ۱۸ عیار:**\n\n`{p_gold:,.0f}` تومان\n\n"
           f"💵 **دلار آمریکا:**\n\n`{get_p('USD'):,.0f}` تومان\n\n"
           f"👑 **سکه امامی:**\n\n`{get_p('IR_COIN_EMAMI'):,.0f}` تومان\n\n"
           f"🌐 **انس جهانی طلا:**\n\n`{get_p('XAUUSD'):,.2f}` دلار\n\n"
           f"⏰ به‌روزرسانی: `{MARKET_DATA['update_time']}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات بازار")
def handle_changes(message):
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    
    current_gold = get_p("IR_GOLD_18K")
    if current_gold == 0:
        bot.reply_to(message, "❌ خطا در دریافت دیتای فعلی برای مقایسه.")
        return

    prompt = (f"امروز {MARKET_DATA['update_date']} است. قیمت فعلی طلا {current_gold:,.0f} تومان است. "
              f"یک گزارش از تغییرات قیمت طلا و دلار در هفته و ماه گذشته پیدا کن و با فاصله بین خطوط بنویس.")
    
    ai_report = ask_liara_ai(prompt, "تو محقق بازار هستی.")
    
    if ai_report:
        bot.send_message(message.chat.id, f"📊 **گزارش نوسانات تاریخی**\n\n{ai_report}", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "⚠️ هوش مصنوعی موقتاً در دسترس نیست.")

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
           f"{icon} **درصد حباب:**\n\n`{bubble_pct:.2f}%` ")
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
    except:
        bot.send_message(message.chat.id, "⚠️ لطفاً عدد انگلیسی وارد کنید.")

def calc_final(message, w):
    try:
        sync_market_data()
        p = get_p("IR_GOLD_18K")
        total = (p * w) * (1 + float(message.text)/100)
        bot.send_message(message.chat.id, f"💰 **مبلغ فاکتور نهایی:**\n\n`{total:,.0f}` تومان", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "⚠️ خطا در محاسبه.")

@bot.message_handler(func=lambda m: m.text == "🧠 تحلیل هوشمند (AI)")
def handle_ai_analysis(message):
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K")
    if p_gold == 0:
        bot.reply_to(message, "❌ دیتایی برای تحلیل وجود ندارد.")
        return
    
    res = ask_liara_ai(f"قیمت طلا {p_gold:,.0f} تومان است. تحلیل کن بخرم؟")
    bot.send_message(message.chat.id, f"🧠 **نظر مومو:**\n\n{res or 'خطای هوش مصنوعی'}")

@bot.message_handler(func=lambda m: m.text == "📉 تحلیل تکنیکال")
def handle_tech(message):
    sync_market_data()
    p = get_p("IR_GOLD_18K")
    msg = (f"📉 **تحلیل تکنیکال**\n\n🛡 حمایت: `{p*0.985:,.0f}`\n\n🚀 مقاومت: `{p*1.015:,.0f}`")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_all_other_chats(message):
    # اگر پیام دکمه‌ای نبود، با هوش مصنوعی چت کن
    bot.send_chat_action(message.chat.id, 'typing')
    sync_market_data()
    ans = ask_liara_ai(message.text)
    bot.reply_to(message, ans or "مومو فعلاً نمی‌تونه حرف بزنه!")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Momo Bot v{VERSION} Fixed Active", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
