from relion_sta_pipeline.prepare.particles import (
    import_particles,
    import_pytom_particles,
    gather_copick_particles,
    combine_star_files_particles,
)
from relion_sta_pipeline.prepare.tilt_series import (
    import_tilt_series,
    combine_star_files_tomograms,
    remove_unused_tomograms,
)
from relion_sta_pipeline.prepare.generate_parameters import (
    relion5_parameters,
    relion5_pipeline,
)
import click

@click.group()
def prepare():
    """Commands for preparing data in relion_sta_pipeline."""
    pass

# Add subcommands to the group
prepare.add_command(import_particles)
prepare.add_command(import_pytom_particles)
prepare.add_command(gather_copick_particles)
prepare.add_command(combine_star_files_particles)
prepare.add_command(import_tilt_series)
prepare.add_command(combine_star_files_tomograms)
prepare.add_command(relion5_parameters)
prepare.add_command(relion5_pipeline)
prepare.add_command(remove_unused_tomograms)

if __name__ == "__main__":
    prepare()