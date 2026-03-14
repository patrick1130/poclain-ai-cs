# 阶段 1：构建产物
FROM node:18-alpine AS builder

WORKDIR /app

# 复制 package.json 并安装依赖
COPY package*.json ./
RUN npm install

# 复制源代码并构建
COPY . .
RUN npm run build

# 阶段 2：Nginx 部署
FROM nginx:alpine

# 移除默认的 nginx 静态资源
RUN rm -rf /usr/share/nginx/html/*

# 从 builder 阶段复制构建出的 dist 目录到 Nginx 托管目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义的 Nginx 配置文件（处理 Vue 路由和后端 API 代理）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]