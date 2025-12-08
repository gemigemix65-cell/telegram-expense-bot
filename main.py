import telebot
from telebot import types as telegram_types # ⬅️ اصلاح ۱: تغییر نام types تلگرام
from flask import Flask, request
import json
import os
import speech_recognition as sr
from pydub import AudioSegment, exceptions as pydub_exceptions
import io
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from matplotlib import rcParams
import csv

# 🚀 اضافه شدن SDK Gemini
import google.genai as genai 
from google.genai import types # ⬅️ این types مخصوص Gemini است

# ----------------------------------------
#           *** ۱. تنظیمات عمومی و AI ***
# ----------------------------------------

# 🚨 امنیت: توکن‌ها را از متغیر محیطی می‌خواند.
TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")

# 💡 تنظیم مسیر دیسک پایدار (Volume Mount) در لیارا
# مسیر پیشنهادی: /app/data
DATA_FOLDER = "/app/data"  
DATA_FILE = os.path.join(DATA_FOLDER, "data.json")

# تضمین وجود پوشه دیسک
if not os.path.exists(DATA_FOLDER):
    try:
        os.makedirs(DATA_FOLDER, exist_ok=True)
    except Exception as e:
        print(f"Error creating data folder: {e}")

bot = telebot.TeleBot(TOKEN)
BUDGET_MONTHLY = 500000 

# --- تنظیمات Plotting فارسی ---
rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False 

# --- بارگذاری ایمن داده‌ها ---
DEFAULT_DATA = {
    "expenses": [], 
    "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"],
} 

data = DEFAULT_DATA.copy() 
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
            data["expenses"] = loaded_data.get("expenses", [])
            data["categories"] = loaded_data.get("categories", ["خوراک", "حمل و نقل", "تفریح", "سایر"])
    except json.JSONDecodeError:
        print(f"Error reading {DATA_FILE}. Starting with default data.")
        pass 
        
# ----------------------------------------
#           *** ۲. Agent هوشمند Gemini ***
# ----------------------------------------

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
else:
    print("⚠️ GEMINI_API_KEY تنظیم نشده است. ربات بدون تحلیل هوشمند کار خواهد کرد.")

SMART_AGENT_SYSTEM_PROMPT = """
شما یک Agent هوش مصنوعی هستید که وظیفه استخراج اطلاعات مالی از متن فارسی کاربر را دارید.
خروجی شما باید یک JSON Payload باشد که شامل:
- 'amount': مبلغ هزینه (به تومان، فقط عدد، بدون کاما یا واحد پول).
- 'category': دسته‌بندی اصلی هزینه (مثال: 'خوراک', 'حمل و نقل', 'تفریح'). اگر مشخص نبود، 'سایر' بگذارید.
- 'note': توضیحات یا یادداشت کامل تراکنش.
- 'tags': لیست تگ‌های موجود در متن (کلماتی که با # شروع می‌شوند، بدون #).

اگر مبلغ یافت نشد، 'amount' را صفر بگذارید.
"""

