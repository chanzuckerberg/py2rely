from py2rely.utils.progress import get_console
from rich.table import Table
from typing import Optional
import json, os

def compute_boxsize_from_project(parameter, utils, binfactor):

    # Read the Parameter File and Initialize the Reconstruct Particle Job (placeholder)
    utils.read_json_params_file(parameter)
    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()

    # Update the Box Size and Binning for Reconstruction and Pseudo-Subtomogram Averaging Job
    utils.update_job_binning_box_size(
        utils.reconstruct_particle_job, 
        utils.pseudo_subtomo_job,
        binningFactor = binfactor
    )

def set_parameters(job, inputs):
    for key, value in inputs.items():
        if value is not None:
            job.joboptions[key].value = value

def print_params( process: str, header: str = None, params: dict = None, **kwargs):
    """
    Pretty-print pipeline parameters using Rich and optionally save them to JSON.

    Args:
        process: The name of the pipeline process or step.
        header: Optional header name under which parameters will be saved in JSON.
        params: Optional dictionary of parameters to display.
        **kwargs: Arbitrary parameters. Merged with `params` if both are provided.
                  If 'file_name' is given, parameters are also saved.
    """

    console = get_console()
    file_name = kwargs.pop("file_name", None)

    # Merge params dict and kwargs, with kwargs taking precedence
    merged = {**(params or {}), **kwargs}
    json_data = {header: merged} if header else merged

    # ---- Rich summary ----
    console.rule(f"[bold cyan]{process} Parameters Summary")

    table = Table(show_header=True, header_style="bold magenta", expand=False)
    table.add_column("Parameter", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for key, value in merged.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        table.add_row(str(key), str(value))

    console.print(table)

    # ---- Save to JSON (quietly) ----
    if file_name:
        if os.path.exists(file_name):
            with open(file_name, "r") as json_file:
                existing_data = json.load(json_file)
        else:
            existing_data = {}

        existing_data.update(json_data)
        with open(file_name, "w") as json_file:
            json.dump(existing_data, json_file, indent=4)

        console.print(
            f"\n[green]Parameters saved to[/green] [b]{file_name}[/b]"
            + (f" under header [cyan]{header}[/cyan]" if header else "")
        )