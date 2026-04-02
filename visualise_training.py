"""
Live training visualiser: 20 arenas running simultaneously in a grid.
Watch the model learn in real-time.

Usage:
    python visualise_training.py                     # 200k steps (default)
    python visualise_training.py --timesteps 500000  # longer

Controls:
    1-5    — change speed (1=slow, 5=fast)
    ESC    — stop training and quit
"""

import argparse
import math
import pygame
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback
from cr_sim.constants import (
    ARENA_WIDTH, ARENA_HEIGHT, RIVER_Y, RIVER_HEIGHT,
    BRIDGE_X_LEFT, BRIDGE_X_RIGHT, BRIDGE_WIDTH,
    KING_TOWER_W, KING_TOWER_H, PRINCESS_TOWER_W, PRINCESS_TOWER_H,
)
from cr_sim.engine import Side
from cr_sim.env import ClashDefenseEnv

# ─── Grid layout ────────────────────────────────────────────────────────
GRID_COLS = 10
GRID_ROWS = 5
N_ENVS = GRID_COLS * GRID_ROWS  # 50

# ─── Mini arena rendering ───────────────────────────────────────────────
MINI_TILE = 8  # pixels per tile in mini view
MINI_W = ARENA_WIDTH * MINI_TILE
MINI_H = ARENA_HEIGHT * MINI_TILE
PAD = 3

# ─── Window ─────────────────────────────────────────────────────────────
STATUS_H = 36
WIN_W = GRID_COLS * (MINI_W + PAD) + PAD
WIN_H = GRID_ROWS * (MINI_H + PAD) + PAD + STATUS_H

# ─── Colours ────────────────────────────────────────────────────────────
BG = (10, 14, 28)
ARENA_GREEN = (25, 42, 25)
RIVER_BLUE = (50, 120, 180)
BRIDGE_GREY = (80, 80, 80)
ATK_RED = (220, 55, 65)
DEF_BLUE = (65, 135, 225)
TOWER_ATK = (160, 45, 45)
TOWER_DEF = (45, 90, 145)
KING_ATK = (185, 55, 55)
KING_DEF = (55, 110, 170)
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)
GREY = (120, 120, 120)
DARK_BG = (12, 16, 32)
GREEN_OK = (46, 204, 113)
RED_BAD = (231, 76, 60)

FPS_BASE = 10


def mini_tile_to_px(tx, ty):
    """Convert 1-indexed tile to pixel within a mini arena."""
    return int((tx - 0.5) * MINI_TILE), int((ty - 0.5) * MINI_TILE)


def draw_mini_arena(surface, env, x0, y0):
    """Draw a single mini arena at offset (x0, y0)."""
    arena = env.arena
    if arena is None:
        return

    state = arena.state
    sub = surface.subsurface(pygame.Rect(x0, y0, MINI_W, MINI_H))

    # Background
    sub.fill(ARENA_GREEN)

    # River
    ry_px = (RIVER_Y - 1) * MINI_TILE
    river_h = RIVER_HEIGHT * MINI_TILE
    pygame.draw.rect(sub, RIVER_BLUE, (0, ry_px, MINI_W, river_h))

    # Bridges
    for bx in [BRIDGE_X_LEFT, BRIDGE_X_RIGHT]:
        ft = int(bx + 0.5 - BRIDGE_WIDTH / 2)
        bpx = (ft - 1) * MINI_TILE
        pygame.draw.rect(sub, BRIDGE_GREY, (bpx, ry_px, BRIDGE_WIDTH * MINI_TILE, river_h))

    # Towers
    for tower in state.towers:
        is_king = tower.tower_type == "king"
        is_atk = tower.side == Side.ATTACKER
        if is_king:
            tw, th = KING_TOWER_W, KING_TOWER_H
            colour = KING_ATK if is_atk else KING_DEF
        else:
            tw, th = PRINCESS_TOWER_W, PRINCESS_TOWER_H
            colour = TOWER_ATK if is_atk else TOWER_DEF

        ftx = int(tower.x + 0.5 - tw / 2)
        fty = int(tower.y + 0.5 - th / 2)
        rect = pygame.Rect((ftx - 1) * MINI_TILE, (fty - 1) * MINI_TILE,
                           tw * MINI_TILE, th * MINI_TILE)

        if tower.alive:
            pygame.draw.rect(sub, colour, rect)
        else:
            pygame.draw.rect(sub, (40, 40, 40), rect)

    # Units
    for unit in state.units:
        if not unit.alive or not unit.deployed:
            continue
        px, py = mini_tile_to_px(unit.x, unit.y)
        is_atk = unit.side == Side.ATTACKER
        colour = ATK_RED if is_atk else DEF_BLUE
        radius = 2 if unit.card_name == "Skeletons" else 4
        pygame.draw.circle(sub, colour, (px, py), radius)

    # Thin border
    pygame.draw.rect(surface, GREY, (x0, y0, MINI_W, MINI_H), 1)


