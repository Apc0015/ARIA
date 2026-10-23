export interface LLMField {
  key: string;
  label: string;
  placeholder: string;
  type: "text" | "password" | "select";
  options?: string[];
  required: boolean;
}

export interface LLMProviderDef {
  id: string;
  name: string;
  icon: string;
  fields: LLMField[];
  defaultModels: string[];
}

export const LLM_CLOUD_PROVIDERS: LLMProviderDef[] = [
  {
    id: "anthropic",
    name: "Anthropic",
    icon: "🧡",
    defaultModels: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"],
    fields: [
      { key: "ANTHROPIC_API_KEY", label: "API Key", placeholder: "sk-ant-...", type: "password", required: true },
      { key: "ANTHROPIC_MODEL", label: "Model", placeholder: "claude-sonnet-4-6", type: "text", required: false },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    icon: "🤖",
    defaultModels: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    fields: [
      { key: "OPENAI_API_KEY", label: "API Key", placeholder: "sk-...", type: "password", required: true },
      { key: "OPENAI_MODEL", label: "Model", placeholder: "gpt-4o", type: "text", required: false },
    ],
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    icon: "🔀",
    defaultModels: ["openai/gpt-4o", "anthropic/claude-sonnet-4-6", "mistralai/mixtral-8x7b"],
    fields: [
      { key: "OPENROUTER_API_KEY", label: "API Key", placeholder: "sk-or-...", type: "password", required: true },
      { key: "OPENROUTER_MODEL", label: "Model", placeholder: "openai/gpt-4o", type: "text", required: false },
    ],
  },
];

export const ENSEMBLE_STRATEGIES = [
  { value: "voting", label: "Voting — majority wins" },
  { value: "first-wins", label: "First-wins — fastest response" },
  { value: "merge", label: "Merge — combine all outputs" },
] as const;

export type EnsembleStrategy = typeof ENSEMBLE_STRATEGIES[number]["value"];
