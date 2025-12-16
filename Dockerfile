# ------------------------------------
# Stage 1: Build stage (نصب بسته‌های پایتون)
# ------------------------------------
# استفاده از ایمیج پایه که از قبل شامل کروم و درایور آن است.
FROM selenium/standalone-chrome:latest as build-stage

# 🚨 نصب ابزارهای توسعه برای کامپایل بسته‌های پایتون (build-essentials)
RUN apt-get update && apt-get install -y \
    build-essential \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن و نصب نیازمندی‌های پایتون
WORKDIR /app
COPY requirements.txt .
# 🚨 pip را با استفاده از pip3 اجرا می‌کنیم تا با سیستم ایمیج هماهنگ باشد
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
# استفاده از ایمیج پایه Selenium برای مرحله اجرا
FROM selenium/standalone-chrome:latest

# کپی کردن بسته‌های پایتون نصب شده از مرحله قبل
# 🚨 تغییر مسیرها به /usr/local/lib/python3.11/site-packages
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

# 🚨 دستور اجرا
CMD ["python3", "main.py"]
