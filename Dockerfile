# Используем официальный образ Python 3.10 slim
FROM python:3.10-slim

# Чтобы apt не спрашивал подтверждения при установке пакетов
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем системные зависимости для Playwright, unzip, JDK и сертификаты
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    libnss3 \
    libxss1 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libasound2 \
    fonts-liberation \
    ca-certificates \
    openjdk-21-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей Python и устанавливаем их
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# Устанавливаем Playwright и браузер Chromium
RUN pip install playwright
RUN python -m playwright install chromium --with-deps

# Скачиваем и устанавливаем Allure CLI
RUN wget -q -O /tmp/allure.zip "https://github.com/allure-framework/allure2/releases/download/2.35.1/allure-2.35.1.zip" \
    && unzip /tmp/allure.zip -d /opt/ \
    && ln -s /opt/allure-2.35.1/bin/allure /usr/bin/allure \
    && rm /tmp/allure.zip

# Копируем весь проект в контейнер
COPY . /app

# Открываем порт для Allure Server
EXPOSE 8080

# Команда по умолчанию: запускаем тесты и поднимаем Allure Server
# Запускаем тесты и поднимаем Allure сервер, контейнер остаётся активным
CMD bash -c "\
pytest -q --alluredir=allure-results; \
allure serve /app/allure-results --host 0.0.0.0 --port 8080 & \
echo 'Allure server is running on port 8080'; \
echo 'Container ID: $(hostname)'; \
tail -f /dev/null"


