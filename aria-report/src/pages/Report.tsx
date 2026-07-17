import { useParams, useNavigate } from "react-router-dom";
import { Download, Play, FileText, FileJson, Table } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RunRow } from "@/components/shared/RunRow";
import { useRun, useRunDocuments } from "@/hooks/useRun";
import { useRuns } from "@/hooks/useRuns";
import { api } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

export default function Report() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: runsData, isLoading: runsLoading } = useRuns();
  const { data: run, isLoading, isError } = useRun(runId ?? "");
  const { data: docsData } = useRunDocuments(runId ?? "");

  const docs = docsData?.documents ?? [];
  const totalDocs = docsData?.total ?? 0;

  async function download(kind: "markdown" | "json" | "csv" | "raw") {
    if (!runId) return;
    try {
      const { blob, filename } = await api.exports.download(runId, kind);
      const url = URL.createObjectURL(blob);
      triggerDownload(url, filename);
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Download failed");
    }
  }

  function triggerDownload(url: string, name: string) {
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
  }

  if (!runId) {
    const runs = runsData?.runs ?? [];
    const reportRuns = runs.filter((r) => r.status === "completed" || r.status === "failed");
    const shownRuns = reportRuns.length ? reportRuns : runs.slice(0, 8);

    return (
      <div className="flex flex-col h-full overflow-hidden">
        <PageTopbar
          title="Reports"
          subtitle={reportRuns.length ? `${reportRuns.length} finished run${reportRuns.length === 1 ? "" : "s"}` : "Run outputs and exports"}
          action={
            <Button
              size="sm"
              variant="primary" className="h-7 px-3.5 text-[13px] font-medium"
              onClick={() => navigate("/launch")}
            >
              <Play size={11} className="mr-1.5" /> New Run
            </Button>
          }
        />

        <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 space-y-3">
          {runsLoading ? (
            [1, 2, 3].map((i) => <div key={i} className="glass rounded-lg h-14 animate-pulse" />)
          ) : shownRuns.length === 0 ? (
            <GlassCard className="p-8 text-center">
              <p className="text-[13px] font-medium text-aria-text2">No reports yet</p>
              <p className="mt-1 text-[11px] text-aria-text4">Completed runs will appear here with export options.</p>
            </GlassCard>
          ) : (
            <div className="space-y-2">
              {shownRuns.map((run) => (
                <RunRow key={run.run_id} run={run} />
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        <PageTopbar title="Report" />
        <div className="flex-1 p-5 space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="glass rounded-lg h-24 animate-pulse" />)}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        <PageTopbar title="Report" />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-aria-text3 text-[13px] tracking-caption">Failed to load report. The run may not exist.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Report"
        subtitle={run?.topic ?? "Untitled run"}
        action={
          <Button
            size="sm"
            variant="subtle"
            className="text-[13px] h-7 px-3.5 font-medium"
            onClick={() => navigate("/launch")}
          >
            <Play size={11} className="mr-1" /> Re-run
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5">
        <div className="space-y-4 max-w-5xl">

          {/* Summary */}
          <GlassCard className="p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="text-[18px] font-semibold text-aria-text1 leading-tight">
                  {run?.topic ?? "Untitled run"}
                </h2>
                <p className="mt-1 flex items-center gap-1.5 text-[12px] text-aria-text4">
                  <span>
                    {run?.updated_at
                      ? `Completed ${formatDistanceToNow(new Date(run.updated_at), { addSuffix: true })}`
                      : "Completed"}
                  </span>
                  <span aria-hidden>·</span>
                  <span className="font-mono">{runId}</span>
                </p>
              </div>
              <Badge className="bg-aria-success/15 text-aria-success border-aria-success/25 text-[11px] flex-shrink-0 tabular-nums">
                {totalDocs.toLocaleString()} documents
              </Badge>
            </div>

            {/* Export buttons */}
            <div className="flex flex-wrap gap-2">
              {[
                { label: "Markdown", icon: FileText, kind: "markdown" as const },
                { label: "JSON", icon: FileJson, kind: "json" as const },
                { label: "CSV", icon: Table, kind: "csv" as const },
                { label: "Raw", icon: Download, kind: "raw" as const },
              ].map(({ label, icon: Icon, kind }) => (
                <Button
                  key={label}
                  size="sm"
                  variant="subtle"
                  className="text-[12px] h-8 px-3 font-medium"
                  onClick={() => download(kind)}
                >
                  <Icon size={11} className="mr-1.5" /> {label}
                </Button>
              ))}
            </div>
          </GlassCard>

          {/* Documents table */}
          {docs.length > 0 && (
            <div>
              <p className="text-[11px] font-medium text-aria-text3 mb-2">
                Documents ({totalDocs.toLocaleString()})
              </p>
              <GlassCard className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-[var(--aria-border)]">
                        {["Title", "Source", "Score"].map((h) => (
                          <th key={h} className="text-left p-3 text-[11px] font-medium text-aria-text3">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {docs.map((doc, i) => (
                        <tr key={doc.id ?? doc.url ?? i} className="border-b border-[var(--aria-border-subtle)] hover:bg-[var(--aria-surface)]/40">
                          <td className="p-3 text-aria-text2 max-w-xs truncate">
                            {doc.url ? (
                              <a href={doc.url} target="_blank" rel="noreferrer" className="hover:text-aria-accent">
                                {doc.title}
                              </a>
                            ) : doc.title}
                          </td>
                          <td className="p-3">
                            <span className="text-[10px] font-medium text-aria-accent bg-aria-accent/[0.08] border border-aria-accent/20 px-1.5 py-0.5 rounded">
                              {doc.source}
                            </span>
                          </td>
                          <td className="p-3 text-aria-text4 tabular-nums">
                            {doc.relevance_score != null ? `${(doc.relevance_score * 100).toFixed(0)}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
