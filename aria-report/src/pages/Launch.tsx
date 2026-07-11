import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Play, ChevronDown, ChevronUp, ArrowRight, SkipForward,
  CheckCircle2, Link2, Upload, FileText, X, Loader2, BookOpen,
} from "lucide-react";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { api, getApiKey } from "@/lib/api";
import { SOURCES, SOURCE_CATEGORIES, sourcesByCategory, advancedSources } from "@/lib/sources";
import { toast } from "sonner";
import type { SourceCategory } from "@/lib/sources";

const DEPTH_LABELS: Record<number, { label: string; docs: string }> = {
  1: { label: "Quick", docs: "~50 docs" },
  2: { label: "Standard", docs: "~200 docs" },
  3: { label: "Deep", docs: "~500 docs" },
  4: { label: "Thorough", docs: "~1500 docs" },
  5: { label: "Exhaustive", docs: "~5000 docs" },
};

// ── Types ─────────────────────────────────────────────────────────────────────

interface DirectorOption { label: string; key: string }
interface DirectorQuestion {
  type: "question"; category: string; question: string;
  options: DirectorOption[]; allows_custom: boolean; skippable: boolean;
}
interface DirectorSession {
  session_id: string; done: boolean;
  question: DirectorQuestion | null; brief: Record<string, unknown> | null;
}

interface SeedPreview {
  title: string;
  authors: string[];
  year: string;
  journal: string;
  doi: string;
  ref_count?: number;
}

type SeedMode = "none" | "doi" | "upload";
type Phase = "topic" | "director" | "config";

// ── API helpers ───────────────────────────────────────────────────────────────

function authHeaders() {
  return getApiKey() ? { "X-API-Key": getApiKey() } : {};
}

