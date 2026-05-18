import os, sys, inspect
import unittest
import numpy as np
import socket, time
from pathlib import Path
import threading

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from VirgoKovizInterface import KovizInterface

# --- Modular VTK Imports (Replaces 'import vtk') ---
from vtkmodules.vtkRenderingCore import (
  vtkRenderer,
  vtkRenderWindowInteractor,
)
def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoKovizInterfaceTestCase))
    return (suites)


class MockKovizClient:
    """
    Pretends to be the koviz application. Connects to KovizThread
    and sends canned messages, then disconnects.
    """
    def __init__(self, port: int, messages: list[str], delay=0.05):
        self.port = port
        self.messages = messages
        self.delay = delay          # small pause so KovizThread is ready
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def wait_until_done(self, timeout=5):
        self._thread.join(timeout)

    def _run(self):
        time.sleep(self.delay)      # give KovizThread time to call listen()
        with socket.create_connection(('127.0.0.1', self.port)) as sock:
            for msg in self.messages:
                sock.sendall(msg.encode())
                time.sleep(0.02)    # tiny gap between messages
        # socket closes here, KovizThread sees empty recv() -> disconnect



class VirgoKovizInterfaceTestCase(unittest.TestCase):
    """
    Test the koviz interface which manages the thread that connects
    to the koviz host/port

    Note this design was recommended by AI but I'm not sold on it,
    however for now some testing is better than none - Jordan 5/2026
    """
    def setUp(self):
        self.iface = KovizInterface(port=0)   # OS picks a free port every time
        self.port = self.iface.get_port()
        time.sleep(0.1)                        # let the thread reach accept()

    def tearDown(self):
        self.iface.stop()
        #self.iface._koviz_thread.join(timeout=2)    # wait for full cleanup before next test

    def test_receives_time(self):

        client = MockKovizClient(self.port, [
            't=1.23,begin_time=0.0,end_time=10.0',
        ])
        client.start()
        client.wait_until_done()
        time.sleep(0.1)   # let KovizThread push the event onto the queue

        result = self.iface.poll()
        self.assertAlmostEqual(result, 1.23)
        self.iface.stop()

    def test_receives_run_dir(self):
        self.iface.set_expected_run_dir('/some/run/dir')

        client = MockKovizClient(self.port, [
            'run=/some/run/dir,t=0.0',
        ])
        client.start()
        client.wait_until_done()
        time.sleep(0.1)

        self.iface.poll()
        self.assertEqual(self.iface.run_dir, Path('/some/run/dir').resolve())
        self.iface.stop()

    def test_run_dir_mismatch_stops_thread(self):
        self.iface.set_expected_run_dir('/expected/dir')

        client = MockKovizClient(self.port, [
            'run=/wrong/dir,t=0.0',
        ])
        client.start()
        client.wait_until_done()
        time.sleep(0.1)

        # TODO the intent is for this to trigger the check_run_dir() function
        # but in practice the mock closes the connection before it can get
        # there. Need to rethink this test - Jordan 5/2026
        self.iface.update()   # triggers check_run_dir()
        self.assertIn('disconnected', self.iface.state)
        self.iface.stop()

    def test_connect_disconnect_events(self):

        client = MockKovizClient(self.port, [])  # connect then immediately drop
        client.start()
        client.wait_until_done()
        time.sleep(0.15)

        self.iface.poll()
        # After the empty-message disconnect, state should reflect disconnected
        self.assertEqual(self.iface.state, 'disconnected')
        self.iface.stop()
