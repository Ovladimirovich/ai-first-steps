param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('start', 'stop')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$StateDirectory = Join-Path $ProjectRoot '.factory'
$StateFile = Join-Path $StateDirectory 'server-process.json'
$ServerPort = 7860

function Test-ServerPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect([System.Net.IPAddress]::Loopback, $ServerPort)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-ManagedServer {
    if (-not (Test-Path -LiteralPath $StateFile)) { return $null }
    try {
        $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
        $processId = [int]$state.ProcessId
        if ($processId -le 0) { return $null }
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
        $process = Get-Process -Id $processId -ErrorAction Stop
        if (-not $processInfo -or -not $state.ExecutablePath -or -not $state.StartTimeUtcTicks) { return $null }
        if (-not [string]::Equals($processInfo.ExecutablePath, [string]$state.ExecutablePath, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
        if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$state.StartTimeUtcTicks) { return $null }
        if ($processInfo.CommandLine -notmatch '(?i)(^|\s)"?-m"?\s+"?factory"?(\s|$)') { return $null }
        if ($processInfo.CommandLine -notmatch '(?i)"?--port"?\s+"?7860"?(\s|$)') { return $null }
        return @{ State = $state; Process = $process; ProcessInfo = $processInfo }
    } catch {
        return $null
    }
}

function Remove-ServerState {
    if (Test-Path -LiteralPath $StateFile) {
        Remove-Item -LiteralPath $StateFile -Force
    }
}

if ($Action -eq 'start') {
    $existing = Get-ManagedServer
    if ($existing) {
        Write-Host "AI Video Factory уже работает (PID $($existing.State.ProcessId))."
        exit 0
    }
    Remove-ServerState
    if (Test-ServerPort) {
        throw "Порт $ServerPort уже занят другим процессом. Он не будет остановлен автоматически."
    }

    $pythonArgs = @()
    $venvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $pythonPath = (Resolve-Path -LiteralPath $venvPython).Path
    } else {
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($python) {
            $pythonPath = $python.Source
        } else {
            $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
            if (-not $launcher) {
                throw 'Python не найден. Установите Python 3.10+ или создайте .venv в корне проекта.'
            }
            $pythonPath = (& $launcher.Source -3 -c 'import sys; print(sys.executable)' | Select-Object -Last 1).Trim()
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pythonPath)) {
                throw 'Не удалось определить путь к Python 3 через py.exe.'
            }
        }
    }
    $pythonArgs += @('-m', 'factory', '--host', '127.0.0.1', '--port', [string]$ServerPort)

    New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
    $server = Start-Process -FilePath $pythonPath -ArgumentList $pythonArgs -WorkingDirectory $ProjectRoot -WindowStyle Normal -PassThru
    Start-Sleep -Milliseconds 300
    $startedProcess = Get-Process -Id $server.Id -ErrorAction SilentlyContinue
    $startedProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($server.Id)"
    if (-not $startedProcess -or -not $startedProcessInfo) {
        throw 'Процесс Python завершился сразу после запуска или Windows не смогла определить его путь.'
    }

    $state = [ordered]@{
        ProcessId = $server.Id
        ExecutablePath = $startedProcessInfo.ExecutablePath
        StartTimeUtcTicks = $startedProcess.StartTime.ToUniversalTime().Ticks
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8

    $ready = $false
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        if (-not (Get-Process -Id $server.Id -ErrorAction SilentlyContinue)) { break }
        if (Test-ServerPort) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        $stillRunning = Get-Process -Id $server.Id -ErrorAction SilentlyContinue
        if ($stillRunning) { & (Join-Path $env:SystemRoot 'System32\taskkill.exe') /PID $server.Id /T /F | Out-Null }
        Remove-ServerState
        throw 'Сервер не открыл порт 7860 за 15 секунд. Проверьте журнал окна сервера.'
    }

    Write-Host "Сервер готов: http://localhost:$ServerPort (PID $($server.Id))."
    exit 0
}

$managed = Get-ManagedServer
if (-not $managed) {
    Remove-ServerState
    if (Test-ServerPort) {
        throw "Порт $ServerPort занят, но процесс не совпадает с записанным экземпляром фабрики. Чужой процесс оставлен работать."
    }
    Write-Host 'Запущенный этим run.bat сервер не найден.'
    exit 0
}

$taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
& $taskkill /PID $managed.State.ProcessId /T /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось завершить процесс фабрики PID $($managed.State.ProcessId)."
}
Remove-ServerState
Write-Host "Остановлен только сервер AI Video Factory (PID $($managed.State.ProcessId))."
