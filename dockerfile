# 1. تعیین ایمیج پایه (استفاده از نسخه سبک پایتون)
FROM python:3.10-slim

# 2. تنظیم دایرکتوری کاری درون کانتینر
WORKDIR /app

# 3. نصب FFmpeg و سایر وابستگی‌های سیستمی (برای اجرای pydub)
# 'apt-get update' لیست پکیج‌ها را به‌روز می‌کند و 'apt-get install -y' FFmpeg و پیش‌نیازهای ساخت را نصب می‌کند.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 4. کپی کردن فایل‌های مورد نیاز از پروژه به کانتینر
COPY requirements.txt .
COPY main.py .

# 5. نصب وابستگی‌های پایتون از requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6. اجرای ربات
# فرض می‌کنیم نقطه ورود (entrypoint) ربات شما فایل main.py است.
CMD ["python", "main.py"]
