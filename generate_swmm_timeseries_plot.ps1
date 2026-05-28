$ErrorActionPreference = "Stop"

$inputFile = "O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM\Discharge_Input_SWMM.txt"
$outputFile = "O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM\Discharge_Input_SWMM_plot.html"

$culture = [Globalization.CultureInfo]::InvariantCulture
$rows = New-Object System.Collections.Generic.List[object]

foreach ($line in [System.IO.File]::ReadLines($inputFile, [System.Text.Encoding]::Default)) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }

    $parts = $line -split "`t"
    if ($parts.Count -lt 2) {
        $parts = $line -split "\s+", 3
        $dateText = "$($parts[0]) $($parts[1])"
        $valueText = $parts[2]
    }
    else {
        $dateText = $parts[0]
        $valueText = $parts[1]
    }

    $date = [datetime]::ParseExact($dateText, "MM/dd/yyyy HH:mm", $culture)
    $value = [double]::Parse($valueText, $culture)
    $rows.Add([pscustomobject]@{ Date = $date; Value = $value })
}

if ($rows.Count -eq 0) {
    throw "Aucune donnee lue dans $inputFile"
}

$rows = $rows | Sort-Object Date
$start = $rows[0].Date
$end = $rows[$rows.Count - 1].Date
$minQ = ($rows | Measure-Object -Property Value -Minimum).Minimum
$maxQ = ($rows | Measure-Object -Property Value -Maximum).Maximum
$rangeQ = [Math]::Max($maxQ - $minQ, 0.000001)

$gaps = New-Object System.Collections.Generic.List[object]
for ($i = 1; $i -lt $rows.Count; $i++) {
    $previous = $rows[$i - 1].Date
    $current = $rows[$i].Date
    $missingHours = [int](($current - $previous).TotalHours) - 1
    if ($missingHours -gt 0) {
        $gaps.Add([pscustomobject]@{
            Start = $previous.AddHours(1)
            End = $current.AddHours(-1)
            Hours = $missingHours
        })
    }
}

$width = 1600
$height = 900
$left = 95
$right = 35
$top = 60
$bottom = 115
$plotWidth = $width - $left - $right
$plotHeight = $height - $top - $bottom
$totalSeconds = [Math]::Max(($end - $start).TotalSeconds, 1)

function Get-X {
    param([datetime]$Date)
    return $left + (($Date - $start).TotalSeconds / $totalSeconds) * $plotWidth
}

function Get-Y {
    param([double]$Value)
    return $top + (($maxQ - $Value) / $rangeQ) * $plotHeight
}

function Html-Escape {
    param([string]$Text)
    return [System.Net.WebUtility]::HtmlEncode($Text)
}

$segments = New-Object System.Collections.Generic.List[string]
$currentSegment = New-Object System.Collections.Generic.List[string]

for ($i = 0; $i -lt $rows.Count; $i++) {
    if ($i -gt 0 -and (($rows[$i].Date - $rows[$i - 1].Date).TotalHours -gt 1.1)) {
        if ($currentSegment.Count -gt 1) {
            $segments.Add("M " + ($currentSegment -join " L "))
        }
        $currentSegment = New-Object System.Collections.Generic.List[string]
    }

    $x = [Math]::Round((Get-X $rows[$i].Date), 2)
    $y = [Math]::Round((Get-Y $rows[$i].Value), 2)
    $currentSegment.Add("$x $y")
}

if ($currentSegment.Count -gt 1) {
    $segments.Add("M " + ($currentSegment -join " L "))
}

$gapRects = foreach ($gap in $gaps) {
    $x1 = [Math]::Round((Get-X $gap.Start), 2)
    $x2 = [Math]::Round((Get-X $gap.End.AddHours(1)), 2)
    $w = [Math]::Max([Math]::Round($x2 - $x1, 2), 1)
    "<rect x=""$x1"" y=""$top"" width=""$w"" height=""$plotHeight"" fill=""#d62828"" opacity=""0.18""><title>Lacune: $($gap.Start.ToString('yyyy-MM-dd HH:mm')) - $($gap.End.ToString('yyyy-MM-dd HH:mm')) ($($gap.Hours) h)</title></rect>"
}

$pathElements = foreach ($segment in $segments) {
    "<path d=""$segment"" fill=""none"" stroke=""#1f6feb"" stroke-width=""1.4"" stroke-linejoin=""round"" stroke-linecap=""round"" />"
}

$xTicks = 8
$xTickElements = for ($i = 0; $i -le $xTicks; $i++) {
    $date = $start.AddSeconds($totalSeconds * $i / $xTicks)
    $x = [Math]::Round((Get-X $date), 2)
    $label = $date.ToString("yyyy-MM")
    "<line x1=""$x"" y1=""$top"" x2=""$x"" y2=""$($top + $plotHeight)"" stroke=""#e5e7eb"" /><text x=""$x"" y=""$($top + $plotHeight + 32)"" text-anchor=""middle"">$label</text>"
}