def smart_parse_amount_category(text):
    """استخراج مبلغ، دسته و یادداشت با استفاده از Gemini Agent."""
    if not GEMINI_API_KEY:
        return None 

    try:
        # فراخوانی Agent (Gemini 2.5 Flash رایگان)
        response = genai.client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[text],
            config=types.GenerateContentConfig( # ⬅️ استفاده از types مربوط به Gemini
                system_instruction=SMART_AGENT_SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        
        # تحلیل پاسخ JSON
        result = json.loads(response.text)
        
        # نرمال‌سازی خروجی
        amount = int(result.get("amount", 0))
        category = result.get("category", "سایر")
        note = result.get("note", category)
        tags = result.get("tags", [])
        
        return {
            "amount": amount,
            "category": category,
            "note": note,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            "tags": tags
        }

    except json.JSONDecodeError:
        print(f"Agent did not return valid JSON: {response.text}")
        return None
    except Exception as e:
        print(f"Gemini API Error in smart_parse: {e}")
        return None


# ----------------------------------------
#           *** ۳. توابع کمکی ***
# ----------------------------------------

def save_data():
    """ذخیره داده‌ها در فایل JSON روی دیسک پایدار"""
    # تاریخ‌گذاری آیتم‌های بدون تاریخ
    for item in data["expenses"]:
        if "date" not in item:
            item["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data_to_save = {
        "expenses": data["expenses"],
        "categories": data["categories"],
    }
    
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
         print(f"Error saving data to {DATA_FILE}: {e}")

def generate_report(expenses_list, period_name):
    """تابع تولید گزارش و نمودار."""
    if not expenses_list:
        return f"⚠️ هیچ هزینه‌ای در بازه **{period_name}** ثبت نشده است.", None, None

    totals = {}
    for exp in expenses_list:
        if "amount" in exp and "category" in exp:
            totals[exp["category"]] = totals.get(exp["category"], 0) + exp["amount"]

    report_text = f"📊 گزارش هزینه‌ها در **{period_name}**:\n"
    for cat, total in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        report_text += f"**{cat}**: {total:,.0f} تومان\n"
    
    total_spent = sum([exp.get("amount", 0) for exp in expenses_list])

    chart_path = None
    plot_totals = {k: v for k, v in totals.items() if v > 0} 
    
    if plot_totals:
        try:
            plt.figure(figsize=(6,6))
            labels = [k for k, v in plot_totals.items()]
            sizes = [v for v in plot_totals.values()]
            
            if sizes:
                plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
                plt.title(f"درصد هزینه‌ها در {period_name}", loc='right')
                plt.tight_layout()
                chart_path = os.path.join(DATA_FOLDER, "report_pie.png") # ذخیره نمودار در دیسک
                plt.savefig(chart_path)
                plt.close()
        except Exception as e:
            print(f"Error generating chart: {e}")
            
    return report_text, total_spent, chart_path


def main_menu(message):
    # ⬅️ استفاده از telegram_types برای کیبورد
    keyboard = telegram_types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    buttons = [
        "/report 📊 گزارش کلی",
        "/filter 🔍 گزارش دسته‌ای",
        "/undo 🔙 حذف آخر",
        "/addcat ➕ دسته‌بندی",
        "/setbudget 💰 بودجه",
        "/export 📤 خروجی CSV",
        "/clear 🔄 پاکسازی"
    ]
    
    keyboard.row(telegram_types.KeyboardButton(buttons[0]), telegram_types.KeyboardButton(buttons[1]))
    keyboard.row(telegram_types.KeyboardButton(buttons[2]), telegram_types.KeyboardButton(buttons[3]))
    keyboard.row(telegram_types.KeyboardButton(buttons[4]), telegram_types.KeyboardButton(buttons[5]))
    keyboard.row(telegram_types.KeyboardButton(buttons[6]))

    return keyboard

# ----------------------------------------
#            *** ۴. Handlers اصلی ***
# ----------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    keyboard = main_menu(message)
    bot.send_message(message.chat.id, "سلام! ربات حسابداری هوشمند آماده است.\n"
                                     "✅ هزینه‌ها را با **مبلغ و عنوان** (متن یا ویس) ثبت کنید. مثال: ۱۰۰۰۰ نان #نانوایی", reply_markup=keyboard)


@bot.message_handler(commands=['undo'])
def undo_last_expense(message):
    if not data["expenses"]:
        bot.send_message(message.chat.id, "لیست هزینه‌های شما خالی است.", reply_markup=main_menu(message))
        return

    # پیدا کردن آخرین آیتم بر اساس تاریخ
    all_items = []
    for item in data["expenses"]:
        try:
            # اگر تاریخ موجود نبود، تاریخ فعلی را در نظر بگیرید
            date_str = item.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            all_items.append((datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S"), item))
        except:
            all_items.append((datetime.min, item)) # آیتم‌های بدون تاریخ در اول قرار می‌گیرند
            
    if not all_items:
        bot.send_message(message.chat.id, "لیست هزینه‌های شما خالی است.", reply_markup=main_menu(message))
        return

    all_items.sort(key=lambda x: x[0], reverse=True) # مرتب‌سازی نزولی بر اساس تاریخ
    last_item = all_items[0][1] 
    
    # حذف آیتم از لیست اصلی
    try:
        data["expenses"].remove(last_item)
        save_data()
        bot.send_message(message.chat.id, f"✅ **آخرین هزینه حذف شد:** {last_item['amount']:,.0f} تومان در {last_item['category']}.", parse_mode='Markdown', reply_markup=main_menu(message))
    except ValueError:
           bot.send_message(message.chat.id, "❌ خطا در حذف آیتم هزینه. آیتم یافت نشد.", parse_mode='Markdown', reply_markup=main_menu(message))

# (توجه: کد سایر Commandها نظیر /report، /filter، /addcat، /setbudget و /export در اینجا قرار نگرفته است)

@bot.message_handler(commands=['clear'])
def clear_data(message):
    global data
    data["expenses"] = []
    data["categories"] = ["خوراک", "حمل و نقل", "تفریح", "سایر"]
    save_data()
    bot.reply_to(message, "✅ همه داده‌ها پاک شدند.", reply_markup=main_menu(message))

# ----------------------------------------
#           *** Handler برای ویس (Voice) ***
# ----------------------------------------

@bot.message_handler(content_types=['voice'])
def add_expense_voice(message):
    if not GEMINI_API_KEY:
        bot.send_message(message.chat.id, "⚠️ **خطا:** کلید GEMINI API تنظیم نشده. نمی‌توانم ویس را پردازش کنم.", reply_markup=main_menu(message))
        return
        
    bot.send_message(message.chat.id, "در حال پردازش ویس و تحلیل هوشمند...", reply_markup=telegram_types.ReplyKeyboardRemove())
    
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # استفاده از DATA_FOLDER برای ذخیره موقت فایل WAV
    temp_wav_path = os.path.join(DATA_FOLDER, "temp_voice.wav")
    text = ""
    
    try:
        # 1. تبدیل ogg/oga به wav 
        audio = AudioSegment.from_file(io.BytesIO(downloaded_file), format="ogg")
        audio.export(temp_wav_path, format="wav")
        
        # 2. تشخیص گفتار
        r = sr.Recognizer()
        with sr.AudioFile(temp_wav_path) as source:
            audio_data = r.record(source, duration=10) 
            text = r.recognize_google(audio_data, language="fa-IR", show_all=False, timeout=7)
            
    except pydub_exceptions.CouldntFindFFmpeg:
        bot.reply_to(message, "❌ **خطای عدم نصب FFmpeg:** پردازش ویس فعال نیست.", reply_markup=main_menu(message))
        return
    except Exception as e:
        print(f"Error in Voice Processing: {e}")
        bot.reply_to(message, "❌ **خطا در تبدیل ویس به متن:** صدای شما واضح نبود.", reply_markup=main_menu(message))
        return
    finally:
        # حذف فایل موقت
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)

    # 3. پردازش متن استخراج شده با Agent جدید
    exp = smart_parse_amount_category(text)
    
    if exp and exp["amount"] > 0:
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: **{exp['category']}**", parse_mode='Markdown')
            
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))
    else:
        bot.reply_to(message, f"❌ متن ویس قابل پردازش نبود یا مبلغ صفر بود. متن تشخیص داده شده: **{text}**", parse_mode='Markdown', reply_markup=main_menu(message))


