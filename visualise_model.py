"""
Visualise a trained PPO model defending with Skeletons against Knight/Mini PEKKA.

Usage:
    python visualise_model.py                  # random attacker card
    python visualise_model.py knight           # specific attacker
    python visualise_model.py mini_pekka       # specific attacker

Controls:
    SPACE  — pause / resume
    R      — restart (new episode)
    ESC    — quit
    1-5    — change speed
"""

import sys
import pygame
from stable_baselines3 import PPO
from cr_sim.constants import (
    ARENA_WIDTH, ARENA_HEIGHT, RIVER_Y, RIVER_HEIGHT,
    BRIDGE_X_LEFT, BRIDGE_X_RIGHT, BRIDGE_WIDTH, CARDS,
    PRINCESS_TOWER, KING_TOWER,
    PRINCESS_TOWER_W, PRINCESS_TOWER_H, KING_TOWER_W, KING_TOWER_H,
)
from cr_sim.engine import Arena, Side
from cr_sim.env import ClashDefenseEnv, PLACE_GRID_X, PLACE_GRID_Y

# Import drawing helpers from visualise.py
from visualise import (
    TILE_SIZE, SIDEBAR_W, SCREEN_W, SCREEN_H, FPS_BASE,
    BG, ARENA_GREEN, RIVER_BLUE, BRIDGE_GREY, WHITE, GREY, GOLD,
    SIDEBAR_BG, ATK_RED, DEF_BLUE,
    tile_to_px, draw_hp_bar, draw_unit, draw_tower, draw_sidebar,
)


