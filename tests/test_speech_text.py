from dicta.speech_text import es_pregunta, ultimo_parrafo


def test_un_solo_parrafo_corto_sale_tal_cual():
    assert ultimo_parrafo("Hecho, todo verde.") == "Hecho, todo verde."


def test_devuelve_el_ultimo_parrafo():
    text = "Primero analicé el bug.\n\nLuego lo arreglé.\n\n¿Quieres que haga commit?"
    assert ultimo_parrafo(text) == "¿Quieres que haga commit?"


def test_ignora_parrafos_de_solo_codigo():
    text = "¿Lanzo los tests?\n\n```bash\npytest -v\n```"
    assert ultimo_parrafo(text) == "¿Lanzo los tests?"


def test_limpia_markdown_para_tts():
    text = "El **fix** está en `app.py`.\n\n## Resumen\nTodo *verde*."
    assert ultimo_parrafo(text) == "Resumen Todo verde."


def test_texto_vacio_devuelve_vacio():
    assert ultimo_parrafo("") == ""
    assert ultimo_parrafo("\n\n  \n") == ""


def test_tope_corta_por_frase_conservando_el_final():
    frases = [f"Frase de relleno número {i}." for i in range(30)]
    text = " ".join(frases) + " ¿Te parece bien?"
    out = ultimo_parrafo(text, max_chars=60)
    assert out.endswith("¿Te parece bien?")
    assert len(out) <= 60


def test_frase_unica_mas_larga_que_el_tope_se_corta_por_el_final():
    text = "x" * 500 + " final"
    out = ultimo_parrafo(text, max_chars=50)
    assert len(out) <= 50
    assert out.endswith("final")


def test_es_pregunta_con_signo_de_apertura():
    assert es_pregunta("Listo. ¿Hago push?") is True


def test_es_pregunta_con_signo_final():
    assert es_pregunta("Todo listo. Dime como seguimos?") is True


def test_no_es_pregunta():
    assert es_pregunta("Hecho. Todo comiteado y en verde.") is False


def test_pregunta_antigua_no_cuenta():
    # La pregunta está a más de dos frases del final: ya no es "la" pregunta.
    assert es_pregunta("¿Ves el error? Da igual. Lo arreglé. Quedó en verde.") is False


def test_es_pregunta_texto_vacio():
    assert es_pregunta("") is False
