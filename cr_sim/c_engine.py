"""Thin ctypes wrapper around libcr_engine — drop-in replacement for engine.py Arena."""

from __future__ import annotations

import ctypes
import os
import platform
from ctypes import (
    POINTER,
    Structure,
    c_float,
    c_int,
)
from enum import IntEnum
from pathlib import Path
from typing import Optional

# ── Load shared library ──────────────────────────────────

_dir = Path(__file__).resolve().parent
_ext = ".dylib" if platform.system() == "Darwin" else ".so"
_lib_path = _dir / f"libcr_engine{_ext}"

if not _lib_path.exists():
    raise ImportError(
        f"C engine not found at {_lib_path}. "
        f"Build it: cd {_dir / 'c_src'} && make"
    )

_lib = ctypes.CDLL(str(_lib_path))

# ── Constants ────────────────────────────────────────────

MAX_UNITS = 64
NUM_TOWERS = 6

# ── Enums (match C values) ──────────────────────────────

class CSide(IntEnum):
    ATTACKER = 1
    DEFENDER = 2


class CTargetType(IntEnum):
    GROUND = 1
    AIR = 2
    BUILDINGS = 3
    AIR_AND_GROUND = 4


class CUnitTransport(IntEnum):
    GROUND = 1
    AIR = 2


class CCardType(IntEnum):
    TROOP = 1
    SPELL = 2
    BUILDING = 3


# Card name lookup by index
CARD_NAMES = [
    "knight", "giant", "hog_rider", "musketeer",
    "mini_pekka", "wizard", "skeletons", "fireball",
]

CARD_INDEX = {name: i for i, name in enumerate(CARD_NAMES)}


# ── ctypes Structures ───────────────────────────────────

class CCUnit(Structure):
    _fields_ = [
        ("card_index", c_int),
        ("side", c_int),
        ("x", c_float),
        ("y", c_float),
        ("hp", c_int),
        ("max_hp", c_int),
        ("damage", c_int),
        ("hit_speed", c_float),
        ("speed", c_float),
        ("range", c_float),
        ("targets", c_int),
        ("transport", c_int),
        ("splash_radius", c_float),
        ("sight_range", c_float),
        ("attack_cooldown", c_float),
        ("deploy_timer", c_float),
        ("alive", c_int),
    ]


class CCTower(Structure):
    _fields_ = [
        ("side", c_int),
        ("tower_type", c_int),
        ("x", c_float),
        ("y", c_float),
        ("hp", c_int),
        ("max_hp", c_int),
        ("damage", c_int),
        ("hit_speed", c_float),
        ("range", c_float),
        ("attack_cooldown", c_float),
        ("active", c_int),
    ]


class CGameState(Structure):
    _fields_ = [
        ("tick", c_int),
        ("time", c_float),
        ("units", CCUnit * MAX_UNITS),
        ("unit_count", c_int),
        ("towers", CCTower * NUM_TOWERS),
        ("attacker_elixir", c_float),
        ("defender_elixir", c_float),
        ("game_over", c_int),
        ("winner", c_int),
        ("tower_damage_dealt", c_int),
    ]


class CArenaStruct(Structure):
    _fields_ = [
        ("state", CGameState),
    ]


# ── Function signatures ──────────────────────────────────

_lib.arena_create.restype = POINTER(CArenaStruct)
_lib.arena_create.argtypes = []

_lib.arena_destroy.restype = None
_lib.arena_destroy.argtypes = [POINTER(CArenaStruct)]

_lib.arena_spawn_card.restype = c_int
_lib.arena_spawn_card.argtypes = [POINTER(CArenaStruct), c_int, c_int, c_float, c_float]

_lib.arena_tick.restype = None
_lib.arena_tick.argtypes = [POINTER(CArenaStruct)]


# ── Wrapper classes ──────────────────────────────────────

class UnitView:
    """Read-only view of a C unit, duck-typed to match engine.Unit."""

    __slots__ = ("_u",)

    def __init__(self, cu: CCUnit):
        self._u = cu

    @property
    def card_name(self) -> str:
        return CARD_NAMES[self._u.card_index]

    @property
    def side(self) -> CSide:
        return CSide(self._u.side)

    @property
    def x(self) -> float:
        return self._u.x

    @property
    def y(self) -> float:
        return self._u.y

    @property
    def hp(self) -> int:
        return self._u.hp

    @property
    def max_hp(self) -> int:
        return self._u.max_hp

    @property
    def damage(self) -> int:
        return self._u.damage

    @property
    def speed(self) -> float:
        return self._u.speed

    @property
    def range(self) -> float:
        return self._u.range

    @property
    def targets(self) -> CTargetType:
        return CTargetType(self._u.targets)

    @property
    def transport(self) -> CUnitTransport:
        return CUnitTransport(self._u.transport)

    @property
    def splash_radius(self) -> float:
        return self._u.splash_radius

    @property
    def sight_range(self) -> float:
        return self._u.sight_range

    @property
    def alive(self) -> bool:
        return bool(self._u.alive and self._u.hp > 0)

    @property
    def deployed(self) -> bool:
        return self._u.deploy_timer <= 0.0

    @property
    def deploy_timer(self) -> float:
        return self._u.deploy_timer


