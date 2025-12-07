# =========================================================
# BUILD STAGE (مرحله ساخت): نصب وابستگی‌های سنگین و سیستمی
# از ایمیج slim برای هر دو مرحله استفاده می کنیم
# =========================================================
FROM python:3.10-slim as builder 

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
# ایمیج نهایی را نیز "slim" نگه می داریم تا GLIBC یکسان باشد
# =========================================================
FROM python:3.10-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# 1. کپی کردن فایل باینری FFmpeg از مرحله builder
# FFmpeg باینری
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
# کپی کردن کتابخانه‌های وابسته به FFmpeg (مانند libavcodec)
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavcodec* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavformat* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavutil* /usr/lib/x86_64-linux-gnu/


# 2. کپی کردن پکیج‌های پایتون نصب شده
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 3. کپی کردن فایل‌های کد اصلی
COPY main.py .

# 4. دستور اجرای ربات
CMD ["python", "main.py"]
