/**
 * Бейдж статуса с цветовой индикацией.
 * Depends on: React
 */

import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const STATUS_COLORS: Record<string, string> = {
  // Устройства
  online: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  offline: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  busy: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  paused: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  calibrating: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',

  // Аккаунты
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  warming: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  banned: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  suspended: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  limited: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',

  // Задачи
  pending: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  queued: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  running: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  completed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  retrying: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  dead: 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-500',

  // Посты
  draft: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  scheduled: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  publishing: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  published: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',

  // Ответы на комментарии
  sent: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  skipped: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',

  // Логин
  logged_in: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  logged_out: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  captcha: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
};

const STATUS_LABELS: Record<string, string> = {
  online: 'Онлайн',
  offline: 'Офлайн',
  busy: 'Занят',
  error: 'Ошибка',
  paused: 'Пауза',
  calibrating: 'Калибровка',
  active: 'Активен',
  warming: 'Прогрев',
  banned: 'Бан',
  suspended: 'Заблокирован',
  limited: 'Ограничен',
  pending: 'Ожидание',
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Завершено',
  failed: 'Ошибка',
  retrying: 'Повтор',
  dead: 'Мёртв',
  draft: 'Черновик',
  scheduled: 'Запланирован',
  publishing: 'Публикация',
  published: 'Опубликован',
  sent: 'Отправлен',
  skipped: 'Пропущен',
  logged_in: 'Вошёл',
  logged_out: 'Вышел',
  captcha: 'Капча',
};

const SIZE_CLASSES = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  className = '',
}) => {
  const colorClass = STATUS_COLORS[status] || 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  const label = STATUS_LABELS[status] || status;
  const sizeClass = SIZE_CLASSES[size];

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${colorClass} ${sizeClass} ${className}`}>
      {label}
    </span>
  );
};
