#define AppName      "SIA Reporte Mensual"
#define AppExeName   "SIA_Reporte_Mensual.exe"
#define AppPublisher "INICA - Autoridad del Canal de Panama"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Cambia este GUID solo si necesitas que se trate como una aplicacion diferente
AppId={{7C3E1B4A-9D2F-4861-A5C3-8F0E27D4B956}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppVerName={#AppName} {#AppVersion}

; Instalacion sin privilegios de administrador
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Ruta de instalacion en el perfil del usuario
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Salida
OutputDir=Output
OutputBaseFilename=SIA_Reporte_Mensual_Setup_{#AppVersion}
SetupIconFile=assets\icon.ico

; Compresion
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Ejecutable y todas sus dependencias (generadas por PyInstaller --onedir)
Source: "dist\SIA_Reporte_Mensual\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; Plantilla de credenciales
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";     Filename: "{app}\{#AppExeName}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "Ejecutar {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[Code]
// Crea .env desde .env.example en la primera instalacion
procedure CurStepChanged(CurStep: TSetupStep);
var
  envExample, envFile: string;
begin
  if CurStep = ssPostInstall then
  begin
    envExample := ExpandConstant('{app}\.env.example');
    envFile    := ExpandConstant('{app}\.env');
    if FileExists(envExample) and not FileExists(envFile) then
      FileCopy(envExample, envFile, False);
  end;
end;
