# How we work (32 hours, no exceptions)

1. `main` always runs. The demo is shown from `main`.
2. Short-lived branches: `feat/<name>-<topic>` or `fix/<name>-<topic>`.
3. Merge small, at least every 1–2 hours. The tech lead merges or approves.
4. Run `pytest` and `streamlit run app/Home.py` before you merge.
5. One owner per module (C1 data · C2 engine · C3 app · C4 AI/report, see `docs/TEAM.md`). Contracts live in `docs/API_CONTRACT.md`. Change them only after telling the consumers.
6. Never commit `.env` or real data. `.env.example` only.
7. Feature freeze on **12 Nov, 11:00** (backup video 12:00, demo submission 13:30). After that: bug fixes only.
8. Stuck for 30 minutes? Ask the team, then a mentor.

```bash
git switch main && git pull
git switch -c feat/<name>-<topic>
# ... work ...
git add -A && git commit -m "feat: <what>"
git push -u origin feat/<name>-<topic>   # open a PR, tech lead merges
```
