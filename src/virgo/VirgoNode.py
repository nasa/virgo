import numpy as np
from typing import List

from .VirgoLabel import VirgoLabel
from .VirgoTrail import VirgoTrail
from .VirgoAxes  import VirgoAxes

from vtkmodules.vtkRenderingCore import (
  vtkActor,
  vtkAssembly,
  vtkPolyDataMapper,
)
from vtkmodules.vtkCommonMath import (
  vtkMatrix4x4,
)
from vtkmodules.vtkCommonTransforms import (
  vtkTransform,
)
from vtkmodules.vtkRenderingAnnotation import (
  vtkAxesActor,
)
from vtkmodules.vtkFiltersHybrid import (
  vtkPolyDataSilhouette,
)

class VirgoSceneNode():
    """
    This class provides a vtkActor and vtkAssembly Node/Graph system such that
    actors are automatically added to assemblies and children (other actors and
    assemblies) can be nested underneath a node as well. This provides the basis
    for building trees (Directed Acyclic Graphs) of actors in the Virgo
    framework and allowing those parts of an assembly to move independently as
    well as the entire tree as a unit.

    This class also provides an intermediate layer between the actors in the scene
    and the rendering provided by higher level Virgo classes
    """
    # Order of magnitude unit length of a self.assembly is considered a
    # celestial body
    celestial_body_oom = 1e6

    def __init__(self, name=None, actor=None, axes=True):
        self.verbosity=1  # TODO make adjustable
        self.fs = 14      # font size
        self.actor = actor
        self.assembly = vtkAssembly()     # The assembly associated with this node
        self.axes_scale = 0.5  # Default scale factor for axes
        self.axes_when = 'toggled'
        self._valid_axes_when = ['always', 'never', 'picked', 'toggled']
        self.axes_style = 'cylinder'
        self.axes_affect_opacity = True
        self.axes = None
        # Internal flag for if this node is currently picked
        self._currently_picked = False
        self.transpose_dcm = True
        # Rendering layer this node's self.assembly will be added to
        self.layer = None

        if axes:
            self.axes = self.create_axes()

        self.label_text_scale = 0.3
        self.labels = {}

        self.set_name(name)

        # Opacity (0-1) of the actor when this node gets created
        self._initialized_opacity = None
        # Full X,Y,Z scale of actor when this instance is created
        self._initialized_scale = None
        # User defined scale (one float) of the associated with this node
        self.user_scale =  1.0
        if self.actor:
            self._initialized_opacity = self.actor.GetProperty().GetOpacity()
            self._initialized_scale = self.actor.GetScale()
            
        # Opacity (0-1) of this actor before manipulating it to a new value
        self._last_opacity = self._initialized_opacity
        # Opacity an actor must be above to trigger reduced opacity when showing
        # axes (which can lie within the bounds of actor geometry) 
        self._actor_opacity_threshold = 0.8 

        if self.actor:
            self.compute_actor_bounds()
            self.assembly.AddPart(self.actor)
        if self.axes:
            self.assembly.AddPart(self.axes.get_assembly())
            if self.actor:
                self.set_axes_length_auto()

        # self.local_transform represents the local transformation of this Node,
        # meaning the position/rotation/scale of this node relative to it's
        # parent, or world coordinates if parent == None. It is stored as a member
        # because the VTK rendering pipeline has no way to query the world state
        # information of an actor inside an assembly after it's moved, so we have
        # to store the transformation in each node to be able to get that information
        self.local_transform = vtkTransform()
        self.local_transform.Identity()
        self.assembly.SetUserTransform(self.local_transform)

        # Stores "last color" if needed
        self.last_color = None
        self.silhouette_actor = None
        self.silhouette_polydata = None
        # Number of vertices self.actor must stay under for a silhoutte to be created
        self.silhouette_vert_limit = int(1.0e5)
        self.create_silhouette()

        # Internal members for bounding box information
        self.bb = []   # Full bounds from self.assembly.GetBounds
        self.bb_longest_length = None
        self.bb_shortest_length = None
        self.bb_x_length = None
        self.bb_y_length = None
        self.bb_z_length = None
        self.is_celestial_body = False

        # If not None, self.parent is another VirgoSceneNode instance that this node
        # is parented to.
        self.parent = None
        self.children = []

        self.data_source = None
        self.static = True

        self.trail = None # May contain a VirgoTrail instance

    def create_silhouette(self):
        """
        Create the silhouette actor which is used to highlight self.actor

        Note this is skipped if:
         1. There is no actor for this node
         2. There is an actor but it's not pickable
         3. The number of vertices in self.actor is too high as we've found
            it significantly impacts performance for complex meshes
        """
        if not self.actor:
            return
        if not self.actor.GetPickable():
            return
        num_vertices = self.actor.get_num_vertices()
        if (num_vertices == None):
            if self.verbosity > 1:
                print(f"Unable to determine number of vertices for actor "
                      f"{self.actor.name}. Skipping highlight silhouette"
                      f"Picking will result in color change of mesh only."
                      )
        elif (num_vertices > self.silhouette_vert_limit):
            if self.verbosity > 1:
                print(f"Skipping highlight silhouette for {self.actor.name} as "
                      f"it has more vertices than the practical limit "
                      f"({num_vertices}/{self.silhouette_vert_limit}). "
                      f"Picking will result in color change of mesh only."
                      )
            return
        mapper = self.actor.GetMapper()
        mapper.update()
        input_connection = mapper.GetInputConnection(0, 0)
        self.silhouette_polydata = vtkPolyDataSilhouette()
        self.silhouette_polydata.SetEnableFeatureAngle(True)
        # TODO this SetFeatureAngle could be adjustable in the scene dict if we
        # wanted, it affects how sharp edges are highlighted
        self.silhouette_polydata.SetFeatureAngle(20.0)
        self.silhouette_polydata.SetInputConnection(input_connection)

        sil_mapper = vtkPolyDataMapper()
        sil_mapper.SetInputConnection(self.silhouette_polydata.GetOutputPort())

        self.silhouette_actor = vtkActor()
        self.silhouette_actor.SetMapper(sil_mapper)
        self.silhouette_actor.GetProperty().SetColor(1.0, 1.0, 0.0)
        self.silhouette_actor.GetProperty().SetLineWidth(5)
        self.silhouette_actor.GetProperty().SetDiffuse(0.0)
        self.silhouette_actor.GetProperty().SetAmbient(1.0)
        self.silhouette_actor.SetVisibility(False)

        # Apply any transformations that self.actor has to the sillhouette
        self.silhouette_actor.SetPosition(self.actor.GetPosition())
        self.silhouette_actor.SetOrientation(self.actor.GetOrientation())
        self.silhouette_actor.SetScale(self.actor.GetScale())
        self.assembly.AddPart(self.silhouette_actor)

    def set_currently_picked(self, picked=True):
        """
        Set value of internally tracked currently picked flag
        """
        self._currently_picked = picked
        for label in self.labels:
            self.labels[label].set_currently_picked(picked)

    def set_transpose_dcm(self, value=True):
        """
        Set value of internally tracked currently picked flag
        """
        self.transpose_dcm = bool(value)

    def set_user_scale(self, us):
        """
        Set the user scale for this node. This is a single float
        multiplier used for scaling the size of nodes
        """
        self.user_scale = us

    def set_highlight_color(self, color):
        """
        Set the color of the highlight for this node. If self.silhoutte_actor exists,
        change it's color as well.
        """
        self.highlight_color = color
        if self.silhouette_actor and self.highlight_color:
            self.silhouette_actor.GetProperty().SetColor(
                self.highlight_color[0], self.highlight_color[1], self.highlight_color[2])

    def set_highlight_thickness(self, thickness):
        """
        Set the thickness of the line produced by self.silhouette_actor
        """
        if self.silhouette_actor:
            self.silhouette_actor.GetProperty().SetLineWidth(thickness)

    def highlight_on(self):
        """
        Turn highlighting on for this node. If a silhouette actor exists, make it
        visible, otherwise turn the object itself the color of self.highlight_color
        """
        if self.silhouette_actor:
            self.silhouette_actor.SetVisibility(True)
        else:
            self.last_color = self.actor.GetProperty().GetColor()
            self.actor.GetProperty().SetColor(
                self.highlight_color[0], self.highlight_color[1], self.highlight_color[2])

    def highlight_off(self):
        """
        Turn highlighting off for this node. If a silhouette actor exists, make it
        not visible, otherwise turn the object itself the color of self.last_color
        """
        if self.silhouette_actor:
            self.silhouette_actor.SetVisibility(False)
        else:
            self.actor.GetProperty().SetColor(
                self.last_color[0], self.last_color[1], self.last_color[2])

    def set_name(self, name):
        if name == None:
            name = "Unnamed Node"
        self.name = str(name)

    def add_label(self, name, text, position=[0.0, 0.0, 0.0], ypr=[0.0, 0.0, 0.0],
                  scale=0.3, color=[1.0, 1.0, 1.0],faces_camera=False, when='always'):
        """
        Add a label to this node's self.labels dict

        Args:
          text (str): String representing the label's content

        Returns: The label added to this node which is also stored in self.labels
        """
        self.labels[name] = VirgoLabel(name=name, text=text, scale=scale)
        # TODO: if text is found in self.vds.additional_data, call other functions
        # so that self.labels[name].update() grabs the value automatically
        self.labels[name].set_position(position)
        self.labels[name].set_yaw_pitch_roll(ypr)
        self.labels[name].set_color(color)
        self.labels[name].set_faces_camera(faces_camera)
        self.labels[name].set_when(when)
        #import pdb; pdb.set_trace()
        follower = self.labels[name].get_follower()
    
        # If this label doesn't always face the camera is is added to this node's
        # vtkAssembly as it travels within the node's local frame. Note that if
        # it does face the camera it gets added as an independent actor to the
        # node's renderer one level up from here
        if self.labels[name].get_faces_camera() == False:
            self.assembly.AddPart(follower)

        return self.labels[name]

    def get_label(self, name):
        """Get a label by name"""
        if name not in self.labels:
            msg = (f"ERROR: Label {name} in node {self.name} not found in self.labels!")
            raise RuntimeError (msg)
        return self.labels[name]

    def get_labels(self):
        return self.labels

    def initialize_labels(self, world_time):
        """
        Initialize all labels in this node

        Args:
          world_time: World time
        """
        world_pos = np.array(self.get_world_position())
        for name, label in self.labels.items():
            label.initialize(world_time, world_pos)

    def update_labels(self, world_time):
        """
        Update all labels in this node
        """
        world_pos = np.array(self.get_world_position())
        
        for name, label in self.labels.items():
            label.update(world_time, world_pos)

    def is_static(self):
        return (self.data_source is None)

    def set_data_source(self, data_source):
        """
        Set the data source of this node

        TODO: Check that data_source has the functions required by by the
        base class and if not raise an exception
        """
        self.data_source = data_source

    def add_child(self, child):
        """
        Add child (another instance of VirgoSceneNode) to this Node,
        adding it as both a child and the child's assembly as a part
        of this assembly
        """
        if self == child:
            msg = (f"ERROR: Cannot add child {child} to {self} because "
                  f"self-referential loops are not supported.")
            raise RuntimeError (msg)
        child.parent = self
        self.assembly.AddPart(child.assembly)
        self.children.append(child)

    def initialize(self, world_time):
        """
        Initialize this node
        """
        self.layer = 'foreground'
        self.update(world_time)
        if self.labels:
            self.initialize_labels(world_time)
        # Configure the axes for this node
        if self.axes:
            if self.axes_when == 'always':
                self.axes.show()
            elif (self.axes_when == 'never' or 
                  self.axes_when == 'toggled'):
                self.axes.hide()

    def compute_actor_bounds(self):
        """
        Compute the physical bounds of interest for this node's assembly

        If the longest bounding box length is greater than a celstial body,
        set self.is_celestial_body to True
        """
        # The bounding box of the assembly
        self.bb = self.actor.GetBounds()
        self.bb_x_length = abs(self.bb[0] - self.bb[1])
        self.bb_y_length = abs(self.bb[2] - self.bb[3])
        self.bb_z_length = abs(self.bb[4] - self.bb[5])
        self.bb_longest_length = max(self.bb_x_length,
                                     self.bb_y_length,
                                     self.bb_z_length)
        self.bb_shortest_length = min(self.bb_x_length,
                                      self.bb_y_length,
                                      self.bb_z_length)

        if self.bb_longest_length > self.celestial_body_oom:
            self.is_celestial_body = True

    def update(self, world_time):
        """
        Update this node with data from self.data_source based on world_time
        """

        # If there's a self.data_source, drive the node with it
        if self.data_source:
            self.data_source.set_current_time(world_time)
            pos   = self.data_source.get_current_position()
            rot   = self.data_source.get_current_rotation()
            scale = self.data_source.get_current_scale()
            opacity = self.data_source.get_current_opacity()
            #import pdb; pdb.set_trace()
            if self.verbosity > 3:
                print(f"In VirgoSceneNode.update() with world_time: {world_time} and")
                print(f"  data_source pos:   {pos}")
                print(f"  data_source rot:   {rot}")
                print(f"  data_source scale: {scale}")
                if self.verbosity > 4:
                    self.report()

            # Pose the node with this data
            self.set_pose(pos=pos, dcm=rot, transpose_dcm=self.transpose_dcm,
                          scale=scale, opacity=opacity)

        if self.trail:
            self.trail.update(self.get_world_position())
        if self.labels:
            self.update_labels(world_time)

    def dump_assembly(self, asm, indent=0):
        """
        Recursive dump of debug information about this Node's assembly and
        it's nested assemblies

        TODO: I think this would be better refactored into a recursive node
        dump rather than an assembly dump. The node dump could contain info
        about the assembly but this currently is missing a lot of info about
        the node itself.
        """
        parts = asm.GetParts()
        parts.InitTraversal()
        for i in range(parts.GetNumberOfItems()):
            prop = parts.GetNextProp()
            prefix = "  " * indent
            print(f"{prefix}- {prop.GetClassName()}")
            if hasattr(prop, 'name'):
                print(f"{prefix}Name: {prop.name}")
            matrix = prop.GetMatrix()
            print(f"{prefix}Matrix:")
            for i in range(4):
                print(f"{prefix}{[matrix.GetElement(i, j) for j in range(4)]}")
            # If this part is another assembly, recurse into it
            if isinstance(prop, vtkAssembly):
                #print(f"{prefix}Recursing into {prop}...")
                self.dump_assembly(prop, indent + 1)
            elif isinstance(prop, vtkActor):
                # Optional: print some extra info about actors
                bounds = prop.GetBounds()
                print(f"{prefix}Bounds: {bounds}")
                print(f"{prefix}Visibility: {prop.GetVisibility()}")
                print(f"{prefix}Pickable: {prop.GetPickable()}")


    def report(self):
        print(f"==== BEGIN  VirgoSceneNode Report for Node {self.name} ===================")
        matrix = self.assembly.GetMatrix()
        print(f"self.layer: {self.layer}")
        print("Top level assembly transform matrix:")
        for i in range(4):
            print([matrix.GetElement(i, j) for j in range(4)])
        print("Top level Bounds:", self.assembly.GetBounds())
        print("Top level Visibility:", self.assembly.GetVisibility())
        print("Top level Pickable:", self.assembly.GetPickable())
        print(f"==== BEGIN  Recursive Assembly Dump for Node {self.name} =================")
        self.dump_assembly(self.assembly)
        print(f"==== END    VirgoSceneNode Report for Node {self.name} ===================")

        
    def set_pose(self, pos=None, ypr=None, dcm=None, transpose_dcm=True,
                 scale=None, opacity=None):
        """
        Manipulate self.local_transform to provide position, rotation, and
        scale adjustments to this Node's self.assembly. Only one rotation method
        (dcm or ypr) may be specified, but in both approaches the node is moved
        by pos first, then the rotation is applied about the pos's origin at that
        new location.

        Args:
          pos: [X,Y,Z] position vector describing where to move this node relative to
               it's parent (or world coordinates if this node has no parent)
          ypr: [Yaw,Pitch,Roll] ordered Euler rotation to apply to this node
               about it's parent's frame axes. Applied after pos: is applied.
          dcm: 3x3 Direction Cosine Matrix representing the rotation to be applied
               to this node. This can be a list of lists but will be converted to
               a numpy matrix in this function if it isn't already. Note that ypr
               and dcm are mutually exclusive and only one can be specified.
          scale: [X,Y,Z] floating point mulitplier describing how to scale the
               assembly of this node in the X,Y,Z directions. Defaults to None.
          transpose_dcm: Boolean for whether dcm should be transposed before passed
               into VTK's matrix.SetElement() function. VTK expects active 
               transformations but aerospace and robotics applications often provide
               passive transformations to describe coordinate frame rotations. Set
               to false if you are using active rotation matrices
          opacity: Single floating point value between 0.0-1.0 describing the opacity
               to be applied this node's actor
        """
        if ypr is not None and dcm is not None:
            raise ValueError("Cannot specify both rot and dcm.")
        # Ensure the given list is in numpy array form
        if dcm is not None and not isinstance(dcm, np.ndarray):
            dcm = np.array(dcm)

        self.local_transform.Identity()
        self.local_transform.PostMultiply()

        # If dcm is given, provide it and pos in a single transform
        if dcm is not None:
            # Transpose the dcm making it an active rotation which VTK expects
            if transpose_dcm:
                dcm = dcm.T
            matrix = vtkMatrix4x4()
            matrix.Identity()
            for i in range(3):
                for j in range(3):
                    matrix.SetElement(i, j, dcm[i][j])
            if pos is not None:
                matrix.SetElement(0, 3, pos[0])
                matrix.SetElement(1, 3, pos[1])
                matrix.SetElement(2, 3, pos[2])
            self.local_transform.SetMatrix(matrix)
        # If dcm is not given, use the Translate() approach
        elif pos is not None:
            self.local_transform.Translate(*pos)

        # The approach below is needed such that the rotation is applied
        # after position is applied. A simple Rotate*() after Translate()
        # results in a rotation about the pre-translation frame, which is
        # not desired here -Jordan 4/2026
        if ypr is not None:
            rz, ry, rx = ypr
            # Build rotation-only transform
            rot_transform = vtkTransform()
            rot_transform.RotateZ(rz)
            rot_transform.RotateY(ry)
            rot_transform.RotateX(rx)
            rot_matrix = rot_transform.GetMatrix()
        
            # Extract current translation, apply rotation around that point
            matrix = vtkMatrix4x4()
            matrix.DeepCopy(self.local_transform.GetMatrix())
        
            rot_only = vtkMatrix4x4()
            for i in range(3):
                for j in range(3):
                    rot_only.SetElement(i, j, rot_matrix.GetElement(i, j))
        
            vtkMatrix4x4.Multiply4x4(matrix, rot_only, matrix)
            self.local_transform.SetMatrix(matrix)

        if scale is not None:
            self.set_scale(scale)

        # if specified, adjust the opacity of the actor
        if opacity != None:
            self.actor.GetProperty().SetOpacity(float(opacity))

    def set_scale(self, scale):
        """
        Args:
          scale: [X,Y,Z] floating point multiplier describing how to scale the
               assembly of this node in the X,Y,Z directions, OR a single
               float which will be applied equally in all directions.
        """
        if isinstance(scale, list) or isinstance(scale, tuple):
            self.local_transform.Scale(*scale)
        elif isinstance(scale, float):
            self.local_transform.Scale(scale, scale, scale)

    def get_world_position(self, local_point=(0.0, 0.0, 0.0)):
        """
        Transform local_point (in this node's local coords) into world coordinates
        by applying local transforms from this node upward to the root.
        """
        p = tuple(local_point)
        node = self
        while node is not None:
            p = node.local_transform.TransformPoint(p)
            node = node.parent
        return p
    
    def get_local_position(self):
        """
        Return this node's local position (translation relative to its parent).
        """
        return self.local_transform.GetPosition()

    def create_axes(self):
        """
        Create an axes
        """
        # Create axes actor
        self.axes = VirgoAxes()

        return self.axes
        
    def set_axes_pickable_on(self):
        # TODO: This function never worked right with vtkAxesActor, should
        # be revisited in VirgoAxes one day - Jordan 7/2026
        #if self.axes:
        #    self.axes.PickableOn()
        pass

    def set_axes_pickable_off(self):
        # TODO: This function never worked right with vtkAxesActor, should
        # be revisited in VirgoAxes one day - Jordan 7/2026
        pass
        #if self.axes:
        #    self.axes.PickableOff()

    def set_axes_length(self, length: List[float]):
        if not isinstance(length, list):
            msg = (f"ERROR: Node {self.name}'s set_axes_length() must be given "
                   f"a 3-element list of positive floats.")
            raise RuntimeError (msg)
        self.axes.set_length(xlen=length[0], ylen=length[1], zlen=length[2])

    def set_axes_length_auto(self):
        '''
        Autosize self.axes based on this node's bounding box, setting it to
        half the length of the average length of the bounding box
        '''
        # No actor
        if not self.axes:
            return
        # No bounding box
        if not self.actor:
            return
        avg_bb_len = (self.bb_longest_length + self.bb_shortest_length)/2/2
        self.axes.set_length(xlen=avg_bb_len, ylen=avg_bb_len, zlen=avg_bb_len)

    def set_axes_when(self, when):
        if not self.axes:
            return
        if when not in self._valid_axes_when:
            msg = (f"ERROR: Node {self.name} axes 'when' setting {when} "
                   f"not recognized. Must be: {self._valid_axes_when}")
            raise RuntimeError (msg)
        self.axes_when = when
        # If never, remove the entire instance
        if self.axes_when == 'never':
            self.axes.set_enabled(False)
        elif self.axes_when == 'always':
            self.axes.set_enabled(True)

    def set_axes_style(self, style):
        if not self.axes:
            return
        if style == 'line':
            self.axes.set_style(style='line')
        elif style == 'cylinder':
            self.axes.set_style(style='cylinder')

        
        
    def set_axes_affect_opacity(self, affect_opacity):
        self.axes_affect_opacity = bool(affect_opacity)

    def get_axes(self):
        return self.axes

    def are_axes_visible(self):
        if not self.axes:
            return False
        return(self.axes.get_visibility())

    def get_root_node(self):
        """
        Get this node's root VirgoSceneNode (highest parent level)
        Returns self is this node is a root node
        """
        if self.parent == None:
            return(self)
        else:
            self.get_root_node(self.parent)

    def set_layer(self, layer):
        """
        TODO: do we need this?
        """
        if self.parent:
            msg = (f"ERROR: Node {self.name} cannot set_layer since it"
                   f"isn't a root node. Parent: {self.parent.name}")
            raise RuntimeError (msg)
        else:
            #print(f"   {self.name} is now in {layer}")
            if self.verbosity > 3:
                print(f" {self.name} is now in {layer}")
            self.layer = layer

    def get_layer(self):
        """
        Get this node's layer. Only root nodes (no parent)
        can have a defined layer, so find it if needed.
        """
        if self.parent:
            return(self.parent.get_layer())
        else:
            return(self.layer)

    def hide_labels(self):
        for label in self.labels:
            self.labels[label].disable()

    def show_labels(self):
        for label in self.labels:
            #import pdb; pdb.set_trace()
            self.labels[label].enable()

    def are_labels_visible(self):
        # TODO: Loose check, if one is visible they all are
        for label in self.labels:
            if self.labels[label].is_enabled():
                return True
        return False

    def is_trail_visible(self):
        if self.trail:
            return self.trail.is_visible()

    def hide_trail(self):
        if self.trail:
            return self.trail.hide()

    def show_trail(self):
        if self.trail:
            return self.trail.show()

    def hide_axes(self):
        """
        Hide the axes for this node, if self.axes_when permits it

        TODO: See TODO in show_axes
        """
        if not self.axes or self.axes_when == 'always':
            return

        self.axes.hide()
        if self.actor and self.axes_affect_opacity == True:
            self.actor.GetProperty().SetOpacity(self._last_opacity)
        #print(f"DEBUG: in hide_axes and axes bb is {self.axes.GetBounds()}")
        #print(f"DEBUG: in hide_axes and assembly bb is {self.assembly.GetBounds()}")

    def show_axes(self):
        """
        Show the axes for this node, if self.axes_when permits it

        TODO: This approach doesn't allow opacity to be reduced when
        self.axes_when == 'always'. See the calling function as well
        and consider a different approach where opacity can be toggled
        independently of the axes.
        """
        if not self.axes or self.axes_when == 'never':
            return
        if self.axes_when == 'picked' and not self._currently_picked:
            return
        # Make the entire axes visible
        self.axes.show()
        #print(f"DEBUG: in show_axes and axes bb is {self.axes.GetBounds()}")
        #print(f"DEBUG: in show_axes and assembly bb is {self.assembly.GetBounds()}")
        if self.actor and self.axes_affect_opacity == True:
            self._last_opacity = self.actor.GetProperty().GetOpacity()
            if self._last_opacity > self._actor_opacity_threshold:
                new_opacity = self._last_opacity / 2.0
                if self.verbosity > 2:
                    print(f"INFO: Reducing opacity of {self.name} to {new_opacity} "
                      f"for increased visibility. Use axes: affect_opacity: to "
                      f"turn this off")
                self.actor.GetProperty().SetOpacity(new_opacity)

    def create_trail(self, color=[1.0, 1.0, 1.0], thickness=2, opacity=1.0):
        self.trail = VirgoTrail(node=self, color=color, thickness=thickness,
                                opacity=opacity)
        return self.trail
        
    def toggle_trail_segments_debug_color(self):
        if not self.trail:
            return

        if self.trail.segment_debug_colors:
            self.trail.uncolor_the_segments()
        else:
            self.trail.color_the_segments()


    def get_current_position(self):
        pos = None
        if self.data_source:
            pos = self.data_source.get_current_position()
        return pos

    def reset_trail(self):
        """
        Remove all lines/points from this actor's trail
        """
        if self.trail:
            self.trail.reset_trail()

