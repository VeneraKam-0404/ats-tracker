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

EXPOSE 10000

CMD ["python", "run.py"]
