import rich_click as click
from py2rely import cli_context
from py2rely import groups  # imported for rich-click configuration / option grouping

from py2rely.config import config_cli
from py2rely.routines.cli import routines_slurm as subroutines_slurm
from py2rely.routines.cli import routines as subroutines
from py2rely.utils.converters import converters
from py2rely.pipelines.cli import pipelines
from py2rely.routines.export import export
from py2rely.prepare.cli import prepare
from py2rely.slabs.cli import slab, slab_slurm


@click.group(context_settings=cli_context)
def routines():
    " py2rely - The Python Execution of Sub-Tomogram Refinement"
    pass

routines.add_command(prepare)
routines.add_command(subroutines)
routines.add_command(export)
routines.add_command(converters)
routines.add_command(pipelines)
routines.add_command(slab)
routines.add_command(config_cli())

@click.group(context_settings=cli_context)
def slurm_routines():
    """Slurm CLI for py2rely."""
    pass

slurm_routines.add_command(subroutines_slurm)
slurm_routines.add_command(slab_slurm)
