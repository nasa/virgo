#!/usr/bin/env python3
import numpy as np
import os, inspect, re
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))

from vtkmodules.vtkRenderingCore import (
  vtkActor,
  vtkPolyDataMapper,
  vtkTexture,
)
from vtkmodules.vtkCommonCore import (
  vtkFloatArray,
  vtkPoints,
)
from vtkmodules.vtkCommonDataModel import (
  vtkPolyData,
  vtkCellArray,
  vtkQuad,
)
from vtkmodules.vtkFiltersSources import (
  vtkCubeSource,
  vtkSphereSource,
  vtkCylinderSource,
  vtkConeSource,
  vtkArrowSource,
  vtkTexturedSphereSource,
)
from vtkmodules.vtkIOGeometry import (
  vtkOBJReader,
  vtkSTLReader,
)
from vtkmodules.vtkIOImage import (
  vtkJPEGReader,
  vtkPNGReader,
)
from vtkmodules.vtkFiltersTexture import (
  vtkTextureMapToPlane,
)
class VirgoActor(vtkActor):
    """
    Wrapper around VTK actor to facilitate the Trick Logged data
    and other capabilities
    """
    def __init__(self, mesh, offset_pos=None, offset_ypr=None, name='No Name', fontsize=12):
        """
        Initialize this instance.

        >>> va = VirgoActor(mesh=os.path.join(thisFileDir,"meshes/teapot.obj"), name='tea')
        >>> va.name
        'tea'

        Parameters
        ----------
        mesh : str
            3D representation of the actor in the scene, which is either 
             a path to an object file to load like .obj, .stl, or a supported
             VIRGO_PREFAB (TODO more info needed here)
        offset_pos : list of 3 doubles
             X-Y-Z position to apply to the model on
             init. Used to adjust position of a model relative to the origin of
             of the model as provided by the CAD or VIRGO_PREFAB itself
        offset_ypr : list of 3 doubles
             Z-Y-X (Yaw-Pitch-Roll) Tait-Bryan rotation in degrees to apply to
             the model on init. Used to rotate a model into another frame
             immediately upon model creation. This rotation is performed after
             offset_pos is applied.
        name : str
            Name given to this actor
        fontsize : int
            Default fontsize for text associated with this actor
        """
        self.backface_culling_enabled = False
        # Call the parent class constructor to ensure proper initialization
        super().__init__()

        self.source = None  # If using a vtk*Source, it's stored here for reference
        self.mesh  = self.expand_env_vars(mesh)
        self.name = name            # Name of this actor
        self._map_mesh(self.mesh)
        self.num_vertices = None
        self.offset_pos  = offset_pos     # Initialization position offset to apply to to actor
        self.offset_ypr  = offset_ypr     # Initialization pitch/yaw/roll to apply to to actor
        self.axes_label_render_threshold = 50    # min distance axes labels can be seen
        
        self.fs = fontsize          # Font size for text associated with this actor
        #import pdb; pdb.set_trace()
        self.static = False       # If true, this actor never moves
        self.initialized = False  # True only if this actor has all needed data to be used
        self.axes_default_scale = 0.5  # Default scaling of axes to be applied

    @staticmethod
    def expand_env_vars(text: str) -> str:
        """
        Accepts a string that may contain environment variables and returns
        the string with all environment variables expanded.
    
        Supports formats:
          - $VAR_NAME
          - ${VAR_NAME}
          - %VAR_NAME%  (Windows-style)
    
        Raises RuntimeError if any variable is not set.
        """
        def _resolve(var_name: str, original: str) -> str:
            if var_name not in os.environ:
                msg = (f"ERROR: Environment var {var_name} not defined.")
                raise RuntimeError (msg)
            return os.environ[var_name]

        result = re.sub(
            r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)',
            lambda m: _resolve(m.group(1) or m.group(2), m.group(0)),
            text
        )
        result = re.sub(
            r'%([^%]+)%',
            lambda m: _resolve(m.group(1), m.group(0)),
            result
        )
        return result

    def set_backface_culling(self, value=True):
        self.backface_culling_enabled = value

    def set_static(self, value=True):
        self.static = value

    def is_static(self):
        return self.static

    def initialize(self):
        """
        Perform pre-rendering setup/initialization
        """
        # Determine the number of vertices in this actor
        mapper = self.GetMapper()
        mapper.Update()
        if mapper:
            polydata = mapper.GetInput()
            if polydata:
                self.num_vertices = polydata.GetNumberOfPoints() 
                #print(f'DEBUG: number of vertices in {self.name}: {self.num_vertices}')
        if self.offset_pos:
          # Apply the initial position/rotation to this object
          self.AddPosition(self.offset_pos)
        # TODO: PYR may not be sufficient for end users, we may need to consider
        # different rotation schemes
        if self.offset_ypr:
          # Apply the initial position/rotation to this object in Z-Y-X order
          self.RotateZ(self.offset_ypr[0])
          self.RotateY(self.offset_ypr[1])
          self.RotateX(self.offset_ypr[2])
        if self.backface_culling_enabled:
            self.GetProperty().BackfaceCullingOn()
        self.verify()

    def verify(self):
        # TO BE FILLED OUT
        pass

    def get_bounding_box(self):
        '''
        Return a list of actor bounding box [x_size, y_size, z_size]
        '''
        # Get size of actor to automatically scale size of axes
        bounds = self.GetBounds()
        # Bounds are returned as (xmin, xmax, ymin, ymax, zmin, zmax)
        center = [(bounds[0] + bounds[1]) / 2.0,  # x-center
                  (bounds[2] + bounds[3]) / 2.0,  # y-center
                  (bounds[4] + bounds[5]) / 2.0]  # z-center
        # Calculate the size of the bounding box
        size = [bounds[1] - bounds[0],  # x-size
                bounds[3] - bounds[2],  # y-size
                bounds[5] - bounds[4]]  # z-size

        return size


    def _map_mesh(self, mesh):
        """
        Given a string mesh (a path to a model file or a VIRGO_PREFAB), set up the vtk
        mapper with the configuration of geometry given
        """
        # TODO: this is quick and dirty, need a VIRGO_PREFAB management class that VirgoActor uses
        mapper = vtkPolyDataMapper()
        texture = None
        if 'VIRGO_PREFAB:sphere300' in str(mesh):
            # Create a sphere source
            self.source = vtkSphereSource()
            self.source.SetRadius(1.0)  # Set radius of the sphere
            self.source.SetThetaResolution(300)  # Number of divisions in theta (longitude)
            self.source.SetPhiResolution(300)  # Number of divisions in phi (latitude)
            # Create a mapper to map the sphere's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
        elif 'VIRGO_PREFAB:sphere' in str(mesh) or 'VIRGO_PREFAB:sphere100' in str(mesh):
            # Create a sphere source
            self.source = vtkSphereSource()
            self.source.SetRadius(1.0)  # Set radius of the sphere
            self.source.SetThetaResolution(100)  # Number of divisions in theta (longitude)
            self.source.SetPhiResolution(100)  # Number of divisions in phi (latitude)
            # Create a mapper to map the sphere's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
        # Medium fidelity earth (for simulations not too close to the surface)
        elif 'VIRGO_PREFAB:earth' in str(mesh):
            equatorial = 6378137.0
            polar = 6356752.0
            # Create a sphere source
            self.source = vtkTexturedSphereSource()
            self.source.SetRadius(equatorial)     # Equatorial radius
            self.source.SetThetaResolution(300)  # Number of divisions in theta (longitude)
            self.source.SetPhiResolution(300)  # Number of divisions in phi (latitude)
            # Read Earth texture image
            reader = vtkJPEGReader()
            reader.SetFileName(os.path.join(thisFileDir, 'images/earth/2k_earth_daymap.jpg'))
            texture = vtkTexture()
            texture.SetInputConnection(reader.GetOutputPort())
            texture.InterpolateOn()
            # Create a mapper to map the sphere's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
            # Scale the sphere to make it an oblate spheroid
            # Earth radii: equatorial ~6378 km, polar ~6357 km
            scale_z = polar / equatorial
            self.SetScale(1.0, 1.0, scale_z)  # squash along Z
            # Standard equirectangular images need 180 rotation to
            # have earth align with ECEF frame
            self.RotateZ(180)
        # High fidelity earth (for simulations not too close to the surface)
        elif 'VIRGO_PREFAB:wgs84-earth' in str(mesh):
            # -----------------------------
            # Create WGS84 Earth ellipsoid
            # -----------------------------
            ellipsoid = self.create_wgs84_ellipsoid()
            mapper.SetInputData(ellipsoid)
            # -----------------------------
            # Load and apply Earth texture
            # -----------------------------
            reader = vtkPNGReader()
            reader.SetFileName(os.path.join(thisFileDir, 'images/earth/earth_4050x2025.png'))
            reader.Update()

            texture = vtkTexture()
            texture.SetInputConnection(reader.GetOutputPort())
            texture.InterpolateOn()   # Smooth texture when magnified
            texture.RepeatOn()        # Repeat texture if UVs extend beyond [0,1]

        elif 'VIRGO_PREFAB:ksc-39b-patch' in str(mesh):
            # -----------------------------
            # Read KSC 39B STL geometry
            # -----------------------------
            stl_reader = vtkSTLReader()
            stl_reader.SetFileName(os.path.join(thisFileDir,'meshes/ksc_39b_1km.stl'))
            stl_reader.Update()
            mapper.SetInputConnection(stl_reader.GetOutputPort())

            # -----------------------------
            # Map textures onto STL geometry
            # -----------------------------
            # Note: vtkTextureMapToPlane works well for plane-like surfaces.
            #       For highly curved or incomplete geometry, texture mapping may fail.
            tex_filter = vtkTextureMapToPlane()
            tex_filter.SetInputConnection(stl_reader.GetOutputPort())
            tex_filter.Update()
            mapper.SetInputConnection(tex_filter.GetOutputPort())

            # -----------------------------
            # Load and apply KSC texture
            # -----------------------------
            png_reader = vtkPNGReader()
            png_reader.SetFileName(os.path.join(thisFileDir,'images/earth/ksc_39b_1km.png'))

            texture = vtkTexture()
            texture.SetInputConnection(png_reader.GetOutputPort())
            texture.InterpolateOn()  # Smooth the texture when scaling
        elif 'VIRGO_PREFAB:moon8k' in str(mesh) :
            # Create a sphere source
            self.source = vtkTexturedSphereSource()
            self.source.SetRadius(1738100.0)     # Set radius of moon
            self.source.SetThetaResolution(300)  # Number of divisions in theta (longitude)
            self.source.SetPhiResolution(300)  # Number of divisions in phi (latitude)
            # Read Moon texture image
            reader = vtkJPEGReader()
            reader.SetFileName(os.path.join(thisFileDir, 'images/moon/lroc_color_poles_8k.jpg'))
            texture = vtkTexture()
            texture.SetInputConnection(reader.GetOutputPort())
            texture.InterpolateOn()
            # Create a mapper to map the sphere's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
            # Scale the sphere to make it an oblate spheroid
            equatorial = 1738100.0
            polar = 1736000.0
            scale_z = polar / equatorial   # ~0.99879
            self.SetScale(1.0, 1.0, scale_z)
            # Standard equirectangular images need 180 rotation to
            # have moon align with ECEF frame
            self.RotateZ(180)
        elif 'VIRGO_PREFAB:moon4k' in str(mesh) :
            # Create a sphere source
            self.source = vtkTexturedSphereSource()
            self.source.SetRadius(1738100.0)     # Set radius of moon
            self.source.SetThetaResolution(300)  # Number of divisions in theta (longitude)
            self.source.SetPhiResolution(300)  # Number of divisions in phi (latitude)
            # Read Moon texture image
            reader = vtkJPEGReader()
            reader.SetFileName(os.path.join(thisFileDir, 'images/moon/lroc_color_poles_4k.jpg'))
            texture = vtkTexture()
            texture.SetInputConnection(reader.GetOutputPort())
            texture.InterpolateOn()
            # Create a mapper to map the sphere's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
            # Scale the sphere to make it an oblate spheroid
            equatorial = 1738100.0
            polar = 1736000.0
            scale_z = polar / equatorial   # ~0.99879
            self.SetScale(1.0, 1.0, scale_z)
            # Standard equirectangular images need 180 rotation to
            # have moon align with ECEF frame
            self.RotateZ(180)
        elif 'VIRGO_PREFAB:moon' in str(mesh) or 'VIRGO_PREFAB:moon2k' in str(mesh) :
            # Create a sphere source
            self.source = vtkTexturedSphereSource()
            self.source.SetRadius(1738100.0)     # Set radius of moon
            self.source.SetThetaResolution(300)  # Number of divisions in theta (longitude)
            self.source.SetPhiResolution(300)  # Number of divisions in phi (latitude)
            # Read Moon texture image
            reader = vtkJPEGReader()
            reader.SetFileName(os.path.join(thisFileDir, 'images/moon/lroc_color_poles_2k.jpg'))
            texture = vtkTexture()
            texture.SetInputConnection(reader.GetOutputPort())
            texture.InterpolateOn()
            # Create a mapper to map the sphere's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
            # Scale the sphere to make it an oblate spheroid
            equatorial = 1738100.0
            polar = 1736000.0
            scale_z = polar / equatorial   # ~0.99879
            self.SetScale(1.0, 1.0, scale_z)
            # Standard equirectangular images need 180 rotation to
            # have moon align with ECEF frame
            self.RotateZ(180)
        elif 'VIRGO_PREFAB:cube' in str(mesh):
            self.source = vtkCubeSource()
            self.source.SetXLength(1.0)
            self.source.SetYLength(1.0)
            self.source.SetZLength(1.0)
            # Create a mapper to map the cube's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
        elif 'VIRGO_PREFAB:cylinder' in str(mesh):
            self.source = vtkCylinderSource()
            self.source.SetHeight(1.0)         # Set height to 3 units
            self.source.SetRadius(0.5)         # Set radius to 1 unit
            self.source.SetCenter(0.0, 0.0, 0.0) # 
            self.source.SetResolution(50)      # Use 50 facets for a smooth cylinder
            self.source.SetCapping(True)       # Ensure the bases are capped
            # Create a mapper to map the cube's geometry to graphics primitives
            mapper.SetInputConnection(self.source.GetOutputPort())
        elif'VIRGO_PREFAB:cone-32' in str(mesh):
            self.source = vtkConeSource()
            height = 1.0
            self.source.SetHeight(height)
            self.source.SetRadius(0.5)
            self.source.SetResolution(32)
            self.source.SetDirection(-1, 0, 0)  # tip pointed along -X
            self.source.SetCenter(height/2, 0.0, 0.0)  # tip at (0,0,0)
            mapper.SetInputConnection(self.source.GetOutputPort())
        elif 'VIRGO_PREFAB:cone' in str(mesh) or  'VIRGO_PREFAB:cone-16' in str(mesh):
            self.source = vtkConeSource()
            height = 1.0
            self.source.SetHeight(height)
            self.source.SetRadius(0.5)
            self.source.SetResolution(16)
            self.source.SetDirection(-1, 0, 0)  # tip pointed along -X
            self.source.SetCenter(height/2, 0.0, 0.0)  # tip at (0,0,0)
            mapper.SetInputConnection(self.source.GetOutputPort())
        elif 'VIRGO_PREFAB:arrow' in str(mesh):
            self.source = vtkArrowSource()
            self.source.SetTipLength(0.35)   # Fraction of total length
            self.source.SetTipRadius(0.2)    # Radius of the cone
            self.source.SetShaftRadius(0.03) # Radius of the cylinder
            self.source.Update()
            mapper.SetInputConnection(self.source.GetOutputPort())
        elif '.obj' in str(mesh):
            # Read in the geometry
            reader = vtkOBJReader()
            reader.SetFileName(mesh)
            reader.Update()
            # Create a mapper and set the reader's output
            mapper.SetInputConnection(reader.GetOutputPort())
        elif '.stl' in str(mesh):
            # Read in the geometry
            reader = vtkSTLReader()
            reader.SetFileName(mesh)
            reader.Update()
            # Create a mapper and set the reader's output
            mapper.SetInputConnection(reader.GetOutputPort())
        else:
            msg = (f"ERROR: mesh name {mesh} for {self.name}"
              " cannot be understood. See documentation for help")
            raise RuntimeError (msg)
        # Set the mapper to the actor
        self.SetMapper(mapper)
        if texture:
            self.SetTexture(texture)

    def set_axes(self, axes):
        self._axes = axes
    def get_num_vertices(self):
        return self.num_vertices


    def create_wgs84_ellipsoid( self, n_lat=360, n_lon=720,
        a=6378137.0, b=6356752.314245):
        """
        Create a WGS-84 ellipsoid mesh using geodetic latitude
        and longitude.

        Parameters:
            n_lat : int
                Number of latitude divisions (-90° to +90°)
            n_lon : int
                Number of longitude divisions (-180° to +180°)
            a : float
                Equatorial radius (meters)
            b : float
                Polar radius (meters)

        Returns:
            vtkPolyData : VTK mesh of the WGS-84 ellipsoid with:
                - points (vertices)
                - quad faces
                - normals
                - texture coordinates
        """
        points = vtkPoints()                # Stores 3D vertex coordinates
        polys = vtkCellArray()              # Stores quad connectivity
        normals = vtkFloatArray()           # Normals for lighting
        normals.SetNumberOfComponents(3)
        normals.SetName("Normals")

        tcoords = vtkFloatArray()           # Texture coordinates (U,V)
        tcoords.SetNumberOfComponents(2)
        tcoords.SetName("TextureCoordinates")

        # Generate latitude and longitude arrays
        # Latitude from -90° (south pole) to +90° (north pole)
        lats = np.linspace(-np.pi / 2, np.pi / 2, n_lat)
        # Longitude from -180° to +180°
        lons = np.linspace(-np.pi, np.pi, n_lon)

        # Precompute squared eccentricity for geodetic calculation
        # e² = 1 - (b² / a²)
        e2 = 1.0 - (b * b) / (a * a)

        # Generate vertices, normals, and texture coordinates
        for phi in lats:
            sin_phi = np.sin(phi)
            cos_phi = np.cos(phi)

            # Radius of curvature in the prime vertical
            N = a / np.sqrt(1.0 - e2 * sin_phi * sin_phi)

            for lam in lons:
                cos_lam = np.cos(lam)
                sin_lam = np.sin(lam)

                # Compute 3D coordinates on ellipsoid surface
                # x = N * cos(lat) * cos(lon)
                # y = N * cos(lat) * sin(lon)
                # z = (b² / a² * N) * sin(lat)
                x = N * cos_phi * cos_lam
                y = N * cos_phi * sin_lam
                z = (b * b / a / a * N) * sin_phi

                points.InsertNextPoint(x, y, z)

                # Compute normal vector at this point
                # Used for lighting / shading
                nx = cos_phi * cos_lam
                ny = cos_phi * sin_lam
                nz = sin_phi
                normals.InsertNextTuple((nx, ny, nz))

                # Compute texture coordinates (UV mapping)
                # U = longitude mapped to [0,1]
                # V = latitude mapped to [0,1]
                u = (lam + np.pi) / (2.0 * np.pi)
                v = (phi + np.pi / 2.0) / np.pi
                tcoords.InsertNextTuple((u, v))

        # Helper function to map 2D grid indices to 1D point index
        def idx(i, j):
            return i * n_lon + j

        # Generate quad faces connecting vertices
        # Each quad is defined by 4 neighboring vertices
        for i in range(n_lat - 1):
            for j in range(n_lon - 1):
                p0 = idx(i, j)
                p1 = idx(i + 1, j)
                p2 = idx(i + 1, j + 1)
                p3 = idx(i, j + 1)

                quad = vtkQuad()
                # Counter-Clockwise winding so normals face out into space
                quad.GetPointIds().SetId(0, p0)
                quad.GetPointIds().SetId(1, p3)
                quad.GetPointIds().SetId(2, p2)
                quad.GetPointIds().SetId(3, p1)
                polys.InsertNextCell(quad)

        # -----------------------------
        # Assemble polydata
        # -----------------------------
        polydata = vtkPolyData()
        polydata.SetPoints(points)                    # Attach vertices
        polydata.SetPolys(polys)                      # Attach quads
        polydata.GetPointData().SetNormals(normals)   # Attach normals
        polydata.GetPointData().SetTCoords(tcoords)   # Attach texture coordinates

        return polydata