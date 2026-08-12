import json
from pathlib import Path

from dicta.speak_queue import SpeakItem, drenar_cola, encolar, preparar


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


def test_unlink_bloqueado_no_crashea_y_no_consume(tmp_path, monkeypatch):
    # Simula el hook con el handle abierto (Set-Content sin terminar):
    # unlink() lanza PermissionError (WinError 32 en Windows real).
    _escribir(tmp_path, "001-aviso.json", "aviso", "bloqueado")
    original_unlink = Path.unlink
    llamadas = {"n": 0}

    def unlink_falla_una_vez(self, *args, **kwargs):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise PermissionError("WinError 32: archivo en uso")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_falla_una_vez)

    # 1er drenado: unlink falla -> no crashea, el item no se devuelve, el
    # archivo sigue en disco (no se consumió).
    assert drenar_cola(tmp_path) == []
    assert list(tmp_path.glob("*.json")) != []

    # 2do drenado: unlink ya funciona -> se devuelve el item y se borra.
    assert drenar_cola(tmp_path) == [SpeakItem("aviso", "bloqueado")]
    assert list(tmp_path.glob("*.json")) == []


def test_preparar_cierre_con_pregunta_abre_mic():
    items = [SpeakItem("cierre", "Hecho.\n\n¿Sigo con el resto?")]
    assert preparar(items, 400, True, True, True) == [
        ("cierre", "¿Sigo con el resto?", True)
    ]


def test_preparar_cierre_sin_pregunta_no_abre_mic():
    items = [SpeakItem("cierre", "Hecho. Todo en verde.")]
    assert preparar(items, 400, True, True, True) == [
        ("cierre", "Hecho. Todo en verde.", False)
    ]


def test_preparar_permiso_nunca_abre_mic():
    items = [SpeakItem("permiso", "Claude necesita permiso para usar Bash")]
    assert preparar(items, 400, True, True, True) == [
        ("permiso", "Claude necesita permiso para usar Bash", False)
    ]


def test_preparar_aviso_abre_mic():
    items = [SpeakItem("aviso", "Claude está esperando tu respuesta")]
    assert preparar(items, 400, True, True, True) == [
        ("aviso", "Claude está esperando tu respuesta", True)
    ]


def test_preparar_respeta_escuchar_tras_pregunta_off():
    # preparar conserva el orden de entrada; solo cambia abre_mic
    items = [SpeakItem("cierre", "¿Sigo?"), SpeakItem("aviso", "esperando")]
    assert preparar(items, 400, True, True, False) == [
        ("cierre", "¿Sigo?", False), ("aviso", "esperando", False)
    ]


def test_preparar_filtra_por_config():
    items = [SpeakItem("aviso", "un aviso"), SpeakItem("cierre", "un cierre")]
    assert preparar(items, 400, False, True, True) == [("cierre", "un cierre", False)]
    assert preparar(items, 400, True, False, True) == [("aviso", "un aviso", True)]


def test_preparar_aplica_tope_al_cierre():
    largo = "Relleno inicial que sobra. " * 30 + "¿Te vale así?"
    items = [SpeakItem("cierre", largo)]
    (kind, texto, abre_mic), = preparar(items, 60, True, True, True)
    assert kind == "cierre"
    assert len(texto) <= 60
    assert texto.endswith("¿Te vale así?")
    assert abre_mic is True


def test_encolar_cierre_nuevo_descarta_cierre_viejo_pendiente():
    pendientes = [("cierre", "cierre viejo", False)]
    nuevos = [("cierre", "cierre nuevo", False)]
    assert encolar(pendientes, nuevos) == [("cierre", "cierre nuevo", False)]


def test_encolar_conserva_avisos_y_permisos_pendientes_en_orden():
    pendientes = [
        ("aviso", "aviso viejo", True),
        ("permiso", "permiso viejo", False),
        ("cierre", "cierre viejo", False),
    ]
    nuevos = [("cierre", "cierre nuevo", True)]
    assert encolar(pendientes, nuevos) == [
        ("aviso", "aviso viejo", True),
        ("permiso", "permiso viejo", False),
        ("cierre", "cierre nuevo", True),
    ]


def test_encolar_sin_cierre_nuevo_no_toca_cierre_pendiente():
    pendientes = [("cierre", "cierre viejo", False)]
    nuevos = [("aviso", "un aviso", True)]
    assert encolar(pendientes, nuevos) == [
        ("cierre", "cierre viejo", False),
        ("aviso", "un aviso", True),
    ]


def test_encolar_pendientes_vacio_solo_agrega_nuevos():
    assert encolar([], [("aviso", "hola", True)]) == [("aviso", "hola", True)]
