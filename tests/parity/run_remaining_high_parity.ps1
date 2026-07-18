param(
    [string]$NodeBaseUrl = "http://127.0.0.1:3001",
    [string]$FastApiBaseUrl = "http://127.0.0.1:3002",
    [string]$OutJson = "tests/parity/remaining_high_parity_report.json",
    [string]$OutMd = "tests/parity/remaining_high_parity_report.md"
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
        [string]$NodePath,
        [string]$FastPath,
        [object]$NodeBody = $null,
        [object]$FastBody = $null
    )

    $node = Invoke-ApiJson -Method $Method -Url "$NodeBaseUrl$NodePath" -Body $NodeBody
    $fast = Invoke-ApiJson -Method $Method -Url "$FastApiBaseUrl$FastPath" -Body $FastBody

    $nodeKeys = Get-TopKeys -Obj $node.body
    $fastKeys = Get-TopKeys -Obj $fast.body

    $missingInFast = @($nodeKeys | Where-Object { $_ -notin $fastKeys })
    $extraInFast = @($fastKeys | Where-Object { $_ -notin $nodeKeys })

    $statusMatch = ($node.status -eq $fast.status)
    $keysMatch = ($missingInFast.Count -eq 0)

    return [pscustomobject]@{
        name = $Name
        method = $Method
        nodePath = $NodePath
        fastPath = $FastPath
        nodeStatus = $node.status
        fastApiStatus = $fast.status
        statusMatch = $statusMatch
        missingInFast = $missingInFast
        extraInFast = $extraInFast
        pass = ($statusMatch -and $keysMatch)
    }
}

# Reachability
$nodeHealth = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/hospital-communication/health"
if ($nodeHealth.status -ne 200) { throw "Node backend not reachable at $NodeBaseUrl." }
$fastHealth = Invoke-ApiJson -Method "GET" -Url "$FastApiBaseUrl/health"
if ($fastHealth.status -ne 200) { throw "FastAPI backend not reachable at $FastApiBaseUrl." }

# Dynamic setup context
$ts = Get-Date -Format "yyyyMMddHHmmss"

# Public users for AI + alert/request flows
$pA = "remain.a.$ts@example.com"
$pB = "remain.b.$ts@example.com"
$signupA = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Remain A"; email = $pA; password = "Pass@123"; role = "public"; location = "Mangalore"; phone = "9000000011" }
$signupB = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Remain B"; email = $pB; password = "Pass@123"; role = "public"; location = "Mangalore"; phone = "9000000012" }

$userA = $null
$userB = $null
if ($signupA.body) {
    $hasUserA = $null -ne ($signupA.body.PSObject.Properties["user"])
    $hasIdA = $null -ne ($signupA.body.PSObject.Properties["_id"])
    if ($hasUserA -and $signupA.body.user -and ($null -ne $signupA.body.user.PSObject.Properties["id"])) {
        $userA = $signupA.body.user.id
    } elseif ($hasIdA) {
        $userA = $signupA.body._id
    }
}
if ($signupB.body) {
    $hasUserB = $null -ne ($signupB.body.PSObject.Properties["user"])
    $hasIdB = $null -ne ($signupB.body.PSObject.Properties["_id"])
    if ($hasUserB -and $signupB.body.user -and ($null -ne $signupB.body.user.PSObject.Properties["id"])) {
        $userB = $signupB.body.user.id
    } elseif ($hasIdB) {
        $userB = $signupB.body._id
    }
}
if (-not $userA -or -not $userB) { throw "Could not resolve setup users for remaining high parity." }

# Resolve hospital + ambulance from existing data
$ambList = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/ambulance/"
if (-not ($ambList.body -and $ambList.body.data -and $ambList.body.data.Count -gt 0)) {
    throw "No ambulances available for setup."
}
$ambulanceId = $ambList.body.data[0]._id
$ambDetail = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/ambulance/$ambulanceId"
$hospitalId = $null
if ($ambDetail.body -and $ambDetail.body.data -and $ambDetail.body.data.hospital) {
    if ($ambDetail.body.data.hospital._id) { $hospitalId = $ambDetail.body.data.hospital._id }
    elseif ($ambDetail.body.data.hospital -is [string]) { $hospitalId = $ambDetail.body.data.hospital }
}
if (-not $hospitalId) { throw "Could not resolve hospitalId for remaining high parity." }

