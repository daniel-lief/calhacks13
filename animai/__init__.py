"""
Animai: narrated educational animations for every subject, built on the ManimGL engine
(the local ../animlib copy).

Scene files start with:

    from animai import *

which brings in all of ManimGL plus Animai's core (themes, layout, narration) and the
subject libraries.
"""
import sys as _sys

__version__ = "0.1.0"

# `python -m animai ...` (the render launcher) only needs paths and themes, and ManimGL
# parses sys.argv as soon as it is imported, so the launcher must not load the engine.
# While Python is still locating a -m module, sys.argv[0] is "-m".
if _sys.argv[:1] != ["-m"]:
    from animai.engine import bootstrap as _bootstrap

    _bootstrap()  # Must run before animlib creates its GPU device

    from animlib import *  # noqa: E402,F401,F403
    from animai.core import *  # noqa: E402,F401,F403
    from animai.subjects import *  # noqa: E402,F401,F403
