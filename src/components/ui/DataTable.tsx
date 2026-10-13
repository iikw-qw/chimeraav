import { useMemo, useState, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'

export interface Column<T> {
  key: string
  header: ReactNode
  width?: string | number
  className?: string
  render?: (row: T, index: number) => ReactNode
  accessor?: (row: T) => ReactNode
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  rowKey: (row: T, index: number) => string
  selectable?: boolean
  selected?: string[]
  onSelectChange?: (ids: string[]) => void
  pageSize?: number
  emptyMessage?: ReactNode
  className?: string
  onRowClick?: (row: T) => void
}

export function DataTable<T>({
  columns,
  data,
  rowKey,
  selectable,
  selected,
  onSelectChange,
  pageSize = 25,
  emptyMessage = 'Нет данных',
  className,
  onRowClick,
}: DataTableProps<T>) {
  const [page, setPage] = useState(0)
  const totalPages = Math.max(1, Math.ceil(data.length / pageSize))
  const safePage = Math.min(page, totalPages - 1)

  const slice = useMemo(
    () => data.slice(safePage * pageSize, safePage * pageSize + pageSize),
    [data, safePage, pageSize],
  )

  const allKeys = useMemo(() => slice.map((r, i) => rowKey(r, i)), [slice, rowKey])
  const allSelected =
    selectable && allKeys.length > 0 && allKeys.every((k) => selected?.includes(k))

  const toggle = (id: string) => {
    if (!onSelectChange) return
    const set = new Set(selected ?? [])
    if (set.has(id)) set.delete(id)
    else set.add(id)
    onSelectChange(Array.from(set))
  }

  const toggleAll = () => {
    if (!onSelectChange) return
    if (allSelected) {
      const next = (selected ?? []).filter((id) => !allKeys.includes(id))
      onSelectChange(next)
    } else {
      const next = Array.from(new Set([...(selected ?? []), ...allKeys]))
      onSelectChange(next)
    }
  }

  return (
    <div className={cn('flex flex-col', className)}>
      <div className="overflow-auto rounded-xl border border-[--line-1]">
        <table className="w-full border-collapse">
          <thead className="bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
            <tr>
              {selectable && (
                <th className="w-10 px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={!!allSelected}
                    onChange={toggleAll}
                    className="h-4 w-4 cursor-pointer accent-[--blue]"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={{ width: col.width }}
                  className={cn('px-4 py-3 text-left font-medium', col.className)}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="px-4 py-10 text-center text-sm text-[--txt-3]"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              slice.map((row, i) => {
                const id = rowKey(row, i)
                const isSelected = selected?.includes(id)
                return (
                  <tr
                    key={id}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      'border-t border-[--line-1] transition-colors hover:bg-[--bg-3]/50',
                      onRowClick && 'cursor-pointer',
                      isSelected && 'bg-[--blue]/5',
                    )}
                  >
                    {selectable && (
                      <td
                        className="px-4 py-3"
                        onClick={(e) => {
                          e.stopPropagation()
                          toggle(id)
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={!!isSelected}
                          onChange={() => toggle(id)}
                          className="h-4 w-4 cursor-pointer accent-[--blue]"
                        />
                      </td>
                    )}
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={cn('px-4 py-3 text-sm text-[--txt-1]', col.className)}
                      >
                        {col.render
                          ? col.render(row, i)
                          : col.accessor
                            ? col.accessor(row)
                            : (row as Record<string, ReactNode>)[col.key]}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {data.length > pageSize && (
        <div className="mt-3 flex items-center justify-between text-xs text-[--txt-2]">
          <div>
            {safePage * pageSize + 1}–{Math.min(data.length, (safePage + 1) * pageSize)} из{' '}
            {data.length}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={safePage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-[--line-2] text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              {safePage + 1} / {totalPages}
            </span>
            <button
              type="button"
              disabled={safePage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-[--line-2] text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
