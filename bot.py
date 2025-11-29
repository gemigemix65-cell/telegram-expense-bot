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
from datetime import datetime, timedelta

TOKEN = 8221583925:AAEEqJ9x2m0httqLjkccLTGjBEOs2MHtuVs
bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"
BUDGET_MONTHLY = 500000  # بودجه ماهانه پیش‌فرض، قابل تغییر

# بارگذاری داده‌ها
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"expenses": [], "categories": ["خوراک", "حمل و نقل", "تفریح", "سایر"]}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def process_text(message_text):
    parts = message_text.split(maxsplit=2)
    if len(parts) < 2:
        return None
    try:
        amount = float(parts[0])
        category = parts[1]
        note = parts[2] if len(parts) > 2 else ""
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"amount": amount, "category": category, "note": note, "date": date}
    except:
        return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام! ربات حسابداری هوشمند آماده است.\n"
                          "📌 ثبت هزینه با متن: مبلغ دسته‌بندی توضیح\n"
                          "📌 ارسال عکس یا ویس رسید\n"
                          "📌 گزارش: /report\n"
                          "📌 اضافه کردن دسته جدید: /addcat دسته‌بندی\n"
                          "📌 تنظیم بودجه ماهانه: /setbudget مبلغ")

@bot.message_handler(commands=['addcat'])
def add_category(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "فرمت اشتباه. مثال: /addcat سرگرمی")
        return
    category = parts[1]
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

@bot.message_handler(commands=['add'])
def add_expense(message):
    exp = process_text(message.text[5:])
    if not exp:
        bot.reply_to(message, "فرمت اشتباه. مثال: /add 50000 خوراک ناهار")
        return
    if exp["category"] not in data["categories"]:
        data["categories"].append(exp["category"])
        bot.reply_to(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
    data["expenses"].append(exp)
    save_data()
    bot.reply_to(message, "✅ هزینه ثبت شد!")

@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)
    image = Image.open(io.BytesIO(downloaded))
    text = pytesseract.image_to_string(image, lang='fas')
    exp = process_text(text)
    if exp:
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp['category']}")
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از عکس ثبت شد: {exp['amount']} در {exp['category']}")
    else:
        bot.reply_to(message, "❌ متن داخل عکس قابل پردازش نبود.")

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
            exp = process_text(text)
            if exp:
                if exp["category"] not in data["categories"]:
                    data["categories"].append(exp["category"])
                    bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: {exp["category"]}")
                data["expenses"].append(exp)
                save_data()
                bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']} در {exp['category']}")
            else:
                bot.reply_to(message, "❌ متن ویس قابل پردازش نبود.")
        except:
            bot.reply_to(message, "❌ خطا در تبدیل ویس به متن.")

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

    dates = [datetime.strptime(exp["date"].split()[0], "%Y-%m-%d") for exp in data["expenses"]]
    amounts = [exp["amount"] for exp in data["expenses"]]
    plt.figure(figsize=(8,4))
    plt.scatter(dates, amounts, color='orange', label='هزینه روزانه')
    plt.plot(dates, np.cumsum(amounts), color='blue', linestyle='--', marker='o', label='هزینه انباشته')
    plt.title("روند هزینه‌ها")
    plt.xlabel("تاریخ")
    plt.ylabel("مبلغ")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig("report.png")
    plt.close()
    with open("report.png", "rb") as f:
        bot.send_photo(message.chat.id, f)
    plt.figure(figsize=(6,6))
    plt.pie(totals.values(), labels=totals.keys(), autopct='%1.1f%%', colors=plt.cm.Paired.colors)
    plt.title("درصد هزینه‌ها بر اساس دسته‌بندی")
    plt.savefig("report_pie.png")
    plt.close()
    with open("report_pie.png", "rb") as f:
        bot.send_photo(message.chat.id, f)

bot.polling()

