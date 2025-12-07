# =========================================================
# BUILD STAGE (مرحله ساخت): نصب وابستگی‌های سنگین و سیستمی
# =========================================================
# استفاده از ایمیج کامل‌تر برای اطمینان از نصب موفقیت‌آمیز apt-get
FROM python:3.10 as builder

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب FFmpeg و Build-Essential در این مرحله
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# کپی کردن و نصب وابستگی‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =========================================================
# FINAL STAGE (مرحله نهایی): ساخت ایمیج سبک و تمیز
# =========================================================
# تغییر به ایمیج slim-buster برای حجم نهایی کوچک‌تر
FROM python:3.10-slim-buster

# تنظیم دایرکتوری کاری
WORKDIR /app

# 1. نصب مجدد FFmpeg (اختیاری اما امن‌تر)
# اگرچه هدف ما کپی کردن بود، اما برای حل GLIBC، نصب دوباره FFmpeg در ایمیج نهایی بهتر است
# البته این خط نیاز به حل مشکل apt-get update دارد، اما ما به جای آن از نصب دستی استفاده می کنیم
# --- راه حل پایدار: فقط کپی کردن باینری FFmpeg و اتکا به GLIBC موجود ---

# 1. کپی کردن فایل باینری FFmpeg از مرحله builder
# ما فقط خود فایل اجرایی ffmpeg را کپی می کنیم.
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg

# 2. کپی کردن پکیج‌های پایتون نصب شده (ضروری)
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 3. کپی کردن فایل‌های کد اصلی
COPY main.py .

# 4. دستور اجرای ربات
CMD ["python", "main.py"]
