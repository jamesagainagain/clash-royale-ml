"""
Watch the trained model defend in real-time.

Usage:
    python watch_trained.py                          # 20 arenas, default model
    python watch_trained.py --model models/best/best_model
    python watch_trained.py --arenas 50

Controls:
    1-5    — change speed (1=slow, 5=fast)
    R      — reset all arenas
    ESC    — quit
"""

import argparse
import pygame
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from cr_sim.env import ClashDefenseEnv
from visualise_training import (
    MINI_TILE, MINI_W, MINI_H, PAD, STATUS_H, FPS_BASE,
    BG, WHITE, GOLD, GREY, GREEN_OK,
    draw_mini_arena,
)
from cr_sim.engine import Side
import numpy as np


def make_env():
    return ClashDefenseEnv(
        defender_cards=["skeletons"],
        attacker_cards=["knight", "mini_pekka"],
    )


def run(model_path: str, n_arenas: int):
    # Grid layout: aim for roughly 16:9 aspect ratio
    cols = min(n_arenas, 10)
    rows = (n_arenas + cols - 1) // cols

    win_w = cols * (MINI_W + PAD) + PAD
    win_h = rows * (MINI_H + PAD) + PAD + STATUS_H

    pygame.init()
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption(f"Trained Agent — {n_arenas} arenas")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("menlo", 10)

    envs = DummyVecEnv([make_env for _ in range(n_arenas)])
    model = PPO.load(model_path)

    obs = envs.reset()
    speed = 2
    total_eps = 0
    total_kills = 0
    total_hp_preserved = 0.0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    obs = envs.reset()
                    total_eps = total_kills = 0
                    total_hp_preserved = 0.0
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    speed = event.key - pygame.K_0

        # Step all envs with trained policy
        actions, _ = model.predict(obs, deterministic=True)
        obs, rewards, dones, infos = envs.step(actions)

        # Track stats
        for info in infos:
            if "reward_breakdown" in info:
                total_eps += 1
                if info["reward_breakdown"].get("kill_bonus", 0) > 0:
                    total_kills += 1
                total_hp_preserved += info["reward_breakdown"].get("hp_preserved", 0)

        # Draw
        screen.fill(BG)
        for i, env in enumerate(envs.envs):
            col = i % cols
            row = i // cols
            x0 = PAD + col * (MINI_W + PAD)
            y0 = PAD + row * (MINI_H + PAD)
            draw_mini_arena(screen, env, x0, y0)

        # Status bar
        status_y = win_h - STATUS_H + 8
        kill_str = ""
        hp_str = ""
        if total_eps > 0:
            kill_str = f"  |  Kill rate: {total_kills / total_eps:.0%}"
            hp_str = f"  |  Avg HP preserved: {total_hp_preserved / total_eps:.0%}"

        status = f"Episodes: {total_eps}{kill_str}{hp_str}  |  Speed: {speed}x  |  [1-5] speed  [R] reset  [ESC] quit"
        text = font.render(status, True, WHITE)
        screen.blit(text, (PAD, status_y))

        pygame.display.flip()
        clock.tick(FPS_BASE * speed)

    pygame.quit()
    envs.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/skeletons_defense")
    parser.add_argument("--arenas", type=int, default=20)
    args = parser.parse_args()
    run(args.model, args.arenas)
