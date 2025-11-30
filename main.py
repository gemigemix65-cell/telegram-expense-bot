import telebot
from telebot import types
import json
import os
import speech_recognition as sr
from pydub import AudioSegment, exceptions as pydub_exceptions
import io
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from matplotlib import rcParams
import csv

# --- تنظیمات عمومی ---
TOKEN = "8221583925:AAEowlZ0gV-WnDen3awIHweJ0i93P5DqUpw"
bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"
BUDGET_MONTHLY = 500000 

DEFAULT_DATA = {
    "expenses": [], 
    "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"],
} 

# --- تنظیمات Plotting ---
rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False 

# --- بارگذاری ایمن داده‌ها ---
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
#          *** توابع کمکی ***
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

def parse_amount_category(text):
    """متن را به مبلغ، دسته‌بندی و تگ‌ها تفکیک می‌کند (فقط برای هزینه)."""
    text = text.replace("تومن", "").replace("ریال", "").replace(",", "").strip()
    words = text.split()
    if not words:
        return None

    try:
        amount = 0
        tags = []
        
        temp_words = []
        for word in words:
            if word.startswith('#'):
                tags.append(word[1:])
            else:
                temp_words.append(word)
        words = temp_words
        
        amount_index = -1
        for i, word in enumerate(words):
            if word.isdigit():
                amount = int(word)
                multiplier = 1
                
                if i + 1 < len(words):
                    next_word = words[i + 1].lower()
                    if next_word in ["هزار", "هزار تومان", "هزارتومن"]:
                        multiplier = 1000
                        amount_index = i + 1
                    elif next_word in ["میلیون", "ملیون"]:
                        multiplier = 1000000
                        amount_index = i + 1
                    elif next_word in ["تومان", "تومن", "ریال"]:
                        amount_index = i + 1
                    else:
                        amount_index = i
                else:
                    amount_index = i
                    
                amount *= multiplier
                
                remaining_text = " ".join(words[amount_index + 1:]).strip()
                
                explicit_category = None
                note = remaining_text
                
                if remaining_text:
                    first_word_after_amount = remaining_text.split()[0]
                    if first_word_after_amount in data["categories"]:
                        explicit_category = first_word_after_amount
                        note = " ".join(remaining_text.split()[1:]).strip()
                        
                # منطق ساخت دسته جدید یا قرار دادن در "سایر"
                if explicit_category:
                    category = explicit_category
                else:
                    if amount_index + 1 < len(words) and len(words[amount_index + 1:]) == 1:
                        category = words[amount_index + 1] 
                        note = category
                    elif remaining_text:
                        category = "سایر" 
                    else:
                        category = "سایر"
                        note = category

                if not note:
                    note = category
                    
                return {"amount": amount, "category": category, "note": note, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tags": tags}
                
                break 

    except Exception as e:
        print(f"Error parsing text: {e}")
        return None
    return None

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
    
    # 🔴 FIX 1: حذف نهایی دکمه‌های ناخواسته
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
#           *** Handlers ***
# ----------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    keyboard = main_menu(message)
    bot.send_message(message.chat.id, "سلام! ربات حسابداری هوشمند آماده است.\n"
                                      "✅ هزینه‌ها را با **مبلغ و عنوان** (متن یا ویس) ثبت کنید. مثال: ۱۰۰۰۰ نان #نانوایی", reply_markup=keyboard)


# 🚨 ثبت هزینه با ویس 🔴 FIX 2: مدیریت خطای صریح‌تر برای ffmpeg
@bot.message_handler(content_types=['voice'])
def add_expense_voice(message):
    bot.send_message(message.chat.id, "در حال پردازش ویس...", reply_markup=types.ReplyKeyboardRemove())
    
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_wav_path = "temp_voice.wav"
    
    try:
        # 1. تبدیل ogg/oga به wav 
        audio = AudioSegment.from_file(io.BytesIO(downloaded_file), format="ogg")
        audio.export(temp_wav_path, format="wav")
    except pydub_exceptions.CouldntFindFFmpeg:
        print("FFMPEG NOT FOUND ERROR")
        bot.reply_to(message, "❌ **خطای عدم نصب پیش‌نیاز (FFmpeg)**: برای تبدیل فایل صوتی تلگرام به متن، لازم است **FFmpeg** روی سیستم شما نصب و در PATH تعریف شده باشد.", reply_markup=main_menu(message))
        return
    except Exception as e:
        print(f"Error in pydub processing: {e}")
        bot.reply_to(message, "❌ خطا در پردازش فایل صوتی (تبدیل فرمت).", reply_markup=main_menu(message))
        return

    r = sr.Recognizer()
    text = ""
    try:
        # 2. تشخیص گفتار
        with sr.AudioFile(temp_wav_path) as source:
            audio_data = r.record(source, duration=10) 
            text = r.recognize_google(audio_data, language="fa-IR", show_all=False, timeout=7) 
            
    except sr.WaitTimeoutError:
        bot.reply_to(message, "❌ تشخیص گفتار بیشتر از حد مجاز (۷ ثانیه) طول کشید. لطفاً دوباره و واضح‌تر صحبت کنید.", reply_markup=main_menu(message))
        return
    except Exception as e:
        print(f"Error in Speech Recognition: {e}")
        # این خطا معمولاً نشان‌دهنده کیفیت پایین صدا یا عدم تشخیص توسط گوگل است.
        bot.reply_to(message, "❌ **خطا در تبدیل ویس به متن:** صدای شما برای گوگل واضح نبود یا فرمت ورودی نامناسب است.", reply_markup=main_menu(message))
        return
    finally:
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)

    # 3. پردازش متن استخراج شده
    exp = parse_amount_category(text)
    if exp and exp["amount"] > 0:
        
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: **{exp['category']}**", parse_mode='Markdown')
            
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))
    else:
        bot.reply_to(message, f"❌ متن ویس قابل پردازش نبود یا مبلغ صفر بود. متن تشخیص داده شده: **{text}**", parse_mode='Markdown', reply_markup=main_menu(message))


