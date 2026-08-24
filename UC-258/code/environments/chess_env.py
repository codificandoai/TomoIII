"""Entorno de ajedrez: discreto, determinista, totalmente observable, estático.

Se provee una implementación mínima sin dependencias. Si `python-chess` está
instalado y se activa en la configuración, se usa para una representación real.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import EnvironmentConfig
from environments.base import Environment
from models import AgentAction, EnvironmentProperties, Observation, StepResult


class ChessboardEnvironment(Environment):
    """Tablero de ajedrez para demostración de búsqueda exacta."""

    def __init__(self, config: Optional[EnvironmentConfig] = None, fen: Optional[str] = None):
        self.config = config or EnvironmentConfig()
        self._use_chess = self.config.chess_use_python_chess
        self.board = None
        self._state: Dict[str, Any] = {}
        self._last_move: Optional[str] = None
        self._init_board(fen)

    def _init_board(self, fen: Optional[str]) -> None:
        if self._use_chess:
            try:
                import chess

                self.board = chess.Board(fen) if fen else chess.Board()
                self._state = {"fen": self.board.fen(), "use_chess": True}
                return
            except Exception:
                self._use_chess = False
        # Fallback: tablero simplificado para puzzle mate-en-uno
        self._state = {
            "white": {"king": "e1", "queen": "d1"},
            "black": {"king": "e8", "pawn": "e5"},
            "turn": "white",
        }

    @property
    def properties(self) -> EnvironmentProperties:
        return EnvironmentProperties(
            name="chess",
            is_dynamic=False,
            is_deterministic=True,
            is_fully_observable=True,
            is_discrete=True,
            is_episodic=False,
            is_multi_agent=True,
        )

    def get_observation(self) -> Observation:
        if self._use_chess and self.board is not None:
            return Observation(
                data={"fen": self.board.fen(), "turn": "white" if self.board.turn else "black"},
                hidden=None,
                confidence=1.0,
                source="chess_board",
            )
        return Observation(
            data=self._state.copy(),
            hidden=None,
            confidence=1.0,
            source="simple_chess",
        )

    def is_valid_action(self, action: Any) -> bool:
        move = action.name if isinstance(action, AgentAction) else str(action)
        if self._use_chess and self.board is not None:
            try:
                import chess
                return chess.Move.from_uci(move) in self.board.legal_moves
            except Exception:
                return False
        return move in self._legal_moves()

    def _legal_moves(self) -> List[str]:
        # En el puzzle simplificado solo damos mate con Dd8# si la reina llega a d8
        if self._state["turn"] == "white":
            return ["Qd8"]
        return []

    def step(self, action: Any) -> StepResult:
        move = action.name if isinstance(action, AgentAction) else str(action)
        if not self.is_valid_action(move):
            return StepResult(
                observation=self.get_observation(),
                reward=-10.0,
                done=False,
                info={"error": "invalid_move", "move": move},
            )

        if self._use_chess and self.board is not None:
            import chess
            self.board.push(chess.Move.from_uci(move))
            reward = 100.0 if self.board.is_checkmate() else 0.0
            done = self.board.is_game_over()
            self._state["fen"] = self.board.fen()
            return StepResult(
                observation=self.get_observation(),
                reward=reward,
                done=done,
                info={"move": move, "checkmate": self.board.is_checkmate()},
            )

        # Fallback simple: Qd8 da mate
        if move == "Qd8":
            self._state["white"]["queen"] = "d8"
            reward = 100.0
            done = True
        else:
            reward = 0.0
            done = False
        self._last_move = move
        return StepResult(
            observation=self.get_observation(),
            reward=reward,
            done=done,
            info={"move": move, "checkmate": done},
        )

    def reset(self) -> Observation:
        self._init_board(None)
        return self.get_observation()

    def get_state(self) -> Dict[str, Any]:
        return self.get_observation().data
