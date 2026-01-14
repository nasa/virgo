import math
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
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

class PlaybackMode(str, Enum):
    PAUSED = "PAUSED"
    PLAYING = "PLAYING"
class LightingMode(str, Enum):
    realistic = 'realistic'
    headlight = 'headlight'
    ultrabright = 'ultrabright'
class AxesWhen(str, Enum):
    toggled = "toggled"
    picked = "picked"
    always = "always"
    never = "never"
class AxesStyle(str, Enum):
    line = "line"
    cylinder = "cylinder"

# Complex types defined here
RGBColor = list[float, float, float]
Vec3 = list[float, float, float]

def validate_vec3(value: Vec3, name: str):
    if len(value) != 3:
        raise ValueError(f"{name} must have exactly 3 elements")
    return value

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
    position: Optional[Vec3] = None
    focal_point: Optional[Vec3] = None
    view_up: Optional[Vec3] = None
    follow: Optional[str] = None
    near_clipping_plane_tolerance: Optional[float] = None

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
    when: Optional[AxesWhen] = None
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

class LabelSchema(BaseModel):
    text: str
    pos: Vec3 = [0.0, 0.0, 0.0]
    ypr: Vec3 = [0.0, 0.0, 0.0]
    scale: Optional[float] = VIRGO_DEFAULT_LABEL_SCALE
    color: RGBColor = VIRGO_DEFAULT_LABEL_COLOR

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        if any(not (0.0 <= c <= 1.0) for c in v):
            raise ValueError("A label's color values must be between 0.0 and 1.0")
        return v


class ActorBaseSchema(BaseModel):
    # --- Optional geometry ---
    scale: float = 1.0
    opacity: float = 1.0
    pos: Vec3 = [0.0, 0.0, 0.0]
    ypr: Vec3 = [0.0, 0.0, 0.0]
    color: Optional[RGBColor] = None

    # --- Interaction ---
    pickable: bool = True

    # --- Subsystems ---
    axes: Optional[AxesSchema] = None
    trail: Optional[TrailSchema] = None
    driven_by: Optional[ActorDrivenBySchema] = None
    labels: Dict[str, LabelSchema] = Field(default_factory=dict)

    # --- Relationships ---
    parent: Optional[str] = None
    provide_aliases: List[str] = Field(default_factory=list)

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
        return data

class VectorSchema(ActorBaseSchema):
    tip_length:   Optional[float]  = None
    tip_radius:   Optional[float]  = None
    shaft_radius: Optional[float] = None
    driven_by: Optional[VectorDrivenBySchema] = None

    # A vector is just an actor with arrow as mesh
    @model_validator(mode='before')
    @classmethod
    def ensure_field_not_given(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if 'mesh' in data:
            raise ValueError('vectors cannot have a mesh: field')
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
    camera: CameraSchema = Field (
        default=None,
        description="Dictionary of camera data"
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
    def validate_camera_follow_node(self):
      if self.camera == None:
        return self
      if self.camera.follow:
        ann = self.get_all_node_names()
        if self.camera.follow not in ann:
            raise ValueError(
                f"camera cannot follow: {self.camera.follow} as it is not "
                f"a valid actor, vector, or frame. Valid options are {ann}")
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
        if thedict.driven_by.pos and thedict.driven_by.pos not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: pos: {thedict.driven_by.pos} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.rot and thedict.driven_by.rot not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: rot: {thedict.driven_by.rot} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.scale and thedict.driven_by.scale not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: scale: {thedict.driven_by.scale} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
        if thedict.driven_by.opacity and thedict.driven_by.opacity not in self.data_source.trickpy:
          raise ValueError(
            f"node {a} cannot have driven_by: opacity: {thedict.driven_by.opacity} as it is not "
            f"a valid data source alias. Valid data source aliases are {dsa}")
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