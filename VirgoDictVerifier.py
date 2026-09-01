import math, re
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator, NonNegativeInt
"""
This module provides verification of the scene dictionary passed into
Virgo instances at initialization. It leverages pydantic to both verify
the fields in the dict are valid and set defaults if those fields are
not given.
"""

# Defaults for optional values if not given by the user
# TODO this list isn't exhaustive and some values are set within
# the *Schema classes below.
VIRGO_DEFAULT_SCENE_NAME = "Unnamed VIRGO Scene"
VIRGO_DEFAULT_SCENE_DESCRIPTION = "VIRGO Scene (Missing Description)"
VIRGO_DEFAULT_PLAYBACK_SPEEDS = [1.0, 2.0, 5.0, 10.0]
VIRGO_DEFAULT_BACKGROUND_COLOR = [0.0, 0.0, 0.05]
VIRGO_DEFAULT_HUD_COLOR = [1.0, 1.0, 1.0]
VIRGO_DEFAULT_HIGHLIGHT_COLOR = [1.0, 1.0, 0.0]
VIRGO_DEFAULT_LIGHTING_MODE = 'headlight'
VIRGO_DEFAULT_LIGHTING_DARK_AMBIENT = 0.2
VIRGO_DEFAULT_LIGHTING_LIGHT_AMBIENT = 0.7
VIRGO_DEFAULT_PICKER_TOLERANCE = 5e-7
VIRGO_DEFAULT_LABEL_SCALE = 1.0
VIRGO_DEFAULT_LABEL_COLOR = [1.0, 1.0, 1.0]
VIRGO_DEFAULT_VECTOR_TIP_LENGTH = 0.35
VIRGO_DEFAULT_VECTOR_TIP_RADIUS = 0.1
VIRGO_DEFAULT_VECTOR_SHAFT_RADIUS = 0.03

class PlaybackMode(str, Enum):
    PAUSED = "PAUSED"
    PLAYING = "PLAYING"
class LightingMode(str, Enum):
    realistic = 'realistic'
    headlight = 'headlight'
    ultrabright = 'ultrabright'
class AxesAndLabelsWhen(str, Enum):
    toggled = "toggled"
    picked = "picked"
    always = "always"
    never = "never"
class AxesStyle(str, Enum):
    line = "line"
    cylinder = "cylinder"
class VectorMode(str, Enum):
    unit = 'unit'
    absolute = 'absolute'
    custom = 'custom'

# Complex types defined here
RGBColor = list[float, float, float]
Vec3 = list[float, float, float]

def validate_vec3(value: Vec3, name: str):
    if len(value) != 3:
        raise ValueError(f"{name} must have exactly 3 elements")
    return value

def force_to_boolen(v):
    if isinstance(v, str):
        return v.lower() in ('true', '1', 'yes', 'on')
    return bool(v)

def format_pydantic_errors(err: ValidationError) -> str:
    lines = []
    for e in err.errors():
        location = ": ".join(str(x) for x in e["loc"])
        message = e["msg"]
        lines.append(f"  {location}: {message}")
    return "\n".join(lines)

class TrailSchema(BaseModel):
    enabled: bool = False
    color: RGBColor = [1.0, 1.0, 1.0]
    thickness: int = 2
    opacity: float = 1.0

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        if any(not (0.0 <= c <= 1.0) for c in v):
            raise ValueError("A trail's color values must be between 0.0 and 1.0")
        return v

class SunSchema(BaseModel):
    direction: Optional[Vec3] = None
    driven_by: Optional[str] = None

