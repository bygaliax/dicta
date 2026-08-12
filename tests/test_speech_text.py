from dicta.speech_text import es_pregunta, ultimo_parrafo


def test_un_solo_parrafo_corto_sale_tal_cual():
    assert ultimo_parrafo("Hecho, todo verde.") == "Hecho, todo verde."


def test_acumula_parrafos_de_prosa_desde_el_final():
    # v3.1: ya no se lee solo el último párrafo, sino toda la prosa que quepa.
    text = "Primero analicé el bug.\n\nLuego lo arreglé.\n\n¿Quieres que haga commit?"
    assert ultimo_parrafo(text) == (
        "Primero analicé el bug. Luego lo arreglé. ¿Quieres que haga commit?"
    )


def test_acumulacion_respeta_el_tope_por_parrafos_completos():
    text = "Primero analicé el bug.\n\nLuego lo arreglé.\n\n¿Quieres que haga commit?"
    # Solo cabe el último párrafo: los anteriores se descartan enteros.
    assert ultimo_parrafo(text, max_chars=30) == "¿Quieres que haga commit?"


def test_ignora_parrafos_de_solo_codigo():
    text = "¿Lanzo los tests?\n\n```bash\npytest -v\n```"
    assert ultimo_parrafo(text) == "¿Lanzo los tests?"


def test_limpia_markdown_para_tts():
    text = "El **fix** está en `app.py`.\n\n## Resumen\nTodo *verde*."
    assert ultimo_parrafo(text) == "El fix está en app.py. Resumen Todo verde."


def test_texto_vacio_devuelve_vacio():
    assert ultimo_parrafo("") == ""
    assert ultimo_parrafo("\n\n  \n") == ""


def test_salta_el_bloque_de_sources_del_final():
    # El caso real: la respuesta termina en la lista de fuentes de una búsqueda web.
    text = (
        "Lo que sí haría: bajar el suelo de 35.\n\n"
        "Y ojo, el mismo techo aplica a Gyaa.\n\n"
        "Sources:\n"
        "- [Shopify Help Center](https://help.shopify.com/klarna)\n"
        "- [Klarna docs](https://docs.klarna.com/shopify)"
    )
    assert ultimo_parrafo(text) == (
        "Lo que sí haría: bajar el suelo de 35. Y ojo, el mismo techo aplica a Gyaa."
    )


def test_salta_titulos_de_fuentes_en_espanol():
    text = "Conclusión real.\n\nFuentes:\n- https://uno.com\n- https://dos.com"
    assert ultimo_parrafo(text) == "Conclusión real."


def test_salta_tablas():
    text = "Conclusión final.\n\n| plan | precio |\n|---|---|\n| basic | 29 |"
    assert ultimo_parrafo(text) == "Conclusión final."


def test_salta_listas_que_son_solo_enlaces():
    text = "Resumen de verdad.\n\n- https://uno.com/a\n- https://dos.com/b"
    assert ultimo_parrafo(text) == "Resumen de verdad."


def test_prosa_con_enlace_inline_no_se_salta():
    text = "La doc está en [la guía](https://x.com/guia), léela.\n\n¿Sigo?"
    assert ultimo_parrafo(text) == "La doc está en la guía, léela. ¿Sigo?"


def test_quita_urls_sueltas_del_texto_hablado():
    assert ultimo_parrafo("Mira https://example.com/x y dime.") == "Mira y dime."


def test_enlace_markdown_se_lee_como_su_texto():
    assert ultimo_parrafo("Está en [la guía](https://example.com).") == "Está en la guía."


def test_todo_ruido_devuelve_vacio():
    text = "Sources:\n- [a](https://b.com)\n- [c](https://d.com)"
    assert ultimo_parrafo(text) == ""


def test_quita_simbolos_que_el_tts_vocaliza_raro():
    # Flechas, rayas, puntos medios y ≈ no deben llegar a la voz.
    text = "Settings → Payments → activar Klarna — coste ≈ 8% · plan Basic."
    assert ultimo_parrafo(text) == "Settings Payments activar Klarna coste 8% plan Basic."


def test_quita_emojis():
    assert ultimo_parrafo("Listo ✅ todo verde 🚀.") == "Listo todo verde ."


def test_conserva_puntuacion_normal_y_acentos():
    text = "¿Vale así? ¡Sí! Cuesta $35, o sea, el 2.9%; nada más."
    assert ultimo_parrafo(text) == text


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
