import pandas as pd

df = pd.read_csv("data/tt_czech_matchlogs.csv", parse_dates=["match_date"])

def parse_sets(s):
    if not isinstance(s, str):
        return []
    return s.split('|')

df["set_count"] = df["sets"].apply(lambda x: len(parse_sets(x)))

df["matchup"] = df.apply(lambda r: tuple(sorted([r["player1"], r["player2"]])), axis=1)

df = df.sort_values("match_date").reset_index(drop=True)

history = {}
records = []

for _, row in df.iterrows():
    m = row["matchup"]

    if m not in history:
        history[m] = []

    prior = history[m]

    avg_sets = sum(prior)/len(prior) if len(prior) > 0 else None

    records.append({
        "matchup": m,
        "prior_avg_sets": avg_sets,
        "samples": len(prior),
        "actual_sets": row["set_count"]
    })

    history[m].append(row["set_count"])

eval_df = pd.DataFrame(records)
eval_df = eval_df[eval_df["prior_avg_sets"].notna()]

# Bucket by avg sets
def bucket(x):
    if x >= 4.5: return "4.5+"
    elif x >= 4.0: return "4.0-4.5"
    elif x >= 3.5: return "3.5-4.0"
    else: return "<3.5"

eval_df["bucket"] = eval_df["prior_avg_sets"].apply(bucket)

summary = eval_df.groupby("bucket").agg(
    samples=("actual_sets", "count"),
    avg_actual_sets=("actual_sets", "mean")
).reset_index()

print(summary)
summary.to_csv("data/setlength_predictiveness.csv", index=False)