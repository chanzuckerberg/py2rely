from py2rely import cli_context
import rich_click as click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def add_class2D_options(func):
    """Decorator to add common options to a Click command."""
    options = [
        click.option("-p", "--particles", type=str, required=True, default='stack/particles_relion.star', help="Path to Extracted Particles StarFile"),
        click.option("-tau", "--tau-fudge", type=float, required=False, default=2, help="Tau Regularization Parameter for Classification"),
        click.option("-nc", "--nr-classes", type=int, required=False, default=3, help="Number of Classes for Classificaiton"),
        click.option("-alg", "--class-algorithm", required=False, default="2DEM", type=click.Choice(["2DEM", "VDAM"], case_sensitive=False), help="Specify Which Classification Algorithm to Use (2DEM or VDAM)"),
        click.option("-ni", "--nr-iter", type=int, required=False, default=None, help="Number of Iterations for Class2D"),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve correct order
        func = option(func)
    return func

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings=cli_context, name='class2d', no_args_is_help=True)
@add_class2D_options
@click.option(
    "--do-ctf-correction",
    required=False, default='no', help="Do CTF Correction on the Images",
    type=click.Choice(["yes", "no"], case_sensitive=False),
)
@click.option(
    "--ctf-intact-first-peak",
    required=False, default='no',
    help="Do CTF Correction on the Images",
    type=click.Choice(["yes", "no"], case_sensitive=False),
)
@click.option(
    "-pd", "--particle-diameter",
    type=float, required=False, default=300,
    help="Diameter of the Particles",
)
@click.option(
    "--highres-limit",
    type=float, required=False, default=-1,
    help="High Resolution Limit for Classification in Angstroms (-1 Means Use Nyquist Limit)"
)
@click.option(
    "--dont-skip-align",
    required=False, default='yes',
    type=click.Choice(["yes", "no"], case_sensitive=False),
    help="Don't Skip Alignment during classification? (If yes, then Relion will align the particles during classification)"
)
@click.option(
    "--use-gpu",
    required=False, default='yes',
    type=click.Choice(["yes", "no"], case_sensitive=False),
    help="Use GPU (Only Available when Alignment is On)"
)
@click.option(
    "--nr-threads",
    type=int, required=False, default=16,
    help="Number of Threads to Use"
)
def slab_average(
    particles: str,
    tau_fudge: float,
    nr_classes: int,
    class_algorithm: str,
    nr_iter: int,
    do_ctf_correction: str,
    ctf_intact_first_peak: str,
    particle_diameter: float,
    highres_limit: float,
    dont_skip_align: str,
    use_gpu: str,
    nr_threads: int
    ):
    """
    Run Class2D on an Extracted Minislab Particle Stack
    """
    run_class2D(
        particles, tau_fudge, nr_classes, class_algorithm, 
        nr_iter, do_ctf_correction, ctf_intact_first_peak, 
        particle_diameter, highres_limit, dont_skip_align, 
        use_gpu, nr_threads
    )

def run_class2D(
    particles: str,
    tau_fudge: float,
    nr_classes: int,
    class_algorithm: str,
    nr_iter: int,
    do_ctf_correction: str,
    ctf_intact_first_peak: str,
    particle_diameter: float,
    highres_limit: float,
    dont_skip_align: str,
    use_gpu: str,
    nr_threads: int
    ):
    """
    Run Class2D on an Extracted Minislab Particle Stack

    Args:
        particles (str): The path to the particles stack
        tau_fudge (float): The tau fudge factor
        nr_classes (int): The number of classes to use
        class_algorithm (str): The classification algorithm to use
        nr_iter (int): The number of iterations to run
        do_ctf_correction (str): Whether to do CTF correction
        ctf_intact_first_peak (str): Whether to keep the first peak of the CTF
        particle_diameter (float): The particle diameter in Angstroms
        highres_limit (float): The high resolution limit in Angstroms
        dont_skip_align (str): Whether to skip alignment
        use_gpu (str): Whether to use GPU
        nr_threads (int): The number of threads to use
    """
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.slabs.pipeline import SlabAveragePipeline

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = SlabAveragePipeline(my_project)
    utils.read_json_directories_file('output_directories.json')

    # Initialize Classification
    utils.initialize_classification(class_algorithm, nr_iter)
    utils.class2D_job.joboptions['fn_img'].value = particles 

    # Set the Class2D Parameters
    utils.class2D_job.joboptions['tau_fudge'].value = tau_fudge
    utils.class2D_job.joboptions['nr_classes'].value = nr_classes     
    utils.class2D_job.joboptions['do_ctf_correction'].value = do_ctf_correction
    utils.class2D_job.joboptions['ctf_intact_first_peak'].value = ctf_intact_first_peak
    utils.class2D_job.joboptions['particle_diameter'].value = particle_diameter
    utils.class2D_job.joboptions['highres_limit'].value = highres_limit
    
    # Check if Alignment is On and GPU is On
    utils.class2D_job.joboptions['dont_skip_align'].value = dont_skip_align
    if dont_skip_align == 'no' and use_gpu == 'yes':
        raise click.BadParameter("Alignment must be on when using GPU")
    utils.class2D_job.joboptions['use_gpu'].value = use_gpu

    # Assign the number of threads to use
    utils.class2D_job.joboptions['nr_threads'].value = nr_threads

    # Run the Class2D Job
    utils.run_class2D()

