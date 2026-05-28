# Claude Code / Claude Desktop Integration

`py2rely mcp` starts a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects Claude Code or Claude Desktop directly to your STA workflows. Claude can inspect available commands, prepare input files, generate SLURM submission scripts, and read pipeline results — all from a conversation.

---

## 🧰 What Claude Can Do

Once connected, Claude has access to the full py2rely and slabpick CLI through these tools:

| Tool | Purpose |
|------|---------|
| `list_py2rely_commands` | Browse all exposed commands and their descriptions |
| `get_command_help` | Fetch the full `--help` output for any command |
| `get_slabpick_tool_help` | Fetch help for slabpick tools (`make_minislabs`, etc.) |
| `get_class2d_summary_pdf` | Locate (or generate) the class average gallery PDF for inspection |
| `run_py2rely_command` | Execute a `py2rely` or `py2rely-slurm` command |
| `run_slabpick_command` | Execute a slabpick tool directly |

!!! info "Default behaviour: suggest, not run"
    By default Claude will give you the exact command to copy and paste — you stay in control of what runs and when. If you'd prefer Claude to run a command directly, just ask: *"go ahead and run it"*.

    For long-running RELION jobs (Class2D, Class3D, STA pipeline), Claude always hands off to you regardless — either by generating a SLURM `.sh` script to `sbatch`, or by printing the command to run locally.

---

## ⚙️ Setup

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

## 💬 Example Workflows

When you start a conversation, Claude will first ask which workflow you want to run.

=== "Workflow A — 2D Slab Filtering"

    Use this to validate or clean picks from a copick project using 2D class averages.

    **Step 1 — Extract slabs**

    Claude generates a SLURM submission script:

    ```bash
    sbatch slabpick.sh   # runs make_minislabs + normalize_stack
    ```

    **Step 2 — Run Class2D**

    Claude generates the Class2D script:

    ```bash
    sbatch class2d.sh
    ```

    **Step 3 — 🔍 Select classes**

    > *"Class2D is done. Show me the class averages and suggest which to keep."*

    Claude calls `get_class2d_summary_pdf`, reads the gallery PDF with its vision capabilities, and suggests which classes show clean particle signal vs noise, ice, or carbon. You make the final call.

    !!! tip "How class selection works"
        Claude inspects the class average gallery visually — the same way you would when browsing the PDF. It flags classes that look like real particles and highlights ones that appear to be junk. You confirm or adjust the selection before anything is written.

    **Step 4 — Export back to copick**

    Claude suggests the `rln_map_particles` command to map selected particles back to their original copick coordinates under your chosen `user_id` and `session_id`.

=== "Workflow B — 3D Sub-Tomogram Averaging"

    Use this to run a full 3D reconstruction from copick coordinates.

    **Step 1 — Prepare inputs**

    Claude suggests the relevant `prepare` commands (e.g. `prepare particles`, `prepare tilt-series`, `prepare relion5-parameters`) to assemble all inputs.

    **Step 2 — Run the STA pipeline**

    Claude suggests the command, either with `--submitit` for direct SLURM submission or as a script to run locally:

    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --submitit
    ```

    **Step 3 — [Optional] 3D Classification**

    Claude suggests the `py2rely-slurm routines class3d` command to generate a `class3d.sh` script for you to submit. Once the job finishes:

    !!! warning "Class3D selection is a human step"
        Deciding which 3D class to carry forward requires expert judgement on map quality, resolution, and biological relevance. Claude will suggest `routines select` once you tell it which class number to keep — but the decision is always yours.

    **Step 4 — [Optional] Polish**

    Claude suggests `pipelines polish` with `--submitit` or the equivalent local command.

    **Step 5 — Export back to copick**

    Claude suggests `export star2copick` to write the final refined picks back to your copick project. This always ends the STA workflow.

---

## 📖 Available Commands

??? note "📋 py2rely commands"

    | Command | Description |
    |---------|-------------|
    | `prepare particles` | Import coordinates from a copick project into a RELION star file |
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
    | `export star2copick` | Export a RELION particles star file back into copick projects |
    | `pipelines sta` | Run the full STA pipeline (use `--submitit` for SLURM) |
    | `pipelines polish` | Run the frame-based polishing pipeline (use `--submitit` for SLURM) |
    | `routines class3d` | Run a single RELION Class3D job |
    | `routines select` | Select particles from the best class after Class3D |

??? note "📋 py2rely-slurm commands (generate .sh scripts)"

    | Command | Script generated |
    |---------|-----------------|
    | `slab slabpick` | `slabpick.sh` — runs `make_minislabs` + `normalize_stack` |
    | `slab class2d` | `class2d.sh` — runs RELION Class2D |
    | `routines class3d` | `class3d.sh` — runs RELION Class3D |

??? note "📋 slabpick tools"

    | Tool | Description |
    |------|-------------|
    | `make_minislabs` | Extract slab projections from tomograms at picked coordinates |
    | `normalize_stack` | Normalize an MRC particle stack to mean=0, std=1 |
    | `rln_map_particles` | Map selected RELION particles back to copick coordinates |
