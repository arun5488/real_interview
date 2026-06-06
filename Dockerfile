FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY params.yaml gunicorn.conf.py ./

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.real_interview.backend.wsgi:app"]