# Setup pending hospital for verify endpoint
$hPendingEmail = "remain.pending.$ts@example.com"
$null = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Remain Pending"; email = $hPendingEmail; password = "Pass@123"; role = "hospital"; location = "Mangalore"; phone = "9880000011"; regNumber = "REG-RP-$ts"; hospitalType = "General" }
$pending = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/dashboard/admin/pending-hospitals"
$pendingUser = $null
if ($pending.body -is [array]) {
    $pendingUser = $pending.body | Where-Object { $_.email -eq $hPendingEmail } | Select-Object -First 1
}
if (-not ($pendingUser -and $pendingUser._id)) { throw "Could not resolve pending hospital user id." }
$pendingHospitalUserId = $pendingUser._id

# Setup alert ids for update and delete tests
$alert1 = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/alerts" -Body @{ userId = $userA; locationDetails = "Lat: 12.95, Lng: 74.84"; message = "Remain alert one" }
$alert2 = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/alerts" -Body @{ userId = $userA; locationDetails = "Lat: 12.96, Lng: 74.85"; message = "Remain alert two" }
$alert3 = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/alerts" -Body @{ userId = $userA; locationDetails = "Lat: 12.97, Lng: 74.86"; message = "Remain alert three" }
$alertUpdateId = $null
$alertDeleteNodeId = $null
$alertDeleteFastId = $null
if ($alert1.body) {
    if ($null -ne $alert1.body.PSObject.Properties["alert_id"]) {
        $alertUpdateId = $alert1.body.alert_id
    } elseif (($null -ne $alert1.body.PSObject.Properties["alert"]) -and $alert1.body.alert -and ($null -ne $alert1.body.alert.PSObject.Properties["id"])) {
        $alertUpdateId = $alert1.body.alert.id
    } elseif ($null -ne $alert1.body.PSObject.Properties["id"]) {
        $alertUpdateId = $alert1.body.id
    }
}
if ($alert2.body) {
    if ($null -ne $alert2.body.PSObject.Properties["alert_id"]) {
        $alertDeleteNodeId = $alert2.body.alert_id
    } elseif (($null -ne $alert2.body.PSObject.Properties["alert"]) -and $alert2.body.alert -and ($null -ne $alert2.body.alert.PSObject.Properties["id"])) {
        $alertDeleteNodeId = $alert2.body.alert.id
    } elseif ($null -ne $alert2.body.PSObject.Properties["id"]) {
        $alertDeleteNodeId = $alert2.body.id
    }
}
if ($alert3.body) {
    if ($null -ne $alert3.body.PSObject.Properties["alert_id"]) {
        $alertDeleteFastId = $alert3.body.alert_id
    } elseif (($null -ne $alert3.body.PSObject.Properties["alert"]) -and $alert3.body.alert -and ($null -ne $alert3.body.alert.PSObject.Properties["id"])) {
        $alertDeleteFastId = $alert3.body.alert.id
    } elseif ($null -ne $alert3.body.PSObject.Properties["id"]) {
        $alertDeleteFastId = $alert3.body.id
    }
}
if (-not $alertUpdateId) { throw "Could not create alert for update." }
if (-not $alertDeleteNodeId) { throw "Could not create alert for delete." }
if (-not $alertDeleteFastId) { throw "Could not create fast alert for delete." }

# Setup request for dashboard notification delete (request)
$requestCreate = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/requests" -Body @{ requester_id = $userA; request_type = "blood"; details = "Remaining parity request"; urgency = "high" }
$requestCreate2 = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/requests" -Body @{ requester_id = $userA; request_type = "blood"; details = "Remaining parity request two"; urgency = "high" }
$requestDeleteNodeId = $null
$requestDeleteFastId = $null
if ($requestCreate.status -eq 201 -or $requestCreate.status -eq 200) {
    $dashFull = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/dashboard/public/$userA/full"
    if ($dashFull.body -and ($null -ne $dashFull.body.PSObject.Properties["resourceRequests"]) -and ($dashFull.body.resourceRequests -is [array]) -and $dashFull.body.resourceRequests.Count -gt 1) {
        $firstReq = $dashFull.body.resourceRequests[0]
        $secondReq = $dashFull.body.resourceRequests[1]
        if ($firstReq -and ($null -ne $firstReq.PSObject.Properties["_id"])) {
            $requestDeleteNodeId = $firstReq._id
        } elseif ($firstReq -and ($null -ne $firstReq.PSObject.Properties["id"])) {
            $requestDeleteNodeId = $firstReq.id
        }
        if ($secondReq -and ($null -ne $secondReq.PSObject.Properties["_id"])) {
            $requestDeleteFastId = $secondReq._id
        } elseif ($secondReq -and ($null -ne $secondReq.PSObject.Properties["id"])) {
            $requestDeleteFastId = $secondReq.id
        }
    }
}
if (-not $requestDeleteNodeId) { throw "Could not create request id for delete." }
if (-not $requestDeleteFastId) { throw "Could not create fast request id for delete." }

