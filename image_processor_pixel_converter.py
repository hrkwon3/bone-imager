from PIL import Image, ImageSequence, ImageDraw, ImageFont
import numpy as np
import pandas as pd
import json, os

# =====================
# Paths (edit these)
# =====================
# Please add the file address of tiff file here!
tiff_path = "xxx_cropped_2x_resized_output.tif"

BEST_PARAMS_JSON = "best_params.json"   # optional; if not found, defaults below are used

# =====================
# Defaults (used if no JSON is present)
# =====================
default_params = {
    # Intensity thresholds
    "S_LOW": 59, "S_HIGH": 80, "B_LOW": 82,
    # Marrow candidate
    "INT_MAX_M": 59,
    # Geometry windows
    "X_WIN": 110, "Y_WIN": 90, "BOTTOM_SKIP": 70,
    # Vertical veto
    "BAL_TOL": 33, "MIN_ABOVE": 3, "MIN_BELOW": 1,
    # Edge handling
    "ENC_MARGIN": 4,          # row envelope slack (pixels)
    "EDGE_BAND": 25,         # columns near left/right edges; 0 disables
    "EDGE_X_WIN": 30,         # tighter X window inside edge band
    "EDGE_POLICY": "tight",   # 'tight' or 'forbid'
}

# Try to load tuned params if present
params = default_params.copy()
if os.path.exists(BEST_PARAMS_JSON):
    try:
        with open(BEST_PARAMS_JSON, "r") as f:
            tuned = json.load(f)
        params.update(tuned)
        print("Loaded tuned params from best_params.json")
    except Exception as e:
        print(f"Warning: could not load best_params.json ({e}); using defaults.")

# =====================
# Outputs
# =====================
base, ext = os.path.splitext(tiff_path)
output_folder = f"{base}_converter"
os.makedirs(output_folder, exist_ok=True)

# Open the TIFF
im = Image.open(tiff_path)

# Collect frames to make a GIF at the end
color_frames = []

