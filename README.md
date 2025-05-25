# Media Downloader

A desktop application developed for educational and personal use, designed to help users explore how media handling tools work. It supports downloading high-quality videos and audio from public sources.

## Application Preview
![Image](https://github.com/user-attachments/assets/c4984fc3-5efb-43f4-9533-4092a2d1caaf)

## Features

- Simple and intuitive user interface
- Download videos and audio in various formats
- Automatic clipboard monitoring for media links
- Customizable download quality settings
- Support for downloading entire playlists
- Desktop support (Windows)
- System tray integration for background operation
- Automatic updates

## Installation

### Option 1: Download the Installer
1. Go to the [Releases](https://github.com/needyamin/media-downloader/releases) page
2. Download the latest `MediaDownloader_Setup.exe` 
3. Run the installer and follow the on-screen instructions

### Option 2: Build from Source
1. Clone this repository:
   ```
   git clone https://github.com/needyamin/media-downloader.git
   cd media-downloader
   ```

2. Make sure you have the required dependencies:
   ```
   pip install yt-dlp pillow pyperclip pystray validators pywin32 requests certifi
   ```

3. Run the application directly:
   ```
   python media-download.py
   ```

4. (Optional) Build the installer:
   - Install [Inno Setup](https://jrsoftware.org/isdl.php)
   - Run the build script:
     ```
     build_installer.bat
     ```
   - Find the installer in the `installer` folder

## Usage

1. Launch the application
2. Paste a media URL or let the app detect it from your clipboard
3. Choose your preferred quality settings
4. Click "Download Video" or "Download Audio"
5. Your media will be saved to the Downloads folder

## Dependencies

- Python 3.6+
- yt-dlp
- Tkinter
- PIL (Pillow)
- PyPerClip
- PyStray
- Validators
- PyWin32
- Requests
- Certifi
- FFmpeg (automatically downloaded by the application)

## Legal Notice

This software is provided for educational and personal use only. Users are responsible for ensuring they comply with all applicable laws and terms of service when using this application.

❌ Do not use this software to access or download content in violation of any terms of service or applicable laws.

## Author

Created by [Md Yamin Hossain](https://github.com/needyamin)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
