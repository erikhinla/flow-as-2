#!/bin/sh
set -eu

# Decision: generate the htpasswd file at container startup so credentials are
# not baked into the image layers and can be rotated through environment config.
: "${DASHBOARD_BASIC_AUTH_USER:=admin}"
: "${DASHBOARD_BASIC_AUTH_PASSWORD:?DASHBOARD_BASIC_AUTH_PASSWORD must be set}"
: "${BIZBRAIN_API_TOKEN:?BIZBRAIN_API_TOKEN must be set}"

reject_placeholder() {
  value=$1
  name=$2
  case "$value" in
    ""|change-me|change-me-dashboard-password|replace_with_long_random_token|replace_with_same_value_as_bizbrain_api_token_unless_rotated|replace_with_strong_password|replace_with_dashboard_password|replace_with_webhook_secret|password|admin)
      echo "$name is a placeholder and cannot be used on the live desk" >&2
      exit 1
      ;;
  esac
  if [ "${#value}" -lt 24 ]; then
    echo "$name must be at least 24 characters" >&2
    exit 1
  fi
  case "$value" in
    *\"*|*\'*|*" "*|*"$"*|*"\`"*|*"@"*|*"/"*|*"?"*|*"#"*|*"&"*|*:*)
      echo "$name contains a character that cannot be embedded safely" >&2
      exit 1
      ;;
  esac
}

reject_placeholder "$DASHBOARD_BASIC_AUTH_PASSWORD" "DASHBOARD_BASIC_AUTH_PASSWORD"
reject_placeholder "$BIZBRAIN_API_TOKEN" "BIZBRAIN_API_TOKEN"

diagnostic_url=${DIAGNOSTIC_PUBLIC_URL:-/diagnostic?type=bizbuilders}
case "$diagnostic_url" in
  *\"*|*\'*|*"\`"*)
    echo "DIAGNOSTIC_PUBLIC_URL contains an unsafe character" >&2
    exit 1
    ;;
esac
printf 'window.__FLOW_DESK__ = { diagnosticUrl: "%s" };\n' "$diagnostic_url" > /usr/share/nginx/html/desk-config.js
printf 'proxy_set_header X-API-Token "%s";\n' "$BIZBRAIN_API_TOKEN" > /etc/nginx/api-token.conf
if [ -n "${HANDOFF_DESK_TOKEN:-}" ]; then
  reject_placeholder "$HANDOFF_DESK_TOKEN" "HANDOFF_DESK_TOKEN"
  printf 'proxy_set_header X-Desk-Token "%s";\n' "$HANDOFF_DESK_TOKEN" > /etc/nginx/handoff-token.conf
else
  printf '# HANDOFF_DESK_TOKEN not set: the gateway rejects /handoff/\n' > /etc/nginx/handoff-token.conf
fi

# Rate limiting configuration with sane defaults
: "${RATE_LIMIT_DASHBOARD_AUTH:=10r/m}"
: "${RATE_LIMIT_API_GENERAL:=60r/m}"
: "${RATE_LIMIT_INTAKE_STRICT:=30r/m}"
: "${RATE_LIMIT_DASHBOARD_BURST:=5}"
: "${RATE_LIMIT_API_BURST:=20}"
: "${RATE_LIMIT_INTAKE_BURST:=10}"

# Generate htpasswd file
htpasswd -bc /etc/nginx/.htpasswd "$DASHBOARD_BASIC_AUTH_USER" "$DASHBOARD_BASIC_AUTH_PASSWORD"

# Template nginx configuration with rate limiting values (using # as delimiter)
sed -i "s#rate=10r/m#rate=${RATE_LIMIT_DASHBOARD_AUTH}#g" /etc/nginx/nginx.conf
sed -i "s#rate=60r/m#rate=${RATE_LIMIT_API_GENERAL}#g" /etc/nginx/nginx.conf
sed -i "s#rate=30r/m#rate=${RATE_LIMIT_INTAKE_STRICT}#g" /etc/nginx/nginx.conf
sed -i "s#burst=5 #burst=${RATE_LIMIT_DASHBOARD_BURST} #g" /etc/nginx/nginx.conf
sed -i "s#burst=20 #burst=${RATE_LIMIT_API_BURST} #g" /etc/nginx/nginx.conf
sed -i "s#burst=10 #burst=${RATE_LIMIT_INTAKE_BURST} #g" /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'