@echo off
setlocal

echo.
echo ==========================================
echo Запуск приложения AI Video Factory
echo ==========================================
echo.

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo Ошибка: не найден Windows PowerShell.
    goto :failed
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0factory-server.ps1" start
if errorlevel 1 goto :failed

start "" "http://localhost:7860"
echo.
echo Приложение открыто в браузере: http://localhost:7860
echo Сервер слушает только этот компьютер; окно сервера содержит журнал.
echo Для остановки используйте stop.bat.
echo.
pause
exit /b 0

:failed
echo.
echo Не удалось запустить сервер. Проверьте Python и сообщение выше.
echo.
pause
exit /b 1
