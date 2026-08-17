@echo off

echo ============================================
echo Building Image Archive Tool
echo ============================================

call .venv\Scripts\activate.bat

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "ImageArchiveTool" ^
    --icon "ImageArchiveTool.ico" ^
    --add-data "ImageArchiveTool.ico:." ^
    "image_archive_gui_IR_RGB_depth_international.py"

echo.
echo ============================================
echo Build finished.
echo EXE: dist\ImageArchiveTool.exe
echo ============================================

pause