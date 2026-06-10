# Honeybook frontend — build the Vue SPA, serve it with nginx, and proxy
# /api + /static to the backend container (same-origin, like the Vite proxy).

# --- build stage -----------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- serve stage -----------------------------------------------------------
FROM nginx:1.27-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
