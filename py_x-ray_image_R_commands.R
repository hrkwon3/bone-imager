library(readxl)
library(dplyr)
library(stringr)

# === 1. Define helper function to extract by location ===
extract_location_subset <- function(df, location) {
  pattern <- paste0("_", location, "$")  # matches columns ending in _B, _S, etc.
  subset_df <- df[, grepl(pattern, colnames(df)), drop = FALSE]
  return(subset_df)
}

# Function to subset by location in ratio sheet
extract_location_subset2 <- function(df, location) {
  pattern <- paste0("_", location, "_Ratio$")
  subset_df <- df[, grepl(pattern, colnames(df))]
  return(subset_df)
}

# === 2. Get list of all Excel files in a folder ===
folder_path <- "xxx/counts_summary_files/"  # change to your actual path
file_list <- list.files(path = folder_path, pattern = "\\.xlsx?$", full.names = TRUE)

# === 3. Initialize lists to collect data ===
all_counts_B <- list()
all_counts_S <- list()
all_counts_BS <- list()
all_counts_M <- list()

all_ratios_B <- list()
all_ratios_S <- list()
all_ratios_BS <- list()
all_ratios_M <- list()

all_averages <- list()


# === 4. Loop over files ===
for (file in file_list) {
  # Read sheets
  counts_df <- read_excel(file, sheet = "Counts")
  ratios_df <- read_excel(file, sheet = "Ratios")
  
  # Convert to data.frame and set rownames
  counts_df <- as.data.frame(counts_df)
  rownames(counts_df) <- counts_df[[1]]
  counts_df[[1]] <- NULL
  
  ratios_df <- as.data.frame(ratios_df)
  rownames(ratios_df) <- ratios_df[[1]]
  ratios_df[[1]] <- NULL
  
  # === Add average row to counts_df ===
  column_averages <- colMeans(counts_df, na.rm = TRUE)
  average_row <- as.data.frame(t(column_averages))
  counts_df_with_averages <- rbind(counts_df, average_row)
  rownames(counts_df_with_averages)[nrow(counts_df_with_averages)] <- "Average"
  
  # (optional) check output
  #print(head(counts_df_with_averages))
  
  # === Add average row to ratio_df ===
  column_averages <- colMeans(ratios_df, na.rm = TRUE)
  average_row <- as.data.frame(t(column_averages))
  ratios_df_with_averages <- rbind(ratios_df, average_row)
  rownames(ratios_df_with_averages)[nrow(ratios_df_with_averages)] <- "Average"
  
  # Extract subsets for each location
  counts_B  <- extract_location_subset(counts_df, "B")
  counts_S  <- extract_location_subset(counts_df, "S")
  counts_BS <- extract_location_subset(counts_df, "BS")
  counts_M  <- extract_location_subset(counts_df, "M")
  
  ratios_B  <- extract_location_subset2(ratios_df, "B")
  ratios_S  <- extract_location_subset2(ratios_df, "S")
  ratios_BS <- extract_location_subset2(ratios_df, "BS")
  ratios_M  <- extract_location_subset2(ratios_df, "M")
  
  
  # Store in lists with file name as ID
  sample_name <- tools::file_path_sans_ext(basename(file))
  
  all_counts_B[[sample_name]]  <- counts_B
  all_counts_S[[sample_name]]  <- counts_S
  all_counts_BS[[sample_name]] <- counts_BS
  all_counts_M[[sample_name]]  <- counts_M
  
  all_ratios_B[[sample_name]]  <- ratios_B
  all_ratios_S[[sample_name]]  <- ratios_S
  all_ratios_BS[[sample_name]] <- ratios_BS
  all_ratios_M[[sample_name]]  <- ratios_M
  
  # === Save only the "Average" rows into all_averages ===
  ave_counts <- counts_df_with_averages["Average", , drop = FALSE]
  ave_ratios <- ratios_df_with_averages["Average", , drop = FALSE]
  
  # Combine into one df
  all_averages[[sample_name]] <- list(
    counts = ave_counts,
    ratios = ave_ratios
  )
  
}


# === 5. Optional: Combine into one big object ===
all_data <- list(
  counts = list(B = all_counts_B, S = all_counts_S, BS = all_counts_BS, M = all_counts_M),
  ratios = list(B = all_ratios_B, S = all_ratios_S, BS = all_ratios_BS, M = all_ratios_M)
)

all_averages
str(all_averages)
all_averages[[1]]$counts
all_averages[[1]]$ratios