# 🚨 ثبت هزینه با متن (اولویت بالا)
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'), content_types=['text'])
def add_expense_text(message):
    exp = parse_amount_category(message.text)
    
    if not exp or exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. مثال: 150 هزار ناهار", reply_markup=main_menu(message))
        return
    
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: **{exp['category']}**", parse_mode='Markdown')
        
    data["expenses"].append(exp)
    save_data()
    
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))


# 1. پیاده‌سازی حذف آخرین تراکنش /undo
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


# اصلاح /addcat
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


# 3. اصلاح /report (فیلترهای تاریخ)
@bot.message_handler(commands=['report'])
def report_start(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("این ماه 📅", callback_data="report_month"))
    keyboard.add(types.InlineKeyboardButton("۳ ماه اخیر 🗓️", callback_data="report_3month"))
    keyboard.add(types.InlineKeyboardButton("۱۵ روز اخیر 📆", callback_data="report_15day"))
    keyboard.add(types.InlineKeyboardButton("۷ روز اخیر ⏳", callback_data="report_week"))
    keyboard.add(types.InlineKeyboardButton("همه زمان‌ها 🌐", callback_data="report_all"))
    
    bot.send_message(message.chat.id, "لطفاً بازه زمانی گزارش را انتخاب کنید:", reply_markup=keyboard)


# مدیریت Inline Keyboardها
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


# گزارش فیلتر شده دسته‌بندی
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
        report_text += f"  - {exp.get('amount', 0):,.0f} تومان ({exp.get('date', 'بدون تاریخ').split()[0]})"
        if exp.get('note') and exp.get('note') != exp.get('category'):
             report_text += f" | {exp['note']}"
        if exp.get('tags'):
             report_text += f" | تگ: {', '.join(exp['tags'])}\n"
        else:
             report_text += "\n"
        
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown', reply_markup=main_menu(message))


# --- اجرای ربات ---

if __name__ == '__main__':
    print("Bot started polling...")
    try:
        bot.polling(non_stop=True, interval=1) 
    except Exception as e:
        print(f"An error occurred during polling: {e}")
