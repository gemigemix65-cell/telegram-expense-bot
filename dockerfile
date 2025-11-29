# پایه: Python 3.13 slim
FROM python:3.13-slim

# نصب کتابخانه‌های مورد نیاز سیستم
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# مسیر کاری
WORKDIR /app

# کپی فایل‌ها
COPY requirements.txt .
COPY bot.py .
COPY data.json .

# نصب پکیج‌های پایتون
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# اجرای ربات
CMD ["python", "bot.py"]