################################################################################

# Create the boilerplate JSON file with a default file path
@cli.command(context_settings=cli_context)
@click.option(
    "--parameter-path",
    type=str, required=True,
    default='class_average_parameters.json',
    help="The JSON File Containing the Pipeline Parameters",
)
@click.option(
    "--min-class-job",
    type=int, required=True, default=1,
    help="The minimum class job number (starting point for bootstrapping)",
)
@click.option(
    "--max-class-job",
    type=int, required=True, default=25,
    help="The maximum class job number (end point for bootstrapping)",
)
@click.option(
    "--rank-threshold",
    type=float, required=False, default=0.5,
    help="Threshold for determining 'real' classes based on score",
)
def auto_class_ranker(
    parameter_path: str, 
    min_class_job: int,
    max_class_job: int,
    rank_threshold: float
    ):
    """
    Run the Class Ranker on a Range of Class2D Jobs

    Args:
        parameter_path (str): The path to the parameter file
        min_class_job (int): The minimum class job number
        max_class_job (int): The maximum class job number
        rank_threshold (float): The threshold for determining 'real' classes
    """
    run_auto_class_ranker(parameter_path, min_class_job, max_class_job, rank_threshold)

def run_auto_class_ranker(
    parameter_path: str, 
    min_class_job: int,
    max_class_job: int,
    rank_threshold: float
    ):
    from pipeliner.api.manage_project import PipelinerProject
    from py2rely.slabs.pipeline import SlabAveragePipeline
    import numpy as np
    import starfile

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = SlabAveragePipeline(my_project)

    # Load pipeline parameters and output directories from JSON files
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # Read Base Particles DataFrame for BoostStrapping
    initial_class_job = f'job{min_class_job:03d}'
    max_iter = utils.find_final_iteration(initial_class_job)  
    class_inputs = starfile.read(f'Class2D/{initial_class_job}/job.star')
    master_dataframe = starfile.read(class_inputs['joboptions_values'].iloc[13]['rlnJobOptionValue'])['particles']
    nParticles = master_dataframe.shape[0]

    # Initialize the auto-selection model for ranking classes
    utils.initialize_auto_selection() 
    utils.auto_select_job.joboptions['rank_threshold'].value = rank_threshold

    # Initialize arrays to store the average score and correct classification count for each particle
    average_score = np.zeros(nParticles); correct_count = np.zeros(nParticles)
    
    # Iterate over each class job within the range (bootstrap iterations)
    for ii in range(min_class_job, max_class_job + 1):
        
        print(f'Running Class Ranker on Class3D/Job{ii:03d}')

        # Load the model for the current class job and run the class ranker
        utils.auto_select_job.joboptions['fn_model'].value = f'Class2D/job{ii:03d}/run_it{max_iter:03d}_optimiser.star'
        utils.run_auto_select(selectStep = f'iter{ii:03d}')

        # Extract ClassRanker Score and Append to Results Count
        particle_results = starfile.read(utils.auto_select_job.output_dir + 'rank_data.star')['particles']
        class_results = starfile.read(utils.auto_select_job.output_dir + 'rank_model.star')

        # Iterate Through All Particles By ParticleID to evaluate the classification score
        for jj in range(nParticles):

            class_num = particle_results.iloc[jj]['rlnClassNumber']
            class_score = class_results.iloc[class_num-1]['rlnClassScore']

            # Accumulate the average score across bootstrap iterations
            average_score[jj] += class_score
            
            # Count how many times this particle was classified into a "real" class
            if class_score > rank_threshold:
                correct_count[jj] += 1
        
    # Average the score based on the number of trials (bootstrap iterations)
    n_trials = max_class_job - min_class_job + 1
    average_score /= n_trials

    master_dataframe['rlnAverageScore'] = average_score
    master_dataframe['rlnCorrectCount'] = correct_count
    starfile.write(master_dataframe, 'class_ranker_results.star')    
  

if __name__ == "__main__":
    cli()
