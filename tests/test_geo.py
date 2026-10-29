"""F1 unit pins — transit classifier + zero-transfer filter regex (unittest).

Source of truth: research/2-e/findings.md §3.1-3.3 via
data/geo/transit_whitelist.json. The pins below are the ones specced in
research/project-review/findings.md F1, plus data-integrity checks.
"""
import sys, unittest
sys.path.insert(0, "/home/z/my-project")

from pipeline import geo
from pipeline.core import Job


class TestDataIntegrity(unittest.TestCase):
    def test_counts(self):
        d = geo._load()
        self.assertEqual(len(d["whitelist"]) + 1, 30)   # 29 municipalities + Erlangen
        self.assertEqual(len(d["borderline"]), 5)        # §3.2
        self.assertGreaterEqual(len(d["excluded_1xfer"]), 20)
        self.assertGreaterEqual(len(d["excluded_no_rail"]), 15)

    def test_every_entry_has_regex(self):
        d = geo._load()
        for section in ("whitelist", "borderline", "excluded_1xfer",
                        "excluded_no_rail", "excluded_far"):
            for e in d[section]:
                self.assertTrue(e["_rx"].pattern, section)


class TestTransitPins(unittest.TestCase):
    def check(self, blob, expected, plz=""):
        self.assertEqual(geo.transit_for(blob, plz), expected)

    def test_whitelisted_0xfer(self):
        self.check("Coburg", "0-xfer (47min)")
        self.check("Lichtenfels", "0-xfer (37min)")
        self.check("Haßfurt", "0-xfer (41min)")
        self.check("Hassfurt", "0-xfer (41min)")          # ascii variant
        self.check("Bamberg", "0-xfer (20min)")
        self.check("Schwaig", "0-xfer (43min)")
        self.check("Lauf an der Pegnitz", "0-xfer (52min)")
        self.check("Breitengüßbach", "0-xfer (30min)")
        self.check("Breitenguessbach", "0-xfer (30min)")  # keyboard variant
        self.check("Erlangen", "0-xfer (0min)")
        self.check("Fürth (Bay) Hbf", "0-xfer (7min)")
        self.check("Vach", "0-xfer (7min)")               # Fürth district stop
        self.check("Kersbach", "0-xfer (7min)")           # Forchheim district stop

    def test_plz_disambiguation_hochstadt(self):
        # 'Höchstadt' alone = the no-rail Aisch town; a.Main needs suffix or PLZ
        self.check("Höchstadt", "none")
        self.check("Höchstadt a.d. Aisch", "none")
        self.check("Höchstadt-Marktzeuln", "0-xfer (56min)")
        self.check("Hochstadt a. Main", "0-xfer (56min)")
        self.check("Hoechstadt", "none", plz="")           # bare name stays no-rail
        self.check("", "0-xfer (56min)", plz="96272")      # PLZ fallback

    def test_limited_ic61(self):
        self.check("Kronach", "limited (51min)")
        self.check("Ansbach", "limited (48min)")

    def test_borderline(self):
        self.check("Hersbruck", "borderline (63min)")
        self.check("Küps", "borderline (61min)")
        self.check("Kueps", "borderline (61min)")
        self.check("Ebersdorf b.Coburg", "borderline (62min)")
        self.check("Dörfles-Esbach", "borderline (63min)")

    def test_excluded_1xfer(self):
        self.check("Neumarkt in der Oberpfalz", "1-xfer")
        self.check("Neumarkt", "1-xfer")
        self.check("Feucht", "1-xfer")
        self.check("Altdorf bei Nürnberg", "1-xfer")
        self.check("Schwabach", "1-xfer")
        self.check("Zirndorf", "1-xfer")
        self.check("Winkelhaid", "1-xfer")
        self.check("Postbauer-Heng", "1-xfer")
        self.check("Würzburg", "1-xfer")
        self.check("Eckental", "1-xfer")
        self.check("Kalchreuth", "1-xfer")

    def test_excluded_no_rail(self):
        self.check("Herzogenaurach", "none")
        self.check("Neunkirchen am Brand", "none")
        self.check("Neunkirchen a. Brand", "none")
        self.check("Pretzfeld", "none")
        self.check("Uttenreuth", "none")
        self.check("Buckenhof", "none")

    def test_excluded_far(self):
        self.check("Rödental", ">60min")
        self.check("Sonneberg", ">60min")

    def test_unknown(self):
        self.check("", "")
        self.check("Berlin", "")
        self.check("hemhofen", "")    # never GTFS-verified -> unverified, not whitelisted


class TestZeroXferRegex(unittest.TestCase):
    """The hard filter for country-scoped sources = regular 0-transfer set only."""

    def test_positive(self):
        rx = geo.zero_xfer_rx()
        for town in ("Erlangen", "Fürth", "Nürnberg", "Coburg", "Lichtenfels",
                     "Bamberg", "Baiersdorf", "Lauf", "Haßfurt", "Forchheim"):
            self.assertTrue(rx.search(f"IT-Admin gesucht in {town}"), town)

    def test_negative(self):
        rx = geo.zero_xfer_rx()
        for town in ("Neumarkt", "Feucht", "Altdorf", "Schwabach", "Zirndorf",
                     "Herzogenaurach", "Hersbruck", "Kronach", "Ansbach", "Würzburg",
                     "Neunkirchen am Brand", "Pretzfeld"):
            self.assertFalse(rx.search(f"IT-Admin gesucht in {town}"), town)

    def test_no_false_positive_on_compounds(self):
        rx = geo.zero_xfer_rx()
        self.assertFalse(rx.search("Laufzeit 450 Euro"))
        self.assertFalse(rx.search("Steinbeis Beratung"))     # \bstein\b regression
        self.assertFalse(rx.search("Rothaarige"))


class TestClassifyJobLocation(unittest.TestCase):
    def test_strict_blob_wins(self):
        j = Job(source="T", title="IT-Supporter", company="X",
                city="Neumarkt in der Oberpfalz",
                description="Unternehmen mit Standorten in Coburg und Bamberg")
        # strict = city+loc+title -> the ACTUAL location is Neumarkt, not the desc mentions
        self.assertEqual(geo.classify_job_location(j), "1-xfer")

    def test_wide_fallback(self):
        j = Job(source="T", title="IT-Supporter", company="X", city="",
                description="Arbeitsort: Coburg, Ketschendorfer Str. 5")
        self.assertEqual(geo.classify_job_location(j), "0-xfer (47min)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
