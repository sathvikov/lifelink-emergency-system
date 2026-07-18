from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.dependencies import get_realtime_service, get_routing_service
from app.db.mongo import get_db
from app.services.collections import ALERTS, AMBULANCE_ASSIGNMENTS, AMBULANCES, NOTIFICATIONS, USERS
from app.services.repository import MongoRepository
from app.services.routing_service import RoutingService

router = APIRouter(tags=["ambulance"])

VALID_STATUSES = ["available", "en_route", "at_location", "returning", "maintenance"]


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def _generate_route_path(lat1: float, lon1: float, lat2: float, lon2: float, points: int = 10) -> list[dict]:
    path = []
    now = datetime.utcnow()
    for i in range(points + 1):
        path.append(
            {
                "latitude": lat1 + (lat2 - lat1) * (i / points),
                "longitude": lon1 + (lon2 - lon1) * (i / points),
                "timestamp": now + timedelta(milliseconds=i * 100),
            }
        )
    return path


def _geometry_to_route_path(geometry: dict | None) -> list[dict]:
    if not geometry or geometry.get("type") != "LineString":
        return []
    coords = geometry.get("coordinates") or []
    now = datetime.utcnow()
    step_seconds = max(3, int(60 / max(1, len(coords))))
    return [
        {
            "latitude": lat,
            "longitude": lng,
            "timestamp": now + timedelta(seconds=idx * step_seconds),
        }
        for idx, (lng, lat) in enumerate(coords)
    ]


def _calculate_average_response_time(history: list[dict]) -> int:
    if not history:
        return 0
    total = sum((trip.get("actualTimeMinutes") or 0) for trip in history)
    return round(total / len(history))


def _calculate_on_time_rate(history: list[dict]) -> int:
    if not history:
        return 100
    on_time = [t for t in history if (t.get("actualTimeMinutes") or 0) <= (t.get("estimatedTimeMinutes") or 0)]
    return round((len(on_time) / len(history)) * 100)


@router.get("/assignments")
async def list_assignments(ambulance_id: str | None = None):
    db = get_db()
    repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    query = {}
    if ambulance_id:
        query["ambulanceId"] = ambulance_id
    records = await repo.find_many(query, sort=[("createdAt", -1)], limit=200)
    return {"count": len(records), "data": records}


