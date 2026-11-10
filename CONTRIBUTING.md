# How we work (32 hours, no exceptions)

1. `main` always runs. The demo is shown from `main`.
2. Short-lived branches: `feat/<name>-<topic>` or `fix/<name>-<topic>`.
3. Merge small, at least every 1–2 hours. The tech lead merges or approves.
4. Run `pytest` before you merge.
5. One owner per file. Agree on the API contract (`docs/API_CONTRACT.md`) first, then work in parallel.
6. Never commit `.env` or real data. `.env.example` only.
7. Feature freeze on **12 Nov, 12:00**. After that: bug fixes only.
8. Stuck for 30 minutes? Ask the team, then a mentor.

```bash
git switch main && git pull
git switch -c feat/<name>-<topic>
# ... work ...
git add -A && git commit -m "feat: <what>"
git push -u origin feat/<name>-<topic>   # open a PR, tech lead merges
```
