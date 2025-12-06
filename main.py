import telebot
from telebot import types
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
from google.genai import types

# ----------------------------------------
#           *** تنظیمات عمومی و AI ***
# ----------------------------------------

# 🚨 امنیت: توکن‌ها را از متغیر محیطی (Environment Variable) لیارا می‌خواند.
TOKEN = os.environ.get("BOT_TOKEN", "8221583925:AAEowlZ0gV-WnDen3awIHweJ0i93P5DqUpw")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"
BUDGET_MONTHLY = 500000 

# --- تنظیمات Plotting ---
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
#           *** Agent هوشمند Gemini ***
# ----------------------------------------

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
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
        # اگر کلید API تنظیم نشده، از ادامه خودداری می‌کند.
        return None 

    try:
        # فراخوانی Agent (Gemini 2.5 Flash رایگان)
        response = genai.client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[text],
            config=types.GenerateContentConfig(
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
#           *** توابع کمکی (اصلاح شده) ***
# ----------------------------------------

def save_data():
    """ذخیره داده‌ها در فایل JSON"""
    for item in data["expenses"]:
        if "date" not in item:
            item["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data_to_save = {
        "expenses": data["expenses"],
        "categories": data["categories"],
    }
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

# 🚨 تابع parse_amount_category قدیمی حذف شد، زیرا از Agent هوشمند استفاده می‌کنیم.
# ... (توابع generate_report و main_menu و سایر توابع کمکی شما بدون تغییر باقی می‌مانند)

def generate_report(expenses_list, period_name):
    """تابع تولید گزارش."""
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

    # --- نمودار دایره‌ای دسته‌بندی‌ها ---
    chart_path = None
    plot_totals = {k: v for k, v in totals.items() if v > 0} 
    
    if plot_totals:
        plt.figure(figsize=(6,6))
        labels = [k for k, v in plot_totals.items()]
        sizes = [v for v in plot_totals.values()]
        
        if sizes:
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
            plt.title(f"درصد هزینه‌ها در {period_name}", loc='right')
            plt.tight_layout()
            chart_path = "report_pie.png"
            plt.savefig(chart_path)
            plt.close()

    return report_text, total_spent, chart_path


def main_menu(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    buttons = [
        "/report 📊 گزارش کلی",
        "/filter 🔍 گزارش دسته‌ای",
        "/undo 🔙 حذف آخر",
        "/addcat ➕ دسته‌بندی",
        "/setbudget 💰 بودجه",
        "/export 📤 خروجی CSV",
        "/clear 🔄 پاکسازی"
    ]
    
    keyboard.row(types.KeyboardButton(buttons[0]), types.KeyboardButton(buttons[1]))
    keyboard.row(types.KeyboardButton(buttons[2]), types.KeyboardButton(buttons[3]))
    keyboard.row(types.KeyboardButton(buttons[4]), types.KeyboardButton(buttons[5]))
    keyboard.row(types.KeyboardButton(buttons[6]))


    return keyboard

# ----------------------------------------
#            *** Handlers (هوشمند شده) ***
# ----------------------------------------

# ... (کدهای handlers قدیمی مانند /start، /undo، /addcat، /setbudget، /clear، /report، /filter را اینجا قرار دهید)

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

    all_items = []
    for item in data["expenses"]:
        try:
            all_items.append((datetime.strptime(item["date"], "%Y-%m-%d %H:%M:%S"), item))
        except:
            continue
            
    if not all_items:
        bot.send_message(message.chat.id, "لیست هزینه‌های شما خالی است.", reply_markup=main_menu(message))
        return

    all_items.sort(key=lambda x: x[0])
    last_item = all_items[-1][1] 
    
    removed_item = last_item

    try:
        data["expenses"].remove(removed_item)
        save_data()
        bot.send_message(message.chat.id, f"✅ **آخرین هزینه حذف شد:** {removed_item['amount']:,.0f} تومان در {removed_item['category']}.", parse_mode='Markdown', reply_markup=main_menu(message))
    except ValueError:
           bot.send_message(message.chat.id, "❌ خطا در حذف آیتم هزینه. آیتم یافت نشد.", parse_mode='Markdown', reply_markup=main_menu(message))


@bot.message_handler(commands=['addcat'])
def add_category(message):
    msg = bot.send_message(message.chat.id, "لطفاً نام دسته‌بندی جدید را وارد کنید (مثال: پوشاک):", 
                             reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_category_step)

def process_category_step(message):
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ فرآیند اضافه کردن دسته لغو شد.", reply_markup=main_menu(message))
        return
        
    category = message.text.strip()
    if not category or category.isdigit():
        bot.send_message(message.chat.id, "❌ نام دسته‌بندی معتبر نیست. لطفاً مجدداً امتحان کنید.", reply_markup=main_menu(message))
        return
        
    if category not in data["categories"]:
        data["categories"].append(category)
        save_data()
        bot.send_message(message.chat.id, f"✅ دسته‌بندی '{category}' اضافه شد!", reply_markup=main_menu(message))
    else:
        bot.send_message(message.chat.id, "این دسته‌بندی قبلاً موجود است.", reply_markup=main_menu(message))


@bot.message_handler(commands=['setbudget'])
def set_budget(message):
    msg = bot.send_message(message.chat.id, "لطفاً مبلغ بودجه ماهانه جدید را وارد کنید (مثال: 1000000 تومان):", 
                             reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_budget_step)

def process_budget_step(message):
    global BUDGET_MONTHLY
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ فرآیند تعیین بودجه لغو شد.", reply_markup=main_menu(message))
        return
        
    try:
        amount_text = message.text.replace("تومان", "").replace("تومن", "").replace(",", "").strip()
        amount = int(amount_text)
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ مبلغ بودجه باید مثبت باشد.", reply_markup=main_menu(message))
            return

        BUDGET_MONTHLY = amount
        bot.send_message(message.chat.id, f"✅ بودجه ماهانه با موفقیت به **{BUDGET_MONTHLY:,.0f} تومان** تغییر یافت.", parse_mode='Markdown', reply_markup=main_menu(message))
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ ورودی نامعتبر. لطفاً فقط عدد وارد کنید (مثال: 1000000).", reply_markup=main_menu(message))
    except Exception:
        bot.send_message(message.chat.id, "❌ خطایی رخ داد.", reply_markup=main_menu(message))


@bot.message_handler(commands=['clear'])
def clear_data(message):
    global data
    data["expenses"] = []
    data["categories"] = ["خوراک", "حمل و نقل", "تفریح", "سایر"]
    save_data()
    bot.reply_to(message, "✅ همه داده‌ها پاک شدند.", reply_markup=main_menu(message))


@bot.message_handler(commands=['report'])
def report_start(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("این ماه 📅", callback_data="report_month"))
    keyboard.add(types.InlineKeyboardButton("۳ ماه اخیر 🗓️", callback_data="report_3month"))
    keyboard.add(types.InlineKeyboardButton("۱۵ روز اخیر 📆", callback_data="report_15day"))
    keyboard.add(types.InlineKeyboardButton("۷ روز اخیر ⏳", callback_data="report_week"))
    keyboard.add(types.InlineKeyboardButton("همه زمان‌ها 🌐", callback_data="report_all"))
    
    bot.send_message(message.chat.id, "لطفاً بازه زمانی گزارش را انتخاب کنید:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('report_'))
def handle_report_callback(call):
    bot.answer_callback_query(call.id, "در حال تولید گزارش...")
    
    period = call.data.split('_')[1]
    
    end_date = datetime.now()
    start_date = None
    period_name = ""

    if period == 'week':
        start_date = end_date - timedelta(days=7)
        period_name = "۷ روز اخیر"
    elif period == '15day':
        start_date = end_date - timedelta(days=15)
        period_name = "۱۵ روز اخیر"
    elif period == '3month':
        start_date = end_date - timedelta(days=90)
        period_name = "۳ ماه اخیر"
    elif period == 'month':
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_name = "ماه جاری"
    elif period == 'all':
        start_date = datetime.min
        period_name = "همه زمان‌ها"

    filtered_expenses = []
    for exp in data["expenses"]:
        try:
            exp_date = datetime.strptime(exp["date"], "%Y-%m-%d %H:%M:%S")
            if start_date <= exp_date <= end_date:
                filtered_expenses.append(exp)
        except:
            continue
            
    report_text, total_spent, chart_path = generate_report(filtered_expenses, period_name)
    
    if total_spent is None:
        total_spent = 0
    
    final_report = report_text
    
    if period == 'month':
        if total_spent > BUDGET_MONTHLY:
            final_report += f"\n\n🚨 **هشدار بودجه**: بودجه ماهانه ({BUDGET_MONTHLY:,.0f} تومان) رد شده است!"
        else:
            remaining = BUDGET_MONTHLY - total_spent
            final_report += f"\n\n💡 **بودجه باقی‌مانده این ماه**: {remaining:,.0f} تومان"
    
    final_report += f"\n\n**💸 مجموع هزینه‌ها در این بازه**: {total_spent:,.0f} تومان"


    bot.edit_message_text(final_report, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=None)
    
    if chart_path:
        try:
            with open(chart_path, "rb") as f:
                bot.send_photo(call.message.chat.id, f)
            os.remove(chart_path)
        except Exception as e:
            bot.send_message(call.message.chat.id, "❌ خطا در ارسال نمودار دایره‌ای.")


@bot.message_handler(commands=['filter'])
def filter_report(message):
    if not data["expenses"]:
        bot.reply_to(message, "هیچ هزینه‌ای ثبت نشده تا گزارش فیلتر شود.", reply_markup=main_menu(message))
        return
        
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    categories = sorted(data["categories"])
    
    row = []
    for i, cat in enumerate(categories):
        row.append(types.KeyboardButton(cat))
        if len(row) == 3 or i == len(categories) - 1:
            keyboard.add(*row)
            row = []
    
    keyboard.add(types.KeyboardButton("لغو ✖️"))
    
    msg = bot.send_message(message.chat.id, "🔍 دسته‌بندی مورد نظر برای گزارش را انتخاب کنید:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_filter_step)

def process_filter_step(message):
    if message.text and (message.text.startswith('/') or message.text == "لغو ✖️"):
        bot.send_message(message.chat.id, "❌ فرآیند فیلتر لغو شد.", reply_markup=main_menu(message))
        return

    chosen_category = message.text.strip()
    
    if chosen_category not in data["categories"]:
        bot.send_message(message.chat.id, "❌ دسته‌بندی مورد نظر یافت نشد.", reply_markup=main_menu(message))
        return

    filtered_expenses = [exp for exp in data["expenses"] if exp.get("category") == chosen_category]
    
    if not filtered_expenses:
        bot.send_message(message.chat.id, f"⚠️ هیچ هزینه‌ای برای دسته‌بندی **{chosen_category}** ثبت نشده است.", parse_mode='Markdown', reply_markup=main_menu(message))
        return
        
    total_spent = sum([exp.get("amount", 0) for exp in filtered_expenses])
    
    report_text = f"📊 گزارش فیلتر شده برای **{chosen_category}**:\n"
    report_text += f"💰 **مجموع هزینه‌ها**: {total_spent:,.0f} تومان\n"
    report_text += "\n📝 **آخرین ۵ تراکنش**:\n"
    
    filtered_expenses.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d %H:%M:%S"), reverse=True)
    
    for exp in filtered_expenses[:5]:
        report_text += f"  - {exp.get('amount', 0):,.0f} تومان ({exp.get('date', 'بدون تاریخ').split()[0]})"
        if exp.get('note') and exp.get('note') != exp.get('category'):
             report_text += f" | {exp['note']}"
        if exp.get('tags'):
             report_text += f" | تگ: {', '.join(exp['tags'])}\n"
        else:
             report_text += "\n"
        
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown', reply_markup=main_menu(message))

# ----------------------------------------
#           *** Handler برای ویس (Voice) ***
# ----------------------------------------

@bot.message_handler(content_types=['voice'])
def add_expense_voice(message):
    if not GEMINI_API_KEY:
        bot.send_message(message.chat.id, "⚠️ **خطا:** کلید GEMINI API تنظیم نشده. نمی‌توانم ویس را پردازش کنم.", reply_markup=main_menu(message))
        return
        
    bot.send_message(message.chat.id, "در حال پردازش ویس و تحلیل هوشمند...", reply_markup=types.ReplyKeyboardRemove())
    
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_wav_path = "temp_voice.wav"
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
        bot.reply_to(message, "❌ **خطای عدم نصب پیش‌نیاز (FFmpeg)**: برای تبدیل فایل صوتی تلگرام به متن، لازم است **FFmpeg** روی سیستم شما نصب باشد.", reply_markup=main_menu(message))
        return
    except Exception as e:
        print(f"Error in Voice Processing: {e}")
        bot.reply_to(message, "❌ **خطا در تبدیل ویس به متن:** صدای شما واضح نبود.", reply_markup=main_menu(message))
        return
    finally:
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
    
    if not exp:
        # اگر GEMINI_API_KEY تنظیم نشده باشد
        bot.reply_to(message, "❌ خطا: سرویس هوشمند غیرفعال است یا ورودی نامعتبر.", reply_markup=main_menu(message))
        return
    
    if exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. (مثال: 150 هزار ناهار رستوران #تولد)", reply_markup=main_menu(message))
        return
        
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: **{exp['category']}**", parse_mode='Markdown')
        
    data["expenses"].append(exp)
    save_data()
    
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))


# ----------------------------------------
#           *** اجرای ربات در لیارا (Webhook) ***
# ----------------------------------------

APP_NAME = os.environ.get("APP_NAME", "my-telegram-bot") 
PORT = int(os.environ.get('PORT', 3000))

WEBHOOK_URL_BASE = f"https://{APP_NAME}.liara.run" 
WEBHOOK_URL_PATH = f"/{TOKEN}" 

server = Flask(__name__)

@server.route(WEBHOOK_URL_PATH, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string) 
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 400

if __name__ == '__main__':
    if not TOKEN or not APP_NAME:
        print("خطا: BOT_TOKEN یا APP_NAME تنظیم نشده است. ربات راه‌اندازی نشد.")
    else:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
        
        print(f"ربات در حالت Webhook شروع به کار کرد روی پورت {PORT}...")
        
        server.run(host="0.0.0.0", port=PORT)
