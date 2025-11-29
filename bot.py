import telebot
import json
import os
from PIL import Image
import pytesseract
import speech_recognition as sr
from pydub import AudioSegment
import io
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from matplotlib import rcParams

# تنظیمات فارسی برای matplotlib
rcParams['font.family'] = 'DejaVu Sans'
rcParams['axes.unicode_minus'] = False

# توکن ربات
TOKEN = "8221583925:AAEowlZ0gV-WnDen3awIHweJ0i93P5DqUpw"
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "data.json"
BUDGET_MONTHLY = 500000  # بودجه ماهانه پیش‌فرض

# بارگذاری داده‌ها
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def parse_amount_category(text):
    """
    متن را به مبلغ و دسته‌بندی تشخیص می‌دهد.
    مثال: "150 هزار تومن ناهار" → amount=150000, category=ناهار
    """
    text = text.replace("تومن", "").replace("ریال", "").replace(",", "").strip()
    words = text.split()
    if not words:
        return None

    # تشخیص مبلغ
    try:
        amount = 0
        for i, word in enumerate(words):
            if word.isdigit():
                amount = int(word)
                multiplier = 1
                if i + 1 < len(words):
                    if words[i + 1] in ["هزار", "هزار تومان"]:
                        multiplier = 1000
                    elif words[i + 1] in ["میلیون"]:
                        multiplier = 1000000
                amount *= multiplier
                category = " ".join(words[i+2:]) if i+2 <= len(words) else "سایر"
                return {"amount": amount, "category": category, "note": ""}
    except:
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
    keyboard.add(*[telebot.types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "📌 منو ربات:", reply_markup=keyboard)

# دستور /start
@bot.message_handler(commands=['start'])
def start(message):
    main_menu(message)
    bot.send_message(message.chat.id, "سلام! ربات حسابداری هوشمند آماده است.\n"
                                      "✅ هزینه‌ها را با متن، عکس یا ویس ثبت کنید.")

# دستور /addcat
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

# دستور /setbudget
@bot.message_handler(commands=['setbudget'])
def set_budget(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "فرمت اشتباه. مثال: /setbudget 1000000")
        return
    try:
        global BUDGET_MONTHLY
        BUDGET_MONTHLY = float(parts[1])
        bot.reply_to(message, f"✅ بودجه ماهانه تنظیم شد: {BUDGET_MONTHLY}")
    except:
        bot.reply_to(message, "مبلغ معتبر نیست.")

# دستور /clear
@bot.message_handler(commands=['clear'])
def clear_data(message):
    global data
    data = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}
    save_data()
    bot.reply_to(message, "✅ همه داده‌ها پاک شدند.")

# ثبت هزینه با متن
@bot.message_handler(func=lambda m: True, content_types=['text'])
def add_expense_text(message):
    exp = parse_amount_category(message.text)
    if not exp:
        bot.reply_to(message, "❌ فرمت اشتباه. مثال: 150 هزار ناهار")
        return
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
    data["expenses"].append(exp)
    save_data()
    bot.reply_to(message, f"✅ هزینه ثبت شد: {exp['amount']} در {exp['category']}")

# ثبت هزینه از عکس
@bot.message_handler(content_types=['photo'])
def add_expense_photo(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)
    image = Image.open(io.BytesIO(downloaded))
    text = pytesseract.image_to_string(image, lang='fas')
    exp = parse_amount_category(text)
    if exp:
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از عکس ثبت شد: {exp['amount']} در {exp['category']}")
    else:
        bot.reply_to(message, "❌ متن داخل عکس قابل پردازش نبود.")

# ثبت هزینه از ویس
@bot.message_handler(content_types=['voice'])
def add_expense_voice(message):
    file_info = bot.get_file(message.voice.file_id)
    downloaded = bot.download_file(file_info.file_path)
    audio = AudioSegment.from_ogg(io.BytesIO(downloaded))
    audio.export("temp.wav", format="wav")
    r = sr.Recognizer()
    with sr.AudioFile("temp.wav") as source:
        audio_data = r.record(source)
        try:
            text = r.recognize_google(audio_data, language="fa-IR")
            exp = parse_amount_category(text)
            if exp:
                if exp["category"] not in data["categories"]:
                    data["categories"].append(exp["category"])
                    bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
                data["expenses"].append(exp)
                save_data()
                bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']} در {exp['category']}")
            else:
                bot.reply_to(message, "❌ متن ویس قابل پردازش نبود.")
        except:
            bot.reply_to(message, "❌ خطا در تبدیل ویس به متن.")

# گزارش
@bot.message_handler(commands=['report'])
def report(message):
    if not data["expenses"]:
        bot.reply_to(message, "هیچ هزینه‌ای ثبت نشده.")
        return

    totals = {}
    amounts_by_category = {}
    for exp in data["expenses"]:
        totals[exp["category"]] = totals.get(exp["category"], 0) + exp["amount"]
        amounts_by_category.setdefault(exp["category"], []).append(exp["amount"])

    report_text = "📊 گزارش هزینه‌ها:\n"
    for cat, total in totals.items():
        report_text += f"{cat}: {total}\n"

    # شناسایی هزینه‌های غیرعادی
    anomalies = []
    for cat, amounts in amounts_by_category.items():
        mean = np.mean(amounts)
        std = np.std(amounts)
        for a in amounts:
            if a > mean + 1.5 * std:
                anomalies.append(f"{a} در {cat}")

    if anomalies:
        report_text += "\n⚠️ هزینه‌های غیرعادی:\n" + "\n".join(anomalies)
    else:
        report_text += "\n✅ هزینه‌ها نرمال هستند."

    total_spent = sum([exp["amount"] for exp in data["expenses"]])
    if total_spent > BUDGET_MONTHLY:
        report_text += f"\n💡 هشدار: بودجه ماهانه ({BUDGET_MONTHLY}) تمام شده یا نزدیک است!"
    else:
        remaining = BUDGET_MONTHLY - total_spent
        report_text += f"\n💡 بودجه باقی‌مانده: {remaining}"

    bot.reply_to(message, report_text)

    # نمودار خطی
    dates = [datetime.strptime(exp["date"].split()[0], "%Y-%m-%d") if "date" in exp else datetime.now() for exp in data["expenses"]]
    amounts = [exp["amount"] for exp in data["expenses"]]

    plt.figure(figsize=(8,4))
    plt.scatter(dates, amounts, color='orange', label='هزینه روزانه')
    plt.plot(dates, np.cumsum(amounts), color='blue', linestyle='--', marker='o', label='هزینه انباشته')
    plt.title("روند هزینه‌ها", loc='right')
    plt.xlabel("تاریخ")
    plt.ylabel("مبلغ")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig("report.png")
    plt.close()
    with open("report.png", "rb") as f:
        bot.send_photo(message.chat.id, f)

    # نمودار دایره‌ای
    plt.figure(figsize=(6,6))
    plt.pie(totals.values(), labels=totals.keys(), autopct='%1.1f%%', colors=plt.cm.Paired.colors)
    plt.title("درصد هزینه‌ها بر اساس دسته‌بندی", loc='right')
    plt.savefig("report_pie.png")
    plt.close()
    with open("report_pie.png", "rb") as f:
        bot.send_photo(message.chat.id, f)

# اجرای ربات
bot.polling()
