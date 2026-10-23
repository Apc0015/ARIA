import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Play, ChevronDown, ChevronUp, ArrowRight, SkipForward, CheckCircle2, BookOpen, X } from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { SOURCES, SOURCE_CATEGORIES, sourcesByCategory, advancedSources } from "@/lib/sources";
import { useEnabledSources } from "@/hooks/useEnabledSources";
import { toast } from "sonner";
import type { SourceCategory } from "@/lib/sources";
import type { SeedPreview } from "@/types";

const DEPTH_LABELS: Record<number, { label: string; docs: string }> = {
  1: { label: "Quick", docs: "~50 docs" },
  2: { label: "Standard", docs: "~200 docs" },
  3: { label: "Deep", docs: "~500 docs" },
  4: { label: "Thorough", docs: "~1500 docs" },
  5: { label: "Exhaustive", docs: "~5000 docs" },
};

// ── Research Director types ───────────────────────────────────────────────────

interface DirectorOption {
  label: string;
  key: string;
}

interface DirectorQuestion {
  type: "question";
  category: string;
  question: string;
  options: DirectorOption[];
  allows_custom: boolean;
  skippable: boolean;
}

interface DirectorSession {
  session_id: string;
  done: boolean;
  question: DirectorQuestion | null;
  brief: Record<string, unknown> | null;
}

// ── Phases ────────────────────────────────────────────────────────────────────
// "topic" → user enters topic
// "director" → Research Director conversation
// "config" → source/depth config (existing form)
type Phase = "topic" | "director" | "config";
type LaunchMode = "guided" | "manual" | "yaml";

const LAUNCH_MODES: Array<{
  id: LaunchMode;
  label: string;
  description: string;
}> = [
  {
    id: "guided",
    label: "Guided",
    description: "Research Director asks clarifying questions before launch.",
  },
  {
    id: "manual",
    label: "Manual",
    description: "You choose depth and sources without Director overrides.",
  },
  {
    id: "yaml",
    label: "YAML",
    description: "Your mission file is used directly as the run contract.",
  },
];

// ── API helpers ───────────────────────────────────────────────────────────────

