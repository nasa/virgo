import importlib.metadata

try:
    __version__ = importlib.metadata.version("virgo")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

from .Virgo import VirgoControlCenter, VirgoScene
from .VirgoActor import VirgoActor
from .VirgoCamera import VirgoCamera
from .VirgoAxes import VirgoAxes
from .VirgoConsole import VirgoConsole
from .VirgoDataLoader import VirgoDataLoader
from .VirgoDataPlayback import VirgoDataPlayback
from .VirgoDataSource import VirgoDataSource, VirgoDataFileSource
from .VirgoDictVerifier import VirgoDictVerifier
from .VirgoHud import VirgoHud
from .VirgoInteractorStyles import (
    VirgoTrackballInteractorStyle,
    VirgoInteractorStyleFirstPerson,
)
from .VirgoKovizInterface import KovizInterface
from .VirgoLabel import VirgoLabel
from .VirgoNode import VirgoSceneNode, VirgoSceneNodeVector
from .VirgoRendering import VirgoRendering
from .VirgoSplash import VirgoSplash
from .VirgoTrail import VirgoTrail
from .VirgoTrickpyFileLoader import VirgoTrickpyFileLoader
from .VirgoUtils import cprint, timed_debug, time_render_layers

__all__ = [
    'VirgoControlCenter',
    'VirgoScene',
    'VirgoActor',
    'VirgoCamera',
    'VirgoAxes',
    'VirgoConsole',
    'VirgoDataLoader',
    'VirgoDataPlayback',
    'VirgoDataSource',
    'VirgoDataFileSource',
    'VirgoDictVerifier',
    'VirgoHud',
    'VirgoTrackballInteractorStyle',
    'VirgoInteractorStyleFirstPerson',
    'KovizInterface',
    'VirgoLabel',
    'VirgoSceneNode',
    'VirgoSceneNodeVector',
    'quaternion_to_dcm',
    'dcm_to_quaternion',
    'is_quaternion_like',
    'is_dcm_like',
    'VirgoRendering',
    'VirgoSplash',
    'VirgoTrail',
    'VirgoTrickpyFileLoader',
    'cprint',
    'timed_debug',
    'time_render_layers',
]
