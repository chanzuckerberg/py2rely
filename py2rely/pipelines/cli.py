from py2rely.pipelines.polishing import polish_pipeline
from py2rely.pipelines.bin1 import high_resolution_cli
from py2rely.pipelines.sta import average
import rich_click as click

@click.group()
def pipelines():
    """Run Pipeline Jobs (e.g., Sub-tomo Averaging, Polishing, High-Resolution Refinement)."""
    pass

pipelines.add_command(average)
pipelines.add_command(high_resolution_cli)
pipelines.add_command(polish_pipeline)

if __name__ == "__main__":
    pipelines()