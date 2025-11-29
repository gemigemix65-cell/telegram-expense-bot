# استفاده از نسخه سبک پایتون
FROM python:3.11-slim

# تنظیم متغیرهای محیطی برای جلوگیری از ساخت فایل‌های اضافی پایتون
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# ایجاد دایرکتوری کاری در کانتینر
WORKDIR /app

# ---------------------------------------------------
# نصب FFmpeg (حیاتی برای تبدیل ویس تلگرام به متن)
# ---------------------------------------------------
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها
COPY requirements.txt /app/

# نصب پکیج‌های پایتون
# دستور upgrade pip برای اطمینان از نصب صحیح است
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کردن باقی فایل‌های پروژه
COPY . /app/

# دستور اجرای ربات
# نکته: اگر نام فایل اصلی شما main.py نیست، آن را اینجا تغییر دهید
CMD ["python", "main.py"]
