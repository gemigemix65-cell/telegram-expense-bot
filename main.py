import telebot
from telebot import types
import json
import os
import speech_recognition as sr
from pydub import AudioSegment
import io
import matplotlib.pyplot as plt
import numpy as np
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
    "income": [], 
    "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"],
    "goals": [], 
    "recurrences": []
} 

SMART_CATEGORIES = {
    "خوراک": ["غذا", "نان", "برنج", "میوه", "آبمیوه", "شام", "ناهار", "صبحانه", "سوپرمارکت", "فست فود", "املت", "پیتزا"],
    "حمل و نقل": ["تاکسی", "اسنپ", "تپسی", "اتوبوس", "مترو", "بنزین", "ماشین"],
    "تفریح": ["سینما", "کافه", "رستوران", "بلیط", "پارک"],
    "پوشاک": ["لباس", "کفش", "پیراهن", "کت", "شلوار", "جوراب"],
    "سیگار": ["سیگار", "وینستون", "بهمن", "مارلبورو", "توتون"]
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
            loaded_data.setdefault("income", [])
            loaded_data.setdefault("goals", [])
            loaded_data.setdefault("recurrences", [])
            data.update(loaded_data)
    except json.JSONDecodeError:
        print(f"Error reading {DATA_FILE}. Starting with default data.")
        pass 

# ----------------------------------------
#          *** توابع کمکی ***
# ----------------------------------------

def save_data():
    """ذخیره داده‌ها در فایل JSON"""
    for item in data["expenses"] + data["income"]:
        if "date" not in item:
            item["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_and_run_recurrences():
    """بررسی و اجرای هزینه‌های تکراری."""
    now = datetime.now()
    new_expenses_count = 0
    
    for rec in data["recurrences"]:
        try:
            last_run = datetime.strptime(rec['last_run'], "%Y-%m-%d")
            should_run = False
            
            if rec['frequency'] == 'ماهانه' and (now.year > last_run.year or (now.year == last_run.year and now.month > last_run.month)):
                should_run = True
            elif rec['frequency'] == 'هفتگی' and now.date() > last_run.date() and (now - last_run).days >= 7:
                 should_run = True
            
            if should_run:
                data["expenses"].append({
                    "amount": rec['amount'],
                    "category": rec['category'],
                    "note": f"هزینه تکراری: {rec['name']}",
                    "date": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "tags": ["تکراری"]
                })
                rec['last_run'] = now.strftime("%Y-%m-%d")
                new_expenses_count += 1
                
        except Exception as e:
            print(f"Error running recurrence {rec['name']}: {e}")
            continue
            
    if new_expenses_count > 0:
        save_data()
    return new_expenses_count

def guess_category_from_text(text, known_categories):
    """حدس می‌زند دسته‌بندی را از روی متن یادداشت"""
    text_lower = text.lower()
    for cat in known_categories:
        if cat.lower() in text_lower:
            return cat
    for category, keywords in SMART_CATEGORIES.items():
        if category in known_categories and any(kw in text_lower for kw in keywords):
            return category
    return "سایر"


def parse_amount_category(text, item_type="expense"):
    """متن را به مبلغ، دسته‌بندی/منبع و تگ‌ها تفکیک می‌کند."""
    text = text.replace("تومن", "").replace("ریال", "").replace(",", "").strip()
    words = text.split()
    if not words:
        return None

    try:
        amount = 0
        tags = []
        
        # استخراج تگ‌ها
        text_without_tags = []
        for word in words:
            if word.startswith('#'):
                tags.append(word[1:])
            else:
                text_without_tags.append(word)
        
        words = text_without_tags
        text = " ".join(words)
        
        for i, word in enumerate(words):
            if word.isdigit():
                amount = int(word)
                multiplier = 1
                
                if i + 1 < len(words):
                    if words[i + 1] in ["هزار", "هزار تومان", "هزارتومن"]:
                        multiplier = 1000
                    elif words[i + 1] in ["میلیون", "ملیون"]:
                        multiplier = 1000000
                amount *= multiplier
                
                start_index = i + 2 if multiplier > 1 or (i + 1 < len(words) and words[i+1].lower() in ["تومان", "تومن", "ریال"]) else i + 1
                
                remaining_text = " ".join(words[start_index:]).strip()
                
                first_word_after_amount = words[start_index] if start_index < len(words) else ""
                
                if item_type == "expense":
                    
                    if first_word_after_amount in data["categories"]:
                        explicit_category = first_word_after_amount
                        note = " ".join(words[start_index+1:]).strip() 
                    else:
                        explicit_category = ""
                        note = remaining_text

                    if not explicit_category or explicit_category.isdigit():
                        category = guess_category_from_text(note, data["categories"])
                    else:
                        category = explicit_category
                        
                    if not note:
                        note = category
                    
                    return {"amount": amount, "category": category, "note": note, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tags": tags}
                
                elif item_type == "income":
                    source = remaining_text if remaining_text else "درآمد متفرقه"
                    return {"amount": amount, "source": source, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tags": tags}

    except Exception:
        return None
    return None

def generate_report(expenses_list, period_name, message):
    """تابع تولید گزارش که اکنون در ابتدای فایل است."""
    if not expenses_list:
        return f"⚠️ هیچ هزینه‌ای در بازه **{period_name}** ثبت نشده است.", None, None

    totals = {}
    
    for exp in expenses_list:
        if "amount" in exp and "category" in exp:
            totals[exp["category"]] = totals.get(exp["category"], 0) + exp["amount"]

    report_text = f"📊 گزارش هزینه‌ها در **{period_name}**:\n"
    for cat, total in totals.items():
        report_text += f"**{cat}**: {total:,.0f} تومان\n"

    total_spent = sum([exp.get("amount", 0) for exp in expenses_list])
    
    # --- نمودار دایره‌ای دسته‌بندی‌ها ---
    chart_path = None
    if totals:
        plt.figure(figsize=(6,6))
        labels = [k for k, v in totals.items() if v > 0]
        sizes = [v for v in totals.values() if v > 0]
        
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
        "/income 💵 ثبت درآمد",
        "/undo 🔙 حذف آخر",
        "/goal 🎯 هدف‌گذاری",
        "/recur 🔁 تکرار هزینه",
        "/addcat ➕ دسته‌بندی",
        "/setbudget 💰 بودجه",
        "/history 📜 تاریخچه",
        "/export 📤 خروجی CSV",
        "/tips 💡 پیشنهاد هوشمند",
        "/clear 🔄 پاکسازی"
    ]
    
    keyboard.row(types.KeyboardButton(buttons[0]), types.KeyboardButton(buttons[1]))
    keyboard.row(types.KeyboardButton(buttons[2]), types.KeyboardButton(buttons[3]))
    keyboard.row(types.KeyboardButton(buttons[4]), types.KeyboardButton(buttons[5]))
    keyboard.row(types.KeyboardButton(buttons[6]), types.KeyboardButton(buttons[7]))
    keyboard.row(types.KeyboardButton(buttons[8]), types.KeyboardButton(buttons[9]))
    keyboard.row(types.KeyboardButton(buttons[10]), types.KeyboardButton(buttons[11]))

    return keyboard

# ----------------------------------------
#           *** Handlers ***
# ----------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    check_and_run_recurrences()
    keyboard = main_menu(message)
    bot.send_message(message.chat.id, "سلام! ربات حسابداری هوشمند آماده است.\n"
                                      "✅ هزینه‌ها و درآمدها را با **متن** یا **ویس** ثبت کنید. می‌توانید از **تگ** نیز استفاده کنید (مثال: ۱۰۰۰ نان #نانوایی)", reply_markup=keyboard)


# 🚨 ثبت هزینه با ویس (اولویت بالا)
@bot.message_handler(content_types=['voice'])
def add_expense_voice(message):
    bot.send_message(message.chat.id, "در حال پردازش ویس...", reply_markup=types.ReplyKeyboardRemove())
    file_info = bot.get_file(message.voice.file_id)
    downloaded = bot.download_file(file_info.file_path)
    
    try:
        audio = AudioSegment.from_ogg(io.BytesIO(downloaded))
        audio.export("temp.wav", format="wav")
    except Exception:
        bot.reply_to(message, "❌ خطا در پردازش فایل صوتی.", reply_markup=main_menu(message))
        return

    r = sr.Recognizer()
    text = ""
    try:
        with sr.AudioFile("temp.wav") as source:
            audio_data = r.record(source)
            # افزایش مدت زمان انتظار برای تشخیص
            text = r.recognize_google(audio_data, language="fa-IR", show_all=False, timeout=5) 
            os.remove("temp.wav")
    except sr.WaitTimeoutError:
        if os.path.exists("temp.wav"):
            os.remove("temp.wav")
        bot.reply_to(message, "❌ تشخیص گفتار بیشتر از حد مجاز طول کشید. لطفاً دوباره و واضح‌تر صحبت کنید.", reply_markup=main_menu(message))
        return
    except Exception:
        if os.path.exists("temp.wav"):
            os.remove("temp.wav")
        bot.reply_to(message, "❌ خطا در تبدیل ویس به متن (احتمالاً صدای واضحی نبود).", reply_markup=main_menu(message))
        return

    exp = parse_amount_category(text, item_type="expense")
    if exp and exp["amount"] > 0:
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
            
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))
    else:
        bot.reply_to(message, f"❌ متن ویس قابل پردازش نبود یا مبلغ صفر بود. متن تشخیص داده شده: {text}", reply_markup=main_menu(message))


# 🚨 ثبت هزینه با متن (اولویت بالا)
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'), content_types=['text'])
def add_expense_text(message):
    exp = parse_amount_category(message.text, item_type="expense")
    
    if not exp or exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. مثال: 150 هزار ناهار", reply_markup=main_menu(message))
        return
    
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
        
    data["expenses"].append(exp)
    save_data()
    
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))


