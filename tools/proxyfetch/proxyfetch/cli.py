"""Command-line interface.

I/O contract (stable, for humans and AI agents alike):
* stdout -- data only: the human table OR (with --json) one JSON payload.
* stderr -- logs always.
* exit codes: 0 ok | 1 no results | 2 usage | 3 no proxies | 4 error | 130 ^C
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

from . import __version__, errors, recipes, userconfig
from .config import Config, default_state_dir
from .logutil import Logger
from .pipeline import run as pipeline_run

PROGRAM = "proxyfetch"

EPILOG = """exit codes:
  0    results collected
  1    ran, but zero items extracted
  2    usage/config error
  3    no working proxy found
  4    unexpected internal error
  130  interrupted (SIGINT) -- partial results may be saved

examples:
  proxyfetch "https://www.autoscout24.de/lst/dacia/jogger" --pages 3
  proxyfetch "https://example.com/page" --json --out /tmp/out
  proxyfetch <url> --fresh --budget 600 --headed
  proxyfetch <url> --css 'article.product' --field title='h3 a::text' \
      --field url='a::attr(href)' --page-template 'https://x/list/page-{n}.html'
  proxyfetch 'https://api.x.com/v1/items' --json-key data.items
  proxyfetch config set engine aiohttp   # set once, remembered forever
  proxyfetch config list
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROGRAM,
        description=("Fetch any URL through an auto-managed free-proxy pool: "
                     "harvest -> verify -> rotate -> self-heal -> stealth-browser "
                     "fallback. Data on stdout, logs on stderr."),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url_pos", nargs="?", metavar="URL",
                   help="target URL (or use --url)")
    p.add_argument("--url", dest="url_opt", metavar="URL", help=argparse.SUPPRESS)
    p.add_argument("--pages", type=int, default=3, metavar="N",
                   help="result pages to fetch (default: 3)")
    p.add_argument("--name", metavar="NAME",
                   help="run name for output files (default: derived from host)")
    p.add_argument("--recipe", choices=("auto", *sorted(recipes.RECIPES)),
                   default="auto", help="extraction recipe (default: auto-detect)")
    p.add_argument("--out", metavar="DIR",
                   help="output directory (default: ./out or $PROXYFETCH_OUT)")
    p.add_argument("--no-save", action="store_true",
                   help="do not write JSON/CSV files")
    p.add_argument("--csv-delimiter", default=";", metavar="CH",
                   help="CSV delimiter (default: ';' -- Excel friendly)")

    g = p.add_argument_group("proxy supply")
    g.add_argument("--fresh", action="store_true",
                   help="ignore cached winners, harvest from scratch")
    g.add_argument("--engine", choices=("aiohttp", "threads"),
                   help="probe engine for THIS run only "
                        "(default: saved config or aiohttp)")
    g.add_argument("--concurrency", type=int, metavar="N",
                   help="max parallel probes for THIS run only "
                        "(default: saved config or 300)")
    g.add_argument("--state-dir", metavar="DIR",
                   help=f"winner-cache dir (default: {default_state_dir()} or $PROXYFETCH_STATE_DIR)")
    g.add_argument("--budget", type=int, metavar="S",
                   help="wall-clock budget in seconds (default: 420)")
    g.add_argument("--timeout", type=float, metavar="S", dest="fetch_timeout",
                   help="per-request timeout in seconds (default: 40)")

    s = p.add_argument_group("scrape anything (universal extraction)")
    s.add_argument("--css", metavar="SEL",
                   help="item CSS selector -- scrape any site, e.g. 'article.product'")
    s.add_argument("--field", action="append", metavar="NAME=SEL",
                   help="field mapping for --css, repeatable: "
                        "title='h3 a::text' url='a::attr(href)' (soupsieve syntax)")
    s.add_argument("--json-key", metavar="PATH",
                   help="dot-path to the items array of a JSON endpoint (e.g. data.items)")
    s.add_argument("--table", type=int, metavar="N",
                   help="scrape HTML table #N (1-based; default: largest table)")
    s.add_argument("--page-template", metavar="TPL",
                   help="pagination template with {n}, e.g. 'https://x.com/list/page-{n}.html'")
    s.add_argument("--no-direct", action="store_true",
                   help="skip the direct-fetch fast path; always use the proxy pool")

    b = p.add_argument_group("browser")
    b.add_argument("--headed", action="store_true",
                   help="show the stealth browser window (forces cloakbrowser; "
                        "lightpanda is always headless)")
    b.add_argument("--no-browser", action="store_true",
                   help="disable browser escalation/proof entirely")
    b.add_argument("--browser-engine", choices=("auto", "lightpanda", "cloakbrowser"),
                   help="render engine: lightpanda (self-healing CDP, proxy-aware) "
                        "with cloakbrowser fallback, or force one "
                        "(default: auto; $PROXYFETCH_BROWSER_ENGINE)")
    b.add_argument("--lightpanda-bin", metavar="PATH",
                   help="lightpanda binary path (default: $LIGHTPANDA_BIN, "
                        "$PATH, or common install locations)")
    b.add_argument("--watchdog", type=int, metavar="S",
                   help="hard kill per browser attempt (default: 110)")
    b.add_argument("--locale", help="browser locale, e.g. de-DE")
    b.add_argument("--timezone", help="browser timezone, e.g. Europe/Berlin")

    o = p.add_argument_group("output & logging")
    o.add_argument("--json", action="store_true", dest="json_mode",
                   help="agent mode: single JSON payload on stdout, no table")
    o.add_argument("--quiet", action="store_true", help="errors/warnings only")
    o.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    o.add_argument("--json-logs", action="store_true",
                   help="NDJSON log lines on stderr (machine monitoring)")
    o.add_argument("--log-file", metavar="FILE", help="mirror logs to a file")
    o.add_argument("--debug", action="store_true", help="show tracebacks on errors")
    o.add_argument("--version", action="version",
                   version=f"{PROGRAM} {__version__}")
    return p


