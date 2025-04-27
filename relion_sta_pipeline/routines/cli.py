from relion_sta_pipeline.routines.extract_subtomo import extract_subtomo, extract_subtomo_slurm
from relion_sta_pipeline.routines.class3d import class3d, class3d_slurm
from relion_sta_pipeline.routines.refine import refine3d, refine3d_slurm
from relion_sta_pipeline.routines.reconstruct import (
    reconstruct_particle, reconstruct_particle_slurm, 
    mask_post_process, create_mask_and_post_process
)
import click

@click.group()
def routines():
    """Routines for relion_sta_pipeline."""
    pass

# Add subcommands to the group
routines.add_command(class3d)
routines.add_command(class3d_slurm)
routines.add_command(refine3d)
routines.add_command(refine3d_slurm)
routines.add_command(reconstruct_particle)
routines.add_command(reconstruct_particle_slurm)
routines.add_command(mask_post_process)
routines.add_command(extract_subtomo)
routines.add_command(extract_subtomo_slurm)

if __name__ == "__main__":
    routines()