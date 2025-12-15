import telebot
from telebot import types as telegram_types
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
from typing import List

# 🚀 اضافه شدن SDK Gemini و Pydantic
import google.genai as genai 
from google.genai import types 
from pydantic import BaseModel, Field 

# ----------------------------------------
#           *** ۱. تنظیمات عمومی و AI ***
# ----------------------------------------

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL")

PORT = int(os.environ.get('PORT', 3000))
WEBHOOK_URL_PATH = f"/{TOKEN}" 
server = Flask(__name__)

DATA_FOLDER = "/app/data"  
DATA_FILE = os.path.join(DATA_FOLDER, "data.json")

if not os.path.exists(DATA_FOLDER):
    try:
        os.makedirs(DATA_FOLDER, exist_ok=True)
    except Exception as e:
        print(f"Error creating data folder: {e}")

if not TOKEN:
    print("خطا: BOT_TOKEN تنظیم نشده است.")
    exit()
if not WEBHOOK_URL_BASE:
    print("خطا: WEBHOOK_URL تنظیم نشده است.")
    exit()

bot = telebot.TeleBot(TOKEN)
BUDGET_MONTHLY = 500000 

rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False 

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

gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini Client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Gemini Client: {e}")
else:
    print("⚠️ GEMINI_API_KEY تنظیم نشده است. ربات بدون تحلیل هوشمند کار خواهد کرد.")


class ExpenseSchema(BaseModel):
    """اسکیما برای اطمینان از خروجی JSON با ساختار ثابت."""
    amount: int = Field(default=0, description="مبلغ هزینه به تومان، فقط عدد صحیح. عبارات نوشتاری (مانند 'یک میلیون') را تبدیل کند.")
    category: str = Field(default="سایر", description="دسته‌بندی اصلی هزینه.")
    note: str = Field(default="", description="توضیحات کامل تراکنش.")
    tags: List[str] = Field(default_factory=list, description="لیست تگ‌های موجود در متن (بدون #).")


SMART_AGENT_SYSTEM_PROMPT = f"""
شما یک Agent هوش مصنوعی هستید که وظیفه استخراج اطلاعات مالی از متن فارسی کاربر را دارید.
شما باید همیشه **مبلغ فارسی نوشتاری** (مانند 'هزار', 'میلیون', 'صد هزار') را به **عدد صحیح و کامل** (بدون کاما) تبدیل کنید.
خروجی شما باید منحصراً یک JSON Payload باشد که دقیقاً با Schema زیر مطابقت دارد. از اضافه کردن هرگونه متن، توضیح یا مقدمه خارج از JSON خودداری کنید.

مثال: برای ورودی 'یک میلیون و ۵۵۰ هزار تومان لباس #جدید':
{{
  "amount": 1550000,
  "category": "پوشاک",
  "note": "لباس",
  "tags": ["جدید"]
}}
"""

def smart_parse_amount_category(text):
    """استخراج مبلغ، دسته و یادداشت با استفاده از Gemini Agent و Pydantic."""
    if not gemini_client:
        return None 

    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[text],
            config=types.GenerateContentConfig( 
                system_instruction=SMART_AGENT_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ExpenseSchema
            )
        )
        
        # 🌟🌟🌟 کد مقاوم‌سازی برای پاکسازی خروجی JSON 🌟🌟🌟
        raw_json_text = response.text.strip()
        if raw_json_text.startswith("```json"):
            raw_json_text = raw_json_text[7:]
        if raw_json_text.endswith("```"):
            raw_json_text = raw_json_text[:-3]
        raw_json_text = raw_json_text.strip()
        # 🌟🌟🌟 پایان کد مقاوم‌سازی 🌟🌟🌟

        parsed_data = ExpenseSchema.model_validate_json(raw_json_text)
        
        exp_dict = parsed_data.model_dump()
        exp_dict["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
        exp_dict["note"] = exp_dict["note"] or exp_dict["category"] 
        
        return exp_dict

    except Exception as e:
        print(f"Gemini/Pydantic Error in smart_parse: {e}")
        print(f"Input Text: {text}")
        print(f"Gemini Response Text (Raw): {response.text if 'response' in locals() else 'N/A'}")
        return None


# ----------------------------------------
#           *** ۳. توابع کمکی ***
# ----------------------------------------

def save_data():
    """ذخیره داده‌ها در فایل JSON روی دیسک پایدار"""
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
                chart_path = os.path.join(DATA_FOLDER, "report_pie.png") 
                plt.savefig(chart_path)
                plt.close()
        except Exception as e:
            print(f"Error generating chart: {e}")
            
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
                                     "✅ هزینه‌ها را با **مبلغ و عنوان** (متن یا ویس) ثبت کنید. مثال: ۱۰۰۰۰ نان #نانوایی", parse_mode='Markdown', reply_markup=keyboard)


