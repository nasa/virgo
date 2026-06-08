import socket
import threading
import queue
import time
import sys, os, yaml, inspect
from pathlib import Path



class KovizThread(threading.Thread):
    """
    A thread that connects to the koviz host/port and allows for communication
    in both directions. The primary purpose of this class is to send and
    receive information about what time both koviz and VIRGO should sync to

    This class was modeled after the example provided by koviz/blender/koviz.py
    """

    HOST = '127.0.0.1'
    MAX_MSG_SIZE = 1024

    def __init__(self, event_queue: queue.Queue, port=64053):
        super().__init__(daemon=True)
        self._q = event_queue
        self._lock = threading.Lock()
        self._last_sent_time = None
        self._client_sock = None
        self._is_running = False
        self.error_msg = None

        # Bind eagerly so callers can read self.port before run() is called
        self._listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._listen_sock.bind((self.HOST, port))
        except OSError as e:
            self.error_msg = f"ERROR: Could not bind to {self.HOST}:{port}\n {e}"
            print(f'[koviz] {self.error_msg}')
            self._listen_sock = None
        else:
            self._listen_sock.listen(1)
            self.port = self._listen_sock.getsockname()[1]  # reflects actual port if 0 was passed



    def start(self):
        self._is_running = True
        super().start()
        print(f'[koviz] KovizThread started, is_alive={self.is_alive()}')

    def stop(self):
        self._is_running = False
        self._listen_sock.close()

    def send_time(self, t: float):
        """
        Send current virgo world_time back to koviz.
        Only transmits when time has actually changed to avoid flooding.
        """
        with self._lock:
            sock = self._client_sock
        if sock is None:
            return
        if t == self._last_sent_time:
            return
        try:
            sock.sendall(f'TIME={t}'.encode())
            self._last_sent_time = t
        except OSError:
            pass

    @staticmethod
    def _isfloat(val: str) -> bool:
        try:
            float(val)
            return True
        except ValueError:
            return False

    def _parse(self, raw: str):
        """Parse a koviz message and push relevant fields onto the event queue."""
        event = {}
        for field in raw.split(','):
            parts = field.split('=', 1)
            if len(parts) != 2:
                continue
            key, val = parts[0].strip(), parts[1].strip()
            if   key == 't'          and self._isfloat(val):
                event['t'] = float(val)
            elif key == 'begin_time' and self._isfloat(val):
                event['begin_time'] = float(val)
            elif key == 'end_time'   and self._isfloat(val):
                event['end_time'] = float(val)
            elif key == 'run':
                event['run'] = val
        if event:
            self._q.put(event)

    def run(self):
        if self._listen_sock is None:
            return
        print(f'[koviz] Listening on {self.HOST}:{self.port}')

        while self._is_running:
            try:
                client, addr = self._listen_sock.accept()
                client.settimeout(2)
                with self._lock:
                    self._client_sock = client
                    self._last_sent_time = None
                print(f'[koviz] Connected: {addr}')
                self._q.put({'connected': True})
            except socket.timeout:
                continue
            except OSError:
                break

            while self._is_running:
                try:
                    raw = self._client_sock.recv(self.MAX_MSG_SIZE).decode()
                except socket.timeout:
                    continue
                if not raw:
                    print('[koviz] Disconnected')
                    # Reset run_dir to None on disconnect so re-checks happen
                    # on later reconnection
                    self.run_dir = None
                    self._q.put({'connected': False})
                    break
                self._parse(raw)

            with self._lock:
                if self._client_sock:
                    self._client_sock.close()
                self._client_sock = None

        self._listen_sock.close()
        print('[koviz] Server shut down')

    def get_port(self):
        return self.port

