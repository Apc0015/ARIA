import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SOURCES, SOURCE_CATEGORIES, sourcesByCategory } from "@/lib/sources";
import { useCredentials } from "@/hooks/useCredentials";
import { useEnabledSources } from "@/hooks/useEnabledSources";
import type { SourceCategory } from "@/lib/sources";

const stagger = { animate: { transition: { staggerChildren: 0.04 } } };
const item = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0, transition: { duration: 0.15 } } };

const CATEGORY_META: Record<string, { color: string; desc: string }> = {
  web:       { color: "#7170ff", desc: "General web, RSS, GitHub, government sites" },
  academic:  { color: "#10b981", desc: "Research papers, preprints, reference libraries" },
  social:    { color: "#f59e0b", desc: "Twitter/X, Slack channels" },
  media:     { color: "#06b6d4", desc: "YouTube, Vimeo, podcast transcripts" },
  data:      { color: "#8b5cf6", desc: "Statistical databases, economic data, government datasets" },
  osint:     { color: "#ef4444", desc: "Cybersecurity intelligence, infrastructure scanning" },
  knowledge: { color: "#f97316", desc: "Reference libraries, patents, personal knowledge bases" },
};

export default function Sources() {
  const navigate = useNavigate();
  const { data: creds } = useCredentials();
  const { isEnabled, toggle } = useEnabledSources();

  function isConfigured(sourceId: string): boolean {
    const src = SOURCES.find((s) => s.id === sourceId);
    if (!src || src.credentials.length === 0) return true;
    return src.credentials.every((f) => !f.required || Boolean(creds?.[f.key]));
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar title="Sources" />

      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 relative">
        <div className="absolute inset-0 aria-atmo-glow pointer-events-none opacity-60" />

        <div className="relative">
          <Tabs defaultValue="web">
            <TabsList className="bg-[var(--aria-surface)] border border-[var(--aria-border)] mb-5 p-1 gap-0.5 shadow-sm">
              {SOURCE_CATEGORIES.map((cat) => (
                <TabsTrigger
                  key={cat.id}
                  value={cat.id}
                  className="text-[12px] font-[510] text-aria-text3 rounded-md px-3 py-1.5 transition-all data-[state=active]:bg-aria-accent data-[state=active]:text-white data-[state=active]:shadow-sm"
                >
                  {cat.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {SOURCE_CATEGORIES.map((cat) => {
              const meta = CATEGORY_META[cat.id] ?? { color: "#6b7280", desc: cat.id };
              const sources = sourcesByCategory(cat.id as SourceCategory);
              const enabledCount = sources.filter((s) => isEnabled(s.id, isConfigured(s.id))).length;

              return (
                <TabsContent key={cat.id} value={cat.id}>
                  {/* Category header */}
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
                    <span className="text-[11px] text-aria-text4">{meta.desc}</span>
                    <span className="ml-auto text-[11px] font-[510]" style={{ color: meta.color }}>
                      {enabledCount}/{sources.length} active
                    </span>
                  </div>

                  <motion.div
                    variants={stagger}
                    initial="initial"
                    animate="animate"
                    className="grid grid-cols-1 sm:grid-cols-2 gap-3"
                  >
                    {sources.map((src) => {
                      const configured = isConfigured(src.id);
                      const enabled = isEnabled(src.id, configured);

                      return (
                        <motion.div key={src.id} variants={item}>
                          <GlassCard
                            className={[
                              "p-4 flex items-start gap-3 transition-all duration-200",
                              enabled ? "opacity-100" : "opacity-45",
                            ].join(" ")}
                            style={enabled ? { borderColor: `${meta.color}22` } : undefined}
                          >
                            {/* Icon with category tint */}
                            <div
                              className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 text-base"
                              style={{ background: `${meta.color}12` }}
                            >
                              {src.icon}
                            </div>

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <span className="text-[13px] font-[590] text-aria-text1">{src.name}</span>

                                {configured ? (
                                  <span className="text-[9px] font-[510] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">
                                    Configured ✓
                                  </span>
                                ) : (
                                  <button
                                    onClick={() => navigate("/settings")}
                                    className="text-[9px] font-[510] text-aria-accent bg-aria-accent/[0.08] border border-aria-accent/20 px-1.5 py-px rounded-full flex items-center gap-0.5 hover:bg-aria-accent/[0.15] transition-colors"
                                  >
                                    Configure <ExternalLink size={8} />
                                  </button>
                                )}
                              </div>
                              <p className="text-[11px] text-aria-text4 leading-relaxed">{src.description}</p>
                            </div>

                            <Switch
                              checked={enabled}
                              onCheckedChange={() => toggle(src.id, configured)}
                              className="flex-shrink-0 data-[state=checked]:bg-aria-accent mt-0.5"
                            />
                          </GlassCard>
                        </motion.div>
                      );
                    })}
                  </motion.div>
                </TabsContent>
              );
            })}
          </Tabs>
        </div>
      </div>
    </div>
  );
}
