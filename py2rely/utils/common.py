import rich_click as click


def add_sta_options(func):
    """
    Decorator to add common STA pipeline options to a Click command.
    """
    options = [
        click.option(
            "-p","--parameter",type=str,required=True,
            default='sta_parameters.json',
            help="The Saved Parameter Path" ),
        click.option(
            "-rt","--reference-template",type=str,
            required=False,default=None,
            help="Provided Template for Preliminary Refinment (Optional)" ),
        click.option(
            "-dg","--run-denovo-generation",type=bool,
            required=False, default=False,
            help="Generate Initial Reconstruction with Denovo" ),
        click.option(
            "--run-class3D",type=bool,
            required=False, default=False,
            help="Run 3D-Classification Job After Refinement" ),
        click.option(
            "--extract3D","-e3d",type=bool,
            required=False, default=False,
            help="Extract 3D Particles Before Initial Model Generation" ),
        click.option(
            "--manual-masking", "-mm",type=bool,
            required=False, default=False,
            help="Apply Manual Masking After First Refinement Job" ),
    ]
    # Add options in reverse order to preserve correct order
    for option in reversed(options):  
        func = option(func)
    
    return func

def add_submitit_options(func):
    """
    Decorator to add submitit option to a Click command.
    """
    options = [
        click.option(
             "--submitit", type=bool, required=False, default=False,
            help="Submit Jobs with Submitit SLURM Interface" ),
        click.option(
            '--cpu-constraint', '-cc', type=str, default='4,16',
            help='Number of CPUs and mem-per-cpu to requested. (e.g., "4,16" for 4 CPUs and 16GB per CPU)'),
        click.option(
            '--timeout', type=int, default=48,
            help="SLURM job timeout per trial when using submitit (hours)"),
    ]
    # Add options in reverse order to preserve correct order
    for option in reversed(options):
        func = option(func)
    return func

def add_core_slurm_compute_options(func):
    """
    Decorator to add core SLURM compute options to a Click command.
    """
    options = [
        click.option("-ng", "--num-gpus", type=int, required=False, default=4,
                     help="Number of GPUs to Use for Processing",
                     callback=validate_even_gpus),
        click.option("-gc", "--gpu-constraint", required=False, default="h100",
                     help="GPU Constraint for Slurm Job",
                     callback=validate_gpu_constraint)
    ]
    for option in reversed(options):  # Add options in reverse order to preserve correct order
        func = option(func)
    return func