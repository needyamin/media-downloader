#define MyAppName "Media Downloader"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Md Yamin Hossain"
#define MyAppURL "https://github.com/needyamin/media-downloader"
#ifndef MyAppExeName
#define MyAppExeName "Media-Downloader.exe"
#endif
#ifndef MyAppSourceDir
#define MyAppSourceDir "..\..\..\..\release\windows\media_download.dist"
#endif

[Setup]
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
Compression=lzma
SolidCompression=yes
SetupIconFile=..\assets\needyamin.ico
UninstallDisplayIcon={app}\needyamin.ico
WizardStyle=modern
OutputDir=..\..\..\..\release\windows
OutputBaseFilename=MediaDownloader_Setup
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "{cm:StartupDescription}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\needyamin.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\needyamin.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\needyamin.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Media Downloader"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[UninstallDelete]
; Fallback removal if [Code] DelTree is blocked; legacy profile paths are removed in uninstall_cleanup.iss
Type: filesandordirs; Name: "{localappdata}\Media Downloader"
Type: files; Name: "{tmp}\media_downloader_bg_remover_diagnostics.txt"

[CustomMessages]
StartupDescription=Start {#MyAppName} when Windows starts

#include "uninstall_cleanup.iss"
