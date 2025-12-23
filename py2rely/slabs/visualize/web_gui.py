from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.command(context_settings=cli_context, name='extract')
@click.option('--server', '-s', type=str, default='127.0.0.1', help='Server address to host the GUI on.')
@click.option('--port', '-p', type=int, default=7860, help='Port number to host the GUI on.')
def extractor(server, port):
    """
    Launch a web-based GUI for browsing and exporting RELION Class2D jobs.

    The GUI is hosted locally on the specified server and port, making it
    accessible from the same machine or via SSH port forwarding
    (e.g. when running on a remote workstation or cluster).

    In addition, a shareable public URL is generated, allowing access to
    the interface from any computer with a web browser.
    """

    print(f"Launching web GUI on http://{server}:{port} ...")
    demo = create_interface()
    demo.launch(
        server_name=server,
        server_port=port,
        share=True,
        debug=True,
        show_error=True,
    )


def list_class2d_jobs():
    """
    List RELION Class2D job directories under ./Class2D.

    A "job" is defined as a directory whose name starts with "job", e.g. job001.

    Returns
    -------
    list[str]
        Sorted list of job directory names (not full paths).
        Returns [] if ./Class2D does not exist.
    """
    import os

    if not os.path.isdir("Class2D"):
        return []
    jobs = []
    for name in sorted(os.listdir("Class2D")):
        p = os.path.join("Class2D", name)
        if os.path.isdir(p) and name.startswith("job"):
            jobs.append(name)
    return jobs

def find_final_iteration(classPath):
    """
    Determine the final (maximum) RELION iteration for a given Class2D job.

    RELION writes per-iteration STAR files like:
      Class2D/job001/run_it003_data.star

    This function glob-matches run_it*_data.star, filters to files that strictly match
    the expected naming pattern, and returns the largest iteration number.

    Parameters
    ----------
    classPath : str
        Job directory name (e.g. "job001") OR relative path under "Class2D".
        The code assumes iteration files are in: ./Class2D/<classPath>/

    Returns
    -------
    int
        Maximum iteration number found (e.g. 3).

    Raises
    ------
    ValueError
        If no valid iteration STAR files are found.
    """
    import glob, re, os

    iterationStarFiles = glob.glob(os.path.join("Class2D", classPath, "run_it*_data.star"))
    iterationStarFiles = [f for f in iterationStarFiles if re.search(r"run_it\d+_data\.star$", f)]
    if not iterationStarFiles:
        raise ValueError(f"No valid iteration files found in {os.path.join('Class2D', classPath)}")
    maxIterationStarFile = max(
        iterationStarFiles, key=lambda x: int(re.search(r"run_it(\d+)_", x).group(1))
    )
    return int(re.search(r"run_it(\d+)_", maxIterationStarFile).group(1))


def load_class2d_data(job):
    """
    Load class-average images and per-class metadata for a RELION Class2D job.

    Reads:
      - run_it###_classes.mrcs : stack of class average images
      - run_it###_model.star   : contains per-class metadata like resolution and distribution
      - run_it###_data.star    : particles STAR (used here to compute absolute particle counts)

    The returned gallery items are RGB uint8 arrays suitable for Gradio Gallery `type="numpy"`.

    Parameters
    ----------
    job : str
        Job directory name under ./Class2D (e.g. "job001").

    Returns
    -------
    tuple
        (items, particlesStarPath, maxIter, status)

        items : list[tuple[np.ndarray, str]]
            Each item is (image_rgb_uint8, caption).
            `image_rgb_uint8` has shape (H, W, 3), dtype uint8.

        particlesStarPath : str | None
            Path to the final iteration particles STAR file (run_it###_data.star).
            Used later for exporting subsets.

        maxIter : int | None
            Final iteration number discovered for this job.

        status : str
            Human-readable status for UI display. Includes errors if job is invalid.

    Notes
    -----
    - Images are "bulletproof normalized" so broken/constant images still display.
    - Captions use a 1-based class label ("Class 1") but selection indices remain 0-based.
    """    
    import os, starfile, mrcfile
    import numpy as np

    # Validate the requested job name against existing Class2D job directories
    available_jobs = list_class2d_jobs()
    if job not in available_jobs:
        return [], None, None, f"Invalid Class Job: Class2D/{job}\nAvailable: {available_jobs}"

    # Construct a normalized, validated path under the Class2D directory
    class2d_root = os.path.abspath("Class2D")
    job_dir = os.path.normpath(os.path.join(class2d_root, job))

    # Ensure the resolved job directory is still within the Class2D root (prevent traversal/absolute paths)
    try:
        if os.path.commonpath([class2d_root, job_dir]) != class2d_root:
            return [], None, None, f"Invalid Class Job directory outside Class2D root: {job}"
    except ValueError:
        # Raised by commonpath on different drives or invalid paths
        return [], None, None, f"Invalid Class Job directory on disk: {job}"

    # Check that the job directory exists
    if not os.path.isdir(job_dir):
        return [], None, None, f"Invalid Class Job directory on disk: {job_dir}"

    maxIter = find_final_iteration(job)
    dataset = mrcfile.read(os.path.join(job_dir, f"run_it{maxIter:03d}_classes.mrcs"))

    resultsStarFile = starfile.read(os.path.join(job_dir, f"run_it{maxIter:03d}_model.star"))
    particlesStarPath = os.path.join(job_dir, f"run_it{maxIter:03d}_data.star")
    particlesStarFile = starfile.read(particlesStarPath)
    nParticles = particlesStarFile["particles"].shape[0]

    items = []
    for i in range(dataset.shape[0]):
        img = dataset[i]

        # bulletproof normalize
        den = float(img.max() - img.min())
        if den <= 0 or not np.isfinite(den):
            img_uint8 = np.zeros_like(img, dtype=np.uint8)
        else:
            img_norm = (img - img.min()) / den
            img_uint8 = np.clip(img_norm * 255, 0, 255).astype(np.uint8)

        # stable display: 3-channel uint8
        arr = np.stack([img_uint8, img_uint8, img_uint8], axis=-1)

        resolution = round(resultsStarFile["model_classes"]["rlnEstimatedResolution"][i], 2)
        n_particles = int(resultsStarFile["model_classes"]["rlnClassDistribution"][i] * nParticles)
        label = f"Class {i+1} | {n_particles} ptcls | {resolution} Å"

        items.append((arr, label))

    status = f"✅ Loaded {len(items)} classes from iteration {maxIter}"
    return items, particlesStarPath, maxIter, status


