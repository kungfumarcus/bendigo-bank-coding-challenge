FROM node:22.16.0-alpine3.21 AS build
WORKDIR /srv
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run lint \
    && npm run format:check \
    && npm run typecheck \
    && npm run build

FROM nginxinc/nginx-unprivileged:1.27.5-alpine3.21 AS runtime
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /srv/dist /usr/share/nginx/html
EXPOSE 8080
