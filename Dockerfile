# JRCA — single-container deploy: builds the React frontend, serves it + the API with uvicorn.
# Works on Render.com free tier, Hugging Face Spaces (Docker), Railway, Fly.io.

FROM node:22-slim AS frontend
WORKDIR /ui
COPY ["Expense Reimbursement Assistant/package.json", "Expense Reimbursement Assistant/package-lock.json", "./"]
RUN npm ci
COPY ["Expense Reimbursement Assistant/", "./"]
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/ ./apps/api/
COPY --from=frontend /ui/dist ./static

# Serve the built frontend from the same process as the API
RUN printf '%s\n' \
    'from pathlib import Path' \
    'from fastapi.staticfiles import StaticFiles' \
    'from app.main import app' \
    'app.mount("/", StaticFiles(directory=str(Path(__file__).resolve().parents[2] / "static"), html=True), name="ui")' \
    > apps/api/app/serve.py

# HF Spaces runs as uid 1000; make the data dir writable for any user
RUN mkdir -p /data && chmod 777 /data
ENV DATA_DIR=/data
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn app.serve:app --app-dir apps/api --host 0.0.0.0 --port ${PORT}"]
