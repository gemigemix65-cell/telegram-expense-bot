# ------------------------------------
# Stage 1: Build stage (نصب وابستگی‌ها)
# ------------------------------------
# 🚨 تغییر به ایمیج کامل‌تر برای پایداری بیشتر
FROM python:3.11 as build-stage

# نصب بسته‌های سیستمی حیاتی برای کروم و ابزارهای مرتبط
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    gnupg \
    curl \
    # وابستگی‌های مورد نیاز برای اجرای کروم در محیط headless
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    lsb-release \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 🚨 بخش نصب گوگل کروم
RUN apt-get update && apt-get install -y --no-install-recommends \
    # مرحله ۱: دانلود و افزودن کلید GPG و ریپازیتوری
    && curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    \
    # مرحله ۲: نصب مرورگر کروم
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    \
    # مرحله ۳: نصب درایور کروم (ChromeDriver) برای Selenium
    && CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+' | head -n 1) \
    && CHROME_DRIVER_VERSION=$(wget -q -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver \
    \
    # مرحله ۴: پاکسازی
    && rm -rf /var/lib/apt/lists/*

# تنظیم دایرکتوری کاری و نصب بسته‌های پایتون
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کدهای برنامه
COPY . /app

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
# 🚨 در مرحله اجرا، استفاده از ایمیج کامل برای اطمینان از دسترسی به کروم
FROM python:3.11 

# کپی کردن ابزارهای نصب شده از مرحله قبل (ضروری برای کروم و درایور)
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/local/bin/chromedriver /usr/local/bin/chromedriver
COPY --from=build-stage /usr/bin/google-chrome /usr/bin/google-chrome
COPY --from=build-stage /usr/lib/google-chrome /usr/lib/google-chrome
COPY --from=build-stage /usr/share/keyrings /usr/share/keyrings
COPY --from=build-stage /etc/apt/sources.list.d /etc/apt/sources.list.d
COPY --from=build-stage /usr/bin/wget /usr/bin/wget
COPY --from=build-stage /usr/bin/curl /usr/bin/curl

# کپی کردن کدهای برنامه
COPY . /app
WORKDIR /app

# تنظیم پورت و اجرای بدون بافر پایتون
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