library(tibble)
library(writexl)
library(readxl)

all_averages_df <- lapply(names(all_averages), function(s) {
  ac <- rownames_to_column(as.data.frame(all_averages[[s]]$counts), var = "Row") %>%
    mutate(Type = "Counts", Sample = s, .before = 1)
  ar <- rownames_to_column(as.data.frame(all_averages[[s]]$ratios), var = "Row") %>%
    mutate(Type = "Ratios", Sample = s, .before = 1)
  dplyr::bind_rows(ac, ar)  # different columns OK; fills with NA
}) %>% bind_rows()

id_cols <- c("Sample", "Type", "Row")  # adjust if your sheet has these
# Split rows by Type first
counts_df_only <- all_averages_df %>% filter(Type == "Counts")
ratios_df_only <- all_averages_df %>% filter(Type == "Ratios")

# Helper to subset by suffix; returns just id cols if none found (avoids errors)
subset_by_suffix <- function(df, suffix_pattern) {
  keep <- grep(suffix_pattern, names(df), value = TRUE)
  # Always include id cols if present
  keep <- c(intersect(id_cols, names(df)), keep)
  df[, keep, drop = FALSE]
}

# ---------- COUNTS (columns end with _B, _S, _BS, _M) ----------
df_counts_B  <- subset_by_suffix(counts_df_only, "_B$")
df_counts_S  <- subset_by_suffix(counts_df_only, "_S$")
df_counts_BS <- subset_by_suffix(counts_df_only, "_BS$")
df_counts_M  <- subset_by_suffix(counts_df_only, "_M$")

# ---------- RATIOS (columns end with _B_Ratio, _S_Ratio, _BS_Ratio, _M_Ratio) ----------
df_ratios_B  <- subset_by_suffix(ratios_df_only, "_B_Ratio$")
df_ratios_S  <- subset_by_suffix(ratios_df_only, "_S_Ratio$")
df_ratios_BS <- subset_by_suffix(ratios_df_only, "_BS_Ratio$")
df_ratios_M  <- subset_by_suffix(ratios_df_only, "_M_Ratio$")

library(openxlsx)
wb <- createWorkbook()
# Add sheets with names
addWorksheet(wb, "all"); writeData(wb, "all", all_averages_df)
addWorksheet(wb, "counts_B");  writeData(wb, "counts_B", df_counts_B)
addWorksheet(wb, "counts_S");  writeData(wb, "counts_S", df_counts_S)
addWorksheet(wb, "counts_BS"); writeData(wb, "counts_BS", df_counts_BS)
addWorksheet(wb, "counts_M");  writeData(wb, "counts_M", df_counts_M)
addWorksheet(wb, "ratios_B");  writeData(wb, "ratios_B", df_ratios_B)
addWorksheet(wb, "ratios_S");  writeData(wb, "ratios_S", df_ratios_S)
addWorksheet(wb, "ratios_BS"); writeData(wb, "ratios_BS", df_ratios_BS)
addWorksheet(wb, "ratios_M");  writeData(wb, "ratios_M", df_ratios_M)
saveWorkbook(wb, "xxx/all_averages_combined.xlsx", overwrite = TRUE) # change to your actual path


#To find the maximum values of B, S, BS, and M counts and ratios for each file, 
#you can loop over the lists in all_data and extract the max values per sample.

# Helper function to exclude 'Total_' columns
exclude_total_columns <- function(df) {
  df[, !grepl("^Total_", colnames(df)), drop = FALSE]
}

# Initialize storage
max_counts_B  <- c()
max_counts_S  <- c()
max_counts_BS <- c()
max_counts_M  <- c()

max_ratios_B  <- c()
max_ratios_S  <- c()
max_ratios_BS <- c()
max_ratios_M  <- c()

sample_names <- names(all_data$counts$B)  # all samples

