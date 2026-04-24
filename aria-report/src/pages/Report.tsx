import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Download, Play, FileText, FileJson, Table } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRun, useRunDocuments } from "@/hooks/useRun";
import { api } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";

const stagger = { animate: { transition: { staggerChildren: 0.04 } } };
const item = { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0, transition: { duration: 0.18 } } };

export default function Report() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading, isError } = useRun(runId ?? "");
  const { data: docsData } = useRunDocuments(runId ?? "");

  const docs = docsData?.documents ?? [];
  const totalDocs = docsData?.total ?? 0;

  function download(url: string, name: string) {
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
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
          <p className="text-aria-text3 text-sm">Failed to load report. The run may not exist.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Report"
        subtitle={run?.topic ?? runId}
        action={
          <Button
            size="sm"
            variant="outline"
            className="text-[11px] h-7 border-white/[0.08] bg-transparent text-aria-text2 hover:bg-white/[0.04]"
            onClick={() => navigate("/launch")}
          >
            <Play size={11} className="mr-1" /> Re-run
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 space-y-4">
        <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-4">

          {/* Summary */}
          <motion.div variants={item}>
            <GlassCard className="p-5 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-[590] text-aria-text1 tracking-tight">
                    {run?.topic ?? "Research Run"}
                  </h2>
                  <p className="text-[12px] text-aria-text4 mt-1">
                    {run?.updated_at
                      ? `Completed ${formatDistanceToNow(new Date(run.updated_at), { addSuffix: true })}`
                      : "—"}
                  </p>
                </div>
                <Badge className="bg-aria-success/20 text-aria-success border-aria-success/30 text-[11px] flex-shrink-0">
                  {totalDocs.toLocaleString()} docs
                </Badge>
              </div>

              {/* Export buttons */}
              <div className="flex flex-wrap gap-2">
                {[
                  { label: "Markdown", icon: FileText, url: api.exports.markdown(runId ?? "") },
                  { label: "JSON", icon: FileJson, url: api.exports.json(runId ?? "") },
                  { label: "CSV", icon: Table, url: api.exports.csv(runId ?? "") },
                  { label: "Raw", icon: Download, url: api.exports.raw(runId ?? "") },
                ].map(({ label, icon: Icon, url }) => (
                  <Button
                    key={label}
                    size="sm"
                    variant="outline"
                    className="text-[11px] h-8 border-white/[0.08] bg-transparent text-aria-text2 hover:bg-white/[0.04]"
                    onClick={() => download(url, `aria-${runId}-${label.toLowerCase()}`)}
                  >
                    <Icon size={11} className="mr-1.5" /> {label}
                  </Button>
                ))}
              </div>
            </GlassCard>
          </motion.div>

          {/* Documents table */}
          {docs.length > 0 && (
            <motion.div variants={item}>
              <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mb-2">
                Documents ({totalDocs.toLocaleString()})
              </p>
              <GlassCard perspective={false} className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-white/[0.06]">
                        {["Title", "Source", "Score"].map((h) => (
                          <th key={h} className="text-left p-3 text-[10px] font-[510] text-aria-text4 uppercase tracking-wide">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {docs.map((doc, i) => (
                        <tr key={doc.id ?? doc.url ?? i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                          <td className="p-3 text-aria-text2 max-w-xs truncate">
                            {doc.url ? (
                              <a href={doc.url} target="_blank" rel="noreferrer" className="hover:text-aria-accent">
                                {doc.title}
                              </a>
                            ) : doc.title}
                          </td>
                          <td className="p-3">
                            <span className="text-[10px] font-[510] text-aria-accent bg-aria-accent/[0.08] border border-aria-accent/20 px-1.5 py-0.5 rounded">
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
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
