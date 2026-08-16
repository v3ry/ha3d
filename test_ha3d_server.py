#!/usr/bin/env python3
"""Tests unitaires ha3d_server — logique pure (pas de réseau).

Lancement : python3 -m unittest test_ha3d_server -v
"""
import unittest
from unittest.mock import patch

import ha3d_server as h


class TestParseHaUrl(unittest.TestCase):
    def test_http_simple(self):
        self.assertEqual(h.parse_ha_url("http://192.168.0.139:8123"), ("192.168.0.139", 8123))

    def test_https_avec_chemin(self):
        self.assertEqual(h.parse_ha_url("https://ha.example.com:8443/"), ("ha.example.com", 8443))

    def test_sans_port(self):
        self.assertEqual(h.parse_ha_url("http://ha.local"), ("ha.local", 8123))

    def test_ipv6(self):
        self.assertEqual(h.parse_ha_url("http://[::1]:8123"), ("::1", 8123))


class TestTrackedIds(unittest.TestCase):
    def test_sensors_sum_with_doors(self):
        layout = {
            "sensors": [
                {"entity": "sensor.a"},
                {"entity": "sensor.b", "sum_with": "sensor.b2"},
            ],
            "doors": [
                {"entity": "binary_sensor.porte"},
                {"id": "sans_entite"},  # porte sans entité → ignorée
            ],
        }
        with patch.object(h, "LAYOUT", layout):
            self.assertEqual(
                h._tracked_ids(),
                {"sensor.a", "sensor.b", "sensor.b2", "binary_sensor.porte"},
            )

    def test_door_ids(self):
        layout = {
            "sensors": [],
            "doors": [
                {"entity": "binary_sensor.porte1"},
                {"id": "brute", "noPanel": True, "entity": "binary_sensor.porte2"},
            ],
        }
        with patch.object(h, "LAYOUT", layout):
            self.assertEqual(h._door_ids(), {"binary_sensor.porte1", "binary_sensor.porte2"})


class TestStatusEntry(unittest.TestCase):
    def test_sum_with_abs(self):
        s = {"entity": "sensor.prod", "sum_with": "sensor.onduleur", "label": "Prod"}
        by_id = {
            "sensor.prod": {"state": "-1200", "unit": "W", "attrs": {}},
            "sensor.onduleur": {"state": "500", "unit": "W", "attrs": {}},
        }
        out = h._status_entry(s, by_id)
        self.assertEqual(float(out["state"]), 1700.0)  # |-1200| + |500|
        self.assertTrue(out["attrs"]["is_sum"])

    def test_sum_with_tous_indisponibles(self):
        s = {"entity": "sensor.a", "sum_with": "sensor.b"}
        out = h._status_entry(s, {})
        self.assertEqual(out["state"], "unavailable")

    def test_entite_normale(self):
        by_id = {"sensor.x": {"state": "22.5", "unit": "°C", "attrs": {"friendly_name": "X"}}}
        out = h._status_entry({"entity": "sensor.x"}, by_id)
        self.assertEqual(out["state"], "22.5")
        self.assertEqual(out["unit"], "°C")

    def test_entite_absente(self):
        out = h._status_entry({"entity": "sensor.inconnu"}, {})
        self.assertEqual(out["state"], "unavailable")


class TestValidateLayout(unittest.TestCase):
    def _valid(self):
        return {
            "house_name": "Test",
            "levels": [{"name": "rdc", "y_floor": 0, "height": 2.6, "rooms": [
                {"id": "salon", "name": "Salon", "x": 0, "z": 0, "w": 5, "d": 4, "color": "#fff"},
            ]}],
            "sensors": [{"entity": "sensor.a", "room": "salon"}],
            "doors": [{"id": "p1", "t": 2, "width": 0.9, "room": "salon", "rotY": 0, "fixed": 0}],
            "furniture": [],
        }

    def test_layout_valide(self):
        self.assertEqual(h.validate_layout(self._valid()), (True, ""))

    def test_layout_reel_valide(self):
        # Le layout chargé par le serveur doit passer la validation
        ok, err = h.validate_layout(h.LAYOUT)
        self.assertTrue(ok, f"layout.json invalide : {err}")

    def test_piece_sans_id(self):
        l = self._valid()
        l["levels"][0]["rooms"][0].pop("id")
        self.assertFalse(h.validate_layout(l)[0])

    def test_id_duplique(self):
        l = self._valid()
        l["levels"][0]["rooms"].append(dict(l["levels"][0]["rooms"][0]))
        self.assertFalse(h.validate_layout(l)[0])

    def test_polygone_trop_petit(self):
        l = self._valid()
        l["levels"][0]["rooms"][0]["pts"] = [[0, 0], [1, 0]]  # 2 sommets
        self.assertFalse(h.validate_layout(l)[0])

    def test_nan_rejete(self):
        l = self._valid()
        l["levels"][0]["rooms"][0]["w"] = float("nan")
        self.assertFalse(h.validate_layout(l)[0])

    def test_dimensions_trop_petites(self):
        l = self._valid()
        l["levels"][0]["rooms"][0]["w"] = 0.2
        self.assertFalse(h.validate_layout(l)[0])

    def test_porte_invalide(self):
        l = self._valid()
        l["doors"][0]["width"] = 0
        self.assertFalse(h.validate_layout(l)[0])

    def test_capteur_duplique(self):
        l = self._valid()
        l["sensors"].append({"entity": "sensor.a", "room": "salon"})
        self.assertFalse(h.validate_layout(l)[0])

    def test_objet_sans_id(self):
        l = self._valid()
        l["levels"][0]["furniture"] = [{"type": "box", "name": "x"}]
        self.assertFalse(h.validate_layout(l)[0])


if __name__ == "__main__":
    unittest.main()
