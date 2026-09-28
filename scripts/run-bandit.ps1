$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dockerArguments = @(
    'run'
    '--rm'
    '--volume'
    "${repositoryRoot}:/workspace"
    '--workdir'
    '/workspace'
    'ghcr.io/pycqa/bandit/bandit:latest'
    '-r'
    'src'
)

& docker @dockerArguments
exit $LASTEXITCODE
