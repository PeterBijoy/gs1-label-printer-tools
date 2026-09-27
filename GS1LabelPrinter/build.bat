@echo off
setlocal

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist "bin\zint.exe" (
    echo ERROR: bin\zint.exe not found. Place the zint.exe binary in the bin folder before building.
    pause
    exit /b 1
)

echo Building standalone app with PyInstaller (--onedir mode)...
set ICON_ARG=
if exist "assets\icon.ico" set ICON_ARG=--icon "assets\icon.ico"

python -m PyInstaller --noconfirm --onedir --windowed --noupx ^
    --name "GS1LabelPrinter" ^
    --add-binary "bin\zint.exe;bin" ^
    --hidden-import win32timezone ^
    %ICON_ARG% ^
    app.py

if not exist "dist\GS1LabelPrinter\GS1LabelPrinter.exe" (
    echo ERROR: Build failed - dist\GS1LabelPrinter\GS1LabelPrinter.exe was not created.
    pause
    exit /b 1
)

echo.
echo Build complete.
echo The app folder is at: dist\GS1LabelPrinter\
echo Run dist\GS1LabelPrinter\GS1LabelPrinter.exe to start the app.
echo (--onedir mode: keep the whole GS1LabelPrinter folder together -- the exe
echo  depends on the other files next to it. Use installer.iss / Inno Setup
echo  to package the whole folder into a distributable Setup.exe.)
echo.
pause
endlocal
