# ایمیج سبک Python 3.13
FROM python:3.13-slim

# نصب ffmpeg برای پخش و پردازش ویس
RUN apt-get update && apt-get install -y ffmpeg

# ساخت دایرکتوری پروژه
WORKDIR /app

# کپی فایل‌های پروژه
COPY requirements.txt .
COPY bot.py .
COPY data.json .

# نصب پکیج‌های پایتون
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# اجرای ربات
CMD ["python", "bot.py"]
