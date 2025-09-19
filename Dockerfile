FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