def export_selected_classes(job, selected_indices, particles_star_path):
    """
    Export particles belonging to selected 2D classes via py2rely/pipeliner pipeline utilities.

    This uses the SlabAveragePipeline helpers to:
      - initialize selection + classification context
      - point the selection job at the chosen Class2D output directory
      - subset-select particles belonging to the chosen classes
      - write a particles.star file in the selection job output directory

    Parameters
    ----------
    job : str
        Job directory name under ./Class2D (e.g. "job001").
    selected_indices : list[int]
        0-based class indices (e.g. [0, 2, 4]).
        IMPORTANT: These are kept 0-based to match the existing PyQt workflow.
    particles_star_path : str
        Path to run_it###_data.star corresponding to the final iteration.

    Returns
    -------
    str
        Human-readable status string for UI display.
    """   
    from py2rely.slabs.pipeline import SlabAveragePipeline as pipeline
    from pipeliner.api.manage_project import PipelinerProject
    import os

    if not particles_star_path:
        return "❌ Please load data first!"
    if not selected_indices:
        return "❌ No classes selected!"

    try:
        my_project = PipelinerProject(make_new_project=True)
        utils = pipeline(my_project)
        utils.read_json_directories_file("output_directories.json")

        # Keep 0-based indices (matches your PyQt version)
        selected_classes = list(selected_indices)

        utils.initialize_selection()
        utils.initialize_classification()
        utils.class2D_job.output_dir = os.path.join("Class2D", job)
        utils.tomo_select_job.joboptions["fn_data"].value = particles_star_path
        utils.tomo_select_job.joboptions["select_minval"].value = selected_classes[0]
        utils.tomo_select_job.joboptions["select_maxval"].value = selected_classes[0]

        utils.run_subset_select(keepClasses=selected_classes, classPath=particles_star_path)

        output_path = os.path.join(utils.tomo_select_job.output_dir, "particles.star")
        return f"✅ Exported {len(selected_classes)} classes → {output_path}"

    except Exception as e:
        return f"❌ Error exporting: {e}"

