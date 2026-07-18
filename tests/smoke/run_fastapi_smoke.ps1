param(
    [string]$BaseUrl = "http://localhost:3001"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
        return [pscustomobject]@{ status = [int]$resp.StatusCode; body = $parsed; raw = $resp.Content; ok = $true }
    } catch {
        $status = 0
        $raw = ""
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $raw = $_.ErrorDetails.Message }
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
        return [pscustomobject]@{ status = $status; body = $parsed; raw = $raw; ok = $false }
    }
}

function Add-Result {
    param(
        [string]$Name,
        [object]$Resp
    )
    $script:results += [pscustomobject]@{
        name = $Name
        status = $Resp.status
        ok = $Resp.ok
        detail = if ($Resp.ok) { "ok" } else { ($Resp.raw | Out-String).Trim() }
    }
}

$results = @()

$ready = $false
for ($i = 0; $i -lt 12; $i++) {
    $healthTry = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/health"
    if ($healthTry.status -eq 200) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    throw "FastAPI did not become ready at $BaseUrl/health"
}

Add-Result -Name "health" -Resp (Invoke-ApiJson -Method "GET" -Url "$BaseUrl/health")
Add-Result -Name "hospital_comm_health" -Resp (Invoke-ApiJson -Method "GET" -Url "$BaseUrl/api/hospital-communication/health")

$ts = Get-Date -Format "yyyyMMddHHmmss"
$pwd = "Pass@123"

$signupA = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/auth/signup" -Body @{ name = "Smoke User A"; email = "smoke.a.$ts@example.com"; password = $pwd; role = "public"; location = "Mangalore"; phone = "9999991111" }
Add-Result -Name "auth_signup_a" -Resp $signupA

$signupB = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/auth/signup" -Body @{ name = "Smoke User B"; email = "smoke.b.$ts@example.com"; password = $pwd; role = "public"; location = "Mangalore"; phone = "9999992222" }
Add-Result -Name "auth_signup_b" -Resp $signupB

$loginA = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/auth/login" -Body @{ email = "smoke.a.$ts@example.com"; password = $pwd; role = "public" }
Add-Result -Name "auth_login_a" -Resp $loginA

$userA = $null
$userB = $null
if ($signupA.body -and $signupA.body._id) { $userA = $signupA.body._id }
if ($signupB.body -and $signupB.body._id) { $userB = $signupB.body._id }
if (-not $userA -and $loginA.body -and $loginA.body.user -and $loginA.body.user.id) { $userA = $loginA.body.user.id }

if ($userA) {
    Add-Result -Name "dashboard_public_full" -Resp (Invoke-ApiJson -Method "GET" -Url "$BaseUrl/api/dashboard/public/$userA/full")
    Add-Result -Name "alerts_create" -Resp (Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/alerts" -Body @{ userId = $userA; locationDetails = "Lat: 12.9716, Lng: 77.5946"; message = "Severe chest pain and breathing difficulty" })
    Add-Result -Name "notifications" -Resp (Invoke-ApiJson -Method "GET" -Url "$BaseUrl/api/notifications/$userA")
} else {
    Add-Result -Name "dashboard_public_full" -Resp ([pscustomobject]@{ status = 0; ok = $false; raw = "missing userA" })
    Add-Result -Name "alerts_create" -Resp ([pscustomobject]@{ status = 0; ok = $false; raw = "missing userA" })
    Add-Result -Name "notifications" -Resp ([pscustomobject]@{ status = 0; ok = $false; raw = "missing userA" })
}

if ($userA -and $userB) {
    Add-Result -Name "compatibility" -Resp (Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/check_compatibility" -Body @{ requester_id = $userA; donor_id = $userB; organ_type = "Blood" })
} else {
    Add-Result -Name "compatibility" -Resp ([pscustomobject]@{ status = 0; ok = $false; raw = "missing user ids" })
}

Add-Result -Name "analyze_report" -Resp (Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/analyze_report" -Body @{ report_text = "Patient shows elevated BP and irregular heart rate patterns" })
Add-Result -Name "hospital_predict_bed_forecast" -Resp (Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/hospital/predict_bed_forecast" -Body @{ hospital_id = 1; occupancy = 78; day_of_week = 3 })
Add-Result -Name "ambulance_list" -Resp (Invoke-ApiJson -Method "GET" -Url "$BaseUrl/api/ambulance/")
Add-Result -Name "gov_emergency_hotspots" -Resp (Invoke-ApiJson -Method "GET" -Url "$BaseUrl/api/gov/emergency_hotspots")

$results | Select-Object name, status, ok | Format-Table -AutoSize
$failed = @($results | Where-Object { -not $_.ok })
if ($failed.Count -gt 0) {
    Write-Host "\nFailed endpoints:" -ForegroundColor Red
    $failed | Select-Object name, status, detail | Format-Table -AutoSize
    exit 1
}
