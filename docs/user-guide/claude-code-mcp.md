# Claude Code / Claude Desktop Integration

`py2rely mcp` starts a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects Claude Code or Claude Desktop directly to your STA workflows. Claude can inspect available commands, prepare input files, read class average galleries, generate SLURM submission scripts, and walk you through the full pipeline — all from a conversation.

---

## What Claude Can Do

Once connected, you can describe what you want in plain language and Claude handles the rest:

<div class="grid cards" markdown>

-   :material-sitemap:{ .lg .middle } **Guide the full workflow**

    ---

    Walks you through every step — slab extraction → class selection → export, or particle import → parameters → STA pipeline — asking only for what it needs.

-   :material-flag-checkered:{ .lg .middle } **Fill in the flags**

    ---

    Looks up the correct options for every command so you don't have to memorise them.

-   :material-image-search:{ .lg .middle } **Inspect class averages**

    ---

    Calls `get_class2d_summary_pdf`, reads the gallery PDF with its vision capabilities, and recommends which classes show real particle signal versus noise or junk.

-   :material-lightning-bolt:{ .lg .middle } **Run fast steps for you**

    ---

    Executes `prepare particles`, `prepare tilt-series`, `routines select`, and `export star2copick` directly and reports back.

-   :material-script-text:{ .lg .middle } **Generate SLURM scripts**

    ---

    For `slab slabpick`, `slab class2d`, and `routines class3d`, produces a ready-to-submit `.sh` script for you to `sbatch` yourself.

</div>

!!! info "You stay in control"
    Claude suggests commands rather than running them by default — you copy, review, and paste. For fast, non-destructive commands you can say *"go ahead and run it"* to skip the copy-paste step. Long-running RELION jobs (`Class2D`, `Class3D`, the STA pipeline) are always handed off as SLURM scripts or copy-pasteable commands, regardless.

??? note "MCP tools used under the hood"
    | Tool | Purpose |
    |------|---------|
    | `list_py2rely_commands` | Browse all exposed commands and their descriptions |
    | `get_command_help` | Fetch the full `--help` output for any command |
    | `get_slabpick_tool_help` | Fetch help for slabpick tools (`make_minislabs`, etc.) |
    | `get_class2d_summary_pdf` | Locate (or generate) the class average gallery PDF for inspection |
    | `run_py2rely_command` | Execute a `py2rely` or `py2rely-slurm` command |
    | `run_slabpick_command` | Execute a slabpick tool directly |

---

## Setup

Run `py2rely mcp install` once from the terminal. It automatically registers the server in the right config file — you never need to start the server manually.

=== "Claude Code (project)"

    Registers py2rely for the current directory only. Other projects won't see it.

    ```bash
    cd /path/to/your/relion/project
    py2rely mcp install
    ```

    This creates a `.mcp.json` file in the current directory. Open Claude Code in that directory and the server connects automatically.

=== "Claude Code (global)"

    Registers py2rely for all Claude Code sessions on this machine.

    ```bash
    py2rely mcp install --target code-global
    ```

    Start a new Claude Code session to pick up the change.

=== "Claude Desktop"

    ```bash
    py2rely mcp install --target desktop
    ```

    Restart Claude Desktop to pick up the change.

You can verify the registration at any time:

```bash
py2rely mcp status                        # check project-level
py2rely mcp status --target code-global   # check global
```

To remove it:

```bash
py2rely mcp uninstall --server-name py2rely
```

---

## Example Workflows

When you start a conversation, Claude will first ask which workflow you want to run.

