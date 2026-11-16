"""
Run this file at first, in order to see what is it printng. Instead of the print() use the respective log level
"""
from abc import ABC, abstractmethod
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from loguru import logger

Bandit_Reward = [1, 2, 3, 4]
NumberOfTrials = 20000
PRECISION = 1.0
SEED = 42
OUTPUT_DIR = Path("results")


class Bandit(ABC):
    @abstractmethod
    def __init__(self, p):
        pass

    @abstractmethod
    def __repr__(self):
        pass

    @abstractmethod
    def pull(self):
        pass

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def experiment(self):
        pass

    @abstractmethod
    def report(self):
        """Store the data in a csv file and log the average reward and
        the average regret of the finished experiment.
        """
        pass


class BaseExperiment(Bandit):
    """Shared bookkeeping for both algorithms.

    The four advertisements are the arms. Arm i pays a noisy reward drawn
    from a normal distribution whose mean is p[i] and whose precision
    (1 / variance) is the same for every arm and known in advance.

    Parameters
    ----------
    p : list of float
        True mean reward of every arm.
    trials : int, optional
        Number of pulls in one experiment.
    precision : float, optional
        Precision of the reward noise.
    seed : int, optional
        Seed of the random generator, for reproducible runs.
    """

    name = "Base"

    def __init__(self, p, trials=NumberOfTrials, precision=PRECISION, seed=SEED):
        self.p = np.asarray(p, dtype=float)
        self.k = len(self.p)
        self.trials = trials
        self.precision = precision
        self.rng = np.random.default_rng(seed)
        self.best_mean = self.p.max()
        self.t = 0
        self.counts = np.zeros(self.k, dtype=int)
        self.estimates = np.zeros(self.k)
        self.arms = np.zeros(trials, dtype=int)
        self.rewards = np.zeros(trials)
        self.regrets = np.zeros(trials)
        self.history = np.zeros((trials, self.k))
        self._last_arm = None
        self._last_reward = None

    def __repr__(self):
        return f"{self.name}(p={self.p.tolist()}, trials={self.trials}, precision={self.precision})"

    @abstractmethod
    def choose_arm(self):
        """Pick the arm to pull next."""

    @abstractmethod
    def learn(self, arm, reward):
        """Fold one observed reward into the algorithm's beliefs."""

    def pull(self):
        """Choose an arm, draw its reward and remember both.

        Returns
        -------
        tuple of (int, float)
            The chosen arm and the reward it paid.
        """
        self.t += 1
        arm = self.choose_arm()
        reward = self.rng.normal(self.p[arm], 1.0 / np.sqrt(self.precision))
        self._last_arm = arm
        self._last_reward = reward
        return arm, reward

    def update(self):
        """Update the beliefs with the last pull and log it in the arrays."""
        arm, reward = self._last_arm, self._last_reward
        self.counts[arm] += 1
        self.learn(arm, reward)
        i = self.t - 1
        self.arms[i] = arm
        self.rewards[i] = reward
        self.regrets[i] = self.best_mean - self.p[arm]
        self.history[i] = self.estimates

    def experiment(self):
        """Run the full experiment of pull/update steps."""
        for _ in range(self.trials):
            self.pull()
            self.update()
        logger.info(f"{self.name}: finished {self.trials} trials")

    @property
    def cumulative_rewards(self):
        return np.cumsum(self.rewards)

    @property
    def cumulative_regrets(self):
        return np.cumsum(self.regrets)

    def to_frame(self):
        """Return the trial data as a DataFrame with Bandit, Reward, Algorithm columns."""
        return pd.DataFrame(
            {
                "Bandit": self.p[self.arms].astype(int),
                "Reward": self.rewards,
                "Algorithm": self.name,
            }
        )

    def report(self):
        """Save the rewards to csv and log the main numbers.

        Returns
        -------
        pandas.DataFrame
            The data that was written to the csv file.
        """
        OUTPUT_DIR.mkdir(exist_ok=True)
        frame = self.to_frame()
        path = OUTPUT_DIR / f"{self.name.lower().replace(' ', '_')}_rewards.csv"
        frame.to_csv(path, index=False)
        logger.info(f"{self.name}: rewards saved to {path}")
        logger.info(f"{self.name}: average reward = {self.rewards.mean():.4f}")
        logger.info(f"{self.name}: average regret = {self.regrets.mean():.4f}")
        logger.info(f"{self.name}: cumulative reward = {self.cumulative_rewards[-1]:.2f}")
        logger.info(f"{self.name}: cumulative regret = {self.cumulative_regrets[-1]:.2f}")
        return frame


class EpsilonGreedy(BaseExperiment):
    """Epsilon-greedy with epsilon decaying as 1/t.

    At trial t the algorithm explores a random arm with probability 1/t and
    otherwise exploits the arm with the best sample-mean estimate.
    """

    name = "Epsilon Greedy"

    def choose_arm(self):
        epsilon = 1.0 / self.t
        if self.rng.random() < epsilon:
            return int(self.rng.integers(self.k))
        return int(np.argmax(self.estimates))

    def learn(self, arm, reward):
        self.estimates[arm] += (reward - self.estimates[arm]) / self.counts[arm]


