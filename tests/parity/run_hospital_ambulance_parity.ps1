param(
    [string]$NodeBaseUrl = "http://127.0.0.1:3001",
    [string]$FastApiBaseUrl = "http://127.0.0.1:3002",
    [string]$OutJson = "tests/parity/hospital_ambulance_parity_report.json",
    [string]$OutMd = "tests/parity/hospital_ambulance_parity_report.md"
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

function Get-TopKeys {
    param([object]$Obj)
    if ($null -eq $Obj) { return @() }
    if ($Obj -is [array]) { return @() }
    $props = $Obj.PSObject.Properties
    if ($null -eq $props) { return @() }
    return @($props | ForEach-Object { $_.Name })
}

function Compare-NodeFastApi {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $node = Invoke-ApiJson -Method $Method -Url "$NodeBaseUrl$Path" -Body $Body
    $fast = Invoke-ApiJson -Method $Method -Url "$FastApiBaseUrl$Path" -Body $Body

    $nodeKeys = Get-TopKeys -Obj $node.body
    $fastKeys = Get-TopKeys -Obj $fast.body

    $missingInFast = @($nodeKeys | Where-Object { $_ -notin $fastKeys })
    $extraInFast = @($fastKeys | Where-Object { $_ -notin $nodeKeys })

    $statusMatch = ($node.status -eq $fast.status)
    $keysMatch = ($missingInFast.Count -eq 0)

    return [pscustomobject]@{
        name = $Name
        method = $Method
        path = $Path
        nodeStatus = $node.status
        fastApiStatus = $fast.status
        statusMatch = $statusMatch
        missingInFast = $missingInFast
        extraInFast = $extraInFast
        pass = ($statusMatch -and $keysMatch)
    }
}

# Reachability checks
$nodeHealth = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/hospital-communication/health"
if ($nodeHealth.status -ne 200) {
    throw "Node backend not reachable at $NodeBaseUrl (status=$($nodeHealth.status))."
}

$fastHealth = Invoke-ApiJson -Method "GET" -Url "$FastApiBaseUrl/health"
if ($fastHealth.status -ne 200) {
    throw "FastAPI backend not reachable at $FastApiBaseUrl (status=$($fastHealth.status))."
}

# Setup hospital users in Node for communication flow
$ts = Get-Date -Format "yyyyMMddHHmmss"
$h1 = "parity.h1.$ts@example.com"
$h2 = "parity.h2.$ts@example.com"
$null = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Parity H1"; email = $h1; password = "Pass@123"; role = "hospital"; location = "Mangalore"; phone = "9888800001"; regNumber = "REG-H1-$ts"; hospitalType = "General" }
$null = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Parity H2"; email = $h2; password = "Pass@123"; role = "hospital"; location = "Mangalore"; phone = "9888800002"; regNumber = "REG-H2-$ts"; hospitalType = "General" }

$pendingNode = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/dashboard/admin/pending-hospitals"
if (-not ($pendingNode.body -is [array])) {
    throw "Could not fetch pending hospital users from Node backend."
}

$hu1 = $pendingNode.body | Where-Object { $_.email -eq $h1 } | Select-Object -First 1
$hu2 = $pendingNode.body | Where-Object { $_.email -eq $h2 } | Select-Object -First 1
if (-not $hu1 -or -not $hu2) {
    throw "Could not resolve hospital user IDs for parity setup."
}

$hUser1 = $hu1._id
$hUser2 = $hu2._id

# Send one node message to get message id for message-level endpoints
$msgCreateNode = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/hospital-communication/send-message" -Body @{
    fromHospitalId = $hUser1
    toHospitalId = $hUser2
    messageType = "resource"
    subject = "Parity Message"
    details = "Need O+ blood units"
    requestDetails = @{ resourceName = "O+ Blood"; resourceQuantity = 2 }
    urgencyLevel = "medium"
}

$messageId = $null
if ($msgCreateNode.body -and $msgCreateNode.body.data -and $msgCreateNode.body.data._id) {
    $messageId = $msgCreateNode.body.data._id
}
if (-not $messageId) {
    throw "Could not create/resolve hospital message ID for parity setup."
}

# Resolve ambulance and hospital ids from node seed data
$ambList = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/ambulance/"
if (-not ($ambList.body -and $ambList.body.data -and $ambList.body.data.Count -gt 0)) {
    throw "No ambulances available for parity setup."
}

$ambulanceId = $ambList.body.data[0]._id
$ambDetail = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/ambulance/$ambulanceId"
$hospitalId = $null
if ($ambDetail.body -and $ambDetail.body.data -and $ambDetail.body.data.hospital) {
    if ($ambDetail.body.data.hospital._id) { $hospitalId = $ambDetail.body.data.hospital._id }
    elseif ($ambDetail.body.data.hospital -is [string]) { $hospitalId = $ambDetail.body.data.hospital }
}
if (-not $hospitalId) {
    throw "Could not resolve hospitalId from ambulance details for parity setup."
}

$results = @()