async function startDirectorSession(topic: string): Promise<DirectorSession> {
  const res = await fetch("/api/director/session", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function sendDirectorAnswer(sessionId: string, answer: string): Promise<DirectorSession> {
  const res = await fetch(`/api/director/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ answer }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function resolveSeedDoi(doiOrUrl: string): Promise<SeedPreview> {
  const res = await fetch(
    `/api/seed/resolve?q=${encodeURIComponent(doiOrUrl)}`,
    { headers: { ...authHeaders() } }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function uploadSeedPdf(file: File): Promise<SeedPreview> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/seed/upload", {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Seed Paper Card ───────────────────────────────────────────────────────────

function SeedPaperSection({
  seedMode, setSeedMode,
  doiInput, setDoiInput,
  seedPreview, setSeedPreview,
  uploadedFile, setUploadedFile,
}: {
  seedMode: SeedMode; setSeedMode: (m: SeedMode) => void;
  doiInput: string; setDoiInput: (v: string) => void;
  seedPreview: SeedPreview | null; setSeedPreview: (p: SeedPreview | null) => void;
  uploadedFile: File | null; setUploadedFile: (f: File | null) => void;
}) {
  const [resolving, setResolving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleDoiResolve() {
    if (!doiInput.trim()) return;
    setResolving(true);
    setSeedPreview(null);
    try {
      const preview = await resolveSeedDoi(doiInput.trim());
      setSeedPreview(preview);
    } catch {
      toast.error("Could not resolve DOI/URL — check the value and try again.");
    } finally {
      setResolving(false);
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== "application/pdf") {
      toast.error("Please upload a PDF file.");
      return;
    }
    setUploadedFile(file);
    setUploading(true);
    setSeedPreview(null);
    try {
      const preview = await uploadSeedPdf(file);
      setSeedPreview(preview);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      // Issue #11 fix — surface the specific error so users know what went wrong
      if (msg.includes("413")) {
        toast.error("PDF too large — maximum size is 50 MB.");
      } else if (msg.includes("400")) {
        toast.error("Only PDF files are supported.");
      } else if (msg.includes("422")) {
        toast.error("Could not read this PDF — try a text-based PDF rather than a scanned image.");
      } else {
        toast.error(`PDF upload failed: ${msg.replace(/^\d+:\s*/, "").slice(0, 120)}`);
      }
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const syntheticEvent = { target: { files: [file] } } as unknown as React.ChangeEvent<HTMLInputElement>;
    handleFileChange(syntheticEvent);
  }

  function clearSeed() {
    setSeedMode("none");
    setSeedPreview(null);
    setDoiInput("");
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <GlassCard className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-[11px] font-[510] text-aria-text4 uppercase tracking-widest flex items-center gap-1.5">
          <BookOpen size={11} />
          Seed Paper <span className="normal-case font-normal">(optional)</span>
        </Label>
        {seedMode !== "none" && (
          <button onClick={clearSeed} className="text-aria-text4 hover:text-aria-text2 transition-colors">
            <X size={13} />
          </button>
        )}
      </div>

      {/* Mode picker */}
      {seedMode === "none" && (
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setSeedMode("doi")}
            className="flex flex-col items-center gap-2 p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] text-aria-text3 hover:border-aria-accent/40 hover:text-aria-text1 hover:bg-aria-accent/[0.04] transition-all text-[12px]"
          >
            <Link2 size={16} className="text-aria-text4" />
            <span className="font-[510]">DOI or URL</span>
            <span className="text-[10px] text-aria-text4 text-center leading-tight">
              Paste a DOI or paper link
            </span>
          </button>
          <button
            onClick={() => { setSeedMode("upload"); setTimeout(() => fileInputRef.current?.click(), 50); }}
            className="flex flex-col items-center gap-2 p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] text-aria-text3 hover:border-aria-accent/40 hover:text-aria-text1 hover:bg-aria-accent/[0.04] transition-all text-[12px]"
          >
            <Upload size={16} className="text-aria-text4" />
            <span className="font-[510]">Upload PDF</span>
            <span className="text-[10px] text-aria-text4 text-center leading-tight">
              Upload the paper directly
            </span>
          </button>
        </div>
      )}

      {/* DOI / URL input */}
      {seedMode === "doi" && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <Input
              value={doiInput}
              onChange={(e) => { setDoiInput(e.target.value); setSeedPreview(null); }}
              onKeyDown={(e) => { if (e.key === "Enter") handleDoiResolve(); }}
              placeholder="10.xxxx/xxxxx or https://..."
              className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 focus-visible:ring-aria-accent text-[13px]"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleDoiResolve}
              disabled={!doiInput.trim() || resolving}
              className="border-white/[0.06] text-aria-text2 hover:border-aria-accent/40 shrink-0"
            >
              {resolving ? <Loader2 size={13} className="animate-spin" /> : <ArrowRight size={13} />}
            </Button>
          </div>
        </div>
      )}

      {/* PDF upload drop zone */}
      {seedMode === "upload" && !uploadedFile && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          className="flex flex-col items-center gap-2 p-6 rounded-lg border border-dashed border-white/[0.12] bg-white/[0.01] text-aria-text4 hover:border-aria-accent/40 hover:text-aria-text3 cursor-pointer transition-all"
        >
          <Upload size={20} />
          <span className="text-[12px]">Drop PDF here or click to browse</span>
        </div>
      )}

      {/* Uploading spinner */}
      {uploading && (
        <div className="flex items-center gap-2 text-[12px] text-aria-text4">
          <Loader2 size={13} className="animate-spin text-aria-accent" />
          Extracting paper info…
        </div>
      )}

      {/* Preview card */}
      {seedPreview && (
        <div className="p-3 rounded-lg bg-aria-accent/[0.06] border border-aria-accent/20 space-y-1.5">
          <div className="flex items-start gap-2">
            <FileText size={13} className="text-aria-accent mt-0.5 shrink-0" />
            <p className="text-[13px] font-[510] text-aria-text1 leading-snug">
              {seedPreview.title || "Title not resolved"}
            </p>
          </div>
          {seedPreview.authors?.length > 0 && (
            <p className="text-[11px] text-aria-text4 pl-5">
              {seedPreview.authors.slice(0, 3).join(", ")}
              {seedPreview.authors.length > 3 ? ` +${seedPreview.authors.length - 3} more` : ""}
              {seedPreview.year ? ` · ${seedPreview.year}` : ""}
            </p>
          )}
          {seedPreview.journal && (
            <p className="text-[11px] text-aria-text4 pl-5 italic">{seedPreview.journal}</p>
          )}
          {seedPreview.ref_count != null && (
            <p className="text-[11px] text-aria-accent pl-5">
              ✓ {seedPreview.ref_count} references found — will crawl all citations
            </p>
          )}
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileChange}
      />
    </GlassCard>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function Launch() {
  const navigate = useNavigate();

  // Shared state
  const [phase, setPhase] = useState<Phase>("topic");
  const [topic, setTopic] = useState("");

  // Seed paper state
  const [seedMode, setSeedMode] = useState<SeedMode>("none");
  const [doiInput, setDoiInput] = useState("");
  const [seedPreview, setSeedPreview] = useState<SeedPreview | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  // Director state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<DirectorQuestion | null>(null);
  const [customAnswer, setCustomAnswer] = useState("");
  const [directorBrief, setDirectorBrief] = useState<Record<string, unknown> | null>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [directorLoading, setDirectorLoading] = useState(false);

  // Config state
  const [missionYaml, setMissionYaml] = useState("");
  const [showYaml, setShowYaml] = useState(false);
  const [depth, setDepth] = useState(2);
  const [showConfig, setShowConfig] = useState(false);
  const [showAdvancedSources, setShowAdvancedSources] = useState(false);
  const [enabledSources, setEnabledSources] = useState<Record<string, boolean>>(
    Object.fromEntries(SOURCES.map((s) => [s.id, ["web", "arxiv", "hackernews"].includes(s.id)]))
  );

  // ── Launch mutation ────────────────────────────────────────────────────────

  const launch = useMutation({
    mutationFn: async () => {
      const free_sources: Record<string, boolean> = {};
      const auth_sources: Record<string, boolean> = {};
      SOURCES.forEach((s) => {
        if (s.credentials.length === 0) free_sources[s.id] = enabledSources[s.id] ?? false;
        else auth_sources[s.id] = enabledSources[s.id] ?? false;
      });

      const resolvedTopic = (directorBrief?.resolved_topic as string) || topic;

      // Build seed payload
      let seedPayload: Record<string, string> = {};
      if (seedMode === "doi" && doiInput.trim()) {
        const isUrl = doiInput.trim().startsWith("http");
        seedPayload = isUrl
          ? { seed_url: doiInput.trim() }
          : { seed_doi: doiInput.trim() };
      } else if (seedMode === "upload" && uploadedFile) {
        // For uploaded PDFs, send as multipart — handled separately below
        const form = new FormData();
        form.append("file", uploadedFile);
        form.append("topic", resolvedTopic);
        form.append("depth_level", String(depth));
        SOURCES.forEach((s) => {
          if (s.credentials.length === 0) form.append(`free_sources[${s.id}]`, String(enabledSources[s.id] ?? false));
        });
        if (sessionId) form.append("director_session_id", sessionId);
        const res = await fetch("/api/runs/with-pdf", {
          method: "POST",
          headers: { ...(getApiKey() ? { "X-API-Key": getApiKey() } : {}) },
          body: form,
        });
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      }

      return api.runs.start({
        topic: resolvedTopic,
        depth_level: depth as 1 | 2 | 3 | 4 | 5,
        free_sources,
        auth_sources,
        ...(sessionId ? { director_session_id: sessionId } : {}),
        ...(missionYaml.trim() ? { mission_yaml: missionYaml } : {}),
        ...seedPayload,
      });
    },
    onSuccess: (run) => {
      toast.success("Run started");
      navigate(`/monitor/${run.run_id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // ── Director handlers ──────────────────────────────────────────────────────

  async function handleTopicSubmit() {
    if (!topic.trim()) return;
    setDirectorLoading(true);
    try {
      const session = await startDirectorSession(topic.trim());
      setSessionId(session.session_id);
      if (session.done || !session.question) {
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
      if (msg.startsWith("401")) toast.error("API authentication failed.");
      else if (/^5\d\d/.test(msg)) toast.error("Director service unavailable.");
      else console.warn("Director answer failed:", msg);
      setPhase("config");
    } finally {
      setDirectorLoading(false);
    }
  }

  function toggleSource(id: string) {
    setEnabledSources((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  const activeCount = Object.values(enabledSources).filter(Boolean).length;
  const hasSeed = (seedMode === "doi" && doiInput.trim()) || (seedMode === "upload" && !!uploadedFile);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageTopbar title="Launch Run" />
      <div className="flex-1 overflow-y-auto p-5 pb-16 md:pb-5 max-w-3xl w-full mx-auto space-y-4">

        {/* ── Phase: topic input ───────────────────────────────────────── */}
        {phase === "topic" && (
          <>
            {/* Seed Paper — shown first, above topic */}
            <SeedPaperSection
              seedMode={seedMode} setSeedMode={setSeedMode}
              doiInput={doiInput} setDoiInput={setDoiInput}
              seedPreview={seedPreview} setSeedPreview={setSeedPreview}
              uploadedFile={uploadedFile} setUploadedFile={setUploadedFile}
            />

            {/* Topic */}
            <GlassCard className="p-4 space-y-2">
              <Label className="text-[11px] font-[510] text-aria-text4 uppercase tracking-widest">
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
                placeholder={
                  hasSeed
                    ? "Add a topic to expand beyond the paper's citations (optional)…"
                    : "What do you want to research? E.g. 'depression', 'quantum computing', 'climate policy'"
                }
                className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 resize-none focus-visible:ring-aria-accent min-h-[80px]"
                autoFocus={!hasSeed}
              />
              {hasSeed && !topic.trim() && (
                <p className="text-[11px] text-aria-text4">
                  No topic needed — ARIA will use the seed paper's subject automatically.
                </p>
              )}
            </GlassCard>

            <Button
              className="w-full h-11 bg-aria-brand hover:bg-aria-accent text-white font-[510] brand-glow disabled:opacity-40"
              onClick={handleTopicSubmit}
              disabled={(!topic.trim() && !hasSeed) || directorLoading}
            >
              {directorLoading ? (
                "Thinking…"
              ) : hasSeed && !topic.trim() ? (
                <><BookOpen size={14} className="mr-2" /> Continue with Seed Paper</>
              ) : (
                <><ArrowRight size={14} className="mr-2" /> Start Research Planning</>
              )}
            </Button>

            {!hasSeed && (
              <p className="text-center text-[12px] text-aria-text4">
                ARIA will ask a few questions to understand what you need before searching.
              </p>
            )}
          </>
        )}

        {/* ── Phase: director conversation ─────────────────────────────── */}
        {phase === "director" && currentQuestion && (
          <>
            <div className="flex items-center gap-2 text-[12px] text-aria-text4">
              <span className="text-aria-text2 font-[510]">{topic}</span>
              {answeredCount > 0 && (
                <span className="ml-auto flex items-center gap-1">
                  <CheckCircle2 size={12} className="text-aria-accent" />
                  {answeredCount} answered
                </span>
              )}
            </div>

            <GlassCard className="p-5 space-y-4">
              <div className="space-y-1">
                <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest">
                  {currentQuestion.category.replace(/_/g, " ")}
                </p>
                <p className="text-[16px] font-[510] text-aria-text1 leading-snug">
                  {currentQuestion.question}
                </p>
              </div>

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

              {currentQuestion.allows_custom && (
                <div className="flex gap-2">
                  <Input
                    value={customAnswer}
                    onChange={(e) => setCustomAnswer(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && customAnswer.trim()) handleAnswer(customAnswer.trim()); }}
                    placeholder="Or type your own answer…"
                    disabled={directorLoading}
                    className="bg-transparent border-white/[0.06] text-aria-text1 placeholder:text-aria-text4 focus-visible:ring-aria-accent text-[13px]"
                  />
                  <Button
                    variant="outline" size="sm"
                    onClick={() => handleAnswer(customAnswer.trim())}
                    disabled={!customAnswer.trim() || directorLoading}
                    className="border-white/[0.06] text-aria-text2 hover:border-aria-accent/40"
                  >
                    <ArrowRight size={14} />
                  </Button>
                </div>
              )}
            </GlassCard>

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
              <p className="text-center text-[12px] text-aria-text4 animate-pulse">Thinking…</p>
            )}
          </>
        )}

        {/* ── Phase: config + launch ────────────────────────────────────── */}
        {phase === "config" && (
          <>
            {/* Seed summary pill */}
            {hasSeed && seedPreview && (
              <GlassCard className="p-3 border-aria-accent/20 flex items-start gap-3">
                <FileText size={14} className="text-aria-accent mt-0.5 shrink-0" />
                <div>
                  <p className="text-[12px] font-[510] text-aria-text1">{seedPreview.title}</p>
                  <p className="text-[11px] text-aria-text4 mt-0.5">
                    Citation crawl enabled · {seedPreview.ref_count ?? "?"} references will be collected
                  </p>
                </div>
              </GlassCard>
            )}

            {/* Director brief */}
            {directorBrief && (
              <GlassCard className="p-4 space-y-2 border-aria-accent/20">
                <p className="text-[10px] font-[510] text-aria-accent uppercase tracking-widest">Research Brief Ready</p>
                <p className="text-[14px] text-aria-text1 font-[510]">
                  {(directorBrief.resolved_topic as string) || topic}
                </p>
                {Array.isArray(directorBrief.key_questions) && directorBrief.key_questions.length > 0 && (
                  <ul className="space-y-1 pt-1">
                    {(directorBrief.key_questions as string[]).slice(0, 4).map((q, i) => (
                      <li key={i} className="text-[12px] text-aria-text3 flex gap-2">
                        <span className="text-aria-text4 flex-shrink-0">{i + 1}.</span>{q}
                      </li>
                    ))}
                    {(directorBrief.key_questions as string[]).length > 4 && (
                      <li className="text-[12px] text-aria-text4">
                        +{(directorBrief.key_questions as string[]).length - 4} more questions
                      </li>
                    )}
                  </ul>
                )}
              </GlassCard>
            )}

            {/* Mission YAML */}
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

            {/* Sources */}
            <GlassCard className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-[11px] font-[510] text-aria-text4 uppercase tracking-widest">Sources</Label>
                <span className="text-[11px] text-aria-accent">{activeCount} selected</span>
              </div>
              {SOURCE_CATEGORIES.map((cat) => {
                const catStandardSources = sourcesByCategory(cat.id as SourceCategory).filter((s) => s.group === "standard");
                if (catStandardSources.length === 0) return null;
                return (
                  <div key={cat.id}>
                    <p className="text-[10px] font-[510] text-aria-text4 uppercase tracking-widest mb-2">{cat.label}</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {catStandardSources.map((s) => (
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
                );
              })}

              <div className="border-t border-white/[0.06] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAdvancedSources((v) => !v)}
                  className="flex w-full items-center justify-between text-[11px] text-aria-text4 hover:text-aria-text2 transition-colors"
                >
                  <span className="font-[510] uppercase tracking-widest">Advanced — Cybersecurity &amp; OSINT</span>
                  {showAdvancedSources ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {showAdvancedSources && (
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {advancedSources.map((s) => (
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
                )}
              </div>
            </GlassCard>

            {/* Depth */}
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
                  <Slider min={1} max={5} step={1} value={[depth]} onValueChange={([v]) => setDepth(v)} />
                  <div className="flex justify-between text-[10px] text-aria-text4">
                    {Object.values(DEPTH_LABELS).map((d) => (
                      <span key={d.label}>{d.label}</span>
                    ))}
                  </div>
                </div>
              )}
            </GlassCard>

            {/* Launch */}
            <Button
              className="w-full h-11 bg-aria-brand hover:bg-aria-accent text-white font-[510] brand-glow disabled:opacity-40"
              onClick={() => launch.mutate()}
              disabled={(!topic.trim() && !hasSeed) || launch.isPending}
            >
              {launch.isPending ? "Starting…" : (
                <><Play size={14} className="mr-2" /> Launch Research Run</>
              )}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
