"""Chess opening trainer GUI - PySide6 + Lichess explorer API."""
import json
import os
import random
import sys
import threading
from pathlib import Path
from typing import Optional

import chess
import chess.svg
import chess.pgn
import requests

from PySide6.QtCore import Qt, QObject, Signal, Slot, QByteArray, QTimer, QSize
from PySide6.QtGui import QColor, QPainter, QFont, QPalette
from PySide6.QtWidgets import QCompleter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QComboBox, QCheckBox,
    QMessageBox, QFileDialog, QDialog, QFrame, QScrollArea, QGroupBox,
    QRadioButton, QButtonGroup, QTextBrowser, QSizePolicy,
)

PARAMS = {
    "api_url": "https://explorer.lichess.ovh/lichess",
    "variant": "standard",
    "speeds": ["blitz", "rapid", "classical"],
    "ratings": [1600, 1800, 2000, 2200],
    "moves": 10,
    "timeout": 10,
    "repertoire_path": "repertoire.json",
    "board_size": 560,
    "opponent_delay_ms": 350,
}

OPENING_LINES = {
    "(none — standard start)": "",
    "1.e4": "e4",
    "1.d4": "d4",
    "1.c4 (English)": "c4",
    "1.Nf3 (Réti)": "Nf3",
    "Italian Game": "e4 e5 Nf3 Nc6 Bc4",
    "Italian: Giuoco Pianissimo": "e4 e5 Nf3 Nc6 Bc4 Bc5 d3",
    "Italian: Evans Gambit": "e4 e5 Nf3 Nc6 Bc4 Bc5 b4",
    "Ruy Lopez (Spanish)": "e4 e5 Nf3 Nc6 Bb5",
    "Ruy Lopez: Berlin": "e4 e5 Nf3 Nc6 Bb5 Nf6",
    "Ruy Lopez: Closed Main": "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3",
    "Scotch Game": "e4 e5 Nf3 Nc6 d4",
    "King's Gambit": "e4 e5 f4",
    "Petrov's Defense": "e4 e5 Nf3 Nf6",
    "Philidor Defense": "e4 e5 Nf3 d6",
    "Sicilian Defense": "e4 c5",
    "Sicilian: Najdorf": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6",
    "Sicilian: Dragon": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6",
    "Sicilian: Sveshnikov": "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 e5",
    "Sicilian: Accelerated Dragon": "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 g6",
    "Sicilian: Taimanov": "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6",
    "Sicilian: Kan": "e4 c5 Nf3 e6 d4 cxd4 Nxd4 a6",
    "Sicilian: Alapin (c3)": "e4 c5 c3",
    "Sicilian: Closed": "e4 c5 Nc3",
    "French Defense": "e4 e6",
    "French: Winawer": "e4 e6 d4 d5 Nc3 Bb4",
    "French: Classical": "e4 e6 d4 d5 Nc3 Nf6",
    "French: Advance": "e4 e6 d4 d5 e5",
    "French: Tarrasch": "e4 e6 d4 d5 Nd2",
    "Caro-Kann": "e4 c6",
    "Caro-Kann: Classical": "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5",
    "Caro-Kann: Advance": "e4 c6 d4 d5 e5",
    "Pirc Defense": "e4 d6 d4 Nf6 Nc3 g6",
    "Modern Defense": "e4 g6",
    "Alekhine's Defense": "e4 Nf6",
    "Scandinavian": "e4 d5",
    "Queen's Gambit": "d4 d5 c4",
    "QG Accepted": "d4 d5 c4 dxc4",
    "QG Declined": "d4 d5 c4 e6",
    "Slav Defense": "d4 d5 c4 c6",
    "Semi-Slav": "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6",
    "London System": "d4 d5 Nf3 Nf6 Bf4",
    "Trompowsky Attack": "d4 Nf6 Bg5",
    "Nimzo-Indian": "d4 Nf6 c4 e6 Nc3 Bb4",
    "Queen's Indian": "d4 Nf6 c4 e6 Nf3 b6",
    "King's Indian": "d4 Nf6 c4 g6 Nc3 Bg7",
    "Grünfeld": "d4 Nf6 c4 g6 Nc3 d5",
    "Catalan": "d4 Nf6 c4 e6 g3",
    "Benoni": "d4 Nf6 c4 c5 d5 e6",
    "Dutch Defense": "d4 f5",
    "English: Symmetrical": "c4 c5",
    "King's Indian Attack": "Nf3 d5 g3",
}

OPPONENT_MODES = [
    "Weighted (real games)", "Most popular", "Random uniform",
    "Maia 1100", "Maia 1500", "Maia 1900",
]

MAIA_USERS = {
    "Maia 1100": "maia1",
    "Maia 1500": "maia5",
    "Maia 1900": "maia9",
}


