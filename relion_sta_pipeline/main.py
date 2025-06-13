from relion_sta_pipeline.routines.cli import routines_slurm as subroutines_slurm
from relion_sta_pipeline.routines.cli import routines as subroutines
from relion_sta_pipeline.utils.converters import converters
from relion_sta_pipeline.pipelines.cli import pipelines
from relion_sta_pipeline.routines.export import export 
from relion_sta_pipeline.prepare.cli import prepare
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

@click.group()
def slurm_routines():
    """Slurm CLI for pyRelion."""
    pass

# slurm_routines.add_command(high_resolution_slurm)
slurm_routines.add_command(subroutines_slurm)

if __name__ == "__main__":
    cli()
