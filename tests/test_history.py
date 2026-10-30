"""F6/F13 tests — job memory degrades gracefully without sqlite_utils and
merges full provenance (unittest; DB tests skipped when sqlite_utils absent)."""
import os, sys, tempfile, unittest
sys.path.insert(0, "/home/z/my-project")

from pipeline.core import Job
from pipeline import history

try:
    import sqlite_utils  # noqa: F401
    HAS_SQLITE_UTILS = True
except ImportError:
    HAS_SQLITE_UTILS = False


class TestLazyImportF6(unittest.TestCase):
    def test_module_importable_without_sqlite_utils(self):
        # importing history must not require sqlite_utils (F6) — the import at
        # the top of this file succeeding IS the test
        import pipeline.history as h
        self.assertTrue(hasattr(h, "MemoryUnavailable"))

    @unittest.skipIf(HAS_SQLITE_UTILS, "sqlite_utils present — nothing to degrade")
    def test_update_raises_actionable_error_without_dep(self):
        with self.assertRaises(history.MemoryUnavailable):
            history.update([Job(source="T", title="IT-Supporter", company="X")])


@unittest.skipUnless(HAS_SQLITE_UTILS, "needs sqlite-utils")
class TestMemoryMergeF13(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_db = history.DB_PATH
        history.DB_PATH = os.path.join(self.tmp.name, "mem.db")

    def tearDown(self):
        history.DB_PATH = self._orig_db
        self.tmp.cleanup()

    def test_reseen_updates_times_seen(self):
        j = Job(source="BA", title="IT-Supporter (m/w/d)", company="X GmbH",
                city="Erlangen", url="https://a.de/1")
        s1 = history.update([j])
        self.assertEqual(s1["fresh"], 1)
        s2 = history.update([j])
        self.assertEqual(s2["known"], 1)
        self.assertEqual(s2["total"], 1)
        row = list(history._db()["postings"].rows)[0]
        self.assertEqual(row["times_seen"], 2)

    def test_url_fold_merges_provenance(self):
        a = Job(source="BA", title="System Engineer Netzwerk (m/w/d)", company="Akkodis",
                city="Nürnberg", url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12634-BB-64")
        history.update([a])
        b = Job(source="XING", title="IT System Engineer z/OS (m/w/d)", company="Akkodis Germany",
                city="Nürnberg", url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12634-BB-64")
        s = history.update([b])
        self.assertEqual(s["total"], 1)          # folded, no second row
        row = list(history._db()["postings"].rows)[0]
        self.assertIn("BA", row["source"])       # F13: multi-source provenance kept
        self.assertIn("XING", row["source"])

    def test_url_key_index_exists(self):
        idx = history._db().execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_postings_url_key'"
        ).fetchall()
        self.assertEqual(len(idx), 1)

    def test_late_columns_exist(self):
        cols = set(history._db()["postings"].columns_dict)
        for name in ("plz", "is_remote", "salary_min", "salary_max", "currency"):
            self.assertIn(name, cols)

    def test_salary_gap_fill(self):
        j1 = Job(source="BA", title="IT-Admin A", company="X GmbH", city="Erlangen",
                 url="https://a.de/a")
        history.update([j1])
        j2 = Job(source="BA", title="IT-Admin A", company="X GmbH", city="Erlangen",
                 url="https://a.de/a", salary_min=42000.0, salary_max=50000.0, currency="EUR")
        history.update([j2])
        row = list(history._db()["postings"].rows)[0]
        self.assertEqual(row["salary_min"], 42000.0)
        self.assertEqual(row["currency"], "EUR")


if __name__ == "__main__":
    unittest.main(verbosity=2)
