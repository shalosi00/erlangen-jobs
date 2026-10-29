"""F2/F3/F4 regression tests — the three CONFIRMED filter false-positives from
research/project-review/findings.md, plus baseline behavior pins (unittest)."""
import sys, unittest
sys.path.insert(0, "/home/z/my-project")

from pipeline.core import Job, classify_job, PARTTIME_RX, EXPERIENCE_BODY_RX


def mk(title="IT-Supporter (m/w/d)", company="Test GmbH", desc="", employment_raw=""):
    return Job(source="T", title=title, company=company, city="Erlangen",
               description=desc, employment_raw=employment_raw)


class TestF2Parttime450(unittest.TestCase):
    """bare-\\b450[ -]?€? matched headcounts and salary digits."""

    def test_headcount_450_mitarbeiter_not_parttime(self):
        j = mk(desc="Unser Kunde, ein Traditionsbetrieb mit über 450 Mitarbeitern "
                    "am Standort, sucht Unterstützung für das IT-Team. Vollzeit.")
        keep, reason = classify_job(j)
        self.assertTrue(keep, f"rejected with: {reason}")
        self.assertFalse(PARTTIME_RX.search(j.description.lower()))

    def test_salary_45000_not_parttime(self):
        self.assertFalse(PARTTIME_RX.search("jahrliches gehalt 45000 euro".lower()))

    def test_real_minijob_still_matches(self):
        for txt in ("auf 450 € Basis", "450-Euro-Job", "450€", "450 EUR", "450 Euro"):
            self.assertTrue(PARTTIME_RX.search(txt.lower()), txt)
        self.assertTrue(PARTTIME_RX.search("minijob"))
        self.assertTrue(PARTTIME_RX.search("Teilzeit (20 Std)"))
        j = mk(desc="Teilzeit auf 450 Euro Basis möglich")
        keep, reason = classify_job(j)
        self.assertFalse(keep)
        self.assertIn("parttime", reason)
        # a posting offering BOTH stays (has_vz_desc keeps it), 450-Euro line alone matches RX
        j2 = mk(desc="Vollzeit oder Teilzeit auf 450 Euro Basis möglich")
        keep2, _ = classify_job(j2)
        self.assertTrue(keep2)
        self.assertTrue(PARTTIME_RX.search("auf 450 Euro"))


class TestF3ExperienceNegation(unittest.TestCase):
    """'... erwartet wir nicht' was rejected as experience(required)."""

    def test_negated_experience_kept(self):
        j = mk(title="1st Level Support (m/w/d)",
               desc="Mindestens 3 Jahre Berufserfahrung im 1st Level Support "
                    "erwartet wir nicht – Quereinsteiger willkommen. Vollzeit, unbefristet.")
        keep, reason = classify_job(j)
        self.assertTrue(keep, f"rejected with: {reason}")
        self.assertIn("negated-experience", j.notes)

    def test_plain_experience_still_rejected(self):
        j = mk(desc="Wir erwarten mindestens 3 Jahre Berufserfahrung im IT-Support. Vollzeit.")
        keep, reason = classify_job(j)
        self.assertFalse(keep)
        self.assertEqual(reason, "experience(desc)")

    def test_english_negated_kept(self):
        j = mk(desc="3+ years of experience is not required, we train you. Full-time.")
        keep, reason = classify_job(j)
        self.assertTrue(keep, reason)
        self.assertIn("negated-experience", j.notes)

    def test_negation_outside_window_still_rejects(self):
        # 'nicht' >90 chars away must NOT rescue the match
        filler = " ".join(["Rahmenbedingungen"] * 20)   # ~160 chars of neutral text
        j = mk(desc="Mindestens 3 Jahre Berufserfahrung erforderlich. " + filler
                    + " Nicht relevant: dies ist ein langer Boilerplate-Satz. Vollzeit.")
        keep, reason = classify_job(j)
        self.assertFalse(keep)
        self.assertEqual(reason, "experience(desc)")


class TestF4AusbildungBoilerplate(unittest.TestCase):
    """\\bausbildung\\b on the full description = boilerplate bomb."""

    def test_boilerplate_mention_kept(self):
        j = mk(title="IT-Systemadministrator (m/w/d)",
               desc="Wir engagieren uns in Ausbildung und Weiterbildung. "
                    "Wir suchen einen IT-Systemadministrator für den 2nd Level. Vollzeit.")
        keep, reason = classify_job(j)
        self.assertTrue(keep, f"rejected with: {reason}")
        self.assertIn("mentions-ausbildung", j.notes)

    def test_role_shaped_desc_rejected(self):
        for d in ("Wir bieten eine Ausbildung zum Fachinformatiker Systemintegration.",
                  "Ausbildung als IT-Kaufmann ab September.",
                  "Wir suchen einen Auszubildenden für unsere IT.",
                  "Ausbildungsplatz IT-Systemelektroniker zu vergeben.",
                  "Duales Studium Wirtschaftsinformatik gesucht."):
            j = mk(desc=d)
            keep, reason = classify_job(j)
            self.assertFalse(keep, d)
            self.assertIn("ausbildung(desc)", reason)

    def test_title_hit_still_hard_reject(self):
        j = mk(title="Ausbildung Fachinformatiker Systemintegration 2026")
        keep, reason = classify_job(j)
        self.assertFalse(keep)
        self.assertEqual(reason, "ausbildung(title)")

    def test_student_roles_title_reject(self):
        for t in ("Werkstudent IT-Support", "Praktikant Systemadministration",
                  "Working Student IT"):
            j = mk(title=t)
            keep, reason = classify_job(j)
            self.assertFalse(keep, t)


class TestBaselines(unittest.TestCase):
    """Guard the behaviors that must NOT change while fixing F2-F4."""

    def test_clean_fulltime_kept(self):
        j = mk(desc="Zur Verstärkung suchen wir dich! Vollzeit, unbefristet, "
                    "39-Stunden-Woche. Abwechslungsreiche Tätigkeiten im User-Support.")
        keep, reason = classify_job(j)
        self.assertTrue(keep, reason)
        self.assertFalse(j.ft_unknown)

    def test_ft_unknown_flag(self):
        j = mk(title="IT-Admin", desc="Spannende Aufgaben in moderner Umgebung.")
        keep, reason = classify_job(j)
        self.assertTrue(keep)
        self.assertTrue(j.ft_unknown)

    def test_senior_title_rejected(self):
        keep, reason = classify_job(mk(title="Senior IT-Supporter (m/w/d)"))
        self.assertFalse(keep)
        self.assertEqual(reason, "experience(title)")

    def test_irrelevant_title_rejected(self):
        keep, reason = classify_job(mk(title="Pflegefachkraft (m/w/d)"))
        self.assertFalse(keep)
        self.assertEqual(reason, "relevance")

    def test_experience_regex_shape_unchanged(self):
        self.assertTrue(EXPERIENCE_BODY_RX.search("5 Jahre Berufserfahrung"))
        self.assertTrue(EXPERIENCE_BODY_RX.search("3+ years of experience"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
