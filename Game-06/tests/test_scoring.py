"""
Tests for the precision-judgement math in src/scoring.py.
"""
import settings
from src import scoring


def test_classify_judgement_perfect_at_zero_distance():
    assert scoring.classify_judgement(0.0) == scoring.PERFECT


def test_classify_judgement_boundaries():
    assert scoring.classify_judgement(settings.PERFECT_WINDOW_SECONDS) == scoring.PERFECT
    assert scoring.classify_judgement(settings.PERFECT_WINDOW_SECONDS + 0.001) == scoring.GOOD
    assert scoring.classify_judgement(settings.GOOD_WINDOW_SECONDS) == scoring.GOOD
    assert scoring.classify_judgement(settings.OK_WINDOW_SECONDS) == scoring.OK


def test_classify_judgement_outside_every_window_is_none():
    assert scoring.classify_judgement(settings.OK_WINDOW_SECONDS + 0.001) is None


def test_combo_multiplier_rises_in_steps_and_caps():
    assert scoring.combo_multiplier(0) == 1.0
    assert scoring.combo_multiplier(settings.COMBO_MULTIPLIER_STEP_SIZE - 1) == 1.0
    assert scoring.combo_multiplier(settings.COMBO_MULTIPLIER_STEP_SIZE) == (
        1.0 + settings.COMBO_MULTIPLIER_STEP
    )

    huge_combo = settings.COMBO_MULTIPLIER_STEP_SIZE * 1000
    assert scoring.combo_multiplier(huge_combo) == settings.COMBO_MULTIPLIER_MAX


def test_score_for_hit_scales_with_multiplier():
    base = scoring.points_for(scoring.PERFECT)
    assert scoring.score_for_hit(scoring.PERFECT, combo_before_hit=0) == base

    tiered_combo = settings.COMBO_MULTIPLIER_STEP_SIZE
    expected = round(base * scoring.combo_multiplier(tiered_combo))
    assert scoring.score_for_hit(scoring.PERFECT, combo_before_hit=tiered_combo) == expected
