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


if __name__ == "__main__":
    unittest.main()
