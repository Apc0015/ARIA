import { useNavigate } from "react-router-dom";
import { Play, ArrowRight, BarChart2, FileStack, Activity, Zap, Search, ChevronRight } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { NumberTicker } from "@/components/glass/NumberTicker";
import { RunRow } from "@/components/shared/RunRow";
import { Button } from "@/components/ui/button";
import { useRuns } from "@/hooks/useRuns";
import { SOURCES } from "@/lib/sources";

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, isLoading } = useRuns();

  const runs = data?.runs ?? [];
  const totalRuns = data?.total ?? runs.length;
  const totalDocs = runs.reduce((s, r) => s + (r.total_documents ?? 0), 0);
  const completedCount = runs.filter((r) => r.status === "completed").length;
  const activeCount = runs.filter(
    (r) => r.status === "running" || r.status === "pending" || r.status === "queued"
  ).length;
  const sourceCount = SOURCES.length;
  const avgDocs = completedCount ? Math.round(totalDocs / completedCount) : 0;

  // Each tile carries context — a number alone doesn't tell a story.
  const STATS = [
    {
      icon: BarChart2,
      accent: "var(--aria-accent)",
      label: "Total runs",
      value: totalRuns,
      context: completedCount
        ? `${completedCount} completed`
        : "No completed runs yet",
    },
    {
      icon: FileStack,
      accent: "#30d158",
      label: "Documents",
      value: totalDocs,
      context: completedCount ? `~${avgDocs.toLocaleString()} per run` : "Across all runs",
    },
    {
      icon: Activity,
      accent: "#ff9f0a",
      label: "Active now",
      value: activeCount,
      context: activeCount ? "In progress" : "Nothing running",
    },
    {
      icon: Zap,
      accent: "#0a84ff",
      label: "Sources",
      value: sourceCount,
      context: "Ready to collect",
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Dashboard"
        action={
          <Button
            size="sm"
            variant="primary"
            className="h-7 px-3.5 text-[13px] font-medium"
            onClick={() => navigate("/launch")}
          >
            <Play size={11} className="mr-1.5" /> New Run
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto pb-16 md:pb-5">
        <div className="p-5 space-y-5 max-w-5xl">
          {/* Stat strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {STATS.map((s) => {
              const Icon = s.icon;
              return (
                <GlassCard key={s.label} className="p-4 flex flex-col">
                  <div className="flex items-center gap-2 mb-3">
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: `${s.accent}1f` }}
                    >
                      <Icon size={14} style={{ color: s.accent }} />
                    </div>
                    <span className="text-[12px] font-medium text-aria-text3 truncate">
                      {s.label}
                    </span>
                  </div>
                  <NumberTicker
                    value={s.value}
                    className="block text-[30px] font-semibold text-aria-text1 tabular-nums leading-none"
                  />
                  <span className="block text-[11px] text-aria-text4 mt-2">
                    {s.context}
                  </span>
                </GlassCard>
              );
            })}
          </div>

          {/* Quick launch — command-palette style */}
          <div>
            <GlassCard
              className="p-4 flex items-center gap-3 cursor-pointer group"
              elevated
              onClick={() => navigate("/launch")}
            >
              <div className="w-8 h-8 rounded-lg bg-aria-accent/10 flex items-center justify-center flex-shrink-0 group-hover:bg-aria-accent/20 transition-colors">
                <Search size={14} className="text-aria-accent" />
              </div>
              <span className="flex-1 text-[13px] text-aria-text3 group-hover:text-aria-text2 transition-colors">
                Enter research topic or paste mission YAML…
              </span>
              <div className="hidden sm:flex gap-1.5 mr-2">
                {["Web", "arXiv", "Social", "Media"].map((s) => (
                  <span
                    key={s}
                    className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-aria-accent/25 text-aria-accent/70 bg-aria-accent/[0.06]"
                  >
                    {s}
                  </span>
                ))}
              </div>
              <Button
                size="sm"
                variant="primary" className="h-7 px-3.5 text-[13px] font-medium flex-shrink-0"
                onClick={(e) => { e.stopPropagation(); navigate("/launch"); }}
              >
                <Play size={11} className="mr-1.5" /> Launch
              </Button>
            </GlassCard>
          </div>

          {/* Recent runs */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-medium text-aria-text3">
                Recent Runs
              </span>
              <button
                onClick={() => navigate("/")}
                className="text-[11px] text-aria-accent hover:text-aria-accent-hover flex items-center gap-0.5 transition-colors"
              >
                View all <ArrowRight size={11} />
              </button>
            </div>

            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="glass rounded-[10px] h-14 animate-pulse" />
                ))}
              </div>
            ) : runs.length === 0 ? (
              <GlassCard className="p-10 text-center">
                {/* Empty state illustration */}
                <div className="w-12 h-12 rounded-2xl bg-aria-accent/10 flex items-center justify-center mx-auto mb-4">
                  <BarChart2 size={22} className="text-aria-accent/60" />
                </div>
                <p className="text-aria-text2 text-[13px] font-medium mb-1">No runs yet</p>
                <p className="text-aria-text4 text-[11px] mb-5 max-w-[240px] mx-auto leading-relaxed">
                  Start a research run to collect and synthesize data from {sourceCount} sources
                </p>
                <Button
                  size="sm"
                  variant="primary" className="h-7 px-4 text-[13px] font-medium"
                  onClick={() => navigate("/launch")}
                >
                  <Play size={11} className="mr-1.5" /> Start first run
                </Button>

                {/* Source type pills */}
                <div className="flex flex-wrap justify-center gap-2 mt-6 opacity-50">
                  {["🌐 Web", "🎓 Academic", "𝕏 Social", "▶️ Media", "📝 Notion"].map((s) => (
                    <span key={s} className="text-[10px] text-aria-text4 bg-[var(--aria-surface)] border border-[var(--aria-border)] px-2.5 py-1 rounded-full">
                      {s}
                    </span>
                  ))}
                </div>
              </GlassCard>
            ) : (
              <div className="space-y-2">
                {runs.slice(0, 8).map((run) => (
                  <RunRow key={run.run_id} run={run} />
                ))}
                {runs.length > 8 && (
                  <button
                    onClick={() => navigate("/")}
                    className="w-full text-center text-[11px] text-aria-text4 hover:text-aria-accent py-2 flex items-center justify-center gap-1 transition-colors"
                  >
                    {runs.length - 8} more runs <ChevronRight size={11} />
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
