import pandas as pd
import math
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import joblib

############################################
# 1. LOAD MATCHLOG DATA
############################################

df = pd.read_csv("data/tt_elite_matchlogs.csv")

df["date"] = pd.to_datetime(df["date"])

# Sort oldest -> newest for Elo calculations
df = df.sort_values("date").reset_index(drop=True)

############################################
# 2. CREATE TARGET VARIABLE (4+ SETS)
############################################

df["four_plus_sets"] = ((df["sets1"] + df["sets2"]) >= 4).astype(int)

############################################
# 3. INITIALIZE ELO RATINGS
############################################

START_RATING = 1500
K = 32

elo = {}

def expected(r1, r2):
    return 1 / (1 + 10 ** ((r2 - r1) / 400))

elo1_list = []
elo2_list = []

############################################
# 4. GENERATE ELO RATINGS
############################################

for _, row in df.iterrows():

    p1 = row["player1"]
    p2 = row["player2"]

    r1 = elo.get(p1, START_RATING)
    r2 = elo.get(p2, START_RATING)

    # store ratings BEFORE the match
    elo1_list.append(r1)
    elo2_list.append(r2)

    exp1 = expected(r1, r2)

    score1 = 1 if row["sets1"] > row["sets2"] else 0

    r1_new = r1 + K * (score1 - exp1)
    r2_new = r2 + K * ((1-score1) - (1-exp1))

    elo[p1] = r1_new
    elo[p2] = r2_new

df["elo1"] = elo1_list
df["elo2"] = elo2_list

############################################
# 5. CREATE MODEL FEATURES
############################################

df["rating_diff"] = abs(df["elo1"] - df["elo2"])

X = df[["rating_diff"]]
y = df["four_plus_sets"]

############################################
# 6. TRAIN / TEST SPLIT
############################################

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

############################################
# 7. TRAIN MODEL
############################################

model = LogisticRegression()

model.fit(X_train, y_train)

############################################
# 8. EVALUATE MODEL
############################################

preds = model.predict_proba(X_test)[:,1]

auc = roc_auc_score(y_test, preds)

print("Model AUC:", round(auc,3))

############################################
# 9. SAVE MODEL + RATINGS
############################################

joblib.dump(model, "four_plus_model.pkl")
joblib.dump(elo, "elo_ratings.pkl")

print("Model saved.")