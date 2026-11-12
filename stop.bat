@echo off
setlocal

echo.
echo ==========================================
echo Остановка AI Video Factory
echo ==========================================
echo.

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo Ошибка: не найден Windows PowerShell.
    goto :failed
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0factory-server.ps1" stop
if errorlevel 1 goto :failed

echo.
pause
exit /b 0

:failed
echo.
echo Сервер не был остановлен. Проверьте сообщение выше.
echo.
pause
exit /b 1
