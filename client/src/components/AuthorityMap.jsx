import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { DashboardCard, LoadingSpinner } from './Common';
import { apiFetch } from '../config/api';
import L from 'leaflet';

// Fix for default Leaflet icons in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const AuthorityMap = () => {
    const [center, setCenter] = useState([12.9716, 77.5946]); // Default Bengaluru
    const [ambulances, setAmbulances] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        navigator.geolocation.getCurrentPosition((pos) => {
            setCenter([pos.coords.latitude, pos.coords.longitude]);
        });
    }, []);

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                const res = await apiFetch('/api/government-ops/ambulances', { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                setAmbulances(data);
            } catch (err) {
                setAmbulances([]);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    return (
        <DashboardCard className="p-0 overflow-hidden">
            <div className="h-[600px] w-full relative">
                <MapContainer center={center} zoom={7} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    
                    {/* User Current Location */}
                    <Circle center={center} radius={5000} pathOptions={{ color: 'blue', fillColor: 'blue' }} />
                    
                    {ambulances
                        .filter((item) => item.currentLocation?.latitude && item.currentLocation?.longitude)
                        .map((ambulance) => (
                            <Marker
                                key={ambulance._id || ambulance.ambulanceId}
                                position={[ambulance.currentLocation.latitude, ambulance.currentLocation.longitude]}
                            >
                                <Popup>
                                    <div className="p-1">
                                        <p className="font-bold text-red-600">{ambulance.ambulanceId || 'Ambulance'}</p>
                                        <p className="text-xs">Status: {ambulance.status || 'Unknown'}</p>
                                    </div>
                                </Popup>
                            </Marker>
                        ))}
                </MapContainer>
                
                <div className="absolute top-4 right-4 z-[1000] bg-white p-3 rounded-lg shadow-lg border">
                    <h4 className="text-xs font-bold uppercase text-gray-400">Live Status</h4>
                    <p className="text-sm font-bold text-red-600 animate-pulse">● Ambulance Tracking</p>
                    {loading && <LoadingSpinner />}
                </div>
            </div>
        </DashboardCard>
    );
};

export default AuthorityMap;