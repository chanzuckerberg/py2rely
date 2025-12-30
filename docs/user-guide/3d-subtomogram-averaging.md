# 3D Sub-tomogram Averaging Workflow

A comprehensive guide to running automated sub-tomogram averaging with py2rely and Relion 5.0.

## Overview

The 3D sub-tomogram averaging (STA) workflow in py2rely automates the entire process from particle extraction to high-resolution reconstruction. The pipeline handles:

- ✅ Pseudo sub-tomogram extraction
- ✅ Initial model generation (de novo or from template)
- ✅ 3D classification (optional)
- ✅ CTF refinement and Bayesian polishing
- ✅ Post-processing and resolution estimation

## Workflow Steps

### 1. 📦 Data Preparation

Refer to the [Import Guide](importing-data.md) for generating the `aligned_tilt_series.star` and `full_picks.star` file.

### 2. ⚙️ Generate Pipeline Parameters

Create a parameter JSON file with default settings:

```bash
py2rely prepare relion5-parameters \
    -p input/full_picks.star \
    -ts input/tiltSeries/aligned_tilt_series.star \
    -ps 1.54 -lp 50 -pd 330 -bs 2 \
    -sym C1 -bl 4,2,1 \
    -o sta_parameters.json
```

??? note "📋 `prepare relion5-parameters`"

    | Parameter | Short | Description | Default |
    |-----------|-------|-------------|---------|
    | `--output` | `-o` | Output path for parameter JSON file | `sta_parameters.json` |
    | `--tilt-series` | `-ts` | Path to tilt series STAR file | `input/tiltSeries/aligned_tilt_series.star` |
    | `--particles` | `-p` | Path to particles STAR file | `input/full_picks.star` |
    | `--tilt-series-pixel-size` | `-ps` | Tilt series pixel size (Å) | `1.54` |
    | `--symmetry` | `-s` | Particle symmetry (C1, C2, D2, etc.) | `C1` |
    | `--low-pass` | `-lp` | Low-pass filter for reference template (Å) | `50` |
    | `--protein-diameter` | `-pd` | Particle diameter (Å) | `290` |
    | `--denovo-generation` | `-dg` | Enable de novo model generation | `False` |
    | `--box-scaling` | `-bs` | Box size padding factor | `2.0` |
    | `--binning-list` | `-bl` | Binning factors (comma-separated) | `4,2,1` |

The generated `sta_parameters.json` contains all Relion job parameters and can be manually edited if needed.

!!! tip "Symmetry"

    If your protein has symmetry, don’t forget to use the `--symmetry` flag!

### 3. 🚀 Run the STA Pipeline

The overall STA pipeline is composed of a series of steps that are ran sequentially.

![pipeline](../assets/workflow.png)

When running the pipeline we have multiple options for generating the inital model, and the ability to enable the auto 3D classification feature. 

??? note "📋 `sta` Parameters"

    | Parameter | Short | Description | Default |
    |-----------|-------|-------------|---------|
    | `--parameter` | `-p` | Path to parameter JSON file | `sta_parameters.json` *(required)* |
    | `--reference-template` | `-rt` | Reference template for initial refinement (optional) | - |
    | `--run-denovo-generation` | `-dg` | Generate initial model without template | `False` |
    | `--run-class3D` | | Run 3D classification after refinement | `False` |

#### Initial Model Options

After we extract our sub-tomograms from our tilt series, we have a few options we can choose from to generate our initial model.

![initmodel](../assets/initial_model_options.png)

=== "Reference Refinement"

    This assumes we have a template that we can use to estimate our initial orientations.

    First, let's generate a template with py2rely. We can use any template that's available on [EMDB](https://www.ebi.ac.uk/emdb/) and downsample it to the resolution at the first binning factor.  

    ```bash
    py2rely prepare template \
        -i ribosome_3883.map -o reference.mrc \
        -ivs 0.83 -ovs 8.3 -lp 50 -b 64 
    ```

    <details markdown="1">
    <summary><b>📋 `py2rely prepare template` Parameters </b></summary>

    | Parameter | Short | Description | Default |
    |-----------|-------|-------------|---------|
    | `--input` | `-i` | Input MRC density map file | *required* |
    | `--output` | `-o` | Output path (.mrc) | `template_{stem}_{voxel}A.mrc` |
    | `--input-voxel-size` | `-ivs` | Voxel size of input map (Å) | *from MRC header* |
    | `--output-voxel-size` | `-ovs` | Target voxel size (Å) - should match tomograms | *required* |
    | `--center` | `-c` | Center density by center of mass before filtering | `False` |
    | `--low-pass` | `-lp` | Gaussian low-pass filter resolution (Å) | `2 × output voxel size` |
    | `--box-size` | `-b` | Final template box size (voxels) | *downsampled size* |
    | `--invert` | | Multiply template by -1 | `False` |
    | `--mirror` | `-m` | Mirror template along first axis | `False` |
    | `--log` | | Logging level | `20` (info) |

    </details>

    In the case that the protein has symmetry, we also need to align the template with relion. 

    ```bash
    # Align to Symmetric Axis
    relion_align_symmetry \
        --i reference.mrc \
        --o reference.mrc \
        --sym D2 
    ```

    Now that we have a template that's at the correct resolution and orientation, we can run the STA pipeline!

    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --reference-template reference.mrc
    ```

    !!! warning "Common Pitfall"
        When generating the template with `py2rely prepare template`, be sure that the box-size and voxel size are the equivalent resolution as the sub-tomograms at the first binning factor. If not, Relion will spit out an error at the first Refine3D step.

=== "De-Novo Generation"

    We can generate our orientations completely de-novo without the need of relying on a template.

    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --run-denovo-generation True
    ```

=== "Reconstruct Particles"

    If we have the orientations already available, we can directly reconstruct our particle and use that reconstruction as our reference. 
    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json
    ```

#### Auto-Class3D

In cases where users would like to rely on classification to improve the particle quality, users can use Class3D with a given number of classes and the best class will be automatically selected for the downstream processing.

## Example: Complete Workflow

Here's a complete example from start to finish:

```bash
# 1. Import data
py2rely prepare tilt-series \
    --base-project /data/aretomo \
    --session 24jan01 \
    --output input \
    --pixel-size 1.54

py2rely prepare particles \
    --config copick.json \
    --session 24jan01 \
    --name ribosome \
    --output input \
    --pixel-size 1.54 \
    --x 4096 --y 4096 --z 1200

# 2. Generate parameters
py2rely prepare relion5-parameters \
    --tilt-series input/tiltSeries/aligned_tilt_series.star \
    --particles input/full_picks.star \
    --tilt-series-pixel-size 1.54 \
    --symmetry C1 \
    --protein-diameter 290 \
    --binning-list 4,2,1 \
    --output sta_parameters.json

# 3. Run pipeline
py2rely pipelines sta \
    --parameter sta_parameters.json \
    --reference-template initial.mrc \
    --run-class3D True

# 4. Check results
ls PostProcess/job015/
# postprocess_masked.mrc - Final sharpened map
# postprocess_fsc.eps - Resolution plot
```

## Next Steps

- Learn about [2D slab classification](../2d-slab-classification.md) for alternative workflows
- Explore [data import options](../importing-data.md) for different data sources
- Check the [API reference](../../api-reference/overview.md) for advanced usage

