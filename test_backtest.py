# -*- coding: utf-8 -*-
import unittest

import numpy as np
import pandas as pd

import gold_backtest as bt


ZERO_COSTS = {
    "spread_points": 0.0,
    "slippage_points_per_side": 0.0,
    "commission_usd_per_contract_side": 0.0,
    "contract_oz": 100.0,
}


def bars():
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    return pd.DataFrame({
        "Open": [100, 101, 102, 103, 104, 105],
        "High": [100.5, 102, 104, 105, 106, 107],
        "Low": [99.5, 100, 101, 102, 103, 104],
        "Close": [100, 101.5, 102.5, 104, 105, 106],
    }, index=idx)


class BacktestExecutionTests(unittest.TestCase):
    def test_entry_is_next_bar_open_not_signal_close(self):
        trade = bt.simulate(bars(), 0, 1, atr=1, max_bars=3, costs=ZERO_COSTS)
        self.assertIsNotNone(trade)
        self.assertEqual(trade["entry_i"], 1)
        self.assertEqual(trade["entry"], 101.0)

    def test_stop_wins_when_stop_and_target_touch_same_bar(self):
        df = bars()
        df.loc[df.index[1], "High"] = 104.0
        df.loc[df.index[1], "Low"] = 98.0
        trade = bt.simulate(df, 0, 1, atr=1, max_bars=2, costs=ZERO_COSTS)
        self.assertEqual(trade["exit_reason"], "stop")
        self.assertEqual(trade["exit_i"], 1)

    def test_trade_cannot_cross_holdout_boundary(self):
        df = bars()
        signals = pd.DataFrame([{"i": 2, "side_raw": 1, "side_adj": 1, "atr": 1.0}])
        res = bt.apply_cost_model(df, signals, costs=ZERO_COSTS, start_i=0, end_i=3)
        self.assertTrue(np.isnan(res["r_adj"].iloc[0]))

    def test_non_overlapping_positions(self):
        df = bars()
        signals = pd.DataFrame([
            {"i": 0, "side_raw": 1, "side_adj": 1, "atr": 1.0},
            {"i": 1, "side_raw": 1, "side_adj": 1, "atr": 1.0},
        ])
        res = bt.apply_cost_model(df, signals, costs=ZERO_COSTS, horizon=3, max_hold=3)
        self.assertEqual(int(res["r_adj"].notna().sum()), 1)


if __name__ == "__main__":
    unittest.main()