class VisualCallback(BaseCallback):
    """Renders all training envs each step, handles pygame events."""

    def __init__(self, screen, clock, font, total_timesteps):
        super().__init__()
        self.screen = screen
        self.clock = clock
        self.font = font
        self.speed = 2
        self.total_timesteps = total_timesteps
        self.quit_requested = False
        self.ep_rewards = []
        self.recent_kills = 0
        self.recent_total = 0

    def _on_step(self) -> bool:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_requested = True
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit_requested = True
                    return False
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    self.speed = event.key - pygame.K_0

        # Track episode stats from infos
        if self.locals.get("infos"):
            for info in self.locals["infos"]:
                if "reward_breakdown" in info:
                    self.recent_total += 1
                    if info["reward_breakdown"].get("kill_bonus", 0) > 0:
                        self.recent_kills += 1

        # Draw
        self.screen.fill(BG)

        # Draw all 20 mini arenas
        envs = self.training_env.envs
        for i, env in enumerate(envs):
            col = i % GRID_COLS
            row = i // GRID_COLS
            x0 = PAD + col * (MINI_W + PAD)
            y0 = PAD + row * (MINI_H + PAD)
            draw_mini_arena(self.screen, env, x0, y0)

        # Status bar
        status_y = WIN_H - STATUS_H + 8
        steps = self.num_timesteps
        pct = min(100, steps / self.total_timesteps * 100)

        kill_rate_str = ""
        if self.recent_total > 0:
            kill_rate = self.recent_kills / self.recent_total
            kill_rate_str = f"  |  Kill rate: {kill_rate:.0%} ({self.recent_kills}/{self.recent_total})"
            # Reset every 100 episodes for rolling average
            if self.recent_total >= 100:
                self.recent_kills = 0
                self.recent_total = 0

        ep_rew = self.locals.get("rewards")
        rew_str = ""
        if ep_rew is not None:
            import numpy as np
            rew_str = f"  |  Step rew: {float(np.mean(ep_rew)):.3f}"

        status = f"Steps: {steps:,}/{self.total_timesteps:,} ({pct:.0f}%){rew_str}{kill_rate_str}  |  Speed: {self.speed}x  |  [1-5] speed  [ESC] quit"
        text = self.font.render(status, True, WHITE)
        self.screen.blit(text, (PAD, status_y))

        # Progress bar
        bar_y = status_y + 20
        bar_w = WIN_W - 2 * PAD
        pygame.draw.rect(self.screen, (40, 40, 40), (PAD, bar_y, bar_w, 6))
        fill_w = int(bar_w * pct / 100)
        bar_colour = GREEN_OK if pct < 100 else GOLD
        pygame.draw.rect(self.screen, bar_colour, (PAD, bar_y, fill_w, 6))

        pygame.display.flip()
        self.clock.tick(FPS_BASE * self.speed)

        return True


def make_env():
    return ClashDefenseEnv(
        defender_cards=["skeletons"],
        attacker_cards=["knight", "mini_pekka"],
    )


def run(timesteps: int = 200_000):
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption(f"CR Training: {N_ENVS} arenas | {timesteps:,} steps")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("menlo", 10)

    env = DummyVecEnv([make_env for _ in range(N_ENVS)])

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        verbose=0,
    )

    callback = VisualCallback(screen, clock, font, timesteps)

    print(f"Training with live visualisation: {N_ENVS} envs, {timesteps:,} steps")
    print("Controls: 1-5 = speed, ESC = quit")

    model.learn(total_timesteps=timesteps, callback=callback)

    if not callback.quit_requested:
        model.save("models/skeletons_defense")
        print("Training complete! Model saved to models/skeletons_defense.zip")

        # Wait for user to close
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN):
                    waiting = False

    pygame.quit()
    env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=200_000)
    args = parser.parse_args()
    run(args.timesteps)
