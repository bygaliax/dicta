from dicta.transcriber import build_initial_prompt, find_cuda_dll_dirs


def test_vocabulario_vacio_devuelve_none():
    assert build_initial_prompt([]) is None


def test_arma_prompt_con_terminos():
    assert (
        build_initial_prompt(["Netlify", "deploy"])
        == "Transcripción técnica. Vocabulario: Netlify, deploy."
    )


def test_dll_dirs_sin_carpeta_nvidia(tmp_path):
    assert find_cuda_dll_dirs(tmp_path / "no-existe") == []


def test_dll_dirs_encuentra_los_bin(tmp_path):
    for pkg in ("cublas", "cudnn", "cuda_nvrtc"):
        (tmp_path / pkg / "bin").mkdir(parents=True)
    (tmp_path / "cublas" / "lib").mkdir()  # carpetas sin /bin se ignoran
    dirs = find_cuda_dll_dirs(tmp_path)
    assert sorted(d.parent.name for d in dirs) == ["cublas", "cuda_nvrtc", "cudnn"]
    assert all(d.name == "bin" for d in dirs)