@router.post("/assignments", status_code=201)
async def create_assignment(payload: dict = Body(default_factory=dict)):
    db = get_db()
    repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)

    ambulance_id = payload.get("ambulanceId") or payload.get("ambulanceUserId")
    patient = payload.get("patient") or "Unknown"
    emergency_type = payload.get("emergencyType") or "General"

    doc = {
        "ambulanceId": ambulance_id,
        "ambulanceUserId": payload.get("ambulanceUserId"),
        "patient": patient,
        "emergencyType": emergency_type,
        "status": payload.get("status") or "Active",
        "etaMinutes": payload.get("etaMinutes"),
        "pickup": payload.get("pickup"),
        "destination": payload.get("destination"),
        "pickupLocation": payload.get("pickupLocation"),
        "destinationLocation": payload.get("destinationLocation"),
        "patientVitals": payload.get("patientVitals") or {},
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return created


@router.patch("/assignments/{assignment_id}")
async def update_assignment(assignment_id: str, payload: dict = Body(default_factory=dict)):
    db = get_db()
    repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)

    update_data = {k: v for k, v in payload.items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updatedAt"] = datetime.utcnow()

    updated = await repo.update_one({"_id": _as_object_id(assignment_id)}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return updated


@router.get("/patient-info")
async def patient_info(ambulance_id: str | None = None):
    db = get_db()
    repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    query = {"status": {"$in": ["Active", "En Route", "At Location"]}}
    if ambulance_id:
        query["ambulanceId"] = ambulance_id
    records = await repo.find_many(query, sort=[("createdAt", -1)], limit=50)
    payload = []
    for item in records:
        payload.append(
            {
                "id": item.get("_id"),
                "patient": item.get("patient"),
                "emergencyType": item.get("emergencyType"),
                "status": item.get("status"),
                "patientVitals": item.get("patientVitals") or {},
            }
        )
    return {"count": len(payload), "data": payload}


@router.get("/emergency-status")
async def emergency_status():
    db = get_db()
    repo = MongoRepository(db, ALERTS)
    alerts = await repo.find_many({"status": {"$ne": "Resolved"}}, sort=[("createdAt", -1)], limit=200)

    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for alert in alerts:
        severity = alert.get("emergencyType") or alert.get("priority") or "Medium"
        if severity not in severity_counts:
            severity = "Medium"
        severity_counts[severity] += 1

    return {
        "count": len(alerts),
        "severityCounts": severity_counts,
        "alerts": alerts,
    }


@router.get("/history")
async def history(ambulance_id: str | None = None):
    db = get_db()
    repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    query = {"status": {"$in": ["Completed", "Resolved", "Closed"]}}
    if ambulance_id:
        query["ambulanceId"] = ambulance_id
    records = await repo.find_many(query, sort=[("updatedAt", -1)], limit=200)
    return {"count": len(records), "data": records}


@router.get("/")
async def get_all_ambulances():
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    docs = await repo.find_many(
        {},
        projection={
            "ambulanceId": 1,
            "registrationNumber": 1,
            "status": 1,
            "currentLocation": 1,
            "etaPrediction": 1,
            "activeRoute": 1,
            "metrics": 1,
            "driver": 1,
        },
    )

    return {"success": True, "count": len(docs), "data": docs}


@router.get("/hospital/{hospital_id}")
async def get_ambulances_by_hospital(hospital_id: str):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    docs = await repo.find_many(
        {"hospital": _as_object_id(hospital_id)},
        projection={
            "ambulanceId": 1,
            "registrationNumber": 1,
            "status": 1,
            "currentLocation": 1,
            "etaPrediction": 1,
            "activeRoute": 1,
            "metrics": 1,
        },
    )

    return {"success": True, "count": len(docs), "data": docs}


@router.get("/{ambulance_id}")
async def get_ambulance_details(ambulance_id: str):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    doc = await repo.find_one({"_id": _as_object_id(ambulance_id)})
    if not doc:
        return {"success": False, "error": "Ambulance not found"}

    return {"success": True, "data": doc}


@router.post("/create", status_code=201)
async def create_ambulance(payload: dict = Body(default_factory=dict)):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    ambulance_id = payload.get("ambulanceId")
    registration_number = payload.get("registrationNumber")
    hospital_id = payload.get("hospitalId")

    if not ambulance_id or not registration_number or not hospital_id:
        return {"success": False, "error": "Missing required fields: ambulanceId, registrationNumber, hospitalId"}

    existing = await repo.find_one({"ambulanceId": ambulance_id})
    if existing:
        return {"success": False, "error": "Ambulance with this ID already exists"}

    doc = {
        "ambulanceId": ambulance_id,
        "registrationNumber": registration_number,
        "hospital": _as_object_id(hospital_id),
        "status": "available",
        "driver": {
            "name": payload.get("driverName") or "Unassigned",
            "licenseNumber": payload.get("licenseNumber"),
            "phone": payload.get("driverPhone"),
            "availability": True,
        },
        "metrics": {
            "averageResponseTime": 0,
            "onTimeDeliveryRate": 100,
            "totalTripsToday": 0,
            "totalDistanceTodayKm": 0,
        },
        "travelHistory": [],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return {"success": True, "message": "Ambulance created successfully", "data": created}


@router.post("/{ambulance_id}/update-location")
async def update_ambulance_location(ambulance_id: str, payload: dict = Body(default_factory=dict)):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if latitude is None or longitude is None:
        return {"success": False, "error": "Latitude and longitude required"}

    current_location = {
        "latitude": latitude,
        "longitude": longitude,
        "address": payload.get("address") or "Location Updated",
        "timestamp": datetime.utcnow(),
    }

    updated = await repo.update_one(
        {"_id": _as_object_id(ambulance_id)},
        {
            "$set": {
                "currentLocation": current_location,
                "lastLocationUpdate": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        },
        return_new=True,
    )

    if not updated:
        return {"success": False, "error": "Ambulance not found"}

    realtime = get_realtime_service()
    await realtime.broadcast(
        "ambulance",
        {
            "type": "location_update",
            "ambulanceId": updated.get("ambulanceId"),
            "payload": updated.get("currentLocation"),
        },
    )

    return {"success": True, "message": "Location updated", "data": updated.get("currentLocation")}


@router.post("/{ambulance_id}/start-route")
async def start_route(
    ambulance_id: str,
    payload: dict = Body(default_factory=dict),
    routing: RoutingService = Depends(get_routing_service),
):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    ambulance = await repo.find_one({"_id": _as_object_id(ambulance_id)})
    if not ambulance:
        return {"success": False, "error": "Ambulance not found"}

    start_lat = float(payload.get("startLatitude"))
    start_lon = float(payload.get("startLongitude"))
    dest_lat = float(payload.get("destinationLatitude"))
    dest_lon = float(payload.get("destinationLongitude"))

    distance_km = _calculate_distance(start_lat, start_lon, dest_lat, dest_lon)
    estimated_minutes = max(1, round(distance_km / 1.5))
    now = datetime.utcnow()
    route_path = [{"latitude": start_lat, "longitude": start_lon, "timestamp": now}]

    try:
        route = await routing.route(start_lat, start_lon, dest_lat, dest_lon, include_geometry=True)
        if route.get("status") == "ok":
            if route.get("distance_meters"):
                distance_km = (route.get("distance_meters") or 0) / 1000
            if route.get("duration_seconds"):
                estimated_minutes = max(1, round((route.get("duration_seconds") or 0) / 60))
            route_path = _geometry_to_route_path(route.get("geometry")) or route_path
    except Exception:
        pass

    metrics = ambulance.get("metrics") or {}
    active_route = {
        "startLocation": {
            "latitude": start_lat,
            "longitude": start_lon,
            "address": payload.get("startAddress"),
        },
        "destinationLocation": {
            "latitude": dest_lat,
            "longitude": dest_lon,
            "address": payload.get("destinationAddress"),
        },
        "routePath": route_path,
        "distanceKm": distance_km,
        "estimatedTimeMinutes": estimated_minutes,
        "startTime": now,
        "estimatedArrivalTime": now + timedelta(minutes=estimated_minutes),
    }

    updated = await repo.update_one(
        {"_id": _as_object_id(ambulance_id)},
        {
            "$set": {
                "status": "en_route",
                "activeRoute": active_route,
                "emergencyType": payload.get("emergencyType"),
                "priorityLevel": payload.get("priorityLevel") or "Medium",
                "metrics.totalTripsToday": int(metrics.get("totalTripsToday") or 0) + 1,
                "metrics.totalDistanceTodayKm": float(metrics.get("totalDistanceTodayKm") or 0) + distance_km,
                "updatedAt": now,
            }
        },
        return_new=True,
    )

    realtime = get_realtime_service()
    await realtime.broadcast(
        "ambulance",
        {
            "type": "route_started",
            "ambulanceId": (updated or {}).get("ambulanceId") or ambulance.get("ambulanceId"),
            "payload": (updated or {}).get("activeRoute") or active_route,
        },
    )

    db = get_db()
    notification_repo = MongoRepository(db, NOTIFICATIONS)
    user_repo = MongoRepository(db, USERS)
    hospital_name = payload.get("destinationAddress") or (updated or {}).get("activeRoute", active_route).get("destinationLocation", {}).get("address") or "Hospital"
    ambulance_code = (updated or {}).get("ambulanceId") or ambulance.get("ambulanceId")
    hospital_users = await user_repo.find_many({"role": "hospital"}, limit=200)
    for hospital_user in hospital_users:
        user_oid = _as_object_id(hospital_user.get("_id"))
        if not user_oid:
            continue
        await notification_repo.insert_one(
            {
                "user": user_oid,
                "type": "ambulance_route",
                "title": "Ambulance En Route",
                "message": f"{ambulance_code} is en route to {hospital_name}. Open live tracking to monitor the route.",
                "createdAt": datetime.utcnow(),
                "read": False,
                "metadata": {
                    "ambulance_id": (updated or {}).get("_id") or ambulance.get("_id"),
                    "ambulance_code": ambulance_code,
                    "hospital_name": hospital_name,
                    "route": "/dashboard/hospital/ambulance-tracking",
                    "actionLabel": "View Live Route",
                },
            }
        )

    return {
        "success": True,
        "message": "Route started",
        "data": {
            "ambulanceId": updated.get("ambulanceId") if updated else ambulance.get("ambulanceId"),
            "status": updated.get("status") if updated else "en_route",
            "activeRoute": updated.get("activeRoute") if updated else active_route,
            "estimatedArrivalTime": (updated or {}).get("activeRoute", active_route).get("estimatedArrivalTime"),
        },
    }


@router.post("/{ambulance_id}/predict-eta")
async def predict_eta(ambulance_id: str, payload: dict = Body(default_factory=dict)):
    current_lat = float(payload.get("currentLatitude"))
    current_lon = float(payload.get("currentLongitude"))
    dest_lat = float(payload.get("destinationLatitude"))
    dest_lon = float(payload.get("destinationLongitude"))

    remaining_distance = _calculate_distance(current_lat, current_lon, dest_lat, dest_lon)
    estimated_minutes = max(1, round((remaining_distance / 40) * 60))

    traffic = payload.get("trafficLevel")
    traffic_factor = 0.95
    if traffic == "high":
        traffic_factor = 0.7
    elif traffic == "medium":
        traffic_factor = 0.85

    eta_prediction = {
        "estimatedMinutes": estimated_minutes,
        "confidenceLevel": "Medium",
        "trafficFactor": traffic_factor,
        "weatherCondition": payload.get("weather") or "clear",
        "lastUpdated": datetime.utcnow(),
    }

    return {
        "success": True,
        "message": "ETA calculated",
        "data": {
            "ambulanceId": ambulance_id,
            "etaPrediction": eta_prediction,
            "remainingDistance": f"{remaining_distance:.2f}",
        },
    }


@router.post("/{ambulance_id}/get-route")
async def get_route(
    ambulance_id: str,
    payload: dict = Body(default_factory=dict),
    routing: RoutingService = Depends(get_routing_service),
):
    required = ["startLatitude", "startLongitude", "destinationLatitude", "destinationLongitude"]
    if any(payload.get(k) is None for k in required):
        return {"success": False, "error": "Missing coordinates"}

    start_lat = float(payload.get("startLatitude"))
    start_lon = float(payload.get("startLongitude"))
    dest_lat = float(payload.get("destinationLatitude"))
    dest_lon = float(payload.get("destinationLongitude"))
    include_geometry = bool(payload.get("includeGeometry") or payload.get("include_geometry"))

    distance_km = _calculate_distance(start_lat, start_lon, dest_lat, dest_lon)
    estimated_time = max(1, round(distance_km / 1.5))
    route_path = _generate_route_path(start_lat, start_lon, dest_lat, dest_lon, 10)

    try:
        route = await routing.route(start_lat, start_lon, dest_lat, dest_lon, include_geometry=include_geometry)
        if route.get("status") == "ok":
            if route.get("distance_meters"):
                distance_km = (route.get("distance_meters") or 0) / 1000
            if route.get("duration_seconds"):
                estimated_time = max(1, round((route.get("duration_seconds") or 0) / 60))
            if include_geometry:
                route_path = _geometry_to_route_path(route.get("geometry")) or route_path
    except Exception:
        pass

    return {
        "success": True,
        "data": {
            "ambulanceId": ambulance_id,
            "distance": f"{distance_km:.2f}",
            "estimatedMinutes": estimated_time,
            "routePath": route_path,
            "alternateRoutes": [
                {
                    "name": "Fastest Route",
                    "distance": f"{distance_km * 0.95:.2f}",
                    "estimatedMinutes": max(1, round(estimated_time * 0.9)),
                },
                {
                    "name": "Scenic Route",
                    "distance": f"{distance_km * 1.15:.2f}",
                    "estimatedMinutes": max(1, round(estimated_time * 1.1)),
                },
            ],
        },
    }


@router.post("/{ambulance_id}/complete-route")
async def complete_route(ambulance_id: str):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    ambulance = await repo.find_one({"_id": _as_object_id(ambulance_id)})
    if not ambulance:
        return {"success": False, "error": "Ambulance not found"}

    active_route = ambulance.get("activeRoute")
    if not active_route:
        return {"success": False, "error": "No active route"}

    start_time_raw = active_route.get("startTime")
    start_time = datetime.fromisoformat(start_time_raw) if isinstance(start_time_raw, str) else (start_time_raw or datetime.utcnow())

    actual_time_minutes = max(1, round((datetime.utcnow() - start_time).total_seconds() / 60))
    estimated_time_minutes = int(active_route.get("estimatedTimeMinutes") or 1)
    prediction_accuracy = round((estimated_time_minutes / actual_time_minutes) * 100)

    history = ambulance.get("travelHistory") or []
    history.append(
        {
            "date": datetime.utcnow(),
            "startLocation": active_route.get("startLocation"),
            "endLocation": active_route.get("destinationLocation"),
            "distanceKm": active_route.get("distanceKm") or 0,
            "actualTimeMinutes": actual_time_minutes,
            "estimatedTimeMinutes": estimated_time_minutes,
            "trafficCondition": "completed",
            "weather": "clear",
            "predictionAccuracy": prediction_accuracy,
        }
    )

    avg_response = _calculate_average_response_time(history)
    on_time_rate = _calculate_on_time_rate(history)

    await repo.update_one(
        {"_id": _as_object_id(ambulance_id)},
        {
            "$set": {
                "status": "at_location",
                "activeRoute.actualArrivalTime": datetime.utcnow(),
                "travelHistory": history,
                "metrics.averageResponseTime": avg_response,
                "metrics.onTimeDeliveryRate": on_time_rate,
                "updatedAt": datetime.utcnow(),
            }
        },
        return_new=False,
    )

    latest = await repo.find_one({"_id": _as_object_id(ambulance_id)})
    return {
        "success": True,
        "message": "Route completed",
        "data": {
            "ambulanceId": latest.get("ambulanceId") if latest else ambulance.get("ambulanceId"),
            "actualTimeMinutes": actual_time_minutes,
            "estimatedTimeMinutes": estimated_time_minutes,
            "predictionAccuracy": f"{prediction_accuracy}%",
            "metrics": (latest or {}).get("metrics") or {},
        },
    }


@router.put("/{ambulance_id}/status")
async def update_status(ambulance_id: str, payload: dict = Body(default_factory=dict)):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    status = payload.get("status")
    if status not in VALID_STATUSES:
        return {"success": False, "error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}

    updated = await repo.update_one(
        {"_id": _as_object_id(ambulance_id)},
        {"$set": {"status": status, "updatedAt": datetime.utcnow()}},
        return_new=True,
    )
    if not updated:
        return {"success": False, "error": "Ambulance not found"}

    return {"success": True, "message": "Status updated", "data": {"ambulanceId": updated.get("ambulanceId"), "status": updated.get("status")}}


@router.get("/{ambulance_id}/metrics")
async def get_metrics(ambulance_id: str):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)

    ambulance = await repo.find_one({"_id": _as_object_id(ambulance_id)})
    if not ambulance:
        return {"success": False, "error": "Ambulance not found"}

    history = ambulance.get("travelHistory") or []
    return {
        "success": True,
        "data": {
            "ambulanceId": ambulance.get("ambulanceId"),
            "metrics": ambulance.get("metrics") or {},
            "travelHistoryCount": len(history),
            "lastTrip": history[-1] if history else None,
        },
    }
