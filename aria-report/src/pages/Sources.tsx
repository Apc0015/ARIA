import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SOURCES, SOURCE_CATEGORIES, sourcesByCategory } from "@/lib/sources";
import { useCredentials } from "@/hooks/useCredentials";
import type { SourceCategory } from "@/lib/sources";

const stagger = { animate: { transition: { staggerChildren: 0.04 } } };
const item = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0, transition: { duration: 0.15 } } };

export default function Sources() {
  const navigate = useNavigate();
  const { data: creds } = useCredentials();

  function isConfigured(sourceId: string): boolean {
    const src = SOURCES.find((s) => s.id === sourceId);
    if (!src || src.credentials.length === 0) return true;
    return src.credentials.every((f) => !f.required || Boolean(creds?.[f.key]));
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar title="Sources" />

      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5">
        <Tabs defaultValue="web">
          <TabsList className="bg-white/[0.04] border border-white/[0.06] mb-5">
            {SOURCE_CATEGORIES.map((cat) => (
              <TabsTrigger
                key={cat.id}
                value={cat.id}
                className="text-[12px] font-[510] data-[state=active]:bg-aria-accent/[0.15] data-[state=active]:text-aria-accent"
              >
                {cat.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {SOURCE_CATEGORIES.map((cat) => (
            <TabsContent key={cat.id} value={cat.id}>
              <motion.div
                variants={stagger}
                initial="initial"
                animate="animate"
                className="grid grid-cols-1 sm:grid-cols-2 gap-3"
              >
                {sourcesByCategory(cat.id as SourceCategory).map((src) => {
                  const configured = isConfigured(src.id);
                  return (
                    <motion.div key={src.id} variants={item}>
                      <GlassCard className="p-4 flex items-start gap-3">
                        <span className="text-xl flex-shrink-0 mt-0.5">{src.icon}</span>
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
                                className="text-[9px] font-[510] text-aria-accent bg-aria-accent/[0.08] border border-aria-accent/20 px-1.5 py-px rounded-full flex items-center gap-0.5 hover:bg-aria-accent/[0.15]"
                              >
                                Configure <ExternalLink size={8} />
                              </button>
                            )}
                          </div>
                          <p className="text-[11px] text-aria-text4 leading-relaxed">{src.description}</p>
                        </div>
                        <Switch
                          checked={configured}
                          disabled={!configured}
                          className="flex-shrink-0 data-[state=checked]:bg-aria-accent"
                        />
                      </GlassCard>
                    </motion.div>
                  );
                })}
              </motion.div>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  );
}
