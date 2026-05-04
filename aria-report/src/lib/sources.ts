export type SourceCategory = "web" | "academic" | "social" | "media" | "data" | "osint";
export type SourceGroup = "standard" | "advanced";

export interface SourceCredentialField {
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
  type?: "text" | "password";
}

export interface SourceDef {
  id: string;
  name: string;
  category: SourceCategory;
  group: SourceGroup;
  description: string;
  icon: string;
  credentials: SourceCredentialField[];
}

export const SOURCES: SourceDef[] = [
  // Web — standard
  { id: "web", name: "Web Search", category: "web", group: "standard", description: "General web search via search API", icon: "🌐",
    credentials: [{ key: "SEARCH_API_KEY", label: "Search API Key", placeholder: "sk-...", required: true, type: "password" }] },
  { id: "reddit", name: "Reddit", category: "web", group: "standard", description: "Posts and comments from subreddits", icon: "🟠",
    credentials: [
      { key: "REDDIT_CLIENT_ID", label: "Client ID", placeholder: "...", required: true, type: "text" },
      { key: "REDDIT_CLIENT_SECRET", label: "Client Secret", placeholder: "...", required: true, type: "password" },
    ] },
  { id: "hackernews", name: "Hacker News", category: "web", group: "standard", description: "Top stories and discussions", icon: "🔶",
    credentials: [] },
  { id: "medium", name: "Medium", category: "web", group: "standard", description: "Articles from Medium publications", icon: "✍️",
    credentials: [] },
  { id: "devto", name: "Dev.to", category: "web", group: "standard", description: "Developer community articles", icon: "👩‍💻",
    credentials: [{ key: "DEVTO_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  { id: "substack", name: "Substack", category: "web", group: "standard", description: "Newsletter posts", icon: "📰",
    credentials: [] },
  { id: "rss", name: "RSS Feeds", category: "web", group: "standard", description: "Custom RSS feed URLs", icon: "📡",
    credentials: [] },
  { id: "wikipedia", name: "Wikipedia", category: "web", group: "standard", description: "Wikipedia articles", icon: "📖",
    credentials: [] },
  { id: "pdf", name: "PDF", category: "web", group: "standard", description: "PDF documents from URLs", icon: "📄",
    credentials: [] },
  { id: "github", name: "GitHub", category: "web", group: "standard", description: "Repository READMEs, issues, discussions", icon: "🐙",
    credentials: [{ key: "GITHUB_TOKEN", label: "Personal Access Token", placeholder: "ghp_...", required: false, type: "password" }] },
  { id: "government", name: "Government", category: "web", group: "standard", description: "Official government publications", icon: "🏛️",
    credentials: [] },
  { id: "notion", name: "Notion", category: "web", group: "standard", description: "Pages and databases from your Notion workspace", icon: "📝",
    credentials: [{ key: "NOTION_API_KEY", label: "Integration Token", placeholder: "secret_...", required: true, type: "password" }] },
  // Academic — standard
  { id: "arxiv", name: "arXiv", category: "academic", group: "standard", description: "Preprints in physics, math, CS, biology", icon: "🎓",
    credentials: [] },
  { id: "pubmed", name: "PubMed", category: "academic", group: "standard", description: "Biomedical literature", icon: "🔬",
    credentials: [{ key: "PUBMED_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  { id: "semantic_scholar", name: "Semantic Scholar", category: "academic", group: "standard", description: "AI-powered research discovery", icon: "🧠",
    credentials: [{ key: "SEMANTIC_SCHOLAR_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  { id: "zotero", name: "Zotero", category: "academic", group: "standard", description: "Personal reference library — local connector or cloud API", icon: "🗂️",
    credentials: [
      { key: "ZOTERO_API_KEY", label: "Cloud API Key", placeholder: "...", required: false, type: "password" },
      { key: "ZOTERO_LIBRARY_ID", label: "Library ID", placeholder: "user/group ID", required: false, type: "text" },
    ] },
  // Social — standard
  { id: "twitter", name: "Twitter / X", category: "social", group: "standard", description: "Tweets and threads", icon: "𝕏",
    credentials: [{ key: "TWITTER_BEARER_TOKEN", label: "Bearer Token", placeholder: "AAAA...", required: true, type: "password" }] },
  { id: "linkedin", name: "LinkedIn", category: "social", group: "standard", description: "Professional posts and articles", icon: "💼",
    credentials: [{ key: "LINKEDIN_ACCESS_TOKEN", label: "Access Token", placeholder: "...", required: true, type: "password" }] },
  { id: "slack", name: "Slack", category: "social", group: "standard", description: "Channel messages (requires bot token)", icon: "💬",
    credentials: [{ key: "SLACK_BOT_TOKEN", label: "Bot Token", placeholder: "xoxb-...", required: true, type: "password" }] },
  // Media — standard
  { id: "youtube", name: "YouTube", category: "media", group: "standard", description: "Video transcripts and metadata", icon: "▶️",
    credentials: [{ key: "YOUTUBE_API_KEY", label: "API Key", placeholder: "AIza...", required: true, type: "password" }] },
  { id: "vimeo", name: "Vimeo", category: "media", group: "standard", description: "Video metadata and transcripts", icon: "🎬",
    credentials: [{ key: "VIMEO_ACCESS_TOKEN", label: "Access Token", placeholder: "...", required: true, type: "password" }] },
  { id: "podcast", name: "Podcast", category: "media", group: "standard", description: "Podcast transcripts via RSS", icon: "🎙️",
    credentials: [] },

  // ── New academic sources ──────────────────────────────────────────────────
  { id: "crossref", name: "CrossRef", category: "academic", group: "standard",
    description: "Scholarly metadata for 140M+ publications with citation counts", icon: "📑",
    credentials: [] },
  { id: "core_ac", name: "CORE", category: "academic", group: "standard",
    description: "300M+ open access full-text research papers", icon: "🔓",
    credentials: [{ key: "CORE_API_KEY", label: "API Key (optional)", placeholder: "...", required: false, type: "password" }] },
  { id: "europe_pmc", name: "Europe PMC", category: "academic", group: "standard",
    description: "Biomedical literature including bioRxiv, medRxiv, PubMed Central", icon: "🧬",
    credentials: [] },
  { id: "ssrn", name: "SSRN", category: "academic", group: "standard",
    description: "Social science and economics preprints", icon: "📊",
    credentials: [] },
  { id: "base_search", name: "BASE Search", category: "academic", group: "standard",
    description: "Bielefeld Academic Search Engine — 300M+ open access documents", icon: "🏛",
    credentials: [] },
  // ── New knowledge & data sources ──────────────────────────────────────────
  { id: "wikidata", name: "Wikidata", category: "web", group: "standard",
    description: "Structured entity knowledge base from Wikimedia Foundation", icon: "🔗",
    credentials: [] },
  { id: "internet_archive", name: "Internet Archive", category: "data", group: "standard",
    description: "Archived web pages, books, and documents from the Wayback Machine", icon: "🏺",
    credentials: [] },
  { id: "propublica", name: "ProPublica", category: "data", group: "standard",
    description: "US Congress bills, votes, and nonprofit financial records", icon: "⚖️",
    credentials: [{ key: "PROPUBLICA_API_KEY", label: "API Key (optional)", placeholder: "...", required: false, type: "password" }] },
  // ── New social sources ─────────────────────────────────────────────────────
  { id: "mastodon", name: "Mastodon", category: "social", group: "standard",
    description: "Public posts from mastodon.social — decentralised social network", icon: "🐘",
    credentials: [{ key: "MASTODON_ACCESS_TOKEN", label: "Access Token (optional)", placeholder: "...", required: false, type: "password" }] },

  // ── Advanced (OSINT / Cybersecurity) — hidden by default ──────────────────
  { id: "shodan", name: "Shodan", category: "osint", group: "advanced",
    description: "Internet-connected device and service discovery", icon: "📡",
    credentials: [{ key: "SHODAN_API_KEY", label: "API Key", placeholder: "...", required: true, type: "password" }] },
  { id: "censys", name: "Censys", category: "osint", group: "advanced",
    description: "Internet-wide device and certificate scanning", icon: "🔍",
    credentials: [
      { key: "CENSYS_API_ID", label: "API ID", placeholder: "...", required: true, type: "text" },
      { key: "CENSYS_API_SECRET", label: "API Secret", placeholder: "...", required: true, type: "password" },
    ] },
  { id: "virustotal", name: "VirusTotal", category: "osint", group: "advanced",
    description: "Malware and URL threat intelligence", icon: "🦠",
    credentials: [{ key: "VIRUSTOTAL_API_KEY", label: "API Key", placeholder: "...", required: true, type: "password" }] },
  { id: "haveibeenpwned", name: "HaveIBeenPwned", category: "osint", group: "advanced",
    description: "Data breach and credential exposure lookup", icon: "🔓",
    credentials: [{ key: "HIBP_API_KEY", label: "API Key", placeholder: "...", required: true, type: "password" }] },
  { id: "whoxy", name: "Whoxy", category: "osint", group: "advanced",
    description: "WHOIS history and reverse domain lookup", icon: "🌐",
    credentials: [{ key: "WHOXY_API_KEY", label: "API Key", placeholder: "...", required: true, type: "password" }] },
  { id: "hunter", name: "Hunter.io", category: "osint", group: "advanced",
    description: "Email finder and company domain search", icon: "📧",
    credentials: [{ key: "HUNTER_API_KEY", label: "API Key", placeholder: "...", required: true, type: "password" }] },
  { id: "social_searcher", name: "Social Searcher", category: "osint", group: "advanced",
    description: "Cross-platform social media monitoring", icon: "📊",
    credentials: [{ key: "SOCIAL_SEARCHER_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  // Jobs Boards — advanced (niche, off by default)
  { id: "jobs_boards", name: "Jobs Boards", category: "data", group: "advanced",
    description: "Job listings from LinkedIn, Indeed, and others", icon: "💼",
    credentials: [] },
];

export const SOURCE_CATEGORIES: { id: SourceCategory; label: string }[] = [
  { id: "web", label: "Web" },
  { id: "academic", label: "Academic" },
  { id: "social", label: "Social" },
  { id: "media", label: "Media" },
  { id: "data", label: "Data" },
  { id: "osint", label: "OSINT" },
];

export function sourcesByCategory(cat: SourceCategory): SourceDef[] {
  return SOURCES.filter((s) => s.category === cat);
}

export const standardSources = SOURCES.filter((s) => s.group === "standard");
export const advancedSources = SOURCES.filter((s) => s.group === "advanced");
