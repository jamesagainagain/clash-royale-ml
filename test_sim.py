"""Quick smoke test: run the engine and env to verify everything works."""

from cr_sim.constants import CARDS
from cr_sim.engine import Arena, Side
from cr_sim.env import ClashDefenseEnv


def test_engine_basic():
    """Spawn a knight vs knight and run until one dies."""
    arena = Arena()
    arena.state.attacker_elixir = 10
    arena.state.defender_elixir = 10

    # Attacker knight at top heading down
    arena.spawn_card(CARDS["knight"], Side.ATTACKER, 9, 10)
    # Defender knight at bottom heading up
    arena.spawn_card(CARDS["knight"], Side.DEFENDER, 9, 24)

    for tick in range(400):
        arena.tick()
        atk_units = [u for u in arena.state.units if u.side == Side.ATTACKER]
        def_units = [u for u in arena.state.units if u.side == Side.DEFENDER]

        if tick % 20 == 0:
            print(f"Tick {tick:3d} | ATK units: {len(atk_units)} | DEF units: {len(def_units)}")
            for u in arena.state.units:
                side = "ATK" if u.side == Side.ATTACKER else "DEF"
                print(f"  [{side}] {u.card_name} pos=({u.x:.1f},{u.y:.1f}) hp={u.hp}")

        if not atk_units and not def_units:
            print(f"Both dead at tick {tick}")
            break
        if not atk_units:
            print(f"Attacker knight died at tick {tick}")
            break
        if not def_units:
            print(f"Defender knight died at tick {tick}")
            break

    print("\nTower HP:")
    print("  Attacker:", arena.get_tower_hp(Side.ATTACKER))
    print("  Defender:", arena.get_tower_hp(Side.DEFENDER))


def test_hog_vs_mini_pekka():
    """Hog Rider (buildings only) should ignore mini pekka and run to tower."""
    arena = Arena()
    arena.state.attacker_elixir = 10
    arena.state.defender_elixir = 10

    arena.spawn_card(CARDS["hog_rider"], Side.ATTACKER, 9, 12)
    arena.spawn_card(CARDS["mini_pekka"], Side.DEFENDER, 9, 22)

    for tick in range(300):
        arena.tick()
        if tick % 20 == 0:
            for u in arena.state.units:
                side = "ATK" if u.side == Side.ATTACKER else "DEF"
                print(f"Tick {tick:3d} [{side}] {u.card_name} ({u.x:.1f},{u.y:.1f}) hp={u.hp}")

        if arena.state.game_over:
            print(f"Game over at tick {tick}, winner: {arena.state.winner}")
            break

    print("\nDefender towers:", arena.get_tower_hp(Side.DEFENDER))


def test_env_runs():
    """Run a few episodes of the Gymnasium env."""
    env = ClashDefenseEnv()
    for ep in range(3):
        obs, info = env.reset()
        print(f"\nEpisode {ep+1} — Attacker plays: {info['attacker_card']}")
        total_reward = 0
        for step in range(100):
            action = env.action_space.sample()
            obs, reward, done, truncated, info = env.step(action)
            total_reward += reward
            if done or truncated:
                print(f"  Done at step {step}, reward: {total_reward:.3f}")
                if "reward_breakdown" in info:
                    print(f"  Breakdown: {info['reward_breakdown']}")
                break
    env.close()


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 1: Knight vs Knight")
    print("=" * 60)
    test_engine_basic()

    print("\n" + "=" * 60)
    print("TEST 2: Hog Rider vs Mini PEKKA")
    print("=" * 60)
    test_hog_vs_mini_pekka()

    print("\n" + "=" * 60)
    print("TEST 3: Gymnasium Env (random actions)")
    print("=" * 60)
    test_env_runs()
