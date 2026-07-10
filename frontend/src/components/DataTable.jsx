import { Fragment, useMemo, useState } from "react";

/**
 * Generic client-side sortable/filterable/scrollable table.
 *
 * columns: [{
 *   key: string (unique),
 *   label: string,
 *   sortValue?: (row) => string | number,   // omit to disable sorting for this column
 *   filterValue?: (row) => string,          // omit to disable the search box for this column
 *   render?: (row) => ReactNode,            // defaults to String(sortValue(row) ?? "")
 * }]
 * rows: array of data objects
 * rowKey: (row) => string | number
 * expandedContent?: (row) => ReactNode -- if provided, clicking a row
 *   toggles an extra detail row rendered directly beneath it (single
 *   row expanded at a time). Omit entirely for a plain, non-expandable
 *   table. If you also render clickable controls (buttons, links)
 *   inside a column's render() on a table that uses expandedContent,
 *   call e.stopPropagation() in their onClick so they don't also
 *   toggle the row.
 *
 * All sorting/filtering happens in memory against the rows already
 * passed in -- callers are responsible for fetching the underlying
 * data (typically once, lazily, when a report tab is first opened).
 * This component doesn't make any network calls itself.
 */
function defaultCellText(col, row) {
  // sortValue is often normalized for comparison purposes (e.g.
  // lowercased for case-insensitive sort) and isn't necessarily what
  // should be shown to the user -- filterValue is closer to a raw
  // display value, so prefer it when no explicit render() is given.
  if (col.filterValue) return String(col.filterValue(row) ?? "");
  if (col.sortValue) return String(col.sortValue(row) ?? "");
  return "";
}

export default function DataTable({
  columns,
  rows,
  rowKey,
  emptyMessage = "Nothing to show.",
  maxHeight = "420px",
  expandedContent,
}) {
  const [sort, setSort] = useState(null); // { key, dir: 'asc' | 'desc' } | null
  const [filters, setFilters] = useState({}); // { [columnKey]: string }
  const [expandedKey, setExpandedKey] = useState(null);

  function handleHeaderClick(col) {
    if (!col.sortValue) return;
    setSort((prev) => {
      if (!prev || prev.key !== col.key) return { key: col.key, dir: "asc" };
      return { key: col.key, dir: prev.dir === "asc" ? "desc" : "asc" };
    });
  }

  const filteredSorted = useMemo(() => {
    let result = rows;

    const activeFilters = Object.entries(filters).filter(([, v]) => v && v.trim() !== "");
    if (activeFilters.length > 0) {
      result = result.filter((row) =>
        activeFilters.every(([key, value]) => {
          const col = columns.find((c) => c.key === key);
          if (!col?.filterValue) return true;
          const cell = col.filterValue(row);
          return String(cell ?? "").toLowerCase().includes(value.trim().toLowerCase());
        })
      );
    }

    if (sort) {
      const col = columns.find((c) => c.key === sort.key);
      if (col?.sortValue) {
        result = [...result].sort((a, b) => {
          const av = col.sortValue(a);
          const bv = col.sortValue(b);
          if (av == null && bv == null) return 0;
          if (av == null) return 1; // nulls last regardless of direction
          if (bv == null) return -1;
          if (av < bv) return sort.dir === "asc" ? -1 : 1;
          if (av > bv) return sort.dir === "asc" ? 1 : -1;
          return 0;
        });
      }
    }

    return result;
  }, [rows, filters, sort, columns]);

  const hasAnyFilterableColumn = columns.some((c) => c.filterValue);

  return (
    <div className="rounded-xl border border-ink/10 overflow-hidden">
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full text-sm">
          <thead className="bg-ink/5 text-left text-xs text-ink/50 sticky top-0 z-10">
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 font-medium select-none">
                  <button
                    type="button"
                    onClick={() => handleHeaderClick(col)}
                    disabled={!col.sortValue}
                    className={`flex items-center gap-1 ${col.sortValue ? "cursor-pointer hover:text-ink" : "cursor-default"}`}
                  >
                    {col.label}
                    {sort?.key === col.key && <span aria-hidden="true">{sort.dir === "asc" ? "▲" : "▼"}</span>}
                  </button>
                </th>
              ))}
            </tr>
            {hasAnyFilterableColumn && (
              <tr className="bg-paper">
                {columns.map((col) => (
                  <th key={col.key} className="px-2 py-1.5 font-normal">
                    {col.filterValue && (
                      <input
                        type="text"
                        value={filters[col.key] || ""}
                        onChange={(e) => setFilters((f) => ({ ...f, [col.key]: e.target.value }))}
                        placeholder="Search…"
                        aria-label={`Filter ${col.label}`}
                        className="w-full rounded-md border border-ink/10 px-2 py-1 text-xs font-normal focus:outline-none focus:ring-1 focus:ring-accent/40"
                      />
                    )}
                  </th>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {filteredSorted.map((row) => {
              const key = rowKey(row);
              const isExpanded = expandedContent && expandedKey === key;
              return (
                <Fragment key={key}>
                  <tr
                    onClick={expandedContent ? () => setExpandedKey(isExpanded ? null : key) : undefined}
                    className={`border-t border-ink/10 ${expandedContent ? "cursor-pointer hover:bg-ink/[0.02]" : ""}`}
                  >
                    {columns.map((col) => (
                      <td key={col.key} className="px-3 py-2">
                        {col.render ? col.render(row) : defaultCellText(col, row)}
                      </td>
                    ))}
                  </tr>
                  {isExpanded && (
                    <tr className="border-t border-ink/10 bg-ink/[0.015]">
                      <td colSpan={columns.length} className="px-3 py-3">
                        {expandedContent(row)}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {filteredSorted.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-ink/40">
                  {rows.length === 0 ? emptyMessage : "No rows match your search."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