# Setup hospital communication messages for delete tests
$h1 = "remain.h1.$ts@example.com"
$h2 = "remain.h2.$ts@example.com"
$null = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Remain H1"; email = $h1; password = "Pass@123"; role = "hospital"; location = "Mangalore"; phone = "9888800011"; regNumber = "REG-RH1-$ts"; hospitalType = "General" }
$null = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/auth/signup" -Body @{ name = "Remain H2"; email = $h2; password = "Pass@123"; role = "hospital"; location = "Mangalore"; phone = "9888800012"; regNumber = "REG-RH2-$ts"; hospitalType = "General" }

$pendingAll = Invoke-ApiJson -Method "GET" -Url "$NodeBaseUrl/api/dashboard/admin/pending-hospitals"
$hUser1 = ($pendingAll.body | Where-Object { $_.email -eq $h1 } | Select-Object -First 1)._id
$hUser2 = ($pendingAll.body | Where-Object { $_.email -eq $h2 } | Select-Object -First 1)._id
if (-not $hUser1 -or -not $hUser2) { throw "Could not resolve hospital users for message delete test." }

$msgNode = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/hospital-communication/send-message" -Body @{ fromHospitalId = $hUser1; toHospitalId = $hUser2; messageType = "resource"; subject = "Delete Node"; details = "Delete path node"; requestDetails = @{ resourceName = "O+ Blood"; resourceQuantity = 1 }; urgencyLevel = "low" }
$msgFast = Invoke-ApiJson -Method "POST" -Url "$NodeBaseUrl/api/hospital-communication/send-message" -Body @{ fromHospitalId = $hUser1; toHospitalId = $hUser2; messageType = "resource"; subject = "Delete Fast"; details = "Delete path fast"; requestDetails = @{ resourceName = "Plasma"; resourceQuantity = 1 }; urgencyLevel = "low" }
$messageDeleteNodeId = $null
$messageDeleteFastId = $null
if ($msgNode.body -and ($null -ne $msgNode.body.PSObject.Properties["data"]) -and $msgNode.body.data -and ($null -ne $msgNode.body.data.PSObject.Properties["_id"])) {
    $messageDeleteNodeId = $msgNode.body.data._id
}
if ($msgFast.body -and ($null -ne $msgFast.body.PSObject.Properties["data"]) -and $msgFast.body.data -and ($null -ne $msgFast.body.data.PSObject.Properties["_id"])) {
    $messageDeleteFastId = $msgFast.body.data._id
}
if (-not $messageDeleteNodeId) { throw "Could not create node message id for delete." }
if (-not $messageDeleteFastId) { throw "Could not create fast message id for delete." }

# Setup for ambulance create route with backend-specific payloads to avoid duplicate conflicts
$newAmbNode = "AMB-RN-$ts"
$newAmbFast = "AMB-RF-$ts"

$results = @()