def create_interface():
    """
    Build and return the Gradio Blocks UI.

    UI features:
      - Job dropdown populated from ./Class2D
      - "Load Classes" button to populate galleries
      - Two gallery modes:
          (fast) no preview pane
          (preview) Gradio preview enabled
      - Tile selection toggling:
          adds "✅" prefix in caption
          stores selected indices as comma-separated 0-based integers
          displays selected classes as 1-based integers for user friendliness
      - "Export Selected Classes" button to write out particles.star

    Returns
    -------
    gr.Blocks
        A fully wired Gradio demo ready to `.launch()`.
    """
    try:    
        import gradio as gr
    except ImportError:
        raise ImportError("Gradio is required for the web GUI. Please install it via 'pip install py2rely[web]'.")
    import os

    with gr.Blocks(title="Class2D Selector") as demo:

        particles_star_path_store = gr.Textbox(value="", visible=False)  # stores particlesStarPath
        max_iter_store = gr.Textbox(value="", visible=False)             # optional; store as text

        gr.Markdown("# Class2D Image Selector")
        gr.Markdown("Click tiles to toggle selection. Selected tiles get a ✅ in the caption.")

        with gr.Row():
            job_input = gr.Dropdown(
                label="Job Name",
                choices=list_class2d_jobs(),
                value=(list_class2d_jobs()[0] if list_class2d_jobs() else None),
                allow_custom_value=True,
            )

            with gr.Column(scale=0):
                load_btn = gr.Button("Load Classes", variant="primary")
                preview_toggle = gr.Button("Preview: OFF")

        def refresh_job_choices():
            jobs = list_class2d_jobs()
            return gr.update(choices=jobs, value=(jobs[0] if jobs else None))

        status_output = gr.Textbox(label="Status", interactive=False)

        gallery_fast = gr.Gallery(
            label="Classes (fast)",
            columns=5, rows=3, height="auto",
            object_fit="contain",
            allow_preview=False,
            type="numpy",
            visible=True,
        )

        gallery_preview = gr.Gallery(
            label="Classes (preview)",
            columns=5, rows=3, height="auto",
            object_fit="contain",
            allow_preview=True,
            type="numpy",
            visible=False,
        )

        # --- Preview toggle handler with color change ---
        def toggle_preview(button_label):
            preview_on = (button_label == "Preview: ON")

            if preview_on:
                # turn preview OFF
                return (
                    gr.update(visible=True),    # gallery_fast
                    gr.update(visible=False),   # gallery_preview
                    gr.update(
                        value="Preview: OFF",
                        variant="secondary",    # gray
                    ),
                )
            else:
                # turn preview ON
                return (
                    gr.update(visible=False),   # gallery_fast
                    gr.update(visible=True),    # gallery_preview
                    gr.update(
                        value="Preview: ON",
                        variant="primary",      # green
                    ),
                )

        preview_toggle.click(
            fn=toggle_preview,
            inputs=[preview_toggle],
            outputs=[gallery_fast, gallery_preview, preview_toggle],
            show_progress="hidden",
        )

        selected_display = gr.Textbox(label="Selected Classes", interactive=False)

        # Hidden store: comma-separated 0-based indices, e.g. "0,2,4"
        selected_store = gr.Textbox(value="", visible=False)

        export_btn = gr.Button("Export Selected Classes", variant="primary")
        export_status = gr.Textbox(label="Export Status", interactive=False)

        # --- Load ---
        def load_handler(job):
            items, particles_path, max_iter, status = load_class2d_data(job)
            return items, items, str(particles_path or ""), str(max_iter or ""), status, "", ""

        load_btn.click(
            fn=load_handler,
            inputs=[job_input],
            outputs=[
                gallery_fast,
                gallery_preview,
                particles_star_path_store,
                max_iter_store,
                status_output,
                selected_store,
                selected_display,
            ],
            show_progress="hidden",
        )

        # --- Toggle selection ---
        def toggle_selection(current_gallery, store, evt: gr.SelectData):
            store = store or ""
            selected = set()
            if store.strip():
                selected = {int(x) for x in store.split(",") if x.strip() != ""}

            idx = int(evt.index)
            if idx in selected:
                selected.remove(idx)
            else:
                selected.add(idx)

            selected_sorted = sorted(selected)

            new_items = []
            for i, (img, label) in enumerate(current_gallery or []):
                base_label = label
                if base_label.startswith("✅ "):
                    base_label = base_label[2:].lstrip()
                if i in selected:
                    base_label = "✅ " + base_label
                new_items.append((img, base_label))

            pretty = ",".join(str(i + 1) for i in selected_sorted)
            new_store = ",".join(str(i) for i in selected_sorted)

            # return updated gallery items for BOTH galleries
            return new_items, new_items, new_store, pretty

        # --- Connect both galleries to the same selection handler ---
        gallery_fast.select(
            fn=toggle_selection,
            inputs=[gallery_fast, selected_store],
            outputs=[gallery_fast, gallery_preview, selected_store, selected_display],
            show_progress="hidden",
        )

        gallery_preview.select(
            fn=toggle_selection,
            inputs=[gallery_preview, selected_store],
            outputs=[gallery_fast, gallery_preview, selected_store, selected_display],
            show_progress="hidden",
        )

        # --- Export ---
        def export_handler(job, store, particles_path):
            if not particles_path or not particles_path.strip():
                return "❌ Please load data first!"
            if not store or not store.strip():
                return "❌ No classes selected!"

            selected = [int(x) for x in store.split(",") if x.strip() != ""]
            return export_selected_classes(job, selected, particles_path)

        # --- Connect export button ---
        export_btn.click(
            fn=export_handler,
            inputs=[job_input, selected_store, particles_star_path_store],  # <-- changed
            outputs=[export_status],
            show_progress="hidden",
        )

    return demo
