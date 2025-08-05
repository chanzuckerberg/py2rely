from pyrelion.routines.cli import routines_slurm as subroutines_slurm
from pyrelion.routines.cli import routines as subroutines
from pyrelion.utils.converters import converters
from pyrelion.pipelines.cli import pipelines
from pyrelion.routines.export import export 
from pyrelion.prepare.cli import prepare
from pyrelion.slabs.cli import slab, slab_slurm
import click

@click.group()
def routines():
    " pyRelion - The Python Execution of Sub-Tomogram Refinement"
    pass

routines.add_command(prepare)
routines.add_command(subroutines)
routines.add_command(export)
routines.add_command(converters)
routines.add_command(pipelines)
routines.add_command(slab)

@click.group()
def slurm_routines():
    """Slurm CLI for pyRelion."""
    pass

slurm_routines.add_command(subroutines_slurm)
slurm_routines.add_command(slab_slurm)

if __name__ == "__main__":
    cli()
