FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create uploads directory
RUN mkdir -p /data/uploads && chmod -R 777 /data

ENV ATS_UPLOAD_DIR=/data/uploads
ENV ATS_SECRET_KEY=change-me-in-render-env
ENV ATS_RELOAD=false
ENV HOST=0.0.0.0
ENV PORT=10000
ENV SMTP_HOST=""
ENV SMTP_PORT=587
ENV SMTP_USER=""
ENV SMTP_PASSWORD=""

EXPOSE 10000

CMD ["python", "run.py"]
