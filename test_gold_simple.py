# -*- coding: utf-8 -*-
import unittest

import gold_simple


class SimpleAgentConflictTests(unittest.TestCase):
    def test_opposing_timeframes_block_entry_even_with_two_votes(self):
        reps = [
            {"tf": "1h", "score": 45, "sup": 2300, "res": 2400, "atr": 20},
            {"tf": "1d", "score": 35, "sup": 2300, "res": 2400, "atr": 25},
            {"tf": "1wk", "score": -25, "sup": 2250, "res": 2450, "atr": 60},
        ]
        pro = {"adj": 32, "plan": {}, "regime": {"kind": "trend", "er": 0.35}}
        result = gold_simple.build(reps, pro, 0, {"bias": 0}, None, [])
        self.assertEqual(result["key"], "wait")
        self.assertTrue(any("تعارض تایم‌فریم‌ها" in x for x in result["conflicts"]))
        self.assertTrue(any("رأی اکثریت" in x[1] for x in result["why"]))
        self.assertEqual(len(result["tf_scores"]), 3)


if __name__ == "__main__":
    unittest.main()
