__version__ = "0.6.0"

# Box sizes considered valid by RELION (FFT-friendly dimensions).
# Used wherever a computed box size must be snapped to the nearest allowed value.
PARTICLE_BOX_SIZES = [
    24, 32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 84, 96, 100, 104, 112, 120, 128,
    132, 140, 168, 180, 192, 196, 208, 216, 220, 224, 256, 288, 300, 320, 352, 360,
    384, 416, 440, 448, 480, 480, 512, 540, 560, 576, 588, 600, 630, 648, 672, 686, 700,
    720, 756, 768, 784, 800, 840, 864, 896, 912, 960, 1008, 1024, 1080, 1120, 1152, 1152,
]


def snap_box_size(size: int, *, side: str = "nearest") -> int:
    """Snap *size* to an allowed RELION box size.

    side='nearest' (default) — closest value (ties go up).
    side='right'             — smallest allowed size >= *size* (never truncates).
    side='left'              — largest allowed size <= *size*.
    """
    import bisect
    if side == "right":
        idx = bisect.bisect_left(PARTICLE_BOX_SIZES, size)
    elif side == "left":
        idx = bisect.bisect_right(PARTICLE_BOX_SIZES, size) - 1
    else:  # nearest
        idx = bisect.bisect_left(PARTICLE_BOX_SIZES, size)
        if idx > 0 and (idx == len(PARTICLE_BOX_SIZES) or size - PARTICLE_BOX_SIZES[idx - 1] < PARTICLE_BOX_SIZES[idx] - size):
            idx -= 1
    return PARTICLE_BOX_SIZES[max(0, min(idx, len(PARTICLE_BOX_SIZES) - 1))]


# Shared CLI context settings for all commands
cli_context = {
    "show_default": True,
    "help_option_names": ["-h", "--help"],  # allow both -h and --help
}