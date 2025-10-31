# cgimage_pixel_check.py
from Quartz import (
    CGWindowListCreateImage, CGRectInfinite,
    kCGWindowListOptionOnScreenOnly, kCGNullWindowID,
    kCGWindowImageDefault, CGImageGetWidth, CGImageGetHeight,
    CGImageGetDataProvider, CGDataProviderCopyData
)
import struct

def check_pixels():
    img_ref = CGWindowListCreateImage(
        CGRectInfinite,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault
    )

    width = CGImageGetWidth(img_ref)
    height = CGImageGetHeight(img_ref)
    print(f"Captured {width}x{height}")

    provider = CGImageGetDataProvider(img_ref)
    data = CGDataProviderCopyData(provider)

    pixel_bytes = bytes(data)
    sample = pixel_bytes[:40]  # first few pixels
    print("Sample bytes:", list(sample))

    # Rough heuristic: if all pixel values are 0 or 255, likely blank/black/white
    unique_values = set(sample)
    if len(unique_values) <= 3:
        print("⚠️  Pixel data looks uniform — possibly blank/protected screen.")
    else:
        print("🟢  Pixel data seems varied — visible content likely accessible.")

if __name__ == "__main__":
    check_pixels()