# Dashboard and hospital operations
$results += Compare-NodeFastApi -Name "dashboard_hospital_stats" -Method "GET" -NodePath "/api/dashboard/hospital/stats" -FastPath "/api/dashboard/hospital/stats"
$results += Compare-NodeFastApi -Name "dashboard_hospital_alerts" -Method "GET" -NodePath "/api/dashboard/hospital/alerts" -FastPath "/api/dashboard/hospital/alerts"
$results += Compare-NodeFastApi -Name "dashboard_hospital_alert_update" -Method "PUT" -NodePath "/api/dashboard/hospital/alert/$alertUpdateId" -FastPath "/api/dashboard/hospital/alert/$alertUpdateId" -NodeBody @{ status = "Resolved" } -FastBody @{ status = "Resolved" }
$results += Compare-NodeFastApi -Name "dashboard_admin_pending" -Method "GET" -NodePath "/api/dashboard/admin/pending-hospitals" -FastPath "/api/dashboard/admin/pending-hospitals"
$results += Compare-NodeFastApi -Name "dashboard_admin_verify" -Method "PUT" -NodePath "/api/dashboard/admin/verify/$pendingHospitalUserId" -FastPath "/api/dashboard/admin/verify/$pendingHospitalUserId"
$results += Compare-NodeFastApi -Name "dashboard_patient_admit" -Method "POST" -NodePath "/api/dashboard/hospital/patient/admit" -FastPath "/api/dashboard/hospital/patient/admit" -NodeBody @{ hospitalId = $hospitalId; name = "Remain Patient"; age = 54; gender = "Male"; dept = "Cardiology"; room = "C-12"; condition = "Chest pain"; severity = "High"; oxygen = 94; heartRate = 102; bp = "150/95" } -FastBody @{ hospitalId = $hospitalId; name = "Remain Patient"; age = 54; gender = "Male"; dept = "Cardiology"; room = "C-12"; condition = "Chest pain"; severity = "High"; oxygen = 94; heartRate = 102; bp = "150/95" }
$results += Compare-NodeFastApi -Name "dashboard_hospital_patients" -Method "GET" -NodePath "/api/dashboard/hospital/patients/$hospitalId" -FastPath "/api/dashboard/hospital/patients/$hospitalId"
$results += Compare-NodeFastApi -Name "dashboard_resource_add" -Method "POST" -NodePath "/api/dashboard/hospital/resource/add" -FastPath "/api/dashboard/hospital/resource/add" -NodeBody @{ hospitalId = $hospitalId; name = "Gloves"; category = "Equipment"; quantity = 200; unit = "pairs"; minThreshold = 50; expiryDate = "2027-01-01" } -FastBody @{ hospitalId = $hospitalId; name = "Gloves"; category = "Equipment"; quantity = 200; unit = "pairs"; minThreshold = 50; expiryDate = "2027-01-01" }
$results += Compare-NodeFastApi -Name "dashboard_hospital_resources" -Method "GET" -NodePath "/api/dashboard/hospital/resources/$hospitalId" -FastPath "/api/dashboard/hospital/resources/$hospitalId"
$results += Compare-NodeFastApi -Name "dashboard_notification_delete_alert" -Method "DELETE" -NodePath "/api/dashboard/notification/alert/$alertDeleteNodeId" -FastPath "/api/dashboard/notification/alert/$alertDeleteFastId"
$results += Compare-NodeFastApi -Name "dashboard_notification_delete_request" -Method "DELETE" -NodePath "/api/dashboard/notification/request/$requestDeleteNodeId" -FastPath "/api/dashboard/notification/request/$requestDeleteFastId"

# AI endpoints under /api
$aiBodyCore = @{ requester_id = $userA; donor_id = $userB; organ_type = "Blood"; age = 42; blood_group = "O+"; heart_rate = 98; oxygen = 95; systolic_bp = 138; diastolic_bp = 90; emergency_count = 12; disease_case_count = 40; current_bed_occupancy = 70; hour = 14; start_node = "Central City General"; end_node = "Downtown"; region = "Mangalore"; policy_type = "resource-allocation"; anomaly_score = 0.62; inventory_level = 120; consumption_rate = 35; recovery_days = 8; stay_days = 4 }
$results += Compare-NodeFastApi -Name "ai_predict_health_risk" -Method "POST" -NodePath "/api/predict_health_risk" -FastPath "/api/predict_health_risk" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_predict_user_cluster" -Method "POST" -NodePath "/api/predict_user_cluster" -FastPath "/api/predict_user_cluster" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_predict_user_forecast" -Method "POST" -NodePath "/api/predict_user_forecast" -FastPath "/api/predict_user_forecast" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_hosp_predict_severity" -Method "POST" -NodePath "/api/hosp/predict_severity" -FastPath "/api/hosp/predict_severity" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_outbreak" -Method "POST" -NodePath "/api/gov/predict_outbreak" -FastPath "/api/gov/predict_outbreak" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_severity" -Method "POST" -NodePath "/api/gov/predict_severity" -FastPath "/api/gov/predict_severity" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_availability" -Method "POST" -NodePath "/api/gov/predict_availability" -FastPath "/api/gov/predict_availability" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_allocation" -Method "POST" -NodePath "/api/gov/predict_allocation" -FastPath "/api/gov/predict_allocation" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_policy_segment" -Method "POST" -NodePath "/api/gov/predict_policy_segment" -FastPath "/api/gov/predict_policy_segment" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_performance_score" -Method "POST" -NodePath "/api/gov/predict_performance_score" -FastPath "/api/gov/predict_performance_score" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_gov_predict_anomaly" -Method "POST" -NodePath "/api/gov/predict_anomaly" -FastPath "/api/gov/predict_anomaly" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_hospital_patient_recovery" -Method "POST" -NodePath "/api/hospital/patient/recovery" -FastPath "/api/hospital/patient/recovery" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_hospital_patient_stay" -Method "POST" -NodePath "/api/hospital/patient/stay" -FastPath "/api/hospital/patient/stay" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_hospital_inventory_predict" -Method "POST" -NodePath "/api/hospital/inventory/predict" -FastPath "/api/hospital/inventory/predict" -NodeBody $aiBodyCore -FastBody $aiBodyCore
$results += Compare-NodeFastApi -Name "ai_ml_predict_eta" -Method "POST" -NodePath "/api/ml/predict-eta" -FastPath "/api/ml/predict-eta" -NodeBody @{ start_node = "Central City General"; end_node = "Downtown"; hour = 13 } -FastBody @{ start_node = "Central City General"; end_node = "Downtown"; hour = 13 }

