from py2rely.routines.extract_subtomo import extract, extract_subtomo_slurm
from py2rely.routines.reconstruct import (
    reconstruct_particle, reconstruct_particle_slurm, 
)
from py2rely.routines.refine import refine3d, refine3d_slurm
from py2rely.routines.class3d import class3d, class3d_slurm
from py2rely.routines.post_process import post_process
from py2rely.routines.mask_create import mask_create
from py2rely.routines.select import select
import rich_click as click

@click.group()
def routines():
    """Run Individual Jobs (e.g., Refine3D, Class3D, Reconstruct)."""
    pass

# Add subcommands to the group
routines.add_command(class3d)
routines.add_command(refine3d)
routines.add_command(reconstruct_particle)
routines.add_command(mask_create)
routines.add_command(post_process)
routines.add_command(extract)
routines.add_command(select)

@click.group(name="routines")
def routines_slurm():
    """Run Individual Jobs on Slurm (e.g., Refine3D, Class3D, Reconstruct)."""
    pass

# Add subcommands to the group
routines_slurm.add_command(class3d_slurm)
routines_slurm.add_command(refine3d_slurm)
routines_slurm.add_command(reconstruct_particle_slurm)
routines_slurm.add_command(extract_subtomo_slurm)

if __name__ == "__main__":
    routines()