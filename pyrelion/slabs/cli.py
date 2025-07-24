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
        "class2D": "Run the class-averaging pipeline.",
        "visualize": "Visualize and Select classes for processing",
    }
    click.echo("Available commands:")
    for cmd, desc in commands.items():
        click.echo(f"  {cmd}: {desc}")

if __name__ == "__main__":
    cli()