# Hospital analytics under /api/hospital and /api/hosp
$hospBody = @{ start_node = "Central City General"; end_node = "Downtown"; hour = 12; emergency_count = 8; disease_case_count = 25; current_bed_occupancy = 68; hospital_id = 1; requester_id = $userA; donor_id = $userB; organ_type = "Blood"; age = 39; severity = "moderate" }
$results += Compare-NodeFastApi -Name "hospital_triage" -Method "POST" -NodePath "/api/hospital/triage" -FastPath "/api/hospital/triage" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_eta" -Method "POST" -NodePath "/api/hospital/eta" -FastPath "/api/hospital/eta" -NodeBody @{ start_node = "Central City General"; end_node = "Downtown"; hour = 12 } -FastBody @{ start_node = "Central City General"; end_node = "Downtown"; hour = 12 }
$results += Compare-NodeFastApi -Name "hospital_bed_forecast" -Method "POST" -NodePath "/api/hospital/bed_forecast" -FastPath "/api/hospital/bed_forecast" -NodeBody @{ emergency_count = 10; disease_case_count = 28; current_bed_occupancy = 72 } -FastBody @{ emergency_count = 10; disease_case_count = 28; current_bed_occupancy = 72 }
$results += Compare-NodeFastApi -Name "hospital_staff" -Method "POST" -NodePath "/api/hospital/staff" -FastPath "/api/hospital/staff" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_donors" -Method "POST" -NodePath "/api/hospital/donors" -FastPath "/api/hospital/donors" -NodeBody @{ requester_id = $userA; donor_id = $userB; organ_type = "Blood" } -FastBody @{ requester_id = $userA; donor_id = $userB; organ_type = "Blood" }
$results += Compare-NodeFastApi -Name "hospital_performance" -Method "POST" -NodePath "/api/hospital/performance" -FastPath "/api/hospital/performance" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_predict_bed_forecast" -Method "POST" -NodePath "/api/hospital/predict_bed_forecast" -FastPath "/api/hospital/predict_bed_forecast" -NodeBody @{ emergency_count = 12; disease_case_count = 30; current_bed_occupancy = 75; hospital_id = 1 } -FastBody @{ emergency_count = 12; disease_case_count = 30; current_bed_occupancy = 75; hospital_id = 1 }
$results += Compare-NodeFastApi -Name "hospital_predict_staff_allocation" -Method "POST" -NodePath "/api/hospital/predict_staff_allocation" -FastPath "/api/hospital/predict_staff_allocation" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_predict_disease_forecast" -Method "POST" -NodePath "/api/hospital/predict_disease_forecast" -FastPath "/api/hospital/predict_disease_forecast" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_predict_recovery" -Method "POST" -NodePath "/api/hospital/predict_recovery" -FastPath "/api/hospital/predict_recovery" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_predict_stay_duration" -Method "POST" -NodePath "/api/hospital/predict_stay_duration" -FastPath "/api/hospital/predict_stay_duration" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_predict_performance" -Method "POST" -NodePath "/api/hospital/predict_performance" -FastPath "/api/hospital/predict_performance" -NodeBody $hospBody -FastBody $hospBody
$results += Compare-NodeFastApi -Name "hospital_inventory" -Method "POST" -NodePath "/api/hospital/inventory" -FastPath "/api/hospital/inventory" -NodeBody $hospBody -FastBody $hospBody

