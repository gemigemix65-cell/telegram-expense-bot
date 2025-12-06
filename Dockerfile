# 1. تعیین ایمیج پایه
# استفاده از نسخه python:3.10-slim-buster که بر پایه Debian Buster است.
FROM python:3.10-slim-buster

# 2. تنظیم دایرکتوری کاری درون کانتینر
WORKDIR /app

# 3. نصب FFmpeg و سایر وابستگی‌های سیستمی
# نصب در یک لایه (Layer) برای کاهش حجم نهایی ایمیج
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # نصب پکیج FFmpeg
        ffmpeg \
        # نصب پکیج‌های توسعه برای زمانی که برخی وابستگی‌های پایتون نیاز به کامپایل دارند
        build-essential \
    # پاکسازی فایل‌های کش APT برای کوچک‌تر شدن ایمیج نهایی
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. کپی کردن فایل‌های مورد نیاز از پروژه به کانتینر
# فایل requirements.txt را زودتر کپی کنید تا تغییرات در کد، باعث کامپایل مجدد وابستگی‌ها نشود (Docker Caching).
COPY requirements.txt .

# 5. نصب وابستگی‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# 6. کپی کردن فایل‌های کد اصلی
# اکنون فایل‌های اصلی پروژه کپی می‌شوند.
COPY main.py .
# اگر فایل‌های دیگری (مانند config.py یا modules) دارید، آن‌ها را نیز اضافه کنید:
# COPY . . 

# 7. اجرای ربات (همان دستور شما)
CMD ["python", "main.py"]
