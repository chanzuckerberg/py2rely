from relion_sta_pipeline.routines.class3d import class3d
from relion_sta_pipeline.routines.refine import refine3d
from relion_sta_pipeline.routines.reconstruct import (
    reconstruct_particle, mask_post_process, create_mask_and_post_process
)
import click

@click.group()
def routines():
    """Routines for relion_sta_pipeline."""
    pass

# Add subcommands to the group
routines.add_command(class3d)
routines.add_command(refine3d)
routines.add_command(reconstruct_particle)
routines.add_command(mask_post_process)
routines.add_command(create_mask_and_post_process)
routines.add_command(slurm_pipeline)
routines.add_command(relion5_parameters)

if __name__ == "__main__":
    routines()