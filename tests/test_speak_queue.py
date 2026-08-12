import json

from dicta.speak_queue import SpeakItem, drenar_cola, preparar


def _escribir(tmp_path, nombre, kind, text):
    (tmp_path / nombre).write_text(
        json.dumps({"ts": 1, "kind": kind, "text": text}), encoding="utf-8"
    )


def test_dir_inexistente_devuelve_vacio(tmp_path):
    assert drenar_cola(tmp_path / "no-existe") == []


def test_lee_en_orden_y_borra(tmp_path):
    _escribir(tmp_path, "001-aviso.json", "aviso", "primero")
    _escribir(tmp_path, "002-permiso.json", "permiso", "segundo")
    items = drenar_cola(tmp_path)
    assert items == [SpeakItem("aviso", "primero"), SpeakItem("permiso", "segundo")]
    assert list(tmp_path.glob("*.json")) == []


def test_coalescing_solo_el_ultimo_cierre(tmp_path):
    _escribir(tmp_path, "001-cierre.json", "cierre", "cierre viejo")
    _escribir(tmp_path, "002-aviso.json", "aviso", "un aviso")
    _escribir(tmp_path, "003-cierre.json", "cierre", "cierre nuevo")
    items = drenar_cola(tmp_path)
    assert items == [SpeakItem("aviso", "un aviso"), SpeakItem("cierre", "cierre nuevo")]


def test_corrupto_se_borra_y_se_sigue(tmp_path):
    (tmp_path / "001-cierre.json").write_text("{esto no es json", encoding="utf-8")
    _escribir(tmp_path, "002-aviso.json", "aviso", "válido")
    assert drenar_cola(tmp_path) == [SpeakItem("aviso", "válido")]
    assert list(tmp_path.glob("*.json")) == []


def test_texto_vacio_y_kind_desconocido_se_ignoran(tmp_path):
    _escribir(tmp_path, "001-aviso.json", "aviso", "   ")
    _escribir(tmp_path, "002-raro.json", "otra-cosa", "hola")
    assert drenar_cola(tmp_path) == []


def test_preparar_cierre_con_pregunta_abre_mic():
    items = [SpeakItem("cierre", "Hecho.\n\n¿Sigo con el resto?")]
    assert preparar(items, 400, True, True, True) == [("¿Sigo con el resto?", True)]


def test_preparar_cierre_sin_pregunta_no_abre_mic():
    items = [SpeakItem("cierre", "Hecho. Todo en verde.")]
    assert preparar(items, 400, True, True, True) == [("Hecho. Todo en verde.", False)]


def test_preparar_permiso_nunca_abre_mic():
    items = [SpeakItem("permiso", "Claude necesita permiso para usar Bash")]
    assert preparar(items, 400, True, True, True) == [
        ("Claude necesita permiso para usar Bash", False)
    ]


def test_preparar_aviso_abre_mic():
    items = [SpeakItem("aviso", "Claude está esperando tu respuesta")]
    assert preparar(items, 400, True, True, True) == [
        ("Claude está esperando tu respuesta", True)
    ]


def test_preparar_respeta_escuchar_tras_pregunta_off():
    # preparar conserva el orden de entrada; solo cambia abre_mic
    items = [SpeakItem("cierre", "¿Sigo?"), SpeakItem("aviso", "esperando")]
    assert preparar(items, 400, True, True, False) == [
        ("¿Sigo?", False), ("esperando", False)
    ]


def test_preparar_filtra_por_config():
    items = [SpeakItem("aviso", "un aviso"), SpeakItem("cierre", "un cierre")]
    assert preparar(items, 400, False, True, True) == [("un cierre", False)]
    assert preparar(items, 400, True, False, True) == [("un aviso", True)]


def test_preparar_aplica_tope_al_cierre():
    largo = "Relleno inicial que sobra. " * 30 + "¿Te vale así?"
    items = [SpeakItem("cierre", largo)]
    (texto, abre_mic), = preparar(items, 60, True, True, True)
    assert len(texto) <= 60
    assert texto.endswith("¿Te vale así?")
    assert abre_mic is True
