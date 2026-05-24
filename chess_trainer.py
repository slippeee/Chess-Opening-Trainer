import json
import random
import sys
from pathlib import Path

import chess
import requests

PARAMS = {
    "api_url": "https://explorer.lichess.ovh/lichess",
    "variant": "standard",
    "speeds": ["blitz", "rapid", "classical"],
    "ratings": [1600, 1800, 2000, 2200],
    "moves": 10,
    "timeout": 10,
    "repertoire_path": "repertoire.json",
}


def query_lichess(board: chess.Board) -> dict | None:
    params = {
        "variant": PARAMS["variant"],
        "fen": board.fen(),
        "speeds": ",".join(PARAMS["speeds"]),
        "ratings": ",".join(str(r) for r in PARAMS["ratings"]),
        "moves": PARAMS["moves"],
    }
    try:
        r = requests.get(PARAMS["api_url"], params=params, timeout=PARAMS["timeout"])
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"  ! API error: {e}")
        return None


def format_move_stats(data: dict, board: chess.Board) -> str:
    moves = data.get("moves", [])
    total_pos = sum(m["white"] + m["draws"] + m["black"] for m in moves) or 1
    lines = []
    header = f"{'SAN':<8}{'Played':>9}{'  W%':>6}{'  D%':>6}{'  L%':>6}{'Games':>10}"
    lines.append(header)
    lines.append("-" * len(header))
    for m in moves:
        try:
            san = board.san(chess.Move.from_uci(m["uci"]))
        except (ValueError, AssertionError):
            san = m.get("san", m["uci"])
        w, d, l = m["white"], m["draws"], m["black"]
        total = w + d + l
        if total == 0:
            continue
        played_pct = 100.0 * total / total_pos
        wpct = 100.0 * w / total
        dpct = 100.0 * d / total
        lpct = 100.0 * l / total
        lines.append(
            f"{san:<8}{played_pct:>8.1f}%{wpct:>5.1f}%{dpct:>5.1f}%{lpct:>5.1f}%{total:>10}"
        )
    return "\n".join(lines)


def pick_weighted_reply(data: dict) -> str | None:
    moves = [m for m in data.get("moves", []) if (m["white"] + m["draws"] + m["black"]) > 0]
    if not moves:
        return None
    weights = [m["white"] + m["draws"] + m["black"] for m in moves]
    chosen = random.choices(moves, weights=weights, k=1)[0]
    return chosen["uci"]


def load_repertoire() -> dict:
    p = Path(PARAMS["repertoire_path"])
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  ! Could not load repertoire: {e}")
        return {}


def save_repertoire(rep: dict) -> None:
    try:
        Path(PARAMS["repertoire_path"]).write_text(
            json.dumps(rep, indent=2), encoding="utf-8"
        )
    except OSError as e:
        print(f"  ! Could not save repertoire: {e}")


def print_board(board: chess.Board) -> None:
    print()
    print(board.unicode(borders=True, empty_square="·"))
    print(f"FEN: {board.fen()}")
    print(f"To move: {'White' if board.turn == chess.WHITE else 'Black'}")


def show_opening(data: dict | None) -> None:
    if not data:
        return
    op = data.get("opening")
    if op:
        eco = op.get("eco", "")
        name = op.get("name", "")
        print(f"Opening: {eco} {name}".strip())


def explore_mode() -> None:
    board = chess.Board()
    history: list[chess.Move] = []
    print("\n=== Explore mode ===")
    print("Type SAN moves (e4, Nf3). Commands: back, reset, quit\n")

    while True:
        print_board(board)
        data = query_lichess(board)
        show_opening(data)
        if data and data.get("moves"):
            print(format_move_stats(data, board))
        elif data is not None:
            print("(no games in database for this position)")

        if board.is_game_over():
            print(f"\nGame over: {board.result()} ({board.outcome().termination.name if board.outcome() else ''})")
            print("Resetting line.\n")
            board.reset()
            history.clear()
            continue

        cmd = input("\n> ").strip()
        if not cmd:
            continue
        low = cmd.lower()
        if low in ("quit", "q", "exit"):
            return
        if low == "reset":
            board.reset()
            history.clear()
            continue
        if low == "back":
            if history:
                history.pop()
                board.reset()
                for mv in history:
                    board.push(mv)
            else:
                print("  ! Nothing to undo.")
            continue
        try:
            move = board.parse_san(cmd)
        except ValueError:
            print("  ! Illegal or unrecognized move. Use SAN like e4, Nf3, O-O.")
            continue
        board.push(move)
        history.append(move)


def drill_mode() -> None:
    rep = load_repertoire()
    print("\n=== Drill mode ===")
    side_in = input("Drill as (w)hite or (b)lack? ").strip().lower()
    user_side = chess.BLACK if side_in.startswith("b") else chess.WHITE
    side_name = "White" if user_side == chess.WHITE else "Black"
    print(f"You will play as {side_name}.")
    print("Commands: hint, reset, quit\n")

    board = chess.Board()

    while True:
        print_board(board)

        if board.is_game_over():
            print(f"\nGame over: {board.result()}. Resetting line.\n")
            board.reset()
            continue

        if board.turn != user_side:
            data = query_lichess(board)
            uci = pick_weighted_reply(data) if data else None
            if uci is None:
                print("  ! No opponent reply available (out of book). Resetting line.\n")
                save_repertoire(rep)
                board.reset()
                continue
            try:
                mv = chess.Move.from_uci(uci)
                san = board.san(mv)
                board.push(mv)
                print(f"Opponent plays: {san}")
            except (ValueError, AssertionError) as e:
                print(f"  ! Could not apply opponent move {uci}: {e}. Resetting line.\n")
                board.reset()
            continue

        fen = board.fen()
        saved = rep.get(fen)

        cmd = input("\nYour move > ").strip()
        if not cmd:
            continue
        low = cmd.lower()
        if low in ("quit", "q", "exit"):
            save_repertoire(rep)
            return
        if low == "reset":
            board.reset()
            continue
        if low == "hint":
            if saved:
                print(f"  Repertoire move: {saved}")
            else:
                data = query_lichess(board)
                if data and data.get("moves"):
                    print(format_move_stats(data, board))
                else:
                    print("  ! No hint available.")
            continue

        try:
            move = board.parse_san(cmd)
        except ValueError:
            print("  ! Illegal or unrecognized move. Use SAN like e4, Nf3, O-O.")
            continue

        played_san = board.san(move)

        if saved is None:
            rep[fen] = played_san
            save_repertoire(rep)
            print(f"  + Saved {played_san} as your repertoire move for this position.")
            board.push(move)
        else:
            if played_san == saved:
                print(f"  ✓ Correct: {played_san}")
                board.push(move)
            else:
                print(f"  ✗ Wrong. Expected {saved}, you played {played_san}. Try again.")


def main() -> None:
    print("Chess Opening Trainer")
    print("---------------------")
    while True:
        print("\n[1] Explore mode")
        print("[2] Drill mode")
        print("[q] Quit")
        choice = input("> ").strip().lower()
        if choice == "1":
            explore_mode()
        elif choice == "2":
            drill_mode()
        elif choice in ("q", "quit", "exit"):
            print("Bye.")
            return
        else:
            print("  ! Unknown option.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Bye.")
        sys.exit(0)
