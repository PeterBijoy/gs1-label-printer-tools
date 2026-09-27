; Inno Setup script for SSCC Label Printer
; Build with: iscc installer.iss  (or open in the Inno Setup Compiler GUI)
;
; NOTE: build.bat now builds in PyInstaller's --onedir mode, so "dist\SSCCLabelPrinter"
; is a FOLDER (the exe plus its supporting files), not a single portable exe.
; The [Files] section below packages that whole folder.

#define MyAppName "SSCC Label Printer"
#define MyAppExeName "SSCCLabelPrinter.exe"
#define MyAppVersion "1.0"
#define MyAppPublisher "GS1 India"

[Setup]
AppId={{C7D3F2C1-A02C-4C8D-9C1B-SSCCLABELPRINTER}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=SSCCLabelPrinter_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; --onedir output: package the whole folder produced by PyInstaller.
Source: "dist\SSCCLabelPrinter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
