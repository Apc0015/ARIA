import { useState, useEffect } from "react";
import { useTheme } from "@/hooks/useTheme";
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
import { ChevronDown, CheckCircle2, XCircle, Loader2, Zap } from "lucide-react";
import { toast } from "sonner";
import { useCredentials, useSaveCredentials } from "@/hooks/useCredentials";
import { SOURCE_CATEGORIES, sourcesByCategory } from "@/lib/sources";
import { LLM_CLOUD_PROVIDERS, ENSEMBLE_STRATEGIES } from "@/lib/llm-providers";
import { api, getApiKey, setApiKey } from "@/lib/api";
import type { SourceCategory } from "@/lib/sources";
import type { EnsembleStrategy } from "@/lib/llm-providers";

const SECTIONS = [
  { id: "connections", label: "Connections" },
  { id: "llm-cloud",   label: "LLM — Cloud" },
  { id: "llm-local",   label: "LLM — Local" },
  { id: "llm-ensemble",label: "LLM Ensemble" },
  { id: "mission",     label: "Default Mission" },
  { id: "output",      label: "Output" },
  { id: "appearance",  label: "Appearance" },
] as const;

type SectionId = typeof SECTIONS[number]["id"];
type VerifyStatus = "idle" | "loading" | "ok" | "fail";

interface LLMStatus {
  provider: string;
  model: string;
  base_url: string;
  configured: boolean;
  connected?: boolean | null;
  message?: string;
}

