; Inno Setup script for PDF Toolkit — a friendly per-user Windows installer with
; Desktop + Start Menu shortcuts and an Add/Remove Programs entry. Compiled in CI.
;
; Expects packaging\staging\ to hold: PDFToolkit.exe, README.md, LICENSE,
; quickopen-root.crt (plus docs\ if present).

#define AppName "PDF Toolkit"
#define AppVersion "1.1.0"
#define AppPublisher "QuickOpen (quickopen.ai)"
#define AppURL "https://quickopen.ai/projects/pdf-toolkit"

[Setup]
AppMutex=QuickOpen.PDFToolkit
AppId={{B3D9A7C1-5E42-4F8A-9C2D-7A1E0B3C4D50}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\PDFToolkit
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\PDFToolkit.exe
; unins000.exe ships UNSIGNED by default, and on a machine with Smart App
; Control or a WDAC policy enforcing, Windows refuses to load it: the Uninstall
; button in Settings fails with CodeIntegrity 3077/3033 and WinError 4551,
; leaving the app impossible to remove through the normal route.
;
; Inno writes that binary on the USER'S machine at install time from a template
; baked into the installer, so no later signing hop can reach it - COMPILE time
; is the only moment it can be signed, which is what SignedUninstaller=yes does.
; That needs a SignTool where ISCC runs, so the ISCC step moved onto the signing
; machine (2026-08-21). ISCC signs uninst.e32, then the setup exe.
;
; Guarded by #ifdef so this same .iss still compiles anywhere without the token
; (CI, a laptop) - just unsigned. publish/scripts/compile-windows-installer.sh
; passes /DSIGNED_UNINSTALLER and defines the "quickopen" SignTool.
#ifdef SIGNED_UNINSTALLER
SignTool=quickopen
SignedUninstaller=yes
#endif
OutputDir=dist
OutputBaseFilename=PDFToolkit-Setup
SetupIconFile=..\pdf-toolkit.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=branding\wizard-large.bmp
WizardSmallImageFile=branding\wizard-small.bmp
AppCopyright=Apache-2.0. 100%% AI-built, published on QuickOpen (quickopen.ai).
VersionInfoCompany=QuickOpen
VersionInfoProductName=PDF Toolkit
VersionInfoVersion=1.1.0.0
; Install per-user by default (no admin needed).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=PDF Toolkit is a 100%% AI-built, open-source offline PDF utility, published on QuickOpen (quickopen.ai).%n%nThis will install it on your computer.
BeveledLabel=QuickOpen · quickopen.ai

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "trustca"; Description: "Trust the QuickOpen Root CA (lets Windows verify QuickOpen signatures)"; GroupDescription: "Security:"; Flags: unchecked

[Files]
Source: "staging\PDFToolkit.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\quickopen-root.crt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "staging\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme skipifsourcedoesntexist
Source: "staging\LICENSE"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "staging\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\PDF Toolkit"; Filename: "{app}\PDFToolkit.exe"; IconFilename: "{app}\PDFToolkit.exe"
Name: "{group}\Uninstall PDF Toolkit"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PDF Toolkit"; Filename: "{app}\PDFToolkit.exe"; IconFilename: "{app}\PDFToolkit.exe"; Tasks: desktopicon

[Run]
Filename: "certutil.exe"; Parameters: "-addstore -user Root ""{app}\quickopen-root.crt"""; Tasks: trustca; Flags: runhidden; StatusMsg: "Trusting the QuickOpen Root CA..."
Filename: "{app}\PDFToolkit.exe"; Description: "Launch PDF Toolkit now"; Flags: nowait postinstall skipifsilent

; Fully clean uninstall: remove the runtime config + recent-files folder that the
; app writes outside {app} (Inno only tracks files it installed).
[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\PDFToolkit"

[Code]
// On uninstall, offer to also remove the QuickOpen Root CA. Default No, because
// other QuickOpen apps on this machine may rely on it — this is opt-in, matching
// how the installer only adds it with consent.
