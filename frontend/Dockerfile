FROM node:20-alpine AS builder

WORKDIR /app
# Use Taobao npm mirror for fast installs in mainland China
RUN npm config set registry https://registry.npmmirror.com
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ../nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
