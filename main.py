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

VERSION = "1.0.7"

TOKEN = os.environ.get("BOT_TOKEN")
BRS_TOKEN = "BiEKVyewj956z3tnPMKtbSjUh2JLziPf" 
ADMIN_ID = "8221583925"

WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 3000))

server = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

MARKET_DATA = {"items": {}, "update_time": "به‌روزرسانی نشده"}

# ----------------------------------------
#           *** ۲. موتور واکشی با عیب‌یابی دقیق ***
# ----------------------------------------

def sync_market_data():
    global MARKET_DATA
    url = f"https://brsapi.ir/Api/Market/Gold_Currency.php?key={BRS_TOKEN}"
    
    try:
        # ارسال درخواست با هدرهای مرورگر برای جلوگیری از بلاک شدن
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=12)
        
        # بررسی فیزیکی پاسخ
        if not response.text or response.text.strip() == "":
            return False, "پاسخ سرور کاملاً خالی (Empty Body) است."

        if response.status_code != 200:
            return False, f"خطای HTTP: {response.status_code}"

        try:
            res_json = response.json()
        except Exception:
            return False, f"پاسخ سرور JSON معتبر نیست: {response.text[:50]}..."

        if not res_json.get('successful'):
            msg = res_json.get('message_error') or "نامشخص"
            return False, f"خطای منطقی API: {msg}"

        # استخراج دیتا
        temp_items = {}
        for sec in ['gold', 'currency']:
            data_block = res_json.get(sec, {})
            if isinstance(data_block, dict):
                for sub_list in data_block.values():
                    if isinstance(sub_list, list):
                        for item in sub_list:
                            symbol = item.get('symbol')
                            if symbol: temp_items[symbol] = item
        
        if not temp_items:
            return False, "دیتای طلا/ارز در JSON یافت نشد (لیست خالی)."

        MARKET_DATA["items"] = temp_items
        MARKET_DATA["update_time"] = jdatetime.datetime.now().strftime("%H:%M:%S")
        return True, "OK"

    except requests.exceptions.Timeout:
        return False, "زمان انتظار تمام شد (Timeout). سرور API کند است."
    except Exception as e:
        return False, f"خطای سیستمی: {str(e)}"

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
    markup.row("💰 قیمت لحظه‌ای", "📊 تغییرات")
    markup.row("⚪️ حباب طلا", "🔄 شروع مجدد")
    return markup

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "🔄 شروع مجدد")
def start(message):
    success, msg_result = sync_market_data()
    status = "🟢 آنلاین" if success else f"🔴 وضعیت: {msg_result}"
    
    welcome_text = (
        f"🤖 **ربات تحلیلگر بازار**\n"
        f"📦 نسخه استقرار: `{VERSION}`\n"
        f"--------------------------\n"
        f"وضعیت اتصال: {status}\n\n"
        f"اگر وضعیت قرمز است، کلید API را در پنل BrsApi چک کنید."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 قیمت لحظه‌ای")
def handle_price(message):
    bot.send_chat_action(message.chat.id, 'typing')
    success, error_msg = sync_market_data()
    
    if not success:
        bot.reply_to(message, f"⚠️ **خطا در واکشی دیتا:**\n`{error_msg}`")
        return

    # استخراج مقادیر
    p_gold = get_p("IR_GOLD_18K") / 10
    p_sekeh = get_p("IR_COIN_EMAMI") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")

    msg = (f"💰 **نرخ‌های بازار (تومان)**\n"
           f"📦 Ver: `{VERSION}` | ⏰ `{MARKET_DATA['update_time']}`\n\n"
           f"🥇 طلا ۱۸ عیار: `{p_gold:,.0f}`\n"
           f"👑 سکه امامی: `{p_sekeh:,.0f}`\n"
           f"💵 دلار آمریکا: `{p_usd:,.0f}`\n"
           f"🌐 انس جهانی: `{p_ons:,.2f}` دلار")
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 تغییرات")
def handle_changes(message):
    sync_market_data()
    g = MARKET_DATA["items"].get("IR_GOLD_18K", {})
    pct = g.get('change_percent', 0)
    bot.send_message(message.chat.id, f"📊 درصد تغییرات طلا: `{pct}%` (نسخه {VERSION})")

@bot.message_handler(func=lambda m: m.text == "⚪️ حباب طلا")
def handle_bubble(message):
    sync_market_data()
    p_gold = get_p("IR_GOLD_18K") / 10
    p_usd = get_p("USD") / 10
    p_ons = get_p("XAUUSD")
    
    if p_gold > 0 and p_usd > 0:
        intrinsic = (p_ons * (p_usd * 10) * 0.75) / 31.1035 / 10
        bubble = ((p_gold - intrinsic) / intrinsic) * 100
        bot.send_message(message.chat.id, f"⚪️ **تحلیل حباب**\nحباب فعلی: `{bubble:.2f}%`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ دیتا ناقص است.")

# ----------------------------------------
#           *** ۴. اجرای سرور ***
# ----------------------------------------

@server.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    bot.process_new_updates([telegram_types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

@server.route('/')
def index():
    return f"Status: Running v{VERSION}", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + "/" + TOKEN)
    server.run(host="0.0.0.0", port=PORT)
