import { useMemo, useState } from 'react'
import Button from './Button'

const collator = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' })

function compareValues(left, right) {
  if (left == null) return right == null ? 0 : -1
  if (right == null) return 1
  const leftNumber = Number(left)
  const rightNumber = Number(right)
  if (String(left).trim() && String(right).trim() && Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
    return leftNumber - rightNumber
  }
  return collator.compare(String(left), String(right))
}

export default function DataTable({
  columns,
  rows,
  rowKey = 'id',
  loading = false,
  emptyMessage = 'Aucun résultat à afficher.',
  page,
  pageSize = 10,
  totalItems,
  onPageChange,
  sortKey,
  sortDirection = 'asc',
  onSortChange,
  searchValue,
  onSearchChange,
  searchLabel = 'Rechercher',
}) {
  const [localSearch, setLocalSearch] = useState('')
  const [localPage, setLocalPage] = useState(1)
  const [localSort, setLocalSort] = useState({ key: '', direction: 'asc' })
  const activeSearch = searchValue ?? localSearch
  const activeSortKey = sortKey ?? localSort.key
  const activeSortDirection = sortKey ? sortDirection : localSort.direction
  const isServerSearch = typeof onSearchChange === 'function'
  const isServerPagination = typeof onPageChange === 'function'

  const filteredRows = useMemo(() => {
    if (isServerSearch || !activeSearch.trim()) return rows
    const query = activeSearch.trim().toLocaleLowerCase('fr')
    return rows.filter((row) =>
      columns.some((column) => {
        const value = column.accessor ? column.accessor(row) : row[column.key]
        return value != null && String(value).toLocaleLowerCase('fr').includes(query)
      }),
    )
  }, [activeSearch, columns, isServerSearch, rows])

  const sortedRows = useMemo(() => {
    if (!activeSortKey) return filteredRows
    const column = columns.find((item) => item.key === activeSortKey)
    if (!column) return filteredRows
    const direction = activeSortDirection === 'desc' ? -1 : 1
    return [...filteredRows].sort((left, right) => {
      const leftValue = column.accessor ? column.accessor(left) : left[column.key]
      const rightValue = column.accessor ? column.accessor(right) : right[column.key]
      return compareValues(leftValue, rightValue) * direction
    })
  }, [activeSortDirection, activeSortKey, columns, filteredRows])

  const currentPage = page ?? localPage
  const itemCount = isServerPagination ? totalItems ?? rows.length : sortedRows.length
  const pageCount = Math.max(1, Math.ceil(itemCount / pageSize))
  const visibleRows = isServerPagination
    ? sortedRows
    : sortedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  function changeSearch(value) {
    if (onSearchChange) onSearchChange(value)
    else setLocalSearch(value)
    if (onPageChange) onPageChange(1)
    else setLocalPage(1)
  }

  function changeSort(key) {
    const direction = activeSortKey === key && activeSortDirection === 'asc' ? 'desc' : 'asc'
    if (onSortChange) onSortChange(key, direction)
    else setLocalSort({ key, direction })
  }

  function changePage(nextPage) {
    if (nextPage < 1 || nextPage > pageCount) return
    if (onPageChange) onPageChange(nextPage)
    else setLocalPage(nextPage)
  }

  const firstItem = itemCount === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const lastItem = Math.min(currentPage * pageSize, itemCount)

  return (
    <section className="table-card" aria-label="Résultats">
      <div className="table-toolbar">
        <label className="table-search">
          <span>{searchLabel}</span>
          <input
            type="search"
            value={activeSearch}
            onChange={(event) => changeSearch(event.target.value)}
            aria-label={searchLabel}
          />
        </label>
        <span className="table-count">{itemCount} résultat{itemCount > 1 ? 's' : ''}</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((column) => {
                const active = activeSortKey === column.key
                const ariaSort = active
                  ? activeSortDirection === 'asc' ? 'ascending' : 'descending'
                  : 'none'
                return (
                  <th key={column.key} scope="col" aria-sort={column.sortable ? ariaSort : undefined}>
                    {column.sortable ? (
                      <button
                        className="sort-button"
                        type="button"
                        onClick={() => changeSort(column.key)}
                      >
                        {column.header}
                        <span aria-hidden="true">{active ? activeSortDirection === 'asc' ? ' ↑' : ' ↓' : ' ↕'}</span>
                      </button>
                    ) : column.header}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td className="table-message" colSpan={columns.length} role="status">Chargement…</td></tr>
            ) : visibleRows.length === 0 ? (
              <tr><td className="table-message" colSpan={columns.length}>{emptyMessage}</td></tr>
            ) : visibleRows.map((row, index) => (
              <tr key={typeof rowKey === 'function' ? rowKey(row) : row[rowKey] ?? index}>
                {columns.map((column) => {
                  const value = column.accessor ? column.accessor(row) : row[column.key]
                  return <td key={column.key}>{column.render ? column.render(value, row) : value ?? '—'}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-pagination">
        <span>{firstItem}–{lastItem} sur {itemCount}</span>
        <div className="pagination-actions">
          <Button variant="secondary" size="small" onClick={() => changePage(currentPage - 1)} disabled={currentPage <= 1}>
            Précédent
          </Button>
          <span aria-live="polite">Page {currentPage} sur {pageCount}</span>
          <Button variant="secondary" size="small" onClick={() => changePage(currentPage + 1)} disabled={currentPage >= pageCount}>
            Suivant
          </Button>
        </div>
      </div>
    </section>
  )
}