for (sample in sample_names) {
  # Cleaned versions of each matrix, excluding Total_ columns
  counts_B_clean  <- exclude_total_columns(all_data$counts$B[[sample]])
  counts_S_clean  <- exclude_total_columns(all_data$counts$S[[sample]])
  counts_BS_clean <- exclude_total_columns(all_data$counts$BS[[sample]])
  counts_M_clean  <- exclude_total_columns(all_data$counts$M[[sample]])
  
  ratios_B_clean  <- exclude_total_columns(all_data$ratios$B[[sample]])
  ratios_S_clean  <- exclude_total_columns(all_data$ratios$S[[sample]])
  ratios_BS_clean <- exclude_total_columns(all_data$ratios$BS[[sample]])
  ratios_M_clean  <- exclude_total_columns(all_data$ratios$M[[sample]])
  
  # Append max values
  max_counts_B  <- c(max_counts_B,  max(counts_B_clean, na.rm = TRUE))
  max_counts_S  <- c(max_counts_S,  max(counts_S_clean, na.rm = TRUE))
  max_counts_BS <- c(max_counts_BS, max(counts_BS_clean, na.rm = TRUE))
  max_counts_M  <- c(max_counts_M,  max(counts_M_clean, na.rm = TRUE))
  
  max_ratios_B  <- c(max_ratios_B,  max(ratios_B_clean, na.rm = TRUE))
  max_ratios_S  <- c(max_ratios_S,  max(ratios_S_clean, na.rm = TRUE))
  max_ratios_BS <- c(max_ratios_BS, max(ratios_BS_clean, na.rm = TRUE))
  max_ratios_M  <- c(max_ratios_M,  max(ratios_M_clean, na.rm = TRUE))
}

# Combine results into a data frame
max_summary <- data.frame(
  Sample = sample_names,
  Max_Count_B = max_counts_B,
  Max_Count_S = max_counts_S,
  Max_Count_BS = max_counts_BS,
  Max_Count_M = max_counts_M,
  Max_Ratio_B = max_ratios_B,
  Max_Ratio_S = max_ratios_S,
  Max_Ratio_BS = max_ratios_BS,
  Max_Ratio_M = max_ratios_M
)

# Show summary
print(max_summary)


library(pheatmap)
library(viridis)  # for viridis color palette
library(RColorBrewer)

### Bone+Surface Count heatmap
# Define breaks and color palette
breaks <- seq(0, 2000, by = 1)

# adjust white color position
n_breaks <- length(breaks) - 1 # total breaks
pos_white <- round(n_breaks / 3) # position where white should occur (first 1/5)
col1 <- colorRampPalette(c("navy", "#fdd835"))(pos_white) # First segment: navy → white
col2 <- colorRampPalette(c("#fdd835", "firebrick3"))(n_breaks - pos_white) # Second segment: white → firebrick3
colors <- c(col1, col2) # Combine

pattern1 <- "^Sector_\\d+_BS$"
out_dir = "xxx/pheatmap_images" # change to your actual path
pdf(file.path(out_dir, "Sector_BS_Counts.pdf"), width = 15, height = 5)  # open once

# Loop through each sample in the list
for (sample_name in names(all_counts_BS)) {
  mat <- all_counts_BS[[sample_name]]
  
  # Subset only sector-specific columns
  sector_cols <- grep(pattern1, colnames(mat), value = TRUE)
  mat_sector <- mat[, sector_cols, drop = FALSE]
  
  # Reverse row and column order
  mat_sector <- mat_sector[rev(rownames(mat_sector)), rev(colnames(mat_sector))]
  
  # Plot heatmap
  pheatmap(mat_sector,
           main = paste("Sector BS Counts \n", sample_name),
           cluster_rows = FALSE,
           cluster_cols = FALSE,
           color = colors,
           breaks = breaks,
           scale = "none",
           show_rownames = TRUE,
           cellwidth = 10,
           cellheight = 1,
           border_color = "white",
           fontsize_row = 5,
           fontsize_col = 5)
}

dev.off()  # close the PDF

###
###
### tiff

library(pheatmap)

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

for (sample_name in names(all_counts_BS)) {
  
  mat <- all_counts_BS[[sample_name]]
  
  # Subset only sector-specific columns
  sector_cols <- grep(pattern1, colnames(mat), value = TRUE)
  mat_sector <- mat[, sector_cols, drop = FALSE]
  
  # Reverse row and column order
  mat_sector <- mat_sector[rev(rownames(mat_sector)), rev(colnames(mat_sector))]
  
  # Define output file
  tiff_file <- file.path(out_dir, paste0("Sector_BS_Counts_", sample_name, ".tiff"))
  
  # Open TIFF device
  tiff(
    filename = tiff_file,
    width = 15,
    height = 5,
    units = "in",
    res = 300,
    compression = "lzw"
  )
  
  # Draw heatmap
  pheatmap(
    mat_sector,
    main = paste("Sector BS Counts\n", sample_name),
    cluster_rows = FALSE,
    cluster_cols = FALSE,
    color = colors,
    breaks = breaks,
    scale = "none",
    show_rownames = TRUE,
    cellwidth = 10,
    cellheight = 1,
    border_color = "white",
    fontsize_row = 5,
    fontsize_col = 5
  )
  
  dev.off()  # close TIFF
}



