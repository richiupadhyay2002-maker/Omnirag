# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Email **richiupadhyay2002@gmail.com** with:

- what you found and which version/commit it affects,
- steps to reproduce (proof-of-concept welcome),
- the impact you think it has.

I will acknowledge your report, investigate, and keep you updated until it is
fixed. Thank you for helping keep OmniRAG and its users safe.

## Please never commit

- `.env` files or any real API keys, tokens, passwords, or connection strings
  (`GROQ_API_KEY`, etc.). Copy `backend/.env.example` to `backend/.env` and
  keep real values local only.
- Uploaded user files (`backend/data/`, `uploads/`, `data/`, `storage/`).
- Vector-store / database files (`backend/data/`, `*.sqlite3`, `*.db`).
- Eval outputs that may contain private document text
  (`backend/eval/results.json`).
- IDE files with personal paths (`.vscode/settings.json`).
- Build / dependency dirs (`venv/`, `node_modules/`, `dist/`, `build/`).

These paths are gitignored. If you accidentally stage one, unstage it and tell
the maintainer before pushing.

## Notes for contributors

- Defaults are local-only (Ollama + ChromaDB). The optional Groq fallback
  (`LLM_PROVIDER=groq`) sends prompts to a third-party API — enable it only
  deliberately and never commit the key.
- Keep `.env.example` files placeholder-only (`GROQ_API_KEY=your_key_here`).
- Enable GitHub secret scanning + push protection in
  Settings → Code security if you fork this repo.
