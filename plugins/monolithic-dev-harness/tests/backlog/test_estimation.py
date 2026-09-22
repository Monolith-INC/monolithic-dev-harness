import json
import tempfile
import unittest
from pathlib import Path

from orchestrator_core.estimation import (
    CompletedItem,
    EstimationConfig,
    calibrate,
    compare_to_halstead,
    distribute_hours,
    estimate_hours,
    estimate_work_item,
    get_scale,
    halstead_hours,
    load_config,
    parse_config,
)
from orchestrator_core.estimation.calibration import STROUD_NUMBER
from orchestrator_core.estimation.config import SEED_BANDS, CalibrationSettings
from orchestrator_core.estimation.mapping import (
    PROVENANCE_CALIBRATED,
    PROVENANCE_CONFIG,
    PROVENANCE_SEED,
)
from orchestrator_core.estimation.scales import (
    DRIVER_MAX,
    DRIVERS,
    FIBONACCI,
    PointScale,
    dominant_drivers,
    story_points_from_drivers,
)


class TestPointScale(unittest.TestCase):
    """Tests for the PointScale value object."""

    def test_known_scales_resolve_by_name(self):
        """Named scales should resolve; unknown names fall back to the default."""
        self.assertEqual(get_scale("fibonacci"), FIBONACCI)
        self.assertEqual(get_scale("driver-max"), DRIVER_MAX)
        self.assertEqual(get_scale("nonsense"), FIBONACCI)
        self.assertEqual(get_scale(None), FIBONACCI)

    def test_normalize_snaps_to_nearest_allowed_value(self):
        """Off-scale values snap to the nearest point on the scale."""
        self.assertEqual(FIBONACCI.normalize(4.0), 5.0)
        self.assertEqual(FIBONACCI.normalize(2.2), 2.0)
        self.assertEqual(FIBONACCI.normalize(100.0), 21.0)

    def test_normalize_ties_round_up(self):
        """A value exactly between two sizes resolves to the larger one."""
        self.assertEqual(FIBONACCI.normalize(2.5), 3.0)

    def test_split_count(self):
        """Stories over the ceiling split into enough pieces to get under it."""
        self.assertEqual(FIBONACCI.split_count(3.0), 1)
        self.assertEqual(FIBONACCI.split_count(5.0), 1)
        self.assertEqual(FIBONACCI.split_count(8.0), 2)
        self.assertEqual(FIBONACCI.split_count(13.0), 3)

    def test_split_count_handles_fractional_values(self):
        """Fractional points and ceilings are not truncated before ceiling division."""
        fractional = PointScale("fractional", FIBONACCI.values, 2.5)
        self.assertEqual(fractional.split_count(5.5), 3)


class TestDriverMax(unittest.TestCase):
    """Tests for the 6-driver MAX heuristic."""

    def test_driver_scale_includes_eight(self):
        """Drivers score 1/2/3/5/8 after the scale reconciliation."""
        self.assertEqual(DRIVER_MAX.values, (1.0, 2.0, 3.0, 5.0, 8.0))

    def test_points_are_the_max_not_the_sum(self):
        """One hard dimension must not be diluted by easy ones."""
        scores = {"escopo": 1, "incerteza": 1, "integracoes": 1, "dados": 1, "qa": 5, "rollout": 1}
        self.assertEqual(story_points_from_drivers(scores), 5.0)

    def test_two_fives_stay_five(self):
        """The removed non-MAX exception must not creep back in."""
        scores = {"escopo": 5, "qa": 5, "dados": 2}
        self.assertEqual(story_points_from_drivers(scores), 5.0)

    def test_accepts_a_bare_list(self):
        """Scores may arrive without driver names."""
        self.assertEqual(story_points_from_drivers([1, 3, 2]), 3.0)

    def test_empty_scores_yield_none(self):
        """Nothing scored means no points, not zero points."""
        self.assertIsNone(story_points_from_drivers({}))
        self.assertIsNone(story_points_from_drivers([0, 0]))

    def test_dominant_drivers_named(self):
        """The Complexity note must be able to say which driver set the MAX."""
        scores = {"escopo": 3, "qa": 5, "rollout": 5}
        self.assertEqual(sorted(dominant_drivers(scores)), ["qa", "rollout"])

    def test_six_canonical_drivers(self):
        """The heuristic is six drivers, matching decomposition-rules.md."""
        self.assertEqual(len(DRIVERS), 6)