class VirgoSceneNodeVector(VirgoSceneNode):
    """
    Derived class which defines specific methods for a vector application
    of a VirgoSceneNode
    """
    def __init__(self, name, actor=None):
        super().__init__(name=name, actor=actor)
        self.VERY_SMALL = 1e-10
        self.mode = 'unit'

    def update(self, world_time):
        """
        Update this vector node with data from self.data_source based on
        world_time

        Overrides base class update() method
        """
        # Update any labels associated with this node
        if self.labels:
            self.update_labels(world_time)

        if not self.data_source:
            return

        # Query self.data_souce for the data we need to drive the node
        self.data_source.set_current_time(world_time)
        pos  = self.data_source.get_current_position()
        opacity = self.data_source.get_current_opacity()
        self.set_vector_pose(vec=pos, opacity=opacity)
        if self.verbosity > 3:
            print(f"In VirgoSceneNodeVector.update() with world_time: {world_time} and")
            print(f"  data_source pos:   {pos}")
            if self.verbosity > 4:
                self.report()


    def set_vector_pose(self, vec, opacity=None):
        """
        Pose (orient) self.local_transform according to the x,y,z values
        in vector vec. This is the only way in VTK to take an arrow mesh
        and orient it along a vector's direction. Also perform other
        actor actions like applying scale and opacity
        Args:
          vec: [X,Y,Z] position vector describing where the tip of the vector
               is relative to it's parent (or world coords if this node has
               no parent)
          opacity: Single floating point value between 0.0-1.0 describing the
               opacity to be applied this node's actor
        """
        # Normalize vector to get direction
        v = np.array(vec, dtype=float)
        length = np.linalg.norm(v)

        # Determine if we have a zero magnitude vector
        zero_vector = False
        if length < self.VERY_SMALL:
            zero_vector = True
        
        if not zero_vector:
            # Compute the unit vector direction
            direction = v / length
            # Compute rotation between X-axis and target direction
            # (vectors always point in +X with no rotation)
            x_axis = np.array([1,0,0])
            axis = np.cross(x_axis, direction)
            angle = np.degrees(np.arccos(np.clip(np.dot(x_axis, direction), -1, 1)))
            # Start with identity matrix - no rotation, position, or scaling
            self.local_transform.Identity()
            # Scale the vector depending on which mode is selected
            if self.mode == 'absolute':
                self.set_scale(length*self.user_scale)
            elif self.mode == 'unit':
                self.set_scale(self.user_scale)
            elif self.mode == 'custom':
                self.custom_scale(vec)
            self.local_transform.PostMultiply()
            # Rotate the node by this rotation
            if np.linalg.norm(axis) > 1e-6:
                self.local_transform.RotateWXYZ(angle, *axis)

            # If specified, adjust the opacity of the actor
            if opacity != None:
                self.actor.GetProperty().SetOpacity(float(opacity))
        else:
            self.set_scale([0.0, 0.0, 0.0])
            self.local_transform.Scale([0.0, 0.0, 0.0])

    def get_world_vector(self):
        """
        Get this vector expressed in world space coordinates
        """
        if not self.data_source:
            return
        pos  = self.data_source.get_current_position()
        # Get the location of the base and tip expressed in world coordinates,
        # then subtract them and normalize to produce the vector in world
        # coordinates
        vec_world_pos_base = self.get_world_position(local_point=(0.0, 0.0, 0.0))
        # We use pos = (1.0, 0.0, 0.0) because all vectors are rotated
        # from +x direction
        vec_world_pos_tip = self.get_world_position(local_point=(1.0, 0.0, 0.0))
        vec_world_pos = np.array(vec_world_pos_tip) - np.array(vec_world_pos_base)
        length = np.linalg.norm(vec_world_pos)
        if length == 0:
            raise ValueError(f"Zero-length vector for {self.name} cannot be displayed.")
        vec_world_pos = list(vec_world_pos / length)
        return(vec_world_pos)
    
    def set_mode(self, value):
        """
        Set the display mode for this vector. Values are 'unit' or 'absolute' as
        enforced by VirgoDictVerifier.
        """
        self.mode = value

    def custom_scale(self, vec):
        """
        Abstract function that allows subclasses to specify how to scale
        this vector

        Args:
          vec: the vector from set_pose()
        """
        pass
