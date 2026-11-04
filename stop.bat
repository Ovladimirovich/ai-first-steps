@echo off
rem ==========================================
rem Остановка сервера AI Video Factory
rem ==========================================

echo.
echo ==========================================
echo Остановка сервера AI Video Factory
echo ==========================================
echo.

rem Завершаем все процессы python (сервер)
taskkill /F /IM python.exe > nul 2>&1

if %errorlevel% equ 0 (
    echo Сервер остановлен.
) else (
    echo Сервер не был запущен.
)

echo.
pause
