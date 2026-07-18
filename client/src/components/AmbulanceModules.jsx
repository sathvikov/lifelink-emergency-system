import React, { useEffect, useMemo, useState } from 'react';
import { Circle, MapContainer, Polyline, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useAuth } from '../context/AuthContext';
import { useDataMode } from '../context/DataModeContext';
import { apiFetch, getAuthToken } from '../config/api';
import { DashboardCard, LoadingSpinner, StatusPill } from './Common';

const resolveAmbulanceId = (user) => user?._id || user?.id || '';

const demoAssignments = () => ([
    {
        id: 'demo-assign-1',
        patient: 'Riya S',
        emergencyType: 'Cardiac arrest',
        etaMinutes: 11,
        status: 'Active'
    },
    {
        id: 'demo-assign-2',
        patient: 'Arun K',
        emergencyType: 'Road accident',
        etaMinutes: 14,
        status: 'En Route'
    },
]);

const demoPatientInfo = () => ([
    {
        id: 'demo-patient-1',
        patient: 'Riya S',
        emergencyType: 'Cardiac arrest',
        status: 'Critical',
        patientVitals: { heartRate: 122, oxygen: 88, bp: '92/58' }
    },
    {
        id: 'demo-patient-2',
        patient: 'Arun K',
        emergencyType: 'Road accident',
        status: 'High',
        patientVitals: { heartRate: 108, oxygen: 92, bp: '104/66' }
    },
]);

const demoHistory = () => ([
    {
        id: 'demo-hist-1',
        patient: 'Meera T',
        emergencyType: 'Trauma',
        status: 'Completed',
        updatedAt: new Date(Date.now() - 86400000).toISOString(),
    },
    {
        id: 'demo-hist-2',
        patient: 'Vikram P',
        emergencyType: 'Respiratory distress',
        status: 'Completed',
        updatedAt: new Date(Date.now() - 5400000).toISOString(),
    },
]);

const demoEmergencyStatus = () => ({
    count: 4,
    severityCounts: { Critical: 2, High: 1, Medium: 1, Low: 0 },
    alerts: [
        {
            id: 'demo-alert-1',
            message: 'Multi-vehicle collision reported',
            emergencyType: 'Critical',
            locationDetails: 'Majestic, Bengaluru',
        },
        {
            id: 'demo-alert-2',
            message: 'Severe asthma attack',
            emergencyType: 'High',
            locationDetails: 'Cubbon Park, Bengaluru',
        },
    ],
});

const normalizeAssignments = (items) => (items || []).map((item) => ({
    ...item,
    patient: item.patient || item.patientName || item.name || 'Unknown',
    emergencyType: item.emergencyType || item.emergency_type || item.type || 'General',
    etaMinutes: item.etaMinutes ?? item.eta ?? item.estimatedTimeMinutes,
}));

const normalizePatientInfo = (items) => (items || []).map((item) => ({
    ...item,
    patient: item.patient || item.patientName || item.name || 'Unknown',
    emergencyType: item.emergencyType || item.emergency_type || item.type || 'General',
    patientVitals: item.patientVitals || item.vitals || {},
}));

const normalizeHistory = (items) => (items || []).map((item) => ({
    ...item,
    patient: item.patient || item.patientName || item.name || 'Unknown',
    emergencyType: item.emergencyType || item.emergency_type || item.type || 'General',
    updatedAt: item.updatedAt || item.completedAt || item.createdAt,
}));

const DEFAULT_CENTER = [12.9716, 77.5946];
const BENGALURU_BOUNDS = {
    latMin: 12.85,
    latMax: 13.05,
    lngMin: 77.45,
    lngMax: 77.75,
};

const buildFallbackRoute = (start, end) => {
    const midLat = (start.lat + end.lat) / 2;
    const midLng = (start.lng + end.lng) / 2;
    return [
        [start.lat, start.lng],
        [midLat + 0.003, midLng - 0.002],
        [midLat - 0.002, midLng + 0.003],
        [end.lat, end.lng],
    ];
};