def load_repertoire() -> dict:
    p = Path(PARAMS["repertoire_path"])
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_repertoire(rep: dict) -> None:
    try:
        Path(PARAMS["repertoire_path"]).write_text(
            json.dumps(rep, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def pick_opponent_move(data: dict, mode: str) -> Optional[str]:
    moves = [m for m in data.get("moves", []) if (m["white"] + m["draws"] + m["black"]) > 0]
    if not moves:
        return None
    if mode == "Most popular" or mode in MAIA_USERS:
        moves.sort(key=lambda m: -(m["white"] + m["draws"] + m["black"]))
        return moves[0]["uci"]
    if mode == "Random uniform":
        return random.choice(moves)["uci"]
    weights = [m["white"] + m["draws"] + m["black"] for m in moves]
    return random.choices(moves, weights=weights, k=1)[0]["uci"]


class LichessFetcher(QObject):
    """Background fetcher. dataReady is queued back to GUI thread automatically."""
    dataReady = Signal(str, object)        # fen, dict (empty dict on API failure)
    playerDataReady = Signal(str, str, object)  # fen, player, dict
    linesReady = Signal(str, object)       # opening_key, list[{"san": str, "moves": [uci]}]

    def fetch(self, fen: str) -> None:
        threading.Thread(target=self._do_fetch, args=(fen,), daemon=True).start()

    def fetch_player(self, fen: str, player: str, color: str) -> None:
        threading.Thread(
            target=self._do_fetch_player, args=(fen, player, color), daemon=True
        ).start()

    def _do_fetch_player(self, fen: str, player: str, color: str) -> None:
        params = {
            "variant": PARAMS["variant"],
            "fen": fen,
            "player": player,
            "color": color,
            "speeds": ",".join(PARAMS["speeds"]),
            "modes": "rated,casual",
            "moves": PARAMS["moves"],
        }
        headers = {"User-Agent": "chess_trainer_gui/1.0"}
        token = os.environ.get("LICHESS_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = requests.get(
                "https://explorer.lichess.ovh/player",
                params=params, headers=headers, stream=True,
                timeout=PARAMS["timeout"],
            )
            r.raise_for_status()
            last_line = None
            for raw in r.iter_lines():
                if raw:
                    last_line = raw
            data = json.loads(last_line) if last_line else {"moves": []}
        except requests.RequestException as e:
            print(f"[API] player request failed: {e!r}", file=sys.stderr)
            data = {"moves": [], "_error": True, "_error_msg": f"{type(e).__name__}: {e}"}
        except (ValueError, TypeError) as e:
            print(f"[API] bad player JSON: {e!r}", file=sys.stderr)
            data = {"moves": [], "_error": True, "_error_msg": f"Bad JSON: {e}"}
        self.playerDataReady.emit(fen, player, data)

    def _do_fetch(self, fen: str) -> None:
        params = {
            "variant": PARAMS["variant"],
            "fen": fen,
            "speeds": ",".join(PARAMS["speeds"]),
            "ratings": ",".join(str(r) for r in PARAMS["ratings"]),
            "moves": PARAMS["moves"],
        }
        headers = {"User-Agent": "chess_trainer_gui/1.0"}
        token = os.environ.get("LICHESS_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = requests.get(
                PARAMS["api_url"], params=params, headers=headers,
                timeout=PARAMS["timeout"],
            )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            print(f"[API] request failed: {e!r}", file=sys.stderr)
            data = {"moves": [], "_error": True, "_error_msg": f"{type(e).__name__}: {e}"}
        except ValueError as e:
            print(f"[API] bad JSON: {e!r}", file=sys.stderr)
            data = {"moves": [], "_error": True, "_error_msg": f"Bad JSON: {e}"}
        self.dataReady.emit(fen, data)

    def fetch_top_lines(self, opening_key: str, start_board: chess.Board, depth: int = 6) -> None:
        threading.Thread(
            target=self._do_fetch_top_lines,
            args=(opening_key, start_board.copy(), depth),
            daemon=True,
        ).start()

    def _explorer_query(self, fen: str) -> dict:
        params = {
            "variant": PARAMS["variant"],
            "fen": fen,
            "speeds": ",".join(PARAMS["speeds"]),
            "ratings": ",".join(str(r) for r in PARAMS["ratings"]),
            "moves": 8,
        }
        headers = {"User-Agent": "chess_trainer_gui/1.0"}
        token = os.environ.get("LICHESS_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = requests.get(
                PARAMS["api_url"], params=params, headers=headers,
                timeout=PARAMS["timeout"],
            )
            r.raise_for_status()
            return r.json() or {"moves": []}
        except (requests.RequestException, ValueError) as e:
            print(f"[API] top-lines fetch failed: {e!r}", file=sys.stderr)
            return {"moves": []}

    def _do_fetch_top_lines(self, opening_key: str, start_board: chess.Board, depth: int) -> None:
        data = self._explorer_query(start_board.fen())
        moves = data.get("moves") or []
        def pop(m):
            return (m.get("white") or 0) + (m.get("draws") or 0) + (m.get("black") or 0)
        moves.sort(key=pop, reverse=True)
        top5 = moves[:5]
        lines = []
        for entry in top5:
            board = start_board.copy()
            uci_seq = []
            san_seq = []
            try:
                mv = chess.Move.from_uci(entry["uci"])
                if mv not in board.legal_moves:
                    continue
                san_seq.append(board.san(mv))
                board.push(mv)
                uci_seq.append(entry["uci"])
            except (KeyError, ValueError):
                continue
            for _ in range(depth - 1):
                d = self._explorer_query(board.fen())
                sub_moves = d.get("moves") or []
                if not sub_moves:
                    break
                sub_moves.sort(key=pop, reverse=True)
                best = sub_moves[0]
                try:
                    mv = chess.Move.from_uci(best["uci"])
                    if mv not in board.legal_moves:
                        break
                    san_seq.append(board.san(mv))
                    board.push(mv)
                    uci_seq.append(best["uci"])
                except (KeyError, ValueError):
                    break
            if uci_seq:
                lines.append({"san": " ".join(san_seq), "moves": uci_seq})
        self.linesReady.emit(opening_key, lines)


class BoardWidget(QSvgWidget):
    moveMade = Signal(object)

    # python-chess svg: SQUARE_SIZE=45, MARGIN=20 when coordinates=True -> total 400, margin ratio 5%
    MARGIN_RATIO = 20 / 400

    def __init__(self):
        super().__init__()
        self.size_px = PARAMS["board_size"]
        self.setMinimumSize(320, 320)
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        self.board = chess.Board()
        self.orientation = chess.WHITE
        self.selected: Optional[int] = None
        self.last_move: Optional[chess.Move] = None
        self.arrows: list = []
        self.hint_move: Optional[chess.Move] = None
        self.locked = False
        self._press_sq: Optional[int] = None
        self._sel_before_press: Optional[int] = None
        self.redraw()

    def set_position(self, board: chess.Board, last_move: Optional[chess.Move] = None):
        self.board = board.copy()
        self.last_move = last_move
        self.selected = None
        self.arrows = []
        self.hint_move = None
        self.redraw()

    def show_hint_arrow(self, move: chess.Move):
        self.hint_move = move
        self.redraw()

    def set_orientation(self, color):
        self.orientation = color
        self.redraw()

    def flip(self):
        self.orientation = not self.orientation
        self.redraw()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return w

    def sizeHint(self):
        return QSize(self.size_px, self.size_px)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_size = min(self.width(), self.height())
        if new_size != self.size_px and new_size > 0:
            self.size_px = new_size
            self.redraw()

    def redraw(self):
        fill = {}
        if self.selected is not None:
            fill[self.selected] = "#f6f669cc"
            for mv in self.board.legal_moves:
                if mv.from_square == self.selected:
                    fill[mv.to_square] = "#7fce7f80"
        arrows = list(self.arrows)
        if self.hint_move is not None:
            fill[self.hint_move.from_square] = "#dc143c99"
            fill[self.hint_move.to_square] = "#dc143cdd"
            arrows.append(chess.svg.Arrow(
                self.hint_move.from_square, self.hint_move.to_square, color="#dc143c"
            ))
        check_sq = None
        if self.board.is_check():
            check_sq = self.board.king(self.board.turn)
        svg = chess.svg.board(
            self.board,
            orientation=self.orientation,
            lastmove=self.last_move,
            check=check_sq,
            fill=fill,
            arrows=arrows,
            coordinates=True,
            size=self.size_px,
        )
        self.load(QByteArray(svg.encode("utf-8")))

    def square_from_pos(self, x: float, y: float):
        rendered = min(self.width(), self.height())
        offset_x = (self.width() - rendered) / 2
        offset_y = (self.height() - rendered) / 2
        x -= offset_x
        y -= offset_y
        margin = rendered * self.MARGIN_RATIO
        board_px = rendered - 2 * margin
        if not (margin <= x < margin + board_px and margin <= y < margin + board_px):
            return None
        sq_size = board_px / 8
        file = int((x - margin) // sq_size)
        rank_from_top = int((y - margin) // sq_size)
        rank = 7 - rank_from_top
        if self.orientation == chess.BLACK:
            file = 7 - file
            rank = 7 - rank
        return chess.square(file, rank)

    def mousePressEvent(self, event):
        if self.locked or event.button() != Qt.LeftButton:
            return
        sq = self.square_from_pos(event.position().x(), event.position().y())
        self._press_sq = sq
        self._sel_before_press = self.selected
        if sq is None:
            return

        if self.selected is None:
            piece = self.board.piece_at(sq)
            if piece and piece.color == self.board.turn:
                self.selected = sq
                self.redraw()
            return

        if sq == self.selected:
            # Defer deselect to release (so drag from selected square still works)
            return

        self._attempt_move(self.selected, sq)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        press_sq = self._press_sq
        prior = self._sel_before_press
        self._press_sq = None
        self._sel_before_press = None
        if press_sq is None:
            return
        release_sq = self.square_from_pos(event.position().x(), event.position().y())

        if release_sq is not None and release_sq != press_sq:
            piece = self.board.piece_at(press_sq)
            if piece and piece.color == self.board.turn:
                self._attempt_move(press_sq, release_sq)
            return

        # Click on already-selected square -> deselect
        if release_sq == press_sq and prior == press_sq and self.selected == press_sq:
            self.selected = None
            self.redraw()

    def _attempt_move(self, src: int, dst: int) -> None:
        if src == dst:
            return
        promo = None
        piece = self.board.piece_at(src)
        if piece and piece.piece_type == chess.PAWN:
            target_rank = chess.square_rank(dst)
            if (piece.color == chess.WHITE and target_rank == 7) or \
               (piece.color == chess.BLACK and target_rank == 0):
                if any(mv.from_square == src and mv.to_square == dst
                       for mv in self.board.legal_moves):
                    promo = self._ask_promotion()
                    if promo is None:
                        self.selected = None
                        self.redraw()
                        return

        move = chess.Move(src, dst, promotion=promo)
        if move in self.board.legal_moves:
            self.selected = None
            self.moveMade.emit(move)
        else:
            other = self.board.piece_at(dst)
            self.selected = dst if (other and other.color == self.board.turn) else None
            self.redraw()

    def _ask_promotion(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Promote to")
        layout = QHBoxLayout(dlg)
        chosen = {"piece": None}
        for pt, sym in [(chess.QUEEN, "Q"), (chess.ROOK, "R"),
                        (chess.BISHOP, "B"), (chess.KNIGHT, "N")]:
            btn = QPushButton(sym)
            btn.setFixedSize(60, 60)
            btn.setStyleSheet("font-size: 22px; font-weight: bold;")
            btn.clicked.connect(lambda _=False, p=pt: (chosen.__setitem__("piece", p), dlg.accept()))
            layout.addWidget(btn)
        dlg.exec()
        return chosen["piece"]


class WdlBar(QWidget):
    def __init__(self, w_pct, d_pct, l_pct):
        super().__init__()
        self.w_pct = w_pct
        self.d_pct = d_pct
        self.l_pct = l_pct

    def paintEvent(self, _event):
        p = QPainter(self)
        rect = self.rect()
        total = self.w_pct + self.d_pct + self.l_pct
        if total <= 0:
            return
        wp = rect.width() * self.w_pct / total
        dp = rect.width() * self.d_pct / total
        lp = rect.width() * self.l_pct / total
        x = rect.x()
        p.fillRect(int(x), rect.y(), int(wp), rect.height(), QColor("#e8e8e0"))
        p.fillRect(int(x + wp), rect.y(), int(dp), rect.height(), QColor("#8a8a8a"))
        p.fillRect(int(x + wp + dp), rect.y(), int(lp), rect.height(), QColor("#2a2a2a"))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)
        y_text = rect.y() + rect.height() - 5
        if wp > 24:
            p.setPen(QColor("#222"))
            p.drawText(int(rect.x() + wp / 2 - 12), y_text, f"{self.w_pct:.0f}%")
        if dp > 24:
            p.setPen(QColor("#fff"))
            p.drawText(int(rect.x() + wp + dp / 2 - 12), y_text, f"{self.d_pct:.0f}%")
        if lp > 24:
            p.setPen(QColor("#fff"))
            p.drawText(int(rect.x() + wp + dp + lp / 2 - 12), y_text, f"{self.l_pct:.0f}%")


class MoveStatRow(QFrame):
    clicked = Signal(str)

    def __init__(self, san, uci, played_pct, w_pct, d_pct, l_pct, total, hide_stats=False):
        super().__init__()
        self.uci = uci
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("MoveStatRow")
        self.setStyleSheet("""
            QFrame#MoveStatRow { background:#2c2c30; border:1px solid #3a3a3e; border-radius:4px; }
            QFrame#MoveStatRow:hover { background:#3a3a40; border-color:#5a5a60; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        san_lbl = QLabel(san)
        san_lbl.setStyleSheet("font-weight:bold; font-family:Consolas,monospace; color:#e8e8e8;")
        san_lbl.setFixedWidth(60)
        layout.addWidget(san_lbl)

        if hide_stats:
            layout.addStretch(1)
            return

        pct_lbl = QLabel(f"{played_pct:.1f}%")
        pct_lbl.setStyleSheet("color:#bbb; font-family:Consolas,monospace;")
        pct_lbl.setFixedWidth(50)
        layout.addWidget(pct_lbl)

        bar = WdlBar(w_pct, d_pct, l_pct)
        bar.setFixedHeight(20)
        layout.addWidget(bar, stretch=1)

        total_lbl = QLabel(f"{total:,}")
        total_lbl.setStyleSheet("color:#888; font-family:Consolas,monospace;")
        total_lbl.setFixedWidth(80)
        total_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(total_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.uci)


class DrillReviewDialog(QDialog):
    KIND_COLORS = {"error": "#ff5555", "blunder": "#ff5555", "inaccuracy": "#e8a13a"}
    KIND_LABEL = {"error": "wrong", "blunder": "blunder", "inaccuracy": "inaccuracy"}
    MINI_SIZE = 380

    def __init__(self, parent, header: str, history_moves: list,
                 drill_log: list, orientation=chess.WHITE):
        super().__init__(parent)
        self.setWindowTitle("Drill review")
        self.resize(980, 620)

        self.history = list(history_moves)
        self.orientation = orientation
        self.issues_by_ply: dict[int, list] = {}
        for ev in drill_log:
            self.issues_by_ply.setdefault(ev["ply"], []).append(ev)

        # Precompute board-before-each-move and SAN list
        self.positions: list[chess.Board] = []
        self.sans: list[str] = []
        tmp = chess.Board()
        for mv in history_moves:
            self.positions.append(tmp.copy())
            self.sans.append(tmp.san(mv))
            tmp.push(mv)
        self.final_board = tmp

        outer = QVBoxLayout(self)

        header_lbl = QLabel(header)
        header_lbl.setStyleSheet("font-weight:bold; padding:6px; color:#f6f6f6; font-size:13px;")
        header_lbl.setWordWrap(True)
        outer.addWidget(header_lbl)

        legend = QLabel(
            "<span style='color:#e8a13a;'>■ inaccuracy</span>&nbsp;&nbsp;"
            "<span style='color:#ff5555;'>■ blunder / wrong</span>&nbsp;&nbsp;"
            "<span style='color:#ccc;'>click any move to inspect it</span>"
        )
        legend.setStyleSheet("padding:2px 6px; font-size:11px;")
        outer.addWidget(legend)

        body = QHBoxLayout()

        self.browser = QTextBrowser()
        self.browser.setStyleSheet(
            "background:#1e1e22; color:#e8e8e8; font-family:Consolas,monospace; font-size:13px;"
        )
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor)
        self.browser.setHtml(self._build_html())
        body.addWidget(self.browser, stretch=2)

        right = QVBoxLayout()
        self.mini_board = QSvgWidget()
        self.mini_board.setFixedSize(self.MINI_SIZE, self.MINI_SIZE)
        right.addWidget(self.mini_board)

        self.info_lbl = QLabel("Click any move on the left to view it on the board.")
        self.info_lbl.setStyleSheet("padding:6px; color:#ccc; font-family:Consolas,monospace; font-size:12px;")
        self.info_lbl.setWordWrap(True)
        right.addWidget(self.info_lbl)
        right.addStretch(1)
        body.addLayout(right, stretch=1)

        outer.addLayout(body, stretch=1)

        btn = QPushButton("Restart drill")
        btn.clicked.connect(self.accept)
        outer.addWidget(btn)

        self._render_mini(self.final_board, [], {}, self.history[-1] if self.history else None)

    def _build_html(self):
        out = ["<html><body style='font-family:Consolas,monospace;'>"]
        n_pushed = len(self.sans)
        max_log_ply = max(self.issues_by_ply.keys()) if self.issues_by_ply else 0
        max_ply = max(n_pushed, max_log_ply)

        if max_ply == 0:
            out.append("<i>No moves played.</i>")
        else:
            placeholder = ("<a href='ply:{p}' style='text-decoration:none;'>"
                           "<span style='color:#ff5555; font-style:italic;'>(failed)</span></a>")
            for i in range(0, max_ply, 2):
                move_num = i // 2 + 1
                white_ply = i + 1
                black_ply = i + 2
                line = (f"<div style='padding:2px 0;'>"
                        f"<span style='color:#888;'>{move_num}.</span> ")
                if white_ply <= n_pushed:
                    line += self._color_san(self.sans[white_ply - 1],
                                            self.issues_by_ply.get(white_ply), white_ply)
                elif white_ply in self.issues_by_ply:
                    line += placeholder.format(p=white_ply)
                if black_ply <= n_pushed:
                    line += "&nbsp;&nbsp;" + self._color_san(
                        self.sans[black_ply - 1],
                        self.issues_by_ply.get(black_ply), black_ply
                    )
                elif black_ply in self.issues_by_ply:
                    line += "&nbsp;&nbsp;" + placeholder.format(p=black_ply)
                line += "</div>"
                out.append(line)

                for ply in (white_ply, black_ply):
                    for issue in self.issues_by_ply.get(ply, []):
                        color = self.KIND_COLORS.get(issue["kind"], "#bbb")
                        label = self.KIND_LABEL.get(issue["kind"], issue["kind"])
                        if issue["kind"] == "error":
                            text = (f"ply {ply} ({label}): you tried {issue['played']}, "
                                    f"expected {issue['better']}")
                        else:
                            text = (f"ply {ply} ({label}): you played {issue['played']}, "
                                    f"better was {issue['better']}")
                        out.append(
                            f"<div style='margin-left:28px; color:{color}; font-size:11px; padding:1px 0;'>"
                            f"└ {text}</div>"
                        )
        out.append("</body></html>")
        return "".join(out)

    def _color_san(self, san: str, ply_issues, ply: int):
        anchor_open = f"<a href='ply:{ply}' style='text-decoration:none;'>"
        anchor_close = "</a>"
        if not ply_issues:
            return f"{anchor_open}<span style='color:#dde;'>{san}</span>{anchor_close}"
        non_error = [i for i in ply_issues if i["kind"] != "error"]
        if non_error:
            color = self.KIND_COLORS[non_error[0]["kind"]]
            return f"{anchor_open}<span style='color:{color}; font-weight:bold;'>{san}</span>{anchor_close}"
        return f"{anchor_open}<span style='color:#ddd;'>{san}<span style='color:#ff5555;'>!</span></span>{anchor_close}"

    def _on_anchor(self, qurl):
        s = qurl.toString()
        if not s.startswith("ply:"):
            return
        try:
            ply = int(s[4:])
        except ValueError:
            return
        self._show_ply(ply)

    def _show_ply(self, ply: int):
        if ply < 1:
            return
        if ply <= len(self.positions):
            idx = ply - 1
            board = self.positions[idx]
            pushed_san: Optional[str] = self.sans[idx]
            last_move = self.history[idx - 1] if idx > 0 else None
            has_pushed = True
        elif ply in self.issues_by_ply:
            board = self.final_board
            pushed_san = None
            last_move = self.history[-1] if self.history else None
            has_pushed = False
        else:
            return
        issues = self.issues_by_ply.get(ply, [])

        arrows = []
        fill = {}
        info_parts = [f"<b>Ply {ply}</b>"]

        if not issues and has_pushed:
            # Clean move — show what was played in blue
            try:
                mv = board.parse_san(pushed_san)
                fill[mv.from_square] = "#3692e755"
                fill[mv.to_square] = "#3692e799"
                arrows.append(chess.svg.Arrow(mv.from_square, mv.to_square, color="#3692e7"))
            except ValueError:
                pass
            info_parts.append(
                f"You played <span style='color:#3692e7; font-weight:bold;'>{pushed_san}</span> (clean)"
            )
        else:
            # Red arrows for every wrong attempt, green arrows for every better/expected move
            wrong_sans = []
            for issue in issues:
                w = issue["played"]
                if w in wrong_sans:
                    continue
                wrong_sans.append(w)
                try:
                    mv = board.parse_san(w)
                    arrows.append(chess.svg.Arrow(mv.from_square, mv.to_square, color="#ff5555"))
                    fill.setdefault(mv.from_square, "#ff555566")
                    fill.setdefault(mv.to_square, "#ff5555aa")
                except ValueError:
                    pass

            better_sans = []
            for issue in issues:
                b = issue["better"]
                if b in better_sans:
                    continue
                better_sans.append(b)
                try:
                    mv = board.parse_san(b)
                    arrows.append(chess.svg.Arrow(mv.from_square, mv.to_square, color="#2bbf5b"))
                    fill.setdefault(mv.from_square, "#2bbf5b66")
                    fill.setdefault(mv.to_square, "#2bbf5baa")
                except ValueError:
                    pass

            kinds = sorted({self.KIND_LABEL.get(i["kind"], i["kind"]) for i in issues})
            info_parts.append(
                f"<span style='color:#ff5555;'>Wrong: <b>{', '.join(wrong_sans)}</b></span> "
                f"<span style='color:#aaa;'>({', '.join(kinds)})</span>"
            )
            # Stats per wrong attempt
            seen_p = set()
            for issue in issues:
                san = issue["played"]
                if san in seen_p:
                    continue
                seen_p.add(san)
                stats = issue.get("played_stats") or {}
                info_parts.append(self._stat_line(san, stats, "#ff8888"))

            info_parts.append(
                f"<span style='color:#2bbf5b;'>Better: <b>{', '.join(better_sans)}</b></span>"
            )
            seen_b = set()
            for issue in issues:
                san = issue["better"]
                if san in seen_b:
                    continue
                seen_b.add(san)
                stats = issue.get("better_stats") or {}
                info_parts.append(self._stat_line(san, stats, "#7fce8a"))

            # Comparison
            cmp_line = self._compare_line(issues)
            if cmp_line:
                info_parts.append(cmp_line)

            if has_pushed and any(i["kind"] in ("inaccuracy", "blunder") for i in issues):
                info_parts.append(
                    f"<span style='color:#888;'>actually pushed: {pushed_san}</span>"
                )
            if not has_pushed:
                info_parts.append(
                    "<span style='color:#aaa;'>(never landed a valid move at this ply)</span>"
                )

        self._render_mini(board, arrows, fill, last_move)
        self.info_lbl.setText("<br>".join(info_parts))

    @staticmethod
    def _stat_line(san: str, stats: dict, color: str) -> str:
        if not stats:
            return (f"<span style='margin-left:14px; color:#666; font-size:11px;'>"
                    f"&nbsp;&nbsp;{san}: no data (rare or off-book)</span>")
        return (
            f"<span style='margin-left:14px; color:{color}; font-size:11px;'>"
            f"&nbsp;&nbsp;<b>{san}</b>: played {stats['freq_pct']:.1f}% &nbsp;·&nbsp; "
            f"W{stats['w_pct']:.0f}/D{stats['d_pct']:.0f}/L{stats['l_pct']:.0f} &nbsp;·&nbsp; "
            f"{stats['games']:,} games &nbsp;·&nbsp; avg {stats['avg_rating']}"
            f"</span>"
        )

    @staticmethod
    def _compare_line(issues: list) -> str:
        # Pick first issue with both stats present
        for issue in issues:
            p = issue.get("played_stats") or {}
            b = issue.get("better_stats") or {}
            if not p or not b:
                continue
            p_score = p["w_pct"] + p["d_pct"]
            b_score = b["w_pct"] + b["d_pct"]
            diff = b_score - p_score
            freq_diff = b["freq_pct"] - p["freq_pct"]
            reasons = []
            if diff > 5:
                reasons.append(
                    f"the better move scores +{diff:.0f}% W+D for your color"
                )
            if freq_diff > 10:
                reasons.append(
                    f"played {freq_diff:.0f}% more often by strong players"
                )
            if b.get("avg_rating", 0) and p.get("avg_rating", 0):
                rd = b["avg_rating"] - p["avg_rating"]
                if abs(rd) >= 50:
                    reasons.append(
                        f"avg rating of games is {'higher' if rd > 0 else 'lower'} by {abs(rd)}"
                    )
            if reasons:
                return (
                    f"<span style='margin-top:6px; color:#dde; font-size:12px;'>"
                    f"<b>Why:</b> {'; '.join(reasons)}.</span>"
                )
        return ""

    def _render_mini(self, board, arrows, fill, last_move):
        svg = chess.svg.board(
            board,
            orientation=self.orientation,
            lastmove=last_move,
            arrows=arrows,
            fill=fill,
            coordinates=True,
            size=self.MINI_SIZE,
        )
        self.mini_board.load(QByteArray(svg.encode("utf-8")))


class LineSummaryDialog(QDialog):
    def __init__(self, parent, opening: str, line_name: str, accuracy: float,
                 total_moves: int, errors: int, inaccuracies: int, strays: list):
        super().__init__(parent)
        self.setWindowTitle("Line complete")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        title = QLabel(f"<b>{opening}</b><br><span style='color:#bbb;'>{line_name}</span>")
        title.setStyleSheet("font-size:14px; padding:6px;")
        layout.addWidget(title)

        acc_color = "#7c7" if accuracy >= 90 else "#dd7" if accuracy >= 75 else "#d77"
        stats = QLabel(
            f"<div style='font-size:13px;'>"
            f"Accuracy: <span style='color:{acc_color};'>{accuracy:.1f}%</span><br>"
            f"Moves: {total_moves} &nbsp; Errors: {errors} &nbsp; Inaccuracies: {inaccuracies}"
            f"</div>"
        )
        stats.setStyleSheet("padding:6px;")
        layout.addWidget(stats)

        strays_hdr = QLabel(
            f"<b>Deviations from selected line:</b> "
            f"<span style='color:#bbb;'>{len(strays)}</span>"
        )
        strays_hdr.setStyleSheet("padding:6px 6px 0 6px;")
        layout.addWidget(strays_hdr)

        if strays:
            body = QTextBrowser()
            body.setOpenLinks(False)
            html_parts = ["<table style='font-size:12px;'>"]
            html_parts.append(
                "<tr><th align='left'>Ply</th>"
                "<th align='left'>You played</th>"
                "<th align='left'>Line expected</th></tr>"
            )
            for s in strays:
                html_parts.append(
                    f"<tr><td>{s['ply']}</td>"
                    f"<td style='color:#e8a13a;'>{s['actual_san']}</td>"
                    f"<td style='color:#7fce7f;'>{s['expected_san']}</td></tr>"
                )
            html_parts.append("</table>")
            body.setHtml("".join(html_parts))
            body.setMinimumHeight(180)
            layout.addWidget(body)
        else:
            ok_lbl = QLabel("<span style='color:#7fce7f;'>You followed the line exactly.</span>")
            ok_lbl.setStyleSheet("padding:8px;")
            layout.addWidget(ok_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Opening Trainer")
        self.setMinimumSize(1040, 680)

        self.board = chess.Board()
        self.history: list[chess.Move] = []
        self.mode = "explore"
        self.user_side = chess.WHITE
        self.repertoire = load_repertoire()
        self.current_data: Optional[dict] = None
        self._maia_data: Optional[dict] = None
        self._maia_data_key: Optional[tuple] = None  # (fen, player)
        self._maia_pending_key: Optional[tuple] = None

        self.drill_total = 0
        self.drill_correct = 0
        self.drill_errors = 0
        self.drill_inaccuracies = 0
        self.drill_inacc_streak = 0
        self.drill_log = []
        self.drill_log: list[dict] = []

        self.eval_cache: dict[str, Optional[int]] = {}
        self.eval_inacc_cp = 200
        self.eval_blunder_cp = 400

        self.fetcher = LichessFetcher()
        self.fetcher.dataReady.connect(self.on_data)
        self.fetcher.playerDataReady.connect(self.on_player_data)
        self.fetcher.linesReady.connect(self.on_lines_ready)
        self.opening_lines_cache: dict = {}
        self._current_opening_key: str = ""
        self._line_script: list = []
        self._line_script_pos: int = 0
        self._line_strays: list = []
        self._line_summary_shown: bool = False
        self._line_start_ply: int = 0

        self._build_ui()
        self._refresh_position()
        self._ensure_lines_fetched()

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)

        # ---- Board column ----
        self.board_widget = BoardWidget()
        self.board_widget.moveMade.connect(self.on_user_move)
        board_col = QVBoxLayout()
        board_col.addWidget(self.board_widget, 1)

        self.opening_label = QLabel("Starting position")
        self.opening_label.setStyleSheet("font-size:13px; padding:4px; color:#d8d8d8;")
        board_col.addWidget(self.opening_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#888; font-family:Consolas,monospace; font-size:10px; padding:2px;")
        self.status_label.setWordWrap(True)
        board_col.addWidget(self.status_label)
        board_col.addStretch(1)

        root.addLayout(board_col)

        # ---- Right column ----
        right = QVBoxLayout()
        right.setSpacing(8)

        # Mode group
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_row = QHBoxLayout()
        self.explore_radio = QRadioButton("Explore")
        self.drill_radio = QRadioButton("Drill")
        self.explore_radio.setChecked(True)
        self.mode_buttons = QButtonGroup(self)
        self.mode_buttons.addButton(self.explore_radio)
        self.mode_buttons.addButton(self.drill_radio)
        self.explore_radio.toggled.connect(self.on_mode_change)
        mode_row.addWidget(self.explore_radio)
        mode_row.addWidget(self.drill_radio)
        mode_row.addStretch(1)
        mode_layout.addLayout(mode_row)

        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("Drill side:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["White", "Black"])
        self.side_combo.currentIndexChanged.connect(self.on_side_change)
        side_row.addWidget(self.side_combo)
        side_row.addStretch(1)
        mode_layout.addLayout(side_row)

        opening_row = QHBoxLayout()
        opening_row.addWidget(QLabel("Drill from:"))
        self.opening_combo = QComboBox()
        self.opening_combo.addItems(OPENING_LINES.keys())
        self.opening_combo.setEditable(True)
        self.opening_combo.setInsertPolicy(QComboBox.NoInsert)
        self.opening_combo.lineEdit().setPlaceholderText("Search openings…")
        _opening_completer = QCompleter(self.opening_combo.model(), self.opening_combo)
        _opening_completer.setCaseSensitivity(Qt.CaseInsensitive)
        _opening_completer.setFilterMode(Qt.MatchContains)
        _opening_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.opening_combo.setCompleter(_opening_completer)
        self.opening_combo.currentIndexChanged.connect(self.on_opening_change)
        opening_row.addWidget(self.opening_combo, stretch=1)
        mode_layout.addLayout(opening_row)

        line_row = QHBoxLayout()
        line_row.addWidget(QLabel("Line:"))
        self.line_combo = QComboBox()
        self.line_combo.addItem("Mainline (no extension)", {"type": "main"})
        self.line_combo.addItem("Random (resample each game)", {"type": "random"})
        self.line_combo.currentIndexChanged.connect(self.on_line_change)
        line_row.addWidget(self.line_combo, stretch=1)
        mode_layout.addLayout(line_row)

        opp_row = QHBoxLayout()
        opp_row.addWidget(QLabel("Opponent:"))
        self.opp_combo = QComboBox()
        self.opp_combo.addItems(OPPONENT_MODES)
        opp_row.addWidget(self.opp_combo, stretch=1)
        mode_layout.addLayout(opp_row)

        self.auto_reply_cb = QCheckBox("Auto-reply with most popular move (Explore)")
        mode_layout.addWidget(self.auto_reply_cb)

        right.addWidget(mode_group)

        # Drill stats
        self.stats_group = QGroupBox("Drill stats")
        stats_layout = QVBoxLayout(self.stats_group)
        self.stats_label = QLabel("Moves: 0   Correct: 0   Errors: 0   Inaccuracies: 0\nAccuracy: -")
        self.stats_label.setStyleSheet("font-family:Consolas,monospace; padding:4px; color:#ccc;")
        stats_layout.addWidget(self.stats_label)
        self.stats_group.setVisible(False)
        right.addWidget(self.stats_group)

        # Explorer
        exp_group = QGroupBox("Explorer")
        exp_layout = QVBoxLayout(exp_group)
        self.explorer_area = QScrollArea()
        self.explorer_area.setWidgetResizable(True)
        self.explorer_area.setMinimumHeight(280)
        self.explorer_container = QWidget()
        self.explorer_layout = QVBoxLayout(self.explorer_container)
        self.explorer_layout.setSpacing(3)
        self.explorer_layout.setContentsMargins(2, 2, 2, 2)
        self.explorer_layout.addStretch(1)
        self.explorer_area.setWidget(self.explorer_container)
        exp_layout.addWidget(self.explorer_area)
        right.addWidget(exp_group, stretch=1)

        # History
        hist_group = QGroupBox("Moves")
        hist_layout = QVBoxLayout(hist_group)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(140)
        self.history_list.setStyleSheet("font-family:Consolas,monospace;")
        hist_layout.addWidget(self.history_list)
        right.addWidget(hist_group)

        # Buttons
        btn_row = QHBoxLayout()
        for label, slot in [
            ("New game", self.new_game),
            ("Flip", self.board_widget.flip),
            ("Undo", self.undo),
            ("Hint", self.show_hint),
            ("Export PGN", self.export_pgn),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        right.addLayout(btn_row)

        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setMinimumWidth(440)
        right_widget.setMaximumWidth(560)
        root.addWidget(right_widget)

        self.setCentralWidget(central)

    # ---------------- mode handling ----------------

    def on_mode_change(self):
        new_mode = "explore" if self.explore_radio.isChecked() else "drill"
        if new_mode == self.mode:
            return
        self.mode = new_mode
        self.stats_group.setVisible(new_mode == "drill")
        if new_mode == "drill":
            self.user_side = chess.WHITE if self.side_combo.currentIndex() == 0 else chess.BLACK
            self.board_widget.set_orientation(self.user_side)
        self.new_game()

    def on_side_change(self):
        if self.mode == "drill":
            self.user_side = chess.WHITE if self.side_combo.currentIndex() == 0 else chess.BLACK
            self.board_widget.set_orientation(self.user_side)
            self.new_game()

    def _check_line_complete(self):
        if not self._line_script:
            return
        if self._line_summary_shown:
            return
        if self._line_script_pos < len(self._line_script):
            return
        self._line_summary_shown = True
        QTimer.singleShot(150, self._show_line_summary)

    def _show_line_summary(self):
        total_user_moves = self.drill_total
        if total_user_moves:
            acc = (self.drill_correct - self.drill_inaccuracies) / total_user_moves * 100.0
        else:
            acc = 0.0
        line_name = self.line_combo.currentText() if hasattr(self, "line_combo") else ""
        opening_name = self.opening_combo.currentText() if hasattr(self, "opening_combo") else ""
        dlg = LineSummaryDialog(
            self,
            opening=opening_name,
            line_name=line_name,
            accuracy=acc,
            total_moves=total_user_moves,
            errors=self.drill_errors,
            inaccuracies=self.drill_inaccuracies,
            strays=list(self._line_strays),
        )
        dlg.exec()

    def _select_extension_ucis(self) -> list:
        if not hasattr(self, "line_combo"):
            return []
        data = self.line_combo.currentData()
        if not isinstance(data, dict):
            return []
        kind = data.get("type")
        if kind == "main":
            return []
        if kind == "fixed":
            return list(data.get("moves", []))
        if kind == "random":
            lines = self.opening_lines_cache.get(self.opening_combo.currentText(), [])
            if not lines:
                return []
            return list(random.choice(lines).get("moves", []))
        return []

    def on_opening_change(self):
        self._refresh_line_combo()
        self.new_game()
        self._ensure_lines_fetched()

    def on_line_change(self):
        self.new_game()

    def _refresh_line_combo(self, preserve_selection: bool = False):
        key = self.opening_combo.currentText()
        prev_data = self.line_combo.currentData() if preserve_selection else None
        self._current_opening_key = key
        self.line_combo.blockSignals(True)
        self.line_combo.clear()
        self.line_combo.addItem("Mainline (no extension)", {"type": "main"})
        self.line_combo.addItem("Random (resample each game)", {"type": "random"})
        for entry in self.opening_lines_cache.get(key, []):
            self.line_combo.addItem(entry["san"], {"type": "fixed", "moves": entry["moves"]})
        new_index = 0
        if preserve_selection and isinstance(prev_data, dict):
            prev_type = prev_data.get("type")
            if prev_type in ("main", "random"):
                new_index = 0 if prev_type == "main" else 1
        self.line_combo.setCurrentIndex(new_index)
        self.line_combo.blockSignals(False)

    def _ensure_lines_fetched(self):
        key = self.opening_combo.currentText()
        if key in self.opening_lines_cache:
            return
        line = OPENING_LINES.get(key, "")
        start_board = chess.Board()
        for tok in line.split():
            try:
                start_board.push_san(tok)
            except ValueError:
                break
        self.fetcher.fetch_top_lines(key, start_board, depth=6)

    def on_lines_ready(self, opening_key, lines):
        self.opening_lines_cache[opening_key] = lines
        if opening_key == self.opening_combo.currentText():
            self._refresh_line_combo(preserve_selection=True)

    def new_game(self):
        self.board.reset()
        self.history.clear()
        self.history_list.clear()
        self.drill_total = 0
        self.drill_correct = 0
        self.drill_errors = 0
        self.drill_inaccuracies = 0
        self.drill_inacc_streak = 0
        self.drill_log = []
        self.eval_cache.clear()
        self._maia_data = None
        self._maia_data_key = None
        self._maia_pending_key = None
        self._update_drill_stats()

        line = OPENING_LINES.get(self.opening_combo.currentText(), "") \
            if hasattr(self, "opening_combo") else ""
        for tok in line.split():
            try:
                mv = self.board.parse_san(tok)
            except ValueError:
                break
            san = self.board.san(mv)
            self.board.push(mv)
            self.history.append(mv)
            self._append_history(san)

        self._line_script = self._select_extension_ucis()
        self._line_script_pos = 0
        self._line_strays = []
        self._line_summary_shown = False
        self._line_start_ply = len(self.history)

        last_move = self.history[-1] if self.history else None
        self.board_widget.set_position(self.board, last_move)
        self._refresh_position()
        if self.mode == "drill" and self.board.turn != self.user_side and not self.board.is_game_over():
            self._schedule_opponent_move()

    def undo(self):
        if self.mode == "drill":
            QMessageBox.information(self, "Undo", "Undo is disabled in Drill mode. Use Reset.")
            return
        if not self.history:
            return
        self.history.pop()
        self.board.reset()
        for mv in self.history:
            self.board.push(mv)
        self._rebuild_history_list()
        last = self.history[-1] if self.history else None
        self.board_widget.set_position(self.board, last)
        self._refresh_position()

    # ---------------- move flow ----------------

    def on_user_move(self, move: chess.Move):
        if self.mode == "drill" and self.board.turn != self.user_side:
            return

        if self.mode == "drill" and self.current_data is None:
            self._flash("Waiting for Lichess data… try again in a sec.")
            return

        if self.mode == "drill":
            fen = self.board.fen()
            played_san = self.board.san(move)
            played_uci = move.uci()
            saved = self.repertoire.get(fen)
            self.drill_total += 1
            sev_wdl = self._classify_move(played_uci)
            sev_eval = self._classify_by_eval(move)
            severity = self._worst_severity(sev_wdl, sev_eval)
            swing_cp = self._eval_swing_cp(move)

            ply = len(self.history) + 1

            if saved is None:
                self.repertoire[fen] = played_san
                save_repertoire(self.repertoire)
                self.drill_correct += 1
                if severity:
                    self.drill_inaccuracies += 1
                    self.drill_inacc_streak += 1
                    better = self._best_lichess_san() or "?"
                    p_stats = self._move_stats_for_san(played_san)
                    b_stats = self._move_stats_for_san(better)
                    self.drill_log.append({"ply": ply, "kind": severity,
                                            "played": played_san, "better": better,
                                            "played_stats": p_stats, "better_stats": b_stats,
                                            "swing_cp": swing_cp})
                    swing_tag = f" Δ{swing_cp/100:+.1f}" if swing_cp is not None and abs(swing_cp) >= 50 else ""
                    self._flash(
                        f"Saved {played_san} ({severity}{swing_tag} — better: {better} "
                        f"[{self._wd_brief(b_stats)}] vs you [{self._wd_brief(p_stats)}])."
                    )
                else:
                    self.drill_inacc_streak = 0
                    self._flash(f"Saved {played_san} as your repertoire move.")
            elif played_san != saved:
                self.drill_errors += 1
                self.drill_inacc_streak = 0
                p_stats = self._move_stats_for_san(played_san)
                b_stats = self._move_stats_for_san(saved)
                self.drill_log.append({"ply": ply, "kind": "error",
                                        "played": played_san, "better": saved,
                                        "played_stats": p_stats, "better_stats": b_stats,
                                        "swing_cp": swing_cp})
                try:
                    correct_move = self.board.parse_san(saved)
                    self.board_widget.show_hint_arrow(correct_move)
                except ValueError:
                    pass
                self._flash(
                    f"✗ WRONG. Expected {saved} [{self._wd_brief(b_stats)}], "
                    f"you played {played_san} [{self._wd_brief(p_stats)}]. Try again — see red arrow."
                )
                self.opening_label.setStyleSheet(
                    "font-size:14px; padding:4px; color:#ff4040; font-weight:bold;"
                )
                self._update_drill_stats()
                if self._check_drill_restart():
                    return
                return
            else:
                self.drill_correct += 1
                if severity:
                    self.drill_inaccuracies += 1
                    self.drill_inacc_streak += 1
                    better = self._best_lichess_san() or "?"
                    p_stats = self._move_stats_for_san(played_san)
                    b_stats = self._move_stats_for_san(better)
                    self.drill_log.append({"ply": ply, "kind": severity,
                                            "played": played_san, "better": better,
                                            "played_stats": p_stats, "better_stats": b_stats,
                                            "swing_cp": swing_cp})
                    swing_tag = f" Δ{swing_cp/100:+.1f}" if swing_cp is not None and abs(swing_cp) >= 50 else ""
                    self._flash(
                        f"✓ Correct: {played_san} ({severity}{swing_tag} — better: {better} "
                        f"[{self._wd_brief(b_stats)}] vs you [{self._wd_brief(p_stats)}])"
                    )
                else:
                    self.drill_inacc_streak = 0
                    self._flash(f"✓ Correct: {played_san}")
            self._update_drill_stats()
            if self._check_drill_restart():
                return

        if self._line_script and self._line_script_pos < len(self._line_script):
            expected_uci = self._line_script[self._line_script_pos]
            if move.uci() != expected_uci:
                try:
                    exp_mv = chess.Move.from_uci(expected_uci)
                    expected_san = self.board.san(exp_mv) if exp_mv in self.board.legal_moves else expected_uci
                except ValueError:
                    expected_san = expected_uci
                self._line_strays.append({
                    "ply": len(self.history) + 1,
                    "expected_uci": expected_uci,
                    "expected_san": expected_san,
                    "actual_uci": move.uci(),
                    "actual_san": self.board.san(move),
                })
            self._line_script_pos += 1

        self._push_move(move)
        self._check_line_complete()

        if self.board.is_game_over():
            return

        if self.mode == "explore" and self.auto_reply_cb.isChecked():
            self._schedule_auto_reply()
        elif self.mode == "drill" and self.board.turn != self.user_side:
            self._schedule_opponent_move()

    def _push_move(self, move: chess.Move):
        san = self.board.san(move)
        self.board.push(move)
        self.history.append(move)
        self._append_history(san)
        self.board_widget.set_position(self.board, move)
        self._refresh_position()
        self._check_game_over()

    def _append_history(self, san: str):
        ply = len(self.history)
        if ply % 2 == 1:
            self.history_list.addItem(QListWidgetItem(f"{(ply + 1) // 2}. {san}"))
        else:
            if self.history_list.count() > 0:
                last = self.history_list.item(self.history_list.count() - 1)
                last.setText(f"{last.text()}  {san}")
        self.history_list.scrollToBottom()

    def _rebuild_history_list(self):
        self.history_list.clear()
        tmp = chess.Board()
        for i, mv in enumerate(self.history):
            san = tmp.san(mv)
            tmp.push(mv)
            if i % 2 == 0:
                self.history_list.addItem(QListWidgetItem(f"{i // 2 + 1}. {san}"))
            else:
                last = self.history_list.item(self.history_list.count() - 1)
                last.setText(f"{last.text()}  {san}")

    # ---------------- opponent / auto-reply ----------------

    def _schedule_opponent_move(self):
        self.board_widget.locked = True
        QTimer.singleShot(PARAMS["opponent_delay_ms"], self._make_opponent_move)

    def _make_opponent_move(self):
        if self._line_script and self._line_script_pos < len(self._line_script):
            uci = self._line_script[self._line_script_pos]
            try:
                mv = chess.Move.from_uci(uci)
                if mv in self.board.legal_moves:
                    self._line_script_pos += 1
                    self.board_widget.locked = False
                    self._push_move(mv)
                    self._check_line_complete()
                    return
            except ValueError:
                pass
            self._line_script = []

        mode = self.opp_combo.currentText()
        if mode in MAIA_USERS:
            fen = self.board.fen()
            player = MAIA_USERS[mode]
            color = "white" if self.board.turn == chess.WHITE else "black"
            key = (fen, player)
            if self._maia_data_key == key and self._maia_data is not None:
                data = self._maia_data
            else:
                if self._maia_pending_key != key:
                    self._maia_pending_key = key
                    self.fetcher.fetch_player(fen, player, color)
                QTimer.singleShot(200, self._make_opponent_move)
                return
        else:
            if self.current_data is None:
                QTimer.singleShot(150, self._make_opponent_move)
                return
            data = self.current_data
        uci = pick_opponent_move(data, mode)
        self.board_widget.locked = False
        if uci is None:
            self._flash("Out of book. Resetting line.")
            QTimer.singleShot(900, self.new_game)
            return
        try:
            mv = chess.Move.from_uci(uci)
            if mv not in self.board.legal_moves:
                raise ValueError("illegal")
            self._push_move(mv)
        except (ValueError, AssertionError):
            self._flash("Bad opponent move. Resetting.")
            QTimer.singleShot(900, self.new_game)

    def _schedule_auto_reply(self):
        self.board_widget.locked = True
        QTimer.singleShot(PARAMS["opponent_delay_ms"], self._make_auto_reply)

    def _make_auto_reply(self):
        if self.current_data is None:
            QTimer.singleShot(150, self._make_auto_reply)
            return
        moves = [m for m in self.current_data.get("moves", [])
                 if (m["white"] + m["draws"] + m["black"]) > 0]
        self.board_widget.locked = False
        if not moves:
            return
        moves.sort(key=lambda m: -(m["white"] + m["draws"] + m["black"]))
        try:
            mv = chess.Move.from_uci(moves[0]["uci"])
            if mv in self.board.legal_moves:
                self._push_move(mv)
        except (ValueError, AssertionError):
            pass

    # ---------------- API / explorer ----------------

    def _refresh_position(self):
        self.current_data = None
        self._update_status()
        self.fetcher.fetch(self.board.fen())
        self._prefetch_eval(self.board.fen())

    @Slot(str, object)
    def on_data(self, fen, data):
        if fen != self.board.fen():
            return
        self.current_data = data if data is not None else {"moves": []}
        self._render_explorer(self.current_data)
        self._update_opening(self.current_data)

    @Slot(str, str, object)
    def on_player_data(self, fen, player, data):
        key = (fen, player)
        self._maia_data_key = key
        self._maia_data = data if data is not None else {"moves": []}
        if self._maia_pending_key == key:
            self._maia_pending_key = None

    def _render_explorer(self, data):
        while self.explorer_layout.count() > 1:
            item = self.explorer_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if data.get("_error"):
            msg = data.get("_error_msg", "Unknown API error")
            err = QLabel(f"API error:\n{msg}")
            err.setStyleSheet("color:#d77; padding:8px; font-family:Consolas,monospace; font-size:11px;")
            err.setWordWrap(True)
            self.explorer_layout.insertWidget(0, err)
            return

        moves = data.get("moves", [])
        total_pos = sum(m["white"] + m["draws"] + m["black"] for m in moves) or 1
        if not moves:
            empty = QLabel("(no games in database)")
            empty.setStyleSheet("color:#888; padding:8px;")
            self.explorer_layout.insertWidget(0, empty)
            return

        insert_idx = 0
        for m in moves:
            w_, d_, l_ = m["white"], m["draws"], m["black"]
            total = w_ + d_ + l_
            if total == 0:
                continue
            try:
                san = self.board.san(chess.Move.from_uci(m["uci"]))
            except (ValueError, AssertionError):
                san = m.get("san", m["uci"])
            row = MoveStatRow(
                san, m["uci"], 100.0 * total / total_pos,
                100.0 * w_ / total, 100.0 * d_ / total, 100.0 * l_ / total,
                total,
                hide_stats=(self.mode == "drill"),
            )
            row.clicked.connect(self._on_explorer_click)
            self.explorer_layout.insertWidget(insert_idx, row)
            insert_idx += 1

    def _on_explorer_click(self, uci):
        try:
            mv = chess.Move.from_uci(uci)
        except ValueError:
            return
        if mv not in self.board.legal_moves:
            return
        if self.mode == "drill" and self.board.turn != self.user_side:
            return
        self.on_user_move(mv)

    def _update_opening(self, data):
        op = data.get("opening") if data else None
        if op:
            eco = op.get("eco", "")
            name = op.get("name", "")
            self.opening_label.setText(f"{eco} {name}".strip())
        elif not self.history:
            self.opening_label.setText("Starting position")

    def _update_status(self):
        turn = "White" if self.board.turn == chess.WHITE else "Black"
        self.status_label.setText(f"{turn} to move\nFEN: {self.board.fen()}")

    def _flash(self, msg: str):
        self.opening_label.setText(msg)
        self.opening_label.setStyleSheet("font-size:13px; padding:4px; color:#d8d8d8;")

    def _move_stats_for_san(self, san: str) -> dict:
        """Return Lichess stats for the SAN from current player's color perspective."""
        if not self.current_data:
            return {}
        moves = self.current_data.get("moves", [])
        if not moves:
            return {}
        try:
            target_uci = self.board.parse_san(san).uci()
        except ValueError:
            return {}
        color_is_white = (self.board.turn == chess.WHITE)
        total_pos = sum(m["white"] + m["draws"] + m["black"] for m in moves)
        for m in moves:
            if m["uci"] != target_uci:
                continue
            t = m["white"] + m["draws"] + m["black"]
            if t == 0:
                return {}
            wins = m["white"] if color_is_white else m["black"]
            losses = m["black"] if color_is_white else m["white"]
            return {
                "freq_pct": 100.0 * t / total_pos if total_pos else 0.0,
                "w_pct": 100.0 * wins / t,
                "d_pct": 100.0 * m["draws"] / t,
                "l_pct": 100.0 * losses / t,
                "games": t,
                "avg_rating": m.get("averageRating", 0),
            }
        return {}

    @staticmethod
    def _wd_brief(stats: dict) -> str:
        if not stats:
            return "no data"
        return f"{stats['w_pct'] + stats['d_pct']:.0f}% W+D"

    def _best_lichess_san(self) -> Optional[str]:
        if not self.current_data:
            return None
        moves = self.current_data.get("moves", [])
        if not moves:
            return None
        color_is_white = (self.board.turn == chess.WHITE)

        def quality(m):
            total = m["white"] + m["draws"] + m["black"]
            if total == 0:
                return -1.0
            wins = m["white"] if color_is_white else m["black"]
            return (wins + m["draws"] / 2.0) / total

        best = max(moves, key=quality)
        try:
            return self.board.san(chess.Move.from_uci(best["uci"]))
        except (ValueError, AssertionError):
            return best.get("san", best["uci"])

    def _cloud_eval_cp(self, fen: str) -> Optional[int]:
        """Centipawn eval (White POV) from Lichess cloud-eval. None if uncached / error."""
        if fen in self.eval_cache:
            return self.eval_cache[fen]
        try:
            r = requests.get(
                "https://lichess.org/api/cloud-eval",
                params={"fen": fen, "multiPv": 1},
                headers={"User-Agent": "chess_trainer_gui/1.0"},
                timeout=2.5,
            )
            if r.status_code == 404:
                self.eval_cache[fen] = None
                return None
            r.raise_for_status()
            pvs = (r.json() or {}).get("pvs") or []
            if not pvs:
                self.eval_cache[fen] = None
                return None
            pv = pvs[0]
            if "mate" in pv:
                cp = 10000 if pv["mate"] > 0 else -10000
            else:
                cp = int(pv.get("cp", 0))
            self.eval_cache[fen] = cp
            return cp
        except (requests.RequestException, ValueError) as e:
            print(f"[cloud-eval] {e!r}", file=sys.stderr)
            self.eval_cache[fen] = None
            return None

    def _prefetch_eval(self, fen: str) -> None:
        if fen in self.eval_cache:
            return
        threading.Thread(target=self._cloud_eval_cp, args=(fen,), daemon=True).start()

    def _eval_swing_cp(self, move: chess.Move) -> Optional[int]:
        """Centipawn loss for the side to move after `move`. None if eval unavailable."""
        pre = self._cloud_eval_cp(self.board.fen())
        if pre is None:
            return None
        test = self.board.copy(stack=False)
        test.push(move)
        post = self._cloud_eval_cp(test.fen())
        if post is None:
            return None
        side = self.board.turn  # side that just moved
        pre_user = pre if side == chess.WHITE else -pre
        post_user = post if side == chess.WHITE else -post
        return pre_user - post_user  # positive = move hurt the player

    def _classify_by_eval(self, move: chess.Move) -> Optional[str]:
        swing = self._eval_swing_cp(move)
        if swing is None:
            return None
        if swing >= self.eval_blunder_cp:
            return "blunder"
        if swing >= self.eval_inacc_cp:
            return "inaccuracy"
        return None

    @staticmethod
    def _worst_severity(a: Optional[str], b: Optional[str]) -> Optional[str]:
        rank = {None: 0, "inaccuracy": 1, "blunder": 2}
        return a if rank.get(a, 0) >= rank.get(b, 0) else b

    def _classify_move(self, uci_played: str) -> Optional[str]:
        """Returns None (good), 'inaccuracy', or 'blunder' relative to best Lichess move."""
        if not self.current_data:
            return None
        moves = self.current_data.get("moves", [])
        if not moves:
            return None
        color_is_white = (self.board.turn == chess.WHITE)

        def quality(m):
            total = m["white"] + m["draws"] + m["black"]
            if total == 0:
                return 0.0
            wins = m["white"] if color_is_white else m["black"]
            return (wins + m["draws"] / 2.0) / total

        # Top-5 most-played moves are always considered fine.
        def popularity(m):
            return m["white"] + m["draws"] + m["black"]
        top5_ucis = {m["uci"] for m in sorted(moves, key=popularity, reverse=True)[:5]}
        if uci_played in top5_ucis:
            return None

        played_q = None
        best_q = 0.0
        for m in moves:
            q = quality(m)
            if q > best_q:
                best_q = q
            if m["uci"] == uci_played:
                played_q = q

        if played_q is None or best_q <= 0:
            return None
        ratio = played_q / best_q
        if ratio >= 0.8:
            return None
        if ratio >= 0.4:
            return "inaccuracy"
        return "blunder"

    def _check_drill_restart(self) -> bool:
        header = None
        if self.drill_inacc_streak >= 3:
            header = "3 inaccuracies in a row — drill will restart."
        elif self.drill_total >= 5:
            acc = (self.drill_correct - self.drill_inaccuracies) / self.drill_total * 100.0
            if acc < 90.0:
                header = f"Accuracy dropped to {acc:.1f}% — drill will restart."
        if header is None:
            return False

        dlg = DrillReviewDialog(
            self, header, list(self.history), list(self.drill_log), self.user_side
        )
        dlg.exec()
        self.new_game()
        return True

    def _update_drill_stats(self):
        total = self.drill_total
        acc = (self.drill_correct - self.drill_inaccuracies) / total * 100.0 if total else 0.0
        color = "#7c7" if acc >= 90 else "#dd7" if acc >= 75 else "#d77"
        if total == 0:
            color = "#ccc"
        self.stats_label.setText(
            f"Moves: {total}   Correct: {self.drill_correct}   "
            f"Errors: {self.drill_errors}   Inaccuracies: {self.drill_inaccuracies}\n"
            f"Accuracy: {acc:.1f}%" + (" (no moves yet)" if total == 0 else "")
        )
        self.stats_label.setStyleSheet(
            f"font-family:Consolas,monospace; padding:4px; color:{color};"
        )

    # ---------------- hint / export ----------------

    def show_hint(self):
        if self.mode == "drill":
            saved = self.repertoire.get(self.board.fen())
            if saved:
                QMessageBox.information(self, "Hint", f"Repertoire move: {saved}")
                return
        if self.current_data and self.current_data.get("moves"):
            lines = []
            for m in self.current_data["moves"][:5]:
                try:
                    san = self.board.san(chess.Move.from_uci(m["uci"]))
                except (ValueError, AssertionError):
                    san = m["uci"]
                total = m["white"] + m["draws"] + m["black"]
                lines.append(f"  {san}  ({total:,} games)")
            QMessageBox.information(self, "Top moves", "\n".join(lines))
        else:
            QMessageBox.information(self, "Hint", "No data available yet.")

    def export_pgn(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PGN", "game.pgn", "PGN files (*.pgn)")
        if not path:
            return
        game = chess.pgn.Game()
        node = game
        for mv in self.history:
            node = node.add_variation(mv)
        try:
            Path(path).write_text(str(game), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))

    # ---------------- game state ----------------

    def _check_game_over(self):
        if not self.board.is_game_over():
            return
        outcome = self.board.outcome()
        msg = f"Game over: {self.board.result()}"
        if outcome:
            msg += f" ({outcome.termination.name})"
        QMessageBox.information(self, "Game over", msg)
        self.new_game()

    def closeEvent(self, event):
        save_repertoire(self.repertoire)
        event.accept()


def _apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(30, 30, 34))
    pal.setColor(QPalette.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.Base, QColor(40, 40, 44))
    pal.setColor(QPalette.AlternateBase, QColor(48, 48, 52))
    pal.setColor(QPalette.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.Button, QColor(50, 50, 54))
    pal.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.Highlight, QColor(90, 130, 200))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)


def main():
    app = QApplication(sys.argv)
    _apply_dark(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
