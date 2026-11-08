# SupplySense Nexus - Frontend Build & Runtime Container

# Stage 1: Build static assets using Node.js
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency definitions
COPY package.json package-lock.json ./

# Clean install of dependencies
RUN npm ci

# Copy frontend source files
COPY . .

# Run production build (typecheck + vite build)
RUN npm run build

# Stage 2: Serve static assets using Nginx
FROM nginx:alpine

# Remove default nginx configurations
RUN rm -rf /etc/nginx/conf.d/*

# Copy custom reverse proxy and SPA routing configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check verifying nginx responds on port 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
