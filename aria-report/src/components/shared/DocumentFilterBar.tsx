import { DocumentFilters } from "@/hooks/useDocumentFilters";

interface Props {
  filters: DocumentFilters;
  options: { contentTypes: string[]; sources: string[] };
  stats: { total: number; shown: number; hidden: number; avgRelevance: number };
  onFilter: <K extends keyof DocumentFilters>(key: K, value: DocumentFilters[K]) => void;
  onReset: () => void;
}

/**
 * Filter bar for document lists.
 * Drop it above any document table/grid that uses useDocumentFilters.
 */
export function DocumentFilterBar({ filters, options, stats, onFilter, onReset }: Props) {
  const hasActiveFilters =
    filters.search ||
    filters.minRelevance > 0 ||
    filters.contentType ||
    filters.source ||
    filters.onlyRelevant;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
      {/* Row 1: search + quick stats */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search title, summary, URL…"
          value={filters.search}
          onChange={(e) => onFilter("search", e.target.value)}
          className="min-w-[220px] flex-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        />

        <span className="text-sm text-gray-500 dark:text-gray-400">
          Showing{" "}
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            {stats.shown}
          </span>
          /{stats.total}
          {stats.shown > 0 && (
            <span className="ml-2 text-gray-400">
              · avg relevance{" "}
              <span className="font-medium text-blue-600 dark:text-blue-400">
                {(stats.avgRelevance * 100).toFixed(0)}%
              </span>
            </span>
          )}
        </span>

        {hasActiveFilters && (
          <button
            onClick={onReset}
            className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Row 2: advanced filters */}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {/* Relevance slider */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
            Min relevance
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={filters.minRelevance}
            onChange={(e) => onFilter("minRelevance", parseFloat(e.target.value))}
            className="w-24 accent-blue-600"
          />
          <span className="w-8 text-right text-xs font-medium text-gray-700 dark:text-gray-300">
            {(filters.minRelevance * 100).toFixed(0)}%
          </span>
        </div>

        {/* Content type */}
        {options.contentTypes.length > 0 && (
          <select
            value={filters.contentType}
            onChange={(e) => onFilter("contentType", e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          >
            <option value="">All types</option>
            {options.contentTypes.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        )}

        {/* Source */}
        {options.sources.length > 0 && (
          <select
            value={filters.source}
            onChange={(e) => onFilter("source", e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          >
            <option value="">All sources</option>
            {options.sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        )}

        {/* Only relevant toggle */}
        <label className="flex cursor-pointer items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
          <input
            type="checkbox"
            checked={filters.onlyRelevant}
            onChange={(e) => onFilter("onlyRelevant", e.target.checked)}
            className="rounded accent-blue-600"
          />
          Only relevant
        </label>
      </div>
    </div>
  );
}
