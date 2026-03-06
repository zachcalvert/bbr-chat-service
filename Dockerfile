FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files at build time so they're baked into the image.
# A dummy SECRET_KEY is used here — it's only needed for Django to load settings.
RUN SECRET_KEY=build-collect-static python manage.py collectstatic --noinput

EXPOSE 8000
