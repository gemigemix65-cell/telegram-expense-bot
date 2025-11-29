# استفاده از نسخه پایدار Python
FROM python:3.11-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی فایل‌های پروژه
COPY bot.py .
COPY requirements.txt .
COPY data.json .

# نصب پیش‌نیازهای سیستم برای Pillow و سایر پکیج‌ها
RUN apt-get update && apt-get install -y \
    libjpeg-dev zlib1g-dev libpng-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# بروزرسانی pip و نصب پکیج‌های Python
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# اجرای ربات
CMD ["python", "bot.py"]
