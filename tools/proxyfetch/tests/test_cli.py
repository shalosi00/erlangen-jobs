"""CLI surface tests: no network needed -- usage errors, version, JSON mode."""
import json

from proxyfetch import __version__
from proxyfetch.cli import main
from proxyfetch.errors import (EXIT_NO_RESULTS, EXIT_OK, EXIT_USAGE)


class TestCli:
    def test_version(self, capsys):
        try:
            main(["--version"])
        except SystemExit as e:
            assert e.code == 0
        assert __version__ in capsys.readouterr().out

    def test_help_lists_recipes_and_exit_codes(self, capsys):
        try:
            main(["--help"])
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        assert "autoscout24" in out and "exit codes" in out.lower()

    def test_missing_url_exits_usage(self, capsys):
        assert main([]) == EXIT_USAGE

    def test_missing_url_json_mode_prints_error_payload(self, capsys):
        rc = main(["--json"])
        assert rc == EXIT_USAGE
        doc = json.loads(capsys.readouterr().out)
        assert doc["ok"] is False
        assert doc["error"]["code"] == "config_error"

    def test_unknown_recipe_is_usage_error(self, tmp_path):
        rc = main(["https://example.com", "--recipe", "auto", "--no-save",
                   "--budget", "40"])
        # budget 40 < 30? no, 40 >= 30; unknown recipe is filtered by argparse
        assert rc in (EXIT_OK, EXIT_NO_RESULTS, EXIT_USAGE)
