# Bone Imager

**Bone Imager** is a Python- and R-based image processing and
quantitative analysis pipeline for analyzing bone and bone marrow
structures from micro-computed tomography (microCT) image stacks.

The pipeline converts grayscale microCT images into spatially classified
masks representing bone, bone surface, and marrow regions, quantifies
their spatial distribution, and generates heatmap-based visualization of
the resulting data.

## Overview

The pipeline performs the following steps:

1.  **TIFF stack processing**\
    Multi-layer grayscale TIFF images are converted into individual
    two-dimensional pixel arrays.

2.  **Bone segmentation**\
    Pixels are classified according to grayscale intensity into:

    -   `B` --- mineralized bone
    -   `S` --- bone surface/boundary
    -   `M` --- marrow space
    -   `.` --- background

3.  **Marrow detection**\
    Low-intensity pixels are evaluated using surrounding bone and
    surface signals. Spatial criteria include horizontal enclosure,
    vertical validation, and local skeletal distribution.

4.  **Anatomical filtering**\
    Additional geometric constraints reduce false-positive marrow
    detection in peripheral image regions, inferior bone edges, and
    cranial suture regions.

5.  **Parameter optimization**\
    Segmentation is performed using a rule-based image processing
    algorithm. Optuna is used for automated hyperparameter optimization
    against manually curated masks. Paired grayscale pixel data
    (`*_pixels.csv`) and manually curated masks (`*_mask_curated.csv`)
    are used as training datasets. Optuna evaluates combinations of
    tunable parameters and identifies parameter sets that maximize
    agreement with curated masks using metrics such as the F1 score.

6.  **Bone-profile adaptation**\
    Different parameter profiles can be applied to thin, medium, and
    thick bone structures to accommodate differences in cortical
    thickness and marrow cavity size.

7.  **Angular sector analysis**\
    Each image can be divided into **30 sectors of 6° each**, spanning
    180° from the bottom-center reference point. Bone (`B`), surface
    (`S`), and marrow (`M`) pixels are quantified within each sector.

8.  **Visualization and heatmap analysis**\
    Classified masks can be exported as color-coded images:

    -   Bone (`B`) --- light yellow
    -   Surface (`S`) --- light red
    -   Marrow (`M`) --- light green
    -   Background (`.`) --- white

    Sequential masks can also be assembled into animated GIFs for
    quality control. Sector-based quantitative results can be further
    analyzed and visualized as heatmaps using R.

## Input

Primary input:

``` text
microCT_image.tif
```

For parameter optimization:

``` text
xxx_pixels.csv
xxx_mask_curated.csv
```

`*_pixels.csv` contains grayscale pixel intensities, whereas
`*_mask_curated.csv` contains manually curated `B`, `S`, `M`, and
background classifications.

## Output

Typical outputs include:

``` text
layer_0000_pixels.csv
layer_0000_mask.csv
layer_0000_mask_color.jpg
layer_0001_pixels.csv
layer_0001_mask.csv
layer_0001_mask_color.jpg
...
mask_color_stack.gif
sector_summary.xlsx
heatmap output
```

The sector summary contains counts and ratios of bone, surface, combined
skeletal (`B+S`), and marrow regions for individual angular sectors and
the entire analyzed region. These spatial measurements can be used as
input for downstream heatmap visualization in R.

## Requirements

### Python

The image processing and quantification pipeline uses Python packages
including:

``` text
numpy
pandas
Pillow
openpyxl
optuna
scikit-learn
```

Install the required Python packages using:

``` bash
python -m pip install numpy pandas pillow openpyxl optuna scikit-learn
```

### R

R is used for downstream heatmap visualization of spatially resolved
quantitative data. Install the R packages required by the provided
heatmap script before running the analysis.

## Workflow

``` text
microCT TIFF stack
        ↓
grayscale pixel extraction
        ↓
B/S intensity classification
        ↓
spatial marrow detection
        ↓
edge and suture filtering
        ↓
optimized segmentation mask
        ↓
30-sector spatial analysis
        ↓
quantitative data export
        ↓
R heatmap visualization
```

## Parameter Optimization

Segmentation itself is rule-based rather than a machine-learning
segmentation model. **Optuna** is used to optimize the tunable
parameters of the segmentation algorithm using manually curated training
masks as ground truth.

The optimized parameters can subsequently be applied to complete microCT
image stacks for automated segmentation and quantification.

## Heatmap Visualization

Sector-based quantitative outputs can be visualized using the
accompanying R heatmap analysis. This provides a spatial representation
of changes in bone and marrow measurements across angular sectors and
image layers.

## Intended Use

Bone Imager was developed for quantitative analysis of bone and bone
marrow organization in microCT datasets, with particular emphasis on
spatial analysis of calvarial bone and marrow structures.

## Citation

Citation information will be added upon publication.

## License

License information will be added.
