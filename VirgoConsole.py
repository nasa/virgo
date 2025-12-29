import inspect, ast, shlex

from vtkmodules.vtkCommonCore import (
  vtkCommand,
)
from vtkmodules.vtkCommonDataModel import (
  vtkCellArray,
  vtkPolyData,
  vtkPolygon,
)
from vtkmodules.vtkRenderingCore import (
  vtkCoordinate,
  vtkActor2D,
  vtkTextActor,
  vtkPolyDataMapper2D,
)
from vtkmodules.vtkCommonCore import (
  vtkPoints,
)
class VirgoConsole:
    """
    The class which manages the developer console (press ` to open/close).
    This captures keyboard input while the console is open and facilitates
    commands being executed by the user.
    """
    def __init__(self, renderer, interactor, vcc, font_size=16):
        self.prompt = '>'
        self.renderer = renderer
        self.interactor = interactor
        self.vcc = vcc  # VirgoControlCenter, so commands can interact
        self.public_functions = self._build_allowed_methods()
        # TODO probably smarter to add a @hidden decorator and use that rather
        # than keeping a manual list here
        self.hidden_functions = ['stop', 'exit']
        #import pdb; pdb.set_trace()
        # The actor which will be the top-half rectangle background of console
        self.console_bg = None
        # The actor which will contain all written text in the console
        self.text_actor = None
        self.font_size = font_size  # Font size of text
        
        # State variables
        self.is_visible = False
        self.command_buffer = ""      # Buffer as command is being typed in console
        self.full_line_history = []   # List of all full printed lines of cmd history
        self.stdin_history = []       # List of all entered commands in console
        self.stdout_history = []      # List of all returned strings from console
        self.last_command = None      # Contains last entered command in console
        # Reduce oldest self.full_line_history line when reaching this num lines
        self.max_history_lines = 100 
        
        # Create the geometry for the self.console_bg actor
        points = vtkPoints()
        points.InsertNextPoint(0.0, 0.5, 0.0) 
        points.InsertNextPoint(1.0, 0.5, 0.0) 
        points.InsertNextPoint(1.0, 1.0, 0.0) 
        points.InsertNextPoint(0.0, 1.0, 0.0) 
        polydata = vtkPolyData()
        polydata.SetPoints(points)
        polygon = vtkPolygon()
        polygon.GetPointIds().SetNumberOfIds(4)
        for i in range(4):
            polygon.GetPointIds().SetId(i, i)
        cells = vtkCellArray()
        cells.InsertNextCell(polygon)
        polydata.SetPolys(cells)
        coordinate = vtkCoordinate()
        coordinate.SetCoordinateSystemToNormalizedViewport()
        mapper2d = vtkPolyDataMapper2D()
        mapper2d.SetInputData(polydata)
        mapper2d.SetTransformCoordinate(coordinate)
        
        # Map that geometry to self.console_bg
        self.console_bg = vtkActor2D()
        self.console_bg.SetMapper(mapper2d)
        self.console_bg.GetProperty().SetColor(0.0, 0.0, 0.0) 
        self.console_bg.GetProperty().SetOpacity(0.8)
        self.console_bg.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        
        self.text_actor = vtkTextActor()
        self.text_actor.GetTextProperty().SetFontSize(self.font_size)
        self.text_actor.GetTextProperty().SetColor(0.0, 1.0, 0.0) 
        self.text_actor.GetTextProperty().SetFontFamilyToCourier()
        self.text_actor.GetTextProperty().BoldOn()
        self.text_actor.SetPosition(10, 10) 
        coord = self.text_actor.GetPositionCoordinate()
        coord.SetCoordinateSystemToNormalizedViewport()
        coord.SetValue(0.01, 0.52) 
        
        self.console_bg.SetVisibility(False)
        self.text_actor.SetVisibility(False)
        self.renderer.AddActor(self.console_bg)
        self.renderer.AddActor(self.text_actor)
        self.update_text_display()

        # --- EVENT OBSERVATION ---
        # 1. KeyPressEvent: Handles the actual typing logic and command buffer
        self.keypress_tag = self.interactor.AddObserver(vtkCommand.KeyPressEvent, self._on_key_press, 1.0)
        
        # 2. CharEvent: Blocks disruptive keypresses intended for 3D scene 'q', 'e', 'w', 's' etc.
        # We must intercept this to prevent the Default Interactor Style from exiting the app
        self.char_tag = self.interactor.AddObserver(vtkCommand.CharEvent, self._on_char_event, 1.0)

    def get_font_size(self):
        """
        Get font size of console text
        """
        return(self.font_size)

    def set_font_size(self, fs):
        """
        Set font size of console text
        """
        if not isinstance(fs, int) or int(fs) <= 0:
          msg = (f"ERROR: Font size {fs} must be a positive integer")
          raise RuntimeError (msg)
        self.font_size = fs
        self.text_actor.GetTextProperty().SetFontSize(self.font_size)

    def toggle(self):
        """
        Switch the console to visible or not visible
        """
        self.is_visible = not self.is_visible
        self.console_bg.SetVisibility(self.is_visible)
        self.text_actor.SetVisibility(self.is_visible)
        if self.is_visible:
            self.update_text_display()
        self.interactor.Render()

    def update_text_display(self):
        """
        Display the entire text of the console
        """
        visible_history = self.full_line_history[-self.max_history_lines:]
        history_str = "\n".join(visible_history)
        full_text = f"{history_str}\n{self.prompt} {self.command_buffer}_"
        self.text_actor.SetInput(full_text)

    def _on_key_press(self, obj, event):
        """
        Keypress callback for the VirgoConsole. This provides three things:
          1. Bringing the console into/out of view with grave/backtick 
          2. manages the command buffer such that it acts similar to a
             terminal
          3. processes the given command buffer when the return key is hit
        """
        key = obj.GetKeySym()
        char = obj.GetKeyCode()
        
        # --- TOGGLE LOGIC ---
        # Check for backtick key being pressed. 
        if key == "grave":
            self.toggle()
            self._abort_event(obj, self.keypress_tag)
            return

        if not self.is_visible:
            return

        # --- CONSOLE INPUT LOGIC ---
        if key == "Return":
            if self.command_buffer.strip():
                self.last_command = self.command_buffer.strip()
                self.full_line_history.append(f"{self.prompt} {self.command_buffer}")
                self.stdin_history.append(f"{self.command_buffer}")
                
                # Process the command, ret contains any text feedback from
                # execution of the command
                ret = self.process_command(self.last_command)
                if ret:
                    self.full_line_history.append(f"{ret}")
                    self.stdout_history.append(f"{ret}")
                    
                self.command_buffer = "" # Empty the buffer
            else:
                # Add the buffer to the history of previous buffers
                self.full_line_history.append(f"{self.prompt}")
                
        elif key == "BackSpace":
            self.command_buffer = self.command_buffer[:-1]
            
        elif key == "Up":
            if self.stdin_history:
                self.command_buffer = self.stdin_history[-1]

        # Simple tab complete
        elif key == "Tab":
            for pf in self.public_functions:
                if pf.startswith(self.command_buffer):
                    self.command_buffer = pf

        elif len(char) == 1 and ord(char) >= 32 and ord(char) <= 126:
            # Add character to buffer
            self.command_buffer += char
            
        self.update_text_display()
        self.interactor.Render()
        
        # Abort the KeyPress so it doesn't trigger other shortcuts
        self._abort_event(obj, self.keypress_tag)

    def process_command(self, cmd) -> str:
        """
        Process the given console command. For special commands
        """
        ret = ''
        print(f"> {cmd}")
        if cmd == "clear":
            self.full_line_history = []
            return ''
        elif cmd == "help":
            self.print_help()
            return ''

        ret = self.execute(cmd)
        return ret

    def _build_allowed_methods(self):
        allowed = {}
        for name, method in inspect.getmembers(self.vcc, predicate=inspect.ismethod):
            if getattr(method, "is_console_command", False):
                # Use console_name if defined, else method name
                cmd_name = getattr(method, "console_name", name)
                allowed[cmd_name] = method
        return allowed

    def execute(self, line: str) -> str:
        if not line.strip():
            return

        try:
            # Use shlex to properly handle quoted strings: give_item "Health Potion" 5
            tokens = shlex.split(line)
        except ValueError as e:
            msg = f"Parse error: {e}"
            print(msg)
            return msg

        if not tokens:
            return

        command_name = tokens[0]
        args_tokens = tokens[1:]

        if command_name not in self.public_functions:
            msg = (f"Unknown command: {command_name}"
                   f"\nRun help for list of available commands")
            print(msg)
            return msg

        method = self.public_functions[command_name]

        # Parse arguments: support both positional and keyword (key=val)
        positional = []
        keyword = {}

        for token in args_tokens:
            if '=' in token and not token.startswith('=') and not token.endswith('='):
                key, val_str = token.split('=', 1)
                key = key.strip()
                try:
                    value = ast.literal_eval(val_str)
                except (ValueError, SyntaxError):
                    # If literal_eval fails, treat as string (user probably meant it)
                    value = val_str
                keyword[key] = value
            else:
                # Positional argument
                try:
                    value = ast.literal_eval(token)
                except (ValueError, SyntaxError):
                    value = token  # fallback to raw string
                positional.append(value)

        # Now call the method safely
        try:
            result = method(*positional, **keyword)
            if result is not None:
                msg = str(result)
                print(result)
                return msg
        except TypeError as e:
            # Very helpful error for wrong number/type of args
            msg = (f"Argument error: {e}\n"
                   f"Usage: {self._get_signature_help(method)}")
            print(msg)
            return(msg)
        except Exception as e:
            msg = f"Error: {e}"
            print(msg)
            return msg

    def _get_signature_help(self, method):
        import inspect
        try:
            sig = inspect.signature(method)
            return f"{method.__name__} {sig}"
        except:
            return "(no signature available)"

    def print_help(self):
        help = ("Available commands:\n")
        all_function_names = self.public_functions.keys()
        # Determine help message 1st column buffer length (3 is added buffer)
        longest_name_length = len(max(all_function_names, key=len)) + 3
        for name, method in sorted(self.public_functions.items()):
            if name in self.hidden_functions:
                continue
            doc = (method.__doc__ or "").strip()
            if doc:
                help += (f"  {name+' -':>{longest_name_length}} {doc.splitlines()[0]:<10}\n")
            else:
                help +=(f"  {name}\n")
        self.stdout_history.append(help)
        self.full_line_history.append(help)
        return

    def _on_char_event(self, obj, event):
        """
        Intercepts the CharEvent. 
        This is where 'q', 'e', 'w', 'r' are usually processed by VTK.
        """
        if self.is_visible:
            # If console is open, swallow ALL char events to prevent 
            # the app from quitting or changing modes.
            self._abort_event(obj, self.char_tag)

    def _abort_event(self, interactor, tag):
        cmd = interactor.GetCommand(tag)
        if cmd:
            cmd.SetAbortFlag(1)