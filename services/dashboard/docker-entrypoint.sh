#!/bin/sh
set -eu

# Decision: generate the htpasswd file at container startup so credentials are
# not baked into the image layers and can be rotated through environment config.
: "${DASHBOARD_BASIC_AUTH_USER:=admin}"
: "${DASHBOARD_BASIC_AUTH_PASSWORD:?DASHBOARD_BASIC_AUTH_PASSWORD must be set}"
: "${BIZBRAIN_API_TOKEN:?BIZBRAIN_API_TOKEN must be set}"

# Rate limiting configuration with sane defaults
: "${RATE_LIMIT_DASHBOARD_AUTH:=10r/m}"
: "${RATE_LIMIT_API_GENERAL:=60r/m}"
: "${RATE_LIMIT_INTAKE_STRICT:=30r/m}"
: "${RATE_LIMIT_DASHBOARD_BURST:=5}"
: "${RATE_LIMIT_API_BURST:=20}"
: "${RATE_LIMIT_INTAKE_BURST:=10}"

# Generate htpasswd file
htpasswd -bc /etc/nginx/.htpasswd "$DASHBOARD_BASIC_AUTH_USER" "$DASHBOARD_BASIC_AUTH_PASSWORD"

# Keep the service credential server-side. The browser only needs the dashboard
# login; nginx authenticates same-origin API calls to BizBrain on its behalf.
escaped_api_token=$(printf '%s' "$BIZBRAIN_API_TOKEN" | sed 's/[\\&#]/\\&/g')
sed -i "s#__BIZBRAIN_API_TOKEN__#${escaped_api_token}#g" /etc/nginx/nginx.conf

# Template nginx configuration with rate limiting values (using # as delimiter)
sed -i "s#rate=10r/m#rate=${RATE_LIMIT_DASHBOARD_AUTH}#g" /etc/nginx/nginx.conf
sed -i "s#rate=60r/m#rate=${RATE_LIMIT_API_GENERAL}#g" /etc/nginx/nginx.conf
sed -i "s#rate=30r/m#rate=${RATE_LIMIT_INTAKE_STRICT}#g" /etc/nginx/nginx.conf
sed -i "s#burst=5 #burst=${RATE_LIMIT_DASHBOARD_BURST} #g" /etc/nginx/nginx.conf
sed -i "s#burst=20 #burst=${RATE_LIMIT_API_BURST} #g" /etc/nginx/nginx.conf
sed -i "s#burst=10 #burst=${RATE_LIMIT_INTAKE_BURST} #g" /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