def build_config_parser() -> argparse.ArgumentParser:
    """Parser for `proxyfetch config <action> ...` (kept separate from the
    main parser so the optional positional URL never collides with it)."""
    cp = argparse.ArgumentParser(
        prog=f"{PROGRAM} config",
        description=("Show or set persistent defaults. Resolution: CLI flag "
                     "> env > saved config > built-in default."))
    cp.add_argument("--state-dir", metavar="DIR",
                    help=f"settings location (default: {default_state_dir()} or $PROXYFETCH_STATE_DIR)")
    cp.add_argument("--json", action="store_true", dest="json_mode",
                    help="print settings as a single JSON object")
    sub = cp.add_subparsers(dest="config_cmd", metavar="ACTION")
    sub.add_parser("list", help="show saved settings and built-in defaults")
    cget = sub.add_parser("get", help="print one setting's value")
    cget.add_argument("key", choices=userconfig.keys())
    cset = sub.add_parser("set", help="persist a setting (remembered forever)")
    cset.add_argument("key", choices=userconfig.keys())
    cset.add_argument("value", metavar="VALUE")
    cunset = sub.add_parser("unset", help="reset a setting to its default")
    cunset.add_argument("key", choices=userconfig.keys())
    return cp


def _error_payload(code: str, message: str, hint: str | None,
                   cfg: Config | None = None) -> dict:
    doc = {
        "schema": "proxyfetch.result/v1",
        "tool": "proxyfetch",
        "version": __version__,
        "ok": False,
        "count": 0,
        "items": [],
        "interrupted": False,
        "error": {"code": code, "message": message, "hint": hint},
    }
    if cfg is not None:
        doc["target"] = {"url": cfg.url, "recipe": cfg.recipe}
    return doc


def _config_main(args) -> int:
    """Handle `proxyfetch config ...` -- data goes to stdout (contract)."""
    action = getattr(args, "config_cmd", None) or "list"
    state_dir = getattr(args, "state_dir", None)
    if action == "set":
        saved = userconfig.set_value(args.key, args.value, state_dir)
        print(f"saved: {args.key}={saved}  ->  {userconfig.path(state_dir)}")
        print(f"every future run will use {args.key}={saved} "
              f"(override once with --{args.key})")
        return errors.EXIT_OK
    if action == "unset":
        userconfig.unset_value(args.key, state_dir)
        print(f"reset: {args.key} -> default ({userconfig.default_of(args.key)})")
        return errors.EXIT_OK
    if action == "get":
        saved = userconfig.load(state_dir)
        print(saved.get(args.key, userconfig.default_of(args.key)))
        return errors.EXIT_OK
    # list (default)
    saved = userconfig.load(state_dir)
    if getattr(args, "json_mode", False):
        print(json.dumps({**userconfig.defaults(), **saved}, sort_keys=True))
        return errors.EXIT_OK
    print(f"proxyfetch settings ({userconfig.path(state_dir)}):")
    for k in userconfig.keys():
        val = saved.get(k)
        src = "saved" if val is not None else "default"
        print(f"  {k:<14} {val if val is not None else userconfig.default_of(k)!s:<10} [{src}]")
    print(f"  ({userconfig.describe('engine')})")
    print("change with: proxyfetch config set <key> <value>")
    return errors.EXIT_OK


def resolve_engine(cfg: Config, engine_flag: str | None,
                   concurrency_flag: int | None, saved: dict) -> None:
    """Resolution chain: CLI flag > env > saved config > dataclass default."""
    env_engine = (os.environ.get("PROXYFETCH_ENGINE") or "").strip().lower()
    engine = engine_flag or env_engine or saved.get("engine")
    if engine is not None:
        if engine not in ("aiohttp", "threads"):
            raise errors.ConfigError(
                f"engine must be 'aiohttp' or 'threads' (got {engine!r})",
                hint="proxyfetch config set engine aiohttp")
        cfg.engine = engine
    conc = concurrency_flag
    if conc is None:
        raw = os.environ.get("PROXYFETCH_CONCURRENCY")
        if raw:
            try:
                conc = int(raw)
            except ValueError:
                raise errors.ConfigError(
                    f"environment variable PROXYFETCH_CONCURRENCY={raw!r} "
                    "is not an integer")
    if conc is None:
        conc = saved.get("concurrency")
    if conc is not None:
        try:
            cfg.concurrency = int(conc)
        except (TypeError, ValueError):
            raise errors.ConfigError(
                f"saved concurrency {conc!r} is not an integer -- fix with: "
                "proxyfetch config set concurrency 300")


