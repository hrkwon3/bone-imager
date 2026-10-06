from PIL import Image, ImageSequence
import os

# === Settings ===
# please add the file address of tiff file here!
input_path = "yyy.tif"

base, ext = os.path.splitext(input_path)
output_path = f"{base}_2x_resized_output{ext}"
scale_factor = 2  # Increase resolution by 2x

# === Open Multi-layer TIFF ===
im = Image.open(input_path)

# === Prepare output frames ===
upsampled_frames = []

for idx, frame in enumerate(ImageSequence.Iterator(im)):
    # Upsample each frame
    new_size = (frame.width * scale_factor, frame.height * scale_factor)
    upsampled = frame.resize(new_size, resample=Image.BICUBIC)  # or Image.NEAREST for masks
    upsampled_frames.append(upsampled)

# === Save multi-page TIFF ===
upsampled_frames[0].save(
    output_path,
    save_all=True,
    append_images=upsampled_frames[1:],
    compression="tiff_deflate"  # Optional: compress output
)

print(f"✅ Upsampled multi-layered TIFF saved: {output_path}")
