import re
import numpy as np

from vtkmodules.vtkRenderingCore import (
  vtkFollower,
  vtkPolyDataMapper,
)

from vtkmodules.vtkRenderingFreeType import (
  vtkVectorText
)

class VirgoLabel():
    """
    A VirgoLabel is a string rendered in 3D space inside a Virgo Scene

    TODO: The self.label_follower is intended to always face the camera but
    we haven't hooked it up by running:
      self.label_follower.SetCamera(renderer.GetActiveCamera())
    but in my independent testing this feature doesn't work as intended when
    the vtkFollower() is inside an assembly. For now the label text is positioned
    and rendered with respect to the parent origin but we could explore fleshing
    out this true "always point at the camera" capability. I also tried an approach
    using vtkBillboardTextActor3D but that didn't work out well. See also
    VirgoDataPlaybackController.orient_labels_to_camera for a 3rd failed attempt
    """
    def __init__(self, name, text, scale=0.3):
        self.original_text = str(text) # Copy of original text field upon label creation
        self.name = name    # Name of this label
        self.scale = scale  # Size in units of the text in the scene
        self.local_position  = [0, 0, 0]
        self.local_ypr =  [0, 0, 0]
        self.label_text = vtkVectorText()
        label_mapper = vtkPolyDataMapper()
        label_mapper.SetInputConnection(self.label_text.GetOutputPort())
        self.label_follower = vtkFollower()
        self.label_follower.SetMapper(label_mapper)
        self.label_follower.SetScale(self.scale, self.scale, self.scale)
        self.label_follower.PickableOff()        # Labels can't be picked
        # Flag for if this label's node is currently picked
        self._node_currently_picked = None
        # This is a VirgoDataSource if this label is driven by sim data
        self.data_source = None
        self.variable = None    # variable name in self.data_source to use
        self.faces_camera = None
        self._valid_axes_when = ['always', 'never', 'picked', 'toggled']
        self.when = None
        self.set_text(self.original_text)
        self.enabled = True
        self.disable()  # Turn it off by default

    def set_scale(self, scale):
        self.scale = scale
        self.label_follower.SetScale(self.scale, self.scale, self.scale)

    def is_enabled(self):
        return self.enabled

    def disable(self):
        """Disable this label"""
        if not self.when or self.when == 'always':
            return
        self.enabled = False
        self.label_follower.SetVisibility(False)

    def enable(self):
        """Enable this label"""
        if not self.when or self.when == 'never':
            return
        if self.when == 'picked' and not self._node_currently_picked:
            return

        self.enabled = True
        self.label_follower.SetVisibility(True)

    def get_follower(self):
        """Get the self.label_follower member"""
        return(self.label_follower)

    def set_text(self, text):
        """Set the text the label displays"""
        self.label_text.SetText(f"{text}")

    def set_position(self, position):
        """
        Set the position of the label (relative to it's parent)
        """
        self.local_position = position
        self.label_follower.SetPosition(self.local_position)

    def get_position(self):
        """
        Get the position of the label (relative to it's parent)
        """
        return(self.label_follower.GetPosition())

    def set_yaw_pitch_roll(self, yaw_pitch_roll):
        """
        Set the yaw-pitch-roll rotation (Z-Y-X order)
        of the label (relative to it's parent)
        """
        self.local_ypr = yaw_pitch_roll
        rz, ry, rx = self.local_ypr
        self.label_follower.RotateZ(rz)
        self.label_follower.RotateY(ry)
        self.label_follower.RotateX(rx)

    def set_color(self, color):
        """
        Set the color of the label text
        """
        self.label_follower.GetProperty().SetColor(color)

    def set_faces_camera(self, fc):
        """
        Set the flag for if this label always faces the camera
        Accepted values are governed by rules in VirgoDictVerifier
        """
        self.faces_camera = fc

    def set_when(self, wh):
        """
        Set the mode for when this label should be displayed
        Accepted values are governed by rules in VirgoDictVerifier
        """
        self.when = wh
        if self.when == 'never':
            self.disable()
        elif self.when == 'picked' and not self._node_currently_picked:
            self.disable()
        elif self.when == 'always':
            self.enable()

    def get_when(self):
        """
        Get the mode for when this label should be displayed
        """
        return(self.when)

    def get_faces_camera(self):
        return(self.faces_camera)

    def set_data_source(self, data_source):
        """Set the data source of the label

        A data_source of None is supported and means "no data source"

        Args:
            data_source (VirgoDataSource): Set self.data_source to this
        """
        self.data_source = data_source
        if self.data_source and not self.data_source.is_initialized():
            self.data_source.initialize()

    def initialize(self, world_time, node_world_position):
        """
        Forcibly update the label's state regardless of whether it's enabled or
        not. This function is meant to be called as the VIRGO scene comes up for
        the first time

        Args:
          world_time: World time
          node_world_position:  World position of this label's node
        """
        orig_state = self.enabled   # Store off original enabled state
        self.enabled = True         # Force the label on for the update
        self.update(world_time, node_world_position) # Update the label
        self.enabled = orig_state   # Set enable state to orig state
        #import pdb; pdb.set_trace()
        # Set the state
        if self.enabled:
            self.enable()
        else:
            self.disable()

    def set_currently_picked(self, picked=True):
        """
        Set value of internally tracked currently picked flag
        """
        self._node_currently_picked = picked

    def update(self, world_time, node_world_position):
        """
        Update this label by making the sure the text is up to date
        and moving the label follower to it's latest position
        """
        #print(f"DEBUG: self._node_currently_picked: {self._node_currently_picked}")
        if not self.enabled:
            return
        self.update_text(world_time)
        # If the label always faces the active camera that means it's NOT part
        # of its node's vtkassembly and we therefore we need to add the node's
        # world position to the label's local position.
        if self.get_faces_camera() == True:
            #import pdb; pdb.set_trace()
            self.get_follower().SetPosition(
                node_world_position + self.local_position)
        else:
            self.get_follower().SetPosition(self.local_position)

    def update_text(self, world_time):
        """
        Update this label with variable information from the data source

        This is the function which updates text strings relying on a data
        source with actual values from that data source. Strings containing
        {<variable>:<format>} notation are parsed and <variable> is replaced
        with the value of <variable> at world_time per the VirgoDataSource
        internal mechanisms. Python formatting is then applied based on the
        <format> string. The result is appied to the text part of the label
        using set_text()
    
        Args:
            world_time (double): World time of the scene. This is ignored if
            this label's self.data_source == None
        """
        #import pdb; pdb.set_trace()
        if self.data_source == None:
            self.set_text(f"{self.original_text}")
            return
        self.data_source.set_current_time(world_time)
        if not self.data_source.is_there_additional_data():
            msg = (f"ERROR: self.data_source.additional_data is unexpectedly" 
                    " empty for label {self.name}!")
            raise RuntimeError (msg)

        text = str(self.original_text)
        found_clauses = self.find_clauses(text)
        for cs in found_clauses:
            value = self.data_source.get_additional_data(cs.var)
            if self.is_not_primitive(value):
              if self.contains_any_letter_except_s(cs.fmt):
                msg = (f"ERROR: {cs.var} is {type(value)}, not a primitive number " 
                       f"so only string can be used in format string (you gave: {cs.fmt})."
                       f" Tip: Use alias_name[index] to use individual array values in"
                       f" your label text: field."
                       )
                raise RuntimeError (msg)
              value = str(value) # Must convert non-primitives to string
            raw_string = "{myval:" + cs.fmt + "}"  # 2 decimal places
            result = raw_string.format(myval=value)
            text = text.replace('{'+cs.clause+'}', result)

        self.set_text(text)

    @staticmethod
    def contains_any_letter_except_s(input_string):
        # This checks if any character in the string, when lowercased, is not 's'
        return any(char.lower() != 's' for char in input_string if char.isalpha())

    @staticmethod
    def is_not_primitive(variable):
        """
        Checks if a variable is a 'non-primitive' (mutable/compound) type.
        """
        # Define a set of "primitive" (immutable) types
        primitive_types = (int, float, str, bool, type(None))
        
        # Check if the variable is NOT an instance of any of the primitive types
        if not isinstance(variable, primitive_types):
            return True
        else:
            return False

    @staticmethod
    def find_clauses(text):
        """Split a string in {<variable>@<time>:<format>} notation into clauses
    
        Given a string text, find all python format strings enclosed
        in curly braces and return a list of ClauseSplit instances
        representing the clause, variable, time, and format content
        separately.
         Example 1:
          text = "hello {myvar[0]@t1}"
          find_clauses(text) = [ cs0 ]
            where cs0 is a ClauseSplit with members:
              clause = myvar[0]@t1
              var    = myvar[0]
              time   = t1
              fmt    = ''
         Example 2:
          text = "hello {myvar[0]@t1:.2}"
          find_clauses(text) = [ cs0 ]
            where cs0 is a ClauseSplit with members:
              clause = myvar[0]@t1:.2
              var    = myvar[0]
              time   = t1
              fmt    = '.2'
         Example 3:
          text = "hello {myvar[0]@t1:.2} {myvar[1]@t2:.1f}"
          find_clauses(text) = [ cs0, cs1 ]
            where cs0 is a ClauseSplit with members:
              clause = myvar[0]@t1:.2
              var    = myvar[0]
              time   = t1
              fmt    = '.2'
            and cs1 is a ClauseSplit with members:
              clause = myvar[1]@t2:.1f
              var    = myvar[1]
              time   = t2
              fmt    = '.1f'
    
        A ClauseSplit class is local to the scope of this function and
        contains the original clause found, the variable part, the time
        part, and the format part. See class definition below.
    
        Args:
            text (str): String to search for clauses
    
        Returns:
            list: List of ClauseSplit class instances resulting from the
                  split of one or more clauses
    
        Raises:
            RuntimeError: If parsing of text fails
        """
        class ClauseSplit:
            """Container class for clause split"""
            def __init__(self, clause):
                self.clause = clause
                self.var = ''
                self.time = ''
                self.fmt = ''
    
        clauses = []
        found_fstrings = re.findall(r'\{(.*?)\}', text)
        if found_fstrings:
            # replace all {} fields with values from the data source
            for fstring in found_fstrings:
                cs = ClauseSplit(fstring)
                
                # First split by ':' to separate format from var@time
                colon_split = fstring.split(':')
                if len(colon_split) == 1:
                    # No format specified
                    var_time_part = colon_split[0]
                    cs.fmt = ''
                elif len(colon_split) == 2:
                    # Format specified
                    var_time_part, fmt = colon_split
                    cs.fmt = fmt
                else:
                    msg = (f"ERROR: Bad formatting in text: {text}. Simple "
                           "variable aliases and python format strings are "
                           "supported but mathematical operations are not")
                    raise RuntimeError(msg)
                
                # Now split var_time_part by '@' to get variable and time
                at_split = var_time_part.split('@')
                if len(at_split) == 1:
                    # No time specified (backward compatibility)
                    cs.var = at_split[0]
                    cs.time = ''
                elif len(at_split) == 2:
                    # Time specified
                    var, time = at_split
                    cs.var = var
                    cs.time = time
                else:
                    msg = (f"ERROR: Bad formatting in text: {text}. Expected "
                           "format {{variable@time:format}} but found multiple "
                           "'@' symbols in clause")
                    raise RuntimeError(msg)
                
                clauses.append(cs)
        return clauses