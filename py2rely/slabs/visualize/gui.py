from py2rely import cli_context
import click

@click.group()
@click.pass_context
def cli(ctx):
    pass


def get_image_selector():
    from PyQt5 import QtWidgets
    import pyqtgraph as pg

    class ImageSelector(QtWidgets.QWidget):
        def __init__(self, images, grid_columns=5, image_size=150, counts=None, resolutions=None):
            super().__init__()
            self.images = images
            self.selected_indices = []
            self.grid_columns = grid_columns
            self.image_size = image_size
            self.counts = counts if counts else [""] * len(images)
            self.resolutions = resolutions if resolutions else [""] * len(images)

            self.initUI()

        def initUI(self):
            from PyQt5 import QtWidgets, QtCore
            from pyqtgraph import TextItem     
            from PyQt5.QtGui import QFont           

            main_layout = QtWidgets.QHBoxLayout(self)
            
            # Scroll area and container for images
            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)
            container = QtWidgets.QWidget()
            self.layout = QtWidgets.QGridLayout(container)
            
            self.image_views = []

            for i, img in enumerate(self.images):
                # Create image view
                view = pg.ImageView()
                view.setImage(img)
                view.ui.roiBtn.hide()
                view.ui.menuBtn.hide()
                view.ui.histogram.hide()
                view.setFixedSize(self.image_size, self.image_size)
                view.getImageItem().mouseClickEvent = self.create_click_handler(i, view)
                self.image_views.append(view)

                if self.counts is not None:
                    # Add text overlay for counts
                    text_item1 = TextItem(self.counts[i], anchor=(0.5, 0.5), color='g')
                    text_item1.setPos(img.shape[1] // 2, img.shape[0] // 15)
                    font = QFont()
                    font.setPointSize(12)  # Set the desired font size here
                    text_item1.setFont(font)
                    view.addItem(text_item1)

                if self.resolutions is not None:
                    # Add text overlay for resolutions
                    text_item2 = TextItem(self.resolutions[i], anchor=(0.5, 0.5), color='g')
                    text_item2.setPos(img.shape[1] // 2, img.shape[0] // 1)
                    font = QFont()
                    font.setPointSize(12)  # Set the desired font size here
                    text_item2.setFont(font)
                    view.addItem(text_item2)

                row = i // self.grid_columns
                col = i % self.grid_columns
                self.layout.addWidget(view, row, col)

            scroll_area.setWidget(container)
            main_layout.addWidget(scroll_area)

            # Add a vertical slider without a ball
            self.slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
            self.slider.setMinimum(0)
            self.slider.setMaximum(100)
            self.slider.setValue(0)
            self.slider.setStyleSheet("""
                QSlider::groove:vertical {
                    background: transparent;
                    width: 8px;
                }
                QSlider::handle:vertical {
                    background: black;
                    border: 1px solid #5c5c5c;
                    height: 20px;
                    margin: 0 -4px;
                }
            """)
            self.slider.valueChanged.connect(self.slider_changed)
            main_layout.addWidget(self.slider)

            self.setWindowTitle('Image Selector')
            self.resize(800, 600)  # Set initial size of the window
            self.show()

        def create_click_handler(self, index, view):
            def handler(event):
                if index in self.selected_indices:
                    self.selected_indices.remove(index)
                    view.getImageItem().setBorder(None)
                else:
                    self.selected_indices.append(index)
                    view.getImageItem().setBorder(pg.mkPen('r', width=3))
                tmp = [x + 1 for x in self.selected_indices]
                print(f"Selected Images: {tmp}")
            return handler

        def slider_changed(self, value):
            from PyQt5 import QtWidgets

            # Adjust the scroll area position based on the slider value
            scroll_area = self.findChild(QtWidgets.QScrollArea)
            max_scroll = scroll_area.verticalScrollBar().maximum()
            scroll_area.verticalScrollBar().setValue(value * max_scroll // 100)

    return ImageSelector

def find_final_iteration(classPath):
    import glob, os, re

    # Find the Final Iteration
    # iterationStarFiles = glob.glob(os.path.join('Class2D', classPath, 'run_*_data.star'))
    # maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'_it(\d+)_', x).group(1)))
    # maxIter = int(re.search(r'it(\d+)', maxIterationStarFile).group(1))
    # Filter out unwanted filenames (exclude 'run_annon_itXXX_*' cases)
    
    # Find the Final Iteration, Ignore User Submission Runs
    iterationStarFiles = glob.glob(os.path.join('Class2D', classPath, 'run_it*_data.star'))
    iterationStarFiles = [f for f in iterationStarFiles if re.search(r'run_it\d+_data\.star$', f)]
    
    if not iterationStarFiles:
        raise ValueError(f"No valid iteration files found in {os.path.join('Class2D', classPath)}")
    
    # Extract iteration number and find the max iteration
    maxIterationStarFile = max(iterationStarFiles, key=lambda x: int(re.search(r'run_it(\d+)_', x).group(1)))
    maxIter = int(re.search(r'run_it(\d+)_', maxIterationStarFile).group(1))

    return maxIter

@cli.command(context_settings=cli_context, name='extract')
@click.option(
    '--job', 
    required=True, 
    type=str, 
    default='job001', 
    help='Job Associated to the class2D to export classes from')
@click.option(
    '--extract-classes',
    required=False,
    type=click.BOOL,
    default=True,
    help='Enable or disable class extraction. (True/False)')
@click.option(
    '--grid-columns', 
    required=False, 
    type=int, 
    default=3, 
    help='Number of grid columns')
@click.option(
    '--image-size', 
    required=False, 
    type=int, 
    default=128,
    help='Size of the images')
def classes(
    job: str,
    extract_classes: bool,
    grid_columns: int,
    image_size: int):
    """
    Launch Class Selector GUI from a 2DClass Job.
    """

    run_class_selector(job, extract_classes, grid_columns, image_size)

def run_class_selector(
    job: str, extract_classes: bool, 
    grid_columns: int, image_size: int
    ):
    from pipeliner.api.manage_project import PipelinerProject
    import sys, os, re, starfile
    import click, glob, mrcfile
    import pyqtgraph as pg
    import numpy as np

    # Check to Make Sure a Valid Class Path is Provided
    if not os.path.isdir(os.path.join('Class2D', job)):
        print(f'\nInvalid Class Job: Class2D/{job}\n')
        print(f'Available Class Jobs: {os.listdir("Class2D")}')
        print(f'Exiting...')
        sys.exit(1)

    app = QtWidgets.QApplication(sys.argv)
    maxIter = find_final_iteration(job)
    dataset = mrcfile.read(os.path.join('Class2D',job,f'run_it{maxIter:03d}_classes.mrcs'))

    num_images = dataset.shape[0]
    text_list = [f"Class {i+1}" for i in range(num_images)]  # Example text for each image

    resultsStarFile = starfile.read( os.path.join('Class2D', job, f'run_it{maxIter:03d}_model.star'))
    resolution_list = [f"{round(resultsStarFile['model_classes']['rlnEstimatedResolution'][i],2)} A" for i in range(num_images)]    

    particlesStarPath = os.path.join('Class2D', job, f'run_it{maxIter:03d}_data.star')
    particlesStarFile = starfile.read( particlesStarPath )
    nParticles = particlesStarFile['particles'].shape[0]
    particle_count_list = [ f"{int(resultsStarFile['model_classes']['rlnClassDistribution'][i] * nParticles)} Particles" for i in range(num_images) ]  

    # Adjust grid_columns and image_size to fit your screen
    ImageSelector = get_image_selector()
    ex = ImageSelector(dataset, grid_columns=grid_columns, image_size=image_size, 
                       counts = particle_count_list, resolutions = resolution_list)
    app.exec_()

    if extract_classes:

        print('Exporting Particles...')

        # Create Pipeliner Project
        my_project = PipelinerProject(make_new_project=True)
        utils = pipeline(my_project)
        utils.read_json_directories_file('output_directories.json')

        selected_classes = ex.selected_indices  
        selected_classes = [x for x in selected_classes]

        if len(selected_classes) == 0:
            print(f'No Classes Selected, Exiting...\n')
            exit(1)

        # class2DIteration = key_with_substring.split('_')[1]
        utils.initialize_selection()
        utils.initialize_classification()
        utils.class2D_job.output_dir = os.path.join('Class2D', job)
        utils.tomo_select_job.joboptions['fn_data'].value = particlesStarPath
        utils.tomo_select_job.joboptions['select_minval'].value = selected_classes[0]
        utils.tomo_select_job.joboptions['select_maxval'].value = selected_classes[0]        
        utils.run_subset_select(keepClasses = selected_classes, classPath = particlesStarPath)

        print(f'✅ Particles Exported to: {utils.tomo_select_job.output_dir}particles.star')


@cli.command(context_settings=cli_context)
@click.option(
    '--particles-path', 
    required=True, 
    type=str, 
    help='Path to the particles stack file.')
@click.option(
    '--grid-columns', 
    required=False, 
    type=int, 
    default=3, 
    help='Number of grid columns')
@click.option(
    '--image-size', 
    required=False, 
    type=int, 
    default=128,
    help='Size of the images')
def particle_stacks(
    particles_path: str,
    grid_columns: int,
    image_size: int
    ):
    """
    Extract Particles from Selected 2D Classes.    
    """
    from PyQt5 import QtWidgets
    import sys, mrcfile

    app = QtWidgets.QApplication(sys.argv)
    dataset = mrcfile.read(particles_path)

    if dataset.shape[0] > 300:
        print('Particles Stack is Too Large, Defaulting to Showing the First 300 Images...')
        dataset = dataset[:300,]

    # Adjust grid_columns and image_size to fit your screen
    ex = ImageSelector(dataset, grid_columns=grid_columns, image_size=image_size)
    app.exec_()


if __name__ == "__main__":
    cli()
