from py2rely import cli_context
import rich_click as click
from typing import List

@click.group()
@click.pass_context
def cli(ctx):
    pass

def add_select_options(func):
    """Decorator to add common options to a Click command."""
    options = [
        click.option("-p", "--particles", type=str, required=True, help="Path to particles StarFile"),
        click.option("-c", "--classes", type=str, required=True, help="Comma-separated 1-based class numbers to keep (e.g. '1,3,5')"),
        click.option("-o", "--output", type=str, required=False, default=None, help="Output path for selected particles.star. If omitted, runs via RELION pipeliner and appends to job history."),
    ]
    for option in reversed(options):
        func = option(func)
    return func

@cli.command(context_settings=cli_context, no_args_is_help=True)
@add_select_options
def select(particles: str, classes: str, output: str):
    """Select particles belonging to specified classes from a 2D or 3D classification."""
    selected_classes = [int(x) for x in classes.split(',') if x.strip()]
    run_select(particles, selected_classes, output)


def run_select(particles: str, classes: List[int], output: str = None) -> str:
    """
    Filter particles to keep only those belonging to the specified classes.

    Parameters
    ----------
    particles : str
        Path to run_it###_data.star.
    classes : List[int]
        Class indices to keep (e.g. [1, 3, 5]).
    output : str or None
        Destination path for the filtered particles.star. If None, runs via
        RELION pipeliner and writes into the Select job directory.

    Returns
    -------
    str
        Path to the output particles.star.
    """
    if output:
        output_path = _local_call(particles, classes, output)
    else:
        output_path = _relion_call(particles, classes)

    print(f"✅ Exported {len(classes)} classes → {output_path}")
    return output_path


def _local_call(particles_fname: str, classes: List[int], output: str) -> str:
    """Filter a particles STAR file and write to an explicit output path."""
    import starfile

    particles_data = starfile.read(particles_fname)
    keys = particles_data.keys()
    # filter classes by class number
    selected_particles = particles_data['particles'][
        particles_data['particles']['rlnClassNumber'].isin(classes)
    ]

    out_df = {}
    if 'general' in keys:
        out_df['general'] = particles_data['general']
    out_df['optics'] = particles_data['optics']
    out_df['particles'] = selected_particles

    starfile.write(out_df, output)
    return output


def _relion_call(particles: str, classes: List[int]) -> str:
    """Run subset selection via RELION pipeliner, appending a Select job to history."""
    from py2rely.utils.sta_tools import PipelineHelper as pipeline
    from py2rely.routines.helper import get_bin_factor
    from pipeliner.api.manage_project import PipelinerProject
    import os, starfile

    # Initialize the pipeliner project
    my_project = PipelinerProject(make_new_project=True)
    utils = pipeline(my_project)
    utils.read_json_directories_file("output_directories.json")

    # Print the progress
    print(f'Extracting Classes ({classes}) from {particles}...')

    # Get the BinFactor from the particles starfile
    utils.binning = get_bin_factor(particles)

    # Initialize the selection and run
    utils.initialize_selection()
    utils.tomo_select_job.joboptions["fn_data"].value = particles
    utils.tomo_select_job.joboptions["select_minval"].value = classes[0]
    utils.tomo_select_job.joboptions["select_maxval"].value = classes[0]
    utils.run_subset_select(keepClasses=None, rerunSelect=True)

    # Manually filter the particles with local call
    output_path = os.path.join(utils.tomo_select_job.output_dir, "particles.star")
    _local_call(particles, classes, output_path)
    return output_path


if __name__ == "__main__":
    cli()
