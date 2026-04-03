#ifndef CARDS_H
#define CARDS_H

/* ── Side ─────────────────────────────────────────────── */
typedef enum { SIDE_ATK = 1, SIDE_DEF = 2 } Side;

/* ── TargetType (matches Python auto() order) ─────────── */
typedef enum {
    TGT_GROUND         = 1,
    TGT_AIR            = 2,
    TGT_BUILDINGS      = 3,
    TGT_AIR_AND_GROUND = 4
} TargetType;

/* ── UnitTransport ────────────────────────────────────── */
typedef enum { TRANSPORT_GROUND = 1, TRANSPORT_AIR = 2 } UnitTransport;

/* ── CardType ─────────────────────────────────────────── */
typedef enum { CARD_TROOP = 1, CARD_SPELL = 2, CARD_BUILDING = 3 } CardType;

/* ── Card index (order matches Python CARD_DB keys) ───── */
typedef enum {
    CARD_KNIGHT     = 0,
    CARD_GIANT      = 1,
    CARD_HOG_RIDER  = 2,
    CARD_MUSKETEER  = 3,
    CARD_MINI_PEKKA = 4,
    CARD_WIZARD     = 5,
    CARD_SKELETONS  = 6,
    CARD_FIREBALL   = 7,
    NUM_CARDS       = 8
} CardIndex;

/* ── Card definition ──────────────────────────────────── */
typedef struct {
    const char   *name;
    CardType      card_type;
    int           elixir_cost;
    int           hp;
    int           damage;
    float         hit_speed;     /* seconds between attacks */
    float         speed;         /* tiles/second (resolved) */
    float         range;         /* attack range in tiles   */
    TargetType    targets;
    UnitTransport transport;
    int           count;         /* units spawned           */
    float         splash_radius;
    float         sight_range;
    /* spell-only */
    int           spell_damage;
    float         spell_radius;
    int           crown_tower_damage;
} CardDef;

/* Lookup by index */
const CardDef *card_def_get(CardIndex idx);

#endif /* CARDS_H */
