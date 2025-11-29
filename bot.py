import telebot
import json
import os
import re
from PIL import Image
import pytesseract
import speech_recognition as sr
from pydub import AudioSegment
import io
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from bidi.algorithm import get_display
import arabic_reshaper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ------------------ تنظیمات ------------------
TOKEN = "8221583925:AAEowlZ0gV-WnDen3awIHweJ0i93P5DqUpw"
bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"
BUDGET_MONTHLY = 500000  # بودجه ماهانه پیش‌فرض

# ------------------ بارگذاری داده‌ها ------------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ------------------ ابزار پردازش متن ------------------
def extract_amount_and_category(text):
    """
    متن رو پردازش می‌کنه تا عدد و دسته‌بندی رو جدا کنه.
    مثال: '740 هزار تومن سیگار' → (740000, 'سیگار')
    """
    # حذف فاصله‌های غیر استاندارد و کاراکترهای اضافه
    text = text.replace('\u200c', ' ').replace('\xa0', ' ').strip()
    # پیدا کردن عدد
    match = re.search(r'(\d+(?:[\.,]\d+)?)(\s*(هزار|میلیون|تومن|ریال)?)', text)
    if not match:
        return None
    amount = float(match.group(1).replace(',', ''))
    unit = match.group(3)
    if unit == "هزار":
        amount *= 1000
    elif unit == "میلیون":
        amount *= 1000000
    # دسته‌بندی = باقی متن بعد عدد و واحد
    category = text[match.end():].strip()
    if not category:
        category = "سایر"
    return int(amount), category

# ------------------ منوی دکمه‌ای ------------------
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("/report"),
        KeyboardButton("/addcat"),
        KeyboardButton("/setbudget"),
        KeyboardButton("/clear")
    )
    return markup

# ------------------ دستورات ------------------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
                     "سلام! ربات حسابداری هوشمند آماده است.\n\n"
                     "📌 ثبت هزینه با متن: مبلغ دسته‌بندی توضیح\n"
                     "📌 ارسال عکس یا ویس رسید\n"
                     "📌 گزارش: /report\n"
                     "📌 اضافه کردن دسته جدید: /addcat دسته‌بندی\n"
                     "📌 تنظیم بودجه ماهانه: /setbudget مبلغ\n"
                     "📌 پاک کردن کل حساب: /clear",
                     reply_markup=main_menu())

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
        BUDGET_MONTHLY = float(parts[1])
        bot.reply_to(message, f"✅ بودجه ماهانه تنظیم شد: {BUDGET_MONTHLY}")
    except:
        bot.reply_to(message, "مبلغ معتبر نیست.")

@bot.message_handler(commands=['clear'])
def clear_data(message):
    global data
    data = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}
    save_data()
    bot.reply_to(message, "✅ تمام داده‌ها پاک شد و از نو ساخته شدند.")

# ------------------ ثبت هزینه با متن ------------------
@bot.message_handler(func=lambda message: True, content_types=['text'])
def add_expense_text(message):
    res = extract_amount_and_category(message.text)
    if not res:
        bot.reply_to(message, "❌ متن قابل پردازش نیست. مثال: '740 هزار تومن سیگار'")
        return
    amount, category = res
    if category not in data["categories"]:
        data["categories"].append(category)
    data["expenses"].append({"amount": amount, "category": category, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    save_data()
    bot.reply_to(message, f"✅ هزینه ثبت شد: {amount} در {category}")

# ------------------ ثبت هزینه با عکس ------------------
@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)
    image = Image.open(io.BytesIO(downloaded))
    text = pytesseract.image_to_string(image, lang='fas')
    res = extract_amount_and_category(text)
    if not res:
        bot.reply_to(message, "❌ متن داخل عکس قابل پردازش نبود.")
        return
    amount, category = res
    if category not in data["categories"]:
        data["categories"].append(category)
    data["expenses"].append({"amount": amount, "category": category, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    save_data()
    bot.reply_to(message, f"✅ هزینه از عکس ثبت شد: {amount} در {category}")

# ------------------ ثبت هزینه با ویس ------------------
@bot.message_handler(content_types=['voice'])
def voice_handler(message):
    file_info = bot.get_file(message.voice.file_id)
    downloaded = bot.download_file(file_info.file_path)
    audio = AudioSegment.from_ogg(io.BytesIO(downloaded))
    audio.export("temp.wav", format="wav")
    r = sr.Recognizer()
    with sr.AudioFile("temp.wav") as source:
        audio_data = r.record(source)
        try:
            text = r.recognize_google(audio_data, language="fa-IR")
            res = extract_amount_and_category(text)
            if not res:
                bot.reply_to(message, "❌ متن ویس قابل پردازش نبود.")
                return
            amount, category = res
            if category not in data["categories"]:
                data["categories"].append(category)
            data["expenses"].append({"amount": amount, "category": category, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            save_data()
            bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {amount} در {category}")
        except:
            bot.reply_to(message, "❌ خطا در تبدیل ویس به متن.")

# ------------------ گزارش ------------------
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

    # نمودار روند هزینه‌ها
    dates = [datetime.strptime(exp["date"].split()[0], "%Y-%m-%d") for exp in data["expenses"]]
    amounts = [exp["amount"] for exp in data["expenses"]]
    plt.figure(figsize=(8,4))
    plt.scatter(dates, amounts, color='orange', label=get_display(arabic_reshaper.reshape('هزینه روزانه')))
    plt.plot(dates, np.cumsum(amounts), color='blue', linestyle='--', marker='o', label=get_display(arabic_reshaper.reshape('هزینه انباشته')))
    plt.title(get_display(arabic_reshaper.reshape("روند هزینه‌ها")))
    plt.xlabel(get_display(arabic_reshaper.reshape("تاریخ")))
    plt.ylabel(get_display(arabic_reshaper.reshape("مبلغ")))
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig("report.png")
    plt.close()
    with open("report.png", "rb") as f:
        bot.send_photo(message.chat.id, f)

    # نمودار دایره‌ای
    plt.figure(figsize=(6,6))
    reshaped_labels = [get_display(arabic_reshaper.reshape(cat)) for cat in totals.keys()]
    plt.pie(totals.values(), labels=reshaped_labels, autopct='%1.1f%%', colors=plt.cm.Paired.colors)
    plt.title(get_display(arabic_reshaper.reshape("درصد هزینه‌ها بر اساس دسته‌بندی")))
    plt.savefig("report_pie.png")
    plt.close()
    with open("report_pie.png", "rb") as f:
        bot.send_photo(message.chat.id, f)

# ------------------ شروع ربات ------------------
bot.polling()


