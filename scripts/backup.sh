#!/bin/bash
# Резервное копирование PostgreSQL и данных Chimera.
# Запуск: ./scripts/backup.sh
# Cron: 0 3 * * * /path/to/chimera/scripts/backup.sh

set -e

BACKUP_DIR="${BACKUP_DIR:-./data/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/chimera_${TIMESTAMP}.sql.gz"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$BACKUP_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') [BACKUP] Начало резервного копирования..."

# PostgreSQL dump
echo "  Дамп PostgreSQL..."
docker compose exec -T postgres pg_dump \
    -U chimera \
    -d chimera \
    --format=plain \
    --no-owner \
    --no-privileges \
    2>/dev/null | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ] && [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "  ${GREEN}✓ Бэкап создан: $BACKUP_FILE ($SIZE)${NC}"
else
    echo -e "  ${RED}✗ Ошибка создания бэкапа${NC}"
    exit 1
fi

# Бэкап Redis (RDB snapshot)
echo "  Бэкап Redis..."
REDIS_BACKUP="${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"
docker compose exec -T redis redis-cli -a chimera_redis BGSAVE 2>/dev/null
sleep 2
docker compose cp redis:/data/dump.rdb "$REDIS_BACKUP" 2>/dev/null || true
if [ -f "$REDIS_BACKUP" ]; then
    echo -e "  ${GREEN}✓ Redis RDB сохранён${NC}"
fi

# Очистка старых бэкапов
echo "  Очистка бэкапов старше ${RETENTION_DAYS} дней..."
DELETED=$(find "$BACKUP_DIR" -name "chimera_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
find "$BACKUP_DIR" -name "redis_*.rdb" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

if [ "$DELETED" -gt 0 ]; then
    echo -e "  ${YELLOW}Удалено старых бэкапов: $DELETED${NC}"
fi

# Список текущих бэкапов
TOTAL=$(ls -1 "$BACKUP_DIR"/chimera_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

echo ""
echo -e "${GREEN}Резервное копирование завершено${NC}"
echo "  Всего бэкапов: $TOTAL"
echo "  Общий размер: $TOTAL_SIZE"
echo "  Хранение: $RETENTION_DAYS дней"
echo ""
echo "  Восстановление:"
echo "    gunzip < $BACKUP_FILE | docker compose exec -T postgres psql -U chimera -d chimera"
