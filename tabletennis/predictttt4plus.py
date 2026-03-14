import pandas as pd

INPUT_CSV = "data/tt_elite_features_weighted.csv"
OUTPUT_CSV = "data/tt_elite_4plus_predictions.csv"

df = pd.read_csv(INPUT_CSV)

# weights
w_h2h_l10 = 0.35
w_h2h_l60 = 0.15
w_a_l30 = 0.05
w_b_l30 = 0.05
w_a_l10 = 0.20
w_b_l10 = 0.20


def reliability_adjust(stat, baseline, count, window):

    reliability = min(count / window, 1)

    return baseline + (stat - baseline) * reliability

def predict_probability(row):

    baseline = row["h2h_L30_weighted"]

    # sample sizes
    h2h10_count = row["h2h_L10_count"]
    h2h30_count = row["h2h_L30_count"]
    h2h60_count = row["h2h_L60_count"]

    # reliability adjustments
    h2h10 = reliability_adjust(row["h2h_L10_weighted"], baseline, h2h10_count, 10)
    h2h60 = reliability_adjust(row["h2h_L60_weighted"], baseline, h2h60_count, 60)
    a_l10 = reliability_adjust(row["recent_A_L10"], baseline, 10, 10)
    b_l10 = reliability_adjust(row["recent_B_L10"], baseline, 10, 10)
    a_l30 = reliability_adjust(row["recent_A_L30"], baseline, 30, 30)
    b_l30 = reliability_adjust(row["recent_B_L30"], baseline, 30, 30)

    adj = 0

    adj += 0.35 * (h2h10 - baseline)
    adj += 0.15 * (h2h60 - baseline)
    adj += 0.20 * (a_l10 - baseline)
    adj += 0.20 * (b_l10 - baseline)
    adj += 0.05 * (a_l30 - baseline)
    adj += 0.05 * (b_l30 - baseline)

    prob = baseline + adj

    return max(0, min(1, prob))


df["P_4plus"] = df.apply(predict_probability, axis=1)

df.to_csv(OUTPUT_CSV, index=False)

print("Predictions saved to:", OUTPUT_CSV)