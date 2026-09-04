import os, sys, shutil, inspect
import unittest
import pdb

import virgo
from virgo.VirgoTrickpyFileLoader import *
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
from VisualizableTestCase import VisualizableTestCase

def generate_increasing_numbers_2D_array(num_rows, num_columns):
    """
    Write a function to create "dummy data" matching patterns in .csv data files
    Generates a numpy array of given size. The first element starts at 1 and
    increases by 1 for each index following row, column. Examples below:

    generate_increasing_numbers_2D_array(3, 3)
    <class 'numpy.ndarray'>
    [[1. 2. 3.]
     [4. 5. 6.]
     [7. 8. 9.]]

    generate_increasing_numbers_2D_array(1, 4)
    <class 'numpy.ndarray'>
    [1. 2. 3. 4.]

    generate_increasing_numbers_2D_array(3, 1)
    <class 'numpy.ndarray'>
    [1. 2. 3.]

    generate_increasing_numbers_2D_array(2, 3)
    <class 'numpy.ndarray'>
    [[1. 2. 3.]
     [4. 5. 6.]]

    """
    expected_pattern = np.zeros((num_rows, num_columns))
    for row in range(num_rows):
        for column in range(num_columns):
            expected_pattern[row, column] = row * num_columns + column + 1
    return expected_pattern.squeeze()

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDataLoaderSimpleTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDataLoaderOverlappingDataTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDataLoaderStaticFunctionsTestCase))
    return (suites)

    import time

