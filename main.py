import telebot
from telebot import types as telegram_types
from flask import Flask, request
import os
import requests
import json
import jdatetime 
import time
import re

# ----------------------------------------
#           *** ۱. تنظیمات پایه ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# حافظه کش برای قیمت‌ها
CACHE = {
    "data": {
        "gold_18k_gram": 0, "sekeh_emami": 0, "usd_rial": 0, 
        "ounce_usd": 0.0, "time": "بروزرسانی نشده"
    }
}

# ----------------------------------------
#           *** ۲. اسکرپینگ پیشرفته از Tala.ir ***
# ----------------------------------------

def fetch_from_tala_ir():
    global CACHE
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }

    try:
        # گام اول: دریافت صفحه اصلی قیمت طلا و سکه
        res = requests.get("https://www.tala.ir/price", headers=headers, timeout=15)
        content = res.text

        # استخراج طلا ۱۸ عیار
        gold_match = re.search(r'طلا ۱۸ عیار.*?<span class="price">([\d,]+)', content)
        if gold_match:
            CACHE['data']['gold_18k_gram'] = int(gold_match.group(1).replace(',', ''))

        # استخراج سکه امامی
        sekeh_match = re.search(r'سکه امامی.*?<span class="price">([\d,]+)', content)
        if sekeh_match:
            CACHE['data']['sekeh_emami'] = int(sekeh_match.group(1).replace(',', ''))

        # استخراج انس جهانی
        ons_match = re.search(r'انس طلا.*?<span class="price">([\d,.]+)', content)
        if ons_match:
            CACHE['data']['ounce_usd'] = float(ons_match.group(1).replace(',', ''))

        # گام دوم: دریافت قیمت دلار (جستجوی اختصاصی در بخش ارزها)
        # اگر در صفحه اصلی نبود، مستقیم به صفحه ارز می‌رویم
        res_currency = requests.get("https://www.tala.ir/price/currency", headers=headers, timeout=10)
        curr_content = res_currency.text
        
        # جستجوی دلار آمریکا (آزاد) با الگوی دقیق‌تر
        usd_match = re.search(r'دلار آمریکا.*?<span class="price">([\d,]+)', curr_content)
        if usd_match:
            CACHE['data']['usd_rial'] = int(usd_match.group(1).replace(',', ''))
        else:
            # جستجوی جایگزین اگر نام متفاوت بود
            usd_alt = re.search(r'دلار آزاد.*?<span class="price">([\d,]+)', curr_content)
            if usd_alt:
                CACHE['data']['usd_rial'] = int(usd_alt.group(1).replace(',', ''))

        # ثبت زمان بروزرسانی
        if CACHE['data']['gold_18k_gram'] > 0:
            CACHE['data']['time'] = jdatetime.datetime.now().strftime("%H:%M:%S")
            return CACHE['data']

    except Exception as e:
        print(f"❌ خطای اسکرپینگ Tala.ir: {e}")
    
    return CACHE['data']

# ----------------------------------------
#           *** ۳. موتور تحلیل منطقی ***
# ----------------------------------------

def get_logic_analysis(d):
    if d['gold_18k_gram'] < 1000 or d['usd_rial'] < 1000:
        return "⚠️ داده‌های قیمت ناقص است.", "لطفاً چند لحظه دیگر دوباره تلاش کنید."

    # فرمول ارزش ذاتی طلا ۱۸ عیار
    # (انس * دلار * 0.75) / 31.1035 / 10
    intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
    bubble = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
    
    if bubble > 2.5:
        summary = f"بازار دارای حباب مثبت ({bubble:.1f}%) است. قیمت طلا بالاتر از ارزش جهانی است."
        advice = "❌ در این سطح قیمت خرید توصیه نمی‌شود."
    elif -1 <= bubble <= 2.5:
        summary = "بازار در وضعیت تعادل قرار دارد. حباب ناچیز است."
        advice = "⚖️ زمان مناسب برای پس‌انداز بلندمدت."
    else:
        summary = f"بازار دارای حباب منفی ({bubble:.1f}%) است. طلا زیر قیمت واقعی است!"
        advice = "✅ فرصت عالی برای خرید."
        
    return summary, advice

# ----------------------------------------
#           *** ۴. هندلرهای تلگرام ***
# ----------------------------------------

def main_menu():
    markup = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 قیمت لحظه‌ای", "⚪️ حباب طلا")
    markup.row("🧠 مشاوره بازار")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        "🏅 **ربات تحلیلگر Tala.ir**\nقیمت‌های دقیق طلا و دلار تهران فعال شد.", 
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    d = fetch_from_tala_ir()
    if d['gold_18k_gram'] == 0:
        bot.reply_to(message, "⚠️ خطا در دریافت اطلاعات. لطفاً دوباره تلاش کنید.")
        return
    
    msg = (f"💰 **قیمت‌های لحظه‌ای (Tala.ir)**\n\n"
           f"🥇 طلا ۱۸ عیار: `{d['gold_18k_gram']:,.0f}` تومان\n"
           f"💵 دلار تهران: `{d['usd_rial']:,.0f}` تومان\n"
           f"👑 سکه امامی: `{d['sekeh_emami']:,.0f}` تومان\n"
           f"🌐 انس جهانی: `{d['ounce_usd']:,.2f}` دلار\n\n"
           f"⏰ بروزرسانی: {d['time']}")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    d = fetch_from_tala_ir()
    try:
        intrinsic = (d['ounce_usd'] * (d['usd_rial'] * 10) * 0.75) / 31.1035 / 10
        percent = ((d['gold_18k_gram'] - intrinsic) / intrinsic) * 100
        emoji = "🔴" if percent > 0 else "🟢"
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب طلا**\n\n📊 میزان حباب: `{percent:.2f}%` {emoji}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ اطلاعات دلار یا طلا ناقص است.")

@bot.message_handler(func=lambda m: m.text == "🧠 مشاوره بازار")
def handle_advice(message):
    bot.send_message(message.chat.id, "🤖 در حال استخراج و تحلیل داده‌ها...")
    d = fetch_from_tala_ir()
    summary, advice = get_logic_analysis(d)
    msg = f"✨ **تحلیل کارشناسی**\n\n📝 {summary}\n\n💡 **پیشنهاد:** {advice}"
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# ----------------------------------------
#           *** ۵. وب‌هوک و اجرا ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
