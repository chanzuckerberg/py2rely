from py2rely.prepare.particles import (
    import_particles,
    import_pytom_particles,
    particles,
    combine_particles,
)
from py2rely.prepare.tilt_series import (
    tilt_series,
    combine_tilt_series,
    filter_unused_tilts,
)
from py2rely.prepare.generate_parameters import (
    relion5_parameters,
    relion5_pipeline,
)
from py2rely.prepare.template import create_template
import click

@click.group()
def prepare():
    """Commands for preparing/importing data from aretomo and copick."""
    pass

# Add subcommands to the group
prepare.add_command(import_particles)
# prepare.add_command(import_pytom_particles)
prepare.add_command(particles)
prepare.add_command(combine_particles)
prepare.add_command(tilt_series)
prepare.add_command(combine_tilt_series)
prepare.add_command(relion5_parameters)
prepare.add_command(relion5_pipeline)
prepare.add_command(filter_unused_tilts)
prepare.add_command(create_template)

if __name__ == "__main__":
    prepare()