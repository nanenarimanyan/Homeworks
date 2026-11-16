# A/B Testing with Epsilon Greedy and Thompson Sampling

Four ads (bandits) pay a noisy reward with true means `[1, 2, 3, 4]`. Each algorithm gets 20000 trials and has to find the best ad while collecting as much reward as it can.

## Run

```
pip install -r requirements.txt
python Bandit.py
```

Everything lands in `results/`:

- `epsilon_greedy_rewards.csv`, `thompson_sampling_rewards.csv`, `rewards.csv` (columns: Bandit, Reward, Algorithm)
- `learning_epsilon_greedy.png`, `learning_thompson_sampling.png` (estimated mean of every bandit over time, linear and log x axis)
- `comparison_cumulative.png` (cumulative reward and cumulative regret of both algorithms)

Average reward, average regret, cumulative reward and cumulative regret are logged with loguru.

## Setup

- Reward of bandit `i` is drawn from a normal distribution with mean `p[i]` and precision 1.
- Epsilon Greedy: epsilon at trial `t` is `1/t`, estimates are updated incrementally.
- Thompson Sampling: normal prior (mean 0, precision 1) on every bandit, noise precision known and equal to 1, so the posterior stays normal.
- Regret of a pull is `max(p) - p[chosen bandit]`.
- Seed is fixed to 42 in `Bandit.py` (`SEED`).

## Results (seed 42)

| Algorithm | Cumulative reward | Cumulative regret | Share of pulls on best bandit |
|---|---|---|---|
| Epsilon Greedy | 73907.23 | 6181.00 | 0.6913 |
| Thompson Sampling | 79967.44 | 7.00 | 0.9998 |

Thompson Sampling wins clearly. Epsilon Greedy with a `1/t` decay explores almost nothing after the first few hundred trials, so in this run it settled on bandit 3 for about 6000 trials before a lucky exploration found bandit 4. Change the seed and that number moves a lot, which is exactly the weakness of the schedule.

## Bonus: a better implementation plan

1. **Run many seeds, not one.** A single run of Epsilon Greedy is mostly luck (see above). Repeat each algorithm 50 to 200 times with different seeds and plot the mean regret with a confidence band. Comparison then says something real.
2. **Fix the exploration schedule.** `1/t` decays too fast for noisy rewards. Better options: `c/sqrt(t)`, or `min(1, K*c/(d^2 * t))` where `d` is the smallest gap between bandits. Tune `c` on a grid and report it.
3. **Add UCB1 as a third baseline.** It needs no epsilon and no prior, and shows whether the gap to Thompson Sampling comes from the algorithm or from the bad schedule.
4. **Unknown precision for Thompson Sampling.** In real A/B tests the noise level is not known. Use a Normal-Gamma prior and sample precision and mean together. For click data a Beta-Bernoulli model fits better than a normal one.
5. **Drop the pseudo-regret assumption in reports.** Real campaigns do not know the true means. Also report the share of pulls on the best bandit and, for a live test, a stopping rule (for example stop when the posterior probability that one bandit is best passes 95 percent).
6. **Non-stationary rewards.** Ad performance drifts. Use a constant step size or a discounted posterior so old data is forgotten.
7. **Engineering.** Make rewards, epsilon, precision and number of trials command line arguments or a config file, vectorize the multi-seed runs with NumPy, add unit tests for the posterior update and the CSV output, and run them in CI on every push.
