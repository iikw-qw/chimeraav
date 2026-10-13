#!/bin/bash
# Обновление Chimera до последней версии.
# Запуск: ./scripts/update.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}══════════════════════════════════════${NC}"
echo -e "${BLUE}  Chimera — Обновление${NC}"
echo -e "${BLUE}══════════════════════════════════════${NC}"
echo ""

# Текущая версия
CURRENT_VERSION=$(grep APP_VERSION .env 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "unknown")
echo -e "  Текущая версия: ${YELLOW}${CURRENT_VERSION}${NC}"

# Бэкап перед обновлением
echo ""
echo -e "${BLUE}1. Резервное копирование...${NC}"
if [ -f scripts/backup.sh ]; then
    bash scripts/backup.sh
    echo -e "${GREEN}✓ Бэкап создан${NC}"
else
    echo -e "${YELLOW}⚠ Скрипт бэкапа не найден, пропускаю${NC}"
fi

# Получение обновлений
echo ""
echo -e "${BLUE}2. Получение обновлений...${NC}"

# Проверка незафиксированных изменений
if [ -d .git ]; then
    if ! git diff --quiet 2>/dev/null; then
        echo -e "${YELLOW}⚠ Обнаружены незафиксированные изменения${NC}"
        git stash
        STASHED=1
    fi

    git pull origin main
    echo -e "${GREEN}✓ Код обновлён${NC}"
else
    echo -e "${YELLOW}⚠ Git не инициализирован, пропускаю pull${NC}"
fi

# Новая версия
NEW_VERSION=$(grep APP_VERSION .env 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "unknown")
echo -e "  Новая версия: ${GREEN}${NEW_VERSION}${NC}"

# Пересборка образов
echo ""
echo -e "${BLUE}3. Пересборка Docker-образов...${NC}"
docker compose build

# Перезапуск сервисов
echo ""
echo -e "${BLUE}4. Перезапуск сервисов...${NC}"
docker compose down
docker compose up -d

# Ожидание
echo ""
echo -e "${BLUE}5. Проверка здоровья...${NC}"
sleep 10

MAX_RETRIES=20
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{}')
    STATUS=$(echo "$HEALTH" | grep -oP '"status":"\K[^"]+' 2>/dev/null || echo "")

    if [ "$STATUS" = "healthy" ]; then
        echo -e "${GREEN}✓ Система здорова${NC}"
        break
    fi

    RETRY=$((RETRY + 1))
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo -e "${RED}✗ Система не отвечает${NC}"
    echo "  Проверьте логи: docker compose logs api"
    exit 1
fi

# Восстановление stash
if [ "${STASHED:-0}" = "1" ]; then
    git stash pop 2>/dev/null || true
fi

# Очистка неиспользуемых образов
echo ""
echo -e "${BLUE}6. Очистка старых образов...${NC}"
docker image prune -f 2>/dev/null || true

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  Обновление завершено!${NC}"
echo -e "${GREEN}  ${CURRENT_VERSION} → ${NEW_VERSION}${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  ${YELLOW}Пользователи получат уведомление о повторном входе${NC}"
echo ""
