from pyrelion.slabs.class2D import slab_average, auto_class_ranker
from pyrelion.slabs.slurm import submit_class2d, submit_slabpick
import click

@click.group()
def slab():
    """Run Jobs to Execute 2D Class Averaging on Slabs."""
    pass

slab.add_command(slab_average)
slab.add_command(auto_class_ranker) 

@click.group(name='slab')
def slab_slurm():
    """Run Jobs to Execute 2D Class Averaging on Slabs on Slurm."""
    pass

slab_slurm.add_command(submit_class2d)
slab_slurm.add_command(submit_slabpick)

if __name__ == "__main__":
    slab()