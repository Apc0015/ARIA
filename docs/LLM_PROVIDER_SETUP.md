# ARIA LLM Provider Setup Guide

**Simplified Configuration:**  
Cloud: OpenRouter, OpenAI, Anthropic  
Local: Ollama  
Model Selection: Users choose 1 or multiple

---

## Quick Start

### Option 1: OpenRouter (Recommended - Default)
```bash
# Set in .env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4.5-turbo
```

**Why OpenRouter?**
- Meta-provider: Access 50+ models (OpenAI, Anthropic, open-source, etc.)
- Single API, multiple model options
- Easy to switch models

---

### Option 2: OpenAI Direct
```bash
# Set in .env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
```

**Available Models:**
- `gpt-4o` — Latest, balanced
- `gpt-4o-mini` — Fast, cheap
- `gpt-4-turbo` — Powerful

---

### Option 3: Anthropic Direct
```bash
# Set in .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
```

**Available Models:**
- `claude-3-5-sonnet-latest` — Latest Claude
- `claude-3-5-haiku-latest` — Fast, cheap
- `claude-3-opus-latest` — Powerful

---

### Option 4: Ollama (Local, Free)
```bash
# No API key needed!
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

**Setup:**
```bash
# Install Ollama from https://ollama.ai
# Run Ollama server
ollama serve

# In another terminal, pull a model
ollama pull llama3.1:8b
```

**Available Models:**
- `llama3.1:8b` — Efficient, balanced
- `llama3.1:70b` — Powerful
- `mistral:latest` — Fast
- `neural-chat:latest` — Optimized

---

## Multi-Model Ensemble (Optional)

Use multiple models in parallel for comparison:

```bash
# .env
LLM_ENSEMBLE_ENABLED=true

# ARIA will query all enabled models:
# Define multiple providers in your mission YAML or code
```

### Example: Using 3 Different Models
```python
from aria.sources.llm import LLMEnsembleCollector

ensemble = LLMEnsembleCollector(
    models=[
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet-latest"),
        ("ollama", "llama3.1:8b"),
    ]
)

# Query all 3 models, get 3 different perspectives
async for response in ensemble.collect(queries):
    print(f"Model: {response['model']}")
    print(f"Answer: {response['text']}")
```

---

## Environment Variables Summary

```env
# Choose provider
LLM_PROVIDER=openrouter|openai|anthropic|ollama

# API Keys (only for selected provider)
OPENROUTER_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
# OLLAMA: No API key needed

# Model selection
OPENROUTER_MODEL=openai/gpt-4.5-turbo
OPENAI_MODEL=gpt-4o
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
OLLAMA_MODEL=llama3.1:8b

# Optional: Ensemble mode
LLM_ENSEMBLE_ENABLED=false

# Quality parameters
LLM_TEMPERATURE=0.1          # Lower = more consistent
LLM_MAX_TOKENS=2000          # Response length
```

---

## Comparison: Which Provider to Choose?

| Provider | Cost | Speed | Local | Quality | Best For |
|----------|------|-------|-------|---------|----------|
| **OpenRouter** | $ | Fast | No | Excellent | Flexibility, trying models |
| **OpenAI** | $$ | Fast | No | Excellent | GPT-4 specifically |
| **Anthropic** | $$ | Medium | No | Excellent | Claude specifically |
| **Ollama** | Free | Slow | Yes | Good | Testing, offline, budget |

---

## Real-World Scenarios

### Scenario 1: Production, Cost-Optimized
```env
LLM_PROVIDER=openrouter
OPENROUTER_MODEL=openai/gpt-4o-mini  # Fast, cheap
LLM_TEMPERATURE=0.1                   # Consistent
```

### Scenario 2: Production, High Quality
```env
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o                   # Best quality
LLM_TEMPERATURE=0.1                   # Consistent
```

### Scenario 3: Research, Multiple Perspectives
```env
LLM_ENSEMBLE_ENABLED=true
# Query: OpenAI + Anthropic + Ollama in parallel
# Get different perspectives on same question
```

### Scenario 4: Local Testing (Free)
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b              # Free, local
# No API keys needed
```

---

## Common Tasks

### Switch Providers
Edit `.env` and change `LLM_PROVIDER`:
```bash
LLM_PROVIDER=anthropic  # Switch to Anthropic
```
Restart ARIA and it uses new provider.

### Test Multiple Models
```env
LLM_ENSEMBLE_ENABLED=true
# ARIA adds responses from all configured models to research
```

### Use Different Model for Specific Task
```python
from aria.config_llm import LLMConfig, LLMProvider, ModelsByProvider

# Temporarily override
config = LLMConfig(
    provider=LLMProvider.OPENAI,
    model="gpt-4o",  # Override default
)
```

---

## What Was Removed

**Simplified from 7 providers to 4:**
- ❌ Removed: Mistral, Google, Together AI (redundant with OpenRouter)
- ✅ Kept: OpenRouter, OpenAI, Anthropic, Ollama

**Why?**
- OpenRouter provides access to all those models anyway
- Simpler configuration for users
- Reduces dependency bloat
- Easier to maintain

---

## Next Steps

1. **Choose a provider** (recommend: OpenRouter for flexibility)
2. **Get API key** (skip if using Ollama)
3. **Update `.env`** with your configuration
4. **Run ARIA**:
   ```bash
   python -m aria.cli --serve-api
   ```

---

**Status:** ✅ Simplified, production-ready LLM configuration
