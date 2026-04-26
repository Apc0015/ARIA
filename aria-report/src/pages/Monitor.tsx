import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { NumberTicker } from "@/components/glass/NumberTicker";
import { StatusDot } from "@/components/glass/StatusDot";
import { Progress } from "@/components/ui/progress";
import { useRun, useRunDocuments } from "@/hooks/useRun";
import { SOURCES } from "@/lib/sources";

export default function Monitor() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run } = useRun(runId!, true);
  const { data: docsData } = useRunDocuments(runId!, true);

  useEffect(() => {
    if (run?.status === "completed" || run?.status === "failed") {
      const t = setTimeout(() => navigate(`/report/${runId}`), 1500);
      return () => clearTimeout(t);
    }
  }, [run?.status, runId, navigate]);

  const docs = docsData?.documents ?? [];
  const totalDocs = docsData?.total ?? 0;
  const progress = run?.progress ?? 0;
  const isLive = run?.status === "running" || run?.status === "pending";

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Live Monitor"
        subtitle={run?.topic ?? runId}
      />

      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 space-y-4">
        {/* Overall progress */}
        <GlassCard className="p-4 space-y-3">
          <div className="flex items-center gap-3">
            <StatusDot status={run?.status ?? "pending"} />
            <span className="text-[13px] font-[510] text-aria-text2 flex-1">
              {run?.message ?? "Initializing…"}
            </span>
            <NumberTicker
              value={totalDocs}
              className="text-[20px] font-[590] text-aria-text1 tabular-nums tracking-h3"
              suffix=" docs"
            />
          </div>
          <Progress
            value={progress}
            className="h-1 bg-[var(--aria-surface)] [&>div]:bg-aria-accent [&>div]:transition-all [&>div]:duration-500"
          />
          <div className="flex justify-between text-[10px] text-aria-text4">
            <span>Stage: {run?.stage ?? "—"}</span>
            <span>{progress}% complete</span>
          </div>
        </GlassCard>

        {/* Per-source pipeline */}
        <div>
          <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mb-2">
            Source Pipeline
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {SOURCES.slice(0, 12).map((src, i) => {
              const sourceActive = isLive && i % 3 !== 2;
              return (
                <motion.div
                  key={src.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <GlassCard className={`p-3 flex items-center gap-2 ${sourceActive ? "border-aria-accent/20" : ""}`}>
                    <span className="text-base">{src.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[11px] font-[510] text-aria-text2 truncate">{src.name}</span>
                        {sourceActive && (
                          <span className="w-1.5 h-1.5 rounded-full bg-aria-accent animate-pulse-dot" />
                        )}
                      </div>
                      <div className="h-0.5 bg-[var(--aria-surface)] rounded-full overflow-hidden">
                        {sourceActive && (
                          <motion.div
                            className="h-full bg-aria-accent rounded-full"
                            initial={{ scaleX: 0 }}
                            animate={{ scaleX: 0.6 }}
                            transition={{ duration: 1.5, ease: "easeOut" }}
                            style={{ transformOrigin: "left" }}
                          />
                        )}
                      </div>
                    </div>
                    <span className="text-[11px] font-[590] text-aria-text1 tabular-nums w-8 text-right">
                      {sourceActive ? "…" : "—"}
                    </span>
                  </GlassCard>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Document stream */}
        {docs.length > 0 && (
          <div>
            <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mb-2">
              Latest Documents
            </p>
            <div className="space-y-1.5">
              {docs.slice(0, 10).map((doc, i) => (
                <motion.div
                  key={doc.id ?? doc.url ?? i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <GlassCard className="p-3 flex items-center gap-3">
                    <span className="text-[10px] font-[510] text-aria-accent uppercase px-1.5 py-0.5 rounded bg-aria-accent/[0.08] border border-aria-accent/20 flex-shrink-0">
                      {doc.source}
                    </span>
                    <span className="text-[12px] text-aria-text2 truncate flex-1">{doc.title}</span>
                    {doc.relevance_score != null && (
                      <span className="text-[10px] text-aria-text4 flex-shrink-0">
                        {(doc.relevance_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </GlassCard>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* Completion notice */}
        {(run?.status === "completed" || run?.status === "failed") && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard className="p-4 text-center border-aria-success/20">
              <p className={`text-[13px] font-[510] tracking-caption ${run.status === "completed" ? "text-aria-success" : "text-red-400"}`}>
                {run.status === "completed" ? "✓ Run complete — redirecting to report…" : "✗ Run failed"}
              </p>
              {run.error && <p className="text-aria-text4 text-[11px] mt-1">{run.error}</p>}
            </GlassCard>
          </motion.div>
        )}
      </div>
    </div>
  );
}
