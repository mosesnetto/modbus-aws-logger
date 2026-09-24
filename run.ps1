$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment not found. Create .venv and install requirements.txt first.'
}
& $python (Join-Path $PSScriptRoot 'modbus_aws_logger.py') @args
exit $LASTEXITCODE