def _parse_fields(raw_list: list[str] | None) -> dict | None:
    """['title=h3 a::text', ...] -> {'title': 'h3 a::text', ...}"""
    if not raw_list:
        return None
    fields: dict = {}
    for raw in raw_list:
        if "=" not in raw:
            raise errors.ConfigError(
                f"--field expects NAME=SELECTOR (got {raw!r})",
                hint="e.g. --field title='h3 a::text'")
        name, sel = raw.split("=", 1)
        name = name.strip()
        if not name:
            raise errors.ConfigError(
                f"--field needs a name before '=' (got {raw!r})")
        fields[name] = sel.strip() or None
    return fields


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `config` is dispatched first -- a dedicated parser avoids clashing
    # with the main parser's optional positional URL.
    if argv and argv[0] == "config":
        try:
            return _config_main(build_config_parser().parse_args(argv[1:]))
        except errors.ProxyFetchError as e:
            print(f"error: {e}" + (f"  [{e.hint}]" if e.hint else ""),
                  file=sys.stderr)
            return e.exit_code

    parser = build_parser()
    args = parser.parse_args(argv)

    url = args.url_pos or args.url_opt
    cfg = Config(url=url or "")
    if args.out:
        cfg.out_dir = args.out
    if args.state_dir:
        cfg.state_dir = args.state_dir
    for attr, arg in (("pages", args.pages), ("name", args.name),
                      ("recipe", args.recipe), ("save", not args.no_save),
                      ("csv_delimiter", args.csv_delimiter),
                      ("fresh", args.fresh), ("use_browser", not args.no_browser),
                      ("headed", args.headed), ("locale", args.locale),
                      ("timezone", args.timezone), ("json_mode", args.json_mode),
                      ("quiet", args.quiet), ("no_color", args.no_color),
                      ("json_logs", args.json_logs), ("log_file", args.log_file),
                      ("debug", args.debug)):
        setattr(cfg, attr, arg)
    resolve_engine(cfg, args.engine, args.concurrency,
                   userconfig.load(args.state_dir))
    try:
        cfg.fields = _parse_fields(args.field)
    except errors.ProxyFetchError as e:
        return _fail(args, cfg, Logger(quiet=True), e.exit_code, e.code,
                     str(e), e.hint)
    if args.css:
        cfg.css_selector = args.css
    if args.json_key:
        cfg.json_key = args.json_key
    if args.table is not None:
        cfg.table_index = args.table
    if args.page_template:
        cfg.page_template = args.page_template
    if args.no_direct or (os.environ.get("PROXYFETCH_NO_DIRECT", "").strip().lower()
                          in ("1", "true", "yes", "on")):
        cfg.direct_first = False
    if args.budget is not None:
        cfg.budget_s = args.budget
    if args.fetch_timeout is not None:
        cfg.fetch_timeout_s = args.fetch_timeout
    if args.watchdog is not None:
        cfg.watchdog_s = args.watchdog
    if args.browser_engine:
        cfg.browser_engine = args.browser_engine
    elif os.environ.get("PROXYFETCH_BROWSER_ENGINE", "").strip():
        cfg.browser_engine = os.environ["PROXYFETCH_BROWSER_ENGINE"].strip()
    if args.lightpanda_bin:
        cfg.lightpanda_bin = args.lightpanda_bin

    logger = Logger(quiet=cfg.quiet, colors=not cfg.no_color,
                    json_lines=cfg.json_logs, log_file=cfg.log_file)
    try:
        payload = pipeline_run(cfg, logger)
        if cfg.json_mode:
            json.dump(payload, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
        return errors.EXIT_OK
    except errors.ProxyFetchError as e:
        return _fail(args, cfg, logger, e.exit_code, e.code, str(e), e.hint)
    except KeyboardInterrupt:
        logger.error("interrupted")
        return _fail(args, cfg, logger, errors.EXIT_INTERRUPTED, "interrupted",
                     "interrupted by user", "partial results may exist in the out dir")
    except Exception as e:  # noqa: BLE001 -- last-resort guard for the CLI boundary
        if args.debug:
            traceback.print_exc()
        return _fail(args, cfg, logger, errors.EXIT_ERROR, "internal_error",
                     f"{type(e).__name__}: {e}",
                     "re-run with --debug for the full traceback")
    finally:
        logger.close()


def _fail(args, cfg, logger, exit_code: int, code: str, message: str,
          hint: str | None) -> int:
    logger.error(message + (f"  [{hint}]" if hint else ""))
    if getattr(args, "json_mode", False):
        json.dump(_error_payload(code, message, hint, cfg), sys.stdout,
                  ensure_ascii=False)
        sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
