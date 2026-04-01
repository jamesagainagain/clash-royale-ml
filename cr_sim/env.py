"""
Gymnasium environment for Clash Royale defense training (Phase 1).

Scenario: Attacker plays ONE card. Defender must choose a card + placement
to minimize damage to their towers.

Observation space:
  - Defender's 2 princess towers HP (normalized 0-1)
  - Defender's king tower HP (normalized 0-1)
  - Defender's elixir (normalized 0-1)
  - For each enemy unit on field (up to MAX_TRACKED_UNITS):
    - x, y (normalized to arena)
    - hp (normalized to max_hp)
    - speed category (normalized)
    - is_building_targeter (0 or 1)
  - Time remaining (normalized 0-1)

Action space (Discrete):
  - 0 = do nothing
  - 1..N = play card_i at tile (x, y)
  - Factored: card_index × grid_x × grid_y
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .constants import (
    ARENA_WIDTH, ARENA_HEIGHT, RIVER_Y, CARDS, ELIXIR_CAP, MATCH_DURATION,
    CardStats, CardType, TargetType, PRINCESS_TOWER, KING_TOWER,
)
from .engine import Arena, Side, Unit


MAX_TRACKED_UNITS = 20  # max enemy units we encode in obs
UNIT_FEATURES = 5  # x, y, hp_ratio, speed_norm, is_building_targeter

# Grid resolution for card placement (coarser than full arena for tractable action space)
PLACE_GRID_X = 9   # 9 columns (every 2 tiles)
PLACE_GRID_Y = 8   # 8 rows on defender's half


class ClashDefenseEnv(gym.Env):
    """
    Phase 1 defense environment.

    Each episode:
      1. Attacker plays a random card at a random position toward the defender.
      2. Defender has `decision_ticks` ticks to play a card.
      3. Simulation runs until all attacker units are dead or towers are hit.
      4. Reward = tower HP preserved (negative for damage taken).
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        defender_cards: list[str] | None = None,
        attacker_cards: list[str] | None = None,
        render_mode: str | None = None,
    ):
        super().__init__()

        self.defender_cards = defender_cards or [
            "knight", "musketeer", "mini_pekka", "wizard", "fireball",
        ]
        self.attacker_cards = attacker_cards or [
            "knight", "giant", "hog_rider", "musketeer", "wizard",
        ]
        self.render_mode = render_mode
        self.arena: Arena | None = None

        n_cards = len(self.defender_cards)
        # Actions: 0=wait, then card_idx * grid_x * grid_y + 1 for each placement
        self.n_actions = 1 + n_cards * PLACE_GRID_X * PLACE_GRID_Y
        self.action_space = spaces.Discrete(self.n_actions)

        # Observation: towers(3) + elixir(1) + time(1) + units(MAX*FEATURES)
        obs_size = 3 + 1 + 1 + MAX_TRACKED_UNITS * UNIT_FEATURES
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_size,), dtype=np.float32
        )

    def _decode_action(self, action: int) -> tuple[int, int, int] | None:
        """Decode action int → (card_idx, grid_x, grid_y) or None for wait."""
        if action == 0:
            return None
        action -= 1
        n_places = PLACE_GRID_X * PLACE_GRID_Y
        card_idx = action // n_places
        remainder = action % n_places
        gx = remainder // PLACE_GRID_Y
        gy = remainder % PLACE_GRID_Y
        return card_idx, gx, gy

    def _grid_to_arena(self, gx: int, gy: int) -> tuple[float, float]:
        """Convert grid coords to arena coords (defender's half)."""
        x = (gx / (PLACE_GRID_X - 1)) * (ARENA_WIDTH - 1)
        # Defender places on their half: y from RIVER_Y+2 to ARENA_HEIGHT-3
        y_min = RIVER_Y + 2  # row 17
        y_max = ARENA_HEIGHT - 3  # row 29
        y = y_min + (gy / (PLACE_GRID_Y - 1)) * (y_max - y_min)
        return x, y

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(self.observation_space.shape, dtype=np.float32)
        state = self.arena.state

        # Tower HP (defender's towers, normalized)
        def_towers = [t for t in state.towers if t.side == Side.DEFENDER]
        princess_towers = [t for t in def_towers if t.tower_type == "princess"]
        king_towers = [t for t in def_towers if t.tower_type == "king"]

        if len(princess_towers) >= 2:
            obs[0] = princess_towers[0].hp / princess_towers[0].max_hp
            obs[1] = princess_towers[1].hp / princess_towers[1].max_hp
        if king_towers:
            obs[2] = king_towers[0].hp / king_towers[0].max_hp

        obs[3] = state.defender_elixir / ELIXIR_CAP
        obs[4] = max(0, (MATCH_DURATION - state.time) / MATCH_DURATION)

        # Enemy units (attacker's units)
        enemy_units = [
            u for u in state.units if u.side == Side.ATTACKER and u.alive
        ]
        for i, unit in enumerate(enemy_units[:MAX_TRACKED_UNITS]):
            base = 5 + i * UNIT_FEATURES
            obs[base + 0] = unit.x / (ARENA_WIDTH - 1)
            obs[base + 1] = unit.y / (ARENA_HEIGHT - 1)
            obs[base + 2] = unit.hp / unit.max_hp
            obs[base + 3] = unit.speed / 2.0  # normalize (max is 2.0 t/s)
            obs[base + 4] = 1.0 if unit.targets == TargetType.BUILDINGS else 0.0

        return obs

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.arena = Arena()

        # Record initial tower HP for reward calculation
        self._initial_tower_hp = sum(
            t.hp for t in self.arena.state.towers
            if t.side == Side.DEFENDER and t.tower_type == "princess"
        )

        # Attacker plays one random card
        rng = self.np_random
        card_key = rng.choice(self.attacker_cards)
        card = CARDS[card_key]

        # Attacker places near top of arena, random x, heading toward defender
        ax = rng.uniform(2, ARENA_WIDTH - 3)
        ay = rng.uniform(2, 14)  # attacker's half

        # Give both sides enough elixir
        self.arena.state.attacker_elixir = 10.0
        self.arena.state.defender_elixir = 10.0
        self.arena.spawn_card(card, Side.ATTACKER, ax, ay)

        self._defender_has_played = False
        self._defender_elixir_spent = 0  # track total elixir used by defender
        self._attacker_elixir_cost = card.elixir_cost
        self._ticks_since_play = 0
        self._episode_ticks = 0
        self._max_idle_ticks = 200  # end if nothing happening

        return self._get_obs(), {"attacker_card": card_key}

    def step(self, action: int):
        assert self.arena is not None

        reward = 0.0
        info = {}

        # Decode and execute defender action
        decoded = self._decode_action(action)
        if decoded is not None and not self._defender_has_played:
            card_idx, gx, gy = decoded
            if 0 <= card_idx < len(self.defender_cards):
                card_key = self.defender_cards[card_idx]
                card = CARDS[card_key]
                x, y = self._grid_to_arena(gx, gy)
                played = self.arena.spawn_card(card, Side.DEFENDER, x, y)
                if played:
                    self._defender_has_played = True
                    self._defender_elixir_spent += card.elixir_cost
                    info["played_card"] = card_key
                    info["placement"] = (x, y)

        # Advance simulation
        self.arena.tick()
        self._episode_ticks += 1

        # Check if fight is over (all attacker units dead or towers destroyed)
        attacker_units_alive = any(
            u.side == Side.ATTACKER and u.alive for u in self.arena.state.units
        )
        defender_units_alive = any(
            u.side == Side.DEFENDER and u.alive for u in self.arena.state.units
        )

        done = False
        truncated = False

        if self.arena.state.game_over:
            done = True
        elif not attacker_units_alive and self._defender_has_played:
            # All attackers dead — defense succeeded
            done = True
        elif self._episode_ticks > self._max_idle_ticks:
            truncated = True

        # ── Reward (only at episode end for stability) ──────────────────
        if done or truncated:
            # Component 1: Tower HP preserved (0 to 1, higher = less damage taken)
            current_tower_hp = sum(
                t.hp for t in self.arena.state.towers
                if t.side == Side.DEFENDER and t.tower_type == "princess"
            )
            hp_preserved = current_tower_hp / self._initial_tower_hp  # 1.0 = no damage

            # Component 2: Elixir efficiency
            # Positive trade = spent less elixir than attacker, negative = overspent
            # Range roughly -1 to +1: e.g. spent 3 to defend 5 → +0.2, spent 5 to defend 3 → -0.2
            elixir_trade = (self._attacker_elixir_cost - self._defender_elixir_spent) / ELIXIR_CAP

            # Component 3: Kill bonus (did all attackers die?)
            kill_bonus = 0.3 if not attacker_units_alive else 0.0

            # Weighted sum — tower HP matters most, but efficiency is rewarded
            reward = (
                0.5 * hp_preserved      # protect towers
                + 0.3 * elixir_trade    # spend efficiently
                + 0.2 * kill_bonus      # clean up attackers
            )
            info["reward_breakdown"] = {
                "hp_preserved": hp_preserved,
                "elixir_trade": elixir_trade,
                "kill_bonus": kill_bonus,
            }
        else:
            reward = 0.0  # no intermediate reward — only score at the end

        obs = self._get_obs()
        return obs, reward, done, truncated, info

    def render(self):
        if self.render_mode != "human":
            return
        state = self.arena.state
        print(f"\n--- Tick {state.tick} | Time {state.time:.1f}s ---")
        print(f"Defender elixir: {state.defender_elixir:.1f}")
        for t in state.towers:
            if t.side == Side.DEFENDER:
                status = "ACTIVE" if t.active else "inactive"
                print(f"  {t.tower_type} ({t.x},{t.y}): {t.hp}/{t.max_hp} [{status}]")
        for u in state.units:
            side = "ATK" if u.side == Side.ATTACKER else "DEF"
            print(f"  [{side}] {u.card_name} ({u.x:.1f},{u.y:.1f}) HP:{u.hp}")
