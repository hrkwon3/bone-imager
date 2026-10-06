import os, json
import numpy as np
import pandas as pd
import optuna
from sklearn.metrics import f1_score, classification_report, confusion_matrix

# =========================
# Config
# =========================
#data_dir   = "/xxx/training_set"     # folder with *_pixels.csv and *_mask_curated.csv
HEIGHT, WIDTH = 220, 720             # expected size for all slices
USE_MEDIAN   = True                   # use median over slices (robust) vs mean
N_TRIALS     = 60                     # Optuna trials
# Class weights for the objective (emphasize M if you want)
W_B, W_S, W_M = 1.0, 1.0, 2.0
# =========================


# ---------- Pair finder ----------
def find_pairs(folder: str):
    """
    Match *_pixels.csv with *_mask_curated.csv in the same folder.
    """
    pairs = []
    for fname in sorted(os.listdir(folder)):
        if fname.endswith("_pixels.csv"):
            base = fname[:-11]  # strip "_pixels.csv" (11 chars)
            pix_path = os.path.join(folder, fname)
            gt_path  = os.path.join(folder, f"{base}_mask_curated.csv")
            if os.path.exists(gt_path):
                pairs.append((pix_path, gt_path))
            else:
                print(f"⚠ GT missing for {fname}")
    print(f"Found {len(pairs)} pairs")
    return pairs


# ---------- Loaders ----------
def load_pixels_csv(pix_path, expected_shape=(220, 720)):
    df = pd.read_csv(pix_path, header=None)
    H, W = expected_shape
    df = df.iloc[:H, :W]
    if df.shape != (H, W):
        raise ValueError(f"{os.path.basename(pix_path)} shape {df.shape} != {(H, W)}")
    # coerce to 0..255 uint8
    arr = pd.DataFrame(df).apply(pd.to_numeric, errors="coerce").fillna(0).values
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr

def load_mask_csv(mask_path, expected_shape=(220, 720)):
    df = pd.read_csv(mask_path, header=None)
    H, W = expected_shape
    df = df.iloc[:H, :W]
    if df.shape != (H, W):
        raise ValueError(f"{os.path.basename(mask_path)} shape {df.shape} != {(H, W)}")
    lab = df.values.astype(str)
    # normalize labels to ".", "B", "S", "M"
    lab = np.char.upper(np.char.strip(lab))
    return lab


