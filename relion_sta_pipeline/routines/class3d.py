from pipeliner.api.manage_project import PipelinerProject
from relion_sta_pipeline.utils import relion5_tools
import pipeliner.job_manager as job_manager
import json, click, starfile, os, mrcfile

@click.group()
@click.pass_context
def cli(ctx):
    pass

def class3d_options(func):
    """Decorator to add shared options for class3d commands."""
    options = [
        @click.option("--parameter-path",type=str,required=True,default="sta_parameters.json",
                      help="Sub-Tomogram Refinement Parameter Path",)
        @click.option("--particles-path",type=str,required=True,
                      help="Path to Particles")
        @click.option("--reference-path",type=str,required=True,
                      help="Path to Reference for Classification")
        @click.option("--mask-path",type=str,required=False,default=None,
                      help="Path of Mask for Classification")
        @click.option("--ini-high",type=float,required=False,default=None,
                      help="Low-Pass Filter to Apply to Model")
        @click.option("--tau-fudge",type=float,required=False,default=3,
                      help="Tau Regularization Parameter for Classification")
        @click.option("--nr-classes",type=int,required=False,default=3,
                      help="Number of Classes for Classificaiton")
        @click.option("--nr-iter",type=int,required=False,default=None,
                      help="Number of Iterations")
        @click.option("--ref-correct-greyscale",type=bool,required=False,default=True,
                      help="Reference Map is on Absolute Greyscale?")
        @click.option("--tomogram-path",type=str,required=False,default=None,
                      help="Path to CtfRefine or Polish tomograms StarFile (e.g., CtfRefine/job010)")
    ]
    for option in reversed(options):  # Add options in reverse order to preserve order in CLI
        func = option(func)
    return func  

@cli.command(context_settings={"show_default": True})
@class3d_options
def class3d(
    parameter_path: str,
    particles_path: str, 
    reference_path: str,
    mask_path: str,     
    ini_high: float,
    tau_fudge: float,
    nr_classes: int,
    nr_iter: int,
    ref_correct_greyscale: bool,
    tomogram_path: str
    ):   

    # Create Pipeliner Project
    my_project = PipelinerProject(make_new_project=True)
    utils = relion5_tools.Relion5Pipeline(my_project)
    utils.read_json_params_file(parameter_path)
    utils.read_json_directories_file('output_directories.json')

    # If a Path for Refined Tomograms is Provided, Assign it 
    if tomogram_path is not None:
        utils.set_new_tomograms_star_file(tomogram_path)    

    # Get Binning
    particlesdata = starfile.read( particles_path )
    currentBinning = int(particlesdata['optics']['rlnTomoSubtomogramBinning'].values[0])
    binIndex = utils.binningList.index(currentBinning)    

    utils.initialize_pseudo_tomos()
    utils.initialize_reconstruct_particle()
    
    # Do I want to Scale My Classification Sampling Based on Resolution?
    utils.update_resolution(binIndex)    

    # 3D Refinement Job and Update Input Parameters 
    utils.initialize_tomo_class3D() 

    # Low Pass Filter If Provided
    if ini_high is not None:  utils.tomo_class3D_job.joboptions['ini_high'].value = ini_high
    else:                     ini_high = utils.tomo_class3D_job.joboptions['ini_high'].value   

    # Apply Mask, Tau-Fudge or Number of Classes If Provided
    if tau_fudge is not None:   utils.tomo_class3D_job.joboptions['tau_fudge'].value = tau_fudge
    else:                       tau_fudge = utils.tomo_class3D_job.joboptions['tau_fudge'].value

    if nr_classes is not None:  utils.tomo_class3D_job.joboptions['nr_classes'].value = nr_classes
    else:                       nr_classes = utils.tomo_class3D_job.joboptions['nr_classes'].value

    if nr_iter is not None:     utils.tomo_class3D_job.joboptions['nr_iter'].value = nr_iter
    else:                       nr_iter = utils.tomo_class3D_job.joboptions['nr_iter'].value    

    if mask_path is not None:   utils.tomo_class3D_job.joboptions['fn_mask'].value = mask_path
    
    # Is the Reference Map Created by Relion?
    utils.tomo_class3D_job.joboptions['ref_correct_greyscale'].value = ref_correct_greyscale

    # Specify Particles and Reference MRC Volume
    utils.tomo_class3D_job.joboptions['fn_img'].value = particles_path
    utils.tomo_class3D_job.joboptions['fn_ref'].value = reference_path

    # Print Input Parameters
    utils.print_pipeline_parameters('Class 3D', Parameter_Path=parameter_path, Reference_Path=reference_path,
                                    Particles_path=particles_path, Mask_path=mask_path, tau_fudge=tau_fudge, 
                                    nr_classes=nr_classes, nr_iter=nr_iter, ini_high=ini_high)     

    # Run
    utils.run_tomo_class3D(rerunClassify=True)

@class3d_options
def class3d_submit(
    parameter_path: str, 
    particles_path: str, 
    reference_path: str, 
    mask_path: str, 
    ini_high: float, 
    tau_fudge: float, 
    nr_classes: int, 
    nr_iter: int, 
    ref_correct_greyscale: bool, 
    tomogram_path: str):

    # Create Class3D Command
    command = f"""
routines class3d \\
    --parameter-path {parameter_path} \\
    --particles-path {particles_path} \\
    --reference-path {reference_path} \\
    --ref-correct-greyscale {ref_correct_greyscale} \\
    --tomogram-path {tomogram_path}
    """

    if mask_path is not None:
        command += f" --mask-path {mask_path}"
    
    if ini_high is not None:
        command += f" --ini-high {ini_high}"

    if tau_fudge is not None:
        command += f" --tau-fudge {tau_fudge}"

    if nr_classes is not None:
        command += f" --nr-classes {nr_classes}"

    if nr_iter is not None:
        command += f" --nr-iter {nr_iter}"

    # Create Slurm Submit Script
    create_shellsubmit(
        job_name="class3d",
        output_file="class3d.out",
        shell_name="class3d.sh",
        command=command,
        num_gpus=0
    )