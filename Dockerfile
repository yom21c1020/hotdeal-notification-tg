FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN mkdir -p /app/db
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]