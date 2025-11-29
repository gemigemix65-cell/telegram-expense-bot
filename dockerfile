# استفاده از نسخه سبک پایتون
FROM python:3.11-slim

# تنظیم متغیرهای محیطی
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# ایجاد دایرکتوری کاری در کانتینر
WORKDIR /app

# ---------------------------------------------------
# نصب پکیج‌های سیستمی و فونت‌های فارسی
# ---------------------------------------------------
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fontconfig \
    # نصب فونت‌های استاندارد لینوکس که فارسی را پشتیبانی می‌کنند (برای نمودارها)
    fonts-dejavu-core \
    # پکیج عمومی برای اطونت‌های یونیکد
    ttf-mscorefonts-installer \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها
COPY requirements.txt /app/

# نصب پکیج‌های پایتون
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کردن باقی فایل‌های پروژه
COPY . /app/

# دستور اجرای ربات
CMD ["python", "main.py"]
