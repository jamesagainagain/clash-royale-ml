"""
Real-time Clash Royale arena visualiser using Pygame.

Usage:
    python visualise.py                       # Hog Rider vs Mini PEKKA (default)
    python visualise.py knight knight         # custom matchup
    python visualise.py giant musketeer       # Giant vs Musketeer

Controls:
    SPACE  — pause / resume
    R      — restart with same matchup
    ESC    — quit
    1-5    — change speed (1=slow, 5=fast)
"""

import sys
import math
import pygame
from cr_sim.constants import (
    ARENA_WIDTH, ARENA_HEIGHT, RIVER_Y, RIVER_HEIGHT,
    BRIDGE_X_LEFT, BRIDGE_X_RIGHT, BRIDGE_WIDTH, CARDS,
    PRINCESS_TOWER, KING_TOWER,
    PRINCESS_TOWER_W, PRINCESS_TOWER_H, KING_TOWER_W, KING_TOWER_H,
)
from cr_sim.engine import Arena, Side

# ─── Display settings ─────────────────────────────────────────────────────
TILE_SIZE = 22
SIDEBAR_W = 180
SCREEN_W = ARENA_WIDTH * TILE_SIZE + SIDEBAR_W
SCREEN_H = ARENA_HEIGHT * TILE_SIZE
FPS_BASE = 10  # ticks per second at speed 1 (1 tick = 0.5s, so 5 real-time-seconds/s)

# ─── Colours ──────────────────────────────────────────────────────────────
BG           = (22, 33, 62)
ARENA_GREEN  = (30, 50, 30)
RIVER_BLUE   = (60, 140, 210)
BRIDGE_GREY  = (90, 90, 90)
ATK_RED      = (230, 57, 70)
DEF_BLUE     = (72, 149, 239)
TOWER_ATK    = (180, 50, 50)
TOWER_DEF    = (50, 100, 160)
KING_ATK     = (200, 60, 60)
KING_DEF     = (60, 120, 180)
HP_GREEN     = (46, 204, 113)
HP_ORANGE    = (230, 126, 34)
HP_RED_BAR   = (231, 76, 60)
WHITE        = (255, 255, 255)
GREY         = (140, 140, 140)
DARK_GREY    = (60, 60, 60)
SIDEBAR_BG   = (16, 20, 40)
GOLD         = (255, 215, 0)

# ─── Card colour/shape mapping ───────────────────────────────────────────
CARD_SHAPES = {
    "Knight":      "circle",
    "Giant":       "circle",
    "Hog Rider":   "diamond",
    "Musketeer":   "triangle",
    "Mini PEKKA":  "square",
    "Wizard":      "triangle",
    "Skeletons":   "circle",
}
CARD_SIZES = {
    "Knight":      8,
    "Giant":       12,
    "Hog Rider":   9,
    "Musketeer":   7,
    "Mini PEKKA":  10,
    "Wizard":      7,
    "Skeletons":   4,
}


def tile_to_px(tx: float, ty: float) -> tuple[int, int]:
    """Convert 1-indexed tile coord to pixel centre of that tile."""
    return int((tx - 0.5) * TILE_SIZE), int((ty - 0.5) * TILE_SIZE)


def draw_hp_bar(surface, cx: int, cy: int, ratio: float, width: int = 20):
    """Draw a small HP bar centred above (cx, cy)."""
    bar_h = 3
    x = cx - width // 2
    y = cy - 14
    # Background
    pygame.draw.rect(surface, DARK_GREY, (x, y, width, bar_h))
    # Fill
    fill_w = max(1, int(width * ratio))
    colour = HP_GREEN if ratio > 0.5 else HP_ORANGE if ratio > 0.25 else HP_RED_BAR
    pygame.draw.rect(surface, colour, (x, y, fill_w, bar_h))


def draw_unit(surface, name: str, px: int, py: int, is_attacker: bool, hp_ratio: float):
    """Draw a unit as a simple shape with HP bar."""
    colour = ATK_RED if is_attacker else DEF_BLUE
    shape = CARD_SHAPES.get(name, "circle")
    size = CARD_SIZES.get(name, 8)

    if shape == "circle":
        pygame.draw.circle(surface, colour, (px, py), size)
        pygame.draw.circle(surface, WHITE, (px, py), size, 1)
    elif shape == "square":
        rect = pygame.Rect(px - size, py - size, size * 2, size * 2)
        pygame.draw.rect(surface, colour, rect)
        pygame.draw.rect(surface, WHITE, rect, 1)
    elif shape == "diamond":
        points = [(px, py - size), (px + size, py), (px, py + size), (px - size, py)]
        pygame.draw.polygon(surface, colour, points)
        pygame.draw.polygon(surface, WHITE, points, 1)
    elif shape == "triangle":
        if is_attacker:
            points = [(px, py + size), (px - size, py - size), (px + size, py - size)]
        else:
            points = [(px, py - size), (px - size, py + size), (px + size, py + size)]
        pygame.draw.polygon(surface, colour, points)
        pygame.draw.polygon(surface, WHITE, points, 1)

    # Direction indicator (small arrow)
    arrow_dy = 5 if is_attacker else -5
    pygame.draw.line(surface, GOLD, (px, py), (px, py + arrow_dy), 2)

    draw_hp_bar(surface, px, py, hp_ratio, width=size * 2)


