# 화면(Next.js) 이미지. 빌드 맥락은 저장소 루트(docker-compose.yml 의 context: .).
# NEXT_PUBLIC_* 는 빌드할 때 화면 코드에 박히므로 빌드 인자로 받는다(비밀값 금지, anon 키는 공개용).
FROM node:22-slim AS build
WORKDIR /web
COPY infra/frontend/package.json infra/frontend/package-lock.json ./
RUN npm ci
COPY infra/frontend/ ./
ARG NEXT_PUBLIC_API_BASE=http://localhost:8001
ARG NEXT_PUBLIC_SUPABASE_URL=
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=
ARG NEXT_PUBLIC_DEV_LOGIN=0
ARG NEXT_PUBLIC_MOCK=0
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_DEV_LOGIN=$NEXT_PUBLIC_DEV_LOGIN \
    NEXT_PUBLIC_MOCK=$NEXT_PUBLIC_MOCK \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:22-slim
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /web ./
EXPOSE 8002
CMD ["node_modules/.bin/next", "start", "-p", "8002"]