function ActiveLLMBadge({ llmStatus }: { llmStatus: LLMStatus | null }) {
  if (!llmStatus) return null;
  const ready = llmStatus.configured && llmStatus.connected !== false;
  const icon  = ready ? "✓" : "○";
  const color = ready ? "text-aria-success border-aria-success/30 bg-aria-success/10"
                      : "text-aria-text4 border-[var(--aria-border)]";
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-[11px] font-medium mb-4 ${color}`}>
      <Zap size={12} />
      <span>Active LLM:</span>
      <span className="font-semibold capitalize">{llmStatus.provider}</span>
      <span className="text-aria-text4">/</span>
      <span className="font-medium">{llmStatus.model}</span>
      {llmStatus.message && (
        <span className="hidden md:inline text-aria-text4 truncate">{llmStatus.message}</span>
      )}
      <span className="ml-auto">{icon}</span>
    </div>
  );
}

export default function Settings() {
  const [activeSection, setActiveSection] = useState<SectionId>("connections");
  const { data: creds } = useCredentials();
  const { theme, toggle: toggleTheme } = useTheme();
  const saveCredentials = useSaveCredentials();

  const [apiKeyInput, setApiKeyInput] = useState(getApiKey());
  const [localCreds, setLocalCreds]         = useState<Record<string, string>>({});
  const [localLLMEnabled, setLocalLLMEnabled] = useState(false);
  const [ollamaUrl, setOllamaUrl]           = useState("http://localhost:11434");
  const [ollamaModel, setOllamaModel]       = useState("llama3.1:8b");
  const [ollamaModels, setOllamaModels]     = useState<string[]>([]);
  const [ensembleEnabled, setEnsembleEnabled] = useState(false);
  const [ensembleModels, setEnsembleModels] = useState<string[]>([]);
  const [ensembleStrategy, setEnsembleStrategy] = useState<EnsembleStrategy>("voting");
  const [outputFormats, setOutputFormats]   = useState({ pdf: false, json: true, csv: true, markdown: true });
  const [defaultMission, setDefaultMission] = useState("");

  // Verify state per source
  const [verifyStatus, setVerifyStatus] = useState<Record<string, VerifyStatus>>({});
  const [verifyMsg,    setVerifyMsg]    = useState<Record<string, string>>({});

  // Active LLM status from backend
  const [llmStatus, setLLMStatus] = useState<LLMStatus | null>(null);

  // Fetch LLM status on mount and when switching to LLM sections
  useEffect(() => {
    api.llm.status()
      .then(setLLMStatus)
      .catch(() => {});
  }, [activeSection]);

  // Fetch Ollama models when URL changes
  useEffect(() => {
    if (!localLLMEnabled) return;
    api.llm.models("ollama", ollamaUrl)
      .then((r) => setOllamaModels(r.models))
      .catch(() => setOllamaModels([]));
  }, [ollamaUrl, localLLMEnabled]);

  function getCredValue(key: string): string {
    const flat = creds?.[key];
    return localCreds[key] ?? (typeof flat === "string" ? flat : undefined) ?? creds?.platforms?.[key] ?? "";
  }

  function setCredValue(key: string, val: string) {
    setLocalCreds((prev) => ({ ...prev, [key]: val }));
  }

  function saveSection() {
    const merged: Record<string, string> = { ...localCreds };
    if (localLLMEnabled) {
      merged["OLLAMA_BASE_URL"] = ollamaUrl;
      merged["OLLAMA_MODEL"]    = ollamaModel;
      merged["LLM_PROVIDER"]    = "ollama";
    }
    if (ensembleEnabled) {
      merged["LLM_ENSEMBLE_ENABLED"]  = "true";
      merged["LLM_ENSEMBLE_MODELS"]   = ensembleModels.join(",");
      merged["LLM_ENSEMBLE_STRATEGY"] = ensembleStrategy;
    }
    saveCredentials.mutate(merged, {
      onSuccess: () => {
        toast.success("Settings saved");
        api.llm.status().then(setLLMStatus).catch(() => {});
      },
      onError: (e: Error) => toast.error(e.message),
    });
  }

  function saveApiKey() {
    setApiKey(apiKeyInput.trim());
    toast.success(apiKeyInput.trim() ? "API key saved locally" : "API key cleared");
  }

  async function verifySource(srcId: string, credFields: { key: string }[]) {
    setVerifyStatus((s) => ({ ...s, [srcId]: "loading" }));
    const credMap: Record<string, string> = {};
    credFields.forEach((f) => { credMap[f.key] = getCredValue(f.key); });
    try {
      const r = await api.credentials.verify(srcId, credMap);
      setVerifyStatus((s) => ({ ...s, [srcId]: r.ok ? "ok" : "fail" }));
      setVerifyMsg((m) => ({ ...m, [srcId]: r.message }));
      if (r.ok) toast.success(`${srcId}: ${r.message}`);
      else       toast.error(`${srcId}: ${r.message}`);
    } catch {
      setVerifyStatus((s) => ({ ...s, [srcId]: "fail" }));
      setVerifyMsg((m) => ({ ...m, [srcId]: "Connection error" }));
    }
  }

  async function verifyCloudLLM(providerId: string, keyField: string) {
    setVerifyStatus((s) => ({ ...s, [providerId]: "loading" }));
    const key = getCredValue(keyField);
    if (!key) {
      toast.error("Enter an API key first");
      setVerifyStatus((s) => ({ ...s, [providerId]: "fail" }));
      return;
    }
    // Test by calling the LLM models endpoint (cloud providers just return static list)
    // A real test would call the provider's API; for now we just validate key format
    const looks_valid = key.length > 10;
    setVerifyStatus((s) => ({ ...s, [providerId]: looks_valid ? "ok" : "fail" }));
    setVerifyMsg((m) => ({ ...m, [providerId]: looks_valid ? "API key format OK — will validate on first run" : "Key too short" }));
    if (looks_valid) toast.success(`${providerId}: key saved`);
    else             toast.error(`${providerId}: key looks invalid`);
  }

  function setActiveProvider(providerId: string, modelKey: string, modelValue: string) {
    setCredValue("LLM_PROVIDER", providerId);
    setCredValue(modelKey, modelValue || getCredValue(modelKey));
    toast.info(`Active LLM set to ${providerId} — click Save to apply`);
  }

  function testOllama() {
    fetch(`${ollamaUrl}/api/tags`)
      .then((r) => r.json())
      .then((d) => {
        const modelList: string[] = (d.models || []).map((m: { name: string }) => m.name);
        setOllamaModels(modelList);
        toast.success(`Ollama connected — ${modelList.length} models available`);
        setVerifyStatus((s) => ({ ...s, ollama: "ok" }));
      })
      .catch(() => {
        toast.error("Cannot reach Ollama — is it running?");
        setVerifyStatus((s) => ({ ...s, ollama: "fail" }));
      });
  }

  function VerifyIcon({ status }: { status: VerifyStatus }) {
    if (status === "loading") return <Loader2 size={13} className="animate-spin text-aria-text4" />;
    if (status === "ok")      return <CheckCircle2 size={13} className="text-aria-success" />;
    if (status === "fail")    return <XCircle size={13} className="text-red-400" />;
    return null;
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar
        title="Settings"
        action={
          <Button
            size="sm"
            variant="primary" className="h-7 px-3.5 text-[13px] font-medium"
            onClick={saveSection}
            disabled={saveCredentials.isPending}
          >
            {saveCredentials.isPending ? "Saving…" : "Save"}
          </Button>
        }
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile section select */}
        <div className="sm:hidden flex-shrink-0 border-b border-[var(--aria-border-subtle)] px-4 py-2">
          <select
            value={activeSection}
            onChange={(e) => setActiveSection(e.target.value as SectionId)}
            className="w-full bg-[var(--aria-surface)] border border-[var(--aria-border)] rounded-[6px] text-[12px] text-aria-text2 px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-aria-accent"
          >
            {SECTIONS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>

        <div className="flex flex-1 overflow-hidden">
          <nav className="w-40 flex-shrink-0 border-r border-[var(--aria-border-subtle)] p-3 space-y-0.5 overflow-y-auto hidden sm:block">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                className={`w-full text-left text-[12px] font-medium px-3 py-2 rounded-lg transition-all ${
                  activeSection === s.id
                    ? "bg-aria-accent/[0.12] text-aria-accent"
                    : "text-aria-text3 hover:text-aria-text2 hover:bg-[var(--aria-surface)]"
                }`}
              >
                {s.label}
              </button>
            ))}
          </nav>

          <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 space-y-4">

            {/* ── Connections ─────────────────────────────────────────────── */}
            {activeSection === "connections" && (
              <motion.div className="space-y-3">
                <GlassCard className="p-3 space-y-2">
                  <Label className="text-[11px] text-aria-text4">ARIA API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      type="password"
                      value={apiKeyInput}
                      onChange={(e) => setApiKeyInput(e.target.value)}
                      placeholder="Paste ARIA_API_KEY"
                      className="h-8 bg-transparent border-[var(--aria-border)] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent rounded-[6px]"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 border-[var(--aria-border)] bg-transparent text-aria-text2 hover:bg-[rgba(255,255,255,0.03)] rounded-[6px]"
                      onClick={saveApiKey}
                    >
                      Save key
                    </Button>
                  </div>
                </GlassCard>
                <p className="text-[11px] text-aria-text4 mb-4">
                  Configure API keys for each source connector. Click <strong>Verify</strong> to test the connection.
                </p>
                {SOURCE_CATEGORIES.map((cat) => (
                  <div key={cat.id}>
                    <p className="text-[11px] font-medium text-aria-text3 mb-2">{cat.label}</p>
                    <div className="space-y-2">
                      {sourcesByCategory(cat.id as SourceCategory).map((src) => {
                        const vs = verifyStatus[src.id] ?? "idle";
                        const configured = src.credentials.length === 0
                          || src.credentials.every((f) => !f.required || Boolean(getCredValue(f.key)));
                        return (
                          <Collapsible key={src.id}>
                            <GlassCard className="overflow-hidden">
                              <CollapsibleTrigger className="w-full flex items-center gap-3 p-3 hover:bg-[var(--aria-surface-2)]/30">
                                <span>{src.icon}</span>
                                <span className="text-[13px] font-medium text-aria-text2 flex-1 text-left">{src.name}</span>
                                <VerifyIcon status={vs} />
                                {src.credentials.length === 0 ? (
                                  <span className="text-[9px] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">No auth</span>
                                ) : configured ? (
                                  <span className="text-[9px] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">Configured ✓</span>
                                ) : (
                                  <span className="text-[9px] text-aria-accent bg-aria-accent/[0.08] border border-aria-accent/20 px-1.5 py-px rounded-full">Needs setup</span>
                                )}
                                {src.credentials.length > 0 && <ChevronDown size={12} className="text-aria-text4" />}
                              </CollapsibleTrigger>

                              {src.credentials.length > 0 && (
                                <CollapsibleContent>
                                  <div className="px-3 pb-3 space-y-2 border-t border-[var(--aria-border-subtle)] pt-3">
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
                                          className="h-8 bg-transparent border-[var(--aria-border)] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent rounded-[6px]"
                                        />
                                      </div>
                                    ))}

                                    {/* Verify button */}
                                    <div className="flex items-center gap-2 pt-1">
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-[11px] h-7 border-[var(--aria-border)] bg-transparent text-aria-text2 hover:bg-[rgba(255,255,255,0.03)] rounded-[6px]"
                                        onClick={() => verifySource(src.id, src.credentials)}
                                        disabled={vs === "loading"}
                                      >
                                        {vs === "loading" ? (
                                          <><Loader2 size={11} className="animate-spin mr-1" />Verifying…</>
                                        ) : "Verify"}
                                      </Button>
                                      {verifyMsg[src.id] && (
                                        <span className={`text-[11px] ${vs === "ok" ? "text-aria-success" : "text-red-400"}`}>
                                          {verifyMsg[src.id]}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </CollapsibleContent>
                              )}
                            </GlassCard>
                          </Collapsible>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </motion.div>
            )}

            {/* ── LLM Cloud ───────────────────────────────────────────────── */}
            {activeSection === "llm-cloud" && (
              <motion.div className="space-y-3">
                <ActiveLLMBadge llmStatus={llmStatus} />
                <p className="text-[11px] text-aria-text4 mb-4">
                  Configure a cloud LLM for document cleaning and synthesis. Click <strong>Set Active</strong> to make it the default.
                </p>
                {LLM_CLOUD_PROVIDERS.map((provider) => {
                  const keyField   = provider.fields.find((f) => f.key.endsWith("_API_KEY"));
                  const modelField = provider.fields.find((f) => f.key.endsWith("_MODEL"));
                  const configured = provider.fields.every((f) => !f.required || Boolean(getCredValue(f.key)));
                  const isActive   = llmStatus?.provider === provider.id;
                  const vs         = verifyStatus[provider.id] ?? "idle";

                  return (
                    <Collapsible key={provider.id}>
                      <GlassCard className={`overflow-hidden ${isActive ? "ring-1 ring-aria-accent/40" : ""}`}>
                        <CollapsibleTrigger className="w-full flex items-center gap-3 p-4 hover:bg-[var(--aria-surface-2)]/30">
                          <span className="text-xl">{provider.icon}</span>
                          <span className="text-[13px] font-semibold text-aria-text1 flex-1 text-left">{provider.name}</span>
                          {isActive && (
                            <span className="text-[9px] text-aria-accent border border-aria-accent/30 bg-aria-accent/10 px-1.5 py-px rounded-full">Active</span>
                          )}
                          <VerifyIcon status={vs} />
                          {configured ? (
                            <span className="text-[9px] text-aria-success bg-aria-success/10 border border-aria-success/20 px-1.5 py-px rounded-full">Configured ✓</span>
                          ) : (
                            <span className="text-[9px] text-aria-text4 bg-[var(--aria-surface)] border border-[var(--aria-border)] px-1.5 py-px rounded-full">Not set</span>
                          )}
                          <ChevronDown size={12} className="text-aria-text4" />
                        </CollapsibleTrigger>

                        <CollapsibleContent>
                          <div className="px-4 pb-4 space-y-3 border-t border-[var(--aria-border-subtle)] pt-3">
                            {/* API key field */}
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
                                  className="h-8 bg-transparent border-[var(--aria-border)] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent rounded-[6px]"
                                />
                              </div>
                            ))}

                            {/* Model selector */}
                            <div>
                              <p className="text-[10px] text-aria-text4 mb-1.5">Select model</p>
                              <div className="flex flex-wrap gap-1.5">
                                {provider.defaultModels.map((m) => {
                                  const currentModel = getCredValue(modelField?.key ?? "");
                                  const selected = currentModel === m || (!currentModel && m === provider.defaultModels[0]);
                                  return (
                                    <button
                                      key={m}
                                      onClick={() => modelField && setCredValue(modelField.key, m)}
                                      className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-all ${
                                        selected
                                          ? "text-aria-accent border-aria-accent/40 bg-aria-accent/10"
                                          : "text-aria-text3 border-[var(--aria-border)] bg-[var(--aria-surface)] hover:border-aria-accent/30"
                                      }`}
                                    >
                                      {m}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2 pt-1">
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-[11px] h-7 border-[var(--aria-border)] bg-transparent text-aria-text2 hover:bg-[rgba(255,255,255,0.03)] rounded-[6px]"
                                onClick={() => keyField && verifyCloudLLM(provider.id, keyField.key)}
                                disabled={vs === "loading"}
                              >
                                {vs === "loading" ? (
                                  <><Loader2 size={11} className="animate-spin mr-1" />Verifying…</>
                                ) : "Verify"}
                              </Button>
                              <Button
                                size="sm"
                                className="text-[11px] h-7 bg-aria-accent/[0.12] text-aria-accent border border-aria-accent/20 hover:bg-aria-accent/20 rounded-[6px]"
                                onClick={() =>
                                  modelField
                                    ? setActiveProvider(provider.id, modelField.key, getCredValue(modelField.key) || provider.defaultModels[0])
                                    : toast.info(`Set ${provider.id} as active — click Save`)
                                }
                              >
                                {isActive ? "Active ✓" : "Set Active"}
                              </Button>
                              {verifyMsg[provider.id] && (
                                <span className={`text-[11px] ${vs === "ok" ? "text-aria-success" : "text-red-400"}`}>
                                  {verifyMsg[provider.id]}
                                </span>
                              )}
                            </div>
                          </div>
                        </CollapsibleContent>
                      </GlassCard>
                    </Collapsible>
                  );
                })}
              </motion.div>
            )}

            {/* ── LLM Local (Ollama) ─────────────────────────────────────── */}
            {activeSection === "llm-local" && (
              <motion.div className="space-y-4">
                <ActiveLLMBadge llmStatus={llmStatus} />
                <GlassCard className="p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[13px] font-semibold text-aria-text1">Local LLM (Ollama)</p>
                      <p className="text-[11px] text-aria-text4 mt-0.5">Use a locally running model — no API key needed</p>
                    </div>
                    <Switch
                      checked={localLLMEnabled}
                      onCheckedChange={setLocalLLMEnabled}
                      className="data-[state=checked]:bg-aria-accent"
                      aria-label="Enable local Ollama LLM"
                    />
                  </div>

                  {localLLMEnabled && (
                    <div className="space-y-3 pt-2 border-t border-[var(--aria-border)]">
                      {/* Base URL */}
                      <div className="space-y-1">
                        <Label className="text-[11px] text-aria-text4">Ollama Base URL</Label>
                        <Input
                          value={ollamaUrl}
                          onChange={(e) => setOllamaUrl(e.target.value)}
                          placeholder="http://localhost:11434"
                          className="h-8 bg-transparent border-[var(--aria-border)] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent rounded-[6px]"
                        />
                      </div>

                      {/* Model selector — shows available models if connected */}
                      <div className="space-y-1.5">
                        <Label className="text-[11px] text-aria-text4">Model</Label>
                        {ollamaModels.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {ollamaModels.map((m) => (
                              <button
                                key={m}
                                onClick={() => setOllamaModel(m)}
                                className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-all ${
                                  ollamaModel === m
                                    ? "text-aria-accent border-aria-accent/40 bg-aria-accent/10"
                                    : "text-aria-text3 border-[var(--aria-border)] bg-[var(--aria-surface)] hover:border-aria-accent/30"
                                }`}
                              >
                                {m}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <Input
                            value={ollamaModel}
                            onChange={(e) => setOllamaModel(e.target.value)}
                            placeholder="llama3.1:8b, mistral, phi3…"
                            className="h-8 bg-transparent border-[var(--aria-border)] text-aria-text2 placeholder:text-aria-text4 text-[12px] focus-visible:ring-aria-accent rounded-[6px]"
                          />
                        )}
                        {ollamaModels.length === 0 && (
                          <p className="text-[10px] text-aria-text4">Click Test Connection to see available models</p>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-[11px] h-7 border-[var(--aria-border)] bg-transparent text-aria-text2 hover:bg-[rgba(255,255,255,0.03)] rounded-[6px]"
                          onClick={testOllama}
                        >
                          {verifyStatus["ollama"] === "loading"
                            ? <><Loader2 size={11} className="animate-spin mr-1" />Testing…</>
                            : "Test Connection"
                          }
                        </Button>
                        <Button
                          size="sm"
                          className="text-[11px] h-7 bg-aria-accent/[0.12] text-aria-accent border border-aria-accent/20 hover:bg-aria-accent/20 rounded-[6px]"
                          onClick={() => {
                            setLocalLLMEnabled(true);
                            setCredValue("LLM_PROVIDER", "ollama");
                            setCredValue("OLLAMA_BASE_URL", ollamaUrl);
                            setCredValue("OLLAMA_MODEL", ollamaModel);
                            toast.info("Ollama set as active LLM — click Save");
                          }}
                        >
                          {llmStatus?.provider === "ollama" ? "Active ✓" : "Set Active"}
                        </Button>
                        {verifyStatus["ollama"] === "ok" && (
                          <span className="text-[11px] text-aria-success">Connected ✓ {ollamaModels.length} models</span>
                        )}
                        {verifyStatus["ollama"] === "fail" && (
                          <span className="text-[11px] text-red-400">Not reachable</span>
                        )}
                      </div>
                    </div>
                  )}
                </GlassCard>
              </motion.div>
            )}

            {/* ── LLM Ensemble ────────────────────────────────────────────── */}
            {activeSection === "llm-ensemble" && (
              <motion.div className="space-y-4">
                <GlassCard className="p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[13px] font-semibold text-aria-text1">LLM Ensemble</p>
                      <p className="text-[11px] text-aria-text4 mt-0.5">Run multiple LLMs in parallel for richer synthesis</p>
                    </div>
                    <Switch
                      checked={ensembleEnabled}
                      onCheckedChange={setEnsembleEnabled}
                      className="data-[state=checked]:bg-aria-accent"
                      aria-label="Enable LLM ensemble"
                    />
                  </div>
                  {ensembleEnabled && (
                    <div className="space-y-4 pt-2 border-t border-[var(--aria-border)]">
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
                                className="border-[var(--aria-border)] data-[state=checked]:bg-aria-accent data-[state=checked]:border-aria-accent"
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
                              <RadioGroupItem value={s.value} id={s.value} className="border-[var(--aria-border)] text-aria-accent" />
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

            {/* ── Default Mission ─────────────────────────────────────────── */}
            {activeSection === "mission" && (
              <motion.div>
                <GlassCard className="p-4 space-y-3">
                  <p className="text-[13px] font-semibold text-aria-text1">Default Mission YAML</p>
                  <p className="text-[11px] text-aria-text4">Used when launching a run without a custom mission.</p>
                  <Textarea
                    value={defaultMission}
                    onChange={(e) => setDefaultMission(e.target.value)}
                    placeholder="Paste default mission YAML here…"
                    className="min-h-[240px] bg-transparent border-[var(--aria-border)] text-aria-text2 placeholder:text-aria-text4 font-mono text-xs focus-visible:ring-aria-accent resize-none rounded-[6px]"
                  />
                </GlassCard>
              </motion.div>
            )}

            {/* ── Output ──────────────────────────────────────────────────── */}
            {activeSection === "output" && (
              <motion.div>
                <GlassCard className="p-4 space-y-4">
                  <p className="text-[13px] font-semibold text-aria-text1">Default Export Formats</p>
                  <div className="space-y-2">
                    {(["json", "csv", "markdown", "pdf"] as const).map((fmt) => (
                      <label key={fmt} className="flex items-center gap-2 cursor-pointer">
                        <Checkbox
                          checked={outputFormats[fmt]}
                          onCheckedChange={(checked) => setOutputFormats((prev) => ({ ...prev, [fmt]: Boolean(checked) }))}
                          className="border-[var(--aria-border)] data-[state=checked]:bg-aria-accent data-[state=checked]:border-aria-accent"
                        />
                        <span className="text-[12px] text-aria-text2 uppercase">{fmt}</span>
                      </label>
                    ))}
                  </div>
                </GlassCard>
              </motion.div>
            )}

            {/* ── Appearance ─────────────────────────────────────────────── */}
            {activeSection === "appearance" && (
              <motion.div className="space-y-4">
                <GlassCard className="p-4 space-y-4">
                  <div>
                    <p className="text-[13px] font-semibold text-aria-text1 mb-0.5">Theme</p>
                    <p className="text-[11px] text-aria-text4">Choose between dark and light interface</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => theme === "light" && toggleTheme()}
                      className={["relative rounded-lg border-2 overflow-hidden transition-all duration-150 text-left",
                        theme === "dark" ? "border-aria-accent shadow-[0_0_0_1px_var(--aria-accent)]"
                                         : "border-[var(--aria-border)] hover:border-[var(--aria-accent)]/40"].join(" ")}
                    >
                      <div className="bg-[#08090a] p-3 h-24 flex flex-col gap-1.5">
                        <div className="flex gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#0a84ff]/70" />
                          <div className="h-1.5 w-8 rounded bg-white/10" />
                        </div>
                        <div className="flex gap-1.5">
                          {["#0a84ff","#30d158","#ff9f0a"].map((c) => (
                            <div key={c} className="flex-1 h-8 rounded" style={{ background:`${c}18`, border:`1px solid ${c}30` }} />
                          ))}
                        </div>
                        <div className="h-4 rounded bg-white/[0.04] border border-[rgba(255,255,255,0.08)]" />
                      </div>
                      <div className="px-3 py-2 bg-[#0f1011] border-t border-[rgba(255,255,255,0.06)]">
                        <span className="text-[11px] font-medium text-white/80">Dark</span>
                        {theme === "dark" && <span className="float-right text-[9px] text-[#0a84ff] font-medium">Active</span>}
                      </div>
                    </button>
                    <button
                      onClick={() => theme === "dark" && toggleTheme()}
                      className={["relative rounded-lg border-2 overflow-hidden transition-all duration-150 text-left",
                        theme === "light" ? "border-aria-accent shadow-[0_0_0_1px_var(--aria-accent)]"
                                          : "border-[var(--aria-border)] hover:border-[var(--aria-accent)]/40"].join(" ")}
                    >
                      <div className="bg-[#f5f6f8] p-3 h-24 flex flex-col gap-1.5">
                        <div className="flex gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#0071e3]/70" />
                          <div className="h-1.5 w-8 rounded bg-black/10" />
                        </div>
                        <div className="flex gap-1.5">
                          {["#0071e3","#248a3d","#c93400"].map((c) => (
                            <div key={c} className="flex-1 h-8 rounded" style={{ background:`${c}14`, border:`1px solid ${c}28` }} />
                          ))}
                        </div>
                        <div className="h-4 rounded bg-black/[0.04] border border-black/[0.08]" />
                      </div>
                      <div className="px-3 py-2 bg-[#eef0f4] border-t border-black/[0.06]">
                        <span className="text-[11px] font-medium text-black/70">Light</span>
                        {theme === "light" && <span className="float-right text-[9px] text-[#0071e3] font-medium">Active</span>}
                      </div>
                    </button>
                  </div>
                </GlassCard>

                <GlassCard className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-[13px] font-semibold text-aria-text1 mb-0.5">Quick toggle</p>
                    <p className="text-[11px] text-aria-text4">
                      Currently: <span className="text-aria-text2 font-medium capitalize">{theme}</span> mode
                    </p>
                  </div>
                  <Switch
                    checked={theme === "light"}
                    onCheckedChange={toggleTheme}
                    className="data-[state=checked]:bg-aria-accent"
                    aria-label="Toggle light theme"
                  />
                </GlassCard>
              </motion.div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
