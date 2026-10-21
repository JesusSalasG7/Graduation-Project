"""Pruebas de las funciones de cálculo con datos sintéticos.

Correr desde la raíz del proyecto:
    .venv/bin/python -m unittest discover -s graphic_interface/analisis/tests -t graphic_interface
"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # graphic_interface/

from analisis.comprehension import attach_comprehension, binarize_comprehension, training_table  # noqa: E402
from analisis.config import AnalysisConfig  # noqa: E402
from analisis.eeg_features import (  # noqa: E402
    add_baseline_change,
    add_within_participant_scaling,
    align_lists,
    baseline_change_pct,
    build_feature_table,
    cognitive_indices,
    combine_bands,
    flag_delta_artifacts,
    log_transform,
    parse_list,
    process_stage,
    quality_mask,
    safe_ratio,
)
from analisis.report import filter_participant, quality_summary, stage_summary  # noqa: E402


def synthetic_row(n=20, poor=None, theta=100.0, low_alpha=40.0, high_alpha=60.0,
                  low_beta=30.0, high_beta=70.0, delta=500.0, **ids):
    """Fila con el mismo formato que dataset_sesiones.csv (listas como texto)."""
    poor = poor if poor is not None else [0] * n
    def as_list(value):
        return str(value if isinstance(value, list) else [value] * n)
    row = {
        "Participante_ID": ids.get("participant", 1), "Nivel_Experiencia": "Perfil 1",
        "Desafio": ids.get("challenge", 1), "Juego": "Game-01",
        "Etapa": ids.get("stage", 2), "Intento": ids.get("attempt", 1),
        "NeuroSky_Theta_List": as_list(theta),
        "NeuroSky_LowAlpha_List": as_list(low_alpha), "NeuroSky_HighAlpha_List": as_list(high_alpha),
        "NeuroSky_LowBeta_List": as_list(low_beta), "NeuroSky_HighBeta_List": as_list(high_beta),
        "NeuroSky_Delta_List": as_list(delta),
        "NeuroSky_PoorSignal_List": str(poor),
        "NeuroSky_Attention_List": str([50] * n), "NeuroSky_Meditation_List": str([0] + [70] * (n - 1)),
    }
    return row


class ParseAndAlignTests(unittest.TestCase):
    def test_parse_list_formats(self):
        self.assertEqual(parse_list("[1, 2, 3]"), [1.0, 2.0, 3.0])
        self.assertEqual(parse_list(""), [])
        self.assertEqual(parse_list(float("nan")), [])
        self.assertEqual(parse_list(None), [])
        self.assertEqual(parse_list("no es lista"), [])

    def test_align_lists_trims_to_shortest_and_warns(self):
        aligned, warning = align_lists({"a": [1, 2, 3], "b": [1, 2]})
        self.assertEqual(len(aligned["a"]), 2)
        self.assertEqual(len(aligned["b"]), 2)
        self.assertIn("recortaron a 2", warning)

    def test_align_lists_same_length_no_warning(self):
        _, warning = align_lists({"a": [1, 2], "b": [3, 4]})
        self.assertIsNone(warning)


class QualityFilterTests(unittest.TestCase):
    def test_default_keeps_only_zero(self):
        mask = quality_mask(np.array([0, 26, 51, 200, 0]))
        self.assertEqual(mask.tolist(), [True, False, False, False, True])

    def test_threshold_configurable_but_200_always_dropped(self):
        mask = quality_mask(np.array([0, 26, 51, 200]), threshold=255)
        self.assertEqual(mask.tolist(), [True, True, True, False])


class BandAndRatioTests(unittest.TestCase):
    def test_combine_bands(self):
        alpha, beta = combine_bands(np.array([1, 2]), np.array([3, 4]), np.array([5, 6]), np.array([7, 8]))
        self.assertEqual(alpha.tolist(), [4, 6])
        self.assertEqual(beta.tolist(), [12, 14])

    def test_log_transform(self):
        np.testing.assert_allclose(log_transform(np.array([0, math.e - 1])), [0.0, 1.0])
        self.assertEqual(log_transform(np.array([-5]))[0], 0.0)  # negativo -> 0, no -inf

    def test_safe_ratio_division_by_zero(self):
        out = safe_ratio(np.array([1.0, 2.0, 3.0]), np.array([2.0, 0.0, np.nan]))
        self.assertEqual(out[0], 0.5)
        self.assertTrue(np.isnan(out[1]))
        self.assertTrue(np.isnan(out[2]))

    def test_cognitive_indices(self):
        idx = cognitive_indices(np.array([2.0]), np.array([4.0]), np.array([4.0]))
        self.assertAlmostEqual(idx["EEG1"][0], 0.25)
        self.assertAlmostEqual(idx["EEG2"][0], 0.5)
        self.assertAlmostEqual(idx["AlphaTheta"][0], 2.0)

    def test_indices_with_zero_alpha(self):
        idx = cognitive_indices(np.array([2.0]), np.array([0.0]), np.array([0.0]))
        self.assertTrue(np.isnan(idx["EEG1"][0]))
        self.assertTrue(np.isnan(idx["EEG2"][0]))


class ProcessStageTests(unittest.TestCase):
    def test_known_values(self):
        out = process_stage(synthetic_row())
        theta, alpha, beta = np.log1p(100), np.log1p(100), np.log1p(100)
        self.assertAlmostEqual(out["EEG1_Media"], theta / (alpha + beta))
        self.assertAlmostEqual(out["EEG2_Media"], theta / alpha)
        self.assertAlmostEqual(out["Delta_Media"], np.log1p(500))
        self.assertEqual(out["Muestras_Validas"], 20)
        self.assertEqual(out["Pct_Descartado"], 0.0)
        self.assertFalse(out["Datos_Insuficientes"])
        self.assertEqual(out["eSense_Attention_Media"], 50)
        self.assertEqual(out["eSense_Meditation_Media"], 70)  # el 0 inicial se descarta

    def test_poor_signal_filter_and_pct(self):
        poor = [0] * 15 + [51] * 4 + [200]
        out = process_stage(synthetic_row(poor=poor))
        self.assertEqual(out["Muestras_Validas"], 15)
        self.assertEqual(out["Pct_Descartado"], 25.0)

    def test_filter_removes_bad_samples_from_features(self):
        theta = [100.0] * 15 + [1e9] * 5  # valores basura en las muestras malas
        poor = [0] * 15 + [200] * 5
        out = process_stage(synthetic_row(theta=theta, poor=poor))
        self.assertAlmostEqual(out["EEG2_Media"], np.log1p(100) / np.log1p(100))

    def test_no_valid_samples(self):
        out = process_stage(synthetic_row(poor=[200] * 20))
        self.assertEqual(out["Muestras_Validas"], 0)
        self.assertTrue(out["Datos_Insuficientes"])
        self.assertTrue(math.isnan(out["EEG1_Media"]))

    def test_insufficient_by_fraction(self):
        out = process_stage(synthetic_row(n=40, poor=[0] * 15 + [51] * 25))
        self.assertTrue(out["Datos_Insuficientes"])  # 15 >= 10 pero 37.5 % < 50 %

    def test_insufficient_by_count_configurable(self):
        row = synthetic_row(n=8)
        self.assertTrue(process_stage(row)["Datos_Insuficientes"])
        self.assertFalse(process_stage(row, AnalysisConfig(min_valid_samples=5))["Datos_Insuficientes"])

    def test_different_lengths_are_trimmed(self):
        row = synthetic_row(n=20)
        row["NeuroSky_Theta_List"] = str([100.0] * 18)
        out = process_stage(row)
        self.assertEqual(out["Muestras_Totales"], 18)
        self.assertIn("largo distinto", out["Advertencias"])

    def test_missing_neurosky_columns(self):
        out = process_stage({"Participante_ID": 1})
        self.assertTrue(out["Datos_Insuficientes"])
        self.assertIn("Sin datos NeuroSky", out["Advertencias"])


class BaselineTests(unittest.TestCase):
    def _table(self, rows):
        return pd.DataFrame(rows)

    def test_change_pct_formula(self):
        self.assertAlmostEqual(baseline_change_pct(1.1, 1.0), 10.0)
        self.assertTrue(math.isnan(baseline_change_pct(1.0, 0.0)))
        self.assertTrue(math.isnan(baseline_change_pct(float("nan"), 1.0)))

    def test_change_vs_stage2_same_challenge(self):
        df = self._table([
            {"Participante_ID": 1, "Desafio": 1, "Etapa": 2, "Intento": 1, "EEG1_Media": 0.5, "Datos_Insuficientes": False},
            {"Participante_ID": 1, "Desafio": 1, "Etapa": 3, "Intento": 1, "EEG1_Media": 0.6, "Datos_Insuficientes": False},
            {"Participante_ID": 1, "Desafio": 2, "Etapa": 2, "Intento": 1, "EEG1_Media": 1.0, "Datos_Insuficientes": False},
            {"Participante_ID": 1, "Desafio": 2, "Etapa": 4, "Intento": 1, "EEG1_Media": 0.5, "Datos_Insuficientes": False},
        ])
        out, warnings = add_baseline_change(df, columns=["EEG1_Media"])
        self.assertEqual(warnings, [])
        self.assertEqual(out["EEG1_Media_Cambio_Pct"].round(6).tolist(), [0.0, 20.0, 0.0, -50.0])
        self.assertTrue(out["Linea_Base_Disponible"].all())

    def test_missing_baseline_warns(self):
        df = self._table([
            {"Participante_ID": 1, "Desafio": 1, "Etapa": 3, "Intento": 1, "EEG1_Media": 0.6, "Datos_Insuficientes": False},
        ])
        out, warnings = add_baseline_change(df, columns=["EEG1_Media"])
        self.assertTrue(math.isnan(out["EEG1_Media_Cambio_Pct"].iloc[0]))
        self.assertFalse(out["Linea_Base_Disponible"].iloc[0])
        self.assertEqual(len(warnings), 1)

    def test_insufficient_baseline_is_not_used(self):
        df = self._table([
            {"Participante_ID": 1, "Desafio": 1, "Etapa": 2, "Intento": 1, "EEG1_Media": 0.5, "Datos_Insuficientes": True},
            {"Participante_ID": 1, "Desafio": 1, "Etapa": 3, "Intento": 1, "EEG1_Media": 0.6, "Datos_Insuficientes": False},
        ])
        out, warnings = add_baseline_change(df, columns=["EEG1_Media"])
        self.assertTrue(out["EEG1_Media_Cambio_Pct"].isna().all())
        self.assertEqual(len(warnings), 1)


class ScalingTests(unittest.TestCase):
    def test_zscore_and_minmax_within_participant(self):
        df = pd.DataFrame({
            "Participante_ID": [1, 1, 1, 2, 2],
            "EEG1_Media": [1.0, 2.0, 3.0, 10.0, 10.0],
            "Datos_Insuficientes": [False] * 5,
        })
        out = add_within_participant_scaling(df, columns=["EEG1_Media"])
        np.testing.assert_allclose(out["EEG1_Media_Z"][:3], [-1.2247449, 0.0, 1.2247449], rtol=1e-6)
        np.testing.assert_allclose(out["EEG1_Media_MinMax"][:3], [0.0, 0.5, 1.0])
        self.assertEqual(out["EEG1_Media_Z"][3:].tolist(), [0.0, 0.0])  # sin variación -> 0

    def test_insufficient_rows_excluded(self):
        df = pd.DataFrame({
            "Participante_ID": [1, 1, 1],
            "EEG1_Media": [1.0, 3.0, 100.0],
            "Datos_Insuficientes": [False, False, True],
        })
        out = add_within_participant_scaling(df, columns=["EEG1_Media"])
        self.assertEqual(out["EEG1_Media_MinMax"][:2].tolist(), [0.0, 1.0])
        self.assertTrue(math.isnan(out["EEG1_Media_MinMax"][2]))

    def test_delta_alert(self):
        df = pd.DataFrame({
            "Participante_ID": [1] * 6,
            "Delta_Media": [10.0, 10.1, 9.9, 10.0, 10.05, 20.0],
            "Datos_Insuficientes": [False] * 6,
        })
        out = flag_delta_artifacts(df, z_threshold=2.0)
        self.assertEqual(out["Delta_Atipica"].tolist(), [False] * 5 + [True])


class PipelineAndComprehensionTests(unittest.TestCase):
    def test_build_feature_table_end_to_end(self):
        dataset = pd.DataFrame([
            synthetic_row(stage=2),
            synthetic_row(stage=3, theta=200.0),
            synthetic_row(stage=4, poor=[200] * 20),
        ])
        features, warnings = build_feature_table(dataset)
        self.assertEqual(len(features), 3)
        self.assertEqual(warnings, [])
        self.assertGreater(features["EEG1_Media_Cambio_Pct"].iloc[1], 0)
        self.assertTrue(features["Datos_Insuficientes"].iloc[2])

    def test_binarize_comprehension(self):
        self.assertTrue(binarize_comprehension(4))
        self.assertFalse(binarize_comprehension(3.5))
        self.assertIsNone(binarize_comprehension(float("nan")))
        self.assertTrue(binarize_comprehension(3, threshold=2.5))
        with self.assertRaises(ValueError):
            binarize_comprehension(7)

    def test_attach_comprehension_and_training_table(self):
        features, _ = build_feature_table(pd.DataFrame([synthetic_row(stage=2), synthetic_row(stage=3)]))
        empty = attach_comprehension(features)
        self.assertTrue(empty["Comprension_Puntaje"].isna().all())
        scored = attach_comprehension(features, {(1, 1, 3, 1): 5.0})
        self.assertEqual(scored["Comprension_Alta"].tolist(), [None, True])
        X, y = training_table(scored, ["EEG1_Media", "EEG2_Media"])
        self.assertEqual(len(X), 1)
        self.assertTrue(y.iloc[0])


class ReportTests(unittest.TestCase):
    def setUp(self):
        dataset = pd.DataFrame([
            synthetic_row(stage=2),
            synthetic_row(stage=3, theta=200.0),
            synthetic_row(stage=4, poor=[200] * 20),
            synthetic_row(participant=2, stage=2),
        ])
        self.features, _ = build_feature_table(dataset)

    def test_filter_participant(self):
        self.assertEqual(len(filter_participant(self.features, 2)), 1)
        self.assertEqual(len(filter_participant(self.features, None)), 4)

    def test_stage_summary_skips_insufficient(self):
        summary = stage_summary(self.features)
        self.assertEqual(summary["Etapa"].tolist(), [2, 3])  # la Etapa 4 no tiene datos válidos
        self.assertEqual(summary.loc[summary["Etapa"] == 2, "Filas"].iloc[0], 2)

    def test_quality_summary(self):
        quality = quality_summary(self.features)
        self.assertEqual(quality["insuficientes"], ["P1 · Desafío 1 · Etapa 4 · Intento 1"])
        self.assertEqual(quality["pct_descartado_por_etapa"][4], 100.0)


if __name__ == "__main__":
    unittest.main()
