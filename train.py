"""
Train a lightweight PPO agent to defend against Knight/Mini PEKKA using Skeletons.

Usage:
    python train.py                    # train for 100k steps
    python train.py --timesteps 500000 # train longer
    python train.py --eval             # evaluate a saved model
"""

import argparse
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback
from cr_sim.env import ClashDefenseEnv


def make_env():
    return ClashDefenseEnv(
        defender_cards=["skeletons"],
        attacker_cards=["knight", "mini_pekka"],
    )


def train(timesteps: int = 100_000, n_envs: int = 4):
    env = make_vec_env(make_env, n_envs=n_envs)
    eval_env = make_vec_env(make_env, n_envs=1)

    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path="./models/best/",
        log_path="./logs/",
        eval_freq=5000,
        n_eval_episodes=20,
        deterministic=True,
    )

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=512,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        verbose=1,
        # tensorboard_log="./tb_logs/",
    )

    print(f"Training for {timesteps} timesteps...")
    print(f"Action space: {env.action_space} (0=wait, 1..{env.action_space.n - 1}=place skeletons)")
    print(f"Observation space: {env.observation_space.shape}")

    model.learn(total_timesteps=timesteps, callback=eval_callback)
    model.save("models/skeletons_defense")
    print("Model saved to models/skeletons_defense.zip")


def evaluate(model_path: str = "models/skeletons_defense", episodes: int = 50):
    env = make_env()
    model = PPO.load(model_path)

    wins, total_reward = 0, 0
    for ep in range(episodes):
        obs, info = env.reset()
        ep_reward = 0
        for _ in range(200):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(action)
            ep_reward += reward
            if done or truncated:
                break
        total_reward += ep_reward
        if "reward_breakdown" in info and info["reward_breakdown"]["kill_bonus"] > 0:
            wins += 1

    print(f"\nEvaluation over {episodes} episodes:")
    print(f"  Avg reward: {total_reward / episodes:.3f}")
    print(f"  Kill rate:  {wins / episodes:.1%}")
    env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--model", default="models/skeletons_defense")
    args = parser.parse_args()

    if args.eval:
        evaluate(args.model)
    else:
        train(args.timesteps)
