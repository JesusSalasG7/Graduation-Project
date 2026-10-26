"""Pruebas del pipeline con datos sintéticos: 3 participantes × Etapas 2–5.

Correr desde la raíz del proyecto:
    .venv/bin/python -m unittest discover -s graphic_interface/analisis/tests -t graphic_interface
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # graphic_interface/

from analisis.config import ConfigAnalisis  # noqa: E402
from analisis.estadistica import holm, tabla_estadistica  # noqa: E402
from analisis.pipeline import (  # noqa: E402
    COLUMNAS_LISTA,
    COLUMNAS_RESULTADO,
    ejecutar_pipeline,
    expandir_formato_largo,
    filtrar_calidad,
    interpretar_carga,
    normalizar_etapa,
    parsear_lista,
)

N_MUESTRAS = 120
N_MALAS = 20  # muestras con PoorSignal > 0 al inicio de cada etapa


def dataset_sintetico(seed: int = 0) -> pd.DataFrame:
    """3 participantes, Etapas 2–5, una fila por participante y etapa con
    listas como texto "[...]" (igual que dataset_sesiones.csv). Las primeras
    N_MALAS muestras tienen PoorSignal 26/51/200 y valores absurdos de
    Theta para detectar si se cuelan."""
    rng = np.random.default_rng(seed)
    filas = []
    for participante in (1, 2, 3):
        for etapa in (2, 3, 4, 5):
            datos = {}
            for nombre in COLUMNAS_LISTA:
                datos[nombre] = rng.lognormal(mean=10, sigma=1, size=N_MUESTRAS).round()
            datos["poor_signal"] = np.zeros(N_MUESTRAS)
            datos["poor_signal"][:N_MALAS] = rng.choice([26, 51, 200], size=N_MALAS)
            datos["theta"][:N_MALAS] = 1e12  # contaminación si el filtro falla
            datos["attention"] = rng.integers(1, 100, N_MUESTRAS)
            datos["meditation"] = rng.integers(1, 100, N_MUESTRAS)
            fila = {
                "Participante_ID": participante, "Desafio": 1, "Etapa": etapa, "Intento": 1,
                "Duracion_Segundos": float(N_MUESTRAS),
                "Cuestionario_Correctas": np.nan if etapa == 3 else float(rng.integers(3, 8)),
                "Cuestionario_Total": np.nan if etapa == 3 else 7.0,
            }
            for nombre, col in COLUMNAS_LISTA.items():
                fila[col] = str([float(v) for v in datos[nombre]])
            filas.append(fila)
    return pd.DataFrame(filas)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.dataset = dataset_sintetico()
        self.cfg = ConfigAnalisis()

    def test_filtro_poor_signal(self):
        largo, _ = expandir_formato_largo(self.dataset, self.cfg)
        validas, calidad, _ = filtrar_calidad(largo, self.cfg)
        self.assertTrue((validas["poor_signal"] == 0).all())
        self.assertLess(validas["theta"].max(), 1e12)
        self.assertTrue((calidad["muestras_validas"] == N_MUESTRAS - N_MALAS).all())
        self.assertTrue(np.allclose(calidad["pct_valido"], 100 * (N_MUESTRAS - N_MALAS) / N_MUESTRAS))

    def test_umbral_poor_signal_menor_50(self):
        cfg = ConfigAnalisis(umbral_poor_signal=49)
        largo, _ = expandir_formato_largo(self.dataset, cfg)
        validas, _, _ = filtrar_calidad(largo, cfg)
        self.assertTrue((validas["poor_signal"] < 50).all())
        self.assertTrue((validas["poor_signal"] == 26).any())

    def test_media_z_por_participante_cero(self):
        resultado = ejecutar_pipeline(self.dataset, self.cfg)
        medias = resultado.muestras.groupby("participante")[["EEG1_z", "EEG2_z"]].mean()
        self.assertTrue(np.allclose(medias.to_numpy(), 0, atol=1e-9))
        desv = resultado.muestras.groupby("participante")[["EEG1_z", "EEG2_z"]].std()
        self.assertTrue(np.allclose(desv.to_numpy(), 1, atol=1e-9))

    def test_una_fila_por_participante_y_etapa(self):
        res = ejecutar_pipeline(self.dataset, self.cfg).resultados
        self.assertEqual(list(res.columns), COLUMNAS_RESULTADO)
        self.assertEqual(len(res), 3 * 4)
        self.assertFalse(res.duplicated(["participante", "etapa"]).any())
        self.assertEqual(set(res["etapa"]), {"Etapa 2", "Etapa 3", "Etapa 4", "Etapa 5"})
        self.assertTrue(res.loc[res["etapa"] == "Etapa 3", "puntaje"].isna().all())
        self.assertTrue(res.loc[res["etapa"] != "Etapa 3", "puntaje"].between(0, 100).all())

    def test_etapa_baja_calidad_excluida(self):
        ds = self.dataset.copy()
        fila = (ds["Participante_ID"] == 1) & (ds["Etapa"] == 4)
        ds.loc[fila, "NeuroSky_PoorSignal_List"] = str([200.0] * N_MUESTRAS)
        res = ejecutar_pipeline(ds, self.cfg)
        self.assertEqual(len(res.resultados), 11)
        self.assertTrue(res.calidad.loc[
            (res.calidad["participante"] == 1) & (res.calidad["etapa"] == "Etapa 4"), "baja_calidad"
        ].all())

    def test_linea_base(self):
        ds = self.dataset.copy()
        reposo = ds[ds["Etapa"] == 2].copy()
        reposo["Etapa"] = 1
        ds = pd.concat([ds, reposo], ignore_index=True)
        sin_base = ejecutar_pipeline(ds, self.cfg)
        self.assertEqual(sin_base.etapas_ignoradas, ["Etapa 1"])
        res = ejecutar_pipeline(ds, ConfigAnalisis(etapa_linea_base="Etapa 1"))
        self.assertNotIn("Etapa 1", set(res.resultados["etapa"]))
        self.assertEqual(len(res.resultados), 12)

    def test_listas_de_largo_distinto(self):
        ds = self.dataset.copy()
        ds.loc[0, "NeuroSky_Theta_List"] = str([5.0] * 50)
        largo, avisos = expandir_formato_largo(ds, self.cfg)
        self.assertTrue(any("largo distinto" in a for a in avisos))
        primera = largo[(largo["participante"] == 1) & (largo["etapa"] == "Etapa 2")]
        self.assertEqual(len(primera), 50)

    def test_estadistica_no_falla(self):
        res = ejecutar_pipeline(self.dataset, self.cfg).resultados
        tabla = tabla_estadistica(res, self.cfg)
        self.assertIn("Friedman", set(tabla["analisis"]))
        self.assertTrue(tabla["nota"].str.contains("muestra pequeña").all())


class TestUtilidades(unittest.TestCase):
    def test_normalizar_etapa(self):
        for valor in (2, 2.0, "2", "etapa_2", "Etapa 2", "ETAPA-2"):
            self.assertEqual(normalizar_etapa(valor), "Etapa 2")
        self.assertIsNone(normalizar_etapa(float("nan")))

    def test_parsear_lista(self):
        self.assertEqual(parsear_lista("[1, 2, 3]"), [1.0, 2.0, 3.0])
        self.assertEqual(parsear_lista("1;2;3"), [1.0, 2.0, 3.0])
        self.assertEqual(parsear_lista(""), [])

    def test_interpretacion(self):
        self.assertEqual(interpretar_carga(-0.5, 0.5), "Alta carga")
        self.assertEqual(interpretar_carga(0.5, -0.5), "Baja carga")
        self.assertEqual(interpretar_carga(-0.5, -0.5), "No concluyente")

    def test_holm(self):
        self.assertTrue(np.allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06]))


if __name__ == "__main__":
    unittest.main()
