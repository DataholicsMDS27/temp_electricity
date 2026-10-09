FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
COPY backend/requirements.lock.txt ./backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY backend ./backend
COPY public/data/fsa-index.json ./public/data/fsa-index.json
COPY --from=frontend /build/dist ./dist
RUN useradd --create-home --uid 10001 explorer
USER explorer
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn backend.production:app --host 0.0.0.0 --port ${PORT:-10000}"]
