import os
import numpy as np
import pandas as pd
import math

# === Settings ===
#input_folder = 'xxx_cropped_2x_resized_output_converter/'  # CHANGE THIS

num_sectors = 30
angle_per_sector = 180 / num_sectors  # Only upper half

# === Set image center (bottom center) ===
height, width = 220, 720
center_x = width // 2
center_y = height - 1  # bottom row is y=219

# === Prepare output filename ===
input_folder_name = os.path.basename(os.path.normpath(input_folder))  # "bbb" from /usr/aaa/bbb
parent_folder = os.path.dirname(os.path.normpath(input_folder))       # "/usr/aaa"
output_excel = os.path.join(parent_folder, f"{input_folder_name}_sector_summary.xlsx")

# === Initialize summary tables ===
counts_summary = []
ratios_summary = []

# === Process each file ===
for filename in sorted(os.listdir(input_folder)):
    if filename.endswith("_mask.csv"):
        filepath = os.path.join(input_folder, filename)
        df = pd.read_csv(filepath, header=None)

        if df.shape != (height, width):
            print(f"Skipping {filename}: Unexpected shape {df.shape}")
            continue

        # Initialize counters
        count_row = {'Filename': filename}
        ratio_row = {'Filename': filename}
        total_B = total_S = total_M = 0

        for i in range(num_sectors):
            count_row[f'Sector_{i}_B'] = 0
            count_row[f'Sector_{i}_S'] = 0
            count_row[f'Sector_{i}_M'] = 0

        # Scan image
        for y in range(height):
            for x in range(width):
                val = str(df.iat[y, x]).strip().upper()
                if val not in ['B', 'S', 'M']:
                    continue

                dx = x - center_x
                dy = center_y - y
                angle = math.degrees(math.atan2(dy, dx))
                if angle < 0 or angle > 180:
                    continue

                sector = int(angle // angle_per_sector)
                if sector >= num_sectors:
                    sector = num_sectors - 1

                if val == 'B':
                    count_row[f'Sector_{sector}_B'] += 1
                elif val == 'S':
                    count_row[f'Sector_{sector}_S'] += 1
                elif val == 'M':
                    count_row[f'Sector_{sector}_M'] += 1

        # Compute sector-wise BS, Total, and Ratios
        for i in range(num_sectors):
            b = count_row[f'Sector_{i}_B']
            s = count_row[f'Sector_{i}_S']
            m = count_row[f'Sector_{i}_M']
            bs = b + s
            total = bs + m

            count_row[f'Sector_{i}_BS'] = bs
            count_row[f'Sector_{i}_Total'] = total

            ratio_row[f'Sector_{i}_B_Ratio'] = b / total if total > 0 else 0
            ratio_row[f'Sector_{i}_S_Ratio'] = s / total if total > 0 else 0
            ratio_row[f'Sector_{i}_BS_Ratio'] = bs / total if total > 0 else 0
            ratio_row[f'Sector_{i}_M_Ratio'] = m / total if total > 0 else 0

            # Running total
            total_B += b
            total_S += s
            total_M += m

        # Overall counts
        total_BS = total_B + total_S
        total_Total = total_BS + total_M
        count_row['Total_B'] = total_B
        count_row['Total_S'] = total_S
        count_row['Total_BS'] = total_BS
        count_row['Total_M'] = total_M
        count_row['Total_Total'] = total_Total

        ratio_row['Total_B_Ratio'] = total_B / total_Total if total_Total > 0 else 0
        ratio_row['Total_S_Ratio'] = total_S / total_Total if total_Total > 0 else 0
        ratio_row['Total_BS_Ratio'] = total_BS / total_Total if total_Total > 0 else 0
        ratio_row['Total_M_Ratio'] = total_M / total_Total if total_Total > 0 else 0

        # Save rows
        counts_summary.append(count_row)
        ratios_summary.append(ratio_row)

# === Save to Excel ===
with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
    pd.DataFrame(counts_summary).to_excel(writer, sheet_name='Counts', index=False)
    pd.DataFrame(ratios_summary).to_excel(writer, sheet_name='Ratios', index=False)

print(f"✅ Done! Summary saved to: {output_excel}")