@echo off
echo Building Media Downloader Installer
echo ===============================

echo Step 1: Installing required dependencies...
pip install pyinstaller
pip install yt-dlp
pip install tkinter
pip install pillow
pip install pyperclip
pip install pystray
pip install validators
pip install pywin32
pip install requests
pip install certifi

echo Step 2: Creating executable with PyInstaller...
pyinstaller --noconfirm --onedir --windowed --icon=needyamin.ico --name="Media-Downloader" --add-data="needyamin.ico;." media-download.py

echo Step 3: Building Inno Setup installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss

echo Done! Installer created in the 'installer' folder.
pause 