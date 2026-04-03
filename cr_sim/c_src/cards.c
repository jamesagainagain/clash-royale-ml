#include "cards.h"

/*
 * Tournament Standard (Level 11) card database.
 * Speed values pre-resolved from SPEED_MAP:
 *   slow=0.75  medium=1.0  fast=1.5  very_fast=2.0
 */
static const CardDef CARD_DB[NUM_CARDS] = {
    [CARD_KNIGHT] = {
        .name = "knight", .card_type = CARD_TROOP, .elixir_cost = 3,
        .hp = 1766, .damage = 202, .hit_speed = 1.2f, .speed = 1.0f,
        .range = 1.2f, .targets = TGT_AIR_AND_GROUND,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 0.0f, .sight_range = 5.5f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_GIANT] = {
        .name = "giant", .card_type = CARD_TROOP, .elixir_cost = 5,
        .hp = 3968, .damage = 253, .hit_speed = 1.5f, .speed = 0.75f,
        .range = 1.2f, .targets = TGT_BUILDINGS,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 0.0f, .sight_range = 7.5f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_HOG_RIDER] = {
        .name = "hog_rider", .card_type = CARD_TROOP, .elixir_cost = 4,
        .hp = 1697, .damage = 317, .hit_speed = 1.6f, .speed = 2.0f,
        .range = 0.8f, .targets = TGT_BUILDINGS,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 0.0f, .sight_range = 9.5f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_MUSKETEER] = {
        .name = "musketeer", .card_type = CARD_TROOP, .elixir_cost = 4,
        .hp = 721, .damage = 217, .hit_speed = 1.0f, .speed = 1.0f,
        .range = 6.0f, .targets = TGT_AIR_AND_GROUND,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 0.0f, .sight_range = 6.0f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_MINI_PEKKA] = {
        .name = "mini_pekka", .card_type = CARD_TROOP, .elixir_cost = 4,
        .hp = 1390, .damage = 755, .hit_speed = 1.6f, .speed = 1.5f,
        .range = 0.8f, .targets = TGT_GROUND,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 0.0f, .sight_range = 5.5f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_WIZARD] = {
        .name = "wizard", .card_type = CARD_TROOP, .elixir_cost = 5,
        .hp = 755, .damage = 281, .hit_speed = 1.4f, .speed = 1.0f,
        .range = 5.5f, .targets = TGT_AIR_AND_GROUND,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 1.5f, .sight_range = 5.5f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_SKELETONS] = {
        .name = "skeletons", .card_type = CARD_TROOP, .elixir_cost = 1,
        .hp = 81, .damage = 81, .hit_speed = 1.1f, .speed = 1.5f,
        .range = 0.8f, .targets = TGT_GROUND,
        .transport = TRANSPORT_GROUND, .count = 3,
        .splash_radius = 0.0f, .sight_range = 5.5f,
        .spell_damage = 0, .spell_radius = 0.0f, .crown_tower_damage = 0
    },
    [CARD_FIREBALL] = {
        .name = "fireball", .card_type = CARD_SPELL, .elixir_cost = 4,
        .hp = 0, .damage = 0, .hit_speed = 0.0f, .speed = 0.0f,
        .range = 0.0f, .targets = TGT_AIR_AND_GROUND,
        .transport = TRANSPORT_GROUND, .count = 1,
        .splash_radius = 0.0f, .sight_range = 0.0f,
        .spell_damage = 688, .spell_radius = 2.5f, .crown_tower_damage = 207
    }
};

const CardDef *card_def_get(CardIndex idx) {
    if (idx < 0 || idx >= NUM_CARDS) return (void *)0;
    return &CARD_DB[idx];
}
