FROM node:20-alpine AS build
WORKDIR /app
COPY . .
# Simple static serve — no build step needed for vanilla HTML/CSS/JS
RUN npm install -g serve

EXPOSE 3000
CMD ["serve", "-s", ".", "-l", "3000"]
