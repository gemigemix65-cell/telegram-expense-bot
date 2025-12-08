# =========================================================
# BUILD STAGE (مرحله ساخت): نصب وابستگی‌های سنگین و سیستمی
# ایمیج SLIM برای یکسان‌سازی GLIBC و رفع خطاهای runtime
# =========================================================
FROM python:3.10-slim as builder 

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب FFmpeg و Build-Essential در این مرحله (با رفع مشکل apt-get update)
# Build-Essential برای کامپایل وابستگی‌های پایتون مثل pydub
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# کپی کردن و نصب وابستگی‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =========================================================
# FINAL STAGE (مرحله نهایی): ساخت ایمیج سبک و تمیز
# ایمیج نهایی نیز slim است تا GLIBC سازگار باشد
# =========================================================
FROM python:3.10-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# 1. کپی کردن فایل‌های باینری ضروری (FFmpeg و FFprobe)
# فایل اجرایی اصلی
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
# ffprobe برای رفع اخطار pydub
COPY --from=builder /usr/bin/ffprobe /usr/bin/ffprobe 

# کپی کردن کتابخانه‌های وابسته به FFmpeg (برای اجرا)
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavcodec* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavformat* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavutil* /usr/lib/x86_64-linux-gnu/

# 2. 💡 تنظیم متغیر PATH برای پیدا کردن ffmpeg/ffprobe
# این خط برای رفع اخطار RuntimeWarning: Couldn't find ffprobe or avprobe حیاتی است.
ENV PATH="/usr/bin:${PATH}"

# 3. کپی کردن پکیج‌های پایتون نصب شده
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 4. کپی کردن فایل‌های کد اصلی
COPY main.py .

# 5. دستور اجرای ربات
CMD ["python", "main.py"]
