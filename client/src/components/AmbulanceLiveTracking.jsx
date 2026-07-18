import React, { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { apiFetch, API_BASE_URL } from '../config/api';
import './AmbulanceLiveTracking.css';

import iconMarker from 'leaflet/dist/images/marker-icon.png';
import iconRetina from 'leaflet/dist/images/marker-icon-2x.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const defaultIcon = L.icon({
    iconRetinaUrl: iconRetina,
    iconUrl: iconMarker,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});
L.Marker.prototype.options.icon = defaultIcon;

const statusColor = {
    available: 'available',
    en_route: 'en-route',
    at_location: 'at-location',
    returning: 'returning',
    maintenance: 'maintenance'
};

const makeAmbulanceIcon = (status) => {
    const className = statusColor[status] || 'available';
    return L.divIcon({
        html: `<div class="ambulance-live-marker ${className}"><i class="fas fa-ambulance"></i></div>`,
        iconSize: [28, 28],
        className: ''
    });
};

const RecenterMap = ({ center, bounds }) => {
    const map = useMap();
    useEffect(() => {
        if (bounds && bounds.isValid()) {
            map.fitBounds(bounds, { padding: [40, 40] });
            return;
        }
        if (center) {
            map.setView(center, 12);
        }
    }, [center, bounds, map]);
    return null;
};

const defaultCenter = [12.9716, 77.5946];

const demoAmbulances = () => ([
    {
        ambulanceId: 'A1',
        status: 'en_route',
        currentLocation: {
            latitude: 12.9716,
            longitude: 77.5946,
            address: 'Majestic, Bengaluru'
        },
        activeRoute: {
            destinationLocation: {
                latitude: 12.9784,
                longitude: 77.6031,
                address: "St. Martha's Hospital"
            }
        }
    },
    {
        ambulanceId: 'A2',
        status: 'available',
        currentLocation: {
            latitude: 12.9669,
            longitude: 77.5865,
            address: 'Shivajinagar, Bengaluru'
        }
    },
    {
        ambulanceId: 'A3',
        status: 'at_location',
        currentLocation: {
            latitude: 12.9812,
            longitude: 77.5718,
            address: 'Malleshwaram, Bengaluru'
        }
    }
]);

const normalizeAmbulances = (list) => (list || []).map((item, index) => ({
    ...item,
    ambulanceId: item.ambulanceId || item._id || item.id || `AMB-${index + 1}`,
    status: item.status || item.currentStatus || 'available',
    currentLocation: {
        ...(item.currentLocation || {}),
        latitude: item.currentLocation?.latitude ?? item.latitude ?? item.lat,
        longitude: item.currentLocation?.longitude ?? item.longitude ?? item.lng,
        address: item.currentLocation?.address || item.address,
    },
}));

