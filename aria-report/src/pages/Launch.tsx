import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Play, ChevronDown, ChevronUp } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { SOURCES, SOURCE_CATEGORIES, sourcesByCategory } from "@/lib/sources";
import { toast } from "sonner";
import type { SourceCategory } from "@/lib/sources";

const DEPTH_LABELS: Record<number, { label: string; docs: string }> = {
  1: { label: "Quick", docs: "~50 docs" },
  2: { label: "Standard", docs: "~200 docs" },
  3: { label: "Deep", docs: "~500 docs" },
  4: { label: "Thorough", docs: "~1500 docs" },
  5: { label: "Exhaustive", docs: "~5000 docs" },
};

export default function Launch() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [missionYaml, setMissionYaml] = useState("");
  const [showYaml, setShowYaml] = useState(false);
  const [depth, setDepth] = useState(2);
  const [showConfig, setShowConfig] = useState(false);
  const [enabledSources, setEnabledSources] = useState<Record<string, boolean>>(
    Object.fromEntries(SOURCES.map((s) => [s.id, ["web", "arxiv", "hackernews"].includes(s.id)]))
  );

  const launch = useMutation({
    mutationFn: () => {
      const free_sources: Record<string, boolean> = {};
      const auth_sources: Record<string, boolean> = {};
      SOURCES.forEach((s) => {
        if (s.credentials.length === 0) free_sources[s.id] = enabledSources[s.id] ?? false;
        else auth_sources[s.id] = enabledSources[s.id] ?? false;
      });
      return api.runs.start({ topic, depth_level: depth as 1 | 2 | 3 | 4 | 5, free_sources, auth_sources });
    },
    onSuccess: (run) => {
      toast.success("Run started");
      navigate(`/monitor/${run.run_id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function toggleSource(id: string) {
    setEnabledSources((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  const activeCount = Object.values(enabledSources).filter(Boolean).length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar title="Launch Run" />
      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 max-w-3xl w-full mx-auto space-y-4">

        {/* Topic */}
        <GlassCard className="p-4 space-y-2">
          <Label className="text-[11px] font-[510] text-aria-text4 uppercase tracking-widest">
            Research Topic
          </Label>
          <Textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What do you want to research? Be specific."
            className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 resize-none focus-visible:ring-aria-accent min-h-[80px]"
          />
        </GlassCard>

        {/* Mission YAML toggle */}
        <GlassCard className="p-4">
          <button
            onClick={() => setShowYaml((v) => !v)}
            className="w-full flex items-center justify-between text-[13px] font-[510] text-aria-text2"
          >
            Mission YAML (optional override)
            {showYaml ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showYaml && (
            <Textarea
              value={missionYaml}
              onChange={(e) => setMissionYaml(e.target.value)}
              placeholder="Paste mission YAML here to override topic settings…"
              className="mt-3 bg-transparent border-white/[0.06] text-aria-text2 placeholder:text-aria-text4 resize-none font-mono text-xs min-h-[120px] focus-visible:ring-aria-accent"
            />
          )}
        </GlassCard>

        {/* Source selector */}
        <GlassCard className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-[11px] font-[510] text-aria-text4 uppercase tracking-widest">
              Sources
            </Label>
            <span className="text-[11px] text-aria-accent">{activeCount} selected</span>
          </div>
          {SOURCE_CATEGORIES.map((cat) => (
            <div key={cat.id}>
              <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mb-2">
                {cat.label}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {sourcesByCategory(cat.id as SourceCategory).map((s) => (
                  <button
                    key={s.id}
                    onClick={() => toggleSource(s.id)}
                    className={`flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-[12px] ${
                      enabledSources[s.id]
                        ? "border-aria-accent/40 bg-aria-accent/[0.08] text-aria-text2"
                        : "border-white/[0.06] bg-transparent text-aria-text4"
                    }`}
                  >
                    <span>{s.icon}</span>
                    <span className="font-[510] truncate">{s.name}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </GlassCard>

        {/* Depth config */}
        <GlassCard className="p-4 space-y-3">
          <button
            onClick={() => setShowConfig((v) => !v)}
            className="w-full flex items-center justify-between text-[13px] font-[510] text-aria-text2"
          >
            <span>
              Depth: {DEPTH_LABELS[depth].label}{" "}
              <span className="text-aria-text4 font-normal">{DEPTH_LABELS[depth].docs}</span>
            </span>
            {showConfig ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showConfig && (
            <div className="pt-2 space-y-2">
              <Slider
                min={1} max={5} step={1}
                value={[depth]}
                onValueChange={([v]) => setDepth(v)}
              />
              <div className="flex justify-between text-[10px] text-aria-text4">
                {Object.values(DEPTH_LABELS).map((d) => (
                  <span key={d.label}>{d.label}</span>
                ))}
              </div>
            </div>
          )}
        </GlassCard>

        {/* Launch button */}
        <Button
          className="w-full h-11 bg-aria-brand hover:bg-aria-accent text-white font-[510] brand-glow disabled:opacity-40"
          onClick={() => launch.mutate()}
          disabled={!topic.trim() || launch.isPending}
        >
          {launch.isPending ? (
            "Starting…"
          ) : (
            <>
              <Play size={14} className="mr-2" /> Launch Research Run
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
