"""
CPU-only reimplementation of pytom-match-pick template generation tools.

This module provides CPU-based (NumPy/SciPy) implementations of template 
generation functions originally from pytom-match-pick, avoiding GPU dependencies (CuPy/voltools)
while maintaining compatible output for template matching workflows.

Original GPU-accelerated implementation:
https://github.com/SBC-Utrecht/pytom-match-pick/blob/main/src/pytom_tm/template.py
"""


from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING
import click

# Optional: satisfy type checkers without runtime imports
if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
    import pathlib

def read_mrc(path: pathlib.Path) -> npt.NDArray[np.floating]:
    import numpy as np
    import mrcfile

    with mrcfile.open(str(path), permissive=True) as m:
        data = np.asarray(m.data, dtype=np.float32)
    return data


def read_mrc_meta_data(path: pathlib.Path) -> dict:
    import mrcfile

    with mrcfile.open(str(path), permissive=True) as m:
        h = m.header
        # voxel size (Å) typically in header.cella / header.mx,my,mz
        try:
            vx = float(h.cella.x) / max(int(h.mx), 1)
            vy = float(h.cella.y) / max(int(h.my), 1)
            vz = float(h.cella.z) / max(int(h.mz), 1)
            # Expect isotropic voxels; fall back to x
            vox = float(vx)
        except Exception:
            # Older files may store nm in 'xlen' fields; mrcfile maps them to cella
            vox = float(h.cella.x) / max(int(h.mx), 1)
    return {"voxel_size": vox}


def write_mrc(path: pathlib.Path, volume: npt.NDArray[np.floating], voxel_size_A: float) -> None:
    import mrcfile, pathlib
    import numpy as np
    
    vol = np.asarray(volume, dtype=np.float32)
    path = pathlib.Path(path)
    with mrcfile.new(str(path), overwrite=True) as m:
        m.set_data(vol)
        # Set voxel size (Å)
        nz, ny, nx = vol.shape
        m.header.cella.x = nx * voxel_size_A
        m.header.cella.y = ny * voxel_size_A
        m.header.cella.z = nz * voxel_size_A
        m.header.mx = nx
        m.header.my = ny
        m.header.mz = nz
        m.update_header_from_data()


# ------------------------------
# Fourier helpers (match prior behavior)
# ------------------------------

def hwhm_to_sigma(hwhm: float) -> float:
    import numpy as np

    return hwhm / (np.sqrt(2.0 * np.log(2.0)))