# 4. پیاده‌سازی ثبت درآمد /income
@bot.message_handler(commands=['income'])
def income_step(message):
    msg = bot.send_message(message.chat.id, "لطفاً مبلغ و منبع درآمد را وارد کنید (مثال: 500000 حقوق ماهیانه):", 
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_income_step)

def process_income_step(message):
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ فرآیند ثبت درآمد لغو شد.", reply_markup=main_menu(message))
        return
        
    income = parse_amount_category(message.text, item_type="income")
    
    if not income or income["amount"] == 0:
        bot.send_message(message.chat.id, "❌ فرمت اشتباه یا مبلغ صفر است. مثال: 1500000 پاداش", reply_markup=main_menu(message))
        return
        
    data["income"].append(income)
    save_data()
    bot.send_message(message.chat.id, f"✅ درآمد ثبت شد: {income['amount']:,.0f} تومان (منبع: {income['source']})", reply_markup=main_menu(message))


# 1. پیاده‌سازی حذف آخرین تراکنش /undo
@bot.message_handler(commands=['undo'])
def undo_last_expense(message):
    if not data["expenses"] and not data["income"]:
        bot.send_message(message.chat.id, "لیست تراکنش‌های شما خالی است.", reply_markup=main_menu(message))
        return

    last_expense_date = datetime.min
    last_income_date = datetime.min
    
    if data["expenses"]:
        last_expense_date = datetime.strptime(data["expenses"][-1]["date"], "%Y-%m-%d %H:%M:%S")
    
    if data["income"]:
        last_income_date = datetime.strptime(data["income"][-1]["date"], "%Y-%m-%d %H:%M:%S")

    if last_expense_date > last_income_date:
        removed_item = data["expenses"].pop()
        save_data()
        bot.send_message(message.chat.id, f"✅ **آخرین هزینه حذف شد:** {removed_item['amount']:,.0f} تومان در {removed_item['category']}.", parse_mode='Markdown', reply_markup=main_menu(message))
    elif last_income_date > last_expense_date:
        removed_item = data["income"].pop()
        save_data()
        bot.send_message(message.chat.id, f"✅ **آخرین درآمد حذف شد:** {removed_item['amount']:,.0f} تومان (منبع: {removed_item['source']}).", parse_mode='Markdown', reply_markup=main_menu(message))
    else:
        bot.send_message(message.chat.id, "خطا در تشخیص آخرین تراکنش.", reply_markup=main_menu(message))


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