class CameraSchema(BaseModel):
    mode: Optional[str] = 'TB'
    pos: Optional[Vec3] = [0, 0, 0]
    focal_point: Optional[Vec3] = None
    view_up: Optional[Vec3]  = [0.0, 0.0, 1.0]
    view_angle: Optional[float]  = 30
    static: Optional[bool]  = False
    frustum_when: Optional[str] = 'never'
    frustum_far_plane: Optional[float] = 1.0
    frustum_color: Optional[RGBColor] = [1.0, 1.0, 1.0]
    frustum_face_opacity: Optional[float] = 0.15
    frustum_line_width: Optional[float] = 2.0
    priority: Optional[NonNegativeInt] = 0
    parent: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def check_forbidden_key(cls, data):
        if isinstance(data, dict) and 'follow' in data:
            msg = ("follow: is no longer supported for cameras."
            "  Use parent: instead.")
            raise ValueError(msg)
        return data

    @field_validator("view_angle")
    @classmethod
    def validate_view_angle(cls, value):
        if value < 0.0:
            raise ValueError("view_angle must be > 0.0")
        return value


class RendererSchema(BaseModel):
    near_clipping_plane_tolerance: Optional[float] = 1e-5
    foreground_far_boundary: Optional[float] = 1e5
    midground_far_boundary: Optional[float] = 1e8
    celestial_foreground_bias: Optional[float] = 1e-2
    # TODO check limits

    @field_validator("foreground_far_boundary", "midground_far_boundary",
                     "near_clipping_plane_tolerance")
    @classmethod
    def greater_than_zero(cls, v, info):
        if v <= 0.0:
            raise ValueError(f"must be greater than 0.0")
        return v

    @field_validator("celestial_foreground_bias")
    @classmethod
    def greater_than_zero_inclusive(cls, v, info):
        if v < 0.0:
            raise ValueError(f"must be greater than 0.0")
        return v

    @field_validator("celestial_foreground_bias",
                     "near_clipping_plane_tolerance")
    @classmethod
    def not_less_than_one(cls, v, info):
        if v >= 1.0:
            raise ValueError(f"must be less than 1.0")
        return v

    @model_validator(mode="after")
    def midground_bound_further_than_foreground(self):
        if self.midground_far_boundary < self.foreground_far_boundary:
            raise ValueError(
                "midground_far_boundary must be > foreground_far_boundary"
            )
        return self

class LightingSchema(BaseModel):
    start_mode: Optional[LightingMode] = Field(
        default=VIRGO_DEFAULT_LIGHTING_MODE,
        description="Initial lighting mode when the window starts"
    )
    dark_ambient: Optional[float] = VIRGO_DEFAULT_LIGHTING_DARK_AMBIENT
    light_ambient: Optional[float] = VIRGO_DEFAULT_LIGHTING_LIGHT_AMBIENT

class PickerSchema(BaseModel):
    tolerance: Optional[float] = VIRGO_DEFAULT_PICKER_TOLERANCE

class AxesSchema(BaseModel):
    when: Optional[AxesAndLabelsWhen] = AxesAndLabelsWhen.toggled
    style: Optional[AxesStyle] = None
    length: Optional[Vec3] = None
    affect_opacity: bool = True

    @field_validator("length")
    @classmethod
    def validate_length(cls, v):
        if v is None:
            return v
        return validate_vec3(v, "axes.length")

