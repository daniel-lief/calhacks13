try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:  # For Python <3.8 fallback
    from importlib_metadata import version, PackageNotFoundError  # type: ignore

try:
    __version__ = version("manimgl")
except PackageNotFoundError:
    __version__ = "unknown"


from animlib.config import manim_config

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from animlib.typing import *

from animlib.constants import *

from animlib.window import *

from animlib.animation.animation import *
from animlib.animation.composition import *
from animlib.animation.creation import *
from animlib.animation.fading import *
from animlib.animation.growing import *
from animlib.animation.indication import *
from animlib.animation.movement import *
from animlib.animation.numbers import *
from animlib.animation.rotation import *
from animlib.animation.specialized import *
from animlib.animation.transform import *
from animlib.animation.transform_matching_parts import *
from animlib.animation.update import *

from animlib.camera.camera import *

from animlib.mobject.boolean_ops import *
from animlib.mobject.changing import *
from animlib.mobject.coordinate_systems import *
from animlib.mobject.fractals import *
from animlib.mobject.frame import *
from animlib.mobject.functions import *
from animlib.mobject.geometry import *
from animlib.mobject.interactive import *
from animlib.mobject.matrix import *
from animlib.mobject.mobject import *
from animlib.mobject.mobject_update_utils import *
from animlib.mobject.number_line import *
from animlib.mobject.numbers import *
from animlib.mobject.probability import *
from animlib.mobject.shape_matchers import *
from animlib.mobject.svg.brace import *
from animlib.mobject.svg.drawings import *
from animlib.mobject.svg.string_mobject import *
from animlib.mobject.svg.svg_mobject import *
from animlib.mobject.svg.special_tex import *
from animlib.mobject.svg.tex_mobject import *
from animlib.mobject.svg.text_mobject import *
from animlib.mobject.three_dimensions import *
from animlib.mobject.types.dot_cloud import *
from animlib.mobject.types.image_mobject import *
from animlib.mobject.types.point_cloud_mobject import *
from animlib.mobject.types.surface import *
from animlib.mobject.types.video_mobject import *
from animlib.mobject.types.vectorized_mobject import *
from animlib.mobject.value_tracker import *
from animlib.mobject.vector_field import *

from animlib.scene.interactive_scene import *
from animlib.scene.scene import *

from animlib.renderer.shader_source import get_colormap_code
from animlib.renderer.uniform_block import *

from animlib.utils.bezier import *
from animlib.utils.cache import *
from animlib.utils.color import *
from animlib.utils.dict_ops import *
from animlib.utils.debug import *
from animlib.utils.directories import *
from animlib.utils.file_ops import *
from animlib.utils.images import *
from animlib.utils.iterables import *
from animlib.utils.paths import *
from animlib.utils.rate_functions import *
from animlib.utils.simple_functions import *
from animlib.utils.sounds import *
from animlib.utils.space_ops import *
from animlib.utils.svg_export import *
from animlib.utils.tex import *