class TowerView:
    """Read-only view of a C tower, duck-typed to match engine.Tower."""

    __slots__ = ("_t",)

    def __init__(self, ct: CCTower):
        self._t = ct

    @property
    def side(self) -> CSide:
        return CSide(self._t.side)

    @property
    def tower_type(self) -> str:
        return "king" if self._t.tower_type == 1 else "princess"

    @property
    def x(self) -> float:
        return self._t.x

    @property
    def y(self) -> float:
        return self._t.y

    @property
    def hp(self) -> int:
        return self._t.hp

    @property
    def max_hp(self) -> int:
        return self._t.max_hp

    @property
    def damage(self) -> int:
        return self._t.damage

    @property
    def range(self) -> float:
        return self._t.range

    @property
    def active(self) -> bool:
        return bool(self._t.active)

    @property
    def alive(self) -> bool:
        return self._t.hp > 0


class GameStateView:
    """Read-only view of C GameState, duck-typed to match engine.GameState."""

    def __init__(self, gs: CGameState):
        self._gs = gs

    @property
    def tick(self) -> int:
        return self._gs.tick

    @property
    def time(self) -> float:
        return self._gs.time

    @property
    def units(self) -> list[UnitView]:
        return [UnitView(self._gs.units[i]) for i in range(self._gs.unit_count)]

    @property
    def towers(self) -> list[TowerView]:
        return [TowerView(self._gs.towers[i]) for i in range(NUM_TOWERS)]

    @property
    def attacker_elixir(self) -> float:
        return self._gs.attacker_elixir

    @attacker_elixir.setter
    def attacker_elixir(self, v: float):
        self._gs.attacker_elixir = v

    @property
    def defender_elixir(self) -> float:
        return self._gs.defender_elixir

    @defender_elixir.setter
    def defender_elixir(self, v: float):
        self._gs.defender_elixir = v

    @property
    def game_over(self) -> bool:
        return bool(self._gs.game_over)

    @property
    def winner(self) -> Optional[CSide]:
        w = self._gs.winner
        if w == 0:
            return None
        return CSide(w)

    @property
    def tower_damage_dealt(self) -> int:
        return self._gs.tower_damage_dealt

    @property
    def unit_count(self) -> int:
        return self._gs.unit_count


# ── CArena — drop-in replacement for engine.Arena ────────

class CArena:
    """C-backed arena with the same public API as engine.Arena."""

    def __init__(self):
        self._ptr = _lib.arena_create()
        if not self._ptr:
            raise MemoryError("arena_create returned NULL")
        self.state = GameStateView(self._ptr.contents.state)

    def __del__(self):
        if hasattr(self, "_ptr") and self._ptr:
            _lib.arena_destroy(self._ptr)
            self._ptr = None

    def get_elixir(self, side: CSide) -> float:
        if side == CSide.ATTACKER:
            return self._ptr.contents.state.attacker_elixir
        return self._ptr.contents.state.defender_elixir

    def spawn_card(self, card, side, x: float, y: float) -> bool:
        """card: CardStats or card name string. side: CSide or engine.Side."""
        # Resolve card index
        if isinstance(card, str):
            idx = CARD_INDEX[card.lower().replace(" ", "_")]
        elif hasattr(card, "name"):
            idx = CARD_INDEX[card.name.lower().replace(" ", "_")]
        else:
            idx = int(card)

        # Resolve side to int
        side_int = int(side)

        return bool(_lib.arena_spawn_card(self._ptr, idx, side_int, c_float(x), c_float(y)))

    def tick(self):
        _lib.arena_tick(self._ptr)

    def get_tower_hp(self, side) -> dict[str, int]:
        side_int = int(side)
        gs = self._ptr.contents.state
        result = {}
        for i in range(NUM_TOWERS):
            t = gs.towers[i]
            if t.side != side_int:
                continue
            if t.tower_type == 1:
                result["king"] = t.hp
            elif "princess_left" not in result:
                result["princess_left"] = t.hp
            else:
                result["princess_right"] = t.hp
        return result