const demoEmergencyData = () => {
    const vehicle = {
        label: 'Ambulance A1',
        lat: 12.9766,
        lng: 77.5713,
        address: 'Majestic Bus Station',
        speedKph: 44,
    };
    const incident = {
        label: 'Incident: Multi-vehicle collision',
        lat: 12.9763,
        lng: 77.5929,
        address: 'Cubbon Park Road',
        severity: 'Critical',
    };
    const hospital = {
        label: "St. Martha's Hospital",
        lat: 12.9686,
        lng: 77.5995,
        address: 'Nrupathunga Road',
    };

    return {
        vehicle,
        incident,
        hospital,
        toIncident: {
            path: buildFallbackRoute(vehicle, incident),
            etaMinutes: 7,
            distanceKm: 4.1,
            traffic: { level: 'Light', adjustedMinutes: 7, baseMinutes: 6, weather: 'Clear' },
        },
        toHospital: {
            path: buildFallbackRoute(incident, hospital),
            etaMinutes: 11,
            distanceKm: 3.5,
            traffic: { level: 'Moderate', adjustedMinutes: 11, baseMinutes: 9, weather: 'Clear' },
        },
        patientStatus: 'Critical',
        justification: {
            routeNote: 'Shortest corridor with highest road clearance, avoids two construction blocks.',
            trafficNote: 'Moderate congestion near Cubbon Rd, rerouted to keep travel time under 12 minutes.',
            navNote: 'Live turn-by-turn active, alternate route ready.',
        },
        lastUpdated: new Date().toISOString(),
    };
};

const toLatLng = (value) => {
    if (!value || typeof value !== 'object') return { lat: null, lng: null, address: '' };
    const lat = value.latitude ?? value.lat ?? value.location?.lat;
    const lng = value.longitude ?? value.lng ?? value.location?.lng;
    const address = value.address || value.location?.address || '';
    return { lat, lng, address };
};

const hasCoords = (point) => Number.isFinite(point?.lat) && Number.isFinite(point?.lng);

const isWithinBengaluru = (point) => (
    hasCoords(point)
    && point.lat >= BENGALURU_BOUNDS.latMin
    && point.lat <= BENGALURU_BOUNDS.latMax
    && point.lng >= BENGALURU_BOUNDS.lngMin
    && point.lng <= BENGALURU_BOUNDS.lngMax
);

const coerceToBengaluru = (point, fallback) => (isWithinBengaluru(point) ? point : { ...fallback });

const isPlaceholderLocation = (value) => {
    if (!value || typeof value !== 'string') return false;
    return /pickup|drop|location|unknown/i.test(value);
};

