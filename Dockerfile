# ------------------------------------
# Stage 1: Build stage (نصب بسته‌های پایتون)
# ------------------------------------
# استفاده از ایمیج پایه که از قبل شامل کروم و درایور آن است.
FROM selenium/standalone-chrome:latest as build-stage

# کپی کردن و نصب نیازمندی‌های پایتون
WORKDIR /app
COPY requirements.txt .
# 🚨 فقط pip را اجرا می‌کنیم و دیگر apt-get install python3.11 را نمی‌زنیم.
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
# استفاده از ایمیج پایه Selenium برای مرحله اجرا
FROM selenium/standalone-chrome:latest

# کپی کردن بسته‌های پایتون نصب شده از مرحله قبل
COPY --from=build-stage /usr/local/lib/python3/dist-packages /usr/local/lib/python3/dist-packages
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages

# کپی کردن کدهای برنامه
COPY . /app
WORKDIR /app

# تنظیم متغیر محیطی برای دسترسی مستقیم به ChromeDriver
ENV PATH="/usr/bin/:${PATH}"

# تنظیم پورت و اجرای بدون بافر پایتون
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# 🚨 استفاده از دستور python3 (نه python) که در Debian رایج است.
CMD ["python3", "main.py"]
