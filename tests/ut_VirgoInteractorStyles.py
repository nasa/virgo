import os, sys, shutil, inspect
import unittest
import io
from numpy.testing import assert_allclose
import pdb
from unittest.mock import Mock

import virgo
from virgo.Virgo import *
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
from virgo.VirgoInteractorStyles import *

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoTrackballInteractorStyleTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoInteractorStyleFirstPersonTestCase))
    return (suites)

class VirgoGenericInteractorStyleInitTestCase(unittest.TestCase):

    def create_context(self):
        """
        Create the common setup context needed for both interactor types
        """
        self.renderer = vtkRenderer()
        self.renderers = {'foreground': self.renderer}
        self.render_window = vtkRenderWindow()
        self.render_window.SetOffScreenRendering(True)  # Key: no display required
        self.render_window.SetSize(300, 300)
        self.render_window.AddRenderer(self.renderer)

        self.interactor = vtkRenderWindowInteractor()

        self.interactor.SetRenderWindow(self.render_window)


    def _simulate_drag(self, start, end):
        """Simulate a left-button click, drag, and release."""
        interactor = self.interactor

        interactor.SetEventPosition(start)
        interactor.InvokeEvent("LeftButtonPressEvent")

        # Simulate intermediate mouse moves for realism
        steps = 5
        for i in range(1, steps + 1):
            t = i / steps
            mid_x = int(start[0] + (end[0] - start[0]) * t)
            mid_y = int(start[1] + (end[1] - start[1]) * t)
            interactor.SetLastEventPosition(interactor.GetEventPosition())
            interactor.SetEventPosition(mid_x, mid_y)
            interactor.InvokeEvent("MouseMoveEvent")

        interactor.SetLastEventPosition(interactor.GetEventPosition())
        interactor.SetEventPosition(end)
        interactor.InvokeEvent("LeftButtonReleaseEvent")


class VirgoTrackballInteractorStyleTestCase(VirgoGenericInteractorStyleInitTestCase):
    """
    Test the trackball style (VirgoTrackballInteractorStyle) class
    """
    def setUp(self):
        self.create_context()
        self.style = VirgoTrackballInteractorStyle(renderers=self.renderers)
        # Mock the camera internals
        self.style.active_camera = Mock()
        self.style.active_camera.is_static.return_value = 0
        self.style.get_active_camera = Mock()
        self.style.get_active_camera.return_value = self.style.active_camera
        self.interactor.SetInteractorStyle(self.style)
        self.interactor.Initialize()
        self.render_window.Render()

    def test_drag_rotates_camera(self):
        """
        In trackball mode, a click drag only rotates the view about
        the focal point, moving the location of the camera in world space
        """
        camera = self.renderer.GetActiveCamera()

        # Capture initial camera state
        initial_position = camera.GetPosition()

        # Simulate a horizontal drag across the center
        self._simulate_drag(start=(100, 150), end=(200, 150))
        self.render_window.Render()

        final_position = camera.GetPosition()
        expected_position = (-0.9182161068, 0.0, 0.396079766)

        # Camera position should have changed
        self.assertNotAlmostEqual(
            initial_position[0], final_position[0], places=3,
            msg="Camera X should change after horizontal drag"
        )
        # Assert the exact position (expected values found by inspection)
        assert_allclose(final_position, expected_position)

    def test_drag_does_not_rotate_camera_when_static(self):
        """
        In trackball mode when static is true, a click drag should
        not impact the camera in any way
        """
        # Simulate the active camera being fixed/static
        self.style.active_camera.is_static.return_value = 1
        camera = self.renderer.GetActiveCamera()

        # Capture initial camera state
        initial_position = camera.GetPosition()

        # Simulate a horizontal drag across the center
        self._simulate_drag(start=(100, 150), end=(200, 150))
        self.render_window.Render()

        final_position = camera.GetPosition()
        assert_allclose(final_position, initial_position)

class VirgoInteractorStyleFirstPersonTestCase(VirgoGenericInteractorStyleInitTestCase):
    """
    Test the first-person style (VirgoInteractorStyleFirstPerson) class
    """
    def setUp(self):
        self.create_context()
        self.cameras = {'mycam': VirgoCamera(name='mycam')}
        self.style = VirgoInteractorStyleFirstPerson(renderers=self.renderers)
        # Mock the camera internals
        self.style.active_camera = self.cameras['mycam']
        #self.style.active_camera.is_static.return_value = 0
        self.style.get_active_camera = Mock()
        self.style.get_active_camera.return_value = self.cameras['mycam']
        self.interactor.SetInteractorStyle(self.style)
        self.interactor.Initialize()
        self.render_window.Render()

    def test_drag_does_not_rotate_camera(self):
        """
        In first person mode, a click drag only rotates the view, it cannot
        move the location of the camera in world space
        """
        camera = self.renderer.GetActiveCamera()

        # Capture initial camera state
        initial_position = camera.GetPosition()

        # Simulate a horizontal drag across the center
        self._simulate_drag(start=(100, 150), end=(200, 150))
        self.render_window.Render()

        final_position = camera.GetPosition()

        # Camera position should not have changed
        assert_allclose(final_position, initial_position)