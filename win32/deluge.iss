; Deluge installation script

#define AppName "Deluge"
#define VersionInfoSource "dist\deluge.exe"
#define AppVersion GetFileVersion(VersionInfoSource)
#define AppTextVersion GetFileVersionString(VersionInfoSource)
#define AppProductVersion GetFileProductVersion(VersionInfoSource)
#define AppProductTextVersion GetFileProductVersion(VersionInfoSource)
#define AppPublisher GetFileCompany(VersionInfoSource)
#define AppCopyright GetFileCopyright(VersionInfoSource)
#define AppHomepage "http://deluge-torrent.org"

[Setup]
AppID={{A95CCB3C-715C-4A39-A17E-43A6BE10B6D3}
AppName={#AppName}
AppVersion={#AppTextVersion}
AppCopyright={#AppCopyright}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppHomepage}
AppSupportURL={#AppHomepage}
AppUpdatesURL={#AppHomepage}
VersionInfoVersion={#AppVersion}
VersionInfoTextVersion={#AppTextVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoCopyright={#AppCopyright}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppProductVersion}
VersionInfoProductTextVersion={#AppProductTextVersion}
LicenseFile=..\LICENSE
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
SetupIconFile=files\deluge.ico
OutputDir=installer
OutputBaseFilename=deluge-{#AppTextVersion}-win32-setup
WizardImageFile=files\installer-side.bmp
WizardSmallImageFile=files\installer-top.bmp
Compression=lzma2/ultra
SolidCompression=true
AllowNoIcons=true
AppendDefaultGroupName=false
ChangesAssociations=true

[Files]
Source: files\IssProc.dll; DestDir: {tmp}; Flags: dontcopy
Source: files\IssProcLanguage.ini; DestDir: {tmp}; Flags: dontcopy
Source: files\vcredist_x86.exe; DestDir: {tmp}; Flags: dontcopy
Source: files\IssProc.dll; DestDir: {app}\uninst
Source: files\IssProcLanguage.ini; DestDir: {app}\uninst
Source: dist\*; DestDir: {app}; Flags: recursesubdirs

[Dirs]
Name: {localappdata}\Deluge

[Run]
Filename: file:vcredist_x86.exe; Parameters: /q; StatusMsg: Installing Mictosoft Visual C++ 2008 Redistributable...
Filename: {app}\deluge.exe; WorkingDir: {app}; Description: {cm:LaunchProgram,{#AppName}}; Flags: postinstall nowait skipifsilent

Filename: {app}\Deluge.exe; Description: {cm:LaunchProgram,Deluge}; Flags: nowait postinstall skipifsilent

[Tasks]
Name: desktopicon; Description: {cm:CreateDesktopIcon}
Name: quicklaunchicon; Description: {cm:CreateQuickLaunchIcon}
Name: fileassoc; Description: {cm:AssocFileExtension,Deluge,.torrent}
Name: urlassoc; Description: {cm:AssocUrlHandler,Deluge,magnet:}

[Icons]
Name: {group}\Deluge; Filename: {app}\deluge.exe; IconFilename: {app}\deluge.exe
Name: {group}\Deluge Daemon; Filename: {app}\deluged.exe; IconFilename: {app}\deluged.exe
Name: {group}\Deluge Console; Filename: {app}\deluge-consoleui.exe; IconFilename: {app}\deluge-consoleui.exe
Name: {group}\Deluge Web; Filename: {app}\deluge-webui.exe; IconFilename: {app}\deluge-webui.exe
Name: {group}\Uninstall Deluge; Filename: {uninstallexe}
Name: {userappdata}\Microsoft\Internet Explorer\Quick Launch\Deluge; Filename: {app}\deluge.exe; Tasks: quicklaunchicon
Name: {userdesktop}\Deluge; Filename: {app}\deluge.exe; Tasks: desktopicon

[Registry]
Root: HKCR; Subkey: {#AppName}; ValueType: string; ValueData: Deluge Bittorrent Client; Flags: uninsdeletekey
Root: HKCR; Subkey: {#AppName}\DefaultIcon; ValueType: string; ValueData: {app}\Deluge.exe,0
Root: HKCR; Subkey: {#AppName}\shell\open\command; ValueType: string; ValueData: """{app}\Deluge.exe"" ""%1"""
Root: HKCR; Subkey: .torrent; ValueType: string; ValueData: {#AppName}; Tasks: fileassoc
Root: HKCR; Subkey: magnet; ValueType: string; ValueData: URL:Magnet Protocol; Tasks: urlassoc
Root: HKCR; Subkey: magnet; ValueType: string; ValueName: URL Protocol; Flags: uninsdeletekey; Tasks: urlassoc
Root: HKCR; Subkey: magnet\DefaultIcon; ValueType: string; ValueData: {app}\Deluge.exe,0; Tasks: urlassoc
Root: HKCR; Subkey: magnet\shell\open\command; ValueType: string; ValueData: """{app}\Deluge.exe"" ""%1"""; Tasks: urlassoc

[CustomMessages]
AssocUrlHandler=Associate %1 with the %2 &protocol

[Languages]
Name: en; MessagesFile: compiler:Default.isl
Name: eu; MessagesFile: compiler:Languages\Basque.isl
Name: pt_BR; MessagesFile: compiler:Languages\BrazilianPortuguese.isl
Name: en; MessagesFile: compiler:Languages\Catalan.isl
Name: ca; MessagesFile: compiler:Languages\Czech.isl
Name: da; MessagesFile: compiler:Languages\Danish.isl
Name: nl; MessagesFile: compiler:Languages\Dutch.isl
Name: fi; MessagesFile: compiler:Languages\Finnish.isl
Name: fr; MessagesFile: compiler:Languages\French.isl
Name: de; MessagesFile: compiler:Languages\German.isl
Name: he; MessagesFile: compiler:Languages\Hebrew.isl
Name: hu; MessagesFile: compiler:Languages\Hungarian.isl
Name: it; MessagesFile: compiler:Languages\Italian.isl
Name: ja; MessagesFile: compiler:Languages\Japanese.isl
Name: no; MessagesFile: compiler:Languages\Norwegian.isl
Name: pl; MessagesFile: compiler:Languages\Polish.isl
Name: pt; MessagesFile: compiler:Languages\Portuguese.isl
Name: ru; MessagesFile: compiler:Languages\Russian.isl
Name: sk; MessagesFile: compiler:Languages\Slovak.isl
Name: sl; MessagesFile: compiler:Languages\Slovenian.isl
Name: es; MessagesFile: compiler:Languages\Spanish.isl

[Code]
// IssFindModule called on install
function IssFindModule(hWnd: Integer; Modulename: PAnsiChar; Language: PAnsiChar; Silent: Boolean; CanIgnore: Boolean): Integer;
external 'IssFindModule@files:IssProc.dll stdcall setuponly';

// IssFindModule called on uninstall
function IssFindModuleU(hWnd: Integer; Modulename: PAnsiChar; Language: PAnsiChar; Silent: Boolean; CanIgnore: Boolean): Integer;
external 'IssFindModule@{app}\uninst\IssProc.dll stdcall uninstallonly';

function NextButtonClick(CurPage: Integer): Boolean;
var
	hWnd: Integer;
	sModuleName: String;
	nCode: Integer;

begin
	Result := true;

	if CurPage = wpReady then begin
		Result := false;
		ExtractTemporaryFile('IssProcLanguage.ini');
		hWnd := StrToInt(ExpandConstant('{wizardhwnd}'));
		sModuleName := ExpandConstant('*deluge.exe;*deluged.exe;*deluge-webui.exe;*deluge-consoleui.exe;'); { searched modules. Tip: separate multiple modules with semicolon Ex: '*mymodule.dll;*mymodule2.dll;*myapp.exe'}

		{ search for module and display files-in-use window if found  }
		nCode := IssFindModule(hWnd, sModuleName, ExpandConstant('{language}'), false, true);

		{IssFindModule returns: 0 if no module found; 1 if cancel pressed; 2 if ignore pressed; -1 if an error occured }
		if nCode = 1 then begin
			{ cancel pressed or files-in-use window closed, quit setup, $0010=WM_CLOSE }
			PostMessage(WizardForm.Handle, $0010, 0, 0);
		end
		else if (nCode = 0) or (nCode = 2) then begin
			{ no module found or ignored pressed, continue setup }
			Result := true;
		end;
	end;
end;


function InitializeUninstall(): Boolean;
var
	sModuleName: String;
	nCode: Integer;

begin
    Result := false;
    sModuleName := ExpandConstant('*deluge.exe;*deluged.exe;*deluge-webui.exe;*deluge-consoleui.exe;');

    nCode := IssFindModuleU(0, sModuleName, ExpandConstant('{language}'), false, false);

    if (nCode = 0) or (nCode = 2) then begin
        Result := true;
    end;

    // Unload the extension, otherwise it will not be deleted by the uninstaller
    UnloadDLL(ExpandConstant('{app}\IssProc.dll'));
end;
