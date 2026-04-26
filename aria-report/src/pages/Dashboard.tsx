import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Play, ArrowRight } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { NumberTicker } from "@/components/glass/NumberTicker";
import { RunRow } from "@/components/shared/RunRow";
import { Button } from "@/components/ui/button";
import { useRuns } from "@/hooks/useRuns";

const stagger = {
  animate: { transition: { staggerChildren: 0.05 } },
};
const item = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.2 } },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, isLoading } = useRuns();

  const runs = data?.runs ?? [];
  const totalDocs = runs.reduce((s, r) => s + (r.total_documents ?? 0), 0);
  const activeCount = runs.filter((r) => r.status === "running" || r.status === "pending").length;
  const sourcesCount = 20;

  const stats = [
    { label: "Total Runs", value: data?.total ?? 0 },
    { label: "Docs Collected", value: totalDocs },
    { label: "Active Now", value: activeCount },
    { label: "Sources", value: sourcesCount },
  ];

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
            <Play size={11} className="mr-1" /> New Run
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-5 space-y-4 pb-16 md:pb-5">
        {/* Stats strip */}
        <motion.div
          variants={stagger}
          initial="initial"
          animate="animate"
          className="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          {stats.map((s) => (
            <motion.div key={s.label} variants={item}>
              <GlassCard className="p-4">
                <NumberTicker
                  value={s.value}
                  className="block text-heading-2 text-aria-text1 tracking-tight tabular-nums"
                />
                <span className="block text-micro text-aria-text4 mt-1">
                  {s.label}
                </span>
              </GlassCard>
            </motion.div>
          ))}
        </motion.div>

        {/* Quick launch */}
        <motion.div variants={item} initial="initial" animate="animate">
          <GlassCard
            className="p-4 flex items-center gap-3 cursor-pointer hover:glass-elevated"
            onClick={() => navigate("/launch")}
          >
            <span className="text-aria-text3 text-lg">🔍</span>
            <span className="flex-1 text-caption text-aria-text3">
              Enter research topic or paste mission YAML…
            </span>
            <div className="hidden sm:flex gap-1.5">
              {["Web", "arXiv", "Social", "Media"].map((s) => (
                <span
                  key={s}
                  className="text-micro px-2 py-0.5 rounded-full border border-aria-accent/30 text-aria-accent bg-aria-accent/[0.08]"
                >
                  {s}
                </span>
              ))}
            </div>
            <Button
              size="sm"
              variant="primary"
              className="h-7 px-3 ml-2 brand-glow flex-shrink-0 text-micro"
            >
              <Play size={11} className="mr-1" /> Launch
            </Button>
          </GlassCard>
        </motion.div>

        {/* Recent runs */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-micro text-aria-text4">
              Recent Runs
            </span>
            <button
              onClick={() => navigate("/")}
              className="text-micro text-aria-accent hover:text-aria-accent-hover flex items-center gap-1"
            >
              View all <ArrowRight size={10} />
            </button>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="glass rounded-lg h-12 animate-pulse" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <GlassCard className="p-8 text-center">
              <p className="text-body text-aria-text3">No runs yet.</p>
              <Button
                size="sm"
                variant="primary"
                className="mt-3 text-micro"
                onClick={() => navigate("/launch")}
              >
                Start your first run
              </Button>
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
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