def draw_tower(surface, tower, font_sm):
    """Draw a tower snapped to tile grid (princess=3×3, king=4×4). 1-indexed."""
    is_king = tower.tower_type == "king"
    is_atk = tower.side == Side.ATTACKER
    colour = (KING_ATK if is_atk else KING_DEF) if is_king else (TOWER_ATK if is_atk else TOWER_DEF)

    if is_king:
        tw, th = KING_TOWER_W, KING_TOWER_H
    else:
        tw, th = PRINCESS_TOWER_W, PRINCESS_TOWER_H

    # Compute first tile the tower occupies (1-indexed)
    first_tile_x = int(tower.x + 0.5 - tw / 2)  # king(9.5,4)→8, princess(4,3)→3
    first_tile_y = int(tower.y + 0.5 - th / 2)
    # Convert to pixel rect (tile N starts at pixel (N-1)*TILE_SIZE)
    w_px = tw * TILE_SIZE
    h_px = th * TILE_SIZE
    rect = pygame.Rect((first_tile_x - 1) * TILE_SIZE, (first_tile_y - 1) * TILE_SIZE, w_px, h_px)

    # Centre point for text/HP bar
    cx = rect.centerx
    cy = rect.centery

    if tower.alive:
        pygame.draw.rect(surface, colour, rect)
        pygame.draw.rect(surface, WHITE, rect, 2)
        hp_text = font_sm.render(str(tower.hp), True, WHITE)
        surface.blit(hp_text, (cx - hp_text.get_width() // 2, cy - hp_text.get_height() // 2))
        draw_hp_bar(surface, cx, cy, tower.hp / tower.max_hp, width=w_px)
    else:
        pygame.draw.rect(surface, DARK_GREY, rect)
        pygame.draw.rect(surface, GREY, rect, 1)
        x_text = font_sm.render("X", True, HP_RED_BAR)
        surface.blit(x_text, (cx - x_text.get_width() // 2, cy - x_text.get_height() // 2))


def draw_sidebar(surface, arena, atk_card, def_card, speed, paused, font, font_sm):
    """Draw info sidebar."""
    x0 = ARENA_WIDTH * TILE_SIZE + 10
    pygame.draw.rect(surface, SIDEBAR_BG, (ARENA_WIDTH * TILE_SIZE, 0, SIDEBAR_W, SCREEN_H))

    state = arena.state
    lines = [
        (f"{CARDS[atk_card].name} vs {CARDS[def_card].name}", GOLD),
        ("", WHITE),
        (f"Tick: {state.tick}", WHITE),
        (f"Time: {state.time:.1f}s / 180s", WHITE),
        ("", WHITE),
        ("── Attacker ──", ATK_RED),
        (f"Elixir: {state.attacker_elixir:.1f}", WHITE),
    ]

    # Attacker towers
    for t in state.towers:
        if t.side == Side.ATTACKER:
            label = "King" if t.tower_type == "king" else f"Princess"
            lines.append((f"  {label}: {t.hp}/{t.max_hp}", GREY))

    lines.append(("", WHITE))
    lines.append(("── Defender ──", DEF_BLUE))
    lines.append((f"Elixir: {state.defender_elixir:.1f}", WHITE))

    for t in state.towers:
        if t.side == Side.DEFENDER:
            label = "King" if t.tower_type == "king" else f"Princess"
            lines.append((f"  {label}: {t.hp}/{t.max_hp}", GREY))

    lines.append(("", WHITE))
    lines.append(("── Units ──", WHITE))
    atk_count = sum(1 for u in state.units if u.side == Side.ATTACKER and u.alive)
    def_count = sum(1 for u in state.units if u.side == Side.DEFENDER and u.alive)
    lines.append((f"  ATK alive: {atk_count}", ATK_RED))
    lines.append((f"  DEF alive: {def_count}", DEF_BLUE))

    for u in state.units:
        if u.alive:
            side_str = "A" if u.side == Side.ATTACKER else "D"
            col = ATK_RED if u.side == Side.ATTACKER else DEF_BLUE
            lines.append((f"  [{side_str}] {u.card_name} {u.hp}hp", col))

    lines.append(("", WHITE))
    speed_str = f"Speed: {speed}x" + ("  PAUSED" if paused else "")
    lines.append((speed_str, GOLD))

    lines.append(("", WHITE))
    lines.append(("[SPACE] pause  [R] restart", GREY))
    lines.append(("[1-5] speed   [ESC] quit", GREY))

    y = 10
    for text, colour in lines:
        if text:
            rendered = font_sm.render(text, True, colour)
            surface.blit(rendered, (x0, y))
        y += 16


def run(atk_card: str, def_card: str):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(f"CR Sim: {CARDS[atk_card].name} vs {CARDS[def_card].name}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("menlo", 14)
    font_sm = pygame.font.SysFont("menlo", 11)

    def init_arena():
        a = Arena()
        a.state.attacker_elixir = 10
        a.state.defender_elixir = 10
        a.spawn_card(CARDS[atk_card], Side.ATTACKER, 9, 10)
        a.spawn_card(CARDS[def_card], Side.DEFENDER, 9, 24)
        return a

    arena = init_arena()
    speed = 2
    paused = False
    finished = False

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
                    arena = init_arena()
                    finished = False
                    paused = False
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    speed = event.key - pygame.K_0

        # Tick simulation
        if not paused and not finished:
            arena.tick()
            atk_alive = any(u.side == Side.ATTACKER and u.alive for u in arena.state.units)
            def_alive = any(u.side == Side.DEFENDER and u.alive for u in arena.state.units)
            if arena.state.game_over or (not atk_alive and not def_alive):
                finished = True

        # ── Draw ──────────────────────────────────────────────────────
        screen.fill(BG)

        # Arena background
        arena_rect = pygame.Rect(0, 0, ARENA_WIDTH * TILE_SIZE, ARENA_HEIGHT * TILE_SIZE)
        pygame.draw.rect(screen, ARENA_GREEN, arena_rect)

        # Grid lines (subtle)
        for tx in range(ARENA_WIDTH + 1):
            x = tx * TILE_SIZE
            pygame.draw.line(screen, (40, 60, 40), (x, 0), (x, SCREEN_H), 1)
        for ty in range(ARENA_HEIGHT + 1):
            y = ty * TILE_SIZE
            pygame.draw.line(screen, (40, 60, 40), (0, y), (ARENA_WIDTH * TILE_SIZE, y), 1)

        # River (2 tiles tall, 1-indexed: tiles RIVER_Y to RIVER_Y+RIVER_HEIGHT-1)
        ry_px = (RIVER_Y - 1) * TILE_SIZE
        river_h = RIVER_HEIGHT * TILE_SIZE
        river_rect = pygame.Rect(0, ry_px, ARENA_WIDTH * TILE_SIZE, river_h)
        pygame.draw.rect(screen, RIVER_BLUE, river_rect)

        # Bridges (3 tiles wide, centred on bridge x, 1-indexed)
        for bx in [BRIDGE_X_LEFT, BRIDGE_X_RIGHT]:
            first_bridge_tile = int(bx + 0.5 - BRIDGE_WIDTH / 2)  # bx=4,w=3 → tile 3
            bpx = (first_bridge_tile - 1) * TILE_SIZE
            bridge_rect = pygame.Rect(bpx, ry_px, BRIDGE_WIDTH * TILE_SIZE, river_h)
            pygame.draw.rect(screen, BRIDGE_GREY, bridge_rect)
            pygame.draw.rect(screen, WHITE, bridge_rect, 1)

        # Towers
        for tower in arena.state.towers:
            draw_tower(screen, tower, font_sm)

        # Units
        for unit in arena.state.units:
            if not unit.alive or not unit.deployed:
                continue
            px, py = tile_to_px(unit.x, unit.y)
            is_atk = unit.side == Side.ATTACKER
            hp_ratio = unit.hp / unit.max_hp
            draw_unit(screen, unit.card_name, px, py, is_atk, hp_ratio)

            # Name label below
            label = font_sm.render(unit.card_name[:6], True, WHITE)
            screen.blit(label, (px - label.get_width() // 2, py + 12))

        # Sidebar
        draw_sidebar(screen, arena, atk_card, def_card, speed, paused, font, font_sm)

        # Finished banner
        if finished:
            banner = font.render("FIGHT OVER — press R to restart", True, GOLD)
            bx = (ARENA_WIDTH * TILE_SIZE - banner.get_width()) // 2
            by = SCREEN_H // 2 - 20
            pygame.draw.rect(screen, (0, 0, 0), (bx - 10, by - 5, banner.get_width() + 20, 30))
            screen.blit(banner, (bx, by))

        pygame.display.flip()
        clock.tick(FPS_BASE * speed)

    pygame.quit()


if __name__ == "__main__":
    atk = sys.argv[1] if len(sys.argv) > 1 else "hog_rider"
    dfn = sys.argv[2] if len(sys.argv) > 2 else "mini_pekka"
    if atk not in CARDS:
        print(f"Unknown card: {atk}. Available: {list(CARDS.keys())}")
        sys.exit(1)
    if dfn not in CARDS:
        print(f"Unknown card: {dfn}. Available: {list(CARDS.keys())}")
        sys.exit(1)
    print(f"Visualising: {CARDS[atk].name} (attacker) vs {CARDS[dfn].name} (defender)")
    print("Controls: SPACE=pause, R=restart, 1-5=speed, ESC=quit")
    run(atk, dfn)
