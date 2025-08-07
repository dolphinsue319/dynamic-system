# API Key Security Guide

## Overview
Since this is a personal project, the main security concern is preventing API key leakage. This guide covers how API keys are handled securely in the codebase.

## Security Measures Implemented

### 1. Environment Variable Loading
- API keys are **never hardcoded** in the source code
- Keys are loaded from environment variables or `.env` file
- The `.env` file is **gitignored** to prevent accidental commits

### 2. Secure Key Handling
```python
# src/utils/env_loader.py
- Loads API keys from environment variables
- Never logs actual API keys
- Provides masked key display (first 4...last 4 characters only)
```

### 3. Key Masking in Logs
When API keys are referenced in logs, they appear as:
```
OpenAI client initialized with key: sk-1234...abcd
Google Gemini client initialized with key: AIza...wxyz
```

### 4. Configuration Files
- `.env.example` contains placeholder keys
- Actual `.env` file is never committed to git
- Configuration files use environment variable references

## Setup Instructions

1. **Create your `.env` file:**
```bash
cp .env.example .env
```

2. **Add your API keys to `.env`:**
```env
OPENAI_API_KEY=your-actual-openai-key
GOOGLE_API_KEY=your-actual-google-key
ANTHROPIC_API_KEY=your-actual-anthropic-key
```

3. **Verify `.env` is gitignored:**
```bash
git status  # Should not show .env file
```

## Best Practices

### DO:
✅ Store API keys in `.env` file or environment variables  
✅ Use the `EnvLoader` class to access keys  
✅ Keep `.env` file in `.gitignore`  
✅ Rotate keys periodically  
✅ Use different keys for dev/prod if needed  

### DON'T:
❌ Never hardcode API keys in source code  
❌ Never commit `.env` file to git  
❌ Never log full API keys  
❌ Never share your `.env` file  

## Verification

To verify your API keys are configured correctly:

```python
from src.utils.env_loader import EnvLoader

env_loader = EnvLoader()
status = env_loader.validate_api_keys()
print(status)
# Output: {'openai': True, 'google': True, 'anthropic': True}
```

## If a Key is Leaked

If you accidentally expose an API key:

1. **Immediately rotate the key** in your provider's dashboard:
   - OpenAI: https://platform.openai.com/api-keys
   - Google: https://console.cloud.google.com/apis/credentials
   - Anthropic: https://console.anthropic.com/settings/keys

2. **Update your `.env` file** with the new key

3. **Check git history** for any committed keys:
```bash
git log -p | grep -E "(sk-|AIza|anthropic)"
```

4. **If found in history**, consider rewriting git history or making the repo private

## Environment Variable Priority

The system loads keys in this order:
1. System environment variables (highest priority)
2. `.env` file in project root
3. Default values (none for API keys)

## Docker/Podman Security

When using containers:
```bash
# Pass API keys as environment variables
podman run -e OPENAI_API_KEY=$OPENAI_API_KEY dynamic-orchestrator

# Or use env file
podman run --env-file .env dynamic-orchestrator
```

Never bake API keys into container images!

## Summary

The implemented `EnvLoader` class provides:
- ✅ Secure loading from environment
- ✅ Key masking for safe logging  
- ✅ Validation of key availability
- ✅ No hardcoded secrets
- ✅ Git-safe configuration

This approach ensures your API keys remain secure while maintaining ease of use for a personal project.