import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Play, ArrowRight, BarChart2, FileStack, Activity, Zap, Search, ChevronRight } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { NumberTicker } from "@/components/glass/NumberTicker";
import { RunRow } from "@/components/shared/RunRow";
import { Button } from "@/components/ui/button";
import { useRuns } from "@/hooks/useRuns";
import { SOURCES } from "@/lib/sources";

const stagger = { animate: { transition: { staggerChildren: 0.06 } } };
const item = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: "easeOut" } },
};

const STAT_COLORS = [
  { icon: BarChart2, accent: "#7170ff", label: "Total Runs" },
  { icon: FileStack, accent: "#10b981", label: "Docs Collected" },
  { icon: Activity,  accent: "#f59e0b", label: "Active Now" },
  { icon: Zap,       accent: "#06b6d4", label: "Sources" },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, isLoading } = useRuns();

  const runs = data?.runs ?? [];
  const totalDocs  = runs.reduce((s, r) => s + (r.total_documents ?? 0), 0);
  const activeCount = runs.filter((r) => r.status === "running" || r.status === "pending").length;

  const sourceCount = SOURCES.length;
  const statValues = [data?.total ?? 0, totalDocs, activeCount, sourceCount];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Dashboard"
        action={
          <Button
            size="sm"
            variant="primary"
            className="h-7 px-3 brand-glow text-micro"
            onClick={() => navigate("/launch")}
          >
            <Play size={11} className="mr-1.5" /> New Run
          </Button>
        }
      />

      {/* Atmospheric layer */}
      <div className="flex-1 overflow-y-auto relative pb-16 md:pb-5">
        <div className="absolute inset-0 aria-atmo-glow aria-grid pointer-events-none" />

        <div className="relative p-5 space-y-5">
          {/* Stat strip */}
          <motion.div
            variants={stagger}
            initial="initial"
            animate="animate"
            className="grid grid-cols-2 md:grid-cols-4 gap-3"
          >
            {STAT_COLORS.map((s, i) => {
              const Icon = s.icon;
              return (
                <motion.div key={s.label} variants={item}>
                  <GlassCard
                    className="p-4 stat-accent-bar overflow-hidden"
                    style={{ "--stat-accent": s.accent } as React.CSSProperties}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{ background: `${s.accent}18` }}
                      >
                        <Icon size={15} style={{ color: s.accent }} />
                      </div>
                    </div>
                    <NumberTicker
                      value={statValues[i]}
                      className="block text-[28px] font-[620] text-aria-text1 tracking-h1 tabular-nums leading-none"
                    />
                    <span className="block text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mt-1.5">
                      {s.label}
                    </span>
                  </GlassCard>
                </motion.div>
              );
            })}
          </motion.div>

          {/* Quick launch — command-palette style */}
          <motion.div variants={item} initial="initial" animate="animate">
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
                    className="text-[10px] font-[510] px-2 py-0.5 rounded-full border border-aria-accent/25 text-aria-accent/70 bg-aria-accent/[0.06]"
                  >
                    {s}
                  </span>
                ))}
              </div>
              <Button
                size="sm"
                className="bg-aria-brand hover:bg-aria-accent text-white text-[11px] h-7 px-3 brand-glow flex-shrink-0 transition-all duration-150"
                onClick={(e) => { e.stopPropagation(); navigate("/launch"); }}
              >
                <Play size={11} className="mr-1.5" /> Launch
              </Button>
            </GlassCard>
          </motion.div>

          {/* Recent runs */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest">
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
                <p className="text-aria-text2 text-[13px] font-[510] mb-1">No runs yet</p>
                <p className="text-aria-text4 text-[11px] mb-5 max-w-[240px] mx-auto leading-relaxed">
                  Start a research run to collect and synthesize data from {sourceCount} sources
                </p>
                <Button
                  size="sm"
                  className="bg-aria-brand hover:bg-aria-accent text-white text-[11px] h-7 px-4 brand-glow"
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
              <motion.div
                variants={stagger}
                initial="initial"
                animate="animate"
                className="space-y-2"
              >
                {runs.slice(0, 8).map((run) => (
                  <motion.div key={run.run_id} variants={item}>
                    <RunRow run={run} />
                  </motion.div>
                ))}
                {runs.length > 8 && (
                  <button
                    onClick={() => navigate("/")}
                    className="w-full text-center text-[11px] text-aria-text4 hover:text-aria-accent py-2 flex items-center justify-center gap-1 transition-colors"
                  >
                    {runs.length - 8} more runs <ChevronRight size={11} />
                  </button>
                )}
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
