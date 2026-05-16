@echo off
chcp 65001
echo ===============================================
echo    THAR PATHOLOGY LAB BUILD SYSTEM
echo ===============================================
echo.

echo Cleaning previous builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del lab_billing.spec 2>nul
del lab_billing.db 2>nul

echo.
echo Installing required packages...
pip install reportlab pyinstaller

echo.
echo Building executable...
pyinstaller --onefile --windowed --name "TharPathologyLab" --clean --noconfirm lab_billing.py

echo.
if exist "dist\TharPathologyLab.exe" (
    echo SUCCESS: Build completed!
    echo.
    echo Files created:
    echo - dist\TharPathologyLab.exe (Main executable)
    echo.
    echo Next steps:
    echo 1. Test TharPathologyLab.exe
    echo 2. Deliver to client
) else (
    echo ERROR: Build failed!
)

echo.
pause