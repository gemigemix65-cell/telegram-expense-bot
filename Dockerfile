# ------------------------------------
# Stage 1: Build stage (نصب وابستگی‌ها)
# ------------------------------------
# استفاده از base image کامل‌تر که شامل ابزارهای لازم برای نصب کروم باشد
FROM python:3.11 as build-stage

# نصب وابستگی‌های سیستمی و کروم
RUN apt-get update && apt-get install -y \
    build-essential \
    libpng-dev \
    pkg-config \
    fontconfig \
    libxrender1 \
    wget \
    gnupg \
    ca-certificates \
    # نصب مرورگر کروم
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    # نصب درایور کروم (ChromeDriver) برای Selenium
    && CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+' | head -n 1) \
    && CHROME_DRIVER_VERSION=$(wget -q -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -O /usr/local/bin/chromedriver "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip /usr/local/bin/chromedriver -d /usr/local/bin/ \
    && rm /usr/local/bin/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver \
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
FROM python:3.11-slim

# کپی کردن کتابخانه‌های سیستمی و مرورگر از مرحله قبل
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/lib/chromium /usr/lib/chromium
COPY --from=build-stage /usr/bin/google-chrome /usr/bin/google-chrome
COPY --from=build-stage /usr/local/bin/chromedriver /usr/local/bin/chromedriver
# کپی کردن کدهای برنامه
COPY . .

# تنظیم پورت و اجرای بدون بافر پایتون
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# تعیین دستوری که پس از راه‌اندازی کانتینر اجرا می‌شود
CMD ["python", "main.py"]
