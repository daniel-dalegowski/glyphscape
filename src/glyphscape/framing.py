"""Circle crop/vignette framing, plus a search for where to center it.

Empirically, the renders that read best had a strong light/dark boundary
(sky meeting a ridgeline, cliff meeting water) inside the circle -- a dead-
centered crop sometimes misses it. find_best_circle_center searches a
handful of vertical positions and keeps whichever gives the strongest
split, scored directly from the source image's luminance (not the glyph
grid, which is comparatively expensive and a step removed from 'is there a
boundary here')."""

from __future__ import annotations

from PIL import Image

# Band-mean spread (0-255 grayscale) below which a photo is considered low
# contrast everywhere -- density_gamma gets eased toward 1.0 proportionally
# so a genuinely flat/misty source doesn't just vanish under a gamma tuned
# for crisp landscapes (see pipeline.py).
LOW_CONTRAST_THRESHOLD = 40.0


def band_contrast_score(
    gray_image: Image.Image, center: tuple[float, float], radius: float, num_bands: int = 8
) -> float:
    """Max-min spread of mean luminance across horizontal bands of the
    circle -- high when something like a horizon splits it into distinct
    light/dark zones, low when the circle is one fairly uniform tone."""
    px = gray_image.load()
    w, h = gray_image.size
    cx, cy = center
    x0, x1 = max(0, int(cx - radius)), min(w, int(cx + radius) + 1)
    y0, y1 = max(0, int(cy - radius)), min(h, int(cy + radius) + 1)
    sums = [0.0] * num_bands
    counts = [0] * num_bands
    r2 = radius * radius

    for y in range(y0, y1, 2):
        dy = y - cy
        dy2 = dy * dy
        if dy2 > r2:
            continue
        band = min(num_bands - 1, max(0, int((dy + radius) / (2 * radius) * num_bands)))
        for x in range(x0, x1, 2):
            dx = x - cx
            if dx * dx + dy2 <= r2:
                sums[band] += px[x, y]
                counts[band] += 1

    means = [s / c for s, c in zip(sums, counts) if c > 0]
    if len(means) < 2:
        return 0.0
    return max(means) - min(means)


def find_best_circle_center(
    image: Image.Image,
    resolution: tuple[int, int],
    radius_frac: float,
    y_candidates: tuple[float, ...] = (0.40, 0.45, 0.5, 0.55, 0.60),
) -> tuple[tuple[float, float], float]:
    res_w, res_h = resolution
    radius = min(res_w, res_h) / 2 * radius_frac
    cx = res_w / 2

    sample = image.convert("L")
    if sample.size != resolution:
        sample = sample.resize(resolution)

    best_center, best_score = (cx, res_h / 2), -1.0
    for fy in y_candidates:
        cy = res_h * fy
        score = band_contrast_score(sample, (cx, cy), radius)
        if score > best_score:
            best_score, best_center = score, (cx, cy)
    return best_center, best_score


def eased_density_gamma(
    configured_gamma: float, contrast_score: float, threshold: float = LOW_CONTRAST_THRESHOLD
) -> float:
    """Pull density_gamma back toward 1.0 when the best achievable circle
    placement still isn't very contrasty, so flat/misty photos keep some
    texture instead of being gamma'd into near-nothingness."""
    if contrast_score >= threshold or configured_gamma <= 1.0:
        return configured_gamma
    factor = max(0.0, min(1.0, contrast_score / threshold))
    return 1.0 + (configured_gamma - 1.0) * factor


def circle_mask_value(
    px: float, py: float, center: tuple[float, float], max_r: float, feather: float
) -> float:
    cx, cy = center
    dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
    if max_r <= 0:
        return 1.0
    inner_r = max_r * (1 - feather)
    if dist >= max_r:
        return 0.0
    if dist <= inner_r:
        return 1.0
    return 1.0 - (dist - inner_r) / (max_r - inner_r)
