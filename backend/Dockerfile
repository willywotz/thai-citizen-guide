FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build DATABASE_URL from individual parts injected by docker-compose
ENV DATABASE_URL=""
ENV PYTHONUNBUFFERED=1

# Entrypoint script assembles DATABASE_URL if not already set
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
