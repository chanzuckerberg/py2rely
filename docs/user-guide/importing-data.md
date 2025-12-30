# Importing Data

This guide covers importing tilt series and particle coordinates into py2rely-compatible STAR file formats.

## Overview

py2rely requires two input files for sub-tomogram averaging:

| File | Contents | Source |
|------|----------|--------|
| **Tilt Series STAR** | Alignment parameters, CTF info | AreTomo output |
| **Particles STAR** | Particle coordinates, orientations | Copick, STAR files, PyTom |

---

## 📐 Import Tilt Series

=== "From AreTomo"

    Import tilt series alignment from an AreTomo processing session.

    !!! question "What it does"

        py2rely reads these files and converts them into RELION's expected format, which includes:

        - Tilt series alignment (`.aln`)
        - CTF parameters (defocus, astigmatism)
        - Dose weighting information
        - Optics group assignments
        - Generates Relion-compatible STAR files

    ```bash
    py2rely prepare tilt-series \
        --base-project /path/to/aretomo \
        --session 24jan01 \
        --run run001 \
        -v 300 -sa 2.7 -ac 0.1 \
        --pixel-size 1.54 --total-dose 60
    ```
    
    !!! info "How does `py2rely` find my data?"

         Given `--base-project`, `--session`, and `--run` flags - py2rely looks for any alignment data in the following full search path: 
         
         * `/{base-project}/{session}/{run}/*_CTF.txt`.

    **Output structure:**
    ```bash
        input/tiltSeries/
        ├── aligned_tilt_series.star  # Global file (use this)
        ├── tomo001.star
        ├── tomo002.star
        └── ...
    ```

    <details markdown="1">
    <summary><b>📋`prepare tilt-series` Parameters</b></summary>

    | Parameter | Description | Default |
    |-----------|-------------|---------|
    | `--base-project` | AreTomo project root directory | `/hpc/projects/.../aretomo3` |
    | `-s, --session` | Session identifier | `23dec21` |
    | `-r, --run` | Run identifier | `run001` |
    | `-o, --output` | Output directory for STAR files | `input` |
    | `-ps, --pixel-size` | Unbinned pixel size (Å) | `1.54` |
    | `-td, --total-dose` | Total dose (e⁻/Å²) | `60` |
    | `-v, --voltage` | Acceleration voltage (kV) | `300` |
    | `-sa, --spherical-aberration` | Cs value (mm) | `2.7` |
    | `-ac, --amplitude-contrast` | Amplitude contrast | `0.07` |
    | `-og, --optics-group` | Optics group number | `1` |
    | `-ogn, --optics-group-name` | Optics group name | `opticsGroup1` |

    </details>

=== "Combine Multiple Sessions"

    If you collected data across multiple days or runs, you can merge them into a single tilt series file.
    
    !!! question "Why combine sessions?"
        - Increase particle count for better statistics
        - Pool data from multiple grid areas
        - Combine different imaging conditions (optics groups)

    ```bash
    # Import each session
    py2rely prepare tilt-series --session 24jan01 --output input/
    py2rely prepare tilt-series --session 24feb15 --output input/

    # Combine them
    py2rely prepare combine-tilt-series \
        --input input/tiltSeries/aligned_tilt_series_24jan01.star \
        --input input/tiltSeries/aligned_tilt_series_24feb15.star \
        --output input/tiltSeries/aligned_tilt_series.star
    ```

=== "Filter Unused Tomograms"

    Remove tomograms that don't contain any particles to speed up processing.
    
    !!! question "Why filter?"

        - Reduces computational overhead
        - Avoids unnecessary pseudo-subtomogram extraction
        - Keeps job logs cleaner

    ```bash
    py2rely prepare filter-unused-tilts \
        --particles input/full_picks.star \
        --tomograms input/tiltSeries/aligned_tilt_series.star
    ```
    
    !!! info "What happens?"
        - Reads which tomograms appear in your particles file
        - Removes tilt series entries for tomograms with zero particles
        - **Overwrites** the original tilt series STAR file (makes backup first)
---

## 🎯 Import Particle Coordinates

