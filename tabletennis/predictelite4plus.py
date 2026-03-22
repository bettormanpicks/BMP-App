import pandas as pd

INPUT_CSV = "data/tt_elite_features_weighted.csv"
OUTPUT_CSV = "data/tt_elite_4plus_predictions.csv"

df = pd.read_csv(INPUT_CSV)

def reliability_adjust(stat, baseline, count, window):
    """Shrink stat toward baseline depending on sample size."""
    reliability = min(count / window, 1)
    return baseline + (stat - baseline) * reliability

def predict_probability(row):
    # baseline can be L30 or L60
    baseline = row["h2h_L30_weighted"]

    # counts
    h2h10_count = row["h2h_L10_count"]
    h2h60_count = row["h2h_L60_count"]

    # reliability adjustments
    h2h10 = reliability_adjust(row["h2h_L10_weighted"], baseline, h2h10_count, 10)
    h2h60 = reliability_adjust(row["h2h_L60_weighted"], baseline, h2h60_count, 60)

    # player match-length tendencies
    playerA_tendency = row["player_A_4plus_rate_last50"]
    playerB_tendency = row["player_B_4plus_rate_last50"]

    tendency_avg = (playerA_tendency + playerB_tendency) / 2

    # player strength difference
    strength_diff = row["strength_diff_last50"]

    # weighted combination based on evaluation
    prob = baseline

    # H2H signal (still strongest)
    prob += 0.1 * (h2h10 - baseline)
    prob += 0.6 * (h2h60 - baseline)

    # player match-length tendencies
    prob += 0.2 * (tendency_avg - baseline)

    # strength difference (bigger mismatch = shorter matches)
    prob -= 0.15 * strength_diff

    # clamp to [0,1]
    return max(0, min(1, prob))

df["R_4plus"] = df.apply(predict_probability, axis=1)
df.to_csv(OUTPUT_CSV, index=False)

print("Predictions saved to:", OUTPUT_CSV)