=== "Workflow A — 2D Slab Filtering"

    Use this to validate or clean picks from a CoPick project using 2D class averages. The full loop: extract slabs → classify → select good classes → export curated picks back to CoPick.

    **Step 1 — Extract slabs**

    > *"I want to run 2D slab classification on ribosomes from my CoPick project at /data/config.json. The picks are under user_id octopi, voxel spacing 10 Å, pixel size 1.54 Å."*

    Claude suggests (or runs):

    ```bash
    make_minislabs \
        --in_coords /data/config.json \
        --out_dir slabs/ \
        --extract_shape 500 500 400 \
        --voxel_spacing 10.0 \
        --tomo_type denoised \
        --user_id octopi \
        --particle_name ribosome \
        --make_stack

    normalize_stack \
        --in_stack slabs/particles.mrcs \
        --out_stack slabs/particles_relion.mrcs \
        --apix 1.54
    ```

    !!! tip "Want a SLURM script instead?"
        Just say *"generate a SLURM script for this"* and Claude will suggest `py2rely-slurm slab slabpick` to produce a `slabpick.sh` you can submit with `sbatch`.

    **Step 2 — Run Class2D**

    > *"Slabpick finished. Run Class2D with 50 classes and a particle diameter of 300 Å."*

    Claude suggests (or runs):

    ```bash
    py2rely slab class2d \
        --particle-diameter 300 \
        --num-classes 50
    ```

    !!! tip "Want a SLURM script instead?"
        Say *"generate a SLURM script for Class2D"* and Claude will suggest `py2rely-slurm slab class2d` to produce a `class2d.sh` for `sbatch`.

    **Step 3 — Inspect class averages and select classes**

    > *"Class2D is done. Show me the class averages and suggest which to keep."*

    Claude calls `get_class2d_summary_pdf`, reads the gallery PDF with its vision capabilities, and replies with something like:

    > *"I can see 50 classes. Classes 3, 7, 12, and 18 show clear ribosomal features with well-defined density. Classes 1, 4, and 9 appear to be carbon edge or ice contamination. I'd suggest keeping classes 3, 7, 12, 18, 22, and 31 — want me to run the selection?"*

    !!! tip "How class selection works"
        Claude inspects the class average gallery visually — the same way you would when browsing the PDF. It flags classes that look like real particles and highlights ones that appear to be junk. You confirm or adjust before anything is written.

    Claude then suggests (or runs):

    ```bash
    py2rely routines select \
        -p Class2D/job001/run_it025_data.star \
        -c 3,7,12,18,22,31
    ```

    **Step 4 — Export back to CoPick**

    > *"Export the selected particles back to CoPick under user_id slabpick, session_id 1."*

    Claude suggests:

    ```bash
    rln_map_particles \
        --rln_file Select/job002/particles.star \
        --map_file stack/particle_map.csv \
        --particle_name ribosome \
        --user_id octopi \
        --session_id 1 \
        --user_id_out slabpick \
        --session_id_out 1
    ```

