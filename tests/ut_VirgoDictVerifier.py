import os, sys, shutil, inspect
import unittest
import io
from unittest.mock import patch
from numpy.testing import assert_allclose
import pdb

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from VirgoDictVerifier import *

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDictVerifierTestCase))
    return (suites)
class VirgoDictVerifierTestCase(unittest.TestCase):
    def setUp(self):
        self.scene = {}
        self.scene['name']  = 'my scene name'
        #self.scene['name']  = 3
        self.scene['description']  = 'my description'
        self.scene['start_mode']  = 'PAUSED'
        self.scene['end_mode']  = 'PAUSED'
        self.scene['background_color']  = [0.0, 0.0, 0.0]
        self.scene['highlight_color']  = [1.0, 0.0, 0.0]
        self.scene['playback_speeds']  = [1.0, 2.0]
        self.scene['playback_speed']  = 1.0
        self.scene['starfield']  = 0

        self.underspecified_scene = self.scene.copy()

        self.scene['actors'] = {}
        self.scene['actors']['myactor'] = {}
        self.scene['actors']['myactor']['mesh'] = 'VIRGO_PREFAB:cube'

    def tearDown(self):
        pass

    def test_nominal(self):
        verified_dict = VirgoDictVerifier(self.scene).verify(terminate=False)
        self.assertIn('playback_speeds', verified_dict)
        # TODO more go here
        self.assertIn('name', verified_dict)

    def test_nominal_with_defaults(self):
        del self.scene['name']
        del self.scene['background_color']
        del self.scene['playback_speeds']
        del self.scene['playback_speed']
        verified_dict = VirgoDictVerifier(self.scene).verify(terminate=False)
        self.assertEqual(verified_dict['name'], VIRGO_DEFAULT_SCENE_NAME)
        self.assertIn('playback_speeds', verified_dict)
        assert_allclose(verified_dict['playback_speeds'], VIRGO_DEFAULT_PLAYBACK_SPEEDS)
        assert_allclose(verified_dict['playback_speed'], 1.0)
        assert_allclose(verified_dict['background_color'], VIRGO_DEFAULT_BACKGROUND_COLOR)

    def test_underspecified_scene(self):
        with self.assertRaises(ValidationError):
            verified_dict = VirgoDictVerifier(
                self.underspecified_scene).verify(terminate=False)

    def test_empty_scene(self):
        """
        Tests that defaults get applied when not given by the user
        """
        self.scene = {}
        with self.assertRaises(ValidationError):
            verified_dict = VirgoDictVerifier(self.scene).verify(terminate=False)

    def test_invalid_schema(self):
        """
        Change some of the self.scene dictionary to be values that are not
        allowed
        """
        self.scene['background_color']  = 'blue'
        self.scene['highlight_color']  = 'green'
        self.scene['playback_speeds']  = 1.0
        self.scene['vectors'] = 'this_is_wrong'
        self.scene['frames'] = 17
        with self.assertRaises(ValidationError) as e:
            verified_dict = VirgoDictVerifier(self.scene).verify(terminate=False)
        self.assertIn("background_color", str(e.exception))
        self.assertIn("highlight_color", str(e.exception))
        self.assertIn("playback_speeds", str(e.exception))
        self.assertIn("vectors", str(e.exception))
        self.assertIn("frames", str(e.exception))



