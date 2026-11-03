"""Source registry — imports every module so @register calls run.
Import primitives from pipeline.sources._base (not here) inside source modules.
The `as` aliases are deliberate re-export markers: these imports exist for
their @register side effects and for `from pipeline.sources import X` users."""
from pipeline.sources import (
    ba as ba,
)
from pipeline.sources import (
    eures as eures,
)
from pipeline.sources import (
    html_boards as html_boards,
)
from pipeline.sources import (
    jobspy_src as jobspy_src,
)
from pipeline.sources import (
    json_apis as json_apis,
)
from pipeline.sources import (
    keyed_apis as keyed_apis,
)
from pipeline.sources import (
    kimeta as kimeta,
)
from pipeline.sources import (
    rss_apis as rss_apis,
)
from pipeline.sources import (
    stellenanzeigen as stellenanzeigen,
)
from pipeline.sources import (
    xing as xing,
)
from pipeline.sources._base import (  # re-export
    GEO_SCOPE as GEO_SCOPE,
)
from pipeline.sources._base import (
    SOURCES as SOURCES,
)
from pipeline.sources._base import (
    check_http as check_http,
)
from pipeline.sources._base import (
    register as register,
)

__all__ = ["GEO_SCOPE", "SOURCES", "ba", "check_http", "eures", "html_boards",
           "jobspy_src", "json_apis", "keyed_apis", "kimeta", "register",
           "rss_apis", "stellenanzeigen", "xing"]

RUN_ORDER = ["ba", "indeed", "linkedin", "xing", "eures", "kimeta", "stellenanzeigen",
             "infranken", "getinit",
             "connecticum", "berufsstart", "talent", "arbeitnow", "adzuna", "jooble",
             "careerjet", "whatjobs", "remotive", "remoteok", "jobicy", "wwr", "himalayas"]
