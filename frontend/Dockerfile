FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build

# Production stage — serve with nginx
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html

# nginx config: SPA fallback + proper cache headers
# index.html → no-cache (ensures fresh build on every deploy)
# static/* (hashed filenames) → 1 year immutable cache
RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    # Never cache index.html so browsers always fetch the latest build\n\
    location = /index.html {\n\
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";\n\
        add_header Pragma "no-cache";\n\
        add_header Expires "0";\n\
        try_files $uri /index.html;\n\
    }\n\
\n\
    # Long-term cache for hashed static assets (JS/CSS/media)\n\
    location /static/ {\n\
        add_header Cache-Control "public, max-age=31536000, immutable";\n\
        try_files $uri =404;\n\
    }\n\
\n\
    # SPA fallback for all other routes\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
