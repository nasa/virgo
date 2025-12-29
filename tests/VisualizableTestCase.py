import os, sys, unittest, vtk, inspect

thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
tests_dir=os.path.join(virgo_dir, 'tests')

class VisualizableTestCase(unittest.TestCase):
    """
    A base class for VTK unit tests that supports optional visualization of the
    unit test. It is recommended you call self.vis() from the test you want to
    see only while developing.

    The environment variable VIRGO_BATCH_TESTS_OVERRIDE=1 will override all
    windowed mechanisms, ensuring a render window never appears which is useful
    when running in a CI system.
    """
    def __init__(self, methodName='runTest', *args, **kwargs):
        super().__init__(methodName, *args, **kwargs)
        self.batch_override = os.environ.get('VIRGO_BATCH_TESTS_OVERRIDE', '0') == '1'
        self.instance = None
        self.renderer = None
        self.camera = None
        self.render_window = None
        self.interactor = None
        self.grid_axes = None
        self.origin_axes = None

    def tearDown(self):
        pass


    def get_grid_axes(self, bounds=[-5, 5, -5, 5, -5, 5]):
        # Create a vtkCubeAxesActor for tick marks
        cube_axes = vtk.vtkCubeAxesActor()
        cube_axes.SetBounds(bounds)
        cube_axes.SetXLabelFormat("%.0f")  # Integer labels
        cube_axes.SetYLabelFormat("%.0f")
        cube_axes.SetZLabelFormat("%.0f")
        cube_axes.SetXTitle("x")
        cube_axes.SetYTitle("y")
        cube_axes.SetZTitle("z")
        cube_axes.SetTickLocationToBoth()  # Show ticks on both sides
        cube_axes.SetGridLineLocation(vtk.vtkCubeAxesActor.VTK_GRID_LINES_ALL)  # Optional: Show grid lines
        cube_axes.SetFlyModeToStaticEdges()  # Render axes on the edges of the bounds
        
        # Enable minor ticks (optional)
        cube_axes.SetDrawXGridlines(True)
        cube_axes.SetDrawYGridlines(True)
        cube_axes.SetDrawZGridlines(True)
        cube_axes.SetCamera(self.renderer.GetActiveCamera())  # Required for proper rendering
        return(cube_axes)

    def set_grid_bounds_automatic(self, actors):
        if actors and self.grid_axes:
            # Initialize with the first actor's bounds
            current_bounds = list(actors[0].GetBounds())
            
            # Expand to include all other actors
            for actor in actors:
                actor_bounds = actor.GetBounds()
                # Update mins and maxs
                current_bounds[0] = min(current_bounds[0], actor_bounds[0])  # xmin
                current_bounds[1] = max(current_bounds[1], actor_bounds[1])  # xmax
                current_bounds[2] = min(current_bounds[2], actor_bounds[2])  # ymin
                current_bounds[3] = max(current_bounds[3], actor_bounds[3])  # ymax
                current_bounds[4] = min(current_bounds[4], actor_bounds[4])  # zmin
                current_bounds[5] = max(current_bounds[5], actor_bounds[5])  # zmax
            self.grid_axes.SetBounds(current_bounds)  # Set bounds for the axes (10x10x10 cube)


    def get_origin_axes(self):
      origin_axes = vtk.vtkAxesActor()
      origin_axes.SetTotalLength(5, 5, 5)  # Size of axes (x, y, z lengths)
      #origin_axes.SetShaftTypeToCylinder()  # Cylindrical shafts
      origin_axes.SetAxisLabels(True)  # Show x, y, z labels
      origin_axes.SetXAxisLabelText("x")
      origin_axes.SetYAxisLabelText("y")
      origin_axes.SetZAxisLabelText("z")
      return(origin_axes)
    

    def save_scene_to_image(self, actors, filename="scene.png"):
        """
        Save the scene with the given actors to an image file without displaying a window.
        :param actors: A single vtkActor or a list of vtkActors to render.
        :param filename: Name of the output image file (e.g., 'scene.png').
        """
        if not isinstance(actors, list):
            actors = [actors]
        
        # Set up the scene
        for actor in actors:
            self.renderer.AddActor(actor)
        self.renderer.AddActor2D(self.get_origin_axes())
        
        # Create render window with off-screen rendering
        render_window = vtk.vtkRenderWindow()
        render_window.AddRenderer(self.renderer)
        render_window.SetSize(800, 600)
        render_window.SetOffScreenRendering(1)  # Enable off-screen rendering
        
        # Render the scene
        render_window.Render()
        
        # Capture the image
        window_to_image = vtk.vtkWindowToImageFilter()
        window_to_image.SetInput(render_window)
        window_to_image.SetInputBufferTypeToRGBA()  # Use RGBA for better quality
        window_to_image.ReadFrontBufferOff()  # Read from back buffer
        window_to_image.Update()
        
        # Write to PNG file
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(os.path.join(tests_dir, filename))
        writer.SetInputConnection(window_to_image.GetOutputPort())
        writer.Write()

    def img(self, actors=None):
        """
        Easy function for saving images in a test
        """
        self.save_scene_to_image(actors=actors, filename=f".{self.__class__.__name__}_{self._testMethodName}.png")

    def vis(self, actors=None, show_origin=True, oal=[5,5,5], show_grid=True):
        """
        Easy-to-call function that will save scenes to image or show them in an
        interactive window depending on what the user has requested. Does nothing
        if neither of those features is enabled by the user
        """
        if self.batch_override:
            return
        
        if not actors:
          actors=self.instance

        self.renderer = vtk.vtkRenderer()
        self.camera = self.renderer.GetActiveCamera()
        self.render_window = vtk.vtkRenderWindow()
        self.interactor = vtk.vtkRenderWindowInteractor()
        self.origin_axes = self.get_origin_axes()
        self.visualize_scene(actors=actors, show_origin=show_origin, 
                             oal=oal, show_grid=show_grid)

    def visualize_scene(self, actors, show_origin=True, 
                        oal=[5, 5, 5], show_grid=True):
        """
        Optionally visualize a list of actors in a render window.

        :param actors: A single vtkActor or a list of vtkActors to visualize.
        :param show_origin: Boolean for showing vtkAxes at origin
        :param ool: Origin Axes Length (x, y, z) values
        :param show_grid: Boolean for showing 3D grid with actor(s)

        When visualization is enabled, a render window will pop up and
        block until closed.
        """
        if not isinstance(actors, list):
            actors = [actors]
        self.set_grid_bounds_automatic(actors)

        # Create a text actor for the test name itself, lower left corner
        test_name = f"{self.__module__}.{self.__class__.__name__}.{self._testMethodName}"
        test_name_text_actor = vtk.vtkTextActor()
        test_name_text_actor.GetTextProperty().SetFontFamilyToCourier()
        test_name_text_actor.GetTextProperty().SetFontSize(12)
        test_name_text_actor.GetTextProperty().SetColor(1, 1, 1)
        test_name_text_actor.SetDisplayPosition(5, 5)
        test_name_text_actor.SetInput(test_name)
        
        # Set up the scene
        for actor in actors:
            self.renderer.AddActor(actor)
        self.renderer.AddActor(test_name_text_actor)
        if show_origin:
            # Size of axes (x, y, z lengths)
            self.origin_axes.SetTotalLength(oal[0], oal[1], oal[2])
            self.renderer.AddViewProp(self.origin_axes)
        if show_grid:
            self.grid_axes = self.get_grid_axes()
            self.renderer.AddActor(self.grid_axes)
        
        # Create render window and interactor
        self.render_window.AddRenderer(self.renderer)
        self.render_window.SetSize(800, 600)  # Optional: Set window size
        
        self.interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.interactor.SetRenderWindow(self.render_window)
        
        # Render and start interaction (blocks until window is closed)
        print(f"Visualizing {test_name}. Exit window (q) to continue.")
        self.renderer.ResetCamera()
        self.render_window.Render()
        self.interactor.Start()