def run(atk_card: str | None = None):
    model = PPO.load("models/skeletons_defense")
    env = ClashDefenseEnv(
        defender_cards=["skeletons"],
        attacker_cards=[atk_card] if atk_card else ["knight", "mini_pekka"],
    )

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("CR Sim: Trained Model Defense")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("menlo", 14)
    font_sm = pygame.font.SysFont("menlo", 11)

    obs, info = env.reset()
    current_atk = info["attacker_card"]
    speed = 2
    paused = False
    finished = False
    episode_reward = 0.0
    step_count = 0
    model_action_info = ""

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    obs, info = env.reset()
                    current_atk = info["attacker_card"]
                    finished = False
                    paused = False
                    episode_reward = 0.0
                    step_count = 0
                    model_action_info = ""
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    speed = event.key - pygame.K_0

        # Model step
        if not paused and not finished:
            action, _ = model.predict(obs, deterministic=True)
            action = int(action)

            # Decode action for display
            if action == 0:
                model_action_info = "WAIT"
            else:
                a = action - 1
                n_places = PLACE_GRID_X * PLACE_GRID_Y
                card_idx = a // n_places
                remainder = a % n_places
                gx = remainder // PLACE_GRID_Y
                gy = remainder % PLACE_GRID_Y
                model_action_info = f"PLACE skeletons grid({gx},{gy})"

            obs, reward, done, truncated, info = env.step(action)
            episode_reward += reward
            step_count += 1

            if done or truncated:
                finished = True

        # ── Draw ──────────────────────────────────────────────────────
        screen.fill(BG)
        arena_rect = pygame.Rect(0, 0, ARENA_WIDTH * TILE_SIZE, ARENA_HEIGHT * TILE_SIZE)
        pygame.draw.rect(screen, ARENA_GREEN, arena_rect)

        # Grid lines
        for tx in range(ARENA_WIDTH + 1):
            x = tx * TILE_SIZE
            pygame.draw.line(screen, (40, 60, 40), (x, 0), (x, SCREEN_H), 1)
        for ty in range(ARENA_HEIGHT + 1):
            y = ty * TILE_SIZE
            pygame.draw.line(screen, (40, 60, 40), (0, y), (ARENA_WIDTH * TILE_SIZE, y), 1)

        # River
        ry_px = (RIVER_Y - 1) * TILE_SIZE
        river_h = RIVER_HEIGHT * TILE_SIZE
        river_rect = pygame.Rect(0, ry_px, ARENA_WIDTH * TILE_SIZE, river_h)
        pygame.draw.rect(screen, RIVER_BLUE, river_rect)

        # Bridges
        for bx in [BRIDGE_X_LEFT, BRIDGE_X_RIGHT]:
            first_bridge_tile = int(bx + 0.5 - BRIDGE_WIDTH / 2)
            bpx = (first_bridge_tile - 1) * TILE_SIZE
            bridge_rect = pygame.Rect(bpx, ry_px, BRIDGE_WIDTH * TILE_SIZE, river_h)
            pygame.draw.rect(screen, BRIDGE_GREY, bridge_rect)
            pygame.draw.rect(screen, WHITE, bridge_rect, 1)

        # Towers and units
        arena = env.arena
        if arena:
            for tower in arena.state.towers:
                draw_tower(screen, tower, font_sm)
            for unit in arena.state.units:
                if not unit.alive or not unit.deployed:
                    continue
                px, py = tile_to_px(unit.x, unit.y)
                is_atk = unit.side == Side.ATTACKER
                hp_ratio = unit.hp / unit.max_hp
                draw_unit(screen, unit.card_name, px, py, is_atk, hp_ratio)
                label = font_sm.render(unit.card_name[:6], True, WHITE)
                screen.blit(label, (px - label.get_width() // 2, py + 12))

        # Sidebar — model info
        x0 = ARENA_WIDTH * TILE_SIZE + 10
        pygame.draw.rect(screen, SIDEBAR_BG, (ARENA_WIDTH * TILE_SIZE, 0, SIDEBAR_W, SCREEN_H))

        lines = [
            ("MODEL DEFENSE", GOLD),
            ("", WHITE),
            (f"Attacker: {CARDS[current_atk].name}", ATK_RED),
            (f"Defender: Skeletons", DEF_BLUE),
            ("", WHITE),
            (f"Step: {step_count}", WHITE),
            (f"Reward: {episode_reward:.3f}", WHITE),
            ("", WHITE),
            (f"Action: {model_action_info}", GOLD),
        ]

        if arena:
            state = arena.state
            lines.append(("", WHITE))
            lines.append((f"Tick: {state.tick}", WHITE))
            lines.append((f"DEF elixir: {state.defender_elixir:.1f}", WHITE))
            lines.append(("", WHITE))

            atk_alive = sum(1 for u in state.units if u.side == Side.ATTACKER and u.alive)
            def_alive = sum(1 for u in state.units if u.side == Side.DEFENDER and u.alive)
            lines.append((f"ATK alive: {atk_alive}", ATK_RED))
            lines.append((f"DEF alive: {def_alive}", DEF_BLUE))

            for u in state.units:
                if u.alive:
                    side_str = "A" if u.side == Side.ATTACKER else "D"
                    col = ATK_RED if u.side == Side.ATTACKER else DEF_BLUE
                    lines.append((f"  [{side_str}] {u.card_name} {u.hp}hp", col))

        lines.append(("", WHITE))
        speed_str = f"Speed: {speed}x" + ("  PAUSED" if paused else "")
        lines.append((speed_str, GOLD))
        lines.append(("", WHITE))
        lines.append(("[SPACE] pause  [R] new", GREY))
        lines.append(("[1-5] speed   [ESC] quit", GREY))

        y = 10
        for text, colour in lines:
            if text:
                rendered = font_sm.render(text, True, colour)
                screen.blit(rendered, (x0, y))
            y += 16

        # Finished banner
        if finished:
            breakdown = info.get("reward_breakdown", {})
            kill = "KILLED" if breakdown.get("kill_bonus", 0) > 0 else "SURVIVED"
            banner_text = f"DONE — {kill} | reward: {episode_reward:.3f} | R to restart"
            banner = font.render(banner_text, True, GOLD)
            bx = (ARENA_WIDTH * TILE_SIZE - banner.get_width()) // 2
            by = SCREEN_H // 2 - 20
            pygame.draw.rect(screen, (0, 0, 0), (bx - 10, by - 5, banner.get_width() + 20, 30))
            screen.blit(banner, (bx, by))

        pygame.display.flip()
        clock.tick(FPS_BASE * speed)

    pygame.quit()
    env.close()


if __name__ == "__main__":
    card = sys.argv[1] if len(sys.argv) > 1 else None
    if card and card not in CARDS:
        print(f"Unknown card: {card}. Available: {list(CARDS.keys())}")
        sys.exit(1)
    run(card)
