# =========================================================
# BUILD STAGE (مرحله ساخت): نصب وابستگی‌های سنگین و سیستمی
# =========================================================
# از ایمیج کامل‌تر برای اطمینان از نصب موفقیت‌آمیز apt-get استفاده می‌کنیم.
FROM python:3.10 as builder

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب FFmpeg و Build-Essential در این مرحله
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential

# کپی کردن و نصب وابستگی‌های پایتون (که ممکن است نیاز به کامپایل داشته باشند)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =========================================================
# FINAL STAGE (مرحله نهایی): ساخت ایمیج سبک و تمیز
# =========================================================
# تغییر به ایمیج slim-buster برای حجم نهایی کوچک‌تر
FROM python:3.10-slim-buster

# تنظیم دایرکتوری کاری
WORKDIR /app

# 1. کپی کردن FFmpeg و کتابخانه‌های سیستمی ضروری از مرحله builder
# FFMPEG binaries and libraries
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=builder /usr/lib/x86_64-linux-gnu/libav* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libsw* /usr/lib/x86_64-linux-gnu/
# اضافه کردن کتابخانه‌های پایه دبیان
COPY --from=builder /lib/x86_64-linux-gnu/libm.so.6 /lib/x86_64-linux-gnu/
COPY --from=builder /lib/x86_64-linux-gnu/libdl.so.2 /lib/x86_64-linux-gnu/

# 2. کپی کردن پکیج‌های پایتون نصب شده (بهترین روش)
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 3. کپی کردن فایل‌های کد اصلی
COPY main.py .

# 4. دستور اجرای ربات
CMD ["python", "main.py"]