class VirgoDataLoaderSimpleTestCase(unittest.TestCase):
    def setUp(self):
        self.trickpy_dict  = {}
        self.trickpy_dict['time']  = {}
        self.trickpy_dict['pos']  = {}
        self.trickpy_dict['rot']  = {}
        self.trickpy_dict['time']['group'] = "one_body_static"
        self.trickpy_dict['pos']['group']  = "one_body_static"
        self.trickpy_dict['rot']['group']  = "one_body_static"
        self.trickpy_dict['time']['var']   = "sys.exec.out.time"
        self.trickpy_dict['pos']['var']    = "position[0-2]"
        self.trickpy_dict['rot']['var']    = "R[0-2][0-2]"

    def setUp_complex_var_names_01(self):
        """A dict suitable for RUN_complex_var_names_01 dir"""
        self.trickpy_dict  = {}
        self.trickpy_dict['time']  = {}
        self.trickpy_dict['pos']  = {}
        self.trickpy_dict['rot']  = {}
        self.trickpy_dict['opacity']  = {}
        self.trickpy_dict['vec1']  = {}
        self.trickpy_dict['time']['group']    = "one_body_static"
        self.trickpy_dict['pos']['group']     = "one_body_static"
        self.trickpy_dict['rot']['group']     = "one_body_static"
        self.trickpy_dict['opacity']['group'] = "one_body_static"
        self.trickpy_dict['vec1']['group'] = "one_body_static"
        self.trickpy_dict['time']['var']      = "sys.exec.out.time"
        self.trickpy_dict['pos']['var']       = "my.foo[0].position[0-2]"
        self.trickpy_dict['rot']['var']       = "my.foo[0].R[0-2][0-2]"
        self.trickpy_dict['opacity']['var']   = "my.foo[0].bar[0]"
        self.trickpy_dict['vec1']['var']   = "my.foo[0][0][0].hi[0][0-2]"

    def setUp_complex_array_sizes_01(self):
        """A dict suitable for RUN_complex_array_sizes_01 dir"""
        self.trickpy_dict                                               = {}
        self.trickpy_dict['quaternion']                                 = {}
        self.trickpy_dict['attitude_control_jets_duty_cycle']           = {}
        self.trickpy_dict['state_error_covariance']                     = {}
        self.trickpy_dict['twobythree']                                 = {}
        self.trickpy_dict['quaternion']['group']                        = "one_body_static"
        self.trickpy_dict['attitude_control_jets_duty_cycle']['group']  = "one_body_static"
        self.trickpy_dict['state_error_covariance']['group']            = "one_body_static"
        self.trickpy_dict['twobythree']['group']                        = "one_body_static"
        self.trickpy_dict['quaternion']['var']                          = "q[0-3]"
        self.trickpy_dict['attitude_control_jets_duty_cycle']['var']    = "acjdc[0-7]"
        self.trickpy_dict['state_error_covariance']['var']              = "sec[0-5][0-5]"
        self.trickpy_dict['twobythree']['var']                          = "tbt[0-1][0-2]"

    def test_expand_arrays(self):
        """
        Test the expand_arrays static method
        """
        t = VirgoTrickpyFileLoader.expand_arrays(varname='foo.bar[0-2]')
        for i in range(3):
          self.assertEqual(t[i], f'foo.bar[{i}]')
        t = VirgoTrickpyFileLoader.expand_arrays(varname='foo.bar[0-2][0-2]')
        self.assertEqual(t[0], f'foo.bar[0][0]')
        self.assertEqual(t[1], f'foo.bar[0][1]')
        self.assertEqual(t[2], f'foo.bar[0][2]')
        self.assertEqual(t[3], f'foo.bar[1][0]')
        self.assertEqual(t[4], f'foo.bar[1][1]')
        self.assertEqual(t[5], f'foo.bar[1][2]')
        self.assertEqual(t[6], f'foo.bar[2][0]')
        self.assertEqual(t[7], f'foo.bar[2][1]')
        self.assertEqual(t[8], f'foo.bar[2][2]')

        t = VirgoTrickpyFileLoader.expand_arrays(varname='foo[1-2].bar[0-2]')

    def test_get_alias_data(self):
        self.instance = VirgoTrickpyFileLoader(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            trickpy_dict=self.trickpy_dict,
            verbosity=1)
        self.instance.load_variables()
        times = self.instance.get_alias_data(alias='time')
        self.assertEqual(times, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        posxs = self.instance.get_alias_data(alias='pos[0]')
        posys = self.instance.get_alias_data(alias='pos[1]')
        poszs = self.instance.get_alias_data(alias='pos[2]')
        # TODO need more assertions here
        self.assertEqual(posxs[0], 0.0)
        self.assertEqual(posys[0], 0.0)
        self.assertEqual(poszs[0], 0.0)

        Rxxs = self.instance.get_alias_data(alias='rot[0][0]')
        # TODO need more assertions here
        self.assertEqual(Rxxs[0], 1.0)

        with self.assertRaises(RuntimeError):
            # Indices not specified when they need to be
            posxs = self.instance.get_alias_data(alias='pos')

    def test_get_alias_data_complex_var_names_01(self):
        self.setUp_complex_var_names_01()

        self.instance = VirgoTrickpyFileLoader(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_complex_var_names_01'),
            trickpy_dict=self.trickpy_dict,
            verbosity=1)
        self.instance.load_variables()
        times = self.instance.get_alias_data(alias='time')
        self.assertEqual(times, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        posxs = self.instance.get_alias_data(alias='pos[0]')
        posys = self.instance.get_alias_data(alias='pos[1]')
        poszs = self.instance.get_alias_data(alias='pos[2]')
        opacities = self.instance.get_alias_data(alias='opacity')
        vec1 = self.instance.get_alias_datas(alias='vec1')
        # TODO need more assertions here
        self.assertEqual(posxs[0], 0.0)
        self.assertEqual(posys[0], 0.0)
        self.assertEqual(poszs[0], 0.0)
        self.assertEqual(opacities[0], 0.5)
        self.assertEqual(vec1[0], (1.0,0.0,0.0))

        Rxxs = self.instance.get_alias_data(alias='rot[0][0]')
        # TODO need more assertions here
        self.assertEqual(Rxxs[0], 1.0)

        with self.assertRaises(RuntimeError):
            # Indices not specified when they need to be
            posxs = self.instance.get_alias_data(alias='pos')


    def test_init_missing_recorded_data_variables(self):
        """
        Add variables to the scene that don't exist in the logged data file
        """
        # Add variables to scene that won't be found
        self.trickpy_dict['noexist']  = {}
        self.trickpy_dict['noexist']['var']  = "noexist[0-2]"
        self.instance = VirgoTrickpyFileLoader(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            trickpy_dict=self.trickpy_dict)
        # Try to load the scene, knowing it will fail
        with self.assertRaises(RuntimeError):
            self.instance.load_variables()

    def test_get_alias_datas(self):
        self.instance = VirgoTrickpyFileLoader(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            trickpy_dict=self.trickpy_dict,
            verbosity=1)
        self.instance.load_variables()
        times = self.instance.get_alias_datas(alias='time')
        self.assertEqual(times, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        positions = self.instance.get_alias_datas(alias='pos')
        self.assertEqual(positions[0], (0.0, 0.0, 0.0))
        rotations = self.instance.get_alias_datas(alias='rot')
        expected_rot_0 = np.array( [ [1.0, 0.0, 0.0 ],
                                     [0.0, 1.0, 0.0 ],
                                     [0.0, 0.0, 1.0 ],
                                   ] )
        np.testing.assert_array_equal(rotations[0], expected_rot_0)
        pass
    
    def test_get_alias_datas_complex_array_sizes_01(self):
        self.setUp_complex_array_sizes_01()

        self.instance = VirgoTrickpyFileLoader(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_complex_array_sizes_01'),
            trickpy_dict=self.trickpy_dict,
            verbosity=1)
        
        self.instance.load_variables()
        quaternions = self.instance.get_alias_datas(alias='quaternion')
        attitude_control_jets_duty_cycles = self.instance.get_alias_datas(alias='attitude_control_jets_duty_cycle')
        state_error_covariances = self.instance.get_alias_datas(alias='state_error_covariance')
        twobythrees = self.instance.get_alias_datas(alias='twobythree')

        
        
        # Create test matrices to compare with
        expected_quaternions_0 = generate_increasing_numbers_2D_array(1, 4)
        expected_attitude_control_jets_duty_cycles_0 = generate_increasing_numbers_2D_array(1, 8)
        expected_state_error_covariances_0 = generate_increasing_numbers_2D_array(6, 6)
        expected_twobythrees_0 = generate_increasing_numbers_2D_array(2,3)

        np.testing.assert_array_equal(quaternions[0], expected_quaternions_0)
        np.testing.assert_array_equal(attitude_control_jets_duty_cycles[0], expected_attitude_control_jets_duty_cycles_0)
        np.testing.assert_array_equal(state_error_covariances[0], expected_state_error_covariances_0)
        np.testing.assert_array_equal(twobythrees[0], expected_twobythrees_0)
        
        pass
    
class VirgoDataLoaderOverlappingDataTestCase(unittest.TestCase):
    """
    In this test case we load variables that are defined in multiple
    data record groups (two log*.csv in the same dir)
    """
    def setUp(self):
        self.trickpy_dict  = {}
        self.trickpy_dict['time']  = {}
        self.trickpy_dict['pos1']  = {}
        self.trickpy_dict['rot1']  = {}
        self.trickpy_dict['time']['group'] = "one_body_static"
        self.trickpy_dict['time']['var']   = "sys.exec.out.time"
        self.trickpy_dict['pos1']['group']  = "one_body_static"
        self.trickpy_dict['pos1']['var']    = "position[0-2]"
        self.trickpy_dict['rot1']['group']  = "one_body_static"
        self.trickpy_dict['rot1']['var']    = "R[0-2][0-2]"
        self.trickpy_dict['pos2']  = {}
        self.trickpy_dict['rot2']  = {}
        self.trickpy_dict['pos2']['group']  = "one_body_moving"
        self.trickpy_dict['pos2']['var']    = "position[0-2]"
        self.trickpy_dict['rot2']['group']  = "one_body_moving"
        self.trickpy_dict['rot2']['var']    = "R[0-2][0-2]"

    def test_load_variables(self):
        self.instance = VirgoTrickpyFileLoader(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_1'),
            trickpy_dict=self.trickpy_dict,
            verbosity=1)
        self.instance.load_variables()
        times = self.instance.get_alias_data(alias='time')
        self.assertEqual(times, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        pos1xs = self.instance.get_alias_data(alias='pos1[0]')
        pos1ys = self.instance.get_alias_data(alias='pos1[1]')
        pos1zs = self.instance.get_alias_data(alias='pos1[2]')

class VirgoDataLoaderStaticFunctionsTestCase(unittest.TestCase):
    """
    Test the static functions
    """
    def setUp(self):
        #  Format of the data is: Input, expected 1st output, expected 2nd output
        self.test_strings = [
            ['sys.exec.out.time',             'sys.exec.out.time',            ''],
            ['time',                          'time',                         ''],
            ['position[0]',                   'position',                  '[0]'],
            ['position[0-2]',                 'position',                '[0-2]'],
            ['my.foo[0].position[0-2]',       'my.foo[0].position',      '[0-2]'],
            ['my.foo[0].position[0]',         'my.foo[0].position',        '[0]'],
            ['my.foo[0].R[0-2][0-2]',         'my.foo[0].R',        '[0-2][0-2]'],
            ['my.foo[0].bar[0]',              'my.foo[0].bar',             '[0]'],
            ['my.foo[0].opacity',             'my.foo[0].opacity',            ''],
            ['my.foo[0][1].bar[0][0]',        'my.foo[0][1].bar',       '[0][0]'],
            ['my.foo[0][1].bar[0-2][0-2]',    'my.foo[0][1].bar',   '[0-2][0-2]'],
            ['my.foo[0][0][0].hello',         'my.foo[0][0][0].hello',        ''],
            ['my.foo[0][0][0].hi[0]',         'my.foo[0][0][0].hi',        '[0]'],
            ['my.foo[0][0][0].hi[0][2]',      'my.foo[0][0][0].hi',     '[0][2]'],
            ['my.foo[0][0][0].hi[0-2][0-2]',  'my.foo[0][0][0].hi', '[0-2][0-2]'],
            ['my.foo[0][0][0].hi[0][0-2]',  'my.foo[0][0][0].hi', '[0][0-2]'],
        ]
    def test_split_variable_indices(self):
        for row in self.test_strings:
            input          = row[0]
            expected_first = row[1]
            expected_second = row[2]
            part1, part2 = VirgoTrickpyFileLoader.split_variable_indices(input)
            self.assertEqual(part1, expected_first)
            self.assertEqual(part2, expected_second)