class TestEstimationConfig(unittest.TestCase):
    """Tests for config parsing and its degradation behaviour."""

    def test_default_config_is_marked_seed_default(self):
        """An unconfigured team gets seed bands, labelled as such."""
        config = EstimationConfig()
        self.assertEqual(config.source, "seed-default")
        self.assertEqual(config.bands, SEED_BANDS)

    def test_parse_config_reads_custom_bands(self):
        """Team-supplied bands replace the seed and change provenance."""
        config = parse_config({"bands": {"1": {"low": 2, "high": 3}}}, source="team.json")
        self.assertEqual(config.band_for(1.0), (2.0, 3.0))
        self.assertEqual(config.source, "team.json")

    def test_parse_config_accepts_list_bands(self):
        """A [low, high] pair is accepted as well as an object."""
        config = parse_config({"bands": {"3": [4, 9]}})
        self.assertEqual(config.band_for(3.0), (4.0, 9.0))

    def test_parse_config_swaps_inverted_band(self):
        """A band given high-first is normalised rather than rejected."""
        config = parse_config({"bands": {"3": {"low": 9, "high": 4}}})
        self.assertEqual(config.band_for(3.0), (4.0, 9.0))

    def test_malformed_bands_fall_back_to_seed(self):
        """Garbage in the bands key degrades to seed defaults instead of raising."""
        config = parse_config({"bands": "not-a-mapping"})
        self.assertEqual(config.bands, SEED_BANDS)
        self.assertEqual(config.source, "seed-default")

    def test_partially_malformed_bands_reject_the_whole_custom_table(self):
        """A partial custom table must not be presented as the team's configuration."""
        config = parse_config({"bands": {"3": [4, 6], "five": "invalid"}})
        self.assertEqual(config.bands, SEED_BANDS)
        self.assertEqual(config.source, "seed-default")
        self.assertEqual(config.rejected_bands, ("five",))

    def test_ceiling_override_applies_to_scale(self):
        """A configured ceiling overrides the scale's own."""
        config = parse_config({"scale": "fibonacci", "ceiling": 8})
        self.assertEqual(config.scale.ceiling, 8.0)

    def test_load_config_missing_file_returns_defaults(self):
        """An absent config file is not an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(Path(tmpdir))
            self.assertEqual(config.source, "seed-default")

    def test_load_config_malformed_json_returns_defaults(self):
        """Broken JSON degrades silently, matching the never-raise idiom."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "estimation.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(load_config(Path(tmpdir)).source, "seed-default")

    def test_load_config_reads_real_file(self):
        """A valid config file is read and its path recorded as provenance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "estimation.json").write_text(
                json.dumps({"bands": {"2": {"low": 5, "high": 7}}}), encoding="utf-8"
            )
            config = load_config(Path(tmpdir))
            self.assertEqual(config.band_for(2.0), (5.0, 7.0))
            self.assertIn("estimation.json", config.source)


class TestEstimateHours(unittest.TestCase):
    """Tests for the points-to-hours mapping."""

    def test_no_points_yields_no_estimate(self):
        """Absent or zero points produce None, never a fabricated number."""
        config = EstimationConfig()
        self.assertIsNone(estimate_hours(None, config=config))
        self.assertIsNone(estimate_hours(0, config=config))
        self.assertIsNone(estimate_hours(-3, config=config))

    def test_seed_estimate_is_flagged_as_suggestion_only(self):
        """An uncalibrated estimate must announce that nothing stands behind it."""
        estimate = estimate_hours(3.0, config=EstimationConfig())
        self.assertEqual(estimate.provenance, PROVENANCE_SEED)
        self.assertTrue(estimate.is_suggestion_only)
        self.assertIn("NOT calibrated", estimate.describe())

    def test_band_midpoint_is_used_for_hours(self):
        """The suggested figure is the midpoint of the band."""
        estimate = estimate_hours(3.0, config=EstimationConfig())
        self.assertEqual((estimate.low, estimate.high), (4.0, 6.0))
        self.assertEqual(estimate.hours, 5.0)

    def test_configured_bands_change_provenance(self):
        """Team config is a stronger claim than a seed default."""
        config = parse_config({"bands": {"3": {"low": 4, "high": 6}}}, source="team.json")
        estimate = estimate_hours(3.0, config=config)
        self.assertEqual(estimate.provenance, PROVENANCE_CONFIG)
        self.assertTrue(estimate.is_suggestion_only)  # still no sample behind it

    def test_off_scale_points_interpolate_from_nearest_band(self):
        """A point value with no band scales from its nearest neighbour."""
        estimate = estimate_hours(4.0, config=EstimationConfig())
        self.assertIsNotNone(estimate)
        self.assertGreater(estimate.hours, 5.0)
        self.assertLess(estimate.hours, 16.0)

    def test_calibration_overrides_bands(self):
        """A usable calibration wins over any band table."""
        history = [CompletedItem(points=2.0, actual_hours=6.0) for _ in range(10)]
        calibration = calibrate(history)
        estimate = estimate_hours(2.0, config=EstimationConfig(), calibration=calibration)
        self.assertEqual(estimate.provenance, PROVENANCE_CALIBRATED)
        self.assertEqual(estimate.hours, 6.0)
        self.assertFalse(estimate.is_suggestion_only)

    def test_estimate_work_item_facade(self):
        """The facade wires history through to calibration."""
        history = [CompletedItem(points=1.0, actual_hours=4.0) for _ in range(10)]
        estimate = estimate_work_item(3.0, history=history)
        self.assertEqual(estimate.provenance, PROVENANCE_CALIBRATED)
        self.assertEqual(estimate.hours, 12.0)


class TestCalibration(unittest.TestCase):
    """Tests for deriving hours-per-point from completed work."""

    def test_empty_history_is_not_usable(self):
        """No history means no calibrated figure."""
        calibration = calibrate([])
        self.assertFalse(calibration.usable)
        self.assertEqual(calibration.confidence, "none")

    def test_items_missing_hours_are_ignored(self):
        """An item with points but no recorded time contributes nothing."""
        calibration = calibrate([CompletedItem(points=3.0, actual_hours=0.0)])
        self.assertFalse(calibration.usable)

    def test_small_sample_is_low_confidence(self):
        """Below min_sample the figure is returned but flagged."""
        calibration = calibrate([CompletedItem(points=1.0, actual_hours=2.0)])
        self.assertTrue(calibration.usable)
        self.assertEqual(calibration.confidence, "low")

    def test_large_sample_is_high_confidence(self):
        """At or above min_sample the figure is trusted."""
        history = [CompletedItem(points=2.0, actual_hours=4.0) for _ in range(8)]
        calibration = calibrate(history)
        self.assertEqual(calibration.confidence, "high")
        self.assertEqual(calibration.hours_per_point, 2.0)

    def test_ratio_of_sums_not_mean_of_ratios(self):
        """Large items must carry proportionally more weight than small ones."""
        history = [
            CompletedItem(points=1.0, actual_hours=10.0),  # 10 h/pt
            CompletedItem(points=9.0, actual_hours=9.0),  # 1 h/pt
        ]
        calibration = calibrate(history, settings=CalibrationSettings(min_sample=1))
        # mean of ratios would be 5.5; ratio of sums is 19/10
        self.assertAlmostEqual(calibration.hours_per_point, 1.9)

    def test_disabled_calibration_returns_nothing(self):
        """Turning calibration off in config suppresses the figure."""
        history = [CompletedItem(points=2.0, actual_hours=4.0) for _ in range(20)]
        calibration = calibrate(history, settings=CalibrationSettings(enabled=False))
        self.assertFalse(calibration.usable)

    def test_window_keeps_only_recent_iterations(self):
        """Older iterations fall out of the rolling window."""
        history = [CompletedItem(points=1.0, actual_hours=100.0, iteration="s1")]
        history += [CompletedItem(points=1.0, actual_hours=2.0, iteration=f"s{n}") for n in range(2, 6)]
        calibration = calibrate(
            history, settings=CalibrationSettings(min_sample=1, window_iterations=2)
        )
        self.assertEqual(calibration.hours_per_point, 2.0)

    def test_items_without_iteration_survive_windowing(self):
        """Absent grouping data must not silently shrink the sample."""
        history = [CompletedItem(points=1.0, actual_hours=3.0) for _ in range(4)]
        calibration = calibrate(
            history, settings=CalibrationSettings(min_sample=1, window_iterations=1)
        )
        self.assertEqual(calibration.sample_size, 4)


class TestHalstead(unittest.TestCase):
    """Tests for the Halstead cross-check."""

    def test_halstead_hours_uses_stroud_number(self):
        """T = E / S seconds, converted to hours."""
        effort = STROUD_NUMBER * 3600.0
        self.assertEqual(halstead_hours(effort), 1.0)

    def test_non_positive_effort_yields_none(self):
        """Zero effort is not zero hours; it is no answer."""
        self.assertIsNone(halstead_hours(0))
        self.assertIsNone(halstead_hours(-5))

    def test_aligned_within_tolerance(self):
        """Estimates within a factor of two count as aligned."""
        divergence = compare_to_halstead(1.5, effort=STROUD_NUMBER * 3600.0)
        self.assertEqual(divergence.verdict, "aligned")

    def test_over_and_under_estimated(self):
        """Divergence beyond the tolerance band is named in both directions."""
        effort = STROUD_NUMBER * 3600.0  # derives 1.0h
        self.assertEqual(compare_to_halstead(10.0, effort=effort).verdict, "over-estimated")
        self.assertEqual(compare_to_halstead(0.1, effort=effort).verdict, "under-estimated")

    def test_comparison_returns_none_without_inputs(self):
        """No effort or no estimate means no comparison."""
        self.assertIsNone(compare_to_halstead(5.0, effort=0))
        self.assertIsNone(compare_to_halstead(0, effort=1000.0))


class TestDistributeHours(unittest.TestCase):
    """Tests for splitting a story's hours across its tasks."""

    def test_parts_sum_to_the_whole(self):
        """Rounding must never lose or invent time."""
        parts = distribute_hours(10.0, [1, 1, 1])
        self.assertEqual(len(parts), 3)
        self.assertEqual(round(sum(parts), 2), 10.0)

    def test_weights_are_respected(self):
        """A task weighted double gets double the hours."""
        self.assertEqual(distribute_hours(9.0, [1, 2]), [3.0, 6.0])

    def test_all_zero_weights_yield_zeros_not_an_equal_split(self):
        """Zero is a decision, not missing information.

        Falling back to an equal split here handed a Story's whole duration to whatever
        tasks had been deliberately weighted out -- e.g. a lone Breakdown marker.
        """
        self.assertEqual(distribute_hours(8.0, [0, 0]), [0.0, 0.0])

    def test_absent_weights_fall_back_to_an_equal_split(self):
        """None means 'no information', which is what an equal share is for."""
        self.assertEqual(distribute_hours(8.0, [None, None]), [4.0, 4.0])

    def test_empty_inputs_return_empty(self):
        """No tasks yields nothing; no hours yields a zero per task, not a short list.

        A shorter list than the tasks it describes gets silently zipped away by callers.
        """
        self.assertEqual(distribute_hours(10.0, []), [])
        self.assertEqual(distribute_hours(0, [1, 2]), [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
