import rich_click as click

def add_optics_options(func):
    """Decorator to add common options to a Click command."""
    options = [
        click.option("-v", "--voltage", type=float, default=300, help="Microscope Acceleration Voltage (kV)"),
        click.option("-sa", "--spherical-aberration", type=float, default=2.7, help="Estimated Microscope Aberrations (mm)"),
        click.option("-ac", "--amplitude-contrast", type=float, default=0.07, help="Microscope Amplitude Contrast"),
        click.option("-og", "--optics-group", type=int, default=1, help="Optics Group"),
        click.option("-ogn", "--optics-group-name", type=str, default="opticsGroup1", help="Optics Group Name"),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve correct order
        func = option(func)
    return func

def add_common_options(func):
    """Decorator to add common options to a Click command."""
    options = [
        click.option("-x", "--x", type=float, default=4096, help="Box size along x-axis in the picked tomogram"),
        click.option("-y", "--y", type=float, default=4096, help="Box size along y-axis in the picked tomogram"),
        click.option("-z", "--z", type=float, default=1200, help="Box size along z-axis in the picked tomogram"),
        click.option("-ps", "--pixel-size", type=float, default=1.54, help="Tilt Series Pixel Size (Å)"),
    ]
    for option in reversed(options):  # Add options in reverse order to preserve correct order
        func = option(func)
    return func

def create_optics_metadata(pixel_size, voltage, spherical_aberration, amplitude_contrast, optics_group, optics_group_name):
    """Create optics metadata dictionary."""
    return {
        'rlnOpticsGroup': optics_group,
        'rlnOpticsGroupName': optics_group_name,
        'rlnSphericalAberration': spherical_aberration,
        'rlnVoltage': voltage,
        'rlnAmplitudeContrast': amplitude_contrast,
        'rlnTomoTiltSeriesPixelSize': [pixel_size],
    }

def process_coordinates(input_df, x, y, z, pixel_size):
    """Process coordinates by centering and scaling."""
    input_df["rlnCenteredCoordinateXAngst"] = (input_df["rlnCoordinateX"] - x / 2) * pixel_size
    input_df["rlnCenteredCoordinateYAngst"] = (input_df["rlnCoordinateY"] - y / 2) * pixel_size
    input_df["rlnCenteredCoordinateZAngst"] = (input_df["rlnCoordinateZ"] - z / 2) * pixel_size
    input_df["rlnTomoName"] = input_df["rlnTomoName"].str.replace("_Vol", "")
    input_df["rlnOpticsGroup"] = 1
    return input_df
