@echo off
rem Бат-файл для запуска Remotion Studio с автоматическим запуском сервера

echo ==========================================
echo Запуск приложения ai-first-steps
echo ==========================================

rem Переходим в директорию проекта
cd /d "C:\Users\1\OneDrive\Desktop\ai-first-steps\remotion"

rem Проверяем, запущен ли уже сервер (порт 3000)
echo Проверка сервера на порту 3000...
netstat -an | find ":3000" >nul
if %errorlevel% equ 0 (
    echo Сервер уже запущен на порту 3000
) else (
    echo Сервер не запущен. Запуск npm run dev...
    rem Запускаем сервер в фоне и перенаправляем вывод в лог
    start /b cmd /c "npm run dev > server.log 2>&1"
    echo Сервер запущен в фоновом режиме
    rem Даем серверу время на инициализацию
    timeout /t 10 /nobreak > nul
)

rem Открываем браузер на порт 3000 (Remotion Studio)
echo Открытие браузера...
start "" "http://localhost:3000"

echo.
echo === Информация ===
echo Приложение открыто в браузере по адресу: http://localhost:3000
echo Лог сервера сохранен в: server.log
echo
echo Для остановки сервера закройте это окно или нажмите Ctrl+C
echo.
pause