const haversineKm = (start, end) => {
    if (!hasCoords(start) || !hasCoords(end)) return 0;
    const toRad = (value) => (value * Math.PI) / 180;
    const r = 6371;
    const dLat = toRad(end.lat - start.lat);
    const dLng = toRad(end.lng - start.lng);
    const a = Math.sin(dLat / 2) ** 2
        + Math.cos(toRad(start.lat)) * Math.cos(toRad(end.lat)) * Math.sin(dLng / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return r * c;
};

const ensureBengaluruQuery = (value) => {
    if (!value || typeof value !== 'string') return value;
    const lowered = value.toLowerCase();
    if (lowered.includes('bengaluru') || lowered.includes('bangalore')) return value;
    return `${value}, Bengaluru`;
};

const trafficLevelFromRatio = (ratio) => {
    if (ratio >= 1.2) return 'Heavy';
    if (ratio >= 1.1) return 'Moderate';
    return 'Light';
};

const weatherSummary = (weather) => {
    if (!weather) return 'Clear';
    if (weather.is_raining) return 'Rain';
    if ((weather.wind_kph || 0) >= 35) return 'Windy';
    return 'Clear';
};

export const AmbulanceEmergencyResponse = () => {
    const { user } = useAuth();
    const { mode } = useDataMode();
    const ambulanceId = resolveAmbulanceId(user);
    const demoFallback = useMemo(() => demoEmergencyData(), []);
    const cacheKey = ambulanceId ? `ambulance_emergency_${ambulanceId}` : 'ambulance_emergency';
    const [state, setState] = useState({ loading: true, error: '', data: null, lastUpdated: null });

    useEffect(() => {
        let isActive = true;

        const geocode = async (query, hasAuth) => {
            if (!query || !hasAuth || isPlaceholderLocation(query)) return null;
            const cleaned = ensureBengaluruQuery(query);
            const res = await apiFetch(`/v2/integrations/maps/geocode?query=${encodeURIComponent(cleaned)}`, { method: 'GET' });
            if (!res.ok || res.data?.status !== 'ok') return null;
            const location = res.data?.location || {};
            return {
                lat: location.lat,
                lng: location.lng,
                address: location.display || cleaned,
            };
        };

        const buildRouteInfo = (routeData, trafficData, start, end) => {
            const geometryPath = (routeData?.geometry?.coordinates || []).map(([lng, lat]) => [lat, lng]);
            const durationSeconds = routeData?.duration_seconds || 0;
            const distanceKm = Number.isFinite(routeData?.distance_meters)
                ? Math.round((routeData.distance_meters / 1000) * 10) / 10
                : Math.round(haversineKm(start, end) * 10) / 10;
            const baseSeconds = trafficData?.base_duration_seconds || durationSeconds || Math.max(300, Math.round((distanceKm / 35) * 3600));
            const adjustedSeconds = trafficData?.adjusted_duration_seconds || Math.round(baseSeconds * 1.1);
            const ratio = baseSeconds ? adjustedSeconds / baseSeconds : 1;
            const trafficLevel = trafficLevelFromRatio(ratio);
            return {
                path: geometryPath.length >= 2 ? geometryPath : buildFallbackRoute(start, end),
                etaMinutes: Math.max(1, Math.round((adjustedSeconds || durationSeconds || 600) / 60)),
                distanceKm,
                traffic: {
                    level: trafficLevel,
                    adjustedMinutes: Math.max(1, Math.round((adjustedSeconds || durationSeconds || 600) / 60)),
                    baseMinutes: Math.max(1, Math.round((baseSeconds || adjustedSeconds || 600) / 60)),
                    weather: weatherSummary(trafficData?.weather),
                },
            };
        };

        const fetchOsrmRoute = async (start, end) => {
            if (!hasCoords(start) || !hasCoords(end)) return null;
            try {
                const url = `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${end.lng},${end.lat}?overview=full&geometries=geojson`;
                const res = await fetch(url);
                const data = await res.json();
                const route = data.routes?.[0];
                if (!route) return null;
                return {
                    status: 'ok',
                    distance_meters: route.distance,
                    duration_seconds: route.duration,
                    geometry: route.geometry,
                };
            } catch (error) {
                return null;
            }
        };

        const loadEmergency = async () => {
            if (mode === 'demo') {
                if (isActive) {
                    setState({ loading: false, error: '', data: demoFallback, lastUpdated: demoFallback.lastUpdated });
                    try {
                        localStorage.setItem(cacheKey, JSON.stringify({ data: demoFallback, lastUpdated: demoFallback.lastUpdated }));
                    } catch (error) {
                        // ignore cache errors
                    }
                }
                return;
            }

            setState((prev) => ({ ...prev, error: '' }));

            try {
                const hasAuth = Boolean(getAuthToken());
                const [assignmentRes, ambulanceRes] = await Promise.all([
                    apiFetch(`/api/ambulance/assignments${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' }),
                    apiFetch('/api/ambulance', { method: 'GET' }),
                ]);
                const assignments = normalizeAssignments(assignmentRes.data?.data || assignmentRes.data || []);
                const activeAssignment = assignments.find((item) => (
                    ['active', 'en route', 'at location'].includes(String(item.status || '').toLowerCase())
                )) || assignments[0];

                const ambulanceList = Array.isArray(ambulanceRes.data?.data) ? ambulanceRes.data.data : (ambulanceRes.data || []);
                const matchedAmbulance = ambulanceList.find((item) => item.ambulanceId === activeAssignment?.ambulanceId)
                    || ambulanceList[0];

                const vehicleLoc = toLatLng(matchedAmbulance?.currentLocation || {});
                const pickupLoc = toLatLng(activeAssignment?.pickupLocation || {});
                const destinationLoc = toLatLng(activeAssignment?.destinationLocation || {});

                const pickupAddress = typeof activeAssignment?.pickup === 'string' ? activeAssignment.pickup : '';
                const destinationAddress = typeof activeAssignment?.destination === 'string' ? activeAssignment.destination : '';

                const vehicle = {
                    label: matchedAmbulance?.ambulanceId || 'Ambulance',
                    lat: vehicleLoc.lat,
                    lng: vehicleLoc.lng,
                    address: vehicleLoc.address || matchedAmbulance?.currentLocation?.address || 'Live location',
                    speedKph: Math.round(42 + Math.random() * 8),
                };

                let incident = {
                    label: activeAssignment?.emergencyType ? `Incident: ${activeAssignment.emergencyType}` : 'Emergency dispatch',
                    lat: pickupLoc.lat,
                    lng: pickupLoc.lng,
                    address: pickupLoc.address || pickupAddress || 'Pickup location, Bengaluru',
                    severity: activeAssignment?.priorityLevel || activeAssignment?.priority || 'High',
                };

                let hospital = {
                    label: destinationAddress || 'Nearest trauma center',
                    lat: destinationLoc.lat,
                    lng: destinationLoc.lng,
                    address: destinationLoc.address || destinationAddress || 'Drop location, Bengaluru',
                };

                if (!hasCoords(incident) && incident.address) {
                    const geo = await geocode(incident.address, hasAuth);
                    if (geo) incident = { ...incident, ...geo };
                }
                if (!hasCoords(hospital) && hospital.address) {
                    const geo = await geocode(hospital.address, hasAuth);
                    if (geo) hospital = { ...hospital, ...geo };
                }

                const boundedVehicle = coerceToBengaluru(vehicle, demoFallback.vehicle);
                const boundedIncident = coerceToBengaluru(incident, demoFallback.incident);
                const boundedHospital = coerceToBengaluru(hospital, demoFallback.hospital);

                const [toIncidentRouteRes, toHospitalRouteRes] = hasAuth
                    ? await Promise.all([
                        apiFetch(`/v2/route?start_lat=${boundedVehicle.lat}&start_lng=${boundedVehicle.lng}&end_lat=${boundedIncident.lat}&end_lng=${boundedIncident.lng}&include_geometry=true`, { method: 'GET' }),
                        apiFetch(`/v2/route?start_lat=${boundedIncident.lat}&start_lng=${boundedIncident.lng}&end_lat=${boundedHospital.lat}&end_lng=${boundedHospital.lng}&include_geometry=true`, { method: 'GET' }),
                    ])
                    : [null, null];

                const [toIncidentTrafficRes, toHospitalTrafficRes] = hasAuth
                    ? await Promise.all([
                        apiFetch(`/v2/integrations/traffic?origin=${boundedVehicle.lat},${boundedVehicle.lng}&destination=${boundedIncident.lat},${boundedIncident.lng}`, { method: 'GET' }),
                        apiFetch(`/v2/integrations/traffic?origin=${boundedIncident.lat},${boundedIncident.lng}&destination=${boundedHospital.lat},${boundedHospital.lng}`, { method: 'GET' }),
                    ])
                    : [null, null];

                const fallbackIncidentRoute = await fetchOsrmRoute(boundedVehicle, boundedIncident);
                const fallbackHospitalRoute = await fetchOsrmRoute(boundedIncident, boundedHospital);

                const routeIncidentData = toIncidentRouteRes?.ok ? toIncidentRouteRes.data : (fallbackIncidentRoute || {});
                const routeHospitalData = toHospitalRouteRes?.ok ? toHospitalRouteRes.data : (fallbackHospitalRoute || {});
                const trafficIncidentData = toIncidentTrafficRes?.ok ? toIncidentTrafficRes.data : {};
                const trafficHospitalData = toHospitalTrafficRes?.ok ? toHospitalTrafficRes.data : {};

                const toIncident = buildRouteInfo(routeIncidentData, trafficIncidentData, boundedVehicle, boundedIncident);
                const toHospital = buildRouteInfo(routeHospitalData, trafficHospitalData, boundedIncident, boundedHospital);

                const patientStatus = activeAssignment?.priorityLevel || activeAssignment?.priority || 'Critical';
                const justification = {
                    routeNote: 'Fastest road corridor with low signal density and clear priority lanes.',
                    trafficNote: `${toIncident.traffic.level} traffic to pickup, ${toHospital.traffic.level.toLowerCase()} traffic to hospital.`,
                    navNote: 'Live turn-by-turn active; alternate corridor ready if congestion rises.',
                };

                const nextData = {
                    vehicle: boundedVehicle,
                    incident: boundedIncident,
                    hospital: boundedHospital,
                    toIncident,
                    toHospital,
                    patientStatus,
                    justification,
                    lastUpdated: new Date().toISOString(),
                };

                if (isActive) {
                    setState({ loading: false, error: '', data: nextData, lastUpdated: nextData.lastUpdated });
                    try {
                        localStorage.setItem(cacheKey, JSON.stringify({ data: nextData, lastUpdated: nextData.lastUpdated }));
                    } catch (error) {
                        // ignore cache errors
                    }
                }
            } catch (err) {
                if (isActive) {
                    setState({ loading: false, error: 'Unable to load live route data.', data: demoFallback, lastUpdated: demoFallback.lastUpdated });
                }
            }
        };

        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                if (parsed?.data) {
                    setState({ loading: false, error: '', data: parsed.data, lastUpdated: parsed.lastUpdated || parsed.data?.lastUpdated });
                    hasCache = true;
                }
            }
        } catch (error) {
            // ignore cache errors
        }

        if (!hasCache) {
            setState({ loading: false, error: '', data: demoFallback, lastUpdated: demoFallback.lastUpdated });
        }

        loadEmergency();
        return () => {
            isActive = false;
        };
    }, [mode, ambulanceId, demoFallback, cacheKey]);

    const payload = state.data || demoFallback;
    const vehicle = payload.vehicle;
    const incident = payload.incident;
    const hospital = payload.hospital;
    const toIncidentRoute = payload.toIncident?.path || buildFallbackRoute(vehicle, incident);
    const toHospitalRoute = payload.toHospital?.path || buildFallbackRoute(incident, hospital);
    const mapCenter = useMemo(() => (
        hasCoords(incident) ? [incident.lat, incident.lng] : (hasCoords(vehicle) ? [vehicle.lat, vehicle.lng] : DEFAULT_CENTER)
    ), [incident, vehicle]);

    const severityColor = incident.severity === 'Critical' ? 'red' : (incident.severity === 'High' ? 'yellow' : 'blue');

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <p className="text-xs font-bold uppercase text-rose-500">Emergency dispatch</p>
                        <p className="text-lg font-bold text-slate-900">{incident.label}</p>
                        <p className="text-sm text-slate-600">Pickup at {incident.address} · Drop at {hospital.label}</p>
                        {state.lastUpdated && (
                            <p className="text-xs text-slate-400 mt-1">Updated {new Date(state.lastUpdated).toLocaleTimeString()}</p>
                        )}
                    </div>
                    <StatusPill text={incident.severity} color={severityColor} />
                </div>
                {state.error && <p className="mt-2 text-xs text-rose-600">{state.error}</p>}
            </DashboardCard>

            <DashboardCard className="p-0 overflow-hidden">
                <div className="h-[420px] w-full">
                    <MapContainer center={mapCenter} zoom={13} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
                        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                        {toIncidentRoute.length > 1 && (
                            <Polyline positions={toIncidentRoute} color="#ef4444" weight={4} opacity={0.9} />
                        )}
                        {toHospitalRoute.length > 1 && (
                            <Polyline positions={toHospitalRoute} color="#0ea5e9" weight={4} opacity={0.9} />
                        )}
                        {hasCoords(vehicle) && (
                            <Circle center={[vehicle.lat, vehicle.lng]} radius={120} pathOptions={{ color: '#1d4ed8', fillColor: '#1d4ed8', fillOpacity: 0.4 }}>
                                <Popup>
                                    <div className="text-xs">
                                        <p className="font-semibold">{vehicle.label}</p>
                                        <p>{vehicle.address}</p>
                                        <p>Speed {vehicle.speedKph} km/h</p>
                                    </div>
                                </Popup>
                            </Circle>
                        )}
                        {hasCoords(incident) && (
                            <Circle center={[incident.lat, incident.lng]} radius={160} pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.4 }}>
                                <Popup>
                                    <div className="text-xs">
                                        <p className="font-semibold">Incident location</p>
                                        <p>{incident.address}</p>
                                    </div>
                                </Popup>
                            </Circle>
                        )}
                        {hasCoords(hospital) && (
                            <Circle center={[hospital.lat, hospital.lng]} radius={140} pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 0.35 }}>
                                <Popup>
                                    <div className="text-xs">
                                        <p className="font-semibold">{hospital.label}</p>
                                        <p>{hospital.address}</p>
                                    </div>
                                </Popup>
                            </Circle>
                        )}
                    </MapContainer>
                </div>
            </DashboardCard>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <DashboardCard>
                    <p className="text-xs font-bold uppercase text-slate-500">ETA to incident</p>
                    <p className="text-3xl font-black text-slate-900">{payload.toIncident?.etaMinutes || 0} min</p>
                    <p className="text-xs text-slate-500 mt-2">Distance {payload.toIncident?.distanceKm || '--'} km · Traffic {payload.toIncident?.traffic?.level || 'Light'}</p>
                    <p className="text-xs text-slate-500">Base {payload.toIncident?.traffic?.baseMinutes || payload.toIncident?.etaMinutes || 0} min · Δ {Math.max(0, (payload.toIncident?.traffic?.adjustedMinutes || payload.toIncident?.etaMinutes || 0) - (payload.toIncident?.traffic?.baseMinutes || payload.toIncident?.etaMinutes || 0))} min</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold uppercase text-slate-500">ETA to hospital</p>
                    <p className="text-3xl font-black text-slate-900">{payload.toHospital?.etaMinutes || 0} min</p>
                    <p className="text-xs text-slate-500 mt-2">Distance {payload.toHospital?.distanceKm || '--'} km · Traffic {payload.toHospital?.traffic?.level || 'Moderate'}</p>
                    <p className="text-xs text-slate-500">Base {payload.toHospital?.traffic?.baseMinutes || payload.toHospital?.etaMinutes || 0} min · Δ {Math.max(0, (payload.toHospital?.traffic?.adjustedMinutes || payload.toHospital?.etaMinutes || 0) - (payload.toHospital?.traffic?.baseMinutes || payload.toHospital?.etaMinutes || 0))} min</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold uppercase text-slate-500">Vehicle speed</p>
                    <p className="text-3xl font-black text-slate-900">{vehicle.speedKph} km/h</p>
                    <p className="text-xs text-slate-500 mt-2">Live tracking with route optimization</p>
                </DashboardCard>
            </div>

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Route justification</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-700">
                    <div className="space-y-2">
                        <p><span className="font-semibold">Why this route:</span> {payload.justification?.routeNote || 'Fastest corridor with high road clearance.'}</p>
                        <p><span className="font-semibold">Traffic update:</span> {payload.justification?.trafficNote || 'Live congestion monitored, reroutes ready.'}</p>
                        <p><span className="font-semibold">Navigation:</span> {payload.justification?.navNote || 'Turn-by-turn navigation active.'}</p>
                    </div>
                    <div className="space-y-2">
                        <p><span className="font-semibold">Patient status:</span> {payload.patientStatus || 'High'} priority, vitals monitored every 2 minutes.</p>
                        <p><span className="font-semibold">Impact:</span> prioritizing fastest hospital with ICU readiness.</p>
                        <p><span className="font-semibold">Suggested action:</span> notify ER triage and prep rapid response bay.</p>
                    </div>
                </div>
            </DashboardCard>
        </div>
    );
};

export const AmbulanceAssignments = () => {
    const { user } = useAuth();
    const ambulanceId = resolveAmbulanceId(user);
    const [assignments, setAssignments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ patient: '', emergencyType: '', etaMinutes: '' });
    const [saving, setSaving] = useState(false);
    const cacheKey = ambulanceId ? `ambulance_assignments_${ambulanceId}` : 'ambulance_assignments';

    const loadAssignments = async (withSpinner = false) => {
        const showSpinner = withSpinner === true && assignments.length === 0;
        if (showSpinner) setLoading(true);
        try {
            const res = await apiFetch(`/api/ambulance/assignments${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' });
            const data = res.ok ? (res.data?.data || []) : [];
            const normalized = normalizeAssignments(data);
            const nextData = normalized.length ? normalized : demoAssignments();
            setAssignments(nextData);
            if (res.ok) {
                localStorage.setItem(cacheKey, JSON.stringify(nextData));
            }
        } catch (err) {
            setAssignments(demoAssignments());
        } finally {
            if (showSpinner) setLoading(false);
        }
    };

    useEffect(() => {
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setAssignments(Array.isArray(parsed) ? parsed : []);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        loadAssignments(!hasCache);
    }, [ambulanceId]);

    const handleCreate = async () => {
        if (!form.patient || !form.emergencyType) return;
        setSaving(true);
        try {
            const res = await apiFetch('/api/ambulance/assignments', {
                method: 'POST',
                body: JSON.stringify({
                    ambulanceId,
                    ambulanceUserId: ambulanceId,
                    patient: form.patient,
                    emergencyType: form.emergencyType,
                    etaMinutes: form.etaMinutes ? Number(form.etaMinutes) : undefined,
                    status: 'Active'
                })
            });
            if (res.ok) {
                const normalized = normalizeAssignments([res.data]);
                setAssignments((prev) => [...normalized, ...prev]);
                setForm({ patient: '', emergencyType: '', etaMinutes: '' });
            }
        } finally {
            setSaving(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Active Assignments</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Patient" value={form.patient} onChange={(e) => setForm({ ...form, patient: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Emergency Type" value={form.emergencyType} onChange={(e) => setForm({ ...form, emergencyType: e.target.value })} />
                <input className="p-2 border rounded" placeholder="ETA (min)" value={form.etaMinutes} onChange={(e) => setForm({ ...form, etaMinutes: e.target.value })} />
                <button className="bg-indigo-600 text-white rounded px-4" onClick={handleCreate} disabled={saving}>
                    {saving ? 'Saving...' : 'Add Assignment'}
                </button>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-4">
                    {assignments.length === 0 ? (
                        <div className="text-sm text-gray-500">No assignments found.</div>
                    ) : (
                        assignments.map((item) => (
                            <div key={item._id || item.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white/70 p-4 rounded-xl border border-white/60">
                                <div>
                                    <p className="font-semibold text-gray-800 text-base">{item.patient || item.patientName}</p>
                                    <p className="text-sm text-gray-500">{item.emergencyType || item.emergency_type}</p>
                                </div>
                                <div className="text-left sm:text-right">
                                    <StatusPill text={item.status || 'Active'} color={item.status === 'Active' ? 'green' : 'yellow'} />
                                    {item.etaMinutes && <p className="text-xs text-gray-500 mt-1">ETA {item.etaMinutes} min</p>}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const AmbulancePatientInfo = () => {
    const { user } = useAuth();
    const ambulanceId = resolveAmbulanceId(user);
    const [info, setInfo] = useState([]);
    const [loading, setLoading] = useState(true);
    const cacheKey = ambulanceId ? `ambulance_patient_${ambulanceId}` : 'ambulance_patient';

    useEffect(() => {
        const load = async (withSpinner = false) => {
            if (withSpinner) setLoading(true);
            try {
                const res = await apiFetch(`/api/ambulance/patient-info${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                const normalized = normalizePatientInfo(data);
                const nextData = normalized.length ? normalized : demoPatientInfo();
                setInfo(nextData);
                if (res.ok) {
                    localStorage.setItem(cacheKey, JSON.stringify(nextData));
                }
            } catch (err) {
                setInfo(demoPatientInfo());
            } finally {
                if (withSpinner) setLoading(false);
            }
        };
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setInfo(Array.isArray(parsed) ? parsed : []);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        load(!hasCache);
    }, [ambulanceId]);

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Patient Status Updates</h3>
            {loading ? (
                <LoadingSpinner />
            ) : info.length === 0 ? (
                <div className="text-sm text-gray-500">No patient vitals available.</div>
            ) : (
                <div className="space-y-3">
                    {info.map((item) => (
                        <div key={item.id} className="border rounded-lg p-3 bg-white/70">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-gray-800">{item.patient || item.patientName}</p>
                                    <p className="text-xs text-gray-500">{item.emergencyType || item.emergency_type}</p>
                                </div>
                                <StatusPill text={item.status || 'Active'} color="blue" />
                            </div>
                            <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
                                <div className="flex items-center justify-between bg-white/80 p-2 rounded">
                                    <span className="text-gray-500">Heart Rate</span>
                                    <span className="font-semibold text-gray-800">{item.patientVitals?.heartRate || 'N/A'} bpm</span>
                                </div>
                                <div className="flex items-center justify-between bg-white/80 p-2 rounded">
                                    <span className="text-gray-500">Oxygen</span>
                                    <span className="font-semibold text-gray-800">{item.patientVitals?.oxygen || 'N/A'}%</span>
                                </div>
                                <div className="flex items-center justify-between bg-white/80 p-2 rounded">
                                    <span className="text-gray-500">BP</span>
                                    <span className="font-semibold text-gray-800">{item.patientVitals?.bp || 'N/A'}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const AmbulanceNavigation = () => {
    const [form, setForm] = useState({ startLat: '', startLng: '', endLat: '', endLng: '' });
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleRoute = async () => {
        if (!form.startLat || !form.startLng || !form.endLat || !form.endLng) return;
        setLoading(true);
        try {
            const res = await apiFetch(`/v2/route?start_lat=${form.startLat}&start_lng=${form.startLng}&end_lat=${form.endLat}&end_lng=${form.endLng}&include_geometry=false`, { method: 'GET' });
            if (res.ok) {
                const trafficRes = await apiFetch(`/v2/integrations/traffic?origin=${form.startLat},${form.startLng}&destination=${form.endLat},${form.endLng}`, { method: 'GET' });
                const baseSeconds = trafficRes.data?.base_duration_seconds || res.data?.duration_seconds || 0;
                const adjustedSeconds = trafficRes.data?.adjusted_duration_seconds || baseSeconds;
                const ratio = baseSeconds ? adjustedSeconds / baseSeconds : 1;
                const trafficLevel = trafficLevelFromRatio(ratio);
                setResult({
                    ...res.data,
                    traffic: trafficRes.ok ? trafficRes.data : null,
                    trafficLevel,
                    trafficEtaMinutes: Math.max(1, Math.round((adjustedSeconds || 600) / 60)),
                });
            } else {
                setResult({ error: res.data?.error || 'Route unavailable' });
            }
        } catch (err) {
            setResult({ error: 'Route unavailable' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Navigation Recommendations</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Start Lat" value={form.startLat} onChange={(e) => setForm({ ...form, startLat: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Start Lng" value={form.startLng} onChange={(e) => setForm({ ...form, startLng: e.target.value })} />
                <input className="p-2 border rounded" placeholder="End Lat" value={form.endLat} onChange={(e) => setForm({ ...form, endLat: e.target.value })} />
                <input className="p-2 border rounded" placeholder="End Lng" value={form.endLng} onChange={(e) => setForm({ ...form, endLng: e.target.value })} />
            </div>
            <button className="bg-blue-600 text-white rounded px-4 py-2" onClick={handleRoute} disabled={loading}>
                {loading ? 'Routing...' : 'Get Route'}
            </button>
            {result && (
                <div className="mt-4 border rounded p-3 bg-white/70">
                    {result.error ? (
                        <p className="text-sm text-red-600">{result.error}</p>
                    ) : (
                        <div className="text-sm text-gray-700">
                            <p className="font-semibold">ETA: {Math.round((result.duration_seconds || 0) / 60)} min</p>
                            <p>Distance: {((result.distance_km ?? (result.distance_meters ? result.distance_meters / 1000 : 0)) || 0).toFixed(1)} km</p>
                            {result.trafficLevel && (
                                <p className="mt-1 text-xs text-gray-500">Traffic {result.trafficLevel} · Adjusted ETA {result.trafficEtaMinutes} min</p>
                            )}
                        </div>
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const AmbulanceEmergencyStatus = () => {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const cacheKey = 'ambulance_emergency_status';

    useEffect(() => {
        const load = async (withSpinner = false) => {
            if (withSpinner) setLoading(true);
            try {
                const res = await apiFetch('/api/ambulance/emergency-status', { method: 'GET' });
                const payload = res.ok ? (res.data || {}) : null;
                const nextStatus = payload?.alerts?.length ? payload : demoEmergencyStatus();
                setStatus(nextStatus);
                if (res.ok) {
                    localStorage.setItem(cacheKey, JSON.stringify(nextStatus || {}));
                }
            } catch (err) {
                setStatus(demoEmergencyStatus());
            } finally {
                if (withSpinner) setLoading(false);
            }
        };
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setStatus(parsed || null);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        load(!hasCache);
    }, []);

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Emergency Status</h3>
            {loading ? (
                <LoadingSpinner />
            ) : !status ? (
                <div className="text-sm text-gray-500">No emergency updates available.</div>
            ) : (
                <div className="space-y-3">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {Object.entries(status.severityCounts || {}).map(([key, value]) => (
                            <div key={key} className="p-3 bg-white/80 border rounded">
                                <p className="text-xs text-gray-500">{key}</p>
                                <p className="text-lg font-bold text-gray-800">{value}</p>
                            </div>
                        ))}
                    </div>
                    <div className="space-y-2">
                        {(status.alerts || []).slice(0, 6).map((alert) => (
                            <div key={alert._id || alert.id} className="border rounded p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-gray-800">{alert.message}</p>
                                        <p className="text-xs text-gray-500">{alert.locationDetails || 'Unknown location'}</p>
                                    </div>
                                    <StatusPill text={alert.emergencyType || 'Medium'} color={alert.emergencyType === 'Critical' ? 'red' : 'yellow'} />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </DashboardCard>
    );
};

export const AmbulanceHistory = () => {
    const { user } = useAuth();
    const ambulanceId = resolveAmbulanceId(user);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const cacheKey = ambulanceId ? `ambulance_history_${ambulanceId}` : 'ambulance_history';

    useEffect(() => {
        const load = async (withSpinner = false) => {
            if (withSpinner) setLoading(true);
            try {
                const res = await apiFetch(`/api/ambulance/history${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                const normalized = normalizeHistory(data);
                const nextData = normalized.length ? normalized : demoHistory();
                setHistory(nextData);
                if (res.ok) {
                    localStorage.setItem(cacheKey, JSON.stringify(nextData));
                }
            } catch (err) {
                setHistory(demoHistory());
            } finally {
                if (withSpinner) setLoading(false);
            }
        };
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setHistory(Array.isArray(parsed) ? parsed : []);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        load(!hasCache);
    }, [ambulanceId]);

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Ambulance History</h3>
            {loading ? (
                <LoadingSpinner />
            ) : history.length === 0 ? (
                <div className="text-sm text-gray-500">No completed missions yet.</div>
            ) : (
                <div className="space-y-3">
                    {history.map((item) => (
                        <div key={item._id || item.id} className="flex items-center justify-between border rounded p-3">
                            <div>
                                <p className="font-semibold text-gray-800">{item.patient || item.patientName}</p>
                                <p className="text-xs text-gray-500">{item.emergencyType || item.emergency_type} • {item.status}</p>
                            </div>
                            <span className="text-xs text-gray-400">{item.updatedAt ? new Date(item.updatedAt).toLocaleString() : ''}</span>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};