def radial_reduced_grid(
    shape: Tuple[int, int, int] | Tuple[int, int], *, shape_is_reduced: bool = False
) -> npt.NDArray[np.floating]:
    """Fourier-space radial grid with last axis reduced (rfftn) and origin centered.
    Values: 0 at DC to 1 at Nyquist.
    This mirrors the behavior you shared from pytom_tm.
    """
    import numpy as np

    if len(shape) not in (2, 3):
        raise ValueError("radial_reduced_grid() only works for 2D or 3D shapes")
    reduced_dim = shape[-1] if shape_is_reduced else shape[-1] // 2 + 1
    if len(shape) == 3:
        x = (
            np.abs(np.arange(-shape[0] // 2 + shape[0] % 2, shape[0] // 2 + shape[0] % 2, 1.0))
            / (shape[0] // 2)
        )[:, None, None]
        y = (
            np.abs(np.arange(-shape[1] // 2 + shape[1] % 2, shape[1] // 2 + shape[1] % 2, 1.0))
            / (shape[1] // 2)
        )[:, None]
        z = np.arange(0, reduced_dim, 1.0) / max(reduced_dim - 1, 1)
        return (x * x + y * y + z * z) ** 0.5
    else:
        x = (
            np.abs(np.arange(-shape[0] // 2 + shape[0] % 2, shape[0] // 2 + shape[0] % 2, 1.0))
            / (shape[0] // 2)
        )[:, None]
        y = np.arange(0, reduced_dim, 1.0) / max(reduced_dim - 1, 1)
        return (x * x + y * y) ** 0.5


def create_gaussian_low_pass(
    shape: Tuple[int, int, int] | Tuple[int, int], spacing: float, resolution: float
) -> npt.NDArray[np.floating]:
    """Gaussian LPF in reduced Fourier space using the same convention you provided.
    cutoff (HWHM) in Fourier space = 2 * spacing / resolution.
    """
    import numpy as np
    q = radial_reduced_grid(shape)
    sigma_fourier = hwhm_to_sigma(2.0 * float(spacing) / float(resolution))
    lpf = np.exp(-(q ** 2) / (2.0 * sigma_fourier ** 2))
    return np.fft.ifftshift(lpf.astype(np.float32), axes=(0, 1) if len(shape) == 3 else 0)


# ------------------------------
# CPU template ops
# ------------------------------

def generate_template_from_map(
    input_map: npt.NDArray[np.floating],
    input_spacing: float,
    output_spacing: float,
    *,
    center: bool = False,
    filter_to_resolution: Optional[float] = None,
    output_box_size: Optional[int] = None,
    ) -> npt.NDArray[np.floating]:

    from scipy.ndimage import center_of_mass, shift as nd_shift
    from scipy.fft import rfftn, irfftn
    from scipy.ndimage import zoom
    import numpy as np
    import logging

    """CPU-only: pad to cube, optional COM-centering, LPF in rFFT, then resample.
    SciPy/NumPy only; no CUDA, no voltools.
    """
    vol = np.asarray(input_map, dtype=np.float32, order="C")

    # Make cubic volume
    if len(set(vol.shape)) != 1:
        maxdim = int(max(vol.shape))
        diff = [maxdim - s for s in vol.shape]
        pad3 = tuple((d // 2, d // 2 + d % 2) for d in diff)
        vol = np.pad(vol, pad3, mode="constant", constant_values=0)

    # Default LPF to Nyquist of output
    nyq_out = 2.0 * float(output_spacing)
    if filter_to_resolution is None:
        filter_to_resolution = nyq_out
    elif filter_to_resolution < nyq_out:
        logging.warning(
            "Filter resolution too low; clamping to %.3f Å (2 * output voxel)", nyq_out
        )
        filter_to_resolution = nyq_out

    # Optional centering via COM
    if center:
        vol_center = (np.array(vol.shape, dtype=np.float32) - 1.0) / 2.0
        com = np.array(center_of_mass(vol ** 2), dtype=np.float32)
        delta = tuple((vol_center - com).tolist())
        vol = nd_shift(vol, shift=delta, order=1, mode="constant", cval=0.0)
        logging.debug("COM before %s; after %s", np.round(com, 2), np.round(center_of_mass(vol ** 2), 2))

    # Optionally expand to accommodate a larger final box before filtering
    if output_box_size is not None:
        final_vox_if_no_pad = (vol.shape[0] * float(input_spacing)) // float(output_spacing)
        if output_box_size > final_vox_if_no_pad:
            target_pre = int(output_box_size * (float(output_spacing) / float(input_spacing)))
            pad = max(0, target_pre - vol.shape[0])
            if pad > 0:
                pad3 = tuple((pad // 2, pad // 2 + pad % 2) for _ in range(3))
                vol = np.pad(vol, pad3, mode="constant", constant_values=0)
        elif output_box_size < final_vox_if_no_pad:
            logging.warning(
                "Requested box smaller than downsampled size; not cropping to avoid truncation."
            )

    # LPF in Fourier (1x rfftn + 1x irfftn)
    lpf = create_gaussian_low_pass(vol.shape, float(input_spacing), float(filter_to_resolution))
    filtered = irfftn(rfftn(vol) * lpf, s=vol.shape)

    # Resample to output spacing; scale = input/ output
    scale = float(input_spacing) / float(output_spacing)
    out = zoom(filtered, scale, order=1, mode="constant", cval=0.0, prefilter=False)
    return out.astype(np.float32, copy=False)


def phase_randomize_template(template: npt.NDArray[np.floating], seed: int = 321) -> npt.NDArray[np.floating]:
    import numpy as np
    from scipy.fft import rfftn, irfftn

    """CPU-only phase randomization (permute phases up to Nyquist, keep amplitudes)."""
    tpl = np.asarray(template, dtype=np.float32, order="C")
    ft = rfftn(tpl)
    amp = np.abs(ft)

    grid = np.fft.ifftshift(radial_reduced_grid(tpl.shape), axes=(0, 1)).ravel()
    relevant = grid <= 1.0

    rng = np.random.default_rng(seed)
    new_phase = np.zeros_like(phase)
    new_phase[relevant] = rng.permutation(phase[relevant])
    new_phase = new_phase.reshape(amp.shape)

    out = irfftn(amp * np.exp(1j * new_phase), s=tpl.shape)
    return out.astype(np.float32, copy=False)


# ------------------------------
# Click-based CLI entry point
# ------------------------------
class LargerThanZeroFloat(click.ParamType):
    name = "posfloat"

    def convert(self, value, param, ctx):  # type: ignore[override]
        try:
            f = float(value)
        except Exception:
            self.fail(f"{value!r} is not a valid float", param, ctx)
        if f <= 0:
            self.fail("value must be > 0", param, ctx)
        return f


class LargerThanZeroInt(click.ParamType):
    name = "posint"

    def convert(self, value, param, ctx):  # type: ignore[override]
        try:
            i = int(value)
        except Exception:
            self.fail(f"{value!r} is not a valid integer", param, ctx)
        if i <= 0:
            self.fail("value must be > 0", param, ctx)
        return i


POSFLOAT = LargerThanZeroFloat()
POSINT = LargerThanZeroInt()

@click.command(context_settings={"show_default": True}, name='template')
@click.option( "-i", "--input",
    type=str, required=True, help="Map to generate template from; MRC file.",
)
@click.option(
    "-o", "--output", required=False, type=str,
    help=(
        "Path to write output (.mrc). If omitted, writes 'template_{stem}_{voxel}A.mrc'"
    ),
)
@click.option(
    "-ivs", "--input-voxel-size",
    type=POSFLOAT, required=False,
    help=(
        "Voxel size of input map (Å). If omitted, read from MRC header (make sure it's correct)."
    ),
)
@click.option(
    "-ovs", "--output-voxel-size",
    type=POSFLOAT, required=True,
    help=(
        "Output voxel size (Å). Map will be downsampled to this spacing; should match tomograms."
    ),
)
@click.option(
    "--center", is_flag=True, default=False,
    help="Center density by center of mass before filtering.",
)
@click.option(
    "--low-pass",
    type=POSFLOAT, required=False,
    help=(
        "Apply Gaussian low-pass to this resolution (Å). Default is 2 * output voxel size."
    ),
)
@click.option(
    "-b", "--box-size", type=POSINT, required=False,
    help=(
        "Desired final template box size (voxels). Only applied if larger than downsampled size."
    ),
)
@click.option(
    "--invert",
    is_flag=True, default=False,
    help="Multiply template by -1 (not needed if CTF with defocus already applied).",
)
@click.option(
    "-m", "--mirror",
    is_flag=True, default=False,
    help="Mirror the final template along the first axis before writing.",
)
@click.option(
    "loglevel", "--log",
    type=click.Choice(["debug", "info", "warning", "error", "critical", "10", "20", "30", "40", "50"], case_sensitive=False),
    default="20",
    show_default=True,
    help="Set logging level.",
)
def create_template(
    input: pathlib.Path,
    output: Optional[pathlib.Path],
    input_voxel_size: Optional[float],
    output_voxel_size: float,
    center: bool,
    low_pass: Optional[float],
    box_size: Optional[int],
    invert: bool,
    mirror: bool,
    loglevel: str,
    ):
    """Generate a template from an input MRC density (CPU-only, SciPy/NumPy)."""
    
    run_create_template(
        input,
        output,
        input_voxel_size,
        output_voxel_size,
        center,
        low_pass,
        box_size,
        invert,
        mirror,
        loglevel,
    )
    
def run_create_template(
    input: pathlib.Path,
    output: Optional[pathlib.Path],
    input_voxel_size: Optional[float],
    output_voxel_size: float,
    center: bool,
    low_pass: Optional[float],
    box_size: Optional[int],
    invert: bool,
    mirror: bool,
    loglevel: str,
    ):
    import logging
    import pathlib

    import numpy as np
    import numpy.typing as npt

    # Configure logging
    try:
        level = int(loglevel)
    except ValueError:
        level = getattr(logging, str(loglevel).upper(), 20)
    logging.basicConfig(level=level, force=True)

    # Read input data and voxel size
    volume = read_mrc(input)
    meta = read_mrc_meta_data(input)

    map_spacing_A = float(input_voxel_size) if input_voxel_size is not None else float(meta["voxel_size"])

    if input_voxel_size is not None and round(input_voxel_size, 3) != round(meta["voxel_size"], 3):
        logging.warning("Provided voxel size != annotated voxel size in input MRC header.")

    # Compose output path if needed
    if output is None:
        output = pathlib.Path(f"template_{input.stem}_{output_voxel_size}A.mrc")

    if map_spacing_A > output_voxel_size:
        raise NotImplementedError(
            "Assumes input map has smaller voxel size than the output template (no upsampling)."
        )

    template = generate_template_from_map(
        volume,
        map_spacing_A,
        output_voxel_size,
        center=center,
        filter_to_resolution=low_pass,
        output_box_size=box_size,
    )

    if invert:
        template = -template

    if mirror:
        template = np.flip(template, axis=0)

    write_mrc(output, template, output_voxel_size)
    logging.info("Wrote %s (voxel size %.3f Å) shape=%s", output, output_voxel_size, template.shape)


# Allow `python cpu_template_tools.py ...` execution
if __name__ == "__main__":  # pragma: no cover
    create_template()  # Click will parse sys.argv
