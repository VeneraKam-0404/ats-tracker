FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories with full permissions (for both disk and no-disk cases)
RUN mkdir -p /data/db /data/uploads && chmod -R 777 /data

# Fallback directories inside the app (used if /data is not a mounted disk)
RUN mkdir -p /app/data /app/uploads

ENV ATS_DATA_DIR=/data/db
ENV ATS_UPLOAD_DIR=/data/uploads
ENV ATS_SECRET_KEY=change-me-in-render-env
ENV ATS_RELOAD=false
ENV HOST=0.0.0.0
ENV PORT=10000

EXPOSE 10000

CMD ["python", "run.py"]
