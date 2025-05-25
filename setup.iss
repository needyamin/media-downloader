#define MyAppName "Media Downloader"
#define MyAppVersion "1.0.15"
#define MyAppPublisher "Md Yamin Hossain"
#define MyAppURL "https://github.com/needyamin/media-downloader"
#define MyAppExeName "Media-Downloader.exe"

[Setup]
; Basic setup parameters
AppId={{EE7A0919-7BE4-4A6D-AB0A-DBD30A51C5B4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Compression settings
Compression=lzma
SolidCompression=yes
; Visuals and UI
SetupIconFile=needyamin.ico
UninstallDisplayIcon={app}\needyamin.ico
WizardStyle=modern
; Output settings
OutputDir=installer
OutputBaseFilename=MediaDownloader_Setup
; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startupicon"; Description: "{cm:StartupDescription}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main executable (corrected path for PyInstaller --onedir output)
Source: "dist\Media-Downloader\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Icon file
Source: "needyamin.ico"; DestDir: "{app}"; Flags: ignoreversion
; Add all other files from the PyInstaller output folder
Source: "dist\Media-Downloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Add registry keys for auto-start (optional)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Media Downloader"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[CustomMessages]
StartupDescription=Start {#MyAppName} when Windows starts

[Code]
// Custom code for the installer can be added here 