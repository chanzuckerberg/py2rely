import starfile, click

@click.command()
@click.option('--original-fname', type=str, required=True, 
    help='Path to the original star file.')
@click.option('--new-fname', type=str, required=True, 
    help='Path to the new star file.')
def convert_ts_to_position(
    original_fname: str, 
    new_fname: str):
    """
    Converts tomography names in a STAR file:
    1. Replace 'TS_' with 'Position_'.
    2. Remove '_1' if it is at the end of the string.

    Args:
        original_fname (str): Path to the original STAR file.
        new_fname (str): Path to the new STAR file to save the updated data.
    """    
    
    # Read the original STAR file
    particles = starfile.read(original_fname)

    # Apply the transformations
    particles['particles']['rlnTomoName'] = particles['particles']['rlnTomoName'].str.replace('TS_', 'Position_')
    particles['particles']['rlnTomoName'] = particles['particles']['rlnTomoName'].str.replace(r'_1$', '', regex=True)
    
    # Write the updated STAR file
    # import pdb; pdb.set_trace()
    starfile.write(particles, new_fname)

def cli():
    convert_ts_to_position()