@bot.message_handler(commands=['undo'])
def undo_last_expense(message):
    if not data["expenses"]:
        bot.send_message(message.chat.id, "لیست هزینه‌های شما خالی است.", reply_markup=main_menu(message))
        return

    all_items = []
    for item in data["expenses"]:
        try:
            date_str = item.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            all_items.append((datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S"), item))
        except:
            all_items.append((datetime.min, item)) 
            
    if not all_items:
        bot.send_message(message.chat.id, "لیست هزینه‌های شما خالی است.", reply_markup=main_menu(message))
        return

    all_items.sort(key=lambda x: x[0], reverse=True) 
    last_item = all_items[0][1] 
    
    try:
        data["expenses"].remove(last_item)
        save_data()
        bot.send_message(message.chat.id, f"✅ **آخرین هزینه حذف شد:** {last_item['amount']:,.0f} تومان در {last_item['category']}.", parse_mode='Markdown', reply_markup=main_menu(message))
    except ValueError:
           bot.send_message(message.chat.id, "❌ خطا در حذف آیتم هزینه. آیتم یافت نشد.", parse_mode='Markdown', reply_markup=main_menu(message))


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
    # ⬅️ اضافه شدن لاگ برای تشخیص اینکه آیا ویس هندلر اجرا می شود یا خیر
    print(f"✅ Handler for voice message received from chat {message.chat.id}")

    if not gemini_client:
        bot.send_message(message.chat.id, "⚠️ **خطا:** کلید GEMINI API تنظیم نشده. نمی‌توانم ویس را پردازش کنم.", reply_markup=main_menu(message))
        return
        
    bot.send_message(message.chat.id, "در حال پردازش ویس و تحلیل هوشمند...", reply_markup=telegram_types.ReplyKeyboardRemove())
    
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_wav_path = os.path.join(DATA_FOLDER, "temp_voice.wav")
    text = ""
    
    try:
        audio = AudioSegment.from_file(io.BytesIO(downloaded_file), format="ogg")
        audio.export(temp_wav_path, format="wav")
        
        r = sr.Recognizer()
        with sr.AudioFile(temp_wav_path) as source:
            audio_data = r.record(source, duration=10) 
            text = r.recognize_google(audio_data, language="fa-IR", show_all=False, timeout=10)
            
    except pydub_exceptions.CouldntFindFFmpeg:
        bot.reply_to(message, "❌ **خطای عدم نصب FFmpeg:** پردازش ویس فعال نیست.", reply_markup=main_menu(message))
        return
    except sr.UnknownValueError:
        bot.reply_to(message, "❌ صدای شما به وضوح تشخیص داده نشد. لطفاً واضح‌تر صحبت کنید.", reply_markup=main_menu(message))
        return
    except Exception as e:
        print(f"Error in Voice Processing: {e}") 
        bot.reply_to(message, "❌ **خطا در تبدیل ویس به متن:** لطفاً دوباره تلاش کنید.", reply_markup=main_menu(message))
        return
    finally:
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)

    exp = smart_parse_amount_category(text)
    
    if exp and exp["amount"] > 0:
        if exp["category"] not in data["categories"]:
            data["categories"].append(exp["category"])
            bot.send_message(message.chat.id, f"دسته‌بندی جدید ساخته شد: **{exp['category']}**", parse_mode='Markdown')
            
        data["expenses"].append(exp)
        save_data()
        bot.reply_to(message, f"✅ هزینه از ویس ثبت شد: {exp['amount']:,.0f} تومان در **{exp['category']}** (یادداشت: {exp['note']})", parse_mode='Markdown', reply_markup=main_menu(message))
    else:
        bot.reply_to(message, f"❌ متن تشخیص داده شده قابل پردازش نبود یا مبلغ صفر بود. متن: **{text}**", parse_mode='Markdown', reply_markup=main_menu(message))


# ----------------------------------------
#           *** Handler برای متن (Text) ***
# ----------------------------------------

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'), content_types=['text'])
def add_expense_text(message):
    # ⬅️ اضافه شدن لاگ برای تشخیص اینکه آیا متن هندلر اجرا می شود یا خیر
    print(f"✅ Handler for text message received: {message.text}")
    
    exp = smart_parse_amount_category(message.text)
    
    if not exp or exp["amount"] == 0:
        bot.reply_to(message, "❌ فرمت اشتباه یا مبلغ صفر است. (مثال: یک میلیون و ۵۵۰ هزار تومان لباس #خرید)", reply_markup=main_menu(message))
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

@server.route(WEBHOOK_URL_PATH, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telegram_types.Update.de_json(json_string) 
        
        # ⬅️ لاگ کردن قبل از پردازش
        print("Received update from Telegram.")
        
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 400

if __name__ == '__main__':
    
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    
    print(f"ربات در حالت Webhook شروع به کار کرد روی پورت {PORT}...")
    
    server.run(host="0.0.0.0", port=PORT)
