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

import math

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .constants import (
    ARENA_WIDTH, ARENA_HEIGHT, RIVER_Y, RIVER_HEIGHT, CARDS, ELIXIR_CAP,
    MATCH_DURATION, CardStats, CardType, TargetType, PRINCESS_TOWER, KING_TOWER,
)
try:
    from .c_engine import CArena as Arena, CSide as Side
    from .engine import Unit  # still needed for type hints
except ImportError:
    from .engine import Arena, Side, Unit


MAX_TRACKED_UNITS = 20  # max enemy units we encode in obs
UNIT_FEATURES = 5  # x, y, hp_ratio, speed_norm, is_building_targeter

# Grid resolution for card placement (tile-by-tile for precise positioning)
PLACE_GRID_X = 18  # 1 column per tile
PLACE_GRID_Y = 15  # 1 row per tile on defender's half (y=18..32)


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

        # Observation: towers(3) + elixir(1) + time(1) + crossed_bridge(1)
        #   + has_played(1) + units(MAX*FEATURES)
        obs_size = 3 + 1 + 1 + 1 + 1 + MAX_TRACKED_UNITS * UNIT_FEATURES
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
        """Convert grid coords to arena coords (defender's half, 1-indexed)."""
        x = 1 + (gx / (PLACE_GRID_X - 1)) * (ARENA_WIDTH - 1)
        # Defender places on their half: y from RIVER_Y+RIVER_HEIGHT to ARENA_HEIGHT
        y_min = RIVER_Y + RIVER_HEIGHT  # tile 18
        y_max = ARENA_HEIGHT            # tile 32
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

        # Has attacker crossed the bridge? (any attacker unit past the river)
        enemy_units = [
            u for u in state.units if u.side == Side.ATTACKER and u.alive
        ]
        obs[5] = 1.0 if any(u.y >= RIVER_Y + RIVER_HEIGHT for u in enemy_units) else 0.0

        # Has defender already played?
        obs[6] = 1.0 if self._defender_has_played else 0.0

        # Enemy units
        for i, unit in enumerate(enemy_units[:MAX_TRACKED_UNITS]):
            base = 7 + i * UNIT_FEATURES
            obs[base + 0] = (unit.x - 1) / (ARENA_WIDTH - 1)
            obs[base + 1] = (unit.y - 1) / (ARENA_HEIGHT - 1)
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
        ax = rng.uniform(3, ARENA_WIDTH - 2)
        ay = rng.uniform(2, RIVER_Y - 1)  # attacker's half (tiles 2..15)

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

        # Track attacker HP for dense reward
        self._prev_attacker_hp = sum(
            u.hp for u in self.arena.state.units if u.side == Side.ATTACKER
        )
        self._attacker_max_hp = self._prev_attacker_hp

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

        # ── Reward ─────────────────────────────────────────────────────
        # Primary objective: minimise tower damage taken.
        # All rewards are ONE-TIME signals — no per-tick accumulation.
        # Placement bonuses (timing, sight range) are small shaping signals;
        # the dominant reward is terminal HP preservation.
        reward = 0.0

        # 1. One-time placement shaping (fired once when card is played)
        #    Only timing signals — no sight range bonus, which was biasing
        #    the agent toward same-lane placement instead of optimal central pulls.
        if "played_card" in info:
            atk_units = [
                u for u in self.arena.state.units
                if u.side == Side.ATTACKER and u.alive
            ]
            if atk_units:
                # Timing: did attacker cross the bridge?
                bridge_y = RIVER_Y + RIVER_HEIGHT
                atk_crossed = any(u.y >= bridge_y for u in atk_units)
                if atk_crossed:
                    reward += 0.15  # good timing

                    # Extra for optimal timing (2-4 tiles past bridge)
                    furthest_y = max(u.y for u in atk_units)
                    tiles_past_bridge = furthest_y - bridge_y
                    if 2.0 <= tiles_past_bridge <= 4.0:
                        reward += 0.1
                else:
                    reward -= 0.3  # early placement penalty

        # 2. Terminal reward (episode end only) — dominated by HP preservation
        if done or truncated:
            current_tower_hp = sum(
                t.hp for t in self.arena.state.towers
                if t.side == Side.DEFENDER and t.tower_type == "princess"
            )
            hp_ratio = current_tower_hp / self._initial_tower_hp if self._initial_tower_hp > 0 else 1.0

            # HP preserved is the primary signal (up to +2.0)
            reward += 2.0 * hp_ratio

            # Small kill bonus — the kill will happen, but reward finishing
            kill_bonus = 1.0 if not attacker_units_alive else 0.0
            reward += 0.3 * kill_bonus

            # Penalty for never placing a card
            if not self._defender_has_played:
                reward -= 0.5

            info["reward_breakdown"] = {
                "hp_preserved": hp_ratio,
                "kill_bonus": kill_bonus,
                "never_placed_penalty": not self._defender_has_played,
            }

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
