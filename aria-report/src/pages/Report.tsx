import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Download, Play, FileArchive, FileCode2, FileText, FileJson, Table } from "lucide-react";
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
  const [evidenceIndex, setEvidenceIndex] = useState<number | null>(null);
  const [evidence, setEvidence] = useState<Awaited<ReturnType<typeof api.runs.evidence>> | null>(null);
  const [evidenceError, setEvidenceError] = useState("");
  const [intelligence, setIntelligence] = useState<Awaited<ReturnType<typeof api.runs.intelligence>> | null>(null);
  const [findingStatement, setFindingStatement] = useState("");
  const [findings, setFindings] = useState<Awaited<ReturnType<typeof api.runs.findings>>["findings"]>([]);
  const availableExports = new Set(run?.available_exports ?? []);

  async function reviewEvidence(index: number) {
    if (!runId) return;
    setEvidenceIndex(index);
    setEvidenceError("");
    try {
      setEvidence(await api.runs.evidence(runId, index));
    } catch (error) {
      setEvidence(null);
      setEvidenceError(error instanceof Error ? error.message : "Evidence could not be loaded");
    }
  }

  async function loadIntelligence() {
    if (!runId) return;
    try {
      setIntelligence(await api.runs.intelligence(runId));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Intelligence results could not be loaded");
    }
  }

  async function approveFinding() {
    if (!runId || !findingStatement.trim()) return;
    try {
      const result = await api.runs.approveFinding(runId, findingStatement, evidenceIndex === null ? [] : [evidenceIndex]);
      setFindings((current) => [...current, result.finding]);
      setFindingStatement("");
      toast.success("Finding approved and linked to this research run.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Finding could not be approved");
    }
  }

  async function download(kind: "markdown" | "html" | "zip" | "json" | "csv" | "raw" | "findings") {
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
                { label: "Markdown", icon: FileText, kind: "markdown" as const, exportKey: "markdown" },
                { label: "HTML", icon: FileCode2, kind: "html" as const, exportKey: "html" },
                { label: "Full package", icon: FileArchive, kind: "zip" as const, exportKey: "zip" },
                { label: "JSON", icon: FileJson, kind: "json" as const, exportKey: "clean_json" },
                { label: "CSV", icon: Table, kind: "csv" as const, exportKey: "clean_csv" },
                { label: "Raw", icon: Download, kind: "raw" as const, exportKey: "raw_json" },
                { label: "Findings", icon: FileText, kind: "findings" as const, exportKey: "approved_findings" },
              ].filter(({ exportKey }) => availableExports.has(exportKey)).map(({ label, icon: Icon, kind }) => (
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
              <Button size="sm" variant="subtle" className="text-[12px] h-8 px-3 font-medium" onClick={loadIntelligence}>Intelligence</Button>
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
                            <button type="button" onClick={() => reviewEvidence(i)} className="hover:text-aria-accent text-left truncate max-w-full">
                              {doc.title}
                            </button>
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

          {evidenceIndex !== null && (
            <GlassCard className="p-5 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-medium text-aria-text3">Evidence review</p>
                  <p className="text-[13px] font-semibold text-aria-text1">{evidence?.clean_document.title ?? "Loading source..."}</p>
                </div>
                <Button size="sm" variant="subtle" onClick={() => { setEvidenceIndex(null); setEvidence(null); }}>Close</Button>
              </div>
              {evidenceError ? <p className="text-[12px] text-red-400">{evidenceError}</p> : evidence && <>
                <div className="grid gap-3 sm:grid-cols-2 text-[12px]">
                  <div><p className="text-aria-text4">AI summary</p><p className="text-aria-text2">{evidence.clean_document.summary || "No summary was produced."}</p></div>
                  <div><p className="text-aria-text4">Score and rationale</p><p className="text-aria-text2">{evidence.clean_document.relevance_score != null ? `${Math.round(evidence.clean_document.relevance_score * 100)}% relevance` : "No relevance score."}</p><p className="text-aria-text4 mt-1">{evidence.scoring_rationale || "No scoring rationale was produced."}</p></div>
                </div>
                <div><p className="text-[11px] font-medium text-aria-text3 mb-1">Extracted claims</p><pre className="whitespace-pre-wrap text-[12px] text-aria-text2">{evidence.claims.length ? evidence.claims.map(String).join("\n") : "No claims were extracted."}</pre></div>
                <div><p className="text-[11px] font-medium text-aria-text3 mb-1">Captured source text</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-[var(--aria-surface)] p-3 text-[11px] text-aria-text2">{evidence.raw_text || "The collector did not retain readable text for this document."}</pre></div>
                <div className="text-[11px] text-aria-text4">Source: {evidence.source_metadata.source || "unknown"}{evidence.source_metadata.author ? ` | ${evidence.source_metadata.author}` : ""}{evidence.source_metadata.url && <> | <a className="text-aria-accent" href={evidence.source_metadata.url} target="_blank" rel="noreferrer">Open original</a></>}</div>
              </>}
            </GlassCard>
          )}

          <GlassCard className="p-5 space-y-3">
            <div><p className="text-[11px] font-medium text-aria-text3">Approved findings</p><p className="text-[12px] text-aria-text4">Record a conclusion only after reviewing the supporting evidence.</p></div>
            <textarea value={findingStatement} onChange={(event) => setFindingStatement(event.target.value)} placeholder="Write the decision-ready finding..." className="min-h-20 w-full rounded border border-[var(--aria-border)] bg-[var(--aria-surface)] p-3 text-[12px] text-aria-text1" />
            <Button size="sm" variant="primary" onClick={approveFinding} disabled={!findingStatement.trim()}>Approve finding{evidenceIndex !== null ? " with selected evidence" : ""}</Button>
            {findings.length > 0 && <div className="space-y-2">{findings.map((finding) => <div key={finding.id} className="rounded border border-[var(--aria-border)] p-3 text-[12px]"><p className="text-aria-text2">{finding.statement}</p><p className="mt-1 text-[10px] text-aria-text4">Approved by {finding.approved_by} | {finding.evidence_document_indexes.length} evidence link(s)</p></div>)}</div>}
          </GlassCard>

          {intelligence && <GlassCard className="p-5 space-y-3">
            <p className="text-[11px] font-medium text-aria-text3">Research intelligence</p>
            <p className="text-[12px] text-aria-text2">Entities: {Array.isArray(intelligence.knowledge_graph.entities) ? intelligence.knowledge_graph.entities.length : 0} | Contradictions: {intelligence.contradictions.length} | Extracted images: {intelligence.images.length}</p>
            <div><p className="text-[11px] text-aria-text4">Research gaps</p><pre className="max-h-48 overflow-auto whitespace-pre-wrap text-[11px] text-aria-text2">{intelligence.gap_analysis.gaps?.length ? intelligence.gap_analysis.gaps.map(String).join("\n") : "No gaps were generated."}</pre></div>
            <div><p className="text-[11px] text-aria-text4">Follow-up queries</p><pre className="max-h-48 overflow-auto whitespace-pre-wrap text-[11px] text-aria-text2">{intelligence.gap_analysis.follow_up_queries?.length ? intelligence.gap_analysis.follow_up_queries.join("\n") : "No follow-up queries were generated."}</pre></div>
          </GlassCard>}
        </div>
      </div>
    </div>
  );
}
