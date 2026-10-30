#!/usr/bin/env python3
"""Offline unit tests for build_companies_map.py (parse, dedupe, adapter,
employer matching, bbox). Run: python3 tests/test_companies_map.py"""
import os, sys, unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_companies_map as bcm


class TestCorridorBbox(unittest.TestCase):
    def test_bbox_covers_bamberg_nuernberg(self):
        s, w, n, e = bcm.corridor_bbox()
        # Bamberg Hbf 49.9006/10.8997 and Nürnberg Hbf 49.4520/11.0776 inside
        self.assertTrue(s < 49.4520 < n and w < 11.0776 < e)
        self.assertTrue(s < 49.9006 < n and w < 10.8997 < e)
        # wide-gazetteer outliers stay OUT (Marktredwitz lon 12.16, Pegnitz 11.55)
        self.assertLess(e, 11.5)
        self.assertGreater(w, 10.4)

    def test_bbox_is_sane(self):
        s, w, n, e = bcm.corridor_bbox()
        self.assertLess(s, n); self.assertLess(w, e)


class TestParseCompanies(unittest.TestCase):
    def test_parses_named_node(self):
        els = [{"type": "N", "id": 1, "lat": 49.5, "lon": 11.0,
                "tags": {"name": "Siemens AG", "office": "company",
                         "addr:street": "Werner-von-Siemens-Str.",
                         "addr:housenumber": "1", "addr:city": "Erlangen"}}]
        cs, dropped = bcm.parse_companies(els)
        self.assertEqual(len(cs), 1); self.assertEqual(dropped, 0)
        c = cs[0]
        self.assertEqual(c["n"], "Siemens AG")
        self.assertEqual(c["k"], "office")
        self.assertIn("Werner-von-Siemens-Str. 1", c["a"])

    def test_drops_nameless(self):
        els = [{"type": "N", "id": 2, "lat": 49.5, "lon": 11.0,
                "tags": {"office": "company"}}]
        cs, dropped = bcm.parse_companies(els)
        self.assertEqual(len(cs), 0); self.assertEqual(dropped, 1)

    def test_categories(self):
        def el(i, tags):
            return {"type": "N", "id": i, "lat": 49.5 + i * 0.01, "lon": 11.0, "tags": tags}
        els = [el(1, {"name": "A", "office": "company"}),
               el(2, {"name": "B", "shop": "supermarket"}),
               el(3, {"name": "C", "craft": "car_repair"}),
               el(4, {"name": "D", "landuse": "industrial"}),
               el(5, {"name": "E", "man_made": "works"}),
               el(6, {"name": "F", "building": "commercial"})]
        cs, _ = bcm.parse_companies(els)
        got = {c["n"]: c["k"] for c in cs}
        self.assertEqual(got, {"A": "office", "B": "retail", "C": "craft",
                               "D": "industry", "E": "industry", "F": "industry"})

    def test_dedupe_same_name_nearby(self):
        els = [{"type": "N", "id": 1, "lat": 49.5000, "lon": 11.0000,
                "tags": {"name": "Alpha GmbH", "office": "company"}},
               {"type": "W", "id": 2, "lat": 49.5004, "lon": 11.0004,
                "tags": {"name": "Alpha GmbH", "office": "company"}}]
        cs, dropped = bcm.parse_companies(els)
        self.assertEqual(len(cs), 1); self.assertEqual(dropped, 1)

    def test_keeps_same_name_far_apart(self):
        els = [{"type": "N", "id": 1, "lat": 49.50, "lon": 11.00,
                "tags": {"name": "Schnell Imbiss", "shop": "fast_food"}},
               {"type": "N", "id": 2, "lat": 49.60, "lon": 11.10,
                "tags": {"name": "Schnell Imbiss", "shop": "fast_food"}}]
        cs, _ = bcm.parse_companies(els)
        self.assertEqual(len(cs), 2)


class TestFeatureAdapter(unittest.TestCase):
    def test_photon_feature_maps_to_element(self):
        f = {"type": "Feature",
             "geometry": {"coordinates": [11.007, 49.588]},
             "properties": {"osm_type": "N", "osm_id": 42, "osm_key": "office",
                            "osm_value": "company", "name": "adesso SE",
                            "street": "Dr.-Gustav-Heinemann-Str.", "housenumber": "59",
                            "city": "Nürnberg", "postcode": "90482"}}
        els = bcm.features_to_elements([f])
        self.assertEqual(len(els), 1)
        e = els[0]
        self.assertEqual(e["lat"], 49.588); self.assertEqual(e["lon"], 11.007)
        self.assertEqual(e["tags"]["office"], "company")
        self.assertEqual(e["tags"]["addr:street"], "Dr.-Gustav-Heinemann-Str.")

    def test_dedupe_by_osm_id(self):
        f1 = {"geometry": {"coordinates": [11.0, 49.5]},
              "properties": {"osm_type": "N", "osm_id": 7, "name": "Alpha",
                             "osm_key": "office"}}
        f2 = dict(f1)                                   # same object twice (a+t sweep)
        els = bcm.features_to_elements([f1, f2])
        self.assertEqual(len(els), 1)

    def test_skips_nameless(self):
        f = {"geometry": {"coordinates": [11.0, 49.5]},
             "properties": {"osm_type": "N", "osm_id": 9, "osm_key": "shop"}}
        self.assertEqual(bcm.features_to_elements([f]), [])


class TestMatchEmployers(unittest.TestCase):
    def test_substring_both_directions(self):
        emps = {"siemens": (5, "Firmware Engineer"), "adessose": (2, "Consultant")}
        cs = [{"n": "Siemens AG", "k": "office", "lat": 49.5, "lon": 11.0},
              {"n": "adesso", "k": "office", "lat": 49.5, "lon": 11.0},
              {"n": "Bratwurstrothlein", "k": "craft", "lat": 49.5, "lon": 11.0}]
        flagged = bcm.match_employers(cs, emps)
        self.assertEqual(flagged, 2)
        by_name = {c["n"]: c for c in cs}
        self.assertEqual(by_name["Siemens AG"]["j"], [5, "Firmware Engineer"])
        self.assertNotIn("j", by_name["Bratwurstrothlein"])

    def test_short_names_do_not_match(self):
        emps = {"ping": (1, "Dev")}
        cs = [{"n": "Pingpong Lieferservice", "k": "shop", "lat": 49.5, "lon": 11.0}]
        # 'ping' (4 chars) is below the min length 5 -> no match
        self.assertEqual(bcm.match_employers(cs, emps), 0)


class TestStmtChunks(unittest.TestCase):
    def test_chunks_respect_gateway_cap(self):
        for ch in bcm._stmt_chunks():
            qlen = (24 + sum(len(s) + 34 for s in ch) + len(ch) - 1 + 3 + 16)
            self.assertLessEqual(qlen, 300, f"chunk too long: {qlen}")
        total = sum(len(ch) for ch in bcm._stmt_chunks())
        self.assertEqual(total, len(bcm.CATEGORIES))


class TestQueryBuild(unittest.TestCase):
    def test_bbox_lands_on_every_statement(self):
        q = bcm.build_query((1.0, 2.0, 3.0, 4.0))
        self.assertEqual(q.count("(1.0000,2.0000,3.0000,4.0000)"), len(bcm.CATEGORIES))
        self.assertNotIn(",", q.split("(1.0000,2.0000,3.0000,4.0000)")[1][:2] if False else q[24:26])


if __name__ == "__main__":
    unittest.main(verbosity=2)
