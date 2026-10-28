"""Testy podpowiedzi GUI bez serwera graficznego."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui_tooltips import BUTTON_HELP, FIELD_HELP, Tooltip


class WidgetStub:
    def __init__(self):
        self.bindings = {}
        self.pending = {}
        self.cancelled = []
        self.counter = 0

    def bind(self, name, callback, add=None):
        self.bindings[name] = callback
        assert add == "+"

    def after(self, delay, callback):
        self.counter += 1
        key = f"after-{self.counter}"
        self.pending[key] = (delay, callback)
        return key

    def after_cancel(self, key):
        self.cancelled.append(key)
        self.pending.pop(key, None)


class TooltipTests(unittest.TestCase):
    def test_every_gui_action_is_described(self):
        self.assertEqual(
            set(BUTTON_HELP),
            {"original", "compressed", "reference", "output", "compress", "start", "stop"},
        )
        self.assertTrue(all(len(text) > 45 for text in BUTTON_HELP.values()))
        self.assertTrue(all(len(text) > 45 for text in FIELD_HELP.values()))
        self.assertTrue({"compression", "searchable", "segments", "pages"} <= FIELD_HELP.keys())

    def test_delay_cancel_and_no_duplicate_schedules(self):
        widget = WidgetStub()
        helptext = Tooltip(widget, BUTTON_HELP["start"], delay_ms=450)
        self.assertEqual(len(widget.bindings), 6)
        widget.bindings["<Enter>"]()
        self.assertEqual(len(widget.pending), 1)
        first_id, (delay, _) = next(iter(widget.pending.items()))
        self.assertEqual(delay, 450)
        widget.bindings["<Enter>"]()
        self.assertIn(first_id, widget.cancelled)
        self.assertEqual(len(widget.pending), 1)
        widget.bindings["<Leave>"]()
        self.assertEqual(widget.pending, {})
        self.assertIsNone(helptext._job)

    def test_accessibility_focus_and_button_press(self):
        widget = WidgetStub()
        Tooltip(widget, BUTTON_HELP["compress"])
        widget.bindings["<FocusIn>"]()
        self.assertEqual(len(widget.pending), 1)
        widget.bindings["<ButtonPress>"]()
        self.assertEqual(widget.pending, {})
        widget.bindings["<FocusIn>"]()
        widget.bindings["<FocusOut>"]()
        self.assertEqual(widget.pending, {})


if __name__ == "__main__":
    unittest.main()
