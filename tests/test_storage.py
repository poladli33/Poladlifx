import json
import os
import tempfile
import unittest

from financialjuice_bot.storage import StateStore


class StorageTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            s = StateStore(path)
            s.mark_sent("news:x")
            s.mark_actual_sent("42")
            s.save()
            s2 = StateStore(path)
            self.assertTrue(s2.sent("news:x"))
            self.assertTrue(s2.actual_sent("42"))
            with open(path, encoding="utf-8") as fh:
                json.load(fh)


if __name__ == "__main__":
    unittest.main()
