@echo off
echo ========================================
echo  LVI Laiteluettelo - Asennus
echo ========================================
echo.

:: Tarkista Python
python --version >nul 2>&1
if errorlevel 1 (
    echo VIRHE: Python ei ole asennettu!
    echo Lataa osoitteesta: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Asennetaan Python-riippuvuudet...
pip install -r requirements.txt
if errorlevel 1 (
    echo VIRHE: Riippuvuuksien asennus epäonnistui!
    pause
    exit /b 1
)

echo.
echo [2/3] Tarkistetaan Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo HUOM: Ollama ei ole asennettu.
    echo Asenna osoitteesta: https://ollama.com
    echo Asennuksen jälkeen lataa malli:
    echo   ollama pull mistral
    echo.
) else (
    echo Ollama on asennettu.
    echo.
    echo [3/3] Ladataan Mistral-malli (voi kestaa hetken)...
    echo Malli on ~4GB, lataus vie aikaa ensimmäisellä kerralla.
    echo.
    set /p confirm="Haluatko ladata mistral-mallin nyt? (k/e): "
    if /i "%confirm%"=="k" (
        ollama pull mistral
    )
)

echo.
echo ========================================
echo  Asennus valmis!
echo ========================================
echo.
echo Kaytto:
echo   python main.py TK01.pdf
echo   python main.py --status
echo   python main.py --help
echo.
pause
