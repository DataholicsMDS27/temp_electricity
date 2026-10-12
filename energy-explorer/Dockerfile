# Build from the repository root so the image can use data/final_predictions_22-26:
#   docker build -f energy-explorer/Dockerfile -t ontario-energy-explorer .
FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY energy-explorer/package.json energy-explorer/package-lock.json ./
RUN npm ci
COPY energy-explorer/index.html energy-explorer/tsconfig.json energy-explorer/vite.config.ts ./
COPY energy-explorer/src ./src
COPY energy-explorer/public ./public
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000 \
    ENERGY_PREDICTOR=backend.parquet_predictor:create_predictor \
    ENERGY_PREDICTIONS_PARQUET=/app/data/grid_predictions.parquet
WORKDIR /app
COPY energy-explorer/backend/requirements.lock.txt ./backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY energy-explorer/backend ./backend
COPY energy-explorer/public/data/fsa-index.json ./public/data/fsa-index.json
COPY data/final_predictions_22-26/grid_predictions.parquet ./data/grid_predictions.parquet
COPY --from=frontend /build/dist ./dist
RUN useradd --create-home --uid 10001 explorer
USER explorer
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn backend.production:app --host 0.0.0.0 --port ${PORT:-10000}"]