# ---------- Rule-based segmenter ----------
def apply_rules(arr, params):
    """
    params:
      S_LOW, S_HIGH, B_LOW: intensity thresholds
      INT_MAX_M: max intensity to consider marrow candidate
      X_WIN, Y_WIN, BOTTOM_SKIP: geometry windows
      BAL_TOL, MIN_ABOVE, MIN_BELOW: vertical veto configuration
    """
    """
    Adds two protections against edge false-positives:
      (A) Row-wise enclosure veto: require x to lie between leftmost and rightmost S/B on that row (± ENC_MARGIN)
      (B) Side-edge stricter band: near left/right edges, require tighter horizontal sandwich (EDGE_X_WIN) or forbid

    Tunable params (in addition to your existing ones):
      ENC_MARGIN      : int (pixels) — expand/contract the per-row envelope (default small, e.g., 2–10)
      EDGE_BAND       : int (columns) — width of stricter band from each side (0 disables)
      EDGE_X_WIN      : int (pixels) — smaller ±window to search S/B inside the edge band
      EDGE_POLICY     : str in {'tight', 'forbid'} — either apply tighter rule or forbid M in edge band
    """
    H, W = arr.shape

    # ---- Base knobs (same as before) ----
    S_LOW       = params["S_LOW"]
    S_HIGH      = params["S_HIGH"]
    B_LOW       = params["B_LOW"]
    INT_MAX_M   = params["INT_MAX_M"]
    X_WIN       = params["X_WIN"]
    Y_WIN       = params["Y_WIN"]
    BOTTOM_SKIP = params["BOTTOM_SKIP"]
    BAL_TOL     = params["BAL_TOL"]
    MIN_ABOVE   = params["MIN_ABOVE"]
    MIN_BELOW   = params["MIN_BELOW"]

    # ---- New knobs for edge handling ----
    ENC_MARGIN  = params.get("ENC_MARGIN", 4)                 # row-wise envelope slack
    EDGE_BAND   = params.get("EDGE_BAND", 0)                  # 0 disables edge band logic
    EDGE_X_WIN  = params.get("EDGE_X_WIN", max(5, X_WIN//3))  # tighter window at edges
    EDGE_POLICY = params.get("EDGE_POLICY", "tight")          # 'tight' or 'forbid'

    # 1) First pass: S/B by intensity
    mask = np.full((H, W), ".", dtype=object)
    for y in range(H):
        row = arr[y]
        for x in range(W):
            v = row[x]
            if S_LOW <= v <= S_HIGH:
                mask[y, x] = "S"
            elif v >= B_LOW:
                mask[y, x] = "B"

    base = mask.copy()

    # 2) Precompute row-wise enclosure from S/B for each row (leftmost & rightmost SB)
    #    If a row has no S/B, set to (-1, -1) which will veto all M on that row.
    row_left = np.full(H, -1, dtype=int)
    row_right = np.full(H, -1, dtype=int)
    for y in range(H):
        sb_indices = np.where(np.isin(base[y], ["S", "B"]))[0]
        if sb_indices.size:
            row_left[y] = sb_indices.min()
            row_right[y] = sb_indices.max()

    # 3) Second pass: M assignment with new vetos
    for y in range(H):
        # compute row envelope (with margin) once per row
        L, R = row_left[y], row_right[y]
        if L != -1 and R != -1:
            Lm = max(0, L - ENC_MARGIN)
            Rm = min(W - 1, R + ENC_MARGIN)
        else:
            Lm, Rm = -1, -1  # disables M on this row

        for x in range(W):
            if arr[y, x] > INT_MAX_M:
                continue

            # --- (A) Row-wise enclosure veto ---
            # Require x to lie inside the row's SB envelope.
            if Lm == -1 or x < Lm or x > Rm:
                # Outside the envelope → cannot be marrow
                continue

            # --- Horizontal sandwich (primary condition) ---
            # Edge band: optionally use a tighter horizontal window or forbid
            in_edge_band = (EDGE_BAND > 0) and (x < EDGE_BAND or x >= W - EDGE_BAND)

            if in_edge_band:
                if EDGE_POLICY == "forbid":
                    continue  # never allow M in the side band
                # 'tight' policy: use smaller X window
                xw = EDGE_X_WIN
            else:
                xw = X_WIN

            x_min = max(0, x - xw)
            x_max = min(W, x + xw + 1)
            left  = base[y, x_min:x]
            right = base[y, x+1:x_max]
            has_l = ("S" in left) or ("B" in left)
            has_r = ("S" in right) or ("B" in right)

            # Bottom band: skip vertical veto (unchanged)
            if y >= H - BOTTOM_SKIP:
                if has_l and has_r:
                    mask[y, x] = "M"
                continue

            if not (has_l and has_r):
                continue

            # --- Vertical veto (same as before) ---
            y_min = max(0, y - Y_WIN)
            y_max = min(H, y + Y_WIN + 1)
            above = base[y_min:y, x]
            below = base[y+1:y_max, x]
            above_SB = np.count_nonzero(np.isin(above, ["S", "B"]))
            below_SB = np.count_nonzero(np.isin(below, ["S", "B"]))

            too_lopsided = abs(above_SB - below_SB) > BAL_TOL
            insufficient = (above_SB < MIN_ABOVE) or (below_SB < MIN_BELOW)

            if not (too_lopsided or insufficient):
                mask[y, x] = "M"

    return mask



# ---------- Scoring ----------
def f1_for_label(pred, gt, label):
    y_true = (gt.ravel() == label).astype(int)
    y_pred = (pred.ravel() == label).astype(int)
    if y_true.sum() == 0 and y_pred.sum() == 0:
        return 1.0
    return f1_score(y_true, y_pred, zero_division=1)

def weighted_score(pred, gt, w_b=1.0, w_s=1.0, w_m=2.0):
    fB = f1_for_label(pred, gt, "B")
    fS = f1_for_label(pred, gt, "S")
    fM = f1_for_label(pred, gt, "M")
    return (w_b * fB + w_s * fS + w_m * fM) / (w_b + w_s + w_m)


# =========================
# Main
# =========================
def main():
    # Build and preload pairs
    pairs = find_pairs(data_dir)
    if not pairs:
        raise RuntimeError("No (pixels, GT) pairs found. Check filenames/suffixes.")

    PIX, GT, kept = [], [], []
    for pix_path, gt_path in pairs:
        try:
            arr = load_pixels_csv(pix_path, expected_shape=(HEIGHT, WIDTH))
            gt  = load_mask_csv(gt_path,  expected_shape=(HEIGHT, WIDTH))
        except Exception as e:
            print(f"Skipping {os.path.basename(pix_path)}: {e}")
            continue
        PIX.append(arr); GT.append(gt); kept.append((pix_path, gt_path))

    if not PIX:
        raise RuntimeError("No valid pairs after loading. Check shapes/dimensions.")

    def objective(trial):
        params = {
            # Intensity thresholds
            "S_LOW":       trial.suggest_int("S_LOW", 50, 70),
            "S_HIGH":      trial.suggest_int("S_HIGH", 70, 95),
            "B_LOW":       trial.suggest_int("B_LOW", 75, 120),

            # Marrow candidate threshold
            "INT_MAX_M":   trial.suggest_int("INT_MAX_M", 40, 100),

            # Geometry windows
            "X_WIN":       trial.suggest_int("X_WIN", 30, 150, step=5),
            "Y_WIN":       trial.suggest_int("Y_WIN", 20, 150, step=5),
            "BOTTOM_SKIP": trial.suggest_int("BOTTOM_SKIP", 0, 150, step=5),

            # Vertical veto
            "BAL_TOL":     trial.suggest_int("BAL_TOL", 5, 50),
            "MIN_ABOVE":   trial.suggest_int("MIN_ABOVE", 0, 3),
            "MIN_BELOW":   trial.suggest_int("MIN_BELOW", 0, 3),

            # NEW
            "ENC_MARGIN":  trial.suggest_int("ENC_MARGIN", 0, 12, step=2),
            "EDGE_BAND":   trial.suggest_int("EDGE_BAND", 0, 60, step=5),      # 0 disables
            "EDGE_X_WIN":  trial.suggest_int("EDGE_X_WIN", 5, 50, step=5),
            "EDGE_POLICY": trial.suggest_categorical("EDGE_POLICY", ["tight","forbid"]),

        }

        # Keep ranges consistent
        if params["S_LOW"] > params["S_HIGH"]:
            return 0.0
        if params["B_LOW"] <= params["S_HIGH"]:
            return 0.0

        scores = []
        for arr, gt in zip(PIX, GT):
            pred = apply_rules(arr, params)
            scores.append(weighted_score(pred, gt, W_B, W_S, W_M))
        return float(np.median(scores) if USE_MEDIAN else np.mean(scores))

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

    completed = [t for t in study.trials if t.value is not None]
    if not completed:
        print("No completed trials. Check data and logs above.")
        return

    best = study.best_params
    print("\nBest score:", study.best_value)
    print("Best params:", json.dumps(best, indent=2))

    # Optional: evaluate best on each slice & print quick summary
    per_slice = []
    for (pix_path, gt_path), arr, gt in zip(kept, PIX, GT):
        pred = apply_rules(arr, best)
        fB = f1_for_label(pred, gt, "B")
        fS = f1_for_label(pred, gt, "S")
        fM = f1_for_label(pred, gt, "M")
        per_slice.append((os.path.basename(pix_path), fB, fS, fM))
    print("\nPer-slice F1 (B, S, M):")
    for name, fB, fS, fM in per_slice[:10]:  # first 10 for brevity
        print(f"{name}: B={fB:.3f}, S={fS:.3f}, M={fM:.3f}")

    # Save best params
    with open("best_params.json", "w") as f:
        json.dump(best, f, indent=2)
    print("\nSaved best_params.json")

if __name__ == "__main__":
    main()