class VectorDrivenBySchema(BaseModel):
    time: str
    pos: Optional[str] = None
    rot: Optional[type] = None # Must be None
    scale: Optional[str] = None
    opacity: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def ensure_field_not_given(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if 'rot' in data:
            raise ValueError('vectors cannot have a rot: field')
        return data

class ActorDrivenBySchema(BaseModel):
    time: str
    pos: Optional[str] = None
    rot: Optional[str] = None
    scale: Optional[str] = None
    opacity: Optional[str] = None
    transpose_rot: Optional[bool] = True

    @model_validator(mode="after")
    def check_at_least_one_driver(self):
        if not any([self.pos, self.rot, self.scale, self.opacity]):
            raise ValueError(
                "driven_by must specify at least one of "
                "'pos', 'rot', 'scale', or 'opacity'"
            )
        return self

class ProvideAliasesSchema(BaseModel):
    time: str
    aliases: Optional[list] = []

    @model_validator(mode="after")
    def validate_no_duplicate_aliases(self):
        if len(self.aliases) != len(set(self.aliases)):
            duplicates = {k for k in self.aliases if self.aliases.count(k) > 1}
            msg = (f"Duplicate names detected: {duplicates}. There can be no "
                  f"duplicate aliases: in a provide_data: section.")
            raise ValueError(msg)
        return self

class LabelSchema(BaseModel):
    text: str
    pos: Vec3 = [0.0, 0.0, 0.0]
    ypr: Vec3 = [0.0, 0.0, 0.0]
    scale: Optional[float] = VIRGO_DEFAULT_LABEL_SCALE
    color: RGBColor = VIRGO_DEFAULT_LABEL_COLOR
    faces_camera: Optional[bool] = False
    when: Optional[AxesAndLabelsWhen] = AxesAndLabelsWhen.toggled

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        if any(not (0.0 <= c <= 1.0) for c in v):
            raise ValueError("A label's color values must be between 0.0 and 1.0")
        return v

    @field_validator('faces_camera', mode='before')
    @classmethod
    def validate_boolean(cls, v):
        return(force_to_boolen(v))

    @model_validator(mode='before')
    @classmethod
    def ensure_no_ypr_if_faces_camera_true(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if ('ypr' in data and 'faces_camera' in data and 
            data['faces_camera'] == True):
            raise ValueError('label cannot have ypr: if faces_camera: is 1')
        return data

class ActorBaseSchema(BaseModel):
    dimensions: List[float] = None
    scale: float = 1.0
    opacity: float = 1.0
    pos: Vec3 = [0.0, 0.0, 0.0]
    ypr: Vec3 = [0.0, 0.0, 0.0]
    color: Optional[RGBColor] = None
    pickable: bool = True
    parent: Optional[str] = None
    backface_culling: Optional[bool] = False
    provide_data: Optional[ProvideAliasesSchema] = None

    # --- SubSchemas ---
    axes: Optional[AxesSchema] = None
    trail: Optional[TrailSchema] = None
    driven_by: Optional[ActorDrivenBySchema] = None
    labels: Dict[str, LabelSchema] = Field(default_factory=dict)


    # --- Validators ---
    @field_validator("pos", "ypr")
    @classmethod
    def validate_vecs(cls, v, info):
        return validate_vec3(v, info.field_name)

    @field_validator("color")
    @classmethod
    def validate_actor_color(cls, v):
        if v is None:
            return v
        if any(not (0.0 <= c <= 1.0) for c in v):
            raise ValueError("an actor's color values must be between 0.0 and 1.0")
        return v
    
    @field_validator("dimensions")
    @classmethod
    def validate_actor_dimensions(cls, v):
        if v is None:
            return v
        if len(v) < 2 or len(v) > 3:
            raise ValueError(f"dimensions must contain 2 or 3 values, got {len(v)}")
        if any(not (0.0 <= c) for c in v):
            raise ValueError(f"dimensions need to be greater than 0.0, got {v}")
        return v


class DataAliasSchema(BaseModel):
    group: str
    var: str

# This will need adjusting as new data sources come online
# - Jordan 1/2026
class DataSourceSchema(BaseModel):
    trickpy: Optional[Dict[str, DataAliasSchema]] = Field(
        default=None,
        description="Dictionary of trickpy data aliases in the scene"
    ) 
    # TODO: variable server data source info goes here
    
@model_validator(mode='before')
@classmethod
def ensure_valid_alias_name(cls, data: Any) -> Any:
    allowed_pattern = r'[_A-Za-z0-9.-]+'
    for data_source in data:
        for alias_name in data[data_source]:
            if not re.fullmatch(allowed_pattern, alias_name):
                raise ValueError(f'data alias {alias_name} cannot contain '
                f'special characters. Only regex {allowed_pattern} allowed')
        return data

class ActorSchema(ActorBaseSchema):
    # --- Required ---
    mesh: str

class FrameSchema(ActorBaseSchema):
    # A frame is just an actor with no mesh
    @model_validator(mode='before')
    @classmethod
    def ensure_field_not_given(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if 'mesh' in data:
            raise ValueError('frames cannot have a mesh: field')
        if 'trail' in data:
            raise ValueError('frames cannot have a trail: field')
        if 'trail' in data:
            raise ValueError('frames cannot have a scale: field')
        return data

class VectorSchema(ActorBaseSchema):
    tip_length:   Optional[float] = VIRGO_DEFAULT_VECTOR_TIP_LENGTH
    tip_radius:   Optional[float] = VIRGO_DEFAULT_VECTOR_TIP_RADIUS
    shaft_radius: Optional[float] = VIRGO_DEFAULT_VECTOR_SHAFT_RADIUS
    mode: Optional[VectorMode] = Field(
        default=VectorMode.unit,
        description="Vector mode"
    )
    driven_by: Optional[VectorDrivenBySchema] = None

    # A vector is just an actor with arrow as mesh
    @model_validator(mode='before')
    @classmethod
    def ensure_field_not_given(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if 'mesh' in data:
            raise ValueError('vectors cannot have a mesh: field')
        if 'trail' in data:
            raise ValueError('vectors cannot have a trail: field')
        return data

    @field_validator("tip_length", "tip_radius", "shaft_radius")
    @classmethod
    def validate_tip_length(cls, v, info):
        if v is None:
            return v
        if v < 0.0 or v > 1.0:
            raise ValueError(f"a vectors's {info.field_name} must be between 0.0 and 1.0")
        return v


class SceneSchema(BaseModel):
    # Tell pydantic to ignore any unknown keys in the dict
    model_config = { "extra": "allow", }
    name: Optional[str] = Field(
        default_factory=lambda: VIRGO_DEFAULT_SCENE_NAME,
        description="Optional name of this scene"
    )
    description: Optional[str] = Field(
        default_factory=lambda: VIRGO_DEFAULT_SCENE_DESCRIPTION,
        description="Optional description of this scene"
    )
    start_mode: Optional[PlaybackMode] = Field(
        default=None,
        description="Initial playback mode when the window starts"
    )
    end_mode: Optional[PlaybackMode] = Field(
        default=None,
        description="Playback mode when reaching end of data"
    )
    background_color: Optional[RGBColor] = Field(
        default_factory=lambda: VIRGO_DEFAULT_BACKGROUND_COLOR.copy(),
        description="RGB background color [0.0–1.0]"
    )
    highlight_color: Optional[RGBColor] = Field(
        default_factory=lambda: VIRGO_DEFAULT_HIGHLIGHT_COLOR.copy(),
        description="RGB picked actor highlight color [0.0–1.0]"
    )
    hud_color: Optional[RGBColor] = Field(
        default_factory=lambda: VIRGO_DEFAULT_HUD_COLOR.copy(),
        description="RGB color of HUD text [0.0–1.0]"
    )
    playback_speeds: Optional[List[float]] = Field(
        default_factory=lambda: VIRGO_DEFAULT_PLAYBACK_SPEEDS.copy(),
        description="Supported playback speeds"
    )
    playback_speed: Optional[float] = Field(
        default=1.0,
        description="Default playback speed"
    )
    starfield: Optional[bool] = Field(
        default=None,
        description="Enable background starfield"
    )
    actors: Dict[str, ActorSchema] = Field(
        default=None,
        description="Dictionary of actors in the scene"
    ) 
    frames: Dict[str, FrameSchema] = Field(
        default=None,
        description="Dictionary of frames in the scene"
    ) 
    vectors: Dict[str, VectorSchema] = Field(
        default=None,
        description="Dictionary of vectors in the scene"
    ) 
    data_source: DataSourceSchema = Field(
        default=None,
        description="Dictionary of data sources in the scene"
    ) 
    sun: SunSchema = Field (
        default=None,
        description="Dictionary of sun data"
    )
    cameras: Dict[str, CameraSchema] = Field (
        default=None,
        description="Dictionary of camera data"
    )
    renderer: RendererSchema = Field (
        default=None,
        description="Dictionary of renderer data"
    )
    lighting: LightingSchema = Field (
        default=None,
        description="Dictionary of lighting data"
    )
    picker: PickerSchema = Field (
        default=None,
        description="Dictionary of picker data"
    )

    def get_all_node_names(self):
      """
      Returns a list of all names of all actors, vectors, and frames
      """
      all_node_names =  list(self.actors.keys()) if self.actors else []
      all_node_names += list(self.vectors.keys()) if self.vectors else []
      all_node_names += list(self.frames.keys()) if self.frames else []
      return(all_node_names)

    @field_validator("background_color", "highlight_color")
    @classmethod
    def validate_rgb_range(cls, value):
        if value is None:
            return value
        if any(not (0.0 <= c <= 1.0) for c in value):
            raise ValueError("RGB color values must be between 0.0 and 1.0")
        return value

    @model_validator(mode="after")
    def check_default_frustum(self):
        if self.cameras and 'default' in self.cameras:
            default_camera = self.cameras['default']
            if default_camera.frustum_when != 'never':
                raise ValueError("frustum_when is not supported for the default camera. "
                                 "The default camera never displays a frustum."
                )
        return self

    @model_validator(mode="after")
    def check_playback_speed_supported(self):
        if ( self.playback_speed is not None
            and self.playback_speeds is not None):
            if not any(
                math.isclose(self.playback_speed, s, rel_tol=1e-9)
                for s in self.playback_speeds
            ):
                raise ValueError(
                    f"playback_speed ({self.playback_speed}) must be one of "
                    f"playback_speeds {self.playback_speeds}"
                )
        return self

    @model_validator(mode="after")
    def check_for_at_least_one_node(self):
        if not self.actors and not self.frames and not self.vectors:
            raise ValueError(
                f"there must be at least one actor, vector, or frame in the scene "
            )
        return self


    @model_validator(mode="after")
    def validate_node_name_uniqueness(self):
        ann = self.get_all_node_names()
        if len(ann) != len(set(ann)):
            duplicates = {k for k in ann if ann.count(k) > 1}
            msg = (f"Duplicate names detected: {duplicates}. There can be no duplicate "
                  f"names across all actors: frames: and vectors: dicts. Rename and try "
                  f"again.")
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_cameras_parents(self):
      if self.cameras == None:
        print("WARNING: No cameras: defined in scene. Default camera"
              " will be placed at world coordinate origin. See cameras:"
              " section of documentation for more information.")
        return self
      for cam in self.cameras:
        if self.cameras[cam].parent:
          parent_name = self.cameras[cam].parent
          ann = self.get_all_node_names()
          if parent_name not in ann:
              raise ValueError(
                  f"camera {cam} cannot follow parent: {cam.parent} as it is not "
                  f"a valid actor, vector, or frame. Valid options are {ann}")
      return self

    @model_validator(mode="after")
    def validate_cameras_priorities(self):
      if self.cameras == None:
        return self
      all_priorities = [self.cameras[c].priority for c in self.cameras if self.cameras[c].priority != 0 ]
      no_dupes = set(all_priorities)
      if len(all_priorities) != len(no_dupes):
        #import pdb; pdb.set_trace()
        msg =(f"Duplicate camera priorities found. If specifying "
              f"priority: the value must be > 0 and unique across all "
              f"defined cameras:")
        raise ValueError(msg)
      return self

    @model_validator(mode="after")
    def validate_sun_driven_by(self):
      if self.sun == None:
        return self
      if self.sun.driven_by:
        vector_names = list(self.vectors.keys()) if self.vectors else []
        if self.sun.driven_by not in vector_names:
            raise ValueError(
                f"sun cannot be driven_by: {self.sun.driven_by} as it is not "
                f"a valid vector in the scene. Valid options are {vector_names}")
      return self

    def get_node_dict(self, name):
        if self.actors and name in self.actors:
          return self.actors[name]
        elif self.vectors and name in self.vectors:
          return self.vectors[name]
        elif self.frames and name in self.frames:
          return self.frames[name]
        return None

    def strip_brackets(self, text):
        # Pattern: match '[' and everything after it until the end of the string
        return re.sub(r'\[.*$', '', text)

    @model_validator(mode="after")
    def validate_actor_driven_by(self):
      """
      Ensure all actor: driven_by: clauses are referencing a data source
      alias that exists
      """
      ann = self.get_all_node_names()
      if not ann:
        return self
      for a in ann:
        thedict = self.get_node_dict(a)
        if thedict.driven_by == None:
          continue
        dsa = list(self.data_source.trickpy.keys())
        if thedict.driven_by.time not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: time: {thedict.driven_by.time} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.pos and self.strip_brackets(thedict.driven_by.pos) not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: pos: {thedict.driven_by.pos} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.rot and self.strip_brackets(thedict.driven_by.rot) not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: rot: {thedict.driven_by.rot} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.scale and self.strip_brackets(thedict.driven_by.scale) not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: scale: {thedict.driven_by.scale} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.opacity and self.strip_brackets(thedict.driven_by.opacity) not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: opacity: {thedict.driven_by.opacity} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
      return self
 
    @model_validator(mode="after")
    def validate_actor_provide_data(self):
      """
      Ensure all actor: provide_data: clauses are referencing a data source
      alias that exists
      """
      ann = self.get_all_node_names()
      if not ann:
        return self
      for a in ann:
        thedict = self.get_node_dict(a)
        if thedict.provide_data == None:
          continue
        dsa = list(self.data_source.trickpy.keys())
        if thedict.provide_data.time not in dsa:
          raise ValueError(
            f"node {a} cannot have provide_data: time: {thedict.provide_data.time} as it "
            f"is not a valid data source alias. Valid data source aliases are {dsa}")
        for alias in thedict.provide_data.aliases:
          if alias not in dsa:
            raise ValueError(
              f"node {a} cannot have provide_data: {alias} as it is not a valid "
              f"data source alias. Valid data source aliases are {dsa}")
      return self

    @model_validator(mode="after")
    def validate_playback_config(self):
        if self.playback_speed is not None and not self.playback_speeds:
            raise ValueError(
                "playback_speeds must be defined if playback_speed is set"
            )
        return self

    @model_validator(mode="after")
    def normalize_nulls(self):
        """
        This prevents a key with no value (null) from being possible
        TODO: we may need to do this with more fields, this is just an example
        of how to do it
        """
        if self.playback_speeds is None:
            self.playback_speeds = VIRGO_DEFAULT_PLAYBACK_SPEEDS.copy()
        if self.background_color is None:
            self.background_color = VIRGO_DEFAULT_BACKGROUND_COLOR.copy()
        return self


class VirgoDictVerifier:
    """
    Entrypoint class for using the Virgo Dict Verifier
    """
    def __init__(self, scene_dict, yaml_file=None):
        # Optional path to associated yaml file for better error messages
        self.yaml_file = yaml_file
        self.scene_dict = scene_dict.copy()

    def verify(self, terminate=True):
        try:
            verified_schema = SceneSchema.model_validate(self.scene_dict)
            # the mode='json' ensures all primitives are dumped in the dict
            verified_scene = verified_schema.model_dump(mode='json')

            # DEBUG INFO ON THE SCHEMA CAN BE SHOWN LIKE THIS IF NEEEDED
            # Write the dictionary to a JSON file
            #import json
            #with open('.schema.json', 'w') as json_file:
            #    json.dump(verified_schema.model_json_schema(), json_file, indent=4)

            return verified_scene

        except ValidationError as e:
            title = ("VIRGO Scene configuration error")
            if self.yaml_file:
              title += (f" in {self.yaml_file}")
            title += (":")
            print(title)
            print(format_pydantic_errors(e))
            print("See the documentation for details on the VIRGO scene definition")
            if terminate:
                raise SystemExit(1)
            else:
                raise e
