#!/usr/bin/env bash
# Bitta buyruq bilan to'liq production deploy (root sifatida serverda):
#   bash scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

DOMAIN="${DOMAIN:-edu.thesofmebel.uz}"

# ── 1. Host'dagi nginx/apache — 80/443 portlarni bo'shatamiz (hammasi Docker ichida)
#    Configlar O'CHIRILMAYDI, faqat servis to'xtatiladi — kerak bo'lsa `systemctl start nginx` bilan qaytariladi.
for svc in nginx apache2; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo "!! DIQQAT: host'dagi '$svc' to'xtatiladi (80/443 endi Docker'dagi Caddy'da)."
    if [ "$svc" = nginx ] && [ -d /etc/nginx/sites-enabled ]; then
      echo "   nginx'da yoqilgan saytlar shular edi:"
      ls /etc/nginx/sites-enabled 2>/dev/null || true
    fi
    systemctl stop "$svc"
    systemctl disable "$svc" >/dev/null 2>&1 || true
  fi
done

# ── 2. .env — yo'q bo'lsa sekretlarni avtomatik generatsiya qilib yaratamiz
if [ ! -f .env ]; then
  echo ">> .env yaratilmoqda (SECRET_KEY, parollar avtomatik generatsiya)..."
  cat > .env <<EOF
DJANGO_ENV=prod
DOMAIN=$DOMAIN
SECRET_KEY=$(openssl rand -hex 40)
ALLOWED_HOSTS=$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN
TIME_ZONE=Asia/Tashkent
POSTGRES_DB=edtech
POSTGRES_USER=edtech
POSTGRES_PASSWORD=$(openssl rand -hex 20)
LIVEKIT_API_KEY=fokus_prod
LIVEKIT_API_SECRET=$(openssl rand -hex 24)
LIVEKIT_URL=wss://$DOMAIN/livekit
EOF
  chmod 600 .env
else
  echo ">> mavjud .env ishlatiladi."
fi

# ── 3. Firewall (ufw aktiv bo'lsa) — kerakli portlarni ochamiz
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  echo ">> ufw portlari ochilmoqda..."
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw allow 443/udp >/dev/null
  ufw allow 7881/tcp >/dev/null
  ufw allow 7882/udp >/dev/null
fi

# ── 4. Docker stack — build + up
echo ">> Docker stack ko'tarilmoqda (build birinchi safar bir necha daqiqa oladi)..."
docker compose -f docker-compose.prod.yml up -d --build

echo
echo "======================================================"
echo "  Tayyor: https://$DOMAIN"
echo "  Admin yaratish:"
echo "    docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser"
echo "  Loglar:"
echo "    docker compose -f docker-compose.prod.yml logs -f"
echo "======================================================"
