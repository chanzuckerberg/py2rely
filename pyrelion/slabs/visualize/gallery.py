from matplotlib.backends.backend_pdf import PdfPages
import mrcfile, os, starfile, math
import matplotlib.pyplot as plt
import numpy as np

def class_average_gallery(stack_path: str, 
                          image_size: int = 2, 
                          images_per_row: int = 5, 
                          rows_per_page: int = 5):

    # Load the stack
    stack = mrcfile.read(stack_path)
    num_images = stack.shape[0]

    # Load Statistics Associated with Class Averages
    data_path = stack_path.replace('classes.mrcs', 'data.star')
    dataStarFile = starfile.read(data_path)
    nParticles = dataStarFile['particles'].shape[0]

    model_path = stack_path.replace('classes.mrcs', 'model.star')
    modelStarFile = starfile.read(model_path)
    particle_count_list = [ f"{math.ceil(modelStarFile['model_classes']['rlnClassDistribution'][i] * nParticles)} Particles" for i in range(num_images) ]      
    resolution_list = [f"{round(modelStarFile['model_classes']['rlnEstimatedResolution'][i],2)} A" for i in range(num_images)]  

    # Create a PDF to save the gallery
    output_pdf_path = "image_gallery.pdf"

    # Replace the file name in stack_path with output_pdf_filename
    stack_dir = os.path.dirname(stack_path)  # Get the directory of stack_path
    output_pdf_path = os.path.join(stack_dir,  "image_gallery.pdf")  # Append the new file name

    images_per_page = images_per_row * rows_per_page
    with PdfPages(output_pdf_path) as pdf:
        
        num_pages = (num_images + images_per_page - 1) // images_per_page
        
        for page in range(num_pages):
            fig, axes = plt.subplots( rows_per_page, images_per_row, 
                                      figsize=(images_per_row * image_size, rows_per_page * image_size) )
            axes = axes.flatten()  # Flatten to easily iterate over axes
            
            for i, ax in enumerate(axes):
                image_idx = page * images_per_page + i
                if image_idx < num_images:

                    num_particles = particle_count_list[image_idx]
                    resolution = resolution_list[image_idx]

                    ax.imshow(stack[image_idx], cmap='gray')
                    ax.axis('off')
                    ax.set_title(f"Class {image_idx + 1}", fontsize=8)

                    # Add the number of particles on top
                    ax.text(0.5, 0.9, num_particles, fontsize=10, ha='center', va='bottom', 
                            transform=ax.transAxes, color='lime')
                    
                    # Add the resolution on the bottom
                    ax.text(0.5, 0.1, resolution, fontsize=10, ha='center', va='top', 
                            transform=ax.transAxes, color='lime')
                else:
                    ax.axis('off')  # Turn off unused subplots
            
            plt.tight_layout()
            pdf.savefig(fig)  # Save the current figure to the PDF
            plt.close(fig)

    print(f"Gallery saved as {output_pdf_path}")
