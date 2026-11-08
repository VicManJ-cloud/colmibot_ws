<#
Exporta las propiedades fisicas de cada pieza del ensamble de SolidWorks a un CSV.

Que hace:
  1. Abre CLM-EnsambleColmibot.SLDASM en SolidWorks (necesita SolidWorks instalado).
  2. Recorre todas las piezas, tambien las que estan dentro de subensambles.
     Junta en un componente cada instancia de un archivo de la carpeta del CAD
     (lo que lista el BOM): la Raspberry Pi y su cooler, que traen piezas sin
     archivo propio (importadas de STEP), quedan como un componente cada uno.
  3. De cada componente guarda: material, densidad, masa, volumen, centro de masa,
     tensor de inercia y caja envolvente, todo en coordenadas del ensamble
     (metros, kg, kg*m2; ejes del CAD, sin girar a ROS).
  4. Escribe inertia/componentes_cad.csv.

El CSV guarda la informacion fisica de TODAS las piezas, aunque despues se
quiten de las mallas visuales. tools/compute_inertial.py lo convierte a ROS.

Ejemplo (PowerShell, desde la carpeta del paquete):
  powershell -ExecutionPolicy Bypass -File tools\export_mass_solidworks.ps1 `
      -Assembly C:\Cad_colmibot2\CAD_Colmibot\CLM-EnsambleColmibot.SLDASM
#>
param(
    [Parameter(Mandatory = $true)][string]$Assembly,
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
# En PowerShell 5.1, $PSScriptRoot aun no existe dentro de param()
if (-not $Out) { $Out = Join-Path $PSScriptRoot '..\inertia\componentes_cad.csv' }
$inv = [Globalization.CultureInfo]::InvariantCulture

# PowerShell no puede usar la biblioteca de tipos de SolidWorks: se llama todo por reflexion.
function Get-P($o, $n) { [System.__ComObject].InvokeMember($n, [Reflection.BindingFlags]::GetProperty, $null, $o, $null) }
function Call($o, $n, $a) { [System.__ComObject].InvokeMember($n, [Reflection.BindingFlags]::InvokeMethod, $null, $o, $a) }
function F($x) { ([double]$x).ToString('G9', $inv) }

$Assembly = (Resolve-Path $Assembly).Path
$sw = [Activator]::CreateInstance([type]::GetTypeFromProgID('SldWorks.Application'))
Write-Host "SolidWorks $(Call $sw 'RevisionNumber' $null)"

$asm = Call $sw 'OpenDoc' @($Assembly, 2)   # 2 = swDocASSEMBLY
if (-not $asm) { throw "No se pudo abrir $Assembly" }
Call $asm 'ResolveAllLightWeightComponents' @($false) | Out-Null

# Propiedades fisicas por archivo de pieza (en el sistema de la pieza), una sola vez por archivo
$cache = @{}
function Get-PartProps($partDoc, $path) {
    if ($cache.ContainsKey($path)) { return $cache[$path] }
    $mp = Call (Get-P $partDoc 'Extension') 'CreateMassProperty' $null
    $mat = Get-P $partDoc 'MaterialIdName'
    $r = [ordered]@{
        material = if ($mat) { ($mat -split '\|')[1] } else { '' }
        density  = Get-P $mp 'Density'
        mass     = Get-P $mp 'Mass'
        volume   = Get-P $mp 'Volume'
        com      = Get-P $mp 'CenterOfMass'
        inertia  = Call $mp 'GetMomentOfInertia' @(0)   # 0 = en el centro de masa, ejes de la pieza
    }
    $cache[$path] = $r
    return $r
}

# Un "componente" es cada instancia de un archivo que esta en la carpeta del CAD
# (lo que lista el BOM). Las piezas que no tienen archivo propio, como las que
# trae el STEP importado de la Raspberry Pi y su cooler, se suman a su subensamble.
$cadDir = Split-Path $Assembly
$parts = New-Object System.Collections.Generic.List[object]

function Walk($comp, $route, $owner) {
    foreach ($ch in @(Call $comp 'GetChildren' $null)) {
        if (-not $ch) { continue }
        if (Call $ch 'IsSuppressed' $null) { continue }
        if (Call $ch 'IsEnvelope' $null) { continue }
        $short = ((Get-P $ch 'Name2') -split '/')[-1]
        $ruta = if ($route) { "$route/$short" } else { $short }
        $doc = Call $ch 'GetModelDoc2' $null
        if (-not $doc) { Write-Warning "$ruta sin documento cargado, se omite"; continue }
        $path = Call $doc 'GetPathName' $null
        $own = $owner
        if ($path -and (Split-Path $path) -eq $cadDir) {
            $own = @{ name = $short; ruta = $ruta; file = [IO.Path]::GetFileName($path) }
        }
        if ((Call $doc 'GetType' $null) -eq 2) { Walk $ch $ruta $own; continue }   # subensamble

        $p = Get-PartProps $doc $path
        # Transform2.ArrayData: [0..8] rotacion R, [9..11] traslacion t, [12] escala.
        # SolidWorks usa vectores fila: p_ensamble = p_pieza * R + t
        # (ojo: en PowerShell $R y $r serian la misma variable)
        $t = Get-P (Get-P $ch 'Transform2') 'ArrayData'
        $R = @(@($t[0], $t[1], $t[2]), @($t[3], $t[4], $t[5]), @($t[6], $t[7], $t[8]))
        $c = $p.com
        $com = 0..2 | ForEach-Object { $c[0] * $R[0][$_] + $c[1] * $R[1][$_] + $c[2] * $R[2][$_] + $t[9 + $_] }
        # I_ensamble = R^T * I_pieza * R
        # SolidWorks da los productos de inercia como +integral(xy dm); el tensor de inercia
        # (lo que usa el URDF) lleva -integral(xy dm). Se cambia el signo ANTES de girar.
        $I = $p.inertia
        $Ip = @(@($I[0], -$I[1], -$I[2]), @(-$I[3], $I[4], -$I[5]), @(-$I[6], -$I[7], $I[8]))
        $Ia = @(@(0, 0, 0), @(0, 0, 0), @(0, 0, 0))
        foreach ($a in 0..2) { foreach ($b in 0..2) {
            $s = 0.0
            foreach ($k in 0..2) { foreach ($l in 0..2) { $s += $R[$k][$a] * $Ip[$k][$l] * $R[$l][$b] } }
            $Ia[$a][$b] = $s
        } }
        $parts.Add([pscustomobject]@{ owner = $own; material = $p.material; mass = [double]$p.mass; volume = [double]$p.volume
                      com = $com; I = $Ia; box = @(Call $ch 'GetBox' @($false, $false)) })
    }
}

$root = Call (Get-P (Get-P $asm 'ConfigurationManager') 'ActiveConfiguration') 'GetRootComponent3' @($true)
Walk $root '' $null

$rows = New-Object System.Collections.Generic.List[string]
$rows.Add('componente,ruta,archivo,piezas_internas,material,densidad,masa_kg,volumen_m3,com_x,com_y,com_z,' +
          'ixx,ixy,ixz,iyy,iyz,izz,box_min_x,box_min_y,box_min_z,box_max_x,box_max_y,box_max_z')
foreach ($g in ($parts | Group-Object { $_.owner.ruta })) {
    $ps = @($g.Group); $o = $ps[0].owner
    $m = ($ps | Measure-Object mass -Sum).Sum
    $v = ($ps | Measure-Object volume -Sum).Sum
    $com = 0..2 | ForEach-Object { $k = $_; ($ps | ForEach-Object { $_.mass * $_.com[$k] } | Measure-Object -Sum).Sum / $m }
    # Teorema de ejes paralelos: I = suma(I_i + m_i (|d|^2 E - d d^T)), d = com_i - com
    $Ic = @(@(0.0, 0.0, 0.0), @(0.0, 0.0, 0.0), @(0.0, 0.0, 0.0))
    foreach ($q in $ps) {
        $d = 0..2 | ForEach-Object { $q.com[$_] - $com[$_] }
        $dd = $d[0] * $d[0] + $d[1] * $d[1] + $d[2] * $d[2]
        foreach ($a in 0..2) { foreach ($b in 0..2) {
            $Ic[$a][$b] += $q.I[$a][$b] + $q.mass * ($(if ($a -eq $b) { $dd } else { 0 }) - $d[$a] * $d[$b])
        } }
    }
    $box = @((0..2 | ForEach-Object { $k = $_; ($ps | ForEach-Object { $_.box[$k] } | Measure-Object -Minimum).Minimum }) +
             (3..5 | ForEach-Object { $k = $_; ($ps | ForEach-Object { $_.box[$k] } | Measure-Object -Maximum).Maximum }))
    $mats = @($ps | ForEach-Object { if ($_.material) { $_.material } else { '(sin material)' } } | Sort-Object -Unique)
    $mat = if ($mats.Count -eq 1) { $mats[0] } else { 'varios: ' + ($mats -join ' + ') }
    $txt = @($o.name, $o.ruta, $o.file, $ps.Count, $mat) | ForEach-Object { '"' + ("$_" -replace '"', '""') + '"' }
    $vals = @($(if ($v) { $m / $v } else { 0 }), $m, $v) + $com +
            @($Ic[0][0], $Ic[0][1], $Ic[0][2], $Ic[1][1], $Ic[1][2], $Ic[2][2]) + $box
    $rows.Add((@($txt) + ($vals | ForEach-Object { F $_ })) -join ',')
}

# Comprobacion: lo que SolidWorks calcula para el ensamble completo
$mp = Call (Get-P $asm 'Extension') 'CreateMassProperty' $null
$tc = Get-P $mp 'CenterOfMass'
$rows.Add("# total_solidworks masa_kg=$(F (Get-P $mp 'Mass')) com=$(F $tc[0]) $(F $tc[1]) $(F $tc[2])")

$Out = [IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
[IO.File]::WriteAllLines($Out, $rows, (New-Object Text.UTF8Encoding $false))
Write-Host "Piezas: $($parts.Count)  ->  componentes: $($rows.Count - 2)  ->  $Out"
Write-Host "Total segun SolidWorks: $(F (Get-P $mp 'Mass')) kg"
Call $sw 'CloseDoc' @((Call $asm 'GetTitle' $null)) | Out-Null
