export type SourceCategory = "web" | "academic" | "social" | "media";

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
  description: string;
  icon: string;
  credentials: SourceCredentialField[];
}

export const SOURCES: SourceDef[] = [
  // Web
  { id: "web", name: "Web Search", category: "web", description: "General web search via search API", icon: "🌐",
    credentials: [{ key: "SEARCH_API_KEY", label: "Search API Key", placeholder: "sk-...", required: true, type: "password" }] },
  { id: "reddit", name: "Reddit", category: "web", description: "Posts and comments from subreddits", icon: "🟠",
    credentials: [
      { key: "REDDIT_CLIENT_ID", label: "Client ID", placeholder: "...", required: true, type: "text" },
      { key: "REDDIT_CLIENT_SECRET", label: "Client Secret", placeholder: "...", required: true, type: "password" },
    ] },
  { id: "hackernews", name: "Hacker News", category: "web", description: "Top stories and discussions", icon: "🔶",
    credentials: [] },
  { id: "medium", name: "Medium", category: "web", description: "Articles from Medium publications", icon: "✍️",
    credentials: [] },
  { id: "devto", name: "Dev.to", category: "web", description: "Developer community articles", icon: "👩‍💻",
    credentials: [{ key: "DEVTO_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  { id: "substack", name: "Substack", category: "web", description: "Newsletter posts", icon: "📰",
    credentials: [] },
  { id: "rss", name: "RSS Feeds", category: "web", description: "Custom RSS feed URLs", icon: "📡",
    credentials: [] },
  { id: "wikipedia", name: "Wikipedia", category: "web", description: "Wikipedia articles", icon: "📖",
    credentials: [] },
  { id: "pdf", name: "PDF", category: "web", description: "PDF documents from URLs", icon: "📄",
    credentials: [] },
  { id: "github", name: "GitHub", category: "web", description: "Repository READMEs, issues, discussions", icon: "🐙",
    credentials: [{ key: "GITHUB_TOKEN", label: "Personal Access Token", placeholder: "ghp_...", required: false, type: "password" }] },
  { id: "government", name: "Government", category: "web", description: "Official government publications", icon: "🏛️",
    credentials: [] },
  // Academic
  { id: "arxiv", name: "arXiv", category: "academic", description: "Preprints in physics, math, CS, biology", icon: "🎓",
    credentials: [] },
  { id: "pubmed", name: "PubMed", category: "academic", description: "Biomedical literature", icon: "🔬",
    credentials: [{ key: "PUBMED_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  { id: "semantic_scholar", name: "Semantic Scholar", category: "academic", description: "AI-powered research discovery", icon: "🧠",
    credentials: [{ key: "SEMANTIC_SCHOLAR_API_KEY", label: "API Key", placeholder: "...", required: false, type: "password" }] },
  // Social
  { id: "twitter", name: "Twitter / X", category: "social", description: "Tweets and threads", icon: "𝕏",
    credentials: [{ key: "TWITTER_BEARER_TOKEN", label: "Bearer Token", placeholder: "AAAA...", required: true, type: "password" }] },
  { id: "linkedin", name: "LinkedIn", category: "social", description: "Professional posts and articles", icon: "💼",
    credentials: [{ key: "LINKEDIN_ACCESS_TOKEN", label: "Access Token", placeholder: "...", required: true, type: "password" }] },
  { id: "slack", name: "Slack", category: "social", description: "Channel messages (requires bot token)", icon: "💬",
    credentials: [{ key: "SLACK_BOT_TOKEN", label: "Bot Token", placeholder: "xoxb-...", required: true, type: "password" }] },
  // Media
  { id: "youtube", name: "YouTube", category: "media", description: "Video transcripts and metadata", icon: "▶️",
    credentials: [{ key: "YOUTUBE_API_KEY", label: "API Key", placeholder: "AIza...", required: true, type: "password" }] },
  { id: "vimeo", name: "Vimeo", category: "media", description: "Video metadata and transcripts", icon: "🎬",
    credentials: [{ key: "VIMEO_ACCESS_TOKEN", label: "Access Token", placeholder: "...", required: true, type: "password" }] },
  { id: "podcast", name: "Podcast", category: "media", description: "Podcast transcripts via RSS", icon: "🎙️",
    credentials: [] },
];

export const SOURCE_CATEGORIES: { id: SourceCategory; label: string }[] = [
  { id: "web", label: "Web" },
  { id: "academic", label: "Academic" },
  { id: "social", label: "Social" },
  { id: "media", label: "Media" },
];

export function sourcesByCategory(cat: SourceCategory): SourceDef[] {
  return SOURCES.filter((s) => s.category === cat);
}
