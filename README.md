# Chess Opening Trainer

A PySide6 desktop app for drilling chess openings against the Lichess opening explorer, with optional Maia bot opponents and post-game accuracy review.

## Full disclosure

**This was written almost entirely by AI (Claude Code), driven by me as a non-programmer.** I had the idea and iterated on it, but I didn't write the code line-by-line and I don't have the background to debug or extend it confidently.

**It's a little buggy.** I'm putting it up because I think the *idea* is good enough that someone with more knowledge might want to take it further — fix the rough edges, restructure it properly, or use it as a starting point for something better. Issues and PRs welcome, but please don't expect me to be much help on the implementation side.

## What it does

- **Drill mode** — pick an opening from the Lichess explorer (or your saved repertoire), play it out against an opponent, and get a post-drill review of inaccuracies/blunders.
- **Opening selection** — searchable combo box, top-5 popular lines, or random play.
- **Opponent modes** — most-popular book move, weighted random, or one of several Maia bot strengths (uses the Lichess player explorer API).
- **Auto-restart rules** — drill resets if accuracy drops below threshold or you string together inaccuracies.
- **Move-level feedback** — eval-bar threshold (±1–2 pawn shift fails the move), inaccuracy/blunder classification, and a review screen showing where you went wrong with the correct move.
- **Responsive board** — SVG board scales to window size with aspect ratio preserved.

## Requirements

- Python 3.10+
- PySide6
- python-chess
- requests
- A Lichess OAuth token in the `LICHESS_TOKEN` environment variable (the `/lichess` and `/masters` explorer endpoints require auth; `/player` is open but the app uses all three).

Create a token at https://lichess.org/account/oauth/token (no scopes needed for read-only explorer access).

```bash
pip install PySide6 python-chess requests
```

## Run

```bash
python chess_trainer_gui.py
```

`chess_trainer.py` is the earlier CLI prototype, kept for reference.

`repertoire.json` is my personal opening repertoire — replace it with your own.

## Known rough edges

- No tests.
- Single-file GUI (~73 KB) — would benefit from being split up.
- Error handling around the Lichess API is minimal; rate limits and network hiccups can produce weird states.
- State management between drill restarts, line scripts, and Maia fetches is fiddly and probably has races I haven't found.
- No packaging — run it from source.

## License

MIT — do whatever you want with it.
