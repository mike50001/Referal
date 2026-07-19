FROM python:3.12-slim

WORKDIR /app

# Сначала зависимости — чтобы кэшировались между сборками
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Затем код бота
COPY . .

# BOT_TOKEN и ADMIN_CHAT_ID передаются как переменные окружения
CMD ["python", "main.py"]
