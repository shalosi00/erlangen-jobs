"""Dedupe layer tests — ported from scripts/test_dedupe_upgrade.py (Task 12
production evidence) into the F15 unittest suite, plus F19 stopword pin."""
import sys, unittest
sys.path.insert(0, "/home/z/my-project")

from pipeline.core import Job, dedupe, canon_url, _jac, title_key

try:
    import rapidfuzz  # noqa: F401
    HAS_FUZZ = True
except ImportError:
    HAS_FUZZ = False


def mk(title, company, city="Nürnberg", url="", source="BA"):
    return Job(source=source, title=title, company=company, city=city, url=url)


class TestDedupeProductionCases(unittest.TestCase):
    def test_a_same_url_different_titles_merge(self):
        a1 = mk("IT System Engineer (m/w/d) z/OS Netzwerk und Security",
                "Akkodis Germany Tech Experts",
                url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12634-BB-64")
        a2 = mk("System Engineer Netzwerk (m/w/d)", "Akkodis",
                url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12634-BB-64",
                source="XING")
        r = dedupe([a1, a2])
        self.assertEqual(len(r), 1)
        self.assertIn("XING", r[0].source)
        self.assertIn("BA", r[0].source)
        self.assertEqual(canon_url(a1.url),
                         "arbeitsagentur.de/jobsuche/jobdetail/12634-bb-64")

    def test_b_ref_id_variants_merge(self):
        b1 = mk("IT-Supporter (m/w/d) ID 7285", "BAVARIAHEADHUNTER GmbH")
        b2 = mk("IT-Supporter (m/w/d) ID SW72", "BAVARIAHEADHUNTER GmbH")
        r = dedupe([b1, b2])
        self.assertEqual(len(r), 1)
        self.assertEqual(title_key("IT-Supporter (m/w/d) ID 7285"),
                         title_key("IT-Supporter (m/w/d)"))

    def test_c_brunel_vs_ferchau_no_merge_but_flag(self):
        c1 = mk("IT-Spezialist (w/m/d)", "Brunel GmbH", city="Erlangen")
        c2 = mk("IT-Spezialist Netzwerk & Connectivity", "FERCHAU GmbH", city="Erlangen")
        r = dedupe([c1, c2])
        self.assertEqual(len(r), 2)     # different employers must NOT merge
        if HAS_FUZZ:
            self.assertIn("near-dupe-candidate", r[0].notes)
            self.assertIn("near-dupe-candidate", r[1].notes)

    def test_d_works_without_rapidfuzz(self):
        r = dedupe([mk("IT Admin", "X GmbH"), mk("IT Admin", "X GmbH")])
        self.assertEqual(len(r), 1)

    def test_legal_form_tokens_ignored(self):
        r = dedupe([mk("IT-Administrator", "Muster Personalberatung GmbH"),
                    mk("IT-Administrator", "Muster GmbH")])
        self.assertEqual(len(r), 1)


class TestF19Stopwords(unittest.TestCase):
    def test_no_duplicate_stopwords(self):
        # regression: 'den' appeared twice in the stopword set literal
        import inspect
        from pipeline import core
        src = inspect.getsource(core._jac)
        self.assertEqual(src.count('"den"'), 1)
        self.assertEqual(src.count('stop = {'), 1)

    def test_umlaut_and_prep_stopwords(self):
        # behavior: umlaut/ascii variants of 'für' + added preps are ignored
        self.assertEqual(_jac(title_key("Support für Server"),
                              title_key("Support Server")), 1.0)
        self.assertEqual(_jac(title_key("Support fuer Server"),
                              title_key("Support Server")), 1.0)
        self.assertEqual(_jac(title_key("Admin von Systemen"),
                              title_key("Admin Systemen")), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