const AmbulanceLiveTracking = () => {
    const [ambulances, setAmbulances] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('connecting');
    const [lastEvent, setLastEvent] = useState(null);
    const socketRef = useRef(null);
    const reconnectRef = useRef(null);

    const wsUrl = useMemo(() => {
        const base = API_BASE_URL || window.location.origin;
        if (!base) return '';
        return `${base.replace(/^http/, 'ws')}/v2/realtime/ws/ambulance`;
    }, []);

    useEffect(() => {
        const fetchInitial = async () => {
            try {
                const res = await apiFetch('/api/ambulance', { method: 'GET' });
                const list = res.data?.data || res.data || [];
                const normalized = Array.isArray(list) ? normalizeAmbulances(list) : [];
                const hasCoords = normalized.some((item) => (
                    typeof item.currentLocation?.latitude === 'number'
                    && typeof item.currentLocation?.longitude === 'number'
                ));
                setAmbulances(hasCoords ? normalized : demoAmbulances());
            } catch (err) {
                setAmbulances(demoAmbulances());
            }
        };
        fetchInitial();
    }, []);

    useEffect(() => {
        if (!wsUrl) {
            setConnectionStatus('error');
            return undefined;
        }

        const connect = () => {
            if (socketRef.current) {
                socketRef.current.close();
            }

            setConnectionStatus('connecting');
            const socket = new WebSocket(wsUrl);
            socketRef.current = socket;

            socket.onopen = () => {
                setConnectionStatus('open');
            };

            socket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    const payload = message?.payload || message || {};
                    const eventType = payload.type || message.type;
                    setLastEvent({ type: eventType || 'update', at: new Date().toISOString() });

                    if (eventType === 'location_update') {
                        setAmbulances((prev) => upsertAmbulance(prev, payload.ambulanceId, {
                            currentLocation: payload.payload || payload.currentLocation || payload,
                            status: payload.status || payload.currentStatus
                        }));
                        return;
                    }

                    if (eventType === 'route_started') {
                        setAmbulances((prev) => upsertAmbulance(prev, payload.ambulanceId, {
                            activeRoute: payload.payload || payload.activeRoute,
                            status: 'en_route'
                        }));
                        return;
                    }
                } catch (err) {
                    console.error('WebSocket message error:', err);
                }
            };

            socket.onerror = () => {
                setConnectionStatus('error');
            };

            socket.onclose = () => {
                setConnectionStatus('closed');
                reconnectRef.current = setTimeout(connect, 2500);
            };
        };

        connect();

        return () => {
            if (reconnectRef.current) {
                clearTimeout(reconnectRef.current);
            }
            socketRef.current?.close();
        };
    }, [wsUrl]);

    const locations = ambulances
        .map((ambulance) => ({
            ...ambulance,
            lat: ambulance.currentLocation?.latitude,
            lng: ambulance.currentLocation?.longitude
        }))
        .filter((ambulance) => typeof ambulance.lat === 'number' && typeof ambulance.lng === 'number');

    const bounds = useMemo(() => {
        if (!locations.length) return null;
        const points = locations.map((item) => [item.lat, item.lng]);
        return L.latLngBounds(points);
    }, [locations]);

    const center = locations.length ? [locations[0].lat, locations[0].lng] : defaultCenter;

    const routeLines = useMemo(() => {
        return locations
            .map((ambulance) => {
                const routePath = Array.isArray(ambulance.activeRoute?.routePath)
                    ? ambulance.activeRoute.routePath
                        .map((point) => [point.latitude, point.longitude])
                        .filter(([lat, lng]) => typeof lat === 'number' && typeof lng === 'number')
                    : [];
                if (routePath.length > 1) {
                    return {
                        id: ambulance._id || ambulance.ambulanceId,
                        path: routePath,
                    };
                }
                const dest = ambulance.activeRoute?.destinationLocation;
                if (!dest || dest.latitude == null || dest.longitude == null) {
                    return null;
                }
                return {
                    id: ambulance._id || ambulance.ambulanceId,
                    path: [
                        [ambulance.lat, ambulance.lng],
                        [dest.latitude, dest.longitude]
                    ]
                };
            })
            .filter(Boolean);
    }, [locations]);

    return (
        <div className="ambulance-live-wrapper">
            <div className="ambulance-live-header">
                <div>
                    <h3 className="text-lg font-bold text-gray-900">Live Tracking</h3>
                    <p className="text-sm text-gray-500">Streaming ambulance locations via WebSocket.</p>
                </div>
                <div className="ambulance-live-status">
                    <span className={`status-pill ${connectionStatus}`}>{connectionStatus}</span>
                    {lastEvent && (
                        <span className="text-xs text-gray-500">Last update {new Date(lastEvent.at).toLocaleTimeString()}</span>
                    )}
                </div>
            </div>

            <div className="ambulance-live-map">
                <MapContainer center={center} zoom={12} scrollWheelZoom={true} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        attribution="&copy; OpenStreetMap contributors"
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    {routeLines.map((route) => (
                        <Polyline key={route.id} positions={route.path} color="#2563eb" weight={3} opacity={0.7} />
                    ))}
                    {locations.map((ambulance) => (
                        <Marker
                            key={ambulance._id || ambulance.ambulanceId}
                            position={[ambulance.lat, ambulance.lng]}
                            icon={makeAmbulanceIcon(ambulance.status)}
                        >
                            <Popup>
                                <div className="text-sm">
                                    <p className="font-semibold">{ambulance.ambulanceId || 'Ambulance'}</p>
                                    <p className="text-xs text-gray-500">Status: {ambulance.status || 'Unknown'}</p>
                                    {ambulance.currentLocation?.address && (
                                        <p className="text-xs text-gray-500">{ambulance.currentLocation.address}</p>
                                    )}
                                </div>
                            </Popup>
                        </Marker>
                    ))}
                    <RecenterMap center={center} bounds={bounds} />
                </MapContainer>
            </div>

            <div className="ambulance-live-list">
                <div className="text-xs font-semibold text-gray-500 uppercase">Active Units</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                    {locations.length === 0 ? (
                        <div className="text-sm text-gray-500">No live ambulance locations yet.</div>
                    ) : (
                        locations.map((ambulance) => (
                            <div key={ambulance._id || ambulance.ambulanceId} className="ambulance-live-card">
                                <div>
                                    <p className="font-semibold text-gray-800">{ambulance.ambulanceId || 'Ambulance'}</p>
                                    <p className="text-xs text-gray-500">{ambulance.currentLocation?.address || 'Tracking...'}</p>
                                </div>
                                <span className={`status-dot ${statusColor[ambulance.status] || 'available'}`}></span>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};

const upsertAmbulance = (list, ambulanceId, patch) => {
    if (!ambulanceId) return list;
    const index = list.findIndex((item) => item.ambulanceId === ambulanceId || item._id === ambulanceId);
    if (index === -1) {
        return [{ ambulanceId, ...patch }, ...list];
    }
    const next = [...list];
    next[index] = { ...next[index], ...patch };
    return next;
};

export default AmbulanceLiveTracking;