class KovizInterface():
    """
    Interface class between VIRGO and koviz. Provides management layer
    between the KovizThread which communicates with koviz and the VIRGO
    using class (VirgoDataPlayback)

    Koviz provides a port that this interface can connect to in order
    to send and receive information about the simulation time.
    """
    def __init__(self, port):
        self.state = 'listening'     # connection state
        self.run_dir = None          # What koviz thinks run dir is
        self.expected_run_dir = None # What VIRGO thinks run dir is
        self.run_dir_checked = False # Flag for if run dir check is done
        self._koviz_q = queue.Queue()  # Message queue from koviz
        self._koviz_thread = KovizThread(event_queue=self._koviz_q,
                                         port=port)
        self._koviz_thread.start()

    def set_expected_run_dir(self, expected_run_dir):
        self.expected_run_dir = Path(expected_run_dir).resolve()

    def set_state(self, in_state):
        """
        TODO: use this setter everywhere and check for valid states
        """
        self.state = in_state

    def get_state(self):
        if self._koviz_thread.error_msg != None:
            return(self._koviz_thread.error_msg)
        elif ('disconnect' not in self.state and 'ERROR' not in self.state
              and 'stopped' not in self.state):
            port = self.get_port()
            return (f"{self.state} on port {port}")
        else:
            return self.state

    def get_port(self):
        return(self._koviz_thread.get_port())

    def get_run_dir(self):
        """Return the run directory as koviz knows it to be"""
        return(self.run_dir)

    def send_time(self, time):
        if self.state == 'connected':
            self._koviz_thread.send_time(time)

    def check_run_dir(self):
        """
        If the check hasn't been performed yet, make sure this instance of
        VIRGO and the run_dir from koviz match. If they don't, stop the
        thread permanently and print the error to the user.

        Note that as of 5/2026 it's unclear when/how koviz decides to send
        the run dir information. This function only runs when we have that
        information.
        """
        #print(f"DEBUG: self.run_dir: {self.run_dir} and self.run_dir_checked: {self.run_dir_checked}")
        # We already checked since last connection, or we don't have the run_dir
        # from koviz yet
        if  self.run_dir == None or self.run_dir_checked == True:
            return

        #import pdb; pdb.set_trace()
        if self.run_dir != self.expected_run_dir:
            print(f"ERROR: koviz thinks the run directory is {self.run_dir} "
                f"but VIRGO was given {self.expected_run_dir}. Stopping the koviz "
                f"thread that connects to koviz to prevent confusion. Check "
                f"ports in both apps (VIRGO is listening on {self.get_port()}) "
                f"and make sure they are operating on the same run "
                f"directory")
            state = 'RUN dir mismatch, see console'
            self.stop(reason=state)
        else:
            self.run_dir_checked = True
            return

    def update(self):
        """
        Main update loop getting information from  the koviz interface. If not
        in an ERROR state, poll the socket for the commanded time and return it.
        
        Returns: Floating point time commanded from koviz or None if no koviz
        time commanded
        """
        if 'ERROR' in self.state or 'disconnected by user' in self.state:
            return None
        ret = self.poll()
        if self.state == 'connected':
            self.check_run_dir()
        return ret

    def poll(self):
        """
        Drain the koviz event queue and handle each event.

        Returns the "go to time" if it's specified in the event queue
        """
        go_to_time = None
        while not self._koviz_q.empty():
            try:
                event = self._koviz_q.get_nowait()
                #print(f'DEBUG: [koviz] event is {event}')
            except queue.Empty:
                break
            if 'connected' in event:
                self.state = 'connected' if event['connected'] else 'disconnected'
                #print(f'[koviz] {self.state}')
            if 'run' in event:
                self.run_dir = Path(event["run"]).resolve()
                # Everytime we get a new run_dir, make sure we check against it
                self.run_dir_checked = False
                #print(f'[koviz] run dir: {self.run_dir}')
            if 't' in event:
                go_to_time = float(event['t'])
        #print(f"DEBUG: poll() returning {go_to_time}")
        return go_to_time

    def _seek(self, t: float):
        """Clamp t to the valid sim range and seek virgo to that time."""
        t = max(self.min_sim_time, min(self.max_sim_time, t))
        try:
            self.set_time(t)
            print(f'[koviz] Seeked virgo to t={t:.4f}s')
        except RuntimeError as e:
            print(f'[koviz] Seek failed: {e}')

    def stop(self, reason=''):
        self._koviz_thread.stop()
        self.state = "stopped"
        if reason:
            self.state += ": " + reason

    def start(self):
        self._koviz_thread._is_running = True

