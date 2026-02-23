# Quick Start

Get up and running with py2rely in minutes! This guide shows the minimal commands needed to start processing your data.

## 🧪 2D Slab Classification Workflow

!!! tip "When to Use This Workflow"
    Use 2D slab classification for:

    - 🔍 Rapid particle validation
    - 🧹 Removing false positives

=== "Step 1: Extract Slabs"

    Extract slabs from your tomograms (requires [`slabpick`](https://github.com/apeck12/slabpick)):

    ```bash
    make_minislabs \
        --in_coords=/path/to/copick/config.json \
        --out_dir=/path/to/output \
        --extract_shape 500 500 400 \
        --coords_scale 1.0 --col_name rlnMicrographName \
        --voxel_spacing 5.0 --tomo_type denoised \
        --user_id octopi --particle_name ribosome

    normalize_stack \
        --in_stack=/path/to/output/particles.mrcs \
        --out_stack=/path/to/output/particles_relion.mrcs \
        --apix 1.54
    ```

    For those that would like to run both of these commands through the slurm can run a single command:

    ```bash
    py2rely-slurm slab slabpick \
        --in-coords input/full_picks.star \
        --in-vols input/tomograms.star \
        --out-dir slabs/ \
        --extract-shape "128,128,32" \
        --voxel-spacing 10.0 \
        --pixel-size 1.54
    
    sbatch slabpick.sh
    ```
    
    !!! info "Slab Dimensions"
        - [Parameter Descriptions](../user-guide/2d-slab-classification.md)
        - **X, Y**: 2-3× particle diameter (e.g., 128-256 pixels)
        - **Z**: Thickness (typically 16-64 pixels)
        - Thinner Z = better alignment, less context

=== "Step 2: Run 2D Classification"

    Classify the extracted slabs:
    
    ```bash
    py2rely slab class2d \
        --particles slabs/particles.star \
        --tau-fudge 4.0 \
        --nr-classes 50 \
        --class-algorithm 2DEM \
        --nr-iter 25
    ```
    
    !!! tip "Parameter Guidelines"
        - **nr-classes**: ~1 per 100-200 particles
        - **tau-fudge**: 3.0-4.0 (balanced)
        - **nr-iter**: 20-30 iterations typically sufficient

=== "Step 3: Visualize Results"

    View and extract class averages:
    
    === "Gradio (Web Interface)"
    
        ```bash
        py2rely slab extract
        ```
        
        !!! success "Access the Interface"
            Open the web page through the local or public URL.

            - Browse class averages
            - Select classes by clicking
            - Export selected particles
    
    === "PyQt5 (Desktop GUI)"
    
        ```bash
        py2rely slab extract-desktop \
            -j job001
        ```
        
        !!! success "Native Desktop App"
            Launches a native GUI application

            - More responsive UI

    !!! warning "GUI Requirements"
        Make sure you've installed either `gradio` (for web GUI) or `PyQt5` (for desktop GUI) as described in the [Installation Guide](installation.md).

=== "Step 4: Exporting 2D Classes to Copick"

    After selecting good classes, you can write the curated particle set back into `CoPick` for reuse in downstream workflows (e.g. 3D STA or visualization).

    ```bash
    rln_map_particles \
        --rln_file Select/job002/particles.star \
        --map_file stack/particle_map.csv \
        --coords_file copick_config.json \
        --particle_name ribosome \
        --session_id 1 \
        --user_id octopi \
        --particle_name_out ribosome_clean \
        --session_id_out 2 \
        --user_id_out slabpick
    ```

    !!! info "Input vs output CoPick identifiers"
        - `--session_id` and `--user_id` specify **where the original particle coordinates came from**
        - `*_out` parameters define **where the curated particle set will be written**

        This allows you to preserve the original picks while tracking multiple rounds of curation.    

---

## 🚀 3D Sub-tomogram Averaging Workflow

!!! tip "Quick Overview"
    This workflow takes you from raw data to high-resolution reconstruction in 3 steps. The entire process typically takes several hours to days depending on your dataset size and compute resources.

=== "Step 1: Prepare Your Data"

    !!! info "Data Sources"
        You can import from:

        - **AreTomo**: Tilt series alignment output
        - [**Copick**](https://github.com/copick/copick): Particle coordinate storage
        - **STAR files**: Pre-formatted Relion files
        - See [Importing Data](../user-guide/importing-data.md) for details

    Import tilt series and particle coordinates:
    
    ```bash
    # Import tilt series from AreTomo output
    py2rely prepare tilt-series \
        --base-project /path/to/aretomo \
        --session 24jan01 \
        --output input \
        --pixel-size 1.54
    
    # Import particles from Copick
    py2rely prepare particles \
        --config copick_config.json \
        --session 24jan01 \
        --name ribosome \
        --output input \
        --pixel-size 1.54 \
        --x 4096 --y 4096 --z 1200
    ```

    !!! question "How particle coordinates are handled"
        Particle coordinates imported from [**Copick**](https://github.com/copick/copick) are stored in **physical units (Ångstroms)** rather than pixel or voxel indices.

        This means:

        - Coordinates are **agnostic to pixel size and voxel size**
        - py2rely automatically maps coordinates into the correct Relion coordinate system based on:
            - Tomogram dimensions (`--x`, `--y`, `--z`)
            - Pixel size

=== "Step 2: Generate Parameters"

    Create a parameter file for your pipeline:
    
    ```bash
    py2rely prepare relion5-parameters \
        --tilt-series input/tiltSeries/aligned_tilt_series.star \
        --particles input/full_picks.star \
        --tilt-series-pixel-size 1.54 \
        --symmetry C1 \
        --protein-diameter 290 \
        --output sta_parameters.json
    ```
    
    !!! question "What parameters should I use?"
        - **Symmetry**: Match your particle (C1, C2, D2, etc.)
        - **Protein diameter**: Estimate particle size (in Angstroms)
        - **Binning list**: Start with `4,2,1` for most cases
        - See [3D STA Guide](../user-guide/3d-subtomogram-averaging.md) for details

=== "Step 3: Run the Pipeline"

    Execute the full sub-tomogram averaging pipeline:
    
    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --reference-template initial_model.mrc
    ```
    
    To run the same pipeline on a **SLURM cluster** with Submitit (jobs submitted and waited on automatically), run once `py2rely config` to set Python and Relion load commands, then:
    
    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --reference-template initial_model.mrc \
        --submitit True --num-gpus 4 --gpu-constraint "a100|h100" \
        --cpu-constraint "8,32 --timeout 72
    ```
    
    See [Running on HPC with Submitit](../user-guide/running-on-hpc-with-submitit.md) for details.

    !!! tip "Flexible pipeline execution"
        The STA pipeline can be run in multiple modes depending on what information you already have.

        You can:
        
        - Provide a **reference template** (recommended when available)
        - Run **de novo model generation** (template-free)
        - Enable or disable **3D classification**
        - Combine these options as needed

    All options are controlled through CLI flags and the parameter file.

    === "Reference Template Available"

        If you have a starting reference (recommended):
        
        ```bash
        py2rely prepare template \
            -i /ribo80S_emd_3883.map -o reference.mrc \
            -ivs 0.8 -ovs 9.24 -lp 40 -b 64

        (OPTIONAL)
        relion_align_symmetry --sym D2 \
            --i reference.mrc --o reference.mrc \

        py2rely pipelines sta \
            --parameter sta_parameters.json \
            --reference-template reference.mrc
        ```
        
        !!! tip "Template Requirements"
            - Low-pass filter to the template to 40-50 Å
            - Ensure the template is aligned to the correct symmetry access.
            - Template can be obtaineed from [EMDB](https://www.ebi.ac.uk/emdb/).
            - The output voxel size (`ovs`) and box size (`-b`) should match the resolution at the first binning level.

    === "No Reference Available"

        Generate initial model from scratch:
        
        ```bash
        py2rely pipelines sta \
            --parameter sta_parameters.json \
            --run-denovo-generation True
        ```
        
        !!! warning "De Novo Generation"
            - Requires more particles
            - May need manual intervention
            - Consider template matching first

    === "Auto 3D Classification"

        Add classification step after refinement at the highest binning (lowest resolution), `py2rely` estimates the best class map and proceeds with following pipeline. This is only for particle cleaning, for high-resolution focused classification we recommend manual intervention. The number of classes can be specified in the `py2rely prepare relion5-parameters` step with the `--nclasses` flag.
        
        ```bash
        py2rely pipelines sta \
            --parameter sta_parameters.json \
            --run-class3D True --class-selection auto
        ```

        !!! warning "Auto-Class Selection"
            Auto class selection only works for cases where two classes are selected for Class3D. In cases where multi-classification is desired, use `--class-selection manual` so the pipeline stops after the Class3D job.
            
            Use `py2rely routines select` to manually pick which classes to keep and combine their particles into a single STAR file. To keep particles from more than one class, pass a comma-separated list to `--keep-classes` (e.g. `--keep-classes 1,2,3`).

            ??? note "📋 `py2rely routines select` Parameters"
                | Parameter | Short | Description | Default |
                |-----------|-------|-------------|---------|
                | `--parameter` | `-p` | Path to pipeline parameter JSON file | `sta_parameters.json` *(required)* |
                | `--class-job` | `-cj` | Class3D job directory name (e.g. job001) | `job001` |
                | `--keep-classes` | `-kc` | Comma-separated class numbers to keep | `1,2,3` |
                | `--best-class` | `-bc` | Class number to use as reference for refinement | `1` |
                | `--run-refinement` | `-rr` | Run 3D refinement after selection | `False` |
                | `--mask-path` | `-mp` | Optional path to mask for refinement | — |

                !!! example "Example"
                    ```bash
                    py2rely routines select \
                        --parameter sta_parameters.json \
                        --class-job job001 \
                        --keep-classes 1,2,3 \
                        --best-class 1
                    ```

    !!! success "What Happens Next"
        The pipeline automatically:

        - ✅ Extracts pseudo sub-tomograms
        - ✅ Generates initial model
        - ✅ Refines at multiple binning levels (4 → 2 → 1)
        - ✅ Reconstructs and post-processes
        - ✅ Estimates final resolution


---

## 📤 Export Data

After a 2D and 3D workflow is complete, we can export the particles back to Copick to visualize the particle orientations in the tomogram

=== "Export STA Results to Copick"

    Export refined particles back to Copick format:
    ```bash
    py2rely export star2copick \
        --particles Refine3D/job001/run_data.star \
        --configs "config1.json,config2.json" \
        --sessions "24jan01,24feb15" \
        --particle-name ribosome \
        --export-user-id relion \
        --export-session-id 99
    ```
    
    Useful for visualization in ChimeraX or training segmentation models.

=== "Export Class3D to a New StarFile"

    In cases where we want to take classification jobs and aggretate the multiple classes to a new particle stack, we can use the `class2star` command.

    ```bash
    py2rely export class2star \
        --parameter sta_parameters.json \
        --class-job job001 \
        --export-classes 1,2,3 \
        --output input/best_classes.star
    ```

=== "Export Class2D to Copick"

    Curated particle selections from 2D slab classification can be written
    back to **CoPick** using `rln_map_particles`.

    ```bash
    rln_map_particles \
        --rln_file Select/job002/particles.star \
        --map_file stack/particle_map.csv \
        --coords_file copick_config.json \
        --particle_name ribosome \
        --session_id 1 \
        --user_id octopi \
        --particle_name_out ribosome_clean \
        --session_id_out 2 \
        --user_id_out slabpick
    ```


---

## 🎯 What's Next?

- **3D STA Workflow**: See the [detailed guide](../user-guide/3d-subtomogram-averaging.md) for comprehensive documentation
- **2D Slab Workflow**: Check out the [slab classification guide](../user-guide/2d-slab-classification.md) for advanced usage
- **Data Import**: Learn about [importing data](../user-guide/importing-data.md) from various sources

