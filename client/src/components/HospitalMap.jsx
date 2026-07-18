import React, { useMemo, useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { apiFetch } from '../config/api';
import mockHospitals from '../data/mockHospitals';

// --- FIX LEAFLET ICONS ---
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

// Custom "You Are Here" Icon (Red)
const userIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const fallbackLogo = 'https://placehold.co/64x64?text=H';
const normalizeName = (name) => String(name || '').toLowerCase().replace(/[^a-z0-9]/g, '');

// Helper: Calculate Distance
const getDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371; // km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return (R * c).toFixed(1);
};

const RecenterMap = ({ lat, lng }) => {
    const map = useMap();
    useEffect(() => {
        // Zoom out slightly (level 7) to show the whole state if needed
        map.setView([lat, lng], 8); 
    }, [lat, lng, map]);
    return null;
};

const HospitalMap = () => {
    // Default Center: Karnataka State Center (near Davangere)
    const [userPos, setUserPos] = useState({ lat: 14.2, lng: 75.8 }); 
    const [gpsEnabled, setGpsEnabled] = useState(false);
    const [nearbyHospitals, setNearbyHospitals] = useState([]);
    const [loading, setLoading] = useState(true);

    const hospitalMetaMap = useMemo(() => {
        const map = new Map();
        mockHospitals.forEach((hospital) => {
            map.set(normalizeName(hospital.name), hospital);
        });
        return map;
    }, []);

    useEffect(() => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    setUserPos({
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    });
                    setGpsEnabled(true);
                },
                () => setGpsEnabled(false),
                { enableHighAccuracy: true }
            );
        }
    }, []);

    useEffect(() => {
        let isActive = true;
        const fetchNearby = async () => {
            setLoading(true);
            try {
                const res = await apiFetch(
                    `/v2/hospital/nearby?lat=${userPos.lat}&lng=${userPos.lng}&limit=20&radius_km=80&include_eta=true`,
                    { method: 'GET' }
                );
                if (res.ok && Array.isArray(res.data?.hospitals)) {
                    const normalized = res.data.hospitals.map((h) => ({
                        id: h.id,
                        name: h.name,
                        location: h.location?.address || 'Nearby',
                        lat: h.location?.lat,
                        lng: h.location?.lng,
                        distance_km: h.distance_km,
                        eta_seconds: h.eta_seconds,
                        wait_time_minutes: h.wait_time_minutes,
                        safety_score: h.safety_score,
                        logo: hospitalMetaMap.get(normalizeName(h.name))?.logo || fallbackLogo,
                        rating: hospitalMetaMap.get(normalizeName(h.name))?.rating || 4.0,
                        bedsAvailable: (h.beds_available ?? hospitalMetaMap.get(normalizeName(h.name))?.bedsAvailable) ?? 12,
                        bedsTotal: (h.beds_total ?? hospitalMetaMap.get(normalizeName(h.name))?.bedsTotal) ?? 120,
                        specialties: hospitalMetaMap.get(normalizeName(h.name))?.specialties || ['Emergency']
                    }));
                    if (isActive) {
                        setNearbyHospitals(normalized);
                    }
                }
            } catch (err) {
                if (isActive) {
                    setNearbyHospitals([]);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        fetchNearby();
        return () => {
            isActive = false;
        };
    }, [userPos.lat, userPos.lng]);

    const fallbackHospitals = useMemo(() => {
        return [...mockHospitals]
            .map((hospital) => ({
                ...hospital,
                distance_km: Number(getDistance(userPos.lat, userPos.lng, hospital.lat, hospital.lng))
            }))
            .sort((a, b) => a.distance_km - b.distance_km);
    }, [userPos.lat, userPos.lng]);

    const hospitals = nearbyHospitals.length ? nearbyHospitals : fallbackHospitals;

    return (
        <div className="bg-white p-4 rounded-xl border shadow-sm h-[600px] flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h3 className="font-bold text-lg text-gray-800">
                        <i className="fas fa-hospital-alt text-red-600 mr-2"></i>
                        Karnataka Hospital Network
                    </h3>
                    <p className="text-xs text-gray-500">
                        {gpsEnabled ? "Showing nearest hospitals to you" : "Showing major hospitals across Karnataka"}
                    </p>
                </div>
                {gpsEnabled && <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full font-bold">● GPS Active</span>}
            </div>

            <div className="flex-grow rounded-lg overflow-hidden border border-gray-300 relative z-0">
                <MapContainer center={[userPos.lat, userPos.lng]} zoom={7} scrollWheelZoom={true} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    
                    {/* User Marker */}
                    {gpsEnabled && (
                        <Marker position={[userPos.lat, userPos.lng]} icon={userIcon}>
                            <Popup><strong>You are here</strong></Popup>
                        </Marker>
                    )}
                    
                    {/* Auto Center Map */}
                    <RecenterMap lat={userPos.lat} lng={userPos.lng} />

                    {/* Hospital Markers */}
                    {hospitals.map((h) => (
                        <Marker key={h.id} position={[h.lat, h.lng]}>
                            <Popup>
                                <div className="text-center">
                                    <img src={h.logo || fallbackLogo} alt={`${h.name} logo`} className="w-10 h-10 mx-auto mb-2 rounded-full border" />
                                    <strong className="text-red-700">{h.name}</strong><br/>
                                    <span className="text-xs text-gray-600">{h.location}</span><br/>
                                    <div className="mt-2 text-sm font-bold">
                                        {h.distance_km ? `${h.distance_km} km` : `${getDistance(userPos.lat, userPos.lng, h.lat, h.lng)} km`} away
                                    </div>
                                    {h.eta_seconds ? (
                                        <div className="text-xs text-gray-500">ETA {Math.round(h.eta_seconds / 60)} min</div>
                                    ) : null}
                                    {h.wait_time_minutes ? (
                                        <div className="text-xs text-gray-500">Wait time {h.wait_time_minutes} min</div>
                                    ) : null}
                                    <div className="text-[11px] text-gray-500 mt-1">Beds: {h.bedsAvailable}/{h.bedsTotal} • Rating: {h.rating}</div>
                                    {h.safety_score ? (
                                        <div className="text-[11px] text-gray-500">Safety score {h.safety_score}</div>
                                    ) : null}
                                </div>
                            </Popup>
                        </Marker>
                    ))}
                </MapContainer>
            </div>
            
            {/* List of 4 Nearest Hospitals */}
            <div className="mt-3">
                <p className="text-xs font-bold text-gray-500 mb-2 uppercase">Nearest to you:</p>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                    {hospitals.slice(0, 4).map(h => (
                         <div key={h.id} className="text-xs bg-gray-50 p-3 rounded border border-gray-200">
                             <div className="flex items-center gap-2">
                                 <img src={h.logo || fallbackLogo} alt={`${h.name} logo`} className="w-10 h-10 rounded-full border" />
                                 <div className="min-w-0">
                                     <p className="font-semibold text-gray-700 truncate">{h.name}</p>
                                     <p className="text-[11px] text-gray-500">Beds {h.bedsAvailable} • {h.specialties?.[0] || 'Emergency'}</p>
                                 </div>
                             </div>
                             <div className="mt-2 flex items-center justify-between">
                                 <span className="text-blue-600 font-bold">
                                     {h.distance_km ? `${h.distance_km} km` : `${getDistance(userPos.lat, userPos.lng, h.lat, h.lng)} km`}
                                 </span>
                                 <span className="text-[11px] text-gray-500">Rating {h.rating}</span>
                             </div>
                             {h.wait_time_minutes ? (
                                 <div className="text-[11px] text-gray-500 mt-1">Wait {h.wait_time_minutes} min • Safety {h.safety_score}</div>
                             ) : null}
                         </div>
                    ))}
                </div>
                {loading && <p className="text-xs text-gray-400 mt-2">Loading nearby hospitals...</p>}
            </div>
        </div>
    );
};

export default HospitalMap;