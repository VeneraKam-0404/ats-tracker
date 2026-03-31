FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent data on Render goes to /data
ENV ATS_DATA_DIR=/data/db
ENV ATS_UPLOAD_DIR=/data/uploads
ENV ATS_SECRET_KEY=change-me-in-render-env
ENV ATS_RELOAD=false
ENV HOST=0.0.0.0
ENV PORT=10000

EXPOSE 10000

CMD ["python", "run.py"]
