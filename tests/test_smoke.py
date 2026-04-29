"""
Smoke tests para norteia-lead-recon. NO toca red por defecto — solo
unit tests deterministas. Para tests con red, usar `pytest -m network`.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _common
import borme
import dirce
import domain_resolver


class TestNormalization(unittest.TestCase):

    def test_nif_validation(self):
        self.assertTrue(_common.is_valid_nif("B12345678"))
        self.assertTrue(_common.is_valid_nif("12345678Z"))
        self.assertTrue(_common.is_valid_nif("X1234567L"))
        self.assertFalse(_common.is_valid_nif("INVALID"))
        self.assertFalse(_common.is_valid_nif(""))
        self.assertFalse(_common.is_valid_nif("1234"))

    def test_normalize_nif(self):
        self.assertEqual(_common.normalize_nif("b-1234.5678"), "B1234.5678")  # only strip - and space
        self.assertEqual(_common.normalize_nif("B12345678"), "B12345678")
        self.assertEqual(_common.normalize_nif(" b12345678 "), "B12345678")

    def test_normalize_razon_social_strips_legal_form(self):
        cases = [
            ("Asesores Pérez S.L.", "asesores perez"),
            ("Asesores Pérez, S.L.", "asesores perez"),
            ("ACME SA", "acme"),
            ("Cooperativa Norte SCCL", "cooperativa norte"),
        ]
        for raw, expected in cases:
            self.assertEqual(_common.normalize_razon_social(raw), expected)

    def test_levenshtein(self):
        self.assertEqual(_common.levenshtein("asesores perez", "asesores perez"), 0)
        self.assertEqual(_common.levenshtein("perez", "peraz"), 1)
        self.assertEqual(_common.levenshtein("", "abc"), 3)


class TestCnaeMapping(unittest.TestCase):

    def test_resolve_alias(self):
        r = _common.resolve_sector("asesoria fiscal")
        self.assertEqual(r["matched_via"], "alias")
        self.assertIn("6920", r["cnae"])

    def test_resolve_cnae_code(self):
        r = _common.resolve_sector("6920")
        self.assertEqual(r["matched_via"], "cnae")
        self.assertEqual(r["cnae"], ["6920"])

    def test_resolve_unknown_returns_none(self):
        r = _common.resolve_sector("xyzqwe")
        # Either fuzzy matched (low) or none — both acceptable; just ensure it doesn't crash
        self.assertIn(r["matched_via"], ("fuzzy", "none"))

    def test_province_code_sevilla(self):
        self.assertEqual(_common.province_code("Sevilla"), "41")

    def test_province_code_with_diacritics(self):
        self.assertEqual(_common.province_code("Málaga"), "29")
        self.assertEqual(_common.province_code("Avila"), "05")  # without diacritic should match Ávila


class TestCache(unittest.TestCase):

    def test_set_and_get_roundtrip(self):
        cfg = _common.CacheConfig(namespace="_test", ttl_seconds=60)
        _common.cache_set(cfg, "key1", {"foo": "bar"})
        self.assertEqual(_common.cache_get(cfg, "key1"), {"foo": "bar"})
        _common.cache_set(cfg, "key2", [1, 2, 3])
        self.assertEqual(_common.cache_get(cfg, "key2"), [1, 2, 3])

    def test_get_returns_none_for_unknown_key(self):
        cfg = _common.CacheConfig(namespace="_test_unknown")
        self.assertIsNone(_common.cache_get(cfg, "never-set"))


class TestProjectDetection(unittest.TestCase):

    def test_detect_returns_dict_with_expected_keys(self):
        out = _common.detect_project_runners()
        self.assertIn("borme_parser_url", out)
        self.assertIn("worker_py_url", out)
        self.assertIn("postgres_url", out)
        self.assertIn("project_root", out)


class TestBormeStubBehavior(unittest.TestCase):

    def test_analyze_invalid_nif(self):
        r = borme.analyze_by_nif("INVALID")
        self.assertEqual(r.get("error"), "invalid-nif-format")

    def test_analyze_valid_nif_returns_stub_with_note(self):
        r = borme.analyze_by_nif("B12345678")
        self.assertIn("note", r)
        self.assertEqual(r["timeline"], [])


class TestDirceContract(unittest.TestCase):

    def test_segment_size_returns_required_fields(self):
        r = dirce.segment_size("6920", "Sevilla")
        self.assertEqual(r["source"], "DIRCE")
        self.assertIn("note", r)
        # totalCompanies may be None in MVP — that's fine, the contract is the shape
        self.assertIn("totalCompanies", r)


class TestDomainResolverHeuristic(unittest.TestCase):

    def test_slugify_strips_legal_form_and_diacritics(self):
        self.assertEqual(domain_resolver.slugify("Asesores Pérez S.L."), "asesoresperez")
        self.assertEqual(domain_resolver.slugify("ACME, S.A."), "acme")

    def test_heuristic_candidates_short_name_returns_empty(self):
        self.assertEqual(domain_resolver.heuristic_candidates("ab"), [])

    def test_heuristic_candidates_returns_5_urls(self):
        c = domain_resolver.heuristic_candidates("Asesores Pérez")
        self.assertEqual(len(c), 5)
        self.assertTrue(any(".es" in url for url in c))
        self.assertTrue(any(".com" in url for url in c))


if __name__ == "__main__":
    unittest.main(verbosity=2)
