import { useState } from "react";
import { motion } from "framer-motion";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useCredentials, useSaveCredentials } from "@/hooks/useCredentials";
import { SOURCES, SOURCE_CATEGORIES, sourcesByCategory } from "@/lib/sources";
import { LLM_CLOUD_PROVIDERS, ENSEMBLE_STRATEGIES } from "@/lib/llm-providers";
import type { SourceCategory } from "@/lib/sources";
import type { EnsembleStrategy } from "@/lib/llm-providers";

const SECTIONS = [
  { id: "connections", label: "Connections" },
  { id: "llm-cloud", label: "LLM — Cloud" },
  { id: "llm-local", label: "LLM — Local" },
  { id: "llm-ensemble", label: "LLM Ensemble" },
  { id: "mission", label: "Default Mission" },
  { id: "output", label: "Output" },
  { id: "appearance", label: "Appearance" },
] as const;

type SectionId = typeof SECTIONS[number]["id"];

export default function Settings() {
  const [activeSection, setActiveSection] = useState<SectionId>("connections");
  const { data: creds } = useCredentials();
  const saveCredentials = useSaveCredentials();

  const [localCreds, setLocalCreds] = useState<Record<string, string>>({});
  const [localLLMEnabled, setLocalLLMEnabled] = useState(false);
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [ollamaModel, setOllamaModel] = useState("llama3");
  const [ensembleEnabled, setEnsembleEnabled] = useState(false);
  const [ensembleModels, setEnsembleModels] = useState<string[]>([]);
  const [ensembleStrategy, setEnsembleStrategy] = useState<EnsembleStrategy>("voting");
  const [outputFormats, setOutputFormats] = useState({ pdf: false, json: true, csv: true, markdown: true });
  const [defaultMission, setDefaultMission] = useState("");

  function getCredValue(key: string): string {
    return localCreds[key] ?? (creds?.[key] as string) ?? "";
  }

  function setCredValue(key: string, val: string) {
    setLocalCreds((prev) => ({ ...prev, [key]: val }));
  }

  function saveSection() {
    const merged: Record<string, string> = { ...localCreds };
    if (localLLMEnabled) {
      merged["OLLAMA_BASE_URL"] = ollamaUrl;
      merged["OLLAMA_MODEL"] = ollamaModel;
    }
    if (ensembleEnabled) {
      merged["LLM_ENSEMBLE_ENABLED"] = "true";
      merged["LLM_ENSEMBLE_MODELS"] = ensembleModels.join(",");
      merged["LLM_ENSEMBLE_STRATEGY"] = ensembleStrategy;
    }
    saveCredentials.mutate(merged, {
      onSuccess: () => toast.success("Settings saved"),
      onError: (e: Error) => toast.error(e.message),
    });
  }

  function testOllama() {
    fetch(`${ollamaUrl}/api/tags`)
      .then((r) => r.json())
      .then((d) => toast.success(`Connected — ${d.models?.length ?? 0} models found`))
      .catch(() => toast.error("Cannot reach Ollama — is it running?"));
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Settings"
        action={
          <Button
            size="sm"
            className="bg-aria-brand hover:bg-aria-accent text-white text-[11px] h-7 px-3 brand-glow"
            onClick={saveSection}
            disabled={saveCredentials.isPending}
          >
            {saveCredentials.isPending ? "Saving…" : "Save"}
          </Button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        <nav className="w-40 flex-shrink-0 border-r border-white/[0.05] p-3 space-y-0.5 overflow-y-auto hidden sm:block">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className={`w-full text-left text-[12px] font-[510] px-3 py-2 rounded-lg transition-all ${
                activeSection === s.id
                  ? "bg-aria-accent/[0.12] text-aria-accent"
                  : "text-aria-text3 hover:text-aria-text2 hover:bg-white/[0.03]"
              }`}
            >
              {s.label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 space-y-4">

          {activeSection === "connections" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
              <p className="text-[11px] text-aria-text4 mb-4">Configure API keys and tokens for each source connector.</p>
              {SOURCE_CATEGORIES.map((cat) => (
                <div key={cat.id}>
                  <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mb-2">{cat.label}</p>
                  <div className="space-y-2">
                    {sourcesByCategory(cat.id as SourceCategory).map((src) => (
                      <Collapsible key={src.id}>
                        <GlassCard perspective={false} className="overflow-hidden">
                          <CollapsibleTrigger className="w-full flex items-center gap-3 p-3 hover:bg-white/[0.02]">
                            <span>{src.icon}</span>
                            <span className="text-[13px] font-[510] text-aria-text2 flex-1 text-left">{src.name}</span>
                            {src.credentials.length === 0 ? (
                              <span className="text-[9px] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">No auth</span>
                            ) : src.credentials.every((f) => !f.required || Boolean(getCredValue(f.key))) ? (
                              <span className="text-[9px] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">Configured ✓</span>
                            ) : (
                              <span className="text-[9px] text-aria-accent bg-aria-accent/[0.08] border border-aria-accent/20 px-1.5 py-px rounded-full">Needs setup</span>
                            )}
                            {src.credentials.length > 0 && <ChevronDown size={12} className="text-aria-text4" />}
                          </CollapsibleTrigger>
                          {src.credentials.length > 0 && (
                            <CollapsibleContent>
                              <div className="px-3 pb-3 space-y-2 border-t border-white/[0.05] pt-3">
                                {src.credentials.map((field) => (
                                  <div key={field.key} className="space-y-1">
                                    <Label className="text-[11px] text-aria-text4">
                                      {field.label}{field.required && <span className="text-red-400 ml-0.5">*</span>}
                                    </Label>
                                    <Input
                                      type={field.type === "password" ? "password" : "text"}
                                      value={getCredValue(field.key)}
                                      onChange={(e) => setCredValue(field.key, e.target.value)}
                                      placeholder={field.placeholder}
                                      className="h-8 bg-transparent border-white/[0.08] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent"
                                    />
                                  </div>
                                ))}
                              </div>
                            </CollapsibleContent>
                          )}
                        </GlassCard>
                      </Collapsible>
                    ))}
                  </div>
                </div>
              ))}
            </motion.div>
          )}

          {activeSection === "llm-cloud" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
              <p className="text-[11px] text-aria-text4 mb-4">Configure cloud LLM providers for document cleaning and synthesis.</p>
              {LLM_CLOUD_PROVIDERS.map((provider) => (
                <Collapsible key={provider.id}>
                  <GlassCard perspective={false} className="overflow-hidden">
                    <CollapsibleTrigger className="w-full flex items-center gap-3 p-4 hover:bg-white/[0.02]">
                      <span className="text-xl">{provider.icon}</span>
                      <span className="text-[13px] font-[590] text-aria-text1 flex-1 text-left">{provider.name}</span>
                      {provider.fields.some((f) => f.required && Boolean(getCredValue(f.key))) ? (
                        <span className="text-[9px] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">Configured ✓</span>
                      ) : (
                        <span className="text-[9px] text-aria-text4 bg-white/[0.04] border border-white/[0.06] px-1.5 py-px rounded-full">Not set</span>
                      )}
                      <ChevronRight size={12} className="text-aria-text4" />
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-4 pb-4 space-y-3 border-t border-white/[0.05] pt-3">
                        {provider.fields.map((field) => (
                          <div key={field.key} className="space-y-1">
                            <Label className="text-[11px] text-aria-text4">
                              {field.label}{field.required && <span className="text-red-400 ml-0.5">*</span>}
                            </Label>
                            <Input
                              type={field.type === "password" ? "password" : "text"}
                              value={getCredValue(field.key)}
                              onChange={(e) => setCredValue(field.key, e.target.value)}
                              placeholder={field.placeholder}
                              className="h-8 bg-transparent border-white/[0.08] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent"
                            />
                          </div>
                        ))}
                        <div>
                          <p className="text-[10px] text-aria-text4 mb-1">Available models</p>
                          <div className="flex flex-wrap gap-1.5">
                            {provider.defaultModels.map((m) => (
                              <span key={m} className="text-[10px] font-[510] text-aria-text3 bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 rounded-full">
                                {m}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </GlassCard>
                </Collapsible>
              ))}
            </motion.div>
          )}

          {activeSection === "llm-local" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
              <GlassCard className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[13px] font-[590] text-aria-text1">Local LLM (Ollama)</p>
                    <p className="text-[11px] text-aria-text4 mt-0.5">Use a locally running model instead of cloud providers</p>
                  </div>
                  <Switch checked={localLLMEnabled} onCheckedChange={setLocalLLMEnabled} className="data-[state=checked]:bg-aria-accent" />
                </div>
                {localLLMEnabled && (
                  <div className="space-y-3 pt-2 border-t border-white/[0.06]">
                    <div className="space-y-1">
                      <Label className="text-[11px] text-aria-text4">Ollama Base URL</Label>
                      <Input value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} placeholder="http://localhost:11434" className="h-8 bg-transparent border-white/[0.08] text-aria-text2 text-[12px] focus-visible:ring-aria-accent" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[11px] text-aria-text4">Model Name</Label>
                      <Input value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} placeholder="llama3, mistral, phi3…" className="h-8 bg-transparent border-white/[0.08] text-aria-text2 text-[12px] focus-visible:ring-aria-accent" />
                    </div>
                    <Button size="sm" variant="outline" className="text-[11px] h-7 border-white/[0.08] bg-transparent text-aria-text2 hover:bg-white/[0.04]" onClick={testOllama}>
                      Test Connection
                    </Button>
                  </div>
                )}
              </GlassCard>
            </motion.div>
          )}

          {activeSection === "llm-ensemble" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
              <GlassCard className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[13px] font-[590] text-aria-text1">LLM Ensemble</p>
                    <p className="text-[11px] text-aria-text4 mt-0.5">Run multiple LLMs in parallel for richer synthesis</p>
                  </div>
                  <Switch checked={ensembleEnabled} onCheckedChange={setEnsembleEnabled} className="data-[state=checked]:bg-aria-accent" />
                </div>
                {ensembleEnabled && (
                  <div className="space-y-4 pt-2 border-t border-white/[0.06]">
                    <div>
                      <Label className="text-[11px] text-aria-text4 mb-2 block">Participating Models</Label>
                      <div className="space-y-1.5">
                        {LLM_CLOUD_PROVIDERS.flatMap((p) =>
                          p.defaultModels.slice(0, 1).map((m) => ({ provider: p.name, model: m, key: `${p.id}/${m}` }))
                        ).map(({ provider, model, key }) => (
                          <label key={key} className="flex items-center gap-2 cursor-pointer">
                            <Checkbox
                              checked={ensembleModels.includes(key)}
                              onCheckedChange={(checked) =>
                                setEnsembleModels((prev) => checked ? [...prev, key] : prev.filter((m) => m !== key))
                              }
                              className="border-white/[0.15] data-[state=checked]:bg-aria-accent data-[state=checked]:border-aria-accent"
                            />
                            <span className="text-[12px] text-aria-text2">{provider} — {model}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px] text-aria-text4 mb-2 block">Strategy</Label>
                      <RadioGroup value={ensembleStrategy} onValueChange={(v) => setEnsembleStrategy(v as EnsembleStrategy)} className="space-y-2">
                        {ENSEMBLE_STRATEGIES.map((s) => (
                          <div key={s.value} className="flex items-center gap-2">
                            <RadioGroupItem value={s.value} id={s.value} className="border-white/[0.2] text-aria-accent" />
                            <Label htmlFor={s.value} className="text-[12px] text-aria-text2 cursor-pointer">{s.label}</Label>
                          </div>
                        ))}
                      </RadioGroup>
                    </div>
                  </div>
                )}
              </GlassCard>
            </motion.div>
          )}

          {activeSection === "mission" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <GlassCard className="p-4 space-y-3">
                <p className="text-[13px] font-[590] text-aria-text1">Default Mission YAML</p>
                <p className="text-[11px] text-aria-text4">Used when launching a run without specifying a custom mission.</p>
                <Textarea value={defaultMission} onChange={(e) => setDefaultMission(e.target.value)} placeholder="Paste default mission YAML here…" className="min-h-[240px] bg-transparent border-white/[0.08] text-aria-text2 placeholder:text-aria-text4 font-mono text-xs focus-visible:ring-aria-accent resize-none" />
              </GlassCard>
            </motion.div>
          )}

          {activeSection === "output" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <GlassCard className="p-4 space-y-4">
                <p className="text-[13px] font-[590] text-aria-text1">Default Export Formats</p>
                <div className="space-y-2">
                  {(["json", "csv", "markdown", "pdf"] as const).map((fmt) => (
                    <label key={fmt} className="flex items-center gap-2 cursor-pointer">
                      <Checkbox
                        checked={outputFormats[fmt]}
                        onCheckedChange={(checked) => setOutputFormats((prev) => ({ ...prev, [fmt]: Boolean(checked) }))}
                        className="border-white/[0.15] data-[state=checked]:bg-aria-accent data-[state=checked]:border-aria-accent"
                      />
                      <span className="text-[12px] text-aria-text2 uppercase">{fmt}</span>
                    </label>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {activeSection === "appearance" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <GlassCard className="p-4">
                <p className="text-[13px] font-[590] text-aria-text1 mb-1">Appearance</p>
                <p className="text-[12px] text-aria-text4">ARIA uses dark mode exclusively. Light mode support is not yet available.</p>
              </GlassCard>
            </motion.div>
          )}

        </div>
      </div>
    </div>
  );
}
