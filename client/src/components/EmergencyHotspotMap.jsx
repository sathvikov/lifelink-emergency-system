import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { DashboardCard, LoadingSpinner } from './Common';
import { apiFetch } from '../config/api';

// Custom icons for density levels
const createIcon = (color) => new L.DivIcon({
    html: `<i class="fas fa-exclamation-circle" style="color: ${color}; font-size: 24px; text-shadow: 0 0 5px rgba(0,0,0,0.5);"></i>`,
    className: 'bg-transparent',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
});

const icons = {
    'High-Density Zone': createIcon('#ef4444'),   // Red
    'Medium-Density Zone': createIcon('#f97316'), // Orange
    'Low-Density Zone': createIcon('#eab308'),    // Yellow
    'Unknown': createIcon('#9ca3af')              // Grey
};

const EmergencyHotspotMap = () => {
    const [hotspots, setHotspots] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchHotspots = async () => {
            setError('');
            try {
                const seedRes = await apiFetch('/api/gov/emergency_hotspots', { method: 'GET' });
                const seed = Array.isArray(seedRes.data) ? seedRes.data : [];
                const heatmapRes = await apiFetch('/v2/ml/heatmap', {
                    method: 'POST',
                    body: JSON.stringify(seed)
                });
                if (heatmapRes.ok && Array.isArray(heatmapRes.data)) {
                    setHotspots(heatmapRes.data);
                } else if (seed.length) {
                    setHotspots(seed);
                } else {
                    setHotspots([]);
                }
            } catch (err) {
                console.error(err);
                setError('Unable to load hotspot data.');
                setHotspots([]);
            } 
            finally { setLoading(false); }
        };
        fetchHotspots();
    }, []);

    return (
        <DashboardCard className="h-full min-h-[500px]">
            <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold text-lg text-gray-900">Live Emergency Hotspots</h3>
                {loading && <LoadingSpinner />}
            </div>
            {error && (
                <div className="mb-3 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded">
                    {error}
                </div>
            )}
            
            <MapContainer center={[12.9716, 77.5946]} zoom={12} style={{ height: '500px', width: '100%', borderRadius: '0.75rem' }}>
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                
                {hotspots.map((h, idx) => (
                    <Marker key={idx} position={[h.lat, h.lng]} icon={icons[h.cluster_label] || icons['Unknown']}>
                        <Popup>
                            <b>{h.emergency_type}</b><br/>
                            Severity: {h.severity}<br/>
                            Cluster: {h.cluster_label}
                        </Popup>
                    </Marker>
                ))}
            </MapContainer>

            <div className="flex gap-4 mt-4 text-sm justify-center">
                <span className="flex items-center gap-1"><i className="fas fa-circle text-red-500"></i> High Density</span>
                <span className="flex items-center gap-1"><i className="fas fa-circle text-orange-500"></i> Medium Density</span>
                <span className="flex items-center gap-1"><i className="fas fa-circle text-yellow-500"></i> Low Density</span>
            </div>
        </DashboardCard>
    );
};

export default EmergencyHotspotMap;