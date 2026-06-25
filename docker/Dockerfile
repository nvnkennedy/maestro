# Maestro full-stack image: builds the frontend, serves everything from FastAPI
FROM node:18-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11.9-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY app.py pytest.ini ./
COPY --from=frontend-build /build/dist ./frontend/dist

ENV MAESTRO_HOST=0.0.0.0 \
    MAESTRO_PORT=8000 \
    MAESTRO_OPEN_BROWSER=false

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["python", "app.py"]
