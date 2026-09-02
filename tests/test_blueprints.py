"""Unit tests for the automation blueprints.

The two blueprint files are the same automation in two languages. Only the
labels may differ; everything that decides what the automation *does* has to
stay identical, otherwise a fix lands in one language and not in the other.

These need PyYAML, which the other tests deliberately do not, so they skip
themselves on an interpreter without it:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the interpreter
    yaml = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parents[1]
_BLUEPRINT_DIR = _REPO / "blueprints" / "automation" / "austrian_air_quality"

ENGLISH = "threshold_notification.yaml"
GERMAN = "schwellenwert_benachrichtigung.yaml"

# Where the blueprints have to point for the My Home Assistant import link and
# the "re-import to update" button in Home Assistant to work.
SOURCE_BASE = (
    "https://github.com/karlrt/ha-austrian-air-quality/blob/main"
    "/blueprints/automation/austrian_air_quality/"
)


def _load(name: str) -> dict[str, Any]:
    """Parse one blueprint, with ``!input`` kept as a marker object."""

    class Loader(yaml.SafeLoader):  # type: ignore[misc, name-defined]
        """Loader that understands the Home Assistant blueprint tag."""

    Loader.add_constructor(
        "!input", lambda loader, node: ("input", loader.construct_scalar(node))
    )
    return yaml.load((_BLUEPRINT_DIR / name).read_text(encoding="utf-8"), Loader=Loader)


def _shape(actions: list[dict[str, Any]]) -> list[frozenset[str]]:
    """The keys of every action step, without the translated aliases."""
    return [frozenset(step) - {"alias"} for step in actions]


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class TestEveryBlueprint(unittest.TestCase):
    """What has to hold for each blueprint on its own."""

    def test_it_is_an_automation_blueprint(self) -> None:
        for name in (ENGLISH, GERMAN):
            with self.subTest(blueprint=name):
                metadata = _load(name)["blueprint"]
                self.assertEqual(metadata["domain"], "automation")
                self.assertTrue(metadata["name"])
                self.assertTrue(metadata["description"])

    def test_the_source_url_points_at_the_file_itself(self) -> None:
        # A wrong source_url makes Home Assistant offer to "update" the
        # blueprint from someone else's file.
        for name in (ENGLISH, GERMAN):
            with self.subTest(blueprint=name):
                self.assertEqual(_load(name)["blueprint"]["source_url"], SOURCE_BASE + name)

    def test_the_threshold_has_no_default(self) -> None:
        # The point of the whole task: no ready-made limit value, because none
        # of them has been verified against the legal text.
        for name in (ENGLISH, GERMAN):
            with self.subTest(blueprint=name):
                threshold = _load(name)["blueprint"]["input"]["threshold"]
                self.assertNotIn("default", threshold)

    def test_the_notification_and_the_cooldown_are_pre_filled(self) -> None:
        # Those two are what makes the blueprint usable without reading
        # anything first.
        for name in (ENGLISH, GERMAN):
            for field in ("notification", "cooldown"):
                with self.subTest(blueprint=name, field=field):
                    self.assertIn("default", _load(name)["blueprint"]["input"][field])

    def test_the_trigger_is_the_threshold_crossing(self) -> None:
        for name in (ENGLISH, GERMAN):
            with self.subTest(blueprint=name):
                triggers = _load(name)["triggers"]
                self.assertEqual(len(triggers), 1)
                self.assertEqual(triggers[0]["trigger"], "numeric_state")
                self.assertEqual(triggers[0]["entity_id"], ("input", "sensor"))
                self.assertEqual(triggers[0]["above"], ("input", "threshold"))

    def test_repeated_crossings_are_dropped_while_the_cooldown_runs(self) -> None:
        # The cooldown is the delay at the end of the sequence; it only keeps
        # anything quiet as long as a second run cannot start beside it.
        for name in (ENGLISH, GERMAN):
            with self.subTest(blueprint=name):
                blueprint = _load(name)
                self.assertEqual(blueprint["mode"], "single")
                self.assertEqual(blueprint["max_exceeded"], "silent")
                self.assertEqual(blueprint["actions"][-1]["delay"], ("input", "cooldown"))


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class TestBothLanguagesAgree(unittest.TestCase):
    """The two files have to stay the same automation."""

    def setUp(self) -> None:
        self.english = _load(ENGLISH)
        self.german = _load(GERMAN)

    def test_they_ask_for_the_same_inputs(self) -> None:
        self.assertEqual(
            sorted(self.english["blueprint"]["input"]),
            sorted(self.german["blueprint"]["input"]),
        )

    def test_the_inputs_are_collected_the_same_way(self) -> None:
        for key, english in self.english["blueprint"]["input"].items():
            with self.subTest(input=key):
                german = self.german["blueprint"]["input"][key]
                self.assertEqual(english["selector"], german["selector"])
                self.assertEqual("default" in english, "default" in german)

    def test_they_run_the_same_steps(self) -> None:
        self.assertEqual(self.english["triggers"], self.german["triggers"])
        self.assertEqual(self.english["mode"], self.german["mode"])
        self.assertEqual(self.english["max_exceeded"], self.german["max_exceeded"])
        self.assertEqual(_shape(self.english["actions"]), _shape(self.german["actions"]))

    def test_they_offer_the_same_variables_to_the_notification(self) -> None:
        self.assertEqual(
            sorted(self.english["variables"]), sorted(self.german["variables"])
        )


if __name__ == "__main__":
    unittest.main()