=== "Workflow B — 3D Sub-Tomogram Averaging"

    Use this to run a full 3D reconstruction from CoPick coordinates. The full loop: import coordinates → import tilt series → prepare parameters → run STA pipeline → (optional classification) → export refined picks back to CoPick.

    **Step 1 — Import particle coordinates**

    > *"I want to run STA on virus-like-particles from /data/config.json. Session is 24jan01, voxel size 10 Å, pixel size 1.54 Å, tomogram dimensions 4096×4096×1200."*

    Claude runs:

    ```bash
    py2rely prepare particles \
        --config /data/config.json \
        --name virus-like-particle \
        --session 24jan01 \
        --voxel-size 10.0 \
        --pixel-size 1.54 \
        -x 4096 -y 4096 -z 1200
    ```

    This writes `input/24jan01_virus_like_particle.star`.

    **Step 2 — Import tilt series**

    > *"Import the tilt series from /data/aretomo_output."*

    Claude suggests (or runs):

    ```bash
    py2rely prepare tilt-series \
        --aretomo-dir /data/aretomo_output \
        --pixel-size 1.54
    ```

    This writes `input/tiltSeries/aligned_tilt_series.star`.

    **Step 3 — Prepare the parameters JSON**

    > *"Generate the pipeline parameters. Particle diameter is 290 Å, symmetry C1, binnings 4,2,1."*

    Claude runs:

    ```bash
    py2rely prepare relion5-parameters \
        -p input/24jan01_virus_like_particle.star \
        -ts input/tiltSeries/aligned_tilt_series.star \
        -ps 1.54 \
        -pd 290 \
        -s C1 \
        -bl 4,2,1
    ```

    Claude reads back the resulting box sizes so you know what template resolution to target:

    ```
    [Initialize] Box Size: 84 @ bin=4
    [Initialize] Box Size: 168 @ bin=2
    [Initialize] Box Size: 352 @ bin=1
    ```

    **Step 4 — Run the STA pipeline**

    > *"I have a reference map at reference.mrc. Run the full pipeline on SLURM with 4 GPUs."*

    Claude suggests:

    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --reference-template reference.mrc \
        --submitit \
        --num-gpus 4
    ```

    !!! tip "No reference? No problem."
        Tell Claude you don't have a reference and it will suggest `--run-denovo-generation True` instead, which generates an initial model from scratch.

    **Step 5 — [Optional] 3D Classification**

    > *"Pipeline is done. Run 3D classification with 4 classes."*

    Claude suggests (or runs):

    ```bash
    py2rely routines class3d \
        --parameter sta_parameters.json \
        --nclasses 4
    ```

    !!! tip "Want a SLURM script instead?"
        Say *"generate a SLURM script for Class3D"* and Claude will suggest `py2rely-slurm routines class3d` to produce a `class3d.sh` for `sbatch`.

    Once the job finishes, tell Claude which class to keep:

    > *"Class 2 looks the best. Select it and continue."*

    Claude suggests:

    ```bash
    py2rely routines select \
        --parameter sta_parameters.json \
        --class-job job001 \
        --keep-classes 2 \
        --best-class 2
    ```

    !!! warning "Class selection is a human step"
        Deciding which 3D class to carry forward requires expert judgement on map quality, resolution, and biological relevance. Claude will suggest `routines select` once you tell it which class number to keep — but the decision is always yours.

    **Step 6 — Export back to CoPick**

    > *"Export the final refined particles back to CoPick under user_id relion, session_id 1."*

    Claude suggests:

    ```bash
    py2rely export star2copick \
        --particles Refine3D/job024/run_data.star \
        --configs /data/config.json \
        --sessions 24jan01 \
        --particle-name virus-like-particle \
        --export-user-id relion \
        --export-session-id 1
    ```

---

## Available Commands

??? note "py2rely commands"

    | Command | Description |
    |---------|-------------|
    | `prepare particles` | Import coordinates from a CoPick project into a RELION star file |
    | `prepare import-particles` | Import particles from an existing STAR file |
    | `prepare combine-particles` | Combine multiple particle STAR files into one |
    | `prepare tilt-series` | Import tilt series from AreTomo output |
    | `prepare combine-tilt-series` | Combine multiple tilt series STAR files |
    | `prepare filter-unused-tilts` | Remove tilts not referenced by any particle |
    | `prepare relion5-parameters` | Generate a `sta_parameters.json` config file |
    | `prepare relion5-pipeline` | Initialize a RELION pipeline from a parameters file |
    | `prepare create-template` | Create a template from an MRC map |
    | `slab class2d` | Run RELION Class2D on slab projections (direct, blocking) |
    | `slab summary` | Generate a PDF gallery of 2D class averages for inspection |
    | `routines select` | Select particles from chosen classes after Class2D or Class3D |
    | `export star2copick` | Export a RELION particles star file back into CoPick |
    | `pipelines sta` | Run the full STA pipeline (use `--submitit` for SLURM) |
    | `pipelines polish` | Run the frame-based polishing pipeline (use `--submitit` for SLURM) |

??? note "py2rely-slurm commands (generate .sh scripts)"

    | Command | Script generated |
    |---------|-----------------|
    | `slab slabpick` | `slabpick.sh` — runs `make_minislabs` + `normalize_stack` |
    | `slab class2d` | `class2d.sh` — runs RELION Class2D |
    | `routines class3d` | `class3d.sh` — runs RELION Class3D |

??? note "slabpick tools"

    | Tool | Description |
    |------|-------------|
    | `make_minislabs` | Extract slab projections from tomograms at picked coordinates |
    | `normalize_stack` | Normalize an MRC particle stack to mean=0, std=1 |
    | `rln_map_particles` | Map selected RELION particles back to CoPick coordinates |
