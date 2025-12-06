# ----------------------------------------
# ۱. تعیین تصویر پایه
# ----------------------------------------
FROM python:3.10-slim-buster

# ----------------------------------------
# ۲. تنظیم دایرکتوری کاری درون کانتینر
# ----------------------------------------
WORKDIR /app

# ----------------------------------------
# ۳. اصلاح فایل منابع APT و نصب (راه حل پایداری شبکه)
# ----------------------------------------
RUN echo "deb http://deb.debian.org/debian buster main" > /etc/apt/sources.list \
    && echo "deb http://deb.debian.org/debian buster-updates main" >> /etc/apt/sources.list \
    && echo "deb http://security.debian.org/debian-security buster/updates main" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------
# ۴. کپی کردن فایل‌ها و نصب وابستگی‌ها
# ----------------------------------------
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------
# ۵. حذف بسته‌های توسعه برای کوچک‌سازی ایمیج نهایی
# ----------------------------------------
RUN apt-get update \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------
# ۶. کپی کردن فایل‌های کد اصلی
# ----------------------------------------
COPY main.py .

# ----------------------------------------
# ۷. اجرای ربات
# ----------------------------------------
CMD ["python", "main.py"]
