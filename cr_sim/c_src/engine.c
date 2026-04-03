#include "engine.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* ── Helpers ──────────────────────────────────────────── */

static float dist(float x1, float y1, float x2, float y2) {
    float dx = x1 - x2, dy = y1 - y2;
    return sqrtf(dx * dx + dy * dy);
}

static float clampf(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

/* ── Tower init ───────────────────────────────────────── */

static void init_towers(Arena *a) {
    GameState *s = &a->state;
    /* Order: DEF princess L, DEF princess R, DEF king,
     *        ATK princess L, ATK princess R, ATK king */
    CTower *t;

    /* Defender princess left */
    t = &s->towers[0];
    t->side = SIDE_DEF; t->tower_type = 0;
    t->x = 4.0f; t->y = 26.0f;
    t->hp = PRINCESS_HP; t->max_hp = PRINCESS_HP;
    t->damage = PRINCESS_DMG; t->hit_speed = PRINCESS_HITSPD;
    t->range = PRINCESS_RANGE; t->attack_cooldown = 0.0f; t->active = 1;

    /* Defender princess right */
    t = &s->towers[1];
    t->side = SIDE_DEF; t->tower_type = 0;
    t->x = 15.0f; t->y = 26.0f;
    t->hp = PRINCESS_HP; t->max_hp = PRINCESS_HP;
    t->damage = PRINCESS_DMG; t->hit_speed = PRINCESS_HITSPD;
    t->range = PRINCESS_RANGE; t->attack_cooldown = 0.0f; t->active = 1;

    /* Defender king */
    t = &s->towers[2];
    t->side = SIDE_DEF; t->tower_type = 1;
    t->x = 9.5f; t->y = 29.5f;
    t->hp = KING_HP; t->max_hp = KING_HP;
    t->damage = KING_DMG; t->hit_speed = KING_HITSPD;
    t->range = KING_RANGE; t->attack_cooldown = 0.0f; t->active = 0;

    /* Attacker princess left */
    t = &s->towers[3];
    t->side = SIDE_ATK; t->tower_type = 0;
    t->x = 4.0f; t->y = 7.0f;
    t->hp = PRINCESS_HP; t->max_hp = PRINCESS_HP;
    t->damage = PRINCESS_DMG; t->hit_speed = PRINCESS_HITSPD;
    t->range = PRINCESS_RANGE; t->attack_cooldown = 0.0f; t->active = 1;

    /* Attacker princess right */
    t = &s->towers[4];
    t->side = SIDE_ATK; t->tower_type = 0;
    t->x = 15.0f; t->y = 7.0f;
    t->hp = PRINCESS_HP; t->max_hp = PRINCESS_HP;
    t->damage = PRINCESS_DMG; t->hit_speed = PRINCESS_HITSPD;
    t->range = PRINCESS_RANGE; t->attack_cooldown = 0.0f; t->active = 1;

    /* Attacker king */
    t = &s->towers[5];
    t->side = SIDE_ATK; t->tower_type = 1;
    t->x = 9.5f; t->y = 3.5f;
    t->hp = KING_HP; t->max_hp = KING_HP;
    t->damage = KING_DMG; t->hit_speed = KING_HITSPD;
    t->range = KING_RANGE; t->attack_cooldown = 0.0f; t->active = 0;
}

/* ── King activation ──────────────────────────────────── */

static void check_king_activation(Arena *a, CTower *damaged) {
    GameState *s = &a->state;
    int side = damaged->side;

    /* King tower index: DEF=2, ATK=5 */
    int king_idx = (side == SIDE_DEF) ? 2 : 5;
    CTower *king = &s->towers[king_idx];

    /* Already active? */
    if (king->active) return;

    /* Direct hit on king tower */
    if (damaged->tower_type == 1) {
        king->active = 1;
        return;
    }

    /* Princess tower destroyed → activate king */
    if (damaged->hp <= 0) {
        king->active = 1;
    }
}

/* ── Does this side have any princess tower alive? ────── */

static int has_princess_alive(GameState *s, int side) {
    /* DEF princess: 0,1  ATK princess: 3,4 */
    int base = (side == SIDE_DEF) ? 0 : 3;
    return (s->towers[base].hp > 0) || (s->towers[base + 1].hp > 0);
}

/* ── Target encoding ──────────────────────────────────── */
/*  >= 0       → unit index
 *  <= -2      → tower index = -(id + 2), i.e. tower 0 = -2, tower 1 = -3
 *  == -1      → no target (TARGET_NONE)
 */
#define TARGET_NONE (-1)
#define TOWER_TO_ID(ti)  (-(ti) - 2)
#define ID_TO_TOWER(id)  (-(id) - 2)
#define IS_TOWER(id)     ((id) <= -2)

/* ── Target finding ───────────────────────────────────── */

/* Find nearest enemy for a unit (respects targets, sight_range, king lock) */
static int find_nearest_target(Arena *a, int ui, float *out_dist) {
    GameState *s = &a->state;
    CUnit *u = &s->units[ui];
    int enemy_side = (u->side == SIDE_ATK) ? SIDE_DEF : SIDE_ATK;
    int enemy_has_princess = has_princess_alive(s, enemy_side);

    float best_d = 1e9f;
    int best = TARGET_NONE;

    /* BUILDINGS-targeting units skip troops entirely */
    int skip_troops = (u->targets == TGT_BUILDINGS);

    /* Check units */
    if (!skip_troops) {
        for (int i = 0; i < s->unit_count; i++) {
            CUnit *e = &s->units[i];
            if (!e->alive || e->hp <= 0 || e->side == u->side) continue;
            if (e->deploy_timer > 0.0f) continue;
            /* Target filter: GROUND units can't hit AIR targets */
            if (u->targets == TGT_GROUND && e->transport == TRANSPORT_AIR) continue;
            float d = dist(u->x, u->y, e->x, e->y);
            if (d <= u->sight_range && d < best_d) {
                best_d = d;
                best = i;
            }
        }
    }

    /* Check towers */
    for (int i = 0; i < NUM_TOWERS; i++) {
        CTower *t = &s->towers[i];
        if (t->hp <= 0 || t->side == u->side) continue;
        /* Skip king if princess alive */
        if (t->tower_type == 1 && enemy_has_princess) continue;
        float d = dist(u->x, u->y, t->x, t->y);
        if (d <= u->sight_range && d < best_d) {
            best_d = d;
            best = TOWER_TO_ID(i);
        }
    }

    if (out_dist) *out_dist = best_d;
    return best;
}

/* Nearest enemy tower as nav fallback */
static int nearest_enemy_tower(Arena *a, int ui) {
    GameState *s = &a->state;
    CUnit *u = &s->units[ui];
    int enemy_side = (u->side == SIDE_ATK) ? SIDE_DEF : SIDE_ATK;
    int enemy_has_princess = has_princess_alive(s, enemy_side);

    float best_d = 1e9f;
    int best = TARGET_NONE;

    for (int i = 0; i < NUM_TOWERS; i++) {
        CTower *t = &s->towers[i];
        if (t->hp <= 0 || t->side == u->side) continue;
        if (t->tower_type == 1 && enemy_has_princess) continue;
        float d = dist(u->x, u->y, t->x, t->y);
        if (d < best_d) {
            best_d = d;
            best = TOWER_TO_ID(i);
        }
    }
    return best;
}

/* Find nearest enemy unit in tower range */
static int find_tower_target(Arena *a, int ti) {
    GameState *s = &a->state;
    CTower *tw = &s->towers[ti];
    float best_d = 1e9f;
    int best = -1;

    for (int i = 0; i < s->unit_count; i++) {
        CUnit *e = &s->units[i];
        if (!e->alive || e->hp <= 0 || e->side == tw->side) continue;
        if (e->deploy_timer > 0.0f) continue;
        float d = dist(tw->x, tw->y, e->x, e->y);
        if (d <= tw->range && d < best_d) {
            best_d = d;
            best = i;
        }
    }
    return best;
}

/* ── Get target position ──────────────────────────────── */

static void target_pos(GameState *s, int target_id, float *tx, float *ty) {
    if (target_id >= 0) {
        *tx = s->units[target_id].x;
        *ty = s->units[target_id].y;
    } else {
        int ti = ID_TO_TOWER(target_id);
        *tx = s->towers[ti].x;
        *ty = s->towers[ti].y;
    }
}

/* ── Bridge constraint ────────────────────────────────── */

static void apply_bridge_constraint(CUnit *u, float *nx, float *ny) {
    if (u->transport == TRANSPORT_AIR) return;

    float river_top = (float)RIVER_Y;          /* 16 */
    float river_bot = (float)(RIVER_Y + RIVER_HEIGHT); /* 18 */

    int in_river_old = (u->y >= river_top && u->y <= river_bot);
    int in_river_new = (*ny >= river_top && *ny <= river_bot);
    int crossed = (u->y < river_top && *ny > river_bot) ||
                  (u->y > river_bot && *ny < river_top);

    /* No river interaction */
    if (!in_river_new && !crossed && !in_river_old) return;

    /* Find nearest bridge to new position */
    float dl = fabsf(*nx - BRIDGE_X_LEFT);
    float dr = fabsf(*nx - BRIDGE_X_RIGHT);
    float bridge_x = (dl <= dr) ? BRIDGE_X_LEFT : BRIDGE_X_RIGHT;
    float half_bw = BRIDGE_WIDTH / 2.0f;

    /* On a bridge? Allow through */
    if (fabsf(*nx - bridge_x) <= half_bw) return;

    /* Not on bridge — snap x to nearest bridge from OLD position, keep old y */
    float dl_old = fabsf(u->x - BRIDGE_X_LEFT);
    float dr_old = fabsf(u->x - BRIDGE_X_RIGHT);
    float snap_x = (dl_old <= dr_old) ? BRIDGE_X_LEFT : BRIDGE_X_RIGHT;
    *nx = snap_x;
    *ny = u->y;
}

/* ── Attack (unit attacks target) ─────────────────────── */

static void do_attack(Arena *a, CUnit *attacker, int target_id) {
    GameState *s = &a->state;

    float tx, ty;
    target_pos(s, target_id, &tx, &ty);

    if (attacker->splash_radius > 0.0f) {
        /* Splash: damage all enemies near target position */
        int enemy_side = (attacker->side == SIDE_ATK) ? SIDE_DEF : SIDE_ATK;
        for (int i = 0; i < s->unit_count; i++) {
            CUnit *e = &s->units[i];
            if (!e->alive || e->hp <= 0 || e->side != enemy_side) continue;
            if (dist(e->x, e->y, tx, ty) <= attacker->splash_radius)
                e->hp -= attacker->damage;
        }
        for (int i = 0; i < NUM_TOWERS; i++) {
            CTower *t = &s->towers[i];
            if (t->hp <= 0 || t->side != enemy_side) continue;
            if (dist(t->x, t->y, tx, ty) <= attacker->splash_radius) {
                t->hp -= attacker->damage;
                s->tower_damage_dealt += attacker->damage;
                check_king_activation(a, t);
            }
        }
    } else {
        /* Single target */
        if (target_id >= 0) {
            s->units[target_id].hp -= attacker->damage;
        } else {
            int ti = ID_TO_TOWER(target_id);
            CTower *t = &s->towers[ti];
            t->hp -= attacker->damage;
            s->tower_damage_dealt += attacker->damage;
            check_king_activation(a, t);
        }
    }
}

/* ── Apply spell ──────────────────────────────────────── */

static void apply_spell(Arena *a, const CardDef *card, int side, float sx, float sy) {
    GameState *s = &a->state;
    int enemy_side = (side == SIDE_ATK) ? SIDE_DEF : SIDE_ATK;

    for (int i = 0; i < s->unit_count; i++) {
        CUnit *e = &s->units[i];
        if (!e->alive || e->hp <= 0 || e->side != enemy_side) continue;
        if (dist(e->x, e->y, sx, sy) <= card->spell_radius)
            e->hp -= card->spell_damage;
    }
    for (int i = 0; i < NUM_TOWERS; i++) {
        CTower *t = &s->towers[i];
        if (t->hp <= 0 || t->side != enemy_side) continue;
        if (dist(t->x, t->y, sx, sy) <= card->spell_radius) {
            t->hp -= card->crown_tower_damage;
            s->tower_damage_dealt += card->crown_tower_damage;
            check_king_activation(a, t);
        }
    }
}

/* ── Compact dead units ───────────────────────────────── */

static void compact_units(GameState *s) {
    int write = 0;
    for (int read = 0; read < s->unit_count; read++) {
        if (s->units[read].alive && s->units[read].hp > 0) {
            if (write != read)
                s->units[write] = s->units[read];
            write++;
        }
    }
    s->unit_count = write;
}

/* ── Win check ────────────────────────────────────────── */

static void check_win(Arena *a) {
    GameState *s = &a->state;

    /* King tower destroyed → instant loss */
    if (s->towers[2].hp <= 0) { /* DEF king */
        s->game_over = 1;
        s->winner = SIDE_ATK;
        return;
    }
    if (s->towers[5].hp <= 0) { /* ATK king */
        s->game_over = 1;
        s->winner = SIDE_DEF;
        return;
    }

    /* Time limit */
    if (s->time >= MATCH_DURATION) {
        /* Compare princess tower HP sums */
        int def_hp = 0, atk_hp = 0;
        for (int i = 0; i < 2; i++) {
            def_hp += (s->towers[i].hp > 0) ? s->towers[i].hp : 0;
            atk_hp += (s->towers[3 + i].hp > 0) ? s->towers[3 + i].hp : 0;
        }
        s->game_over = 1;
        if (def_hp < atk_hp)
            s->winner = SIDE_ATK; /* defender took more damage */
        else if (atk_hp < def_hp)
            s->winner = SIDE_DEF;
        else
            s->winner = 0; /* draw */
    }
}

/* ════════════════════════════════════════════════════════
 *  PUBLIC API
 * ════════════════════════════════════════════════════════ */

Arena *arena_create(void) {
    Arena *a = (Arena *)calloc(1, sizeof(Arena));
    if (!a) return (void *)0;
    a->state.attacker_elixir = 5.0f;
    a->state.defender_elixir = 5.0f;
    init_towers(a);
    return a;
}

void arena_destroy(Arena *a) {
    free(a);
}

int arena_spawn_card(Arena *a, int card_index, int side, float x, float y) {
    GameState *s = &a->state;
    const CardDef *card = card_def_get((CardIndex)card_index);
    if (!card) return 0;

    /* Elixir check */
    float *elixir = (side == SIDE_ATK) ? &s->attacker_elixir : &s->defender_elixir;
    if (*elixir < (float)card->elixir_cost) return 0;
    *elixir -= (float)card->elixir_cost;

    /* Spell */
    if (card->card_type == CARD_SPELL) {
        apply_spell(a, card, side, x, y);
        return 1;
    }

    /* Clamp to own half */
    x = clampf(x, 1.0f, (float)ARENA_WIDTH);
    if (side == SIDE_ATK) {
        y = clampf(y, 1.0f, 15.0f);
    } else {
        y = clampf(y, 18.0f, (float)ARENA_HEIGHT);
    }

    /* Spawn offsets */
    static const float offsets_3[][2] = {{0, 0}, {-0.5f, 0.5f}, {0.5f, 0.5f}};
    static const float offsets_1[][2] = {{0, 0}};
    const float (*offsets)[2];
    int count = card->count;
    if (count == 3) offsets = offsets_3;
    else { offsets = offsets_1; count = 1; }

    for (int i = 0; i < count; i++) {
        if (s->unit_count >= MAX_UNITS) break;
        CUnit *u = &s->units[s->unit_count++];
        u->card_index = card_index;
        u->side = side;
        u->x = x + offsets[i][0];
        u->y = y + offsets[i][1];
        u->hp = card->hp;
        u->max_hp = card->hp;
        u->damage = card->damage;
        u->hit_speed = card->hit_speed;
        u->speed = card->speed;
        u->range = card->range;
        u->targets = card->targets;
        u->transport = card->transport;
        u->splash_radius = card->splash_radius;
        u->sight_range = card->sight_range;
        u->attack_cooldown = 0.0f;
        u->deploy_timer = DEPLOY_TIME;
        u->alive = 1;
    }
    return 1;
}

void arena_tick(Arena *a) {
    GameState *s = &a->state;
    if (s->game_over) return;

    float dt = TICK_DURATION;
    s->tick++;
    s->time += dt;
    s->tower_damage_dealt = 0;

    /* Elixir regen */
    s->attacker_elixir = clampf(s->attacker_elixir + ELIXIR_RATE * dt, 0.0f, ELIXIR_CAP);
    s->defender_elixir = clampf(s->defender_elixir + ELIXIR_RATE * dt, 0.0f, ELIXIR_CAP);

    /* Deploy timers */
    for (int i = 0; i < s->unit_count; i++) {
        CUnit *u = &s->units[i];
        if (u->alive && u->deploy_timer > 0.0f)
            u->deploy_timer -= dt;
    }

    /* ── Unit AI ──────────────────────────────────────── */
    for (int i = 0; i < s->unit_count; i++) {
        CUnit *u = &s->units[i];
        if (!u->alive || u->hp <= 0 || u->deploy_timer > 0.0f) continue;

        float target_d;
        int target = find_nearest_target(a, i, &target_d);

        /* No target in sight → walk toward nearest enemy tower */
        if (target == TARGET_NONE) {
            target = nearest_enemy_tower(a, i);
            if (target == TARGET_NONE) continue;
            target_d = 1e9f; /* force movement */
        }

        if (target_d > u->range) {
            /* Move toward target */
            float tx, ty;
            target_pos(s, target, &tx, &ty);
            float d = dist(u->x, u->y, tx, ty);
            if (d > 0.001f) {
                float step = u->speed * dt;
                float nx = u->x + (tx - u->x) / d * step;
                float ny = u->y + (ty - u->y) / d * step;
                apply_bridge_constraint(u, &nx, &ny);
                u->x = clampf(nx, 1.0f, (float)ARENA_WIDTH);
                u->y = clampf(ny, 1.0f, (float)ARENA_HEIGHT);
            }
        } else {
            /* In range → attack */
            u->attack_cooldown -= dt;
            if (u->attack_cooldown <= 0.0f) {
                do_attack(a, u, target);
                u->attack_cooldown = u->hit_speed;
            }
        }
    }

    /* ── Tower attacks ────────────────────────────────── */
    for (int i = 0; i < NUM_TOWERS; i++) {
        CTower *tw = &s->towers[i];
        if (tw->hp <= 0 || !tw->active) continue;

        int target = find_tower_target(a, i);
        if (target < 0) continue;

        tw->attack_cooldown -= dt;
        if (tw->attack_cooldown <= 0.0f) {
            s->units[target].hp -= tw->damage;
            s->tower_damage_dealt += tw->damage;
            tw->attack_cooldown = tw->hit_speed;
        }
    }

    /* Mark dead */
    for (int i = 0; i < s->unit_count; i++) {
        if (s->units[i].hp <= 0)
            s->units[i].alive = 0;
    }

    /* Compact */
    compact_units(s);

    /* Win check */
    check_win(a);
}
