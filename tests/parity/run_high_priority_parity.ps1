param(
    [string]$BaseUrl = "http://127.0.0.1:3002",
    [string]$GoldenDir = "tests/parity/golden_responses",
    [string]$OutJson = "tests/parity/high_priority_parity_report.json",
    [string]$OutMd = "tests/parity/high_priority_parity_report.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    $raw = Get-Content -Path $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return $raw | ConvertFrom-Json
}

function Get-TopKeys {
    param([object]$Obj)
    if ($null -eq $Obj) { return @() }
    if ($Obj -is [array]) { return @() }
    $props = $Obj.PSObject.Properties
    if ($null -eq $props) { return @() }
    return @($props | ForEach-Object { $_.Name })
}

function Invoke-ApiJson {
    param(
        [string]$Method,
        [string]$Url,
        [object]$Body = $null
    )

    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 20
    }

    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $Url -ContentType "application/json" -Body $jsonBody
        $parsed = $null
        if (-not [string]::IsNullOrWhiteSpace($resp.Content)) {
            try { $parsed = $resp.Content | ConvertFrom-Json } catch { $parsed = $resp.Content }
        }
        return [pscustomobject]@{
            status = [int]$resp.StatusCode
            body = $parsed
            raw = $resp.Content
            ok = $true
        }
    } catch {
        $status = 0
        $raw = ""
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $raw = $_.ErrorDetails.Message
        }
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode.value__
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $raw = $reader.ReadToEnd()
                    $reader.Close()
                }
            } catch {}
        }

        $parsed = $null
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            try { $parsed = $raw | ConvertFrom-Json } catch { $parsed = $raw }
        }

        return [pscustomobject]@{
            status = $status
            body = $parsed
            raw = $raw
            ok = $false
        }
    }
}

function Compare-Contract {
    param(
        [string]$Name,
        [int]$ExpectedStatus,
        [object]$GoldenBody,
        [object]$Actual
    )

    $goldenKeys = Get-TopKeys -Obj $GoldenBody
    $actualKeys = Get-TopKeys -Obj $Actual.body

    $missing = @($goldenKeys | Where-Object { $_ -notin $actualKeys })
    $extra = @($actualKeys | Where-Object { $_ -notin $goldenKeys })

    $statusOk = ($Actual.status -eq $ExpectedStatus)
    $keysOk = ($missing.Count -eq 0)

    [pscustomobject]@{
        name = $Name
        expectedStatus = $ExpectedStatus
        actualStatus = $Actual.status
        statusOk = $statusOk
        missingKeys = $missing
        extraKeys = $extra
        goldenKeys = $goldenKeys
        actualKeys = $actualKeys
        pass = ($statusOk -and $keysOk)
    }
}

# Ensure FastAPI is reachable
$health = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/health"
if ($health.status -ne 200) {
    throw "FastAPI service not reachable at $BaseUrl/health (status=$($health.status))."
}

$ctx = Read-JsonFile -Path (Join-Path $GoldenDir "capture_context.json")
$goldLogin = Read-JsonFile -Path (Join-Path $GoldenDir "auth_login_200.json")

$userA = $ctx.userA
$userB = $ctx.userB
$emailA = $ctx.emailA
if (-not $emailA -and $goldLogin -and $goldLogin.user -and $goldLogin.user.email) {
    $emailA = $goldLogin.user.email
}

$cases = @()

# Signup parity check (dynamic user)
$ts = Get-Date -Format "yyyyMMddHHmmss"
$signupBody = @{ name = "Parity User"; email = "parity.$ts@example.com"; password = "Pass@123"; role = "public"; location = "Mangalore"; phone = "9999991212" }
$cases += [pscustomobject]@{ name = "auth_signup"; method = "POST"; path = "/api/auth/signup"; status = 201; golden = "auth_signup_201.json"; body = $signupBody }

# Login parity check
$loginBody = @{ email = $emailA; password = "Pass@123"; role = "public" }
$cases += [pscustomobject]@{ name = "auth_login"; method = "POST"; path = "/api/auth/login"; status = 200; golden = "auth_login_200.json"; body = $loginBody }

