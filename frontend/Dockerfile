# Multi-stage: build the static bundle with Node, then serve it with nginx
# — the running container never needs Node, only the built dist/ output.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Vite inlines VITE_* variables into the bundle at build time, not runtime
# — this must be the URL the *browser* can reach (the host-published API
# port), not a docker-network-internal hostname like `http://api:8000`.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