#
#
#
#
#
#
#
#
### Marrow Count heatmap
# Define breaks and color palette
breaks2 <- seq(0, 900, by = 1)
colors2 <- colorRampPalette(brewer.pal(9, "Reds"))(length(breaks2) - 1)

pattern2 <- "^Sector_\\d+_M$"

pdf(file.path(out_dir, "Sector_M_Counts.pdf"), width = 15, height = 5)  # open once


# Loop through each sample in the list
for (sample_name in names(all_counts_M)) {
  mat <- all_counts_M[[sample_name]]
  
  # Subset only sector-specific columns
  sector_cols <- grep(pattern2, colnames(mat), value = TRUE)
  mat_sector <- mat[, sector_cols, drop = FALSE]
  
  # Reverse row and column order
  mat_sector <- mat_sector[rev(rownames(mat_sector)), rev(colnames(mat_sector))]
  
  # Plot heatmap
  pheatmap(mat_sector,
           main = paste("Sector M Counts \n", sample_name),
           cluster_rows = FALSE,
           cluster_cols = FALSE,
           color = colors2,
           breaks = breaks2,
           scale = "none",
           show_rownames = TRUE,
           cellwidth = 10,
           cellheight = 1,
           border_color = "white",
           fontsize_row = 5,
           fontsize_col = 5)
}

dev.off()  # close the PDF

###
###
### tiff

library(pheatmap)

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

for (sample_name in names(all_counts_M)) {
  
  mat <- all_counts_M[[sample_name]]
  
  # Subset only sector-specific columns
  sector_cols <- grep(pattern2, colnames(mat), value = TRUE)
  mat_sector <- mat[, sector_cols, drop = FALSE]
  
  # Reverse row and column order
  mat_sector <- mat_sector[rev(rownames(mat_sector)), rev(colnames(mat_sector))]
  
  # Define output file
  tiff_file <- file.path(out_dir, paste0("Sector_M_Counts_", sample_name, ".tiff"))
  
  # Open TIFF device
  tiff(
    filename = tiff_file,
    width = 15,
    height = 5,
    units = "in",
    res = 300,
    compression = "lzw"
  )
  
  # Draw heatmap
  pheatmap(
    mat_sector,
    main = paste("Sector M Counts\n", sample_name),
    cluster_rows = FALSE,
    cluster_cols = FALSE,
    color = colors2,
    breaks = breaks2,
    scale = "none",
    show_rownames = TRUE,
    cellwidth = 10,
    cellheight = 1,
    border_color = "white",
    fontsize_row = 5,
    fontsize_col = 5
  )
  
  dev.off()  # close TIFF
}

### Bone+Surface Ratio heatmap

breaks3 <- seq(0, 1, by = 0.1)
colors3 <- viridis(length(breaks3) - 1)  # number of color intervals = breaks - 1

pattern3 <- "^Sector_\\d+_BS_Ratio$"

pdf(file.path(out_dir, "Sector_BS_Ratios.pdf"), width = 15, height = 5)  # open once

# Loop through each sample in the list
for (sample_name in names(all_ratios_BS)) {
  mat <- all_ratios_BS[[sample_name]]
  
  # Subset only sector-specific columns
  sector_cols <- grep(pattern3, colnames(mat), value = TRUE)
  mat_sector <- mat[, sector_cols, drop = FALSE]
  
  # Reverse row and column order
  mat_sector <- mat_sector[rev(rownames(mat_sector)), rev(colnames(mat_sector))]
  
  # Plot heatmap
  pheatmap(mat_sector,
           main = paste("Sector BS Ratios \n", sample_name),
           cluster_rows = FALSE,
           cluster_cols = FALSE,
           color = colors3,
           breaks = breaks3,
           scale = "none",
           show_rownames = TRUE,
           cellwidth = 10,
           cellheight = 1,
           border_color = "white",
           fontsize_row = 3,
           fontsize_col = 3)
}


dev.off()  # close the PDF

### marrow Ratio heatmap

breaks4 <- seq(0, 0.8, by = 0.1)
colors4 <- colorRampPalette(brewer.pal(9, "Reds"))(length(breaks4) - 1)

pattern4 <- "^Sector_\\d+_M_Ratio$"

pdf(file.path(out_dir, "Sector_M_Ratios.pdf"), width = 15, height = 6)  # open once

