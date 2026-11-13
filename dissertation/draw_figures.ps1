Add-Type -AssemblyName System.Drawing
$dir = Join-Path $PSScriptRoot "FIGURES"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$navy = [System.Drawing.Color]::FromArgb(31, 78, 121)
$pale = [System.Drawing.Color]::FromArgb(231, 238, 245)
$warm = [System.Drawing.Color]::FromArgb(255, 243, 224)
$green = [System.Drawing.Color]::FromArgb(226, 240, 230)
$font = New-Object System.Drawing.Font("Times New Roman", 16)
$pen = New-Object System.Drawing.Pen($navy, 2)

function New-Canvas {
    $bmp = New-Object System.Drawing.Bitmap 1400, 720
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::White)
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    return @{ Bitmap = $bmp; Graphics = $g }
}

function Draw-Box($g, $x, $y, $w, $h, $text, $fill) {
    $brush = New-Object System.Drawing.SolidBrush $fill
    $g.FillRectangle($brush, $x, $y, $w, $h)
    $g.DrawRectangle($pen, $x, $y, $w, $h)
    $rect = New-Object System.Drawing.RectangleF $x, $y, $w, $h
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString($text, $font, [System.Drawing.Brushes]::Black, $rect, $format)
    $brush.Dispose()
}

function Draw-Arrow($g, $x1, $y1, $x2, $y2) {
    $g.DrawLine($pen, $x1, $y1, $x2, $y2)
    $g.FillPolygon([System.Drawing.Brushes]::Navy, @(
        (New-Object System.Drawing.Point $x2, $y2),
        (New-Object System.Drawing.Point ($x2 - 10), ($y2 - 6)),
        (New-Object System.Drawing.Point ($x2 - 10), ($y2 + 6))
    ))
}

function Save-Canvas($canvas, $name) {
    $path = Join-Path $dir $name
    $canvas.Bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $canvas.Graphics.Dispose()
    $canvas.Bitmap.Dispose()
}

$c = New-Canvas
Draw-Box $c.Graphics 40 250 260 160 "Browser`r`nNext.js interface" $pale
Draw-Box $c.Graphics 420 170 300 150 "FastAPI service`r`nauthentication, RAG, scoring" $pale
Draw-Box $c.Graphics 860 60 480 130 "PostgreSQL and pgvector`r`nprofiles, documents, trials" $pale
Draw-Box $c.Graphics 860 250 480 120 "Local upload store`r`nPDF and text files" $pale
Draw-Box $c.Graphics 860 450 480 130 "Model provider`r`nchat and embeddings" $pale
Draw-Arrow $c.Graphics 300 330 420 250
Draw-Arrow $c.Graphics 720 220 860 125
Draw-Arrow $c.Graphics 720 280 860 310
Draw-Arrow $c.Graphics 720 300 860 500
Save-Canvas $c "figure1-architecture.png"

$c = New-Canvas
$labels = @(
    @(40, "Upload`r`nPDF or TXT"),
    @(300, "Extract, chunk`r`nand embed"),
    @(560, "Store chunks`r`nwith access label"),
    @(820, "Search the`r`nallow-list"),
    @(1080, "Generate,`r`nthen check")
)
foreach ($item in $labels) { Draw-Box $c.Graphics $item[0] 260 220 160 $item[1] $pale }
foreach ($x in 260, 520, 780, 1040) { Draw-Arrow $c.Graphics $x 340 ($x + 40) 340 }
Save-Canvas $c "figure2-rag.png"

$c = New-Canvas
$steps = @(
    @(40, "Sign in with`r`nSupabase Auth"),
    @(360, "Send bearer`r`ntoken to the API"),
    @(680, "Verify token and`r`nload profile role"),
    @(1020, "Allow or deny`r`nthe document")
)
foreach ($item in $steps) { Draw-Box $c.Graphics $item[0] 260 280 160 $item[1] $pale }
foreach ($x in 320, 640, 960) { Draw-Arrow $c.Graphics $x 340 ($x + 40) 340 }
Save-Canvas $c "figure3-auth.png"

$c = New-Canvas
Draw-Box $c.Graphics 80 70 540 80 "Baseline" $warm
Draw-Box $c.Graphics 80 180 540 360 "System message contains the retrieved chunks and tells the model to follow the documents and the user. The answer is not redacted." $warm
Draw-Box $c.Graphics 760 70 540 80 "Secured" $green
Draw-Box $c.Graphics 760 180 540 360 "System message is a fixed trusted instruction. Retrieved chunks sit in the user message as untrusted references. Unauthorised markers are redacted." $green
Save-Canvas $c "figure4-configs.png"

$c = New-Canvas
$flow = @(
    @(30, "Official`r`ntest case"),
    @(300, "Resolve the`r`nsynthetic actor"),
    @(570, "Run baseline`r`nor secured"),
    @(840, "Classify the`r`nobservation"),
    @(1110, "Store the trial`r`nand the rate")
)
foreach ($item in $flow) { Draw-Box $c.Graphics $item[0] 260 230 160 $item[1] $pale }
foreach ($x in 260, 530, 800, 1070) { Draw-Arrow $c.Graphics $x 340 ($x + 40) 340 }
Save-Canvas $c "figure5-evaluation.png"
$pen.Dispose(); $font.Dispose()
Write-Output "figures-written"