async function startDirectorSession(topic: string): Promise<DirectorSession> {
  const res = await fetch("/api/director/session", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function sendDirectorAnswer(
  sessionId: string,
  answer: string
): Promise<DirectorSession> {
  const res = await fetch(`/api/director/${sessionId}/answer`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Launch() {
  const navigate = useNavigate();

  // Shared
  const [phase, setPhase] = useState<Phase>("topic");
  const [launchMode, setLaunchMode] = useState<LaunchMode>("guided");
  const [topic, setTopic] = useState("");

  // Director state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<DirectorQuestion | null>(null);
  const [customAnswer, setCustomAnswer] = useState("");
  const [directorBrief, setDirectorBrief] = useState<Record<string, unknown> | null>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [directorLoading, setDirectorLoading] = useState(false);

  // Config state (existing form)
  const [missionYaml, setMissionYaml] = useState("");
  const [showYaml, setShowYaml] = useState(false);
  const [depth, setDepth] = useState(2);
  const [showConfig, setShowConfig] = useState(false);
  const [showAdvancedSources, setShowAdvancedSources] = useState(false);
  const { isEnabled, toggle } = useEnabledSources();
  const sourceEnabled = (id: string) => isEnabled(id, ["web", "arxiv", "hackernews"].includes(id));

  // Seed paper (optional citation crawl)
  const [seedInput, setSeedInput] = useState("");
  const [seedPreview, setSeedPreview] = useState<SeedPreview | null>(null);
  const [seedResolving, setSeedResolving] = useState(false);

  // ── Mutations ─────────────────────────────────────────────────────────────

  const launch = useMutation({
    mutationFn: () => {
      const free_sources: Record<string, boolean> = {};
      const auth_sources: Record<string, boolean> = {};
      SOURCES.forEach((s) => {
        if (s.credentials.length === 0) free_sources[s.id] = sourceEnabled(s.id);
        else auth_sources[s.id] = sourceEnabled(s.id);
      });

      const resolvedTopic =
        ((launchMode === "guided" ? directorBrief?.resolved_topic : null) as string | null)
        || topic.trim()
        || "Mission YAML run";

      if (missionYaml.trim()) {
        return api.runs.start({
          topic: topic.trim() || undefined,
          mission_yaml: missionYaml,
          launch_mode: "yaml",
        });
      }

      const seed = seedInput.trim();
      const seedPayload = seed
        ? /^https?:\/\//i.test(seed) ? { seed_url: seed } : { seed_doi: seed }
        : {};

      return api.runs.start({
        topic: resolvedTopic,
        depth_level: depth as 1 | 2 | 3 | 4 | 5,
        free_sources,
        auth_sources,
        launch_mode: launchMode,
        ...(launchMode === "guided" && sessionId ? { director_session_id: sessionId } : {}),
        ...seedPayload,
      });
    },
    onSuccess: (run) => {
      toast.success("Run started");
      navigate(`/monitor/${run.run_id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // ── Handlers ──────────────────────────────────────────────────────────────

  async function handleTopicSubmit() {
    if (!topic.trim() && launchMode !== "yaml") return;
    if (launchMode !== "guided") {
      setSessionId(null);
      setCurrentQuestion(null);
      setDirectorBrief(null);
      setPhase("config");
      return;
    }
    setDirectorLoading(true);
    try {
      const session = await startDirectorSession(topic.trim());
      setSessionId(session.session_id);
      if (session.done || !session.question) {
        // No conversation needed (LLM unavailable, etc.) → go straight to config
        setDirectorBrief(session.brief);
        setPhase("config");
      } else {
        setCurrentQuestion(session.question);
        setPhase("director");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.startsWith("401")) {
        toast.error("API authentication failed. Check your API key in Settings.");
      } else if (/^5\d\d/.test(msg)) {
        toast.error("Director service unavailable. Starting in manual mode.");
      } else {
        console.warn("Director session failed:", msg);
        toast.error("Guided research could not start. Configure an AI model or use Manual mode.");
      }
      setPhase("config");
    } finally {
      setDirectorLoading(false);
    }
  }

  async function handleAnswer(answer: string) {
    if (!sessionId) return;
    setDirectorLoading(true);
    setAnsweredCount((n) => n + 1);
    try {
      const session = await sendDirectorAnswer(sessionId, answer);
      setCustomAnswer("");
      if (session.done || !session.question) {
        setDirectorBrief(session.brief);
        setPhase("config");
      } else {
        setCurrentQuestion(session.question);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.startsWith("401")) {
        toast.error("API authentication failed. Check your API key in Settings.");
      } else if (/^5\d\d/.test(msg)) {
        toast.error("Director service unavailable.");
      } else {
        console.warn("Director answer failed:", msg);
      }
      setPhase("config");
    } finally {
      setDirectorLoading(false);
    }
  }

  async function handleSeedResolve() {
    const seed = seedInput.trim();
    if (!seed) return;
    setSeedResolving(true);
    setSeedPreview(null);
    try {
      setSeedPreview(await api.seed.resolve(seed));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg.replace(/^\d+:\s*/, "") || "Could not look up that paper.");
    } finally {
      setSeedResolving(false);
    }
  }

  function clearSeed() {
    setSeedInput("");
    setSeedPreview(null);
  }

  function toggleSource(id: string) {
    toggle(id, ["web", "arxiv", "hackernews"].includes(id));
  }

  const activeCount = SOURCES.filter((source) => sourceEnabled(source.id)).length;
  const hasMissionYaml = Boolean(missionYaml.trim());
  const canLaunch =
    launchMode === "yaml" || hasMissionYaml
      ? hasMissionYaml && !launch.isPending
      : Boolean(topic.trim()) && activeCount > 0 && !launch.isPending;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar title="Launch Run" />
      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 max-w-3xl w-full mx-auto space-y-4">

        {/* ── Phase: topic input ───────────────────────────────────────── */}
        {phase === "topic" && (
          <>
            <GlassCard className="p-3">
              <div className="grid grid-cols-3 gap-2" role="group" aria-label="Launch mode">
                {LAUNCH_MODES.map((mode) => {
                  const active = launchMode === mode.id;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => {
                        setLaunchMode(mode.id);
                        if (mode.id === "yaml") setShowYaml(true);
                      }}
                      className={`min-h-[72px] rounded-lg border px-2 py-2 text-left transition-all ${
                        active
                          ? "border-aria-accent/50 bg-aria-accent/[0.10]"
                          : "border-white/[0.06] bg-transparent hover:border-aria-accent/30"
                      }`}
                      aria-pressed={active}
                    >
                      <span className={`block text-[12px] font-semibold ${active ? "text-aria-accent" : "text-aria-text2"}`}>
                        {mode.label}
                      </span>
                      <span className="mt-1 block text-[10px] leading-snug text-aria-text4">
                        {mode.description}
                      </span>
                    </button>
                  );
                })}
              </div>
            </GlassCard>

            <GlassCard className="p-4 space-y-2">
              <Label className="text-[11px] font-medium text-aria-text3">
                Research Topic
              </Label>
              <Textarea
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && topic.trim()) {
                    e.preventDefault();
                    handleTopicSubmit();
                  }
                }}
                placeholder="What do you want to research? E.g. 'depression', 'quantum computing', 'climate policy'"
                className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 resize-none focus-visible:ring-aria-accent min-h-[80px]"
                autoFocus
              />
            </GlassCard>

            <Button
              variant="primary" className="w-full h-11 font-medium text-[15px] disabled:opacity-40"
              onClick={handleTopicSubmit}
              disabled={(launchMode !== "yaml" && !topic.trim()) || directorLoading}
            >
              {directorLoading ? (
                "Thinking…"
              ) : (
                <>
                  <ArrowRight size={14} className="mr-2" />
                  {launchMode === "guided" ? "Start Research Planning" : "Continue to Configuration"}
                </>
              )}
            </Button>

            <p className="text-center text-[12px] text-aria-text4">
              {launchMode === "guided"
                ? "ARIA will ask a few questions to understand what you need before searching."
                : "Manual and YAML modes launch exactly from your selected settings."}
            </p>
          </>
        )}

        {/* ── Phase: director conversation ─────────────────────────────── */}
        {phase === "director" && currentQuestion && (
          <>
            {/* Progress indicator */}
            <div className="flex items-center gap-2 text-[12px] text-aria-text4">
              <span className="text-aria-text2 font-medium">{topic}</span>
              {answeredCount > 0 && (
                <span className="ml-auto flex items-center gap-1">
                  <CheckCircle2 size={12} className="text-aria-accent" />
                  {answeredCount} answered
                </span>
              )}
            </div>

            {/* Question card */}
            <GlassCard className="p-5 space-y-4">
              <div className="space-y-1">
                <p className="text-[11px] font-medium text-aria-text3">
                  {currentQuestion.category.replace(/_/g, " ")}
                </p>
                <p className="text-[16px] font-medium text-aria-text1 leading-snug">
                  {currentQuestion.question}
                </p>
              </div>

              {/* Option buttons */}
              {currentQuestion.options.length > 0 && (
                <div className="grid grid-cols-1 gap-2">
                  {currentQuestion.options.map((opt) => (
                    <button
                      key={opt.key}
                      onClick={() => handleAnswer(opt.key)}
                      disabled={directorLoading}
                      className="flex items-center gap-3 p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] text-left text-[13px] text-aria-text2 hover:border-aria-accent/40 hover:bg-aria-accent/[0.06] transition-all disabled:opacity-40"
                    >
                      <ArrowRight size={12} className="text-aria-text4 flex-shrink-0" />
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}

              {/* Custom text input */}
              {currentQuestion.allows_custom && (
                <div className="flex gap-2">
                  <Input
                    value={customAnswer}
                    onChange={(e) => setCustomAnswer(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && customAnswer.trim()) {
                        handleAnswer(customAnswer.trim());
                      }
                    }}
                    placeholder="Or type your own answer…"
                    disabled={directorLoading}
                    className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 focus-visible:ring-aria-accent text-[13px]"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAnswer(customAnswer.trim())}
                    disabled={!customAnswer.trim() || directorLoading}
                    className="border-white/[0.06] text-aria-text2 hover:border-aria-accent/40"
                  >
                    <ArrowRight size={14} />
                  </Button>
                </div>
              )}
            </GlassCard>

            {/* Skip / Start now actions */}
            <div className="flex gap-2">
              {currentQuestion.skippable && (
                <Button
                  variant="ghost"
                  className="flex-1 text-[13px] text-aria-text4 hover:text-aria-text2 border border-white/[0.04]"
                  onClick={() => handleAnswer("skip")}
                  disabled={directorLoading}
                >
                  <SkipForward size={13} className="mr-1.5" /> Skip
                </Button>
              )}
              <Button
                variant="ghost"
                className="flex-1 text-[13px] text-aria-accent hover:text-aria-brand border border-aria-accent/20 hover:border-aria-accent/40"
                onClick={() => handleAnswer("start")}
                disabled={directorLoading}
              >
                <Play size={13} className="mr-1.5" /> Start research now
              </Button>
            </div>

            {directorLoading && (
              <p className="text-center text-[12px] text-aria-text4 animate-pulse">
                Thinking…
              </p>
            )}
          </>
        )}

        {/* ── Phase: config + launch ────────────────────────────────────── */}
        {phase === "config" && (
          <>
            {/* Brief summary if available */}
            {directorBrief && (
              <GlassCard className="p-4 space-y-2 border-aria-accent/20">
                <p className="text-[11px] font-medium text-aria-accent">
                  Research Brief Ready
                </p>
                <p className="text-[14px] text-aria-text1 font-medium">
                  {(directorBrief.resolved_topic as string) || topic}
                </p>
                {Array.isArray(directorBrief.key_questions) &&
                  directorBrief.key_questions.length > 0 && (
                    <ul className="space-y-1 pt-1">
                      {(directorBrief.key_questions as string[]).slice(0, 4).map((q, i) => (
                        <li key={i} className="text-[12px] text-aria-text3 flex gap-2">
                          <span className="text-aria-text4 flex-shrink-0">{i + 1}.</span>
                          {q}
                        </li>
                      ))}
                      {(directorBrief.key_questions as string[]).length > 4 && (
                        <li className="text-[12px] text-aria-text4">
                          +{(directorBrief.key_questions as string[]).length - 4} more questions
                        </li>
                      )}
                    </ul>
                  )}
                {Array.isArray((directorBrief as Record<string, unknown>).phases) && (
                  <div className="flex gap-2 pt-1 flex-wrap">
                    {((directorBrief as Record<string, unknown>).phases as Array<Record<string, unknown>>).map((ph) => (
                      <span
                        key={ph.name as string}
                        className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-white/[0.08] text-aria-text4"
                      >
                        {(ph.name as string).replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </GlassCard>
            )}

            <GlassCard className="p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-medium text-aria-text3">
                    Launch Mode
                  </p>
                  <p className="mt-1 text-[12px] text-aria-text3">
                    {LAUNCH_MODES.find((mode) => mode.id === launchMode)?.description}
                  </p>
                </div>
                <span className="text-[10px] font-semibold uppercase tracking-widest text-aria-accent border border-aria-accent/25 bg-aria-accent/[0.08] px-2 py-1 rounded">
                  {launchMode}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2" role="group" aria-label="Launch mode">
                {LAUNCH_MODES.map((mode) => {
                  const active = launchMode === mode.id;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => {
                        setLaunchMode(mode.id);
                        if (mode.id === "yaml") setShowYaml(true);
                      }}
                      className={`rounded-md border px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        active
                          ? "border-aria-accent/50 bg-aria-accent/[0.10] text-aria-accent"
                          : "border-white/[0.06] text-aria-text4 hover:text-aria-text2"
                      }`}
                      aria-pressed={active}
                    >
                      {mode.label}
                    </button>
                  );
                })}
              </div>
            </GlassCard>

            {/* Mission YAML toggle */}
            <GlassCard className="p-4">
              <button
                onClick={() => {
                  setShowYaml((v) => !v);
                  setLaunchMode("yaml");
                }}
                className="w-full flex items-center justify-between text-[13px] font-medium text-aria-text2"
              >
                Mission YAML {launchMode === "yaml" ? "(required)" : "(optional override)"}
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
                <Label className="text-[11px] font-medium text-aria-text3">
                  Sources
                </Label>
                <span className="text-[11px] text-aria-accent">{activeCount} selected</span>
              </div>
              {SOURCE_CATEGORIES.map((cat) => {
                const catStandardSources = sourcesByCategory(cat.id as SourceCategory).filter(
                  (s) => s.group === "standard"
                );
                if (catStandardSources.length === 0) return null;
                return (
                  <div key={cat.id}>
                    <p className="text-[11px] font-medium text-aria-text3 mb-2">
                      {cat.label}
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {catStandardSources.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => toggleSource(s.id)}
                          className={`flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-[12px] ${
                            sourceEnabled(s.id)
                              ? "border-aria-accent/40 bg-aria-accent/[0.08] text-aria-text2"
                              : "border-white/[0.06] bg-transparent text-aria-text4"
                          }`}
                        >
                          <span>{s.icon}</span>
                          <span className="font-medium truncate">{s.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* Advanced Sources — collapsed by default */}
              <div className="border-t border-white/[0.06] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAdvancedSources((v) => !v)}
                  className="flex w-full items-center justify-between text-[11px] text-aria-text4 hover:text-aria-text2 transition-colors"
                >
                  <span className="font-medium uppercase tracking-widest">
                    Advanced Sources
                  </span>
                  {showAdvancedSources ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>

                {showAdvancedSources && (
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {advancedSources.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => toggleSource(s.id)}
                        className={`flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-[12px] ${
                          sourceEnabled(s.id)
                            ? "border-aria-accent/40 bg-aria-accent/[0.08] text-aria-text2"
                            : "border-white/[0.06] bg-transparent text-aria-text4"
                        }`}
                      >
                        <span>{s.icon}</span>
                        <span className="font-medium truncate">{s.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </GlassCard>

            {/* Seed paper — optional citation crawl */}
            {launchMode !== "yaml" && !hasMissionYaml && (
              <GlassCard className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-[11px] font-medium text-aria-text3 flex items-center gap-1.5">
                    <BookOpen size={12} />
                    Seed Paper <span className="text-aria-text4 font-normal">(optional)</span>
                  </Label>
                  {seedInput && (
                    <button
                      type="button"
                      onClick={clearSeed}
                      aria-label="Clear seed paper"
                      className="text-aria-text4 hover:text-aria-text2 transition-colors"
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
                <p className="text-[12px] text-aria-text4">
                  Start from a paper's DOI or URL and ARIA will also collect the works it cites.
                </p>
                <div className="flex gap-2">
                  <Input
                    value={seedInput}
                    onChange={(e) => {
                      setSeedInput(e.target.value);
                      setSeedPreview(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && seedInput.trim()) {
                        e.preventDefault();
                        handleSeedResolve();
                      }
                    }}
                    placeholder="10.5787/52-3-1483 or https://…"
                    disabled={seedResolving}
                    className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 focus-visible:ring-aria-accent text-[13px]"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSeedResolve}
                    disabled={!seedInput.trim() || seedResolving}
                    className="border-white/[0.06] text-aria-text2 hover:border-aria-accent/40"
                  >
                    {seedResolving ? "Looking up…" : "Look up"}
                  </Button>
                </div>
                {seedPreview && (
                  <div className="rounded-lg border border-aria-accent/20 bg-aria-accent/[0.06] p-3 space-y-1">
                    <p className="text-[13px] font-medium text-aria-text1">
                      {seedPreview.title || "Title not found — the crawl will still try this seed"}
                    </p>
                    {seedPreview.authors.length > 0 && (
                      <p className="text-[12px] text-aria-text3">
                        {seedPreview.authors.slice(0, 3).join(", ")}
                        {seedPreview.authors.length > 3 ? ` +${seedPreview.authors.length - 3} more` : ""}
                        {seedPreview.year ? ` · ${seedPreview.year}` : ""}
                      </p>
                    )}
                    {seedPreview.journal && (
                      <p className="text-[11px] italic text-aria-text4">{seedPreview.journal}</p>
                    )}
                    {seedPreview.ref_count != null && (
                      <p className="text-[12px] text-aria-accent flex items-center gap-1">
                        <CheckCircle2 size={12} />
                        {seedPreview.ref_count} references found — they'll be crawled during the run
                      </p>
                    )}
                  </div>
                )}
              </GlassCard>
            )}

            {/* Depth config */}
            <GlassCard className="p-4 space-y-3">
              <button
                onClick={() => setShowConfig((v) => !v)}
                className="w-full flex items-center justify-between text-[13px] font-medium text-aria-text2"
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
              variant="primary" className="w-full h-11 font-medium text-[15px] disabled:opacity-40"
              onClick={() => launch.mutate()}
              disabled={!canLaunch}
            >
              {launch.isPending ? (
                "Starting…"
              ) : (
                <>
                  <Play size={14} className="mr-2" /> Launch Research Run
                </>
              )}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