# Loop through each sample in the list
for (sample_name in names(all_ratios_M)) {
  mat <- all_ratios_M[[sample_name]]
  
  # Subset only sector-specific columns
  sector_cols <- grep(pattern4, colnames(mat), value = TRUE)
  mat_sector <- mat[, sector_cols, drop = FALSE]
  
  # Reverse row and column order
  mat_sector <- mat_sector[rev(rownames(mat_sector)), rev(colnames(mat_sector))]
  
  # Plot heatmap
  pheatmap(mat_sector,
           main = paste("Sector M Ratios \n", sample_name),
           cluster_rows = FALSE,
           cluster_cols = FALSE,
           color = colors4,
           breaks = breaks4,
           scale = "none",
           show_rownames = TRUE,
           cellwidth = 10,
           cellheight = 1,
           border_color = "white",
           fontsize_row = 8,
           fontsize_col = 8)
  
}


dev.off()  # close the PDF

#
#
#
#
#
#
#
#
#
#
#
#

library(readxl)
library(dplyr)
library(stringr)
# 
# folder_path <- "/zzz/counts_summary_files/"   # <-- your folder
# file_list   <- list.files(path = folder_path, pattern = "\\.xlsx?$", full.names = TRUE)

# -------- helpers --------
# keep only sector columns for a given location & sheet type
#   type = "Counts" -> expects "..._Count"
#   type = "Ratios" -> expects "..._Ratio"
pick_sector_cols <- function(df, location, type = c("Counts","Ratios")) {
  type <- match.arg(type)
  suffix <- if (type == "Counts") "Count" else "Ratio"
  pat <- paste0("^Sector_\\d+_", location, "_", suffix, "$")
  keep <- grep(pat, colnames(df), value = TRUE)
  # drop any "Total_*"
  keep <- keep[!grepl("^Total_", keep)]
  df[, keep, drop = FALSE]
}

# numeric coercion & overall mean across ALL cells
mean_all_cells <- function(df) {
  if (is.null(df) || ncol(df) == 0) return(NA_real_)
  df_num <- suppressWarnings(as.data.frame(lapply(df, function(x) as.numeric(as.character(x)))))
  mean(as.matrix(df_num), na.rm = TRUE)
}

# -------- loop & summarize --------
avg_summary <- vector("list", length(file_list))

for (i in seq_along(file_list)) {
  file <- file_list[i]
  sample_name <- tools::file_path_sans_ext(basename(file))
  
  # read sheets
  counts_df <- as.data.frame(read_excel(file, sheet = "Counts"))
  ratios_df <- as.data.frame(read_excel(file, sheet = "Ratios"))
  
  # set rownames from first column then drop it
  rownames(counts_df) <- counts_df[[1]]; counts_df[[1]] <- NULL
  rownames(ratios_df) <- ratios_df[[1]]; ratios_df[[1]] <- NULL
  
  # pick sector columns per location
  cB  <- pick_sector_cols(counts_df, "B",  "Counts")
  cS  <- pick_sector_cols(counts_df, "S",  "Counts")
  cBS <- pick_sector_cols(counts_df, "BS", "Counts")
  cM  <- pick_sector_cols(counts_df, "M",  "Counts")
  
  rB  <- pick_sector_cols(ratios_df, "B",  "Ratios")
  rS  <- pick_sector_cols(ratios_df, "S",  "Ratios")
  rBS <- pick_sector_cols(ratios_df, "BS", "Ratios")
  rM  <- pick_sector_cols(ratios_df, "M",  "Ratios")
  
  # overall average across ALL columns/cells per block
  avg_summary[[i]] <- data.frame(
    Sample        = sample_name,
    Avg_Count_B   = mean_all_cells(cB),
    Avg_Count_S   = mean_all_cells(cS),
    Avg_Count_BS  = mean_all_cells(cBS),
    Avg_Count_M   = mean_all_cells(cM),
    Avg_Ratio_B   = mean_all_cells(rB),
    Avg_Ratio_S   = mean_all_cells(rS),
    Avg_Ratio_BS  = mean_all_cells(rBS),
    Avg_Ratio_M   = mean_all_cells(rM),
    stringsAsFactors = FALSE
  )
}

avg_summary <- dplyr::bind_rows(avg_summary)

# preview & save
print(head(avg_summary))
# write.csv(avg_summary, "average_summary_per_file.csv", row.names = FALSE)

#
#
#
#
#
#
#
#
#
#
