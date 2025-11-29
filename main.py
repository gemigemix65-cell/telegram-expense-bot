import telebot
import json
import os
import speech_recognition as sr
from pydub import AudioSegment
import io
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from matplotlib import rcParams

# تنظیمات Plotting (برای نمودارها)
rcParams['font.family'] = 'DejaVu Sans' 
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False

# توکن ربات (توصیه می‌شود این را به عنوان متغیر محیطی در Render ذخیره کنید)
TOKEN = "8221583925:AAEowlZ0gV-WnDen3awIHweJ0i93P5DqUpw"
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "data.json"
BUDGET_MONTHLY = 500000  # بودجه ماهانه پیش‌فرض
DEFAULT_DATA = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}
data = DEFAULT_DATA.copy() # شروع با داده پیش‌فرض

# بارگذاری ایمن داده‌ها از JSON (اصلاح شده برای رفع KeyError)
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
            # ترکیب با داده‌های پیش‌فرض برای اطمینان از وجود همه کلیدها
            data.update(loaded_data)
    except json.JSONDecodeError:
        # اگر فایل خراب بود، با داده پیش‌فرض ادامه می‌دهد
        print(f"Error reading {DATA_FILE}. Starting with default data.")
        pass 

# اطمینان از وجود کلیدهای ضروری (حتی اگر فایل JSON آن‌ها را نداشته باشد)
if "expenses" not in data:
    data["expenses"] = []
if "categories" not in data:
    data["categories"] = DEFAULT_DATA["categories"]


def save_data():
    """ذخیره داده‌ها در فایل JSON و اضافه کردن تاریخ به ورودی‌های فاقد تاریخ"""
    for exp in data["expenses"]:
        if "date" not in exp:
            exp["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def parse_amount_category(text):
    """متن را به مبلغ و دسته‌بندی تشخیص می‌دهد."""
    text = text.replace("تومن", "").replace("ریال", "").replace(",", "").strip()
    words = text.split()
    if not words:
        return None

    try:
        amount = 0
        category = "سایر"
        
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
                
                category_words = words[start_index:]
                category = " ".join(category_words).strip()
                
                if not category or category.isdigit():
                    category = "سایر"

                return {"amount": amount, "category": category, "note": "", "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    except Exception:
        return None
    return None

# دکمه منو
def main_menu(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        "/report 📊 گزارش",
        "/addcat ➕ اضافه کردن دسته‌بندی",
        "/setbudget 💰 تعیین بودجه",
        "/clear 🔄 پاک کردن همه داده‌ها"
    ]
    row1 = [telebot.types.KeyboardButton(b) for b in buttons[0:2]]
    row2 = [telebot.types.KeyboardButton(b) for b in buttons[2:4]]
    keyboard.add(*row1)
    keyboard.add(*row2)

    bot.send_message(message.chat.id, "📌 منو ربات:", reply_markup=keyboard)

# --- Message Handlers ---

@bot.message_handler(commands=['start'])
def start(message):
    main_menu(message)
    bot.send_message(message.chat.id, "سلام! ربات حسابداری هوشمند آماده است.\n"
                                      "✅ هزینه‌ها را با **متن** یا **ویس** ثبت کنید.")

@bot.message_handler(commands=['addcat'])
def add_category(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "فرمت اشتباه. مثال: /addcat سرگرمی")
        return
    category = parts[1].strip()
    if category not in data["categories"]:
        data["categories"].append(category)
        save_data()
        bot.reply_to(message, f"✅ دسته‌بندی '{category}' اضافه شد!")
    else:
        bot.reply_to(message, "این دسته‌بندی قبلاً موجود است.")

@bot.message_handler(commands=['setbudget'])
def set_budget(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "فرمت اشتباه. مثال: /setbudget 1000000")
        return
    try:
        global BUDGET_MONTHLY
        budget_input = "".join(filter(str.isdigit, parts[1]))
        BUDGET_MONTHLY = float(budget_input)
        bot.reply_to(message, f"✅ بودجه ماهانه تنظیم شد: {BUDGET_MONTHLY:,.0f} تومان")
    except:
        bot.reply_to(message, "مبلغ معتبر نیست.")

@bot.message_handler(commands=['clear'])
def clear_data(message):
    global data
    data = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}
    save_data()
    bot.reply_to(message, "✅ همه داده‌ها پاک شدند.")

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'), content_types=['text'])
def add_expense_text(message):
    exp = parse_amount_category(message.text)
    if not exp or exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. مثال: 150 هزار ناهار")
        return
    
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
        
    data["expenses"].append(exp)
    save_data()
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']:,.0f} تومان در {exp['category']}")

# قابلیت پردازش عکس (OCR) به طور کامل حذف شده است.

@bot.message_handler(content_types=['voice'])
def add_expense_voice(message):
    file_info = bot.get_file(message.voice.file_id)
    downloaded = bot.download_file(file_info.file_path)
    
    try:
        audio = AudioSegment.from_ogg(io.BytesIO(downloaded))
        audio.export("temp.wav", format="wav")
    except Exception:
        bot.reply_to(message, "❌ خطا در پردازش فایل صوتی.")
        return

    r = sr.Recognizer()
    try:
        with sr.AudioFile("temp.wav") as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language="fa-IR")
            os.remove("temp.wav")
    except Exception:
        if os.path.exists("temp.wav"):
            os.remove("temp.wav")
        bot.reply_to(message, "❌ خطا در تبدیل ویس به متن (احتمالاً صدای واضحی نبود).")
        return

    exp = parse_amount_category(text)
    if exp and exp["amount"] > 0:
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
            
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']:,.0f} تومان در {exp['category']}")
    else:
        bot.reply_to(message, f"❌ متن ویس قابل پردازش نبود یا مبلغ صفر بود. متن تشخیص داده شده: {text}")