for idx, page in enumerate(ImageSequence.Iterator(im)):
    gray = page.convert("L")
    arr = np.array(gray)
    height, width = arr.shape

    # --- Save raw pixels CSV (no header/index) ---
    df_pixels = pd.DataFrame(arr)
    df_pixels.to_csv(os.path.join(output_folder, f"layer_{idx:04d}_pixels.csv"), index=False, header=False)

    # --------------------------------------------
    # 1st pass: intensity -> S, B (tunable)
    # --------------------------------------------
    mask = np.full((height, width), ".", dtype=object)
    S_LOW, S_HIGH = params["S_LOW"], params["S_HIGH"]
    B_LOW = params["B_LOW"]

    # vectorized first pass (faster)
    S_mask = (arr >= S_LOW) & (arr <= S_HIGH)
    B_mask = (arr >= B_LOW)
    mask[S_mask] = "S"
    mask[B_mask] = "B"

    # snapshot for reference in 2nd pass
    base_mask = mask.copy()

    # ---------------------------------------------------------
    # Precompute row-wise enclosure (leftmost/rightmost S/B)
    # ---------------------------------------------------------
    row_left = np.full(height, -1, dtype=int)
    row_right = np.full(height, -1, dtype=int)
    sb = np.isin(base_mask, ["S", "B"])

    for y in range(height):
        cols = np.where(sb[y])[0]
        if cols.size:
            row_left[y] = int(cols.min())
            row_right[y] = int(cols.max())

    # --------------------------------------------
    # 2nd pass: assign M with edge protections
    # --------------------------------------------
    X_WIN       = params["X_WIN"]
    Y_WIN       = params["Y_WIN"]
    BOTTOM_SKIP = params["BOTTOM_SKIP"]
    INT_MAX_M   = params["INT_MAX_M"]
    BAL_TOL     = params["BAL_TOL"]
    MIN_ABOVE   = params["MIN_ABOVE"]
    MIN_BELOW   = params["MIN_BELOW"]
    ENC_MARGIN  = params.get("ENC_MARGIN", 4)
    EDGE_BAND   = params.get("EDGE_BAND", 0)
    EDGE_X_WIN  = params.get("EDGE_X_WIN", max(5, X_WIN//3))
    EDGE_POLICY = params.get("EDGE_POLICY", "tight")

    for y in range(height):
        # row envelope with margin
        L, R = row_left[y], row_right[y]
        if L != -1 and R != -1:
            Lm = max(0, L - ENC_MARGIN)
            Rm = min(width - 1, R + ENC_MARGIN)
        else:
            Lm, Rm = -1, -1  # disables M on this row (no S/B seen)

        for x in range(width):
            # intensity gate for marrow candidates
            if arr[y, x] > INT_MAX_M:
                continue

            # must be inside S/B envelope for the row
            if Lm == -1 or x < Lm or x > Rm:
                continue

            # choose horizontal window (edge band vs interior)
            in_edge_band = (EDGE_BAND > 0) and (x < EDGE_BAND or x >= width - EDGE_BAND)
            if in_edge_band and EDGE_POLICY == "forbid":
                continue
            xw = EDGE_X_WIN if in_edge_band else X_WIN

            # horizontal sandwich search
            x_min = max(0, x - xw)
            x_max = min(width, x + xw + 1)
            left_vals  = base_mask[y, x_min:x]
            right_vals = base_mask[y, x+1:x_max]
            has_l = ("S" in left_vals) or ("B" in left_vals)
            has_r = ("S" in right_vals) or ("B" in right_vals)

            # bottom band: accept by horizontal only
            if y >= height - BOTTOM_SKIP:
                if has_l and has_r:
                    mask[y, x] = "M"
                continue

            if not (has_l and has_r):
                continue

            # vertical veto
            y_min = max(0, y - Y_WIN)
            y_max = min(height, y + Y_WIN + 1)
            above = base_mask[y_min:y, x]
            below = base_mask[y+1:y_max, x]
            above_SB = np.count_nonzero(np.isin(above, ["S", "B"]))
            below_SB = np.count_nonzero(np.isin(below, ["S", "B"]))

            too_lopsided = abs(above_SB - below_SB) > BAL_TOL
            insufficient = (above_SB < MIN_ABOVE) or (below_SB < MIN_BELOW)
            if not (too_lopsided or insufficient):
                mask[y, x] = "M"

    # --- Save masking CSV (no header/index) ---
    pd.DataFrame(mask).to_csv(os.path.join(output_folder, f"layer_{idx:04d}_mask.csv"),
                              index=False, header=False)

    # --- Colored preview (white='.', yellow=B, red=S, green=M) ---
    rgb = np.full((height, width, 3), 255, dtype=np.uint8)
    mB = (mask == "B"); rgb[mB] = (255, 255, 200)
    mS = (mask == "S"); rgb[mS] = (255, 200, 200)
    mM = (mask == "M"); rgb[mM] = (200, 255, 200)

    img_color = Image.fromarray(rgb)
    img_color.save(os.path.join(output_folder, f"layer_{idx:04d}_mask_color.jpg"), quality=95)
    color_frames.append(img_color)

# Save animated GIF of the colored stack
if color_frames:
    gif_path = os.path.join(output_folder, "mask_color_stack.gif")
    color_frames[0].save(
        gif_path,
        save_all=True,
        append_images=color_frames[1:],
        duration=200,
        loop=0,
        disposal=2
    )

print("✅ Done: pixels/masks saved, colored previews written, GIF created.")










"""
# Output settings
base, ext = os.path.splitext(tiff_path)
output_path = f"{base}_resized_output{ext}"
output_folder = f"{base}_converter"
os.makedirs(output_folder, exist_ok=True)

# Open the TIFF
im = Image.open(tiff_path)
#font = ImageFont.load_default()
#scale_factor = 10  # Resize for annotation

# 1) Before the page loop, prepare a list to collect colored frames
color_frames = []  # collect per-layer colored images for a GIF

for idx, page in enumerate(ImageSequence.Iterator(im)):
    gray = page.convert("L")
    arr = np.array(gray)

    # --- Save raw pixel values ---
    df_pixels = pd.DataFrame(arr)
    df_pixels.index.name = 'Y'
    df_pixels.columns = [f'X{x}' for x in df_pixels.columns]
    df_pixels.to_csv(os.path.join(output_folder, f"layer_{idx:04d}_pixels.csv"), index=False, header=False)


    # --- Apply masking before resizing ---
    height, width = arr.shape
    mask = np.full_like(arr, '.', dtype=object)

    # 1st pass: Assign 'S' and 'B'
    for y in range(height):
        for x in range(width):
            val = arr[y, x]
            if 61 <= val <= 80:
                mask[y, x] = 'S'
            elif 81 <= val <= 255:
                mask[y, x] = 'B'

    # ========= Tunable knobs =========
    X_WIN       = 110   # ±X pixels to look for S/B on left/right
    Y_WIN       = 30   # ±Y pixels for vertical veto
    BOTTOM_SKIP = 90   # rows from bottom where we skip vertical veto
    INT_MAX_M   = 60   # intensity threshold for marrow candidate (<= this)
    BAL_TOL     = 23   # vertical balance tolerance
    MIN_ABOVE   = 1
    MIN_BELOW   = 1
    EDGE_BAND   = X_WIN  # how far from left/right edge to treat as "corner"
    # =================================

    mask_base = mask.copy()

    for y in range(height):
        for x in range(width):
            # Only consider low-intensity candidates
            if arr[y, x] > INT_MAX_M:
                continue

            # --- Horizontal S/B search ---
            x_min = max(0, x - X_WIN)
            x_max = min(width, x + X_WIN + 1)
            left  = mask_base[y, x_min:x]
            right = mask_base[y, x+1:x_max]

            has_SB_left  = ('S' in left) or ('B' in left)
            has_SB_right = ('S' in right) or ('B' in right)

            # --- Bottom band: apply corner-friendly rules ---
            if y >= height - BOTTOM_SKIP:
                # Near left edge: only need RIGHT S/B
                if x <= EDGE_BAND:
                    if has_SB_right:
                        mask[y, x] = 'M'
                    # else leave '.'
                    continue

                # Near right edge: only need LEFT S/B
                if x >= width - 1 - EDGE_BAND:
                    if has_SB_left:
                        mask[y, x] = 'M'
                    # else leave '.'
                    continue

                # Bottom middle: need both
                if has_SB_left and has_SB_right:
                    mask[y, x] = 'M'
                # else leave '.'
                continue  # bottom band handled, move on

            # --- Not in bottom band: require horizontal enclosure first ---
            if not (has_SB_left and has_SB_right):
                continue

            # --- Vertical veto (sanity check) ---
            y_min = max(0, y - Y_WIN)
            y_max = min(height, y + Y_WIN + 1)
            above = mask_base[y_min:y, x]
            below = mask_base[y + 1:y_max, x]

            above_SB = np.count_nonzero(np.isin(above, ['S', 'B']))
            below_SB = np.count_nonzero(np.isin(below, ['S', 'B']))

            too_lopsided = abs(above_SB - below_SB) > BAL_TOL
            insufficient = (above_SB < MIN_ABOVE) or (below_SB < MIN_BELOW)
    
            if not (too_lopsided or insufficient):
                mask[y, x] = 'M'
            # else leave '.'

#    # 2nd pass: Assign 'M' where 0–50 and sandwiched in ±80 x-direction
#    for y in range(height):
#        for x in range(width):
#            val = arr[y, x]
#            if val <= 60:
#                # --- X-direction (left/right sandwich) ---
#                x_min = max(0, x - 100)
#                x_max = min(width, x + 101)
#                left = mask[y, x_min:x]
#                right = mask[y, x+1:x_max]

#                has_SB_left = 'S' in left or 'B' in left
#                has_SB_right = 'S' in right or 'B' in right

#                # --- Skip y-direction check near bottom edge ---
#                Y_WIN = 50
#                BOTTOM_SKIP = 0

#                if y >= height - BOTTOM_SKIP:
#                    if has_SB_left and has_SB_right:
#                        mask[y, x] = 'M'
#                    else:
#                        mask[y, x] = '.'
#                else:
#                    # --- Y-direction (quality + balance) ---
#                    y_min = max(0, y - Y_WIN)
#                    y_max = min(height, y + Y_WIN + 1)
#                    above = mask[y_min:y, x]
#                    below = mask[y + 1:y_max, x]
#                    above_SB = np.count_nonzero(np.isin(above, ['S', 'B']))
#                    below_SB = np.count_nonzero(np.isin(below, ['S', 'B']))

#                    #balanced = abs(above_SB - below_SB) <= 15
#                    #sufficient = above_SB >= 1 and below_SB >= 1

#                    # --- Final marrow condition ---
#                    #if has_SB_left and has_SB_right and balanced and sufficient:
#                    if has_SB_left and has_SB_right:
#                        mask[y, x] = 'M'
#                    else:
#                        mask[y, x] = '.'

    # --- Save masking file ---
    df_mask = pd.DataFrame(mask)
    df_mask.index.name = 'Y'
    df_mask.columns = [f'X{x}' for x in df_mask.columns]
    # df_mask.to_csv(os.path.join(output_folder, f"layer_{idx}_mask.csv"))
    df_mask.to_csv(os.path.join(output_folder, f"layer_{idx:04d}_mask.csv"), index=False, header=False)


    # --- Make a colored mask preview image (720x220) ---
    # Start as all white
    h, w = mask.shape
    rgb = np.full((h, w, 3), 255, dtype=np.uint8)

    # Build boolean masks
    mB = (mask == 'B')
    mS = (mask == 'S')
    mM = (mask == 'M')
    # '.' stays white

    # Apply colors
    rgb[mB] = (255, 255, 200)  # light yellow for B
    rgb[mS] = (255, 200, 200)  # light red for S
    rgb[mM] = (200, 255, 200)  # light green for M

    # Save per-layer JPEG
    img_color = Image.fromarray(rgb)  # size will be (width=720, height=220) pixels when your mask is 220x720
    img_color.save(os.path.join(output_folder, f"layer_{idx:04d}_mask_color.jpg"), quality=95)

    # Also keep for GIF
    color_frames.append(img_color)

if color_frames:
    gif_path = os.path.join(output_folder, "mask_color_stack.gif")
    color_frames[0].save(
        gif_path,
        save_all=True,
        append_images=color_frames[1:],
        duration=200,  # ms per frame
        loop=0,
        disposal=2
    )


    # --- Resize image for annotation ---
    #resized = gray.resize((width * scale_factor, height * scale_factor), Image.NEAREST)
    #mask_resized = np.array(resized)

    # Annotate pixel values
    #img_annotated = Image.new("RGB", resized.size, color="white")
    #draw = ImageDraw.Draw(img_annotated)
    #for y in range(0, mask_resized.shape[0], 10):
    #    for x in range(0, mask_resized.shape[1], 10):
    #        val = mask_resized[y, x]
    #        draw.text((x, y), str(val), fill="black", font=font)
    #
    #img_annotated.save(os.path.join(output_folder, f"annotated_layer_{idx}.tif"))





print("✅ Done: pixel + mask CSVs saved, annotated images created.")
"""