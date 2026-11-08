<#
Exporta el ensamble de SolidWorks a STL, una pieza por archivo, en su posicion del ensamble.

Hace lo mismo que el paso 4.2 de PROCESO.md (Guardar como -> STL) con las mismas opciones:
binario, milimetros, desviacion 0.16 mm, angulo 10 grados, sin "espacio positivo" y sin juntar
todo en un archivo. Al terminar deja las preferencias de SolidWorks como estaban.

No modifica el ensamble: se abre, se exporta y se cierra sin guardar.

SolidWorks no exporta las piezas ocultas (en el CAD, CLM-Body esta oculto para ver adentro).
Con -IncluirOcultas se muestran solo en memoria antes de exportar.

Ejemplo (PowerShell, desde la carpeta del paquete):
  powershell -ExecutionPolicy Bypass -File tools\export_stl_solidworks.ps1 `
      -Assembly C:\Cad_colmibot2\CAD_Colmibot\CLM-EnsambleColmibot.SLDASM `
      -OutDir C:\Cad_colmibot2\stl_cad_actual -IncluirOcultas
#>
param(
    [Parameter(Mandatory = $true)][string]$Assembly,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [switch]$IncluirOcultas
)
$ErrorActionPreference = 'Stop'

# PowerShell no puede usar la biblioteca de tipos de SolidWorks: se llama todo por reflexion.
# Los argumentos van con su tipo explicito ([int], [bool]...): si no, COM responde "los tipos no coinciden".
function Get-P($o, $n) { [System.__ComObject].InvokeMember($n, [Reflection.BindingFlags]::GetProperty, $null, $o, $null) }
function Call($o, $n, $a) { [System.__ComObject].InvokeMember($n, [Reflection.BindingFlags]::InvokeMethod, $null, $o, $a) }

# Preferencias de STL: (tipo, id de SolidWorks.Interop.swconst, valor)
$PREFS = @(
    @('Toggle', 69, $true),                     # swSTLBinaryFormat
    @('Toggle', 70, $false),                    # swSTLShowInfoOnSave (sin ventanas)
    @('Toggle', 71, $true),                     # swSTLDontTranslateToPositive
    @('Toggle', 72, $false),                    # swSTLComponentsIntoOneFile
    @('IntegerValue', 211, 0),                  # swExportStlUnits = swMM
    @('IntegerValue', 78, 3),                   # swSTLQuality = swSTLQuality_Custom
    @('DoubleValue', 2, 0.00016),               # swSTLDeviation (m)
    @('DoubleValue', 3, (10 * [Math]::PI / 180))  # swSTLAngleTolerance (rad)
)
function Typed($kind, $v) { switch ($kind) { 'Toggle' { [bool]$v } 'IntegerValue' { [int]$v } default { [double]$v } } }

$Assembly = (Resolve-Path $Assembly).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
if (Get-ChildItem $OutDir -Filter *.stl) { throw "$OutDir ya tiene archivos STL: usar una carpeta vacia" }

$sw = [Activator]::CreateInstance([type]::GetTypeFromProgID('SldWorks.Application'))
Write-Host "SolidWorks $(Call $sw 'RevisionNumber' $null)"

$old = foreach ($p in $PREFS) { Call $sw "GetUserPreference$($p[0])" @([int]$p[1]) }
try {
    foreach ($p in $PREFS) { Call $sw "SetUserPreference$($p[0])" @([int]$p[1], (Typed $p[0] $p[2])) | Out-Null }
    $asm = Call $sw 'OpenDoc' @([string]$Assembly, [int]2)   # 2 = swDocASSEMBLY
    if (-not $asm) { throw "No se pudo abrir $Assembly" }
    Call $asm 'ResolveAllLightWeightComponents' @($false) | Out-Null
    foreach ($c in @(Call $asm 'GetComponents' @($false))) {
        if ((Get-P $c 'Visible') -eq 0 -and -not (Call $c 'IsSuppressed' $null)) {
            if ($IncluirOcultas) {
                [System.__ComObject].InvokeMember('Visible', [Reflection.BindingFlags]::SetProperty, $null, $c, @([int]1))
                Write-Host "  oculta -> se muestra para exportar: $(Get-P $c 'Name2')"
            } else {
                Write-Warning "$(Get-P $c 'Name2') esta oculta y no se exporta (usar -IncluirOcultas)"
            }
        }
    }
    Write-Host 'Exportando (puede tardar)...'
    # Con piezas separadas, SolidWorks crea "<ensamble> - <componente>.STL" en la carpeta de $target
    $target = Join-Path $OutDir ([IO.Path]::GetFileNameWithoutExtension($Assembly) + '.STL')
    $err = Call $asm 'SaveAs3' @([string]$target, [int]0, [int]1)   # version actual, silencioso
    Call $sw 'CloseDoc' @([string](Call $asm 'GetTitle' $null)) | Out-Null
    if ($err -ne 0) { throw "SaveAs3 devolvio el error $err" }
}
finally {
    for ($i = 0; $i -lt $PREFS.Count; $i++) {
        $p = $PREFS[$i]
        Call $sw "SetUserPreference$($p[0])" @([int]$p[1], (Typed $p[0] $old[$i])) | Out-Null
    }
    Write-Host 'Preferencias de SolidWorks restauradas'
}
$n = @(Get-ChildItem $OutDir -Filter *.stl).Count
Write-Host "STL exportados: $n  ->  $OutDir"
