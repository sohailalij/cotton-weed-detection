# Build stage: install dependencies and compile the React app.
FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite writes this address into the JavaScript at build time, so it cannot be
# changed when the container starts. Pass it with --build-arg.
ARG VITE_API_URL=http://127.0.0.1:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Serve stage: a small nginx that runs as a non-root user.
FROM nginxinc/nginx-unprivileged:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080