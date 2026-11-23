@echo off
rem ==========================================================================
rem recompile-chorus.bat - Comprueba Chorus y reinicia el servicio de dev.
rem
rem Chorus NO tiene React ni build de frontend: web/ son ficheros estaticos
rem (HTML/CSS/JS) que Apache sirve en http://chorus-app con no-store, asi que
rem los cambios de interfaz se ven recargando el navegador.
rem
rem Lo que hace este .bat:
rem   1. Comprueba la sintaxis de Python (compileall). Si falla, NO reinicia.
rem   2. Reinicia el servicio chorus (puerto 9600) con la BD de desarrollo.
rem   3. Espera al healthcheck.
rem
rem No toca osap-api, Apache ni la base de datos de pruebas (osap_chorus_test).
rem
rem ATENCION: Chorus NO aplica migraciones al arrancar. Para actualizar el
rem esquema usa primero (dev / test / prod):
rem     python scripts\upgrade_dev_db.py --env dev  --verify-only
rem     python scripts\upgrade_dev_db.py --env dev
rem     python scripts\upgrade_dev_db.py --env dev  --apply
rem     python scripts\upgrade_dev_db.py --env test --apply
rem     python scripts\upgrade_dev_db.py --env prod --database-url "..." --apply --confirm-production
rem
rem Uso:
rem   recompile-chorus.bat              compilar + reiniciar + esperar healthcheck
rem   recompile-chorus.bat -SkipCompile solo reiniciar (sin comprobar sintaxis)
rem   recompile-chorus.bat -NoWait      no esperar al healthcheck
rem
rem Si el puerto esta ocupado por un proceso elevado, ejecuta este .bat
rem como administrador (o usa osap-api\script\restart-dev.ps1).
rem ==========================================================================
setlocal

set "REPO=%~dp0"
set "SCRIPT=%REPO%scripts\restart-chorus-dev.ps1"

where pwsh >nul 2>nul
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
)

set "RC=%errorlevel%"
echo.
if "%RC%"=="0" goto :ok

echo *** Finalizo con errores - codigo %RC%. Revisa los mensajes y los logs de arriba. ***
echo.
pause
exit /b %RC%

:ok
echo *** Completado correctamente. ***
exit /b 0