=== "From Copick"

    Import from coordinates from a [Copick](https://github.com/copick/copick) project:

    ```bash
    py2rely prepare particles \
        --config copick_config.json \
        --session 24jan01 \
        --name virus-like-particle \
        -ps 1.54 -x 4096 -y 4096 -z 1200 \
        -v 300 -sa 2.7  -ac 0.1
    ```
    
    !!! info "Coordinate System"
        Copick stores coordinates in **physical units (Ångstroms)**, not pixels.
        
        py2rely automatically converts to Relion format using:

        - Tomogram **unbinned** dimensions (`-x`, `-y`, `-z`)
        - Tilt-series Pixel size (`-ps`)

    !!! example "Particle Import"

        **Filter by specific runs:**
        ```bash
        py2rely prepare particles \
            --run-ids "run001,run002,run003" \
            ...
        ```
        
        **Filter by user/session ID:**
        ```bash
        py2rely prepare particles \
            --user-id "octopi" \
            --session-id "1" \
            ...
        ```


    <details markdown="1">
    <summary><b>📋 `prepare particles` Parameters</b></summary>

    | Parameter | Short | Description | Default |
    |-----------|-------|-------------|---------|
    | `--config` | `-c` | Path to Copick config file | *required* |
    | `--session` | `-s` | Experiment session identifier | *required* |
    | `--name` | `-n` | Protein/particle name | *required* |
    | `--output` | `-o` | Output directory for STAR file | `input` |
    | `--session-id` | `-sid` | Copick session ID filter | - |
    | `--user-id` | `-uid` | Copick user ID filter | - |
    | `--run-ids` | `-rids` | Run IDs to filter (comma-separated) | - |
    | `--voxel-size` | `-vs` | Voxel size of picked tomograms (Å) | - |
    | `--x` | `-x` | Tomogram x-dimension (pixels) | `4096` |
    | `--y` | `-y` | Tomogram y-dimension (pixels) | `4096` |
    | `--z` | `-z` | Tomogram z-dimension (pixels) | `1200` |
    | `--pixel-size` | `-ps` | Tilt series pixel size (Å) | `1.54` |
    | `--voltage` | `-v` | Acceleration voltage (kV) | `300` |
    | `--spherical-aberration` | `-sa` | Cs value (mm) | `2.7` |
    | `--amplitude-contrast` | `-ac` | Amplitude contrast | `0.07` |
    | `--optics-group` | `-og` | Optics group number | `1` |
    | `--optics-group-name` | `-ogn` | Optics group name | `opticsGroup1` |
    | `--relion5` | | Use Relion5 centered coordinates | `True` |

    </details>

=== "Combine Multiple Sources"

    Merge particles from different picking methods, sessions, or manual annotations. 

    ```bash
    py2rely prepare combine-particles \
        --input input/session1_particles.star \
        --input input/session2_particles.star \
        --input input/manual_picks.star \
        --output input/all_particles.star
    ```

    !!! info "Common Scenarios"
        - Merge automated + manual picks (derived from different copick sessionIDs, userIDs)
        - Multiple experimental sessions

---

## 🔄 Coordinate Systems

### Relion 5.0 Format

py2rely uses Relion 5.0 centered coordinate convention:

| Type | Columns | Units | Origin |
|------|---------|-------|--------|
| **Centered** | `rlnCenteredCoordinate[XYZ]Angst` | Ångstroms | Center of tomogram |
| **Pixel** | `rlnCoordinate[XYZ]` | Pixels | Top-left corner |

**Conversion formula:**
```
centered_angstrom = (pixel_coordinate - tomogram_size/2) × pixel_size
```

---

## Complete Example
```bash
# 1. Import tilt series
py2rely prepare tilt-series \
    --session 24jan01 \
    --output input \
    --pixel-size 1.54

# 2. Import particles
py2rely prepare particles \
    --config copick.json \
    --session 24jan01 \
    --name ribosome \
    --output input

# 3. Clean up unused tomograms
py2rely prepare filter-unused-tilts \
    --particles input/full_picks.star \
    --tomograms input/tiltSeries/aligned_tilt_series.star

# 4. Verify
python -c "import starfile; print(len(starfile.read('input/full_picks.star')['particles']))"
```

---

## Next Steps

- **Ready to refine?** → [3D Sub-tomogram Averaging](3d-subtomogram-averaging.md)
- **Want to validate first?** → [2D Slab Classification](2d-slab-classification.md)
- **Need examples?** → [Quick Start Guide](../getting-started/quick-start.md)