$yTicks = 6
$yTickElements = for ($i = 0; $i -le $yTicks; $i++) {
    $value = $minQ + ($rangeQ * $i / $yTicks)
    $y = [Math]::Round((Get-Y $value), 2)
    $label = $value.ToString("0.###", $culture)
    "<line x1=""$left"" y1=""$y"" x2=""$($left + $plotWidth)"" y2=""$y"" stroke=""#e5e7eb"" /><text x=""$($left - 12)"" y=""$($y + 4)"" text-anchor=""end"">$label</text>"
}

$gapTableRows = if ($gaps.Count -eq 0) {
    "<tr><td colspan=""3"">Aucune lacune detectee dans la time series.</td></tr>"
}
else {
    foreach ($gap in $gaps) {
        "<tr><td>$($gap.Start.ToString('yyyy-MM-dd HH:mm'))</td><td>$($gap.End.ToString('yyyy-MM-dd HH:mm'))</td><td>$($gap.Hours)</td></tr>"
    }
}

$summary = @(
    "Fichier source: $(Html-Escape $inputFile)"
    "Periode tracee: $($start.ToString('yyyy-MM-dd HH:mm')) - $($end.ToString('yyyy-MM-dd HH:mm'))"
    "Nombre de valeurs: $($rows.Count)"
    "Nombre de lacunes: $($gaps.Count)"
) -join "<br>"

$html = @"
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Discharge Input SWMM - Time Series</title>
<style>
body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #172033; background: #f7f8fb; }
main { max-width: 1720px; margin: 0 auto; padding: 28px 34px 44px; }
h1 { margin: 0 0 8px; font-size: 24px; font-weight: 700; }
.meta { margin-bottom: 18px; line-height: 1.5; color: #4b5563; font-size: 14px; }
.figure { background: white; border: 1px solid #d9dee8; border-radius: 8px; padding: 18px; }
svg { width: 100%; height: auto; display: block; }
.axis text, text { font-size: 14px; fill: #374151; }
.axis-title { font-size: 16px; font-weight: 700; fill: #172033; }
.legend { display: flex; gap: 24px; align-items: center; margin: 14px 0 4px; color: #374151; font-size: 14px; }
.swatch { width: 34px; height: 12px; display: inline-block; margin-right: 8px; vertical-align: -1px; }
table { width: 100%; border-collapse: collapse; margin-top: 18px; background: white; border: 1px solid #d9dee8; }
th, td { padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 13px; }
th { background: #eef2f7; }
</style>
</head>
<body>
<main>
<h1>Discharge_Input_SWMM - Time series</h1>
<div class="meta">$summary</div>
<div class="figure">
<svg viewBox="0 0 $width $height" role="img" aria-label="Time series SWMM avec lacunes">
<rect x="0" y="0" width="$width" height="$height" fill="#ffffff" />
<g class="axis">
$($xTickElements -join "`n")
$($yTickElements -join "`n")
<line x1="$left" y1="$top" x2="$left" y2="$($top + $plotHeight)" stroke="#172033" stroke-width="1.2" />
<line x1="$left" y1="$($top + $plotHeight)" x2="$($left + $plotWidth)" y2="$($top + $plotHeight)" stroke="#172033" stroke-width="1.2" />
<text class="axis-title" x="$($left + $plotWidth / 2)" y="$($height - 35)" text-anchor="middle">Date</text>
<text class="axis-title" x="24" y="$($top + $plotHeight / 2)" transform="rotate(-90 24 $($top + $plotHeight / 2))" text-anchor="middle">Debit [m3/s]</text>
</g>
<g>
$($gapRects -join "`n")
</g>
<g>
$($pathElements -join "`n")
</g>
</svg>
<div class="legend">
<span><span class="swatch" style="background:#1f6feb"></span>Debit combine</span>
<span><span class="swatch" style="background:#d62828; opacity:.35"></span>Plage de lacune</span>
</div>
</div>
<table>
<thead><tr><th>Debut lacune</th><th>Fin lacune</th><th>Duree [h]</th></tr></thead>
<tbody>
$($gapTableRows -join "`n")
</tbody>
</table>
</main>
</body>
</html>
"@

[System.IO.File]::WriteAllText($outputFile, $html, [System.Text.Encoding]::UTF8)
Write-Host "OUTPUT`t$outputFile"
Write-Host "ROWS`t$($rows.Count)"
Write-Host "GAPS`t$($gaps.Count)"