@bot.message_handler(commands=['report'])
def report(message):
    # این چک اکنون کاملا ایمن است زیرا ساختار data همیشه توسط کد بارگذاری ایمن تضمین شده است.
    if not data["expenses"]:
        bot.reply_to(message, "هیچ هزینه‌ای ثبت نشده.")
        return

    totals = {}
    amounts_by_category = {}
    
    for exp in data["expenses"]:
        if "amount" in exp and "category" in exp:
            totals[exp["category"]] = totals.get(exp["category"], 0) + exp["amount"]
            amounts_by_category.setdefault(exp["category"], []).append(exp["amount"])

    report_text = "📊 گزارش هزینه‌ها:\n"
    for cat, total in totals.items():
        report_text += f"**{cat}**: {total:,.0f} تومان\n"

    anomalies = []
    for cat, amounts in amounts_by_category.items():
        if len(amounts) > 1:
            mean = np.mean(amounts)
            std = np.std(amounts)
            for a in amounts:
                if a > mean + 1.5 * std:
                    anomalies.append(f"{a:,.0f} تومان در {cat}")

    if anomalies:
        report_text += "\n⚠️ **هزینه‌های غیرعادی**:\n" + "\n".join(anomalies)
    else:
        report_text += "\n✅ هزینه‌ها نرمال هستند."

    total_spent = sum([exp.get("amount", 0) for exp in data["expenses"]])
    if total_spent > BUDGET_MONTHLY:
        report_text += f"\n🚨 **هشدار بودجه**: بودجه ماهانه ({BUDGET_MONTHLY:,.0f} تومان) رد شده است!"
    else:
        remaining = BUDGET_MONTHLY - total_spent
        report_text += f"\n💡 **بودجه باقی‌مانده**: {remaining:,.0f} تومان"

    bot.reply_to(message, report_text, parse_mode='Markdown')

    # --- نمودار خطی روند هزینه‌ها ---
    
    sorted_expenses = sorted([exp for exp in data["expenses"] if "date" in exp], key=lambda x: datetime.strptime(x["date"].split()[0], "%Y-%m-%d"))
    dates = [datetime.strptime(exp["date"].split()[0], "%Y-%m-%d") for exp in sorted_expenses]
    amounts = [exp["amount"] for exp in sorted_expenses]
    
    if dates:
        plt.figure(figsize=(8,4))
        plt.plot(dates, np.cumsum(amounts), color='blue', linestyle='-', marker='o', label='هزینه انباشته')
        plt.title("روند هزینه‌های انباشته", loc='right')
        plt.xlabel("تاریخ")
        plt.ylabel("مبلغ (تومان)")
        plt.legend(loc='upper left')
        plt.xticks(rotation=30)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig("report_line.png")
        plt.close()
        try:
            with open("report_line.png", "rb") as f:
                bot.send_photo(message.chat.id, f)
            os.remove("report_line.png")
        except:
            bot.send_message(message.chat.id, "❌ خطا در ارسال نمودار خطی.")


    # --- نمودار دایره‌ای دسته‌بندی‌ها ---
    if totals:
        plt.figure(figsize=(6,6))
        labels = [k for k, v in totals.items() if v > 0]
        sizes = [v for v in totals.values() if v > 0]
        
        if sizes:
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
            plt.title("درصد هزینه‌ها بر اساس دسته‌بندی", loc='right')
            plt.tight_layout()
            plt.savefig("report_pie.png")
            plt.close()
            try:
                with open("report_pie.png", "rb") as f:
                    bot.send_photo(message.chat.id, f)
                os.remove("report_pie.png")
            except:
                bot.send_message(message.chat.id, "❌ خطا در ارسال نمودار دایره‌ای.")


# اجرای ربات
if __name__ == '__main__':
    print("Bot started polling...")
    bot.polling(none_stop=True)

