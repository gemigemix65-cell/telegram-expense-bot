# ------------------------------------
# Stage 1: Build stage (نصب کروم و وابستگی‌ها)
# ------------------------------------
# 🚨 بازگشت به ایمیج slim اما با نصب build-essential و کروم به روش مستقیم
FROM python:3.11-slim as build-stage

# نصب ابزارهای توسعه پایتون و وابستگی‌های سیستمی کروم
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    unzip \
    # وابستگی‌های ضروری برای اجرای کروم Headless
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    lsb-release \
    # پکیج‌هایی که برای اجرای کروم لازمند
    xz-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 🚨 نصب مستقیم کروم و درایور (بدون افزودن ریپازیتوری خارجی)
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -P /tmp/ \
    && dpkg -i /tmp/google-chrome-stable_current_amd64.deb || true \
    && apt-get install -f -y \
    && rm /tmp/google-chrome-stable_current_amd64.deb

# نصب درایور کروم
RUN CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+' | head -n 1) \
    && CHROME_DRIVER_VERSION=$(wget -q -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver

# تنظیم دایرکتوری کاری و نصب بسته‌های پایتون
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
FROM python:3.11-slim

# کپی کردن تمام فایل‌های نصب شده از مرحله ساخت (شامل کروم، درایور و کتابخانه‌های پایتون)
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/local/bin/chromedriver /usr/local/bin/
COPY --from=build-stage /usr/bin/google-chrome /usr/bin/
COPY --from=build-stage /opt/google /opt/google

# کپی کردن کدهای برنامه
COPY . /app
WORKDIR /app

# تنظیم متغیر محیطی
ENV PORT=3000
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:/usr/bin:${PATH}" # اطمینان از دسترسی به درایور

CMD ["python", "main.py"]
