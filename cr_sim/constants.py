"""
Clash Royale game constants and card database.
All stats are Tournament Standard (Level 11) from Liquipedia wiki.
Movement speeds are in tiles per second.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Arena dimensions (in tiles)
# =============================================================================
ARENA_WIDTH = 18
ARENA_HEIGHT = 32
RIVER_Y = 15  # River runs across rows 15-16 (centre of 32-tile arena)
BRIDGE_X_LEFT = 3    # centre of left bridge
BRIDGE_X_RIGHT = 14  # centre of right bridge
BRIDGE_WIDTH = 3     # each bridge is 3 tiles wide

# Tower positions (x, y) — y=0 is attacker's top edge, y=31 is defender's bottom edge
# Matched to reference grid screenshot
# Attacker towers (top half)
ATTACKER_KING_TOWER = (8.5, 2)
ATTACKER_LEFT_TOWER = (3, 6)
ATTACKER_RIGHT_TOWER = (14, 6)

# Defender towers (bottom half)
DEFENDER_LEFT_TOWER = (3, 25)
DEFENDER_RIGHT_TOWER = (14, 25)
DEFENDER_KING_TOWER = (8.5, 29)

# =============================================================================
# Game timing
# =============================================================================
TICK_DURATION = 0.5  # seconds per tick
MATCH_DURATION = 180.0  # 3 minutes
ELIXIR_RATE = 1.0 / 2.8  # elixir per second
ELIXIR_CAP = 10.0
DEPLOY_TIME = 1.0  # seconds (universal deploy delay)

# =============================================================================
# Speed categories → tiles per second
# =============================================================================
SPEED_MAP = {
    "slow": 45 / 60,       # 0.75 t/s
    "medium": 60 / 60,     # 1.0 t/s
    "fast": 90 / 60,       # 1.5 t/s
    "very_fast": 120 / 60, # 2.0 t/s
}


class TargetType(Enum):
    """What a unit can target."""
    GROUND = auto()
    AIR = auto()
    BUILDINGS = auto()
    AIR_AND_GROUND = auto()


class UnitTransport(Enum):
    """Whether a unit is ground or air."""
    GROUND = auto()
    AIR = auto()


class CardType(Enum):
    TROOP = auto()
    SPELL = auto()
    BUILDING = auto()


@dataclass(frozen=True)
class CardStats:
    name: str
    card_type: CardType
    elixir_cost: int
    # Troop stats
    hp: int = 0
    damage: int = 0
    hit_speed: float = 0.0  # seconds between attacks
    speed: str = "medium"  # key into SPEED_MAP
    range: float = 0.0  # tiles (0 = melee)
    targets: TargetType = TargetType.AIR_AND_GROUND
    transport: UnitTransport = UnitTransport.GROUND
    count: int = 1  # how many units spawn
    splash_radius: float = 0.0  # 0 = single target
    # Spell stats
    spell_damage: int = 0
    spell_radius: float = 0.0
    crown_tower_damage: int = 0


# =============================================================================
# Card database — Tournament Standard (Level 11)
# =============================================================================
CARDS = {
    "knight": CardStats(
        name="Knight",
        card_type=CardType.TROOP,
        elixir_cost=3,
        hp=1766,
        damage=202,
        hit_speed=1.2,
        speed="medium",
        range=1.2,  # melee medium
        targets=TargetType.AIR_AND_GROUND,
        transport=UnitTransport.GROUND,
        count=1,
    ),
    "giant": CardStats(
        name="Giant",
        card_type=CardType.TROOP,
        elixir_cost=5,
        hp=3968,
        damage=253,
        hit_speed=1.5,
        speed="slow",
        range=1.2,  # melee medium
        targets=TargetType.BUILDINGS,
        transport=UnitTransport.GROUND,
        count=1,
    ),
    "hog_rider": CardStats(
        name="Hog Rider",
        card_type=CardType.TROOP,
        elixir_cost=4,
        hp=1697,
        damage=317,
        hit_speed=1.6,
        speed="very_fast",
        range=0.8,  # melee short
        targets=TargetType.BUILDINGS,
        transport=UnitTransport.GROUND,
        count=1,
    ),
    "musketeer": CardStats(
        name="Musketeer",
        card_type=CardType.TROOP,
        elixir_cost=4,
        hp=721,
        damage=217,
        hit_speed=1.0,
        speed="medium",
        range=6.0,
        targets=TargetType.AIR_AND_GROUND,
        transport=UnitTransport.GROUND,
        count=1,
    ),
    "mini_pekka": CardStats(
        name="Mini PEKKA",
        card_type=CardType.TROOP,
        elixir_cost=4,
        hp=1390,
        damage=755,
        hit_speed=1.6,
        speed="fast",
        range=0.8,  # melee short
        targets=TargetType.GROUND,
        transport=UnitTransport.GROUND,
        count=1,
    ),
    "wizard": CardStats(
        name="Wizard",
        card_type=CardType.TROOP,
        elixir_cost=5,
        hp=755,
        damage=281,
        hit_speed=1.4,
        speed="medium",
        range=5.5,
        targets=TargetType.AIR_AND_GROUND,
        transport=UnitTransport.GROUND,
        count=1,
        splash_radius=1.5,
    ),
    "fireball": CardStats(
        name="Fireball",
        card_type=CardType.SPELL,
        elixir_cost=4,
        spell_damage=688,
        spell_radius=2.5,
        crown_tower_damage=207,
    ),
}


@dataclass(frozen=True)
class TowerStats:
    hp: int
    damage: int
    hit_speed: float
    range: float


PRINCESS_TOWER = TowerStats(hp=3052, damage=109, hit_speed=0.8, range=7.5)
KING_TOWER = TowerStats(hp=4824, damage=109, hit_speed=1.0, range=7.0)
