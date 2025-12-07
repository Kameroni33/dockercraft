FROM nginx:alpine

# Copy nginx config
COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf

# Expose server port
EXPOSE 80

# NOTE: web files will be mounted as volume