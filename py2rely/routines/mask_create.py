import click

@click.group()
@click.pass_context
def cli(ctx):
    pass

def auto_mask_create(utils, low_pass):
    """
    Iteratively increases `width_mask_edge` until the phase-randomised FSC warning disappears.
    """

    # Configure mask creation
    utils.mask_create_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'merged.mrc'
    utils.mask_create_job.joboptions['lowpass_filter'].value = low_pass
    ini_mask = utils.get_reconstruction_std(utils.reconstruct_particle_job.output_dir + 'merged.mrc')
    utils.mask_create_job.joboptions['extend_inimask'].value = 0
    utils.mask_create_job.joboptions['inimask_threshold'].value = ini_mask
    utils.mask_create_job.joboptions['nr_threads'].value = 16

    # Iterate from 10 - > 50 with step of 10
    for width_edge in range(10, 50, 10):

        # Set the width_mask_edge and Run Mask Create
        utils.mask_create_job.joboptions['width_mask_edge'].value = width_edge
        utils.run_mask_create(utils.tomo_refine3D_job, None, False, rerunMaskCreate=True) 

        # Run post-process with the newly created mask
        utils.post_process_job.joboptions['fn_in'].value = utils.reconstruct_particle_job.output_dir + 'half1.mrc'
        utils.post_process_job.joboptions['fn_mask'].value = utils.mask_create_job.output_dir + 'mask.mrc'
        utils.post_process_job.joboptions['low_pass'].value = 0
        utils.run_post_process(rerunPostProcess=True)

        # Check if the warning is gone
        if not check_phase_randomised_fsc_warning(utils.post_process_job.output_dir + 'run.err'):
            print(f"Success at width_mask_edge={width_edge}")
            break

    print("Warning still present after trying all edge widths.")

def check_phase_randomised_fsc_warning(filepath):
    warning_line = "WARNING: The phase-randomised FSC is larger than 0.10 at the estimated resolution!"
    with open(filepath, 'r') as f:
        for line in f:
            if warning_line in line.strip():
                return True  # Warning is present
    return False  # No warning found

# # Mask Create + Post Process Command
# @cli.command(context_settings={"show_default": True})
# @click.option("--parameter", type=str, required=True, default="sta_parameters.json", 
#               help="Sub-Tomogram Refinement Parameter Path")
# @click.option("--input-map", type=str, required=True, 
#               help="Input Map to Create Mask From")
# @click.option()
# def mask_create(parameter: str, input_map: str):

#     run(parameter, low_pass)

# def fresh_run(parameter: str, input_map: str, low_pass: float):

#     # Create Pipeliner Project
#     my_project = PipelinerProject(make_new_project=True)
#     utils = relion5_tools.Relion5Pipeline(my_project)
#     utils.read_json_params_file(parameter)
#     utils.read_json_directories_file('output_directories.json')

# def run(utils, input_map, low_pass):

