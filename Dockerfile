# ------------------------------------
# Stage 1: Build stage (نصب وابستگی‌ها)
# ------------------------------------
# استفاده از base image کامل‌تر که شامل ابزارهای لازم برای نصب کروم باشد
FROM python:3.11-slim as build-stage

# نصب بسته‌های سیستمی حیاتی: build-essential و ابزارهای لازم برای نصب کروم
RUN apt-get update && apt-get install -y \
    build-essential \
    libpng-dev \
    pkg-config \
    fontconfig \
    libxrender1 \
    wget \
    unzip \
    # 🚨 gnupg برای مدیریت کلیدها
    gnupg \
    ca-certificates \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 🚨 بخش نصب گوگل کروم: روش اصلاح شده برای دور زدن خطای apt-key
RUN apt-get update && apt-get install -y --no-install-recommends \
    # مرحله ۱: دانلود کلید GPG و اضافه کردن آن به منابع apt (روش مدرن)
    && curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    # مرحله ۲: اضافه کردن ریپازیتوری کروم به منابع apt
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    \
    # مرحله ۳: نصب مرورگر کروم
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    \
    # مرحله ۴: نصب درایور کروم (ChromeDriver) برای Selenium
    && CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+' | head -n 1) \
    && CHROME_DRIVER_VERSION=$(wget -q -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver \
    \
    # مرحله ۵: پاکسازی
    && rm -rf /var/lib/apt/lists/*

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی کردن فایل نیازمندی‌ها و نصب بسته‌های پایتون
COPY requirements.txt .
RUN pip install --upgrade pip
# نصب بسته‌ها
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
# استفاده از python:3.11-slim برای کوچک نگه داشتن کانتینر
FROM python:3.11-slim

# 🚨 کپی کردن کتابخانه‌های سیستمی و مرورگر از مرحله قبل
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/share/keyrings /usr/share/keyrings
COPY --from=build-stage /etc/apt/sources.list.d /etc/apt/sources.list.d
COPY --from=build-stage /usr/bin/google-chrome /usr/bin/google-chrome
COPY --from=build-stage /usr/lib/google-chrome /usr/lib/google-chrome
COPY --from=build-stage /usr/local/bin/chromedriver /usr/local/bin/chromedriver

# کپی کردن کدهای برنامه
COPY . /app
WORKDIR /app

# تنظیم پورت و اجرای بدون بافر پایتون
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# تعیین دستوری که پس از راه‌اندازی کانتینر اجرا می‌شود
CMD ["python", "main.py"]