$cases += [pscustomobject]@{ name = "hospital_communication_health"; method = "GET"; path = "/api/hospital-communication/health"; status = 200; golden = "hospital_communication_health_200.json"; body = $null }
$cases += [pscustomobject]@{ name = "alerts_create"; method = "POST"; path = "/api/alerts"; status = 201; golden = "alerts_create_201.json"; body = @{ userId = $userA; locationDetails = "Lat: 12.97, Lng: 77.59"; message = "Severe chest pain and breathing difficulty" } }
$cases += [pscustomobject]@{ name = "notifications"; method = "GET"; path = "/api/notifications/$userA"; status = 200; golden = "notifications_200.json"; body = $null }
$cases += [pscustomobject]@{ name = "compatibility"; method = "POST"; path = "/api/check_compatibility"; status = 200; golden = "compatibility_200.json"; body = @{ requester_id = $userA; donor_id = $userB; organ_type = "Blood" } }
$cases += [pscustomobject]@{ name = "analyze_report"; method = "POST"; path = "/api/analyze_report"; status = 200; golden = "analyze_report_200.json"; body = @{ report_text = "Patient report indicates elevated BP and irregular pulse trend." } }
$cases += [pscustomobject]@{ name = "requests_create"; method = "POST"; path = "/api/requests"; status = 201; golden = "requests_create_201.json"; body = @{ requester_id = $userA; request_type = "blood"; details = "O+ Blood needed urgently"; urgency = "high" } }
$cases += [pscustomobject]@{ name = "dashboard_public_full"; method = "GET"; path = "/api/dashboard/public/$userA/full"; status = 200; golden = "dashboard_public_full_200.json"; body = $null }
$cases += [pscustomobject]@{ name = "dashboard_profile_update"; method = "PUT"; path = "/api/dashboard/profile/$userA"; status = 200; golden = "dashboard_profile_update_200.json"; body = @{ name = "Golden3 A Updated"; phone = "9000000001"; location = "Mangalore City"; medicalHistory = "asthma,diabetes" } }

# users_verify flow needs fresh pending hospital user
$hMail = "parity.hospital.$ts@example.com"
$signupHospital = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/auth/signup" -Body @{ name = "Parity Hospital"; email = $hMail; password = "Pass@123"; role = "hospital"; location = "Mangalore"; phone = "9888800000"; regNumber = "REG-PAR-$ts"; hospitalType = "General" }
$pending = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/api/dashboard/admin/pending-hospitals"
$hospitalUser = $null
if ($pending.body -is [array]) {
    $hospitalUser = $pending.body | Where-Object { $_.email -eq $hMail } | Select-Object -First 1
}
if ($hospitalUser -and $hospitalUser._id) {
    $cases += [pscustomobject]@{ name = "users_verify"; method = "POST"; path = "/api/users/verify"; status = 200; golden = "users_verify_200.json"; body = @{ hospitalUserId = $hospitalUser._id } }
}

$results = @()
foreach ($c in $cases) {
    $url = "$BaseUrl$($c.path)"
    $actual = Invoke-ApiJson -Method $c.method -Url $url -Body $c.body
    $gold = Read-JsonFile -Path (Join-Path $GoldenDir $c.golden)
    $cmp = Compare-Contract -Name $c.name -ExpectedStatus $c.status -GoldenBody $gold -Actual $actual

    $results += [pscustomobject]@{
        name = $cmp.name
        method = $c.method
        path = $c.path
        pass = $cmp.pass
        expectedStatus = $cmp.expectedStatus
        actualStatus = $cmp.actualStatus
        statusOk = $cmp.statusOk
        missingKeys = $cmp.missingKeys
        extraKeys = $cmp.extraKeys
    }
}

$summary = [pscustomobject]@{
    checkedAt = (Get-Date).ToString("o")
    baseUrl = $BaseUrl
    total = $results.Count
    passed = (@($results | Where-Object { $_.pass }).Count)
    failed = (@($results | Where-Object { -not $_.pass }).Count)
    results = $results
}

$summary | ConvertTo-Json -Depth 20 | Out-File -FilePath $OutJson -Encoding utf8

$lines = @()
$lines += "# High Priority Parity Report"
$lines += ""
$lines += "- Checked at: $($summary.checkedAt)"
$lines += "- Base URL: $($summary.baseUrl)"
$lines += "- Total: $($summary.total)"
$lines += "- Passed: $($summary.passed)"
$lines += "- Failed: $($summary.failed)"
$lines += ""
$lines += "## Endpoint Results"
$lines += ""
$lines += "| Name | Method | Path | Status | Missing Keys | Extra Keys |"
$lines += "|---|---|---|---|---|---|"
foreach ($r in $results) {
    $statusTxt = if ($r.pass) { "PASS" } else { "FAIL ($($r.actualStatus)/$($r.expectedStatus))" }
    $missingTxt = if ($r.missingKeys.Count -eq 0) { "-" } else { ($r.missingKeys -join ", ") }
    $extraTxt = if ($r.extraKeys.Count -eq 0) { "-" } else { ($r.extraKeys -join ", ") }
    $lines += "| $($r.name) | $($r.method) | $($r.path) | $statusTxt | $missingTxt | $extraTxt |"
}

$lines -join "`n" | Out-File -FilePath $OutMd -Encoding utf8

Write-Output "Parity report written: $OutJson"
Write-Output "Parity summary written: $OutMd"
Write-Output "Passed=$($summary.passed), Failed=$($summary.failed), Total=$($summary.total)"
