FROM node:20.20.0-alpine AS build
WORKDIR /app
ARG BASE_PATH=/
ENV VITE_BASE_PATH=$BASE_PATH
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
FROM nginx:1.28-alpine
ENV API_UPSTREAM=backend:8000
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
