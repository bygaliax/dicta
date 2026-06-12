from dicta.transcriber import build_initial_prompt


def test_vocabulario_vacio_devuelve_none():
    assert build_initial_prompt([]) is None


def test_arma_prompt_con_terminos():
    assert (
        build_initial_prompt(["Netlify", "deploy"])
        == "Transcripción técnica. Vocabulario: Netlify, deploy."
    )
