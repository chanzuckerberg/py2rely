# Claude Code / Claude Desktop Integration

`py2rely mcp` starts a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects Claude Code or Claude Desktop directly to your STA workflows. Claude can inspect available commands, prepare input files, generate SLURM submission scripts, and read pipeline results — all from a conversation.

---

## 🧰 What Claude Can Do

Once connected, Claude has access to the full py2rely and slabpick CLI through six tools:

| Tool | Purpose |
|------|---------|
| `list_py2rely_commands` | Browse all exposed commands and their descriptions |
| `get_command_help` | Fetch the full `--help` output for any command |
| `get_slabpick_tool_help` | Fetch help for slabpick tools (`make_minislabs`, etc.) |
| `get_class2d_summary_pdf` | Locate (or generate) the class average gallery PDF for inspection |
| `run_py2rely_command` | Execute a `py2rely` or `py2rely-slurm` command |
| `run_slabpick_command` | Execute a slabpick tool directly |

!!! info "How Claude handles long-running jobs"
    py2rely commands fall into two categories depending on how long they take to run.
    Just let Claude know whether you're on a SLURM cluster or running locally — it will adjust accordingly.

??? success "✅ Commands Claude runs for you"

    These are fast, non-blocking operations. Claude executes them directly and returns the result in the conversation.

    | Command | What it does |
    |---------|-------------|
    | `prepare particles` | Export copick coordinates to a RELION star file |
    | `prepare import-particles` | Import particles from an existing STAR file |
    | `prepare combine-particles` | Merge multiple particle STAR files |
    | `prepare tilt-series` | Import tilt series from AreTomo |
    | `prepare combine-tilt-series` | Merge multiple tilt series STAR files |
    | `prepare filter-unused-tilts` | Remove tilts not used by any particle |
    | `prepare relion5-parameters` | Generate a `sta_parameters.json` config file |
    | `prepare relion5-pipeline` | Initialise a RELION pipeline from a parameters file |
    | `prepare create-template` | Create a template from an MRC map |
    | `routines select` | Extract particles from the best 3D class |
    | `export star2copick` | Write refined RELION picks back to a copick project |
    | `rln_map_particles` | Map selected slab particles back to copick coordinates |

??? warning "⏳ Commands that submit or hand off to you"

    These jobs run for minutes to hours. Claude will either generate a SLURM submission script or print the exact command for you to run, depending on your setup.

    === "On a SLURM cluster"

        Claude calls `py2rely-slurm`, which writes a `.sh` script. You submit it with `sbatch`.

        | Command | Script generated |
        |---------|-----------------|
        | `slab slabpick` | `slabpick.sh` — runs `make_minislabs` + `normalize_stack` |
        | `slab class2d` | `class2d.sh` — runs RELION Class2D |
        | `routines class3d` | `class3d.sh` — runs RELION Class3D |
        | `pipelines sta` | submitted via Submitit directly to SLURM |
        | `pipelines polish` | submitted via Submitit directly to SLURM |

    === "Without SLURM (local / interactive)"

        Claude provides the exact `py2rely` command to paste into your terminal. Nothing is executed on your behalf — you stay in control of when the job runs.

        ```bash
        # Example — Claude will give you the filled-in version of commands like:
        py2rely slab class2d \
            --particles stack/particles_relion.star \
            --nr-classes 50 --particle-diameter 300

        py2rely routines class3d \
            --parameter sta_parameters.json \
            --particles particles.star \
            --reference reference.mrc
        ```

---

## 🚀 Starting the Server

Run `py2rely mcp` from your terminal. No extra installation is needed — the MCP server is included with py2rely.

```bash
py2rely mcp
```

By default the server uses **stdio** transport, which is what Claude Code and Claude Desktop expect. An SSE transport is also available for other MCP clients:

```bash
py2rely mcp --transport sse --port 8000
```

---

## ⚙️ Setup

=== "Claude Code"

    Add py2rely as an MCP server to your project from the terminal:

    ```bash
    claude mcp add py2rely -- py2rely mcp
    ```

    Or edit `.claude/mcp.json` in your project directory manually:

    ```json
    {
      "mcpServers": {
        "py2rely": {
          "command": "py2rely",
          "args": ["mcp"]
        }
      }
    }
    ```

    Restart Claude Code. You should see `py2rely` listed under connected MCP servers.

=== "Claude Desktop"

    Edit the Claude Desktop config file for your platform:

    **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
    **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

    ```json
    {
      "mcpServers": {
        "py2rely": {
          "command": "py2rely",
          "args": ["mcp"]
        }
      }
    }
    ```

    Restart Claude Desktop to pick up the change.

    !!! warning "Using a conda or virtual environment?"
        If py2rely is installed in a specific environment, use the full path to the binary:

        ```json
        {
          "mcpServers": {
            "py2rely": {
              "command": "/path/to/your/env/bin/py2rely",
              "args": ["mcp"]
            }
          }
        }
        ```

        Find the path with `which py2rely` after activating your environment.

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

    Claude runs `rln_map_particles` directly, mapping the selected particles back to their original copick coordinates and writing them under your chosen `user_id` and `session_id`.

=== "Workflow B — 3D Sub-Tomogram Averaging"

    Use this to run a full 3D reconstruction from copick coordinates.

    **Step 1 — Prepare inputs**

    Claude runs the relevant `prepare` commands directly (e.g. `prepare particles`, `prepare tilt-series`, `prepare relion5-parameters`) to assemble all inputs.

    **Step 2 — Run the STA pipeline**

    Claude either generates a submission script or runs with `--submitit` for direct SLURM submission:

    ```bash
    py2rely pipelines sta \
        --parameter sta_parameters.json \
        --submitit
    ```

    **Step 3 — [Optional] 3D Classification**

    Claude generates a `class3d.sh` script for you to submit. Once the job finishes:

    !!! warning "Class3D selection is a human step"
        Deciding which 3D class to carry forward requires expert judgement on map quality, resolution, and biological relevance. Claude will run `routines select` once you tell it which class number to keep — but the decision is always yours.

    **Step 4 — [Optional] Polish**

    Claude runs `pipelines polish` with `--submitit` or generates a script depending on your setup.

    **Step 5 — Export back to copick**

    Claude runs `export star2copick` directly to write the final refined picks back to your copick project. This always ends the STA workflow.

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
