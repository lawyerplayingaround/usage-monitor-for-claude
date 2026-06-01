; ============================================================================
;  Usage Monitor for Claude - Inno Setup installer script
; ============================================================================
;
;  Recommended invocation (via build_installer.ps1):
;      ISCC /DPayloadDir=<abs path> /DOutputDirOverride=<abs out> setup.iss
;
;  /D defines override PayloadDir and OutputDirOverride at compile time so
;  build artefacts can live outside the repo.  Without overrides, ISCC
;  falls back to "payload\" and "dist\" relative to this .iss (useful for
;  one-off manual compiles).
;
;  Resulting installer:
;    - Per-user install, no admin rights, no UAC prompt.
;    - Default install dir: %LOCALAPPDATA%\UsageMonitorForClaude
;    - Optional tasks: Autostart with Windows, Desktop shortcut.
;    - Start Menu shortcut + uninstaller entry created by default.
;    - Pre-install check warns (non-blocking) if ~/.claude/.credentials.json
;      is missing, so the user knows they need to log in to Claude Code.
;    - Stops a running UsageMonitorForClaude.exe before uninstalling.
;    - Registers in Add/Remove Programs (uninstall via Windows UI).
;
;  The AppId GUID below identifies the product; keep it stable across
;  versions so Inno Setup detects upgrades vs fresh installs.
; ============================================================================

#define MyAppName "Usage Monitor for Claude"
#define MyAppVersion "1.15.1-fork.win.5"
#define MyAppPublisher "lawyerplayingaround"
#define MyAppURL "https://github.com/lawyerplayingaround/usage-monitor-for-claude"
#define MyAppExeName "UsageMonitorForClaude.exe"

; Override on the CLI with /DPayloadDir=... and /DOutputDirOverride=...
#ifndef PayloadDir
  #define PayloadDir "payload"
#endif
#ifndef OutputDirOverride
  #define OutputDirOverride "dist"
#endif

[Setup]
AppId={{15543282-AED1-4076-B1FA-8842AFAD022A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

DefaultDirName={localappdata}\UsageMonitorForClaude
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=

OutputDir={#OutputDirOverride}
OutputBaseFilename=UsageMonitorForClaude-Setup-v{#MyAppVersion}
SetupIconFile=..\usage_monitor_for_claude.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile={#PayloadDir}\LICENSE.txt

ShowLanguageDialog=auto
DisableWelcomePage=no

; Minimum Windows version - PyInstaller bundles need at least Windows 10.
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart";   Description: "Start with Windows";        GroupDescription: "Startup:"
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";             Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";   Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Autostart on login. uninsdeletevalue removes it on uninstall.  Quoting
; the path handles spaces in the install directory.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "UsageMonitorForClaude"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start the monitor now"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop a running instance so its EXE is not locked when files are removed.
; runhidden keeps taskkill silent; the RunOnceId ensures it only runs once.
Filename: "taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; \
  Flags: runhidden; RunOnceId: "KillMonitor"

[Code]
{
  Pre-install check: warn (but do not block) if Claude Code credentials
  are missing. The user can still proceed; the monitor will show an
  error icon until Claude Code is set up.
}
function InitializeSetup(): Boolean;
var
  CredPath: String;
  Choice: Integer;
begin
  Result := True;
  // Inno Setup has no built-in USERPROFILE constant - read the env var.
  // GetEnv returns '' if the variable is undefined; in that case we
  // simply skip the credential check (no false positive).
  if GetEnv('USERPROFILE') = '' then
    Exit;
  CredPath := GetEnv('USERPROFILE') + '\.claude\.credentials.json';
  if not FileExists(CredPath) then begin
    Choice := MsgBox(
      'Claude Code credentials not found at:' + #13#10 +
      '  ' + CredPath + #13#10 + #13#10 +
      'Without this file, the monitor will show an error icon (it cannot' + #13#10 +
      'query usage). To fix it:' + #13#10 +
      '  1. Install Claude Code: https://claude.ai/download' + #13#10 +
      '  2. Open a terminal and run: claude' + #13#10 +
      '  3. Log in. The credentials file is created automatically.' + #13#10 + #13#10 +
      'Continue installation anyway?',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
    if Choice = IDNO then
      Result := False;
  end;
end;
