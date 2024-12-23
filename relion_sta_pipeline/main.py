import click

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Main entry point for the relion_sta_pipeline."""
    if ctx.invoked_subcommand is None:
        list_commands()

@cli.command()
def list_commands():
    """List all available CLI commands."""
    commands = {
        "create": "Generate parameters or shell submissions for the pipeline.",
        "prepare_relion5": "Prepare input files for Relion5.",
        "run_relion5": "Run the Relion5 pipeline.",
        "classes": "Select classes for processing.",
        "process": "Run individual Processes in the STA pipeline (e.g., Refine3D, Class3D, Reconstrut Particle)",
        "report": "Generate reports from the pipeline.",
    }
    click.echo("Available commands:")
    for cmd, desc in commands.items():
        click.echo(f"  {cmd}: {desc}")

if __name__ == "__main__":
    cli()
