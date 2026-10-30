#!/usr/bin/env python3
"""
Voynich Graph Animation Creator
Place this script in ~/voynich-engine/ and run it.
"""

import os
from pathlib import Path
import re
from PIL import Image
import imageio.v2 as imageio

# ===================== CONFIG =====================
INPUT_DIR = Path("voynich_graphs")
OUTPUT_GIF = Path("voynich_all_graphs.gif")

# Duration per frame in seconds
FRAME_DURATION = 1.2   # 1.2 seconds per frame is good for viewing

# Optional: limit for testing
MAX_FRAMES = None      # Set to e.g. 20 for testing
# =================================================

def natural_sort_key(filename):
    """Sort folios like f1r, f10r, f100r, f2r correctly"""
    # Extract the main folio number and any suffix
    match = re.search(r'f(\d+)([a-zA-Z0-9]*)', filename)
    if match:
        num = int(match.group(1))
        suffix = match.group(2)
        return (num, suffix)
    return (9999, filename)

def main():
    # Get all PNG files
    png_files = sorted(
        [f for f in INPUT_DIR.glob("*.png")],
        key=lambda x: natural_sort_key(x.name)
    )

    print(f"Found {len(png_files)} graph images.")

    if MAX_FRAMES:
        png_files = png_files[:MAX_FRAMES]
        print(f"Limited to first {MAX_FRAMES} frames for testing.")

    if not png_files:
        print("No PNG files found!")
        return

    # Load all images
    images = []
    for i, png in enumerate(png_files):
        print(f"Reading {i+1:3d}/{len(png_files)}: {png.name}")
        img = Image.open(png)
        # Convert to RGB (some might be RGBA)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        images.append(img)

    # Save as GIF
    print(f"\nCreating animated GIF → {OUTPUT_GIF}")
    print(f"Frame duration: {FRAME_DURATION}s | Total frames: {len(images)}")

    imageio.mimsave(
        OUTPUT_GIF,
        images,
        duration=FRAME_DURATION * 1000,   # imageio expects milliseconds
        loop=0,                           # infinite loop
        optimize=True
    )

    print("✅ Done! Your GIF is ready:")
    print(f"   {OUTPUT_GIF.resolve()}")
    print(f"   Size: {OUTPUT_GIF.stat().st_size / (1024*1024):.1f} MB")

if __name__ == "__main__":
    main()