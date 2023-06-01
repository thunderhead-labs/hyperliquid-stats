FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN apt-get update && apt-get install -y cron

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
