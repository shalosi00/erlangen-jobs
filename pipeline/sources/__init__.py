"""Source registry — imports every module so @register calls run.
Import primitives from pipeline.sources._base (not here) inside source modules."""
from pipeline.sources._base import SOURCES, GEO_SCOPE, register, check_http  # re-export
from pipeline.sources import (ba, eures, xing, html_boards, json_apis, rss_apis,
                              jobspy_src, keyed_apis, kimeta, stellenanzeigen)  # noqa: F401

RUN_ORDER = ["ba", "indeed", "linkedin", "xing", "eures", "kimeta", "stellenanzeigen",
             "infranken", "getinit",
             "connecticum", "berufsstart", "talent", "arbeitnow", "adzuna", "jooble",
             "careerjet", "whatjobs", "remotive", "remoteok", "jobicy", "wwr", "himalayas"]
