# Switching & Upgrading Models (`docs/upgrading-models.md`)

Pixel Corp is designed to be **provider and model agnostic**. Switching from Groq free tier models to OpenAI, Anthropic, or local models requires editing `config/models.yaml` — **zero code changes**.

## 1. Switching Providers

In `config/models.yaml`:
```yaml
default_provider: groq  # or 'openai', 'ollama', 'mock'

providers:
  groq:
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
  openai:
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
  local:
    base_url: http://localhost:11434/v1
    api_key_env: OLLAMA_API_KEY
```

## 2. Upgrading Model Tiers

Map the tiers (`fast`, `smart`, `premium`) to your target models:
```yaml
tiers:
  fast:
    provider: groq
    model: llama-3.1-8b-instant
    fallbacks:
      - llama-3.3-70b-versatile
  smart:
    provider: groq
    model: llama-3.3-70b-versatile
    fallbacks:
      - llama-3.1-8b-instant
  premium:
    provider: groq
    model: llama-3.3-70b-versatile
    fallbacks:
      - llama-3.1-8b-instant
```

## 3. Rate Limit Configuration

Set rate limits (RPM, TPM, RPD, TPD) in `limits`:
```yaml
limits:
  llama-3.1-8b-instant:
    rpm: 30
    tpm: 6000
    rpd: 1000
    tpd: 100000
  gpt-4o:
    rpm: 500
    tpm: 150000
    rpd: 100000
    tpd: 10000000
```
The central rate limiter automatically enforces RPM, TPM, and persists daily usage in SQLite so process restarts preserve quota accounting.
