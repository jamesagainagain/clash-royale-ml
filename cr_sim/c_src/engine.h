#ifndef ENGINE_H
#define ENGINE_H

#include "cards.h"

/* ── Limits ───────────────────────────────────────────── */
#define MAX_UNITS   64
#define NUM_TOWERS  6

/* ── Arena constants ──────────────────────────────────── */
#define ARENA_WIDTH       18
#define ARENA_HEIGHT      32
#define RIVER_Y           16
#define RIVER_HEIGHT      2
#define BRIDGE_X_LEFT     4.0f
#define BRIDGE_X_RIGHT    15.0f
#define BRIDGE_WIDTH      3.0f

#define TICK_DURATION     0.5f
#define MATCH_DURATION    180.0f
#define ELIXIR_RATE       (1.0f / 2.8f)
#define ELIXIR_CAP        10.0f
#define DEPLOY_TIME       1.0f

/* Tower stats */
#define PRINCESS_HP       3052
#define PRINCESS_DMG      109
#define PRINCESS_HITSPD   0.8f
#define PRINCESS_RANGE    7.5f
#define PRINCESS_W        3
#define PRINCESS_H        3

#define KING_HP           4824
#define KING_DMG          109
#define KING_HITSPD       1.0f
#define KING_RANGE        7.0f
#define KING_W            4
#define KING_H            4

/* ── CUnit ────────────────────────────────────────────── */
typedef struct {
    int           card_index;      /* CardIndex enum */
    int           side;            /* Side enum */
    float         x, y;
    int           hp, max_hp;
    int           damage;
    float         hit_speed;       /* seconds between attacks */
    float         speed;           /* tiles/second */
    float         range;
    int           targets;         /* TargetType */
    int           transport;       /* UnitTransport */
    float         splash_radius;
    float         sight_range;
    float         attack_cooldown;
    float         deploy_timer;
    int           alive;           /* 1=alive, 0=dead */
} CUnit;

/* ── CTower ───────────────────────────────────────────── */
typedef struct {
    int           side;            /* Side enum */
    int           tower_type;      /* 0=princess, 1=king */
    float         x, y;
    int           hp, max_hp;
    int           damage;
    float         hit_speed;
    float         range;
    float         attack_cooldown;
    int           active;          /* king towers start inactive */
} CTower;

/* ── GameState (flat, no heap pointers) ───────────────── */
typedef struct {
    int           tick;
    float         time;
    CUnit         units[MAX_UNITS];
    int           unit_count;
    CTower        towers[NUM_TOWERS];
    float         attacker_elixir;
    float         defender_elixir;
    int           game_over;
    int           winner;          /* 0=none, SIDE_ATK, SIDE_DEF */
    int           tower_damage_dealt;
} GameState;

/* ── Arena handle ─────────────────────────────────────── */
typedef struct {
    GameState state;
} Arena;

/* ── Public API ───────────────────────────────────────── */
Arena *arena_create(void);
void   arena_destroy(Arena *a);
int    arena_spawn_card(Arena *a, int card_index, int side, float x, float y);
void   arena_tick(Arena *a);

#endif /* ENGINE_H */
