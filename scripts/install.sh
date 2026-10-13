#!/bin/bash
# Установка Chimera v5.0 с нуля.
# Зависит от: Docker, Docker Compose, git

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}══════════════════════════════════════${NC}"
echo -e "${BLUE}  Chimera v5.0 — Установка${NC}"
echo -e "${BLUE}══════════════════════════════════════${NC}"
echo ""

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker не установлен${NC}"
    echo "  Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker найден$(docker --version | grep -oP 'version \K[^,]+')${NC}"

# Проверка Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose не найден${NC}"
    echo "  Установите Docker Compose V2"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose найден${NC}"

# Проверка .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ Файл .env не найден, создаю из шаблона...${NC}"
    cat > .env << 'ENVEOF'
DATABASE_URL=postgresql+asyncpg://chimera:chimera_pass@postgres:5432/chimera
REDIS_URL=redis://:chimera_redis@redis:6379/0
SECRET_KEY=change-me-to-random-secret-key-at-least-32-chars
APP_VERSION=5.0.0
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
TWOCAPTCHA_API_KEY=
LLM_API_KEY=
LLM_PROVIDER=claude
POSTGRES_USER=chimera
POSTGRES_PASSWORD=chimera_pass
POSTGRES_DB=chimera
REDIS_PASSWORD=chimera_redis
ENVEOF
    echo -e "${GREEN}✓ .env создан — отредактируйте SECRET_KEY!${NC}"
fi

# Создание директорий
echo ""
echo -e "${BLUE}Создание директорий...${NC}"
mkdir -p data/postgres data/redis data/uploads data/backups
echo -e "${GREEN}✓ Директории созданы${NC}"

# Сборка и запуск
echo ""
echo -e "${BLUE}Сборка Docker-образов...${NC}"
docker compose build --no-cache

echo ""
echo -e "${BLUE}Запуск сервисов...${NC}"
docker compose up -d

echo ""
echo -e "${BLUE}Ожидание готовности сервисов...${NC}"
sleep 10

# Проверка здоровья
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{}')
    STATUS=$(echo "$HEALTH" | grep -oP '"status":"\K[^"]+' 2>/dev/null || echo "")

    if [ "$STATUS" = "healthy" ]; then
        echo -e "${GREEN}✓ API здоров${NC}"
        break
    fi

    RETRY=$((RETRY + 1))
    echo -e "  Попытка $RETRY/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo -e "${RED}✗ API не отвечает после $MAX_RETRIES попыток${NC}"
    echo "  Проверьте логи: docker compose logs api"
    exit 1
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  Chimera v5.0 установлена!${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  Веб-интерфейс: ${BLUE}http://localhost:3000${NC}"
echo -e "  API:            ${BLUE}http://localhost:8000${NC}"
echo -e "  Prometheus:     ${BLUE}http://localhost:9090${NC}"
echo -e "  Grafana:        ${BLUE}http://localhost:3001${NC} (admin/admin)"
echo ""
echo -e "  ${YELLOW}Следующий шаг: откройте http://localhost:3000 и зарегистрируйтесь${NC}"
echo ""
