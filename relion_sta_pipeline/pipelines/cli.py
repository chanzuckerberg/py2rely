from relion_sta_pipeline.pipelines.bin1 import high_resolution_cli
from relion_sta_pipeline.pipelines.sta import average
import click

@click.group()
def pipelines():
    """Run Pipeline Jobs (e.g., Sub-tomo Averaging, Polishing, High-Resolution Refinement)."""
    pass

pipelines.add_command(average)
pipelines.add_command(high_resolution_cli)

if __name__ == "__main__":
    pipelines()