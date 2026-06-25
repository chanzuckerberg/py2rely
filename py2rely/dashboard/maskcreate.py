"""Python reimplementation of RELION's ``relion_mask_create`` (file mode).

This mirrors the algorithm in ``src/apps/mask_create.cpp`` +
``autoMask()``/``lowPassFilterMap()`` from the RELION source so the dashboard's
interactive Mask Tuner produces masks that match a real MaskCreate job:

    1. (optional) low-pass filter the input map (raised-cosine in Fourier space)
    2. binarize at ``ini_threshold``
    3. extend (dilate) or shrink (erode) the binary mask by ``extend_inimask`` px
    4. add a raised-cosine soft edge of ``width_soft_edge`` px
    5. (optional) invert

The brute-force neighbour search RELION uses for steps 3 and 4 is exactly a
Euclidean distance transform, so we use ``scipy.ndimage.distance_transform_edt``
which is both faithful and fast (sub-second for typical STA boxes).

Helical masking is intentionally not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import distance_transform_edt


@dataclass
class MaskResult:
    mask: np.ndarray          # float32, values in [0, 1]
    angpix: float             # pixel size used (Å)
    fraction: float           # fraction of the box occupied (mean mask value)


def lowpass_filter(vol: np.ndarray, low_pass: float, angpix: float, filter_edge_width: int = 2) -> np.ndarray:
    """Raised-cosine low-pass filter, matching RELION's ``lowPassFilterMap``.

    ``low_pass`` and ``angpix`` are in Angstroms.  The filter is defined on
    resolution shells (cycles/pixel) with a soft edge spanning
    ``filter_edge_width`` shells centred on the cut-off shell.
    """
    vol = np.asarray(vol, dtype=np.float64)
    nz, ny, nx = vol.shape
    # RELION uses XSIZE as the reference dimension; assume (near-)cubic boxes.
    ori_size = max(nx, ny, nz)

    ires_filter = round((ori_size * angpix) / low_pass)
    half = filter_edge_width // 2
    edge_low = max(0.0, (ires_filter - half) / ori_size)        # 1/pixel
    edge_high = (ires_filter + half) / ori_size                 # 1/pixel
    edge_width = edge_high - edge_low

    fz = np.fft.fftfreq(nz)
    fy = np.fft.fftfreq(ny)
    fx = np.fft.rfftfreq(nx)
    rz, ry, rx = np.meshgrid(fz, fy, fx, indexing="ij")
    res = np.sqrt(rz * rz + ry * ry + rx * rx)                  # 1/pixel

    coeff = np.ones_like(res)
    if edge_width > 0:
        mid = (res >= edge_low) & (res <= edge_high)
        coeff[mid] = 0.5 + 0.5 * np.cos(np.pi * (res[mid] - edge_low) / edge_width)
    coeff[res > edge_high] = 0.0

    ft = np.fft.rfftn(vol)
    ft *= coeff
    return np.fft.irfftn(ft, s=vol.shape).astype(np.float64)


def auto_mask(
    vol: np.ndarray,
    ini_threshold: float,
    extend_inimask: float,
    width_soft_edge: float,
    invert: bool = False,
) -> np.ndarray:
    """Binarize → extend/shrink → soft edge → invert. Mirrors RELION ``autoMask``."""
    vol = np.asarray(vol, dtype=np.float64)

    # A. initial binary mask
    mask = (vol >= ini_threshold).astype(np.float64)

    # B. extend (dilate) or shrink (erode) the binary mask by a Euclidean radius.
    #    RELION's neighbour search with `r2 < extend^2` == thresholding the EDT.
    if extend_inimask > 0:
        # distance from each background voxel to the nearest foreground voxel
        dist = distance_transform_edt(mask < 0.5)
        mask[(mask < 0.5) & (dist < extend_inimask)] = 1.0
    elif extend_inimask < 0:
        # distance from each foreground voxel to the nearest background voxel
        dist = distance_transform_edt(mask > 0.5)
        mask[(mask > 0.5) & (dist < abs(extend_inimask))] = 0.0

    # C. raised-cosine soft edge on the (extended) binary mask
    if width_soft_edge > 0:
        bg = mask < 0.5
        dist = distance_transform_edt(bg)                       # to nearest mask==1
        sel = bg & (dist < width_soft_edge)
        mask[sel] = 0.5 + 0.5 * np.cos(np.pi * dist[sel] / width_soft_edge)
        mask[bg & ~sel] = 0.0

    if invert:
        mask = 1.0 - mask

    return mask.astype(np.float32)


def create_mask(
    vol: np.ndarray,
    *,
    header_angpix: float,
    ini_threshold: float = 0.02,
    extend_inimask: float = 3.0,
    width_soft_edge: float = 3.0,
    lowpass: float = -1.0,
    angpix: float = -1.0,
    invert: bool = False,
) -> MaskResult:
    """High-level entry point mirroring the MaskCreate job parameters.

    ``angpix`` <= 0 falls back to the value from the map header (as RELION does).
    ``lowpass`` <= 0 skips the low-pass filter.
    """
    used_angpix = angpix if angpix > 0 else header_angpix
    if used_angpix <= 0:
        used_angpix = 1.0

    work = np.asarray(vol, dtype=np.float64)
    if lowpass > 0:
        work = lowpass_filter(work, lowpass, used_angpix)

    mask = auto_mask(
        work,
        ini_threshold=ini_threshold,
        extend_inimask=extend_inimask,
        width_soft_edge=width_soft_edge,
        invert=invert,
    )
    return MaskResult(mask=mask, angpix=used_angpix, fraction=float(mask.mean()))


def build_relion_command(
    input_path: str,
    output_path: str,
    *,
    ini_threshold: float,
    extend_inimask: float,
    width_soft_edge: float,
    lowpass: float = -1.0,
    angpix: float = -1.0,
    invert: bool = False,
) -> str:
    """Return the equivalent ``relion_mask_create`` command line (for reference)."""
    cmd = [f"relion_mask_create --i {input_path} --o {output_path}"]
    if lowpass > 0:
        cmd.append(f"--lowpass {lowpass}")
    if angpix > 0:
        cmd.append(f"--angpix {angpix}")
    cmd.append(f"--ini_threshold {ini_threshold}")
    cmd.append(f"--extend_inimask {extend_inimask}")
    cmd.append(f"--width_soft_edge {width_soft_edge}")
    if invert:
        cmd.append("--invert")
    return " ".join(cmd)