# Hospital communication remaining high endpoint
$results += Compare-NodeFastApi -Name "hospital_comm_delete_message" -Method "DELETE" -NodePath "/api/hospital-communication/message/$messageDeleteNodeId" -FastPath "/api/hospital-communication/message/$messageDeleteFastId"

# Ambulance remaining high endpoints
$results += Compare-NodeFastApi -Name "ambulance_create" -Method "POST" -NodePath "/api/ambulance/create" -FastPath "/api/ambulance/create" -NodeBody @{ ambulanceId = $newAmbNode; registrationNumber = "KA-19-$ts"; hospitalId = $hospitalId; driverName = "Node Driver"; licenseNumber = "NODE-$ts"; driverPhone = "9000011111" } -FastBody @{ ambulanceId = $newAmbFast; registrationNumber = "KA-20-$ts"; hospitalId = $hospitalId; driverName = "Fast Driver"; licenseNumber = "FAST-$ts"; driverPhone = "9000022222" }
$results += Compare-NodeFastApi -Name "ambulance_update_location" -Method "POST" -NodePath "/api/ambulance/$ambulanceId/update-location" -FastPath "/api/ambulance/$ambulanceId/update-location" -NodeBody @{ latitude = 12.91; longitude = 74.81; address = "Near City Center" } -FastBody @{ latitude = 12.91; longitude = 74.81; address = "Near City Center" }
$results += Compare-NodeFastApi -Name "ambulance_start_route" -Method "POST" -NodePath "/api/ambulance/$ambulanceId/start-route" -FastPath "/api/ambulance/$ambulanceId/start-route" -NodeBody @{ startLatitude = 12.91; startLongitude = 74.81; startAddress = "Start"; destinationLatitude = 12.95; destinationLongitude = 74.85; destinationAddress = "Destination"; emergencyType = "Cardiac"; priorityLevel = "High" } -FastBody @{ startLatitude = 12.91; startLongitude = 74.81; startAddress = "Start"; destinationLatitude = 12.95; destinationLongitude = 74.85; destinationAddress = "Destination"; emergencyType = "Cardiac"; priorityLevel = "High" }
$results += Compare-NodeFastApi -Name "ambulance_complete_route" -Method "POST" -NodePath "/api/ambulance/$ambulanceId/complete-route" -FastPath "/api/ambulance/$ambulanceId/complete-route"

$summary = [pscustomobject]@{
    checkedAt = (Get-Date).ToString("o")
    nodeBaseUrl = $NodeBaseUrl
    fastApiBaseUrl = $FastApiBaseUrl
    total = $results.Count
    passed = (@($results | Where-Object { $_.pass }).Count)
    failed = (@($results | Where-Object { -not $_.pass }).Count)
    results = $results
}

$summary | ConvertTo-Json -Depth 40 | Out-File -FilePath $OutJson -Encoding utf8

$lines = @()
$lines += "# Remaining High Priority Parity Report"
$lines += ""
$lines += "- Checked at: $($summary.checkedAt)"
$lines += "- Node base URL: $($summary.nodeBaseUrl)"
$lines += "- FastAPI base URL: $($summary.fastApiBaseUrl)"
$lines += "- Total: $($summary.total)"
$lines += "- Passed: $($summary.passed)"
$lines += "- Failed: $($summary.failed)"
$lines += ""
$lines += "| Name | Method | Node Path | FastAPI Path | Status | Missing In FastAPI | Extra In FastAPI |"
$lines += "|---|---|---|---|---|---|---|"
foreach ($r in $results) {
    $statusTxt = if ($r.pass) { "PASS" } elseif ($r.statusMatch) { "KEY MISMATCH" } else { "STATUS MISMATCH ($($r.nodeStatus)/$($r.fastApiStatus))" }
    $missingTxt = if ($r.missingInFast.Count -eq 0) { "-" } else { ($r.missingInFast -join ", ") }
    $extraTxt = if ($r.extraInFast.Count -eq 0) { "-" } else { ($r.extraInFast -join ", ") }
    $lines += "| $($r.name) | $($r.method) | $($r.nodePath) | $($r.fastPath) | $statusTxt | $missingTxt | $extraTxt |"
}

$lines -join "`n" | Out-File -FilePath $OutMd -Encoding utf8

Write-Output "Parity report written: $OutJson"
Write-Output "Parity summary written: $OutMd"
Write-Output "Passed=$($summary.passed), Failed=$($summary.failed), Total=$($summary.total)"