# ⚠️ اضافه کردن /setbudget و process_budget_step
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
        # حذف کاراکترهای اضافی و تبدیل به عدد
        amount_text = message.text.replace("تومان", "").replace("تومن", "").replace(",", "").strip()
        amount = int(amount_text)
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ مبلغ بودجه باید مثبت باشد.", reply_markup=main_menu(message))
            return

        BUDGET_MONTHLY = amount
        # در ربات‌های واقعی، باید این مقدار در فایل داده‌ها ذخیره شود. 
        # ما در اینجا برای سادگی، فقط متغیر سراسری را تغییر می‌دهیم.
        bot.send_message(message.chat.id, f"✅ بودجه ماهانه با موفقیت به **{BUDGET_MONTHLY:,.0f} تومان** تغییر یافت.", parse_mode='Markdown', reply_markup=main_menu(message))
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ ورودی نامعتبر. لطفاً فقط عدد وارد کنید (مثال: 1000000).", reply_markup=main_menu(message))
    except Exception:
        bot.send_message(message.chat.id, "❌ خطایی رخ داد.", reply_markup=main_menu(message))


@bot.message_handler(commands=['clear'])
def clear_data(message):
    global data
    data = {"expenses": [], "income": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"], "goals": [], "recurrences": []}
    save_data()
    bot.reply_to(message, "✅ همه داده‌ها پاک شدند.", reply_markup=main_menu(message))


# 3. اصلاح /report (فیلتر تاریخ)
@bot.message_handler(commands=['report'])
def report_start(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("این ماه 📅", callback_data="report_month"))
    keyboard.add(types.InlineKeyboardButton("۷ روز اخیر 🗓️", callback_data="report_week"))
    keyboard.add(types.InlineKeyboardButton("همه زمان‌ها 🌐", callback_data="report_all"))
    
    bot.send_message(message.chat.id, "لطفاً بازه زمانی گزارش را انتخاب کنید:", reply_markup=keyboard)


# 4. قابلیت گزارش تاریخی بر اساس ماه (/history)
@bot.message_handler(commands=['history'])
def history_start(message):
    keyboard = types.InlineKeyboardMarkup()
    for i in range(3):
        date_obj = datetime.now().replace(day=1) - timedelta(days=i * 30)
        month_name = date_obj.strftime("%B")
        callback_data = f"history_{date_obj.year}_{date_obj.month}"
        keyboard.add(types.InlineKeyboardButton(f"گزارش ماه {month_name}", callback_data=callback_data))
    
    bot.send_message(message.chat.id, "📜 گزارش ماهانه خود را انتخاب کنید:", reply_markup=keyboard)


# 🚨 مدیریت Inline Keyboardها و رفع خطای TypeError
@bot.callback_query_handler(func=lambda call: call.data.startswith('report_') or call.data.startswith('history_'))
def handle_report_callback(call):
    bot.answer_callback_query(call.id, "در حال تولید گزارش...")
    
    is_report = call.data.startswith('report_')
    
    if is_report:
        period = call.data.split('_')[1]
    else:
        parts = call.data.split('_')
        year = int(parts[1])
        month = int(parts[2])
        period = 'history'
        
    end_date = datetime.now()
    start_date = None
    period_name = ""

    if period == 'week':
        start_date = end_date - timedelta(days=7)
        period_name = "۷ روز اخیر"
    elif period == 'month':
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_name = "ماه جاری"
    elif period == 'all':
        start_date = datetime.min
        period_name = "همه زمان‌ها"
    elif period == 'history':
        start_date = datetime(year, month, 1)
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
        period_name = f"ماه {month}/{year}"

    filtered_expenses = []
    for exp in data["expenses"]:
        try:
            exp_date = datetime.strptime(exp["date"], "%Y-%m-%d %H:%M:%S")
            if exp_date >= start_date and exp_date <= end_date:
                filtered_expenses.append(exp)
        except:
            continue
            
    report_text, total_spent, chart_path = generate_report(filtered_expenses, period_name, call.message)
    
    # FIX: بررسی و تبدیل None به 0 برای جلوگیری از TypeError
    if total_spent is None:
        total_spent = 0
    
    if is_report and period != 'history':
        total_income = sum([inc.get("amount", 0) for inc in data["income"]])
        net_balance = total_income - total_spent 
        
        final_report = report_text
        final_report += f"\n\n💰 **مجموع درآمد**: {total_income:,.0f} تومان"
        final_report += f"\n💸 **ترازنامه خالص**: {net_balance:,.0f} تومان"
        
        if period == 'month':
            if total_spent > BUDGET_MONTHLY:
                final_report += f"\n\n🚨 **هشدار بودجه**: بودجه ماهانه ({BUDGET_MONTHLY:,.0f} تومان) رد شده است!"
            else:
                remaining = BUDGET_MONTHLY - total_spent
                final_report += f"\n\n💡 **بودجه باقی‌مانده این ماه**: {remaining:,.0f} تومان"
    else:
        final_report = report_text

    # ارسال گزارش و نمودار
    bot.edit_message_text(final_report, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=None)
    
    if chart_path:
        try:
            with open(chart_path, "rb") as f:
                bot.send_photo(call.message.chat.id, f)
            os.remove(chart_path)
        except Exception as e:
            bot.send_message(call.message.chat.id, "❌ خطا در ارسال نمودار دایره‌ای.")


# 1. قابلیت هدف‌گذاری (/goal)
@bot.message_handler(commands=['goal'])
def goal_start(message):
    msg = bot.send_message(message.chat.id, "🎯 نام، مبلغ هدف و تعداد ماه‌های باقیمانده را وارد کنید (مثال: گوشی جدید 10000000 6):", 
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_goal_step)

def process_goal_step(message):
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ فرآیند هدف‌گذاری لغو شد.", reply_markup=main_menu(message))
        return
        
    parts = message.text.split()
    if len(parts) < 3 or not parts[-2].isdigit() or not parts[-1].isdigit():
        bot.send_message(message.chat.id, "❌ فرمت اشتباه. مثال: گوشی جدید 10000000 6", reply_markup=main_menu(message))
        return

    try:
        months = int(parts.pop())
        amount = float(parts.pop())
        name = " ".join(parts)
        
        target_date = (datetime.now() + timedelta(days=months * 30)).strftime("%Y-%m-%d")
        
        data["goals"].append({
            "name": name, 
            "amount": amount, 
            "saved": 0, 
            "target_date": target_date, 
            "start_date": datetime.now().strftime("%Y-%m-%d")
        })
        save_data()
        
        required_monthly = amount / months if months > 0 else amount
        
        bot.send_message(message.chat.id, f"✅ هدف '{name}' تنظیم شد. برای رسیدن به آن تا {target_date}، باید ماهانه **{required_monthly:,.0f} تومان** پس‌انداز کنید.", parse_mode='Markdown', reply_markup=main_menu(message))
    except Exception:
        bot.send_message(message.chat.id, "❌ خطایی رخ داد.", reply_markup=main_menu(message))


# 2. قابلیت هزینه‌های تکراری (/recur)
@bot.message_handler(commands=['recur'])
def recur_start(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("ماهانه 🗓️", callback_data="recur_month"))
    keyboard.add(types.InlineKeyboardButton("هفتگی 📅", callback_data="recur_week"))
    
    bot.send_message(message.chat.id, "🔁 دوره تکرار هزینه جدید را انتخاب کنید:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('recur_'))
def handle_recur_callback(call):
    bot.answer_callback_query(call.id)
    frequency = "ماهانه" if call.data == "recur_month" else "هفتگی"
    
    msg = bot.send_message(call.message.chat.id, f"لطفاً نام، مبلغ و دسته‌بندی هزینه {frequency} را وارد کنید (مثال: اجاره 5000000 اجاره):", 
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_recur_step, frequency)

def process_recur_step(message, frequency):
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ فرآیند تکرار هزینه لغو شد.", reply_markup=main_menu(message))
        return
        
    parts = message.text.split()
    if len(parts) < 3 or not parts[-2].isdigit() or parts[-1] not in data["categories"]:
        bot.send_message(message.chat.id, f"❌ فرمت اشتباه. مثال: اجاره 5000000 اجاره (دسته بندی باید موجود باشد)", reply_markup=main_menu(message))
        return
        
    try:
        category = parts.pop()
        amount = float(parts.pop())
        name = " ".join(parts)
        
        data["recurrences"].append({
            "name": name, 
            "amount": amount, 
            "category": category, 
            "frequency": frequency, 
            "last_run": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        })
        save_data()
        
        bot.send_message(message.chat.id, f"✅ هزینه '{name}' به صورت {frequency} با موفقیت ثبت شد.", reply_markup=main_menu(message))
    except Exception:
        bot.send_message(message.chat.id, "❌ خطایی رخ داد.", reply_markup=main_menu(message))


# 5. قابلیت خروجی CSV (/export)
@bot.message_handler(commands=['export'])
def export_data(message):
    if not data["expenses"] and not data["income"]:
        bot.send_message(message.chat.id, "هیچ داده‌ای برای خروجی گرفتن وجود ندارد.", reply_markup=main_menu(message))
        return
        
    filename = "Financial_Report.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['نوع', 'مبلغ', 'دسته/منبع', 'یادداشت/توضیح', 'تگ‌ها', 'تاریخ']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        all_items = sorted(data["expenses"] + data["income"], key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d %H:%M:%S"))
        
        for item in all_items:
            row = {}
            if 'category' in item:
                row['نوع'] = 'هزینه'
                row['دسته/منبع'] = item['category']
                row['یادداشت/توضیح'] = item.get('note', '')
            else:
                row['نوع'] = 'درآمد'
                row['دسته/منبع'] = item['source']
                row['یادداشت/توضیح'] = ''
            
            row['مبلغ'] = item['amount']
            row['تگ‌ها'] = ', '.join(item.get('tags', []))
            row['تاریخ'] = item['date']
            writer.writerow(row)

    try:
        with open(filename, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📥 خروجی کامل داده‌ها (CSV)")
    except Exception:
        bot.send_message(message.chat.id, "❌ خطایی در ایجاد یا ارسال فایل رخ داد.")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


@bot.message_handler(commands=['tips'])
def give_economic_advice(message):
    total_spent_this_month = 0
    cigs_spent = 0
    food_spent = 0
    
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    for exp in data["expenses"]:
        try:
            exp_date = datetime.strptime(exp["date"], "%Y-%m-%d %H:%M:%S")
            if exp_date >= start_of_month:
                total_spent_this_month += exp.get("amount", 0)
                if exp.get("category") == "سیگار":
                    cigs_spent += exp.get("amount", 0)
                if exp.get("category") == "خوراک":
                    food_spent += exp.get("amount", 0)
        except:
            continue
            
    advice_text = "💡 **پیشنهادات هوشمند اقتصادی برای شما:**\n\n"
    
    if cigs_spent > 50000:
        advice_text += f"🚬 هزینه **سیگار** شما این ماه {cigs_spent:,.0f} تومان بوده است.\nبا کاهش این هزینه، علاوه بر **سالمتی**، می‌توانید ماهانه این مبلغ را **پس‌انداز** کنید.\n\n"
        
    if total_spent_this_month > BUDGET_MONTHLY * 0.7:
        advice_text += "⚠️ **هشدار بودجه**: شما ۷۰٪ از بودجه ماهانه خود را مصرف کرده‌اید. در روزهای باقیمانده، مراقب **هزینه‌های غیرضروری** باشید.\n\n"
        
    if food_spent > total_spent_this_month * 0.4 and total_spent_this_month > 0:
        advice_text += "🍔 هزینه **خوراک** شما درصد بالایی از کل هزینه‌ها است. سعی کنید برای وعده‌های ناهار از **غذای خانگی** استفاده کنید تا هم **مقرون به صرفه** باشد و هم **سالم‌تر**.\n\n"
        
    if data["goals"]:
        goal = data["goals"][0] 
        # محاسبه ساده برای ماهانه مورد نیاز
        remaining_months = max(1, (datetime.strptime(goal['target_date'], "%Y-%m-%d").year - datetime.now().year) * 12 + (datetime.strptime(goal['target_date'], "%Y-%m-%d").month - datetime.now().month))
        needed_monthly = (goal['amount'] - goal['saved']) / remaining_months
        
        advice_text += f"🎯 **هدف شما ({goal['name']})**: شما نیاز دارید ماهانه {needed_monthly:,.0f} تومان پس‌انداز کنید. مطمئن شوید که بخشی از درآمدتان را به این هدف اختصاص می‌دهید.\n\n"
        
    if not data["goals"] and total_spent_this_month <= BUDGET_MONTHLY * 0.7:
        advice_text += "✅ عملکرد شما خوب است! برای بهبود بیشتر، می‌توانید در پایان ماه، **۱۰٪ از درآمد خالص** خود را به طور خودکار به یک **حساب پس‌انداز بلندمدت** منتقل کنید.\n\n"
        
    bot.send_message(message.chat.id, advice_text, parse_mode='Markdown', reply_markup=main_menu(message))


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
    
    for exp in filtered_expenses[-5:]:
        report_text += f"  - {exp.get('amount', 0):,.0f} تومان ({exp.get('date', 'بدون تاریخ').split()[0]})"
        if exp.get('note'):
             report_text += f" | {exp['note']}"
        if exp.get('tags'):
             report_text += f" | تگ: {', '.join(exp['tags'])}\n"
        else:
             report_text += "\n"
        
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown', reply_markup=main_menu(message))


# --- اجرای ربات ---

if __name__ == '__main__':
    check_and_run_recurrences()
    print("Bot started polling...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"An error occurred during polling: {e}")