# Hospital communication parity
$results += Compare-NodeFastApi -Name "hospital_comm_health" -Method "GET" -Path "/api/hospital-communication/health"
$results += Compare-NodeFastApi -Name "hospital_comm_debug" -Method "GET" -Path "/api/hospital-communication/debug/status"
$results += Compare-NodeFastApi -Name "hospital_comm_list" -Method "GET" -Path "/api/hospital-communication/list/$hUser1"
$results += Compare-NodeFastApi -Name "hospital_comm_details" -Method "GET" -Path "/api/hospital-communication/details/$hUser2"
$results += Compare-NodeFastApi -Name "hospital_comm_send" -Method "POST" -Path "/api/hospital-communication/send-message" -Body @{
    fromHospitalId = $hUser1
    toHospitalId = $hUser2
    messageType = "resource"
    subject = "Parity Message 2"
    details = "Need plasma"
    requestDetails = @{ resourceName = "Plasma"; resourceQuantity = 1 }
    urgencyLevel = "low"
}
$results += Compare-NodeFastApi -Name "hospital_comm_messages" -Method "GET" -Path "/api/hospital-communication/messages/$hUser2"
$results += Compare-NodeFastApi -Name "hospital_comm_sent" -Method "GET" -Path "/api/hospital-communication/sent-messages/$hUser1"
$results += Compare-NodeFastApi -Name "hospital_comm_patch" -Method "PATCH" -Path "/api/hospital-communication/message/$messageId" -Body @{ status = "approved"; responseMessage = "Approved"; response = @{ respondedBy = $hUser1 } }
$results += Compare-NodeFastApi -Name "hospital_comm_reply" -Method "POST" -Path "/api/hospital-communication/message/$messageId/reply" -Body @{ status = "approved"; responseMessage = "Handled" }
$results += Compare-NodeFastApi -Name "hospital_comm_my" -Method "GET" -Path "/api/hospital-communication/my-hospital/$hUser1"
$results += Compare-NodeFastApi -Name "hospital_comm_my_put" -Method "PUT" -Path "/api/hospital-communication/my-hospital/$hUser1" -Body @{ beds = @{ totalBeds = 100; occupiedBeds = 40; availableBeds = 60 } }

# Hospital analytics parity (/api/hospital and /api/hosp)
$etaPayload = @{ start_node = "Central City General"; end_node = "Downtown" }
$results += Compare-NodeFastApi -Name "hospital_predict_eta" -Method "POST" -Path "/api/hospital/predict_eta" -Body $etaPayload
$results += Compare-NodeFastApi -Name "hosp_predict_eta_alias" -Method "POST" -Path "/api/hosp/predict_eta" -Body $etaPayload

# Ambulance parity
$results += Compare-NodeFastApi -Name "ambulance_list" -Method "GET" -Path "/api/ambulance/"
$results += Compare-NodeFastApi -Name "ambulance_hospital_list" -Method "GET" -Path "/api/ambulance/hospital/$hospitalId"
$results += Compare-NodeFastApi -Name "ambulance_details" -Method "GET" -Path "/api/ambulance/$ambulanceId"
$results += Compare-NodeFastApi -Name "ambulance_predict_eta" -Method "POST" -Path "/api/ambulance/$ambulanceId/predict-eta" -Body @{ currentLatitude = 12.9; currentLongitude = 74.8; destinationLatitude = 12.95; destinationLongitude = 74.85; trafficLevel = "medium"; weather = "clear" }
$results += Compare-NodeFastApi -Name "ambulance_get_route" -Method "POST" -Path "/api/ambulance/$ambulanceId/get-route" -Body @{ startLatitude = 12.9; startLongitude = 74.8; destinationLatitude = 12.95; destinationLongitude = 74.85 }
$results += Compare-NodeFastApi -Name "ambulance_status" -Method "PUT" -Path "/api/ambulance/$ambulanceId/status" -Body @{ status = "available" }
$results += Compare-NodeFastApi -Name "ambulance_metrics" -Method "GET" -Path "/api/ambulance/$ambulanceId/metrics"

$summary = [pscustomobject]@{
    checkedAt = (Get-Date).ToString("o")
    nodeBaseUrl = $NodeBaseUrl
    fastApiBaseUrl = $FastApiBaseUrl
    total = $results.Count
    passed = (@($results | Where-Object { $_.pass }).Count)
    failed = (@($results | Where-Object { -not $_.pass }).Count)
    results = $results
}

$summary | ConvertTo-Json -Depth 30 | Out-File -FilePath $OutJson -Encoding utf8

$lines = @()
$lines += "# Hospital and Ambulance Parity Report"
$lines += ""
$lines += "- Checked at: $($summary.checkedAt)"
$lines += "- Node base URL: $($summary.nodeBaseUrl)"
$lines += "- FastAPI base URL: $($summary.fastApiBaseUrl)"
$lines += "- Total: $($summary.total)"
$lines += "- Passed: $($summary.passed)"
$lines += "- Failed: $($summary.failed)"
$lines += ""
$lines += "| Name | Method | Path | Status Match | Missing In FastAPI | Extra In FastAPI |"
$lines += "|---|---|---|---|---|---|"
foreach ($r in $results) {
    $statusTxt = if ($r.pass) { "PASS" } elseif ($r.statusMatch) { "KEY MISMATCH" } else { "STATUS MISMATCH ($($r.nodeStatus)/$($r.fastApiStatus))" }
    $missingTxt = if ($r.missingInFast.Count -eq 0) { "-" } else { ($r.missingInFast -join ", ") }
    $extraTxt = if ($r.extraInFast.Count -eq 0) { "-" } else { ($r.extraInFast -join ", ") }
    $lines += "| $($r.name) | $($r.method) | $($r.path) | $statusTxt | $missingTxt | $extraTxt |"
}

$lines -join "`n" | Out-File -FilePath $OutMd -Encoding utf8

Write-Output "Parity report written: $OutJson"
Write-Output "Parity summary written: $OutMd"
Write-Output "Passed=$($summary.passed), Failed=$($summary.failed), Total=$($summary.total)"
