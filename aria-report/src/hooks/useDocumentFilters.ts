import { useMemo, useState } from "react";

export interface DocumentFilters {
  search: string;
  minRelevance: number;       // 0–1
  contentType: string;        // "" = all
  source: string;             // "" = all
  onlyRelevant: boolean;      // hide is_relevant=false
}

export const DEFAULT_FILTERS: DocumentFilters = {
  search: "",
  minRelevance: 0,
  contentType: "",
  source: "",
  onlyRelevant: false,
};

export type DocLike = Record<string, unknown>;

/**
 * Client-side document filtering hook.
 *
 * Usage:
 *   const { filters, setFilter, filtered, stats } = useDocumentFilters(documents);
 */
export function useDocumentFilters(documents: DocLike[]) {
  const [filters, setFilters] = useState<DocumentFilters>(DEFAULT_FILTERS);

  const setFilter = <K extends keyof DocumentFilters>(
    key: K,
    value: DocumentFilters[K]
  ) => setFilters((prev) => ({ ...prev, [key]: value }));

  const resetFilters = () => setFilters(DEFAULT_FILTERS);

  // Derived filter options from the actual documents
  const options = useMemo(() => {
    const contentTypes = new Set<string>();
    const sources = new Set<string>();
    for (const doc of documents) {
      if (doc.content_type) contentTypes.add(String(doc.content_type));
      const src =
        (doc.platform as string) ||
        (doc.source_type as string) ||
        (doc.source as string);
      if (src) sources.add(src);
    }
    return {
      contentTypes: Array.from(contentTypes).sort(),
      sources: Array.from(sources).sort(),
    };
  }, [documents]);

  const filtered = useMemo(() => {
    const query = filters.search.toLowerCase();
    return documents.filter((doc) => {
      // Text search across title, summary, url
      if (query) {
        const haystack = [
          doc.title,
          doc.summary,
          doc.url,
          doc.text,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      // Relevance threshold
      const score = typeof doc.relevance_score === "number" ? doc.relevance_score : 0;
      if (score < filters.minRelevance) return false;
      // Only relevant
      if (filters.onlyRelevant && doc.is_relevant === false) return false;
      // Content type
      if (filters.contentType && doc.content_type !== filters.contentType) return false;
      // Source
      if (filters.source) {
        const src =
          (doc.platform as string) ||
          (doc.source_type as string) ||
          (doc.source as string);
        if (src !== filters.source) return false;
      }
      return true;
    });
  }, [documents, filters]);

  const stats = useMemo(
    () => ({
      total: documents.length,
      shown: filtered.length,
      hidden: documents.length - filtered.length,
      avgRelevance:
        filtered.length > 0
          ? filtered.reduce(
              (sum, d) =>
                sum + (typeof d.relevance_score === "number" ? d.relevance_score : 0),
              0
            ) / filtered.length
          : 0,
    }),
    [documents, filtered]
  );

  return { filters, setFilter, resetFilters, filtered, options, stats };
}
