FROM python:3.9-slim-buster

WORKDIR /app

# Copy requirements first (cache layer)
COPY requirements.txt ./

# Install Python deps
RUN pip install  -r requirements.txt

# Copy the app code
COPY . .

EXPOSE 5000

ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
