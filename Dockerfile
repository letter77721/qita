FROM node:22-bookworm-slim AS web
WORKDIR /web
RUN npm install --global pnpm@11.25.0
COPY mobile/package.json mobile/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY mobile/App.js mobile/index.js mobile/app.json ./
COPY mobile/LiveCamera.js mobile/LiveCamera.web.js ./
ENV EXPO_NO_TELEMETRY=1 CI=1
RUN pnpm build:web

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY agents ./agents
COPY backend ./backend
COPY database ./database
COPY services ./services
COPY workflows ./workflows
COPY --from=web /web/dist ./mobile/dist
RUN mkdir -p /var/data/uploads
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers"]
