#define MyAppName "Media Downloader"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Md Yamin Hossain"
#define MyAppURL "https://github.com/needyamin/media-downloader"
#define MyAppExeName "Media-Downloader.exe"

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
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
OutputDir=..\..\..\..\release\windows
OutputBaseFilename=MediaDownloader_Setup
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startupicon"; Description: "{cm:StartupDescription}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\..\..\release\windows\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\needyamin.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Media Downloader"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[CustomMessages]
StartupDescription=Start {#MyAppName} when Windows starts
