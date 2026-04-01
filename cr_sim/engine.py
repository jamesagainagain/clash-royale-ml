"""
Core game engine: units, towers, arena, and tick-based simulation.

Faithful targeting rules:
  - BUILDINGS-targeting units (Giant, Hog) → nearest building/tower
  - AIR_AND_GROUND units → nearest enemy (troop or tower)
  - Towers → nearest enemy in range

Movement: units walk toward their target each tick.
Combat: units attack when in range, respecting hit_speed cooldowns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto

from .constants import (
    ARENA_WIDTH, ARENA_HEIGHT, RIVER_Y,
    BRIDGE_X_LEFT, BRIDGE_X_RIGHT, BRIDGE_WIDTH,
    TICK_DURATION, SPEED_MAP,
    DEFENDER_LEFT_TOWER, DEFENDER_RIGHT_TOWER, DEFENDER_KING_TOWER,
    ATTACKER_LEFT_TOWER, ATTACKER_RIGHT_TOWER, ATTACKER_KING_TOWER,
    PRINCESS_TOWER, KING_TOWER,
    CardStats, CardType, TargetType, UnitTransport,
    ELIXIR_RATE, ELIXIR_CAP, MATCH_DURATION, DEPLOY_TIME,
)


class Side(Enum):
    ATTACKER = auto()
    DEFENDER = auto()


# ─────────────────────────────────────────────────────────────────────────────
# Unit (troop instance on the field)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Unit:
    card_name: str
    side: Side
    x: float
    y: float
    hp: int
    max_hp: int
    damage: int
    hit_speed: float  # seconds between attacks
    speed: float  # tiles per second
    range: float  # attack range in tiles
    targets: TargetType
    transport: UnitTransport
    splash_radius: float = 0.0
    attack_cooldown: float = 0.0  # seconds until next attack
    deploy_timer: float = DEPLOY_TIME  # seconds until active

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def deployed(self) -> bool:
        return self.deploy_timer <= 0


# ─────────────────────────────────────────────────────────────────────────────
# Tower
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Tower:
    side: Side
    tower_type: str  # "princess" or "king"
    x: float
    y: float
    hp: int
    max_hp: int
    damage: int
    hit_speed: float
    range: float
    attack_cooldown: float = 0.0
    active: bool = True  # king tower starts inactive

    @property
    def alive(self) -> bool:
        return self.hp > 0


# ─────────────────────────────────────────────────────────────────────────────
# Game State
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class GameState:
    tick: int = 0
    time: float = 0.0
    units: list[Unit] = field(default_factory=list)
    towers: list[Tower] = field(default_factory=list)
    attacker_elixir: float = 5.0
    defender_elixir: float = 5.0
    game_over: bool = False
    winner: Optional[Side] = None


def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _find_nearest_target(
    unit: Unit,
    enemies: list[Unit | Tower],
) -> Optional[Unit | Tower]:
    """Find the nearest valid target for a unit following CR targeting rules."""
    best = None
    best_dist = float("inf")

    for enemy in enemies:
        if isinstance(enemy, Unit):
            if not enemy.alive or not enemy.deployed:
                continue
            # BUILDINGS-only units ignore enemy troops
            if unit.targets == TargetType.BUILDINGS:
                continue
        elif isinstance(enemy, Tower):
            if not enemy.alive:
                continue
            # Non-active king tower can't be targeted unless princess towers are down
            # (handled in the caller by filtering)
        else:
            continue

        d = _dist(unit.x, unit.y, enemy.x, enemy.y)
        if d < best_dist:
            best_dist = d
            best = enemy

    # For BUILDINGS-targeting units, find nearest tower
    if unit.targets == TargetType.BUILDINGS and best is None:
        for enemy in enemies:
            if isinstance(enemy, Tower) and enemy.alive:
                d = _dist(unit.x, unit.y, enemy.x, enemy.y)
                if d < best_dist:
                    best_dist = d
                    best = enemy

    return best


def _find_nearest_tower_target(
    tower: Tower,
    enemies: list[Unit],
) -> Optional[Unit]:
    """Towers target the nearest enemy unit in range."""
    best = None
    best_dist = float("inf")
    for enemy in enemies:
        if not enemy.alive or not enemy.deployed:
            continue
        d = _dist(tower.x, tower.y, enemy.x, enemy.y)
        if d <= tower.range and d < best_dist:
            best_dist = d
            best = enemy
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Arena (the game engine)
# ─────────────────────────────────────────────────────────────────────────────
class Arena:
    def __init__(self) -> None:
        self.state = GameState()
        self._init_towers()

    def _init_towers(self) -> None:
        """Place all 6 towers (3 per side)."""
        for pos, ttype, stats, side in [
            (DEFENDER_LEFT_TOWER, "princess", PRINCESS_TOWER, Side.DEFENDER),
            (DEFENDER_RIGHT_TOWER, "princess", PRINCESS_TOWER, Side.DEFENDER),
            (DEFENDER_KING_TOWER, "king", KING_TOWER, Side.DEFENDER),
            (ATTACKER_LEFT_TOWER, "princess", PRINCESS_TOWER, Side.ATTACKER),
            (ATTACKER_RIGHT_TOWER, "princess", PRINCESS_TOWER, Side.ATTACKER),
            (ATTACKER_KING_TOWER, "king", KING_TOWER, Side.ATTACKER),
        ]:
            is_king = ttype == "king"
            self.state.towers.append(Tower(
                side=side,
                tower_type=ttype,
                x=pos[0],
                y=pos[1],
                hp=stats.hp,
                max_hp=stats.hp,
                damage=stats.damage,
                hit_speed=stats.hit_speed,
                range=stats.range,
                active=not is_king,  # king towers start inactive
            ))

    def get_elixir(self, side: Side) -> float:
        if side == Side.ATTACKER:
            return self.state.attacker_elixir
        return self.state.defender_elixir

    def _spend_elixir(self, side: Side, cost: int) -> bool:
        if side == Side.ATTACKER:
            if self.state.attacker_elixir >= cost:
                self.state.attacker_elixir -= cost
                return True
        else:
            if self.state.defender_elixir >= cost:
                self.state.defender_elixir -= cost
                return True
        return False

    def spawn_card(self, card: CardStats, side: Side, x: float, y: float) -> bool:
        """Attempt to play a card at (x, y). Returns True if successful."""
        if not self._spend_elixir(side, card.elixir_cost):
            return False

        if card.card_type == CardType.SPELL:
            self._apply_spell(card, side, x, y)
            return True

        # Clamp to valid deployment zone (own half)
        if side == Side.ATTACKER:
            y = min(y, RIVER_Y - 1)
        else:
            y = max(y, RIVER_Y + 1)
        x = max(0, min(x, ARENA_WIDTH - 1))

        for i in range(card.count):
            # Slight offset if multiple units (future swarm cards)
            offset_x = (i % 5 - 2) * 0.5 if card.count > 1 else 0.0
            offset_y = (i // 5 - 1) * 0.5 if card.count > 1 else 0.0
            unit = Unit(
                card_name=card.name,
                side=side,
                x=x + offset_x,
                y=y + offset_y,
                hp=card.hp,
                max_hp=card.hp,
                damage=card.damage,
                hit_speed=card.hit_speed,
                speed=SPEED_MAP.get(card.speed, 1.0),
                range=card.range,
                targets=card.targets,
                transport=card.transport,
                splash_radius=card.splash_radius,
            )
            self.state.units.append(unit)
        return True

    def _apply_spell(self, card: CardStats, side: Side, x: float, y: float) -> None:
        """Apply instant spell damage."""
        for unit in self.state.units:
            if unit.side != side and unit.alive:
                if _dist(x, y, unit.x, unit.y) <= card.spell_radius:
                    unit.hp -= card.spell_damage

        for tower in self.state.towers:
            if tower.side != side and tower.alive:
                if _dist(x, y, tower.x, tower.y) <= card.spell_radius:
                    tower.hp -= card.crown_tower_damage
                    self._check_king_activation(tower)

    def _check_king_activation(self, damaged_tower: Tower) -> None:
        """Activate king tower if it was hit, or if a princess tower was destroyed."""
        side = damaged_tower.side
        king = next(
            (t for t in self.state.towers if t.side == side and t.tower_type == "king"),
            None,
        )
        if king is None or king.active:
            return

        # King activates if directly damaged
        if damaged_tower.tower_type == "king":
            king.active = True
            return

        # King activates if a princess tower is destroyed
        if not damaged_tower.alive:
            king.active = True

    def _get_targetable_enemies(self, unit: Unit) -> list[Unit | Tower]:
        """Return all valid enemy targets for a unit."""
        enemies: list[Unit | Tower] = []
        for u in self.state.units:
            if u.side != unit.side and u.alive and u.deployed:
                enemies.append(u)
        for t in self.state.towers:
            if t.side != unit.side and t.alive:
                # Can only target king tower if it's active or both princess towers dead
                if t.tower_type == "king":
                    princess_alive = any(
                        tw.side == t.side and tw.tower_type == "princess" and tw.alive
                        for tw in self.state.towers
                    )
                    if princess_alive:
                        continue  # skip king tower, princess still standing
                enemies.append(t)
        return enemies

    def tick(self) -> None:
        """Advance the simulation by one tick (TICK_DURATION seconds)."""
        if self.state.game_over:
            return

        dt = TICK_DURATION
        self.state.tick += 1
        self.state.time += dt

        # Regenerate elixir
        self.state.attacker_elixir = min(
            ELIXIR_CAP, self.state.attacker_elixir + ELIXIR_RATE * dt
        )
        self.state.defender_elixir = min(
            ELIXIR_CAP, self.state.defender_elixir + ELIXIR_RATE * dt
        )

        # Deploy timers
        for unit in self.state.units:
            if not unit.deployed:
                unit.deploy_timer -= dt

        # Unit AI: find target, move, attack
        for unit in self.state.units:
            if not unit.alive or not unit.deployed:
                continue

            enemies = self._get_targetable_enemies(unit)
            target = _find_nearest_target(unit, enemies)
            if target is None:
                continue

            dist = _dist(unit.x, unit.y, target.x, target.y)

            # Move toward target if out of range
            if dist > unit.range:
                move_dist = unit.speed * dt
                dx = target.x - unit.x
                dy = target.y - unit.y
                norm = math.hypot(dx, dy)
                if norm > 0:
                    # Bridge constraint: units must cross river via bridges
                    new_x = unit.x + (dx / norm) * move_dist
                    new_y = unit.y + (dy / norm) * move_dist
                    new_x, new_y = self._apply_bridge_constraint(
                        unit, new_x, new_y
                    )
                    unit.x = max(0, min(new_x, ARENA_WIDTH - 1))
                    unit.y = max(0, min(new_y, ARENA_HEIGHT - 1))
            else:
                # In range — attack if cooldown is ready
                unit.attack_cooldown -= dt
                if unit.attack_cooldown <= 0:
                    self._attack(unit, target)
                    unit.attack_cooldown = unit.hit_speed

        # Tower attacks
        for tower in self.state.towers:
            if not tower.alive or not tower.active:
                continue
            enemy_units = [
                u for u in self.state.units
                if u.side != tower.side and u.alive and u.deployed
            ]
            target = _find_nearest_tower_target(tower, enemy_units)
            if target is not None:
                tower.attack_cooldown -= dt
                if tower.attack_cooldown <= 0:
                    target.hp -= tower.damage
                    tower.attack_cooldown = tower.hit_speed

        # Remove dead units
        self.state.units = [u for u in self.state.units if u.alive]

        # Check win conditions
        self._check_win()

    def _apply_bridge_constraint(
        self, unit: Unit, new_x: float, new_y: float
    ) -> tuple[float, float]:
        """Force ground units to cross the river only via bridges."""
        if unit.transport == UnitTransport.AIR:
            return new_x, new_y

        old_side_of_river = unit.y < RIVER_Y
        new_side_of_river = new_y < RIVER_Y

        # Not crossing the river
        if old_side_of_river == new_side_of_river:
            return new_x, new_y

        # Crossing — must go through a bridge
        left_bridge_dist = abs(unit.x - BRIDGE_X_LEFT)
        right_bridge_dist = abs(unit.x - BRIDGE_X_RIGHT)

        if left_bridge_dist <= right_bridge_dist:
            bridge_x = BRIDGE_X_LEFT
        else:
            bridge_x = BRIDGE_X_RIGHT

        # If not within the bridge width, redirect toward the nearest one
        half_w = BRIDGE_WIDTH / 2
        if abs(unit.x - bridge_x) > half_w:
            return bridge_x, unit.y  # move toward bridge, don't cross yet
        else:
            return new_x, new_y  # within bridge width, allow crossing

    def _attack(self, attacker: Unit, target: Unit | Tower) -> None:
        """Apply damage from attacker to target (with splash if applicable)."""
        if attacker.splash_radius > 0:
            # Splash: damage all enemies near the target
            for entity in self.state.units + self.state.towers:
                if isinstance(entity, Unit):
                    if entity.side == attacker.side or not entity.alive:
                        continue
                elif isinstance(entity, Tower):
                    if entity.side == attacker.side or not entity.alive:
                        continue
                else:
                    continue
                if _dist(target.x, target.y, entity.x, entity.y) <= attacker.splash_radius:
                    entity.hp -= attacker.damage
                    if isinstance(entity, Tower):
                        self._check_king_activation(entity)
        else:
            target.hp -= attacker.damage
            if isinstance(target, Tower):
                self._check_king_activation(target)

    def _check_win(self) -> None:
        """Check if either king tower is destroyed or time is up."""
        for tower in self.state.towers:
            if tower.tower_type == "king" and not tower.alive:
                self.state.game_over = True
                self.state.winner = (
                    Side.DEFENDER if tower.side == Side.ATTACKER else Side.ATTACKER
                )
                return

        if self.state.time >= MATCH_DURATION:
            self.state.game_over = True
            # Compare crown tower damage
            atk_hp = sum(
                t.hp for t in self.state.towers
                if t.side == Side.ATTACKER and t.tower_type == "princess"
            )
            def_hp = sum(
                t.hp for t in self.state.towers
                if t.side == Side.DEFENDER and t.tower_type == "princess"
            )
            if atk_hp > def_hp:
                self.state.winner = Side.DEFENDER  # attacker's towers healthier = defender lost more
            elif def_hp > atk_hp:
                self.state.winner = Side.ATTACKER
            else:
                self.state.winner = None  # draw

    def get_tower_hp(self, side: Side) -> dict[str, int]:
        """Get HP of all towers for a side."""
        result = {}
        for t in self.state.towers:
            if t.side == side:
                if t.tower_type == "king":
                    label = "king"
                else:
                    label = f"princess_{'left' if t.x < ARENA_WIDTH // 2 else 'right'}"
                result[label] = t.hp
        return result
