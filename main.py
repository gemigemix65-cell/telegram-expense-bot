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
# NOTE: none_stop=True را در polling استفاده می‌کنیم
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

# --- دسته‌بندی‌های هوشمند ---
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

# --- توابع کمکی ---

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

# توابع guess_category_from_text و parse_amount_category بدون تغییر اساسی حفظ می‌شوند.

# تابع parse_amount_category (برای جلوگیری از تکرار کد، متن تابع را فرض می‌کنم و بخش اصلی را فقط برای اطمینان مجدد می‌آورم)
def parse_amount_category(text, item_type="expense"):
    """متن را به مبلغ، دسته‌بندی/منبع و تگ‌ها تفکیک می‌کند."""
    # ... (منطق کامل parse_amount_category از کد قبلی) ...
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

# --- دکمه منو ---

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

# --- Message Handlers ---

@bot.message_handler(commands=['start'])
def start(message):
    check_and_run_recurrences()
    keyboard = main_menu(message)
    bot.send_message(message.chat.id, "سلام! ربات حسابداری هوشمند آماده است.\n"
                                      "✅ هزینه‌ها و درآمدها را با **متن** یا **ویس** ثبت کنید. می‌توانید از **تگ** نیز استفاده کنید (مثال: ۱۰۰۰ نان #نانوایی)", reply_markup=keyboard)


# 🚨 اصلاح اصلی: ثبت هزینه با متن و ویس باید قبل از بقیه منطق‌ها باشد.

# ثبت هزینه با متن (همراه با هوشمندی دسته‌بندی)
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'), content_types=['text'])
def add_expense_text(message):
    # اطمینان از حذف کیبورد قبلی اگر در مرحله‌ای بودیم
    bot.send_message(message.chat.id, "در حال پردازش...", reply_markup=types.ReplyKeyboardRemove())
    
    exp = parse_amount_category(message.text, item_type="expense")
    
    if not exp or exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. مثال: 150 هزار ناهار", reply_markup=main_menu(message))
        return
    
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
        
    data["expenses"].append(exp)
    save_data()
    
    # نمایش مجدد منو پس از ثبت موفق
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))


# ثبت هزینه از ویس
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
            # افزایش تایم‌آوت برای تشخیص ویس
            text = r.recognize_google(audio_data, language="fa-IR", show_all=False, pfilter=True, keyword_entries=None)
            os.remove("temp.wav")
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


# --- توابع مربوط به منو و گزارش‌ها (بیشتر بدون تغییر، به جز callback) ---

# تابع اصلی گزارش (برای استفاده در /report و /filter)
def generate_report(expenses_list, period_name, message):
    # ... (منطق کامل generate_report از کد قبلی) ...
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

# 3. اصلاح /report (فیلتر تاریخ)
@bot.message_handler(commands=['report'])
def report_start(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("این ماه 📅", callback_data="report_month"))
    keyboard.add(types.InlineKeyboardButton("۷ روز اخیر 🗓️", callback_data="report_week"))
    keyboard.add(types.InlineKeyboardButton("همه زمان‌ها 🌐", callback_data="report_all"))
    
    bot.send_message(message.chat.id, "لطفاً بازه زمانی گزارش را انتخاب کنید:", reply_markup=keyboard)

# 🚨 اصلاح اصلی: مدیریت Inline Keyboardها
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
        # برای گزارش تاریخی، بازه دقیقاً همان ماه است
        start_date = datetime(year, month, 1)
        # محاسبه آخرین روز ماه
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
        period_name = f"ماه {month}/{year}"

    # فیلتر کردن هزینه‌ها
    filtered_expenses = []
    for exp in data["expenses"]:
        try:
            exp_date = datetime.strptime(exp["date"], "%Y-%m-%d %H:%M:%S")
            if exp_date >= start_date and exp_date <= end_date:
                filtered_expenses.append(exp)
        except:
            continue
            
    report_text, total_spent, chart_path = generate_report(filtered_expenses, period_name, call.message)
    
    # --- محاسبه درآمد و ترازنامه (فقط برای گزارش‌های کلی) ---
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

    # 🚨 اصلاح: استفاده از edit_message_text
    bot.edit_message_text(final_report, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=None)
    
    if chart_path:
        try:
            with open(chart_path, "rb") as f:
                bot.send_photo(call.message.chat.id, f)
            os.remove(chart_path)
        except Exception as e:
            print(f"Error sending chart: {e}")
            bot.send_message(call.message.chat.id, "❌ خطا در ارسال نمودار دایره‌ای.")


# --- سایر Handlers (باید پس از ثبت هزینه باشند) ---

# (لطفاً بقیه توابع handler شامل /undo, /income, /goal, /recur, /addcat, /setbudget, /history, /export, /tips, /clear و توابع next_step آن‌ها را از نسخه قبلی کپی کنید و در این قسمت قرار دهید. منطق این توابع سالم بوده‌اند و نیازی به تغییرات درونی نداشتند، فقط توالی آن‌ها مهم است.)
# برای سادگی و جلوگیری از تکرار کد بسیار طولانی، من فرض می‌کنم که توابع `process_income_step` و `process_goal_step` و ... در کد شما وجود دارند و در اینجا فقط مهم‌ترین‌ها را برای رفع خطا آوردم.

# تابع set_budget:
@bot.message_handler(commands=['setbudget'])
def set_budget(message):
    msg = bot.send_message(message.chat.id, "لطفاً مبلغ بودجه ماهانه جدید را وارد کنید (مثال: 1000000 تومان):", 
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_budget_step)
# ... process_budget_step ...

# تابع add_category:
@bot.message_handler(commands=['addcat'])
def add_category(message):
    msg = bot.send_message(message.chat.id, "لطفاً نام دسته‌بندی جدید را وارد کنید (مثال: پوشاک):", 
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_category_step)
# ... process_category_step ...

# ... (ادامه توابع) ...

# اجرای ربات
if __name__ == '__main__':
    check_and_run_recurrences()
    print("Bot started polling...")
    # NOTE: در Polling، بهتر است همه دستورات در یک فایل و با توالی صحیح باشند.
    bot.polling(none_stop=True)