class ThompsonSampling(BaseExperiment):
    """Thompson Sampling for normal rewards with known precision.

    Every arm has a normal prior on its mean. Since the noise precision is
    known, the posterior stays normal and only its mean and precision move.

    Parameters
    ----------
    prior_mean : float, optional
        Mean of the prior on every arm.
    prior_precision : float, optional
        Precision of the prior on every arm.
    """

    name = "Thompson Sampling"

    def __init__(self, p, trials=NumberOfTrials, precision=PRECISION, seed=SEED,
                 prior_mean=0.0, prior_precision=1.0):
        super().__init__(p, trials, precision, seed)
        self.prior_mean = prior_mean
        self.prior_precision = prior_precision
        self.post_precision = np.full(self.k, prior_precision, dtype=float)
        self.estimates = np.full(self.k, prior_mean, dtype=float)
        self.reward_sums = np.zeros(self.k)

    def choose_arm(self):
        draws = self.rng.normal(self.estimates, 1.0 / np.sqrt(self.post_precision))
        return int(np.argmax(draws))

    def learn(self, arm, reward):
        self.reward_sums[arm] += reward
        n = self.counts[arm]
        self.post_precision[arm] = self.prior_precision + n * self.precision
        self.estimates[arm] = (
            self.prior_precision * self.prior_mean + self.precision * self.reward_sums[arm]
        ) / self.post_precision[arm]


class Visualization():
    """Plots for the two finished experiments.

    Parameters
    ----------
    epsilon_greedy : EpsilonGreedy
        A bandit object whose experiment already ran.
    thompson : ThompsonSampling
        A bandit object whose experiment already ran.
    """

    def __init__(self, epsilon_greedy, thompson):
        self.eg = epsilon_greedy
        self.ts = thompson
        OUTPUT_DIR.mkdir(exist_ok=True)

    def plot1(self):
        """Learning process of each algorithm, on a linear and on a log x axis."""
        for algo in (self.eg, self.ts):
            fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
            x = np.arange(1, algo.trials + 1)
            for ax, scale in zip(axes, ("linear", "log")):
                for arm in range(algo.k):
                    ax.plot(x, algo.history[:, arm], label=f"Bandit {int(algo.p[arm])}")
                    ax.axhline(algo.p[arm], color="gray", linestyle=":", linewidth=0.8)
                ax.set_xscale(scale)
                ax.set_xlabel("Trial")
                ax.set_ylabel("Estimated mean reward")
                ax.set_title(f"{algo.name} ({scale} scale)")
                ax.legend()
            fig.tight_layout()
            path = OUTPUT_DIR / f"learning_{algo.name.lower().replace(' ', '_')}.png"
            fig.savefig(path, dpi=130)
            plt.close(fig)
            logger.info(f"saved {path}")

    def plot2(self):
        """Cumulative rewards and cumulative regrets of both algorithms side by side."""
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
        for algo in (self.eg, self.ts):
            axes[0].plot(algo.cumulative_rewards, label=algo.name)
            axes[1].plot(algo.cumulative_regrets, label=algo.name)
        axes[0].set_title("Cumulative reward")
        axes[1].set_title("Cumulative regret")
        for ax in axes:
            ax.set_xlabel("Trial")
            ax.legend()
        axes[0].set_ylabel("Reward")
        axes[1].set_ylabel("Regret")
        fig.tight_layout()
        path = OUTPUT_DIR / "comparison_cumulative.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        logger.info(f"saved {path}")


def comparison():
    """Run both algorithms, compare them numerically and visually.

    Returns
    -------
    pandas.DataFrame
        Summary table with one row per algorithm.
    """
    eg = EpsilonGreedy(Bandit_Reward)
    ts = ThompsonSampling(Bandit_Reward)
    for algo in (eg, ts):
        logger.info(repr(algo))
        algo.experiment()

    frames = [eg.report(), ts.report()]
    pd.concat(frames, ignore_index=True).to_csv(OUTPUT_DIR / "rewards.csv", index=False)

    viz = Visualization(eg, ts)
    viz.plot1()
    viz.plot2()

    rows = []
    for algo in (eg, ts):
        share_best = np.mean(algo.arms == np.argmax(algo.p))
        rows.append(
            {
                "Algorithm": algo.name,
                "Cumulative reward": round(algo.cumulative_rewards[-1], 2),
                "Cumulative regret": round(algo.cumulative_regrets[-1], 2),
                "Best arm share": round(share_best, 4),
            }
        )
    summary = pd.DataFrame(rows)
    logger.info("\n" + summary.to_string(index=False))

    winner = summary.loc[summary["Cumulative regret"].idxmin(), "Algorithm"]
    logger.info(f"lower cumulative regret: {winner}")
    return summary


if __name__ == '__main__':
    logger.debug("starting A/B testing experiment")
    logger.debug(f"bandit rewards {Bandit_Reward}, trials {NumberOfTrials}")
    comparison()
    logger.debug("done")
