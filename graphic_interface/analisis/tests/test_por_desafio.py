"""Pruebas de la vista por desafío con el dataset sintético de
test_pipeline duplicado como Desafío 2 (otros puntajes y otras señales).

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
from analisis.pipeline import COLUMNAS_RESULTADO, ejecutar_pipeline  # noqa: E402
from analisis.por_desafio import (  # noqa: E402
    COLUMNAS_POR_DESAFIO, desafios_disponibles, resultados_por_desafio, vista_desafio,
)
from analisis.tests.test_pipeline import dataset_sintetico  # noqa: E402


def dataset_dos_desafios() -> pd.DataFrame:
    d1 = dataset_sintetico(seed=0).assign(Juego="Game-01")
    d2 = dataset_sintetico(seed=1).assign(Desafio=2, Juego="Game-04")
    return pd.concat([d1, d2], ignore_index=True)


class TestPorDesafio(unittest.TestCase):
    def setUp(self):
        self.cfg = ConfigAnalisis()
        self.dataset = dataset_dos_desafios()
        self.pipeline = ejecutar_pipeline(self.dataset, self.cfg)
        self.tabla, self.avisos = resultados_por_desafio(self.pipeline.muestras, self.dataset, self.cfg)

    def test_una_fila_por_participante_desafio_y_etapa(self):
        self.assertEqual(list(self.tabla.columns), COLUMNAS_POR_DESAFIO)
        self.assertEqual(len(self.tabla), 3 * 2 * 4)
        self.assertFalse(self.tabla.duplicated(["participante", "desafio", "etapa"]).any())
        self.assertEqual(desafios_disponibles(self.tabla), [(1, "Desafío 1 · Game-01"), (2, "Desafío 2 · Game-04")])

    def test_mismos_z_que_el_pipeline(self):
        """La mediana de cada celda sale de las mismas muestras normalizadas."""
        m = self.pipeline.muestras
        esperado = m.groupby(["participante", "desafio", "etapa"])["EEG1_z"].median()
        obtenido = self.tabla.set_index(["participante", "desafio", "etapa"])["EEG1_z"]
        self.assertTrue(np.allclose(obtenido.loc[esperado.index], esperado))

    def test_puntaje_del_desafio(self):
        fila = self.dataset[(self.dataset["Participante_ID"] == 2) & (self.dataset["Desafio"] == 2)
                            & (self.dataset["Etapa"] == 4)].iloc[0]
        celda = self.tabla[(self.tabla["participante"] == 2) & (self.tabla["desafio"] == 2)
                           & (self.tabla["etapa"] == "Etapa 4")].iloc[0]
        self.assertAlmostEqual(celda["puntaje"], 100 * fila["Cuestionario_Correctas"] / 7.0)
        self.assertTrue(self.tabla.loc[self.tabla["etapa"] == "Etapa 3", "puntaje"].isna().all())

    def test_vista_tiene_columnas_de_resultados(self):
        vista = vista_desafio(self.tabla, 2)
        self.assertEqual(list(vista.columns), COLUMNAS_RESULTADO)
        self.assertEqual(len(vista), 3 * 4)

    def test_celda_con_pocas_muestras_sin_z(self):
        cfg = ConfigAnalisis(min_muestras_validas=10_000)
        tabla, avisos = resultados_por_desafio(self.pipeline.muestras, self.dataset, cfg)
        self.assertTrue(tabla["EEG1_z"].isna().all())
        self.assertEqual(len(avisos), len(tabla))

    def test_graficos_de_un_desafio_y_participante(self):
        from analisis.graficos import generar_figuras
        vista = vista_desafio(self.tabla, 1)
        for participante in (None, 1):
            figuras = generar_figuras(vista, self.cfg, participante=participante, contexto="Desafío 1 · Game-01")
            self.assertEqual(len(figuras), 4)
            self.assertIn("Desafío 1", figuras["perfil_etapas"]._suptitle.get_text())


if __name__ == "__main__":
    unittest.main()
