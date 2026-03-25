import pandas as pd
import numpy as np

# -------------------------
# Load matchlog
# -------------------------
df = pd.read_csv("data/tt_czech_matchlogs.csv")

# -------------------------
# Preprocessing
# -------------------------
df['match_date'] = pd.to_datetime(df['match_date'])
df = df.sort_values('match_date')

# Non-sweep indicator
df['is_non_sweep'] = df['four_plus']

# -------------------------
# Compute L30 NS%
# -------------------------
def compute_l30_ns(group):
    group = group.sort_values('match_date')
    group['NS_L30'] = group['is_non_sweep'].rolling(30, min_periods=1).mean() * 100
    return group

df = df.groupby(['player1', 'player2'], group_keys=False).apply(compute_l30_ns)

# -------------------------
# Parameters
# -------------------------
NS_THRESHOLD = 82
SAMPLE_SIZE = 10
SIMULATIONS = 10000

# Martingale structure
PAYOUT_SET2 = 0.833   # profit from 1u @ -120
PAYOUT_SET3 = 0.666   # net profit after recovery
LOSS_SWEEP = -3.0

# Assumption split
P_SET2_WIN = 0.65
P_SET3_WIN = 0.35

# -------------------------
# Filter matches
# -------------------------
df_threshold = df[df['NS_L30'] >= NS_THRESHOLD]

total_matches = len(df_threshold)
non_sweeps = df_threshold['is_non_sweep'].sum()
sweeps = total_matches - non_sweeps

p_non_sweep = non_sweeps / total_matches if total_matches > 0 else 0
p_sweep = 1 - p_non_sweep

# -------------------------
# Expected value calculation
# -------------------------
p_set2 = p_non_sweep * P_SET2_WIN
p_set3 = p_non_sweep * P_SET3_WIN

expected_profit = (
    p_set2 * PAYOUT_SET2 +
    p_set3 * PAYOUT_SET3 +
    p_sweep * LOSS_SWEEP
)

# -------------------------
# Monte Carlo simulation
# -------------------------
profit_samples = []

for _ in range(SIMULATIONS):
    profit = 0
    for _ in range(SAMPLE_SIZE):
        r = np.random.rand()

        if r < p_set2:
            profit += PAYOUT_SET2
        elif r < p_set2 + p_set3:
            profit += PAYOUT_SET3
        else:
            profit += LOSS_SWEEP

    profit_samples.append(profit)

profit_samples = np.array(profit_samples)

# -------------------------
# Output
# -------------------------
print("=== Martingale Strategy Simulation ===")
print(f"Matches meeting NS ≥ {NS_THRESHOLD}%: {total_matches}")
print(f"Non-sweep rate: {p_non_sweep*100:.2f}%")
print(f"Sweep rate: {p_sweep*100:.2f}%")
print()
print(f"Expected profit per match: {expected_profit:.3f}")
print()
print(f"Sample size {SAMPLE_SIZE}:")
print(f"Mean profit: {profit_samples.mean():.2f}")
print(f"Std dev: {profit_samples.std():.2f}")
print(f"95% range: {profit_samples.mean() - 2*profit_samples.std():.2f} to {profit_samples.mean() + 2*profit_samples.std():.2f}")