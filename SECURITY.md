# Security Notes

- Do not commit `.env` or real API tokens.
- Runtime token input is kept in browser memory only and is sent per request.
- Sanitized logs preserve model name, timing, usage, request mode, score summaries, and reflection.
- Raw F12 feedback files are intentionally excluded from this GitHub package.
- Before publishing, run:

```powershell
rg -n "sk-[A-Za-z0-9_-]{20,}|DEEPSEEK_API_KEY\\s*=\\s*[^\\s#]+|Authorization: Bearer|Bearer\\s+sk-" -S .
```