# ----------------------------------------
#           *** Handler برای متن (Text) ***
# ----------------------------------------

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'), content_types=['text'])
def add_expense_text(message):
    
    exp = smart_parse_amount_category(message.text)
    
    if not exp or exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. (مثال: 150 هزار ناهار رستوران #تولد)", reply_markup=main_menu(message))
        return
        
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: **{exp['category']}**", parse_mode='Markdown')
        
    data["expenses"].append(exp)
    save_data()
    
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))


# ----------------------------------------
#           *** ۵. اجرای ربات در لیارا (Webhook) ***
# ----------------------------------------

PORT = int(os.environ.get('PORT', 3000))
WEBHOOK_URL_PATH = f"/{TOKEN}" 

server = Flask(__name__)

@server.route(WEBHOOK_URL_PATH, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        # ⬅️ اصلاح ۲: استفاده از telegram_types برای دریافت به‌روزرسانی
        update = telegram_types.Update.de_json(json_string) 
        
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 400

if __name__ == '__main__':
    # 🚨 چک کردن توکن و آدرس
    if not TOKEN:
        print("خطا: BOT_TOKEN تنظیم نشده است. ربات نمی‌تواند به API تلگرام متصل شود.")
    if not WEBHOOK_URL_BASE:
        print("خطا: WEBHOOK_URL تنظیم نشده است. ربات نمی‌تواند وب‌هوک را تنظیم کند.")

    if TOKEN and WEBHOOK_URL_BASE:
        bot.remove_webhook()
        # استفاده از آدرس کامل خوانده شده از محیط
        bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
        
        print(f"ربات در حالت Webhook شروع به کار کرد روی پورت {PORT}...")
        
        server.run(host="0.0.0.0", port=PORT)
