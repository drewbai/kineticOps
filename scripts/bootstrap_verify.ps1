$ErrorActionPreference = "Stop"

$venvPython = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    py -3.13 -m venv .venv
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
& $venvPython -m pip install -r requirements-dev.txt
& $venvPython -c "import torch; print(torch.__version__)"
& $venvPython -m pytest -q
