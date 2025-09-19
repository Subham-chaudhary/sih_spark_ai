FROM python:3.9-slim-buster

WORKDIR /app

# Install system dependencies (common for psycopg2, numpy, pandas, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    wget \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first (cache layer)
COPY requirements.txt ./

# Install Python deps
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . .

EXPOSE 5000

ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
