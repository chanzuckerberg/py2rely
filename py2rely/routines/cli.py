from py2rely.routines.extract_subtomo import extract_subtomo, extract_subtomo_slurm
from py2rely.routines.reconstruct import (
    reconstruct_particle, reconstruct_particle_slurm, 
    mask_post_process, create_mask_and_post_process
)
from py2rely.routines.refine import refine3d, refine3d_slurm
from py2rely.routines.class3d import class3d, class3d_slurm
from py2rely.routines.select import select, select_slurm
from py2rely.routines.post_process import post_process
from py2rely.routines.report import box_sizes
import rich_click as click

@click.group()
def routines():
    """Run Individual Jobs (e.g., Refine3D, Class3D, Reconstruct)."""
    pass

# Add subcommands to the group
routines.add_command(class3d)
routines.add_command(refine3d)
routines.add_command(reconstruct_particle)
routines.add_command(mask_post_process)
routines.add_command(post_process)
routines.add_command(extract_subtomo)
routines.add_command(select)
routines.add_command(box_sizes)

@click.group(name="routines")
def routines_slurm():
    """Run Individual Jobs on Slurm (e.g., Refine3D, Class3D, Reconstruct)."""
    pass

# Add subcommands to the group
routines_slurm.add_command(class3d_slurm)
routines_slurm.add_command(refine3d_slurm)
routines_slurm.add_command(reconstruct_particle_slurm)
routines_slurm.add_command(extract_subtomo_slurm)
routines_slurm.add_command(select_slurm)

if __name__ == "__main__":
    routines()