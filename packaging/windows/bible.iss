; Windows installer for `bible` - an Inno Setup script.
;
; Wraps the standalone Nuitka-built bible.exe in a normal double-click
; installer: no admin prompt (it's a per-user install into
; %LOCALAPPDATA%\Programs\Bible), a Start menu entry, `bible` on the user
; PATH so it works from any terminal, and a clean uninstall from
; Settings > Apps. Reading data in %APPDATA%\bible-tui is left alone on
; uninstall, the same as every other app's user data.
;
; Built in CI by .github/workflows/build.yml, or locally by
; packaging/build_windows.ps1:
;   iscc /DAppVersion=1.2.3 /DSourceExe=C:\path\to\bible.exe packaging\windows\bible.iss

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef SourceExe
  #define SourceExe "..\..\dist\windows\bible.exe"
#endif

[Setup]
; Never change AppId - it's how an upgrade finds the existing install.
AppId={{75723362-754F-4572-A61F-4121B23D2F58}
AppName=Bible
AppVersion={#AppVersion}
AppPublisher=ginnfx
AppPublisherURL=https://github.com/ginnfx/bible
AppSupportURL=https://github.com/ginnfx/bible/issues
DefaultDirName={autopf}\Bible
DefaultGroupName=Bible
; Fewest possible clicks: no folder pickers, straight to Install.
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ChangesEnvironment=yes
UninstallDisplayIcon={app}\bible.exe
UninstallDisplayName=Bible
OutputDir=..\..\dist\windows
OutputBaseFilename=bible-windows-x86_64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "bible.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Bible"; Filename: "{app}\bible.exe"; Comment: "Read the Bible in your terminal"
Name: "{autodesktop}\Bible"; Filename: "{app}\bible.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\bible.exe"; Description: "Open Bible now"; Flags: nowait postinstall skipifsilent

[Code]
const
  EnvironmentKey = 'Environment';

{ Case-insensitive whole-entry match, so C:\Foo doesn't match C:\Foobar. }
function PathHasEntry(Paths, Dir: string): Boolean;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0;
end;

procedure AddToUserPath(Dir: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, EnvironmentKey, 'Path', Paths) then
    Paths := '';
  if PathHasEntry(Paths, Dir) then
    exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then
    Paths := Paths + ';';
  RegWriteExpandStringValue(HKCU, EnvironmentKey, 'Path', Paths + Dir);
end;

procedure RemoveFromUserPath(Dir: string);
var
  Paths: string;
  Index: Integer;
begin
  if not RegQueryStringValue(HKCU, EnvironmentKey, 'Path', Paths) then
    exit;
  { Wrap in sentinels so the first and last entries match like the rest. }
  Paths := ';' + Paths + ';';
  Index := Pos(';' + Uppercase(Dir) + ';', Uppercase(Paths));
  if Index = 0 then
    exit;
  Delete(Paths, Index, Length(Dir) + 1);
  RegWriteExpandStringValue(HKCU, EnvironmentKey, 'Path', Copy(Paths, 2, Length(Paths) - 2));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddToUserPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromUserPath(ExpandConstant('{app}'));
end;
