# UEFA Extra UCL Spot Simulator

Simulate remaining UEFA club-competition matches (UCL / UEL / UECL) and see how association coefficients change for the current season. Intended to simulate which two associations would earn the extra Champions League direct qualification spot ("performance spots").

Available in https://uefa-ucl-extra-spot-simulator.onrender.com/ - if not opened recently, becomes idle (as it's free tier in Render), hence start might be slow.

## Run locally

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.

```bash
python tests/test_engine.py
```
## Sources

- UEFA regulations (Annex D: Coefficient Ranking System): https://documents.uefa.com/r/Regulations-of-the-UEFA-Champions-League-2025/26/Annex-D-Coefficient-Ranking-System-Online
- Wikipedia (match/standings pages used by `backend/scraper.py`):
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_qualifying
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_league_phase
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_knockout_phase
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Europa_League_qualifying
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Europa_League_league_phase
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Europa_League_knockout_phase
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Conference_League_qualifying
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Conference_League_league_phase
  - https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Conference_League_knockout_phase

## Notes

- Built with Codex and Claude Code.
- Development-only prompt/spec files and local reference materials (e.g. `CLAUDE.md`, `.claude/`, cached scrape output, PDFs) are intentionally not committed.
- The repo includes a `data/results_snapshot.json` dataset which includes all the relevant results for computing the association coefficient and is based on Wikipedia. You can refresh locally by running `python backend/scraper.py` (writes `data/results_cache.json`).
