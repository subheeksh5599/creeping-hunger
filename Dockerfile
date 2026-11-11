FROM node:24-slim AS dashboard
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY mcp_server/ mcp_server/
COPY extension/ extension/
COPY hostile/ hostile/
COPY samples/ samples/
COPY web/ web/
COPY --from=dashboard /app/dashboard/dist dashboard/dist
ENV PORT=8787
CMD ["sh", "-c", "cd backend && uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
