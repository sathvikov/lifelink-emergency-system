import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { apiFetch, API_BASE_URL } from '../config/api';
import './AmbulanceETARoute.css';

const AmbulanceETARoute = ({ currentHospitalId, currentHospitalName, hospitalLocation = { lat: 12.8752, lng: 74.8470 } }) => {
    // KMC Hospital Mangalore as default
    const KMC_HOSPITAL_LAT = 12.8752;
    const KMC_HOSPITAL_LNG = 74.8470;
    const KMC_HOSPITAL_NAME = 'KMC Hospital Mangalore';
    const MANGALORE_LAT = 12.8479;
    const MANGALORE_LNG = 74.8478;

    const resolvedHospital = {
        lat: hospitalLocation?.lat ?? KMC_HOSPITAL_LAT,
        lng: hospitalLocation?.lng ?? KMC_HOSPITAL_LNG,
        name: currentHospitalName || KMC_HOSPITAL_NAME
    };

    // Main States
    const [activeTab, setActiveTab] = useState('tracking'); // tracking, manage
    const [ambulances, setAmbulances] = useState([]);
    const [selectedAmbulance, setSelectedAmbulance] = useState(null); // Manually selected in list (for highlighting)
    const [autoSelectedAmbulance, setAutoSelectedAmbulance] = useState(null); // Auto-selected for routing and details
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [mapReady, setMapReady] = useState(false);

    // Location Input States
    const [pickupLocation, setPickupLocation] = useState('');
    const [destinationLocation, setDestinationLocation] = useState(KMC_HOSPITAL_NAME);
    const [latitude, setLatitude] = useState(null);
    const [longitude, setLongitude] = useState(null);

    // Map and Route States
    const mapRef = useRef(null);
    const mapInstance = useRef(null);
    const markersRef = useRef({});
    const [routePath, setRoutePath] = useState([]);
    const [etaData, setEtaData] = useState(null);
    const [alternateRoutes, setAlternateRoutes] = useState([]);
    const [coordination, setCoordination] = useState(null);

    // ETA Timer State
    const [etaTimer, setEtaTimer] = useState(null);
    const etaIntervalRef = useRef(null);

    // Ambulance Management States
    const [newAmbulance, setNewAmbulance] = useState({
        ambulanceId: '',
        registrationNumber: '',
        driverName: '',
        licenseNumber: '',
        driverPhone: ''
    });

    // State to track all ambulance markers
    const ambulanceMarkersRef = useRef({});

    // Reinitialize map when tab changes
    useEffect(() => {
        if (activeTab === 'tracking' && mapInstance.current) {
            setTimeout(() => {
                try {
                    mapInstance.current?.invalidateSize();
                    setMapReady(true);
                } catch (err) {
                    console.error('Map resize error:', err);
                }
            }, 100);
        }
    }, [activeTab]);

    // Initialize Map
    useEffect(() => {
        // Only initialize if on tracking tab
        if (activeTab !== 'tracking') {
            return;
        }

        // Wait for next tick to ensure DOM is ready
        const initMap = async () => {
            try {
                // Check if map ref exists and mapInstance not already created
                if (!mapRef.current || mapInstance.current) {
                    return;
                }

                // Small delay to ensure DOM is ready
                await new Promise(resolve => setTimeout(resolve, 50));

                if (!mapRef.current) return;

                // Initialize map
                mapInstance.current = L.map(mapRef.current, {
                    zoom: 13,
                    center: [resolvedHospital.lat, resolvedHospital.lng]
                });

                // Add tile layer
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors',
                    maxZoom: 19
                }).addTo(mapInstance.current);

                // Add hospital marker
                const hospitalIcon = L.divIcon({
                    html: '<div class="hospital-marker"><i class="fas fa-hospital-user"></i></div>',
                    iconSize: [32, 32],
                    className: ''
                });

                L.marker([resolvedHospital.lat, resolvedHospital.lng], { icon: hospitalIcon })
                    .bindPopup(`<b>${resolvedHospital.name}</b><br>Hospital Location`)
                    .addTo(mapInstance.current);

                markersRef.current.hospital = true; // Mark as initialized
                setMapReady(true);
            } catch (err) {
                console.error('Error initializing map:', err);
                setError('Failed to load map');
            }
        };

        initMap();

        return () => {
            // Cleanup on unmount
        };
    }, [activeTab]);

    // Update ambulance markers when ambulances list changes
    useEffect(() => {
        if (!mapInstance.current || ambulances.length === 0) {
            return;
        }

        try {
            // Clear existing ambulance markers
            Object.keys(markersRef.current).forEach(key => {
                if (key.startsWith('ambulance-')) {
                    if (mapInstance.current.hasLayer(markersRef.current[key])) {
                        mapInstance.current.removeLayer(markersRef.current[key]);
                    }
                    delete markersRef.current[key];
                }
            });

            // Add new ambulance markers
            ambulances.forEach(ambulance => {
                if (ambulance.currentLocation?.latitude && ambulance.currentLocation?.longitude) {
                    const ambulanceIcon = L.divIcon({
                        html: `<div class="ambulance-map-marker ${ambulance.status}"><i class="fas fa-ambulance"></i></div>`,
                        iconSize: [28, 28],
                        className: ''
                    });

                    const marker = L.marker(
                        [ambulance.currentLocation.latitude, ambulance.currentLocation.longitude],
                        { icon: ambulanceIcon }
                    ).bindPopup(`<b>${ambulance.ambulanceId}</b><br>Status: ${ambulance.status.replace(/_/g, ' ')}`)
                     .addTo(mapInstance.current);

                    markersRef.current[`ambulance-${ambulance._id}`] = marker;
                }
            });
        } catch (err) {
            console.error('Error updating ambulance markers:', err);
        }
    }, [ambulances]);
    // Fetch ambulances on mount and set up refresh interval
    useEffect(() => {
        fetchAmbulances();
        const interval = setInterval(fetchAmbulances, 15000); // Refresh every 15 seconds
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (!currentHospitalId) return;
        let isActive = true;
        const loadCoordination = async () => {
            try {
                const res = await apiFetch(`/api/hospital-ops/ceo/ambulance/coordination?hospitalId=${currentHospitalId}`, { method: 'GET' });
                if (isActive) {
                    setCoordination(res.ok ? res.data : null);
                }
            } catch (err) {
                if (isActive) setCoordination(null);
            }
        };
        loadCoordination();
        const interval = setInterval(loadCoordination, 20000);
        return () => {
            isActive = false;
            clearInterval(interval);
        };
    }, [currentHospitalId]);

    // ETA Timer Effect
    useEffect(() => {
        if (etaData?.estimatedTimeMinutes && selectedAmbulance?.status === 'en_route') {
            const endTime = Date.now() + etaData.estimatedTimeMinutes * 60000;

            etaIntervalRef.current = setInterval(() => {
                const remaining = Math.max(0, Math.ceil((endTime - Date.now()) / 60000));
                setEtaTimer(remaining);

                if (remaining === 0) {
                    clearInterval(etaIntervalRef.current);
                    setSuccess('Ambulance arrived at destination!');
                }
            }, 1000);

            return () => clearInterval(etaIntervalRef.current);
        }
    }, [etaData, selectedAmbulance]);

    const fetchAmbulances = async () => {
        try {
            // Always fetch all ambulances (hospital filter handled on backend)
            const response = await apiFetch('/api/ambulance', { method: 'GET' });
            if (!response.ok) {
                console.error('API Error:', response.status);
                return; // Silently fail, don't set error repeatedly
            }

            const data = response.data;

            let ambulanceList = [];
            if (data.success && Array.isArray(data.data)) {
                ambulanceList = data.data;
            } else if (Array.isArray(data.data)) {
                ambulanceList = data.data;
            } else if (Array.isArray(data)) {
                ambulanceList = data;
            }

            // Only update if we got new data
            if (ambulanceList.length > 0) {
                // Ensure all ambulances have currentLocation data
                ambulanceList = ambulanceList.map(amb => ({
                    ...amb,
                    currentLocation: amb.currentLocation || {
                        latitude: MANGALORE_LAT + (Math.random() - 0.5) * 0.2,
                        longitude: MANGALORE_LNG + (Math.random() - 0.5) * 0.2,
                        address: 'Mangalore'
                    }
                }));

                setAmbulances(ambulanceList);

                // Auto-select first ambulance if none auto-selected
                if (!autoSelectedAmbulance && ambulanceList.length > 0) {
                    setAutoSelectedAmbulance(ambulanceList[0]);
                }
            }
        } catch (err) {
            // Silently fail - don't show error on every fetch
            console.error('Fetch error:', err.message);
        }
    };

    const handleAutoDetectLocation = () => {
        setLoading(true);
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    setLatitude(position.coords.latitude);
                    setLongitude(position.coords.longitude);
                    setPickupLocation(`${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`);
                    setSuccess('Location detected successfully!');
                    setLoading(false);
                    // Automatically calculate route after getting location
                    setTimeout(() => handleGetRoute(), 500);
                },
                (error) => {
                    setError('Unable to get location. Using Mangalore as default.');
                    setLatitude(MANGALORE_LAT);
                    setLongitude(MANGALORE_LNG);
                    setLoading(false);
                }
            );
        } else {
            setError('Geolocation not supported by your browser');
            setLoading(false);
        }
    };

    const geocodeLocation = async (locationName) => {
        try {
            // Use Nominatim OpenStreetMap API with Mangalore bounding box for accuracy
            // Mangalore bounds: N: 13.42, S: 12.65, E: 75.10, W: 74.80
            const boundingBox = `viewbox=${74.80},13.42,75.10,12.65&bounded=1`;
            const response = await fetch(
                `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(locationName)}&${boundingBox}&format=json&limit=1&countrycodes=IN`,
                { headers: { 'Accept-Language': 'en' } }
            );
            const data = await response.json();
            
            if (data && data.length > 0) {
                const lat = parseFloat(data[0].lat);
                const lon = parseFloat(data[0].lon);
                // Verify result is within Mangalore bounds
                if (lat >= 12.65 && lat <= 13.42 && lon >= 74.80 && lon <= 75.10) {
                    return { lat, lng: lon };
                }
            }
            return null;
        } catch (err) {
            console.error('Geocoding error:', err);
            return null;
        }
    };

    const handleLocationInputChange = async (value) => {
        setPickupLocation(value);
        
        if (value && value.length > 0) {
            // Try to parse as coordinates (e.g., "12.8479, 74.8478")
            const coordMatch = value.match(/[-+]?\d+\.?\d*\s*,\s*[-+]?\d+\.?\d*/);
            
            if (coordMatch) {
                // Parse coordinates
                const [lat, lng] = value.split(',').map(v => parseFloat(v.trim()));
                if (!isNaN(lat) && !isNaN(lng)) {
                    setLatitude(lat);
                    setLongitude(lng);
                    setSuccess('✓ Location set.');
                    // Find and auto-select nearest ambulance immediately
                    if (ambulances.length > 0) {
                        findNearestAmbulance(lat, lng);
                        // Auto-trigger route calculation after ambulance selection
                        setTimeout(() => {
                            handleGetRoute();
                        }, 1000);
                    }
                    return;
                }
            }
            
            // Try to geocode place name (e.g., "Kadri Hills", "Balmatta", etc.)
            setLoading(true);
            const coords = await geocodeLocation(value);
            
            if (coords) {
                setLatitude(coords.lat);
                setLongitude(coords.lng);
                setSuccess(`✓ Location found: ${value}`);
                // Find and auto-select nearest ambulance immediately
                if (ambulances.length > 0) {
                    findNearestAmbulance(coords.lat, coords.lng);
                    // Auto-trigger route calculation after ambulance selection
                    setTimeout(() => {
                        handleGetRoute();
                    }, 1000);
                }
            } else {
                setError(`Location '${value}' not found. Try another name or use coordinates (lat, lng).`);
            }
            setLoading(false);
        }
    };

    const findNearestAmbulance = (pickupLat, pickupLng) => {
        try {
            if (ambulances.length === 0) {
                setError('No ambulances available yet. Please wait...');
                return;
            }

            // Calculate distance using Haversine formula
            const calculateDistance = (lat1, lng1, lat2, lng2) => {
                const R = 6371;
                const dLat = (lat2 - lat1) * Math.PI / 180;
                const dLng = (lng2 - lng1) * Math.PI / 180;
                const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                    Math.sin(dLng / 2) * Math.sin(dLng / 2);
                const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
                return R * c;
            };

            // Find nearest available ambulance
            let nearest = null;
            let minDistance = Infinity;

            ambulances.forEach(ambulance => {
                const ambLat = ambulance.currentLocation?.latitude;
                const ambLng = ambulance.currentLocation?.longitude;
                
                // Only consider ambulances with valid locations
                if (ambLat && ambLng) {
                    const distance = calculateDistance(pickupLat, pickupLng, ambLat, ambLng);
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        nearest = ambulance;
                    }
                }
            });

            if (nearest) {
                setAutoSelectedAmbulance(nearest);
                console.log(`Selected nearest ambulance: ${nearest.ambulanceId} (${minDistance.toFixed(2)}km away)`);
            } else {
                setError('No valid ambulances found with location data');
            }
        } catch (err) {
            console.error('Error finding nearest ambulance:', err);
        }
    };

    const calculateDistance = (lat1, lng1, lat2, lng2) => {
        const R = 6371; // Earth's radius in km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    };

    const handleStartTracking = async () => {
        if (!selectedAmbulance) {
            setError('Please select an ambulance first');
            return;
        }

        if (!latitude || !longitude) {
            setError('Please set pickup location first');
            return;
        }

        setLoading(true);
        try {
                const response = await apiFetch(`/api/ambulance/${selectedAmbulance._id}/start-route`, {
                    method: 'POST',
                    body: JSON.stringify({
                        startLatitude: latitude,
                        startLongitude: longitude,
                        startAddress: pickupLocation || 'Pickup Location',
                        destinationLatitude: resolvedHospital.lat,
                        destinationLongitude: resolvedHospital.lng,
                        destinationAddress: resolvedHospital.name,
                        emergencyType: 'General',
                        priorityLevel: 'High'
                    })
                });

                const data = response.data || {};

            if (data.success || response.ok) {
                setSuccess(`✓ Tracking started for ${selectedAmbulance.ambulanceId}`);
                setEtaData(null);
                setTimeout(() => {
                    predictETA(selectedAmbulance._id);
                    fetchAmbulances();
                }, 500);
            } else {
                setError(data.error || 'Failed to start tracking');
            }
        } catch (err) {
            setError('Error starting tracking: ' + err.message);
            console.error('Start tracking error:', err);
        } finally {
            setLoading(false);
        }
    };

    const predictETA = async (ambulanceId) => {
        if (!ambulanceId || !latitude || !longitude) return;
        try {
            const ambulanceLat = selectedAmbulance?.currentLocation?.latitude || MANGALORE_LAT;
            const ambulanceLng = selectedAmbulance?.currentLocation?.longitude || MANGALORE_LNG;

                const response = await apiFetch(`/api/ambulance/${ambulanceId}/predict-eta`, {
                    method: 'POST',
                    body: JSON.stringify({
                        currentLatitude: ambulanceLat,
                        currentLongitude: ambulanceLng,
                        destinationLatitude: latitude,
                        destinationLongitude: longitude,
                        trafficLevel: 'medium',
                        weather: 'clear'
                    })
                });

                const data = response.data || {};

            if (data.success && data.data) {
                // Only update ETA time, keep distance and other data from OSRM
                const etaMinutes = data.data.etaPrediction?.estimatedMinutes || data.data.etaPrediction?.duration;
                if (etaMinutes) {
                    setEtaData(prev => ({
                        ...prev,
                        duration: etaMinutes,
                        trafficFactor: data.data.etaPrediction?.trafficFactor || 0.8
                    }));
                    setEtaTimer(etaMinutes);
                }
            }
        } catch (err) {
            console.error('ETA Prediction error:', err);
            // Continue without error - route already calculated
        }
    };

    const handleGetRoute = async () => {
        if (!latitude || !longitude) {
            setError('Please set pickup location first');
            return;
        }

        // If no auto-selected ambulance for routing, try to find the nearest one
        if (!autoSelectedAmbulance) {
            findNearestAmbulance(latitude, longitude);
            return;
        }

        setLoading(true);
        setError(null); // Clear previous errors
        try {
            // Get ambulance current location
            const ambulanceLat = autoSelectedAmbulance.currentLocation?.latitude || MANGALORE_LAT;
            const ambulanceLng = autoSelectedAmbulance.currentLocation?.longitude || MANGALORE_LNG;
            const destinationLat = resolvedHospital.lat;
            const destinationLng = resolvedHospital.lng;

            const fetchSegment = async (startLat, startLng, endLat, endLng) => {
                const query = new URLSearchParams({
                    start_lat: startLat,
                    start_lng: startLng,
                    end_lat: endLat,
                    end_lng: endLng,
                    include_geometry: true
                });
                const { ok, data } = await apiFetch(`/v2/route?${query.toString()}`);
                if (!ok || data.status !== 'ok' || !data.geometry) {
                    return null;
                }
                return data;
            };

            const [segmentToPickup, segmentToHospital] = await Promise.all([
                fetchSegment(ambulanceLat, ambulanceLng, latitude, longitude),
                fetchSegment(latitude, longitude, destinationLat, destinationLng)
            ]);

            const segments = [segmentToPickup, segmentToHospital].filter(Boolean);
            if (segments.length === 0) {
                throw new Error('No route found');
            }

            const totalDistance = segments.reduce((sum, seg) => sum + (seg.distance_meters || 0), 0);
            const totalDuration = segments.reduce((sum, seg) => sum + (seg.duration_seconds || 0), 0);
            const featureCollection = {
                type: 'FeatureCollection',
                features: segments.map((seg, index) => ({
                    type: 'Feature',
                    properties: { segment: index },
                    geometry: seg.geometry
                }))
            };

            const routeCoords = segments.flatMap((seg) =>
                (seg.geometry?.coordinates || []).map((coord) => ({
                    latitude: coord[1],
                    longitude: coord[0]
                }))
            );

            setRoutePath(routeCoords);
            drawRouteOnMap(featureCollection, ambulanceLat, ambulanceLng, latitude, longitude, destinationLat, destinationLng);
            setSuccess(`✓ Route: ${(totalDistance / 1000).toFixed(1)}km, ~${Math.round(totalDuration / 60)}min via roads`);

            setEtaData({
                distance: (totalDistance / 1000).toFixed(2),
                duration: Math.round(totalDuration / 60),
                trafficFactor: 0.8,
                weatherCondition: 'Clear',
                unit: 'km/min'
            });

            if (autoSelectedAmbulance?._id) {
                setTimeout(() => predictETA(autoSelectedAmbulance._id), 800);
            }
        } catch (err) {
            console.error('Error getting route:', err);
            setError('Failed to calculate route. Please try again.');
            // Still draw fallback
            if (autoSelectedAmbulance) {
                const ambulanceLat = autoSelectedAmbulance.currentLocation?.latitude || MANGALORE_LAT;
                const ambulanceLng = autoSelectedAmbulance.currentLocation?.longitude || MANGALORE_LNG;
                const simplePath = [
                    { latitude: ambulanceLat, longitude: ambulanceLng },
                    { latitude: latitude, longitude: longitude },
                    { latitude: resolvedHospital.lat, longitude: resolvedHospital.lng }
                ];
                const fallbackGeoJson = {
                    type: 'FeatureCollection',
                    features: [
                        {
                            type: 'Feature',
                            properties: { segment: 0 },
                            geometry: {
                                type: 'LineString',
                                coordinates: simplePath.map((point) => [point.longitude, point.latitude])
                            }
                        }
                    ]
                };
                drawRouteOnMap(fallbackGeoJson, ambulanceLat, ambulanceLng, latitude, longitude, resolvedHospital.lat, resolvedHospital.lng);
                setRoutePath(simplePath);
            }
        } finally {
            setLoading(false);
        }
    };

    const drawRouteOnMap = (geoJson, ambulanceLat, ambulanceLng, pickupLat, pickupLng, destinationLat, destinationLng) => {
        if (!mapInstance.current) return;

        // Clear existing route line
        if (markersRef.current.routeLayer) {
            mapInstance.current.removeLayer(markersRef.current.routeLayer);
        }

        // Clear special markers
        if (markersRef.current.pickup) {
            mapInstance.current.removeLayer(markersRef.current.pickup);
        }
        if (markersRef.current.ambulanceStart) {
            mapInstance.current.removeLayer(markersRef.current.ambulanceStart);
        }

        if (geoJson) {
            markersRef.current.routeLayer = L.geoJSON(geoJson, {
                style: (feature) => ({
                    color: feature?.properties?.segment === 0 ? '#667eea' : '#4f46e5',
                    weight: 4,
                    opacity: 0.9
                })
            }).addTo(mapInstance.current);

            // Add ambulance marker at start (current location)
            const ambulanceStartIcon = L.divIcon({
                html: '<div class="ambulance-start-marker"><i class="fas fa-ambulance"></i></div>',
                iconSize: [36, 36],
                className: ''
            });

            if (ambulanceLat && ambulanceLng) {
                markersRef.current.ambulanceStart = L.marker([ambulanceLat, ambulanceLng], { icon: ambulanceStartIcon })
                    .bindPopup(`<b>${selectedAmbulance?.ambulanceId || 'Ambulance'}</b><br>Current Location<br>En Route to Pickup`)
                    .addTo(mapInstance.current);
            }

            // Add pickup marker (where patient is waiting)
            const pickupIcon = L.divIcon({
                html: '<div class="pickup-start-marker"><i class="fas fa-map-pin"></i></div>',
                iconSize: [32, 32],
                className: ''
            });

            // Pickup marker at the specified pickup location coordinates
            markersRef.current.pickup = L.marker([pickupLat, pickupLng], { icon: pickupIcon })
                .bindPopup(`<b>Pickup Location</b><br>${pickupLocation}<br>Lat: ${pickupLat?.toFixed(4) || 'N/A'}, Lng: ${pickupLng?.toFixed(4) || 'N/A'}`)
                .addTo(mapInstance.current)
                .openPopup();

            // Fit bounds to show entire route including all waypoints
            const bounds = markersRef.current.routeLayer?.getBounds();
            if (bounds && bounds.isValid()) {
                mapInstance.current.fitBounds(bounds, { padding: [50, 50] });
            } else {
                const allPoints = [
                    [ambulanceLat, ambulanceLng],
                    [pickupLat, pickupLng],
                    [destinationLat, destinationLng]
                ];
                const fallbackBounds = L.latLngBounds(allPoints);
                mapInstance.current.fitBounds(fallbackBounds, { padding: [50, 50] });
            }
        }
    };

    const handleCreateAmbulance = async () => {
        if (!newAmbulance.ambulanceId || !newAmbulance.registrationNumber) {
            setError('Please fill in ambulance ID and registration number');
            return;
        }

        setLoading(true);
        try {
                const response = await apiFetch('/api/ambulance/create', {
                    method: 'POST',
                    body: JSON.stringify({
                        ...newAmbulance,
                        hospitalId: currentHospitalId
                    })
                });

                const data = response.data || {};

            if (data.success) {
                setSuccess('Ambulance created successfully!');
                setNewAmbulance({
                    ambulanceId: '',
                    registrationNumber: '',
                    driverName: '',
                    licenseNumber: '',
                    driverPhone: ''
                });
                fetchAmbulances();
            } else {
                setError(data.error || 'Failed to create ambulance');
            }
        } catch (err) {
            setError('Error creating ambulance: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const clearMessages = () => {
        setTimeout(() => {
            setError(null);
            setSuccess(null);
        }, 3000);
    };

    useEffect(() => {
        if (error || success) clearMessages();
    }, [error, success]);

    return (
        <div className="ambulance-eta-section">
            {/* Header */}
            <div className="ambulance-eta-header">
                <h2 className="ambulance-eta-title">
                    <i className="fas fa-ambulance"></i>
                    Ambulance ETA & Route Tracking
                </h2>
                <div className="ambulance-tab-controls">
                    <button
                        className={`ambulance-tab-btn ${activeTab === 'tracking' ? 'active' : ''}`}
                        onClick={() => {
                            setActiveTab('tracking');
                            setMapReady(false); // Reset map ready state
                        }}
                    >
                        <i className="fas fa-map-location-dot"></i> Track Ambulance
                    </button>
                    <button
                        className={`ambulance-tab-btn ${activeTab === 'manage' ? 'active' : ''}`}
                        onClick={() => setActiveTab('manage')}
                    >
                        <i className="fas fa-cogs"></i> Manage
                    </button>
                </div>
            </div>

            {/* Messages */}
            {error && <div className="ambulance-error"><i className="fas fa-exclamation-circle"></i> {error}</div>}
            {success && <div className="ambulance-success"><i className="fas fa-check-circle"></i> {success}</div>}

            {coordination && (
                <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-bold text-slate-800">Coordination Signals</h3>
                        <span className="text-xs text-slate-400">Live guidance</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Active assignments</p>
                            <p className="text-lg font-bold text-gray-900">{coordination.activeAssignments || 0}</p>
                        </div>
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Available units</p>
                            <p className="text-lg font-bold text-gray-900">{coordination.availableUnits || 0}</p>
                        </div>
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Guidance</p>
                            <p className="text-xs text-gray-700">{(coordination.guidance || [])[0] || 'Coverage stable'}</p>
                        </div>
                    </div>
                    {(coordination.multiVehiclePlan || []).length > 0 && (
                        <div className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                            {coordination.multiVehiclePlan[0].recommendation}
                        </div>
                    )}
                </div>
            )}

            {/* Tracking Tab */}
            {activeTab === 'tracking' && (
                <>
                    {/* Location Input */}
                    <div className="ambulance-location-input-container">
                        <div className="ambulance-input-group">
                            <label className="ambulance-input-label">
                                <i className="fas fa-map-pin"></i> Pickup Location (Enter address or coords)
                            </label>
                            <input
                                type="text"
                                className="ambulance-input-field"
                                placeholder="e.g., Mangalore or 12.8479, 74.8478"
                                value={pickupLocation}
                                onChange={(e) => handleLocationInputChange(e.target.value)}
                            />

                        </div>

                        <div className="ambulance-input-group">
                            <label className="ambulance-input-label">
                                <i className="fas fa-hospital"></i> Destination
                            </label>
                            <input
                                type="text"
                                className="ambulance-input-field"
                                placeholder="Hospital destination"
                                value={destinationLocation}
                                disabled
                            />
                        </div>

                        <button
                            className={`ambulance-location-btn ${loading ? 'loading' : ''}`}
                            onClick={handleAutoDetectLocation}
                            disabled={loading}
                        >
                            <i className="fas fa-location-crosshairs"></i>
                            {loading ? 'Detecting...' : 'Auto-Detect'}
                        </button>

                        <button
                            className={`ambulance-location-btn ${loading ? 'loading' : ''}`}
                            onClick={handleGetRoute}
                            disabled={loading}
                            style={{backgroundColor: '#667eea'}}
                        >
                            <i className="fas fa-road"></i>
                            {loading ? 'Calculating...' : 'Show Route'}
                        </button>
                    </div>

                    {/* Main Content Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '16px', marginTop: '16px' }}>
                        {/* Ambulance Selection - Left Sidebar */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '600px', overflowY: 'auto' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#667eea', margin: '0 0 8px 0' }}>
                                <i className="fas fa-list"></i> Available Ambulances ({ambulances.length})
                            </h3>
                            {ambulances.length > 0 ? (
                                ambulances.map((ambulance) => (
                                    <div
                                        key={ambulance._id}
                                        className={`ambulance-card ${selectedAmbulance?._id === ambulance._id ? 'selected' : ''}`}
                                        onClick={() => setSelectedAmbulance(ambulance)}
                                        style={{ cursor: 'pointer', padding: '12px', borderRadius: '8px', backgroundColor: selectedAmbulance?._id === ambulance._id ? '#667eea' : '#f5f5f5', color: selectedAmbulance?._id === ambulance._id ? 'white' : 'black', transition: 'all 0.3s' }}
                                    >
                                        <div style={{ fontWeight: '700', marginBottom: '4px' }}>
                                            <i className="fas fa-ambulance"></i> {ambulance.ambulanceId}
                                        </div>
                                        <div style={{ fontSize: '12px', marginBottom: '4px' }}>
                                            <strong>Status:</strong> {ambulance.status.replace(/_/g, ' ').toUpperCase()}
                                        </div>
                                        {ambulance.driver && (
                                            <div style={{ fontSize: '12px', marginBottom: '4px' }}>
                                                <strong>Driver:</strong> {ambulance.driver.name}
                                            </div>
                                        )}
                                        {ambulance.currentLocation && (
                                            <div style={{ fontSize: '12px' }}>
                                                <strong>Loc:</strong> {ambulance.currentLocation.address || 'Tracking...'}
                                            </div>
                                        )}
                                    </div>
                                ))
                            ) : (
                                <div style={{ color: '#999', fontSize: '14px', padding: '16px', textAlign: 'center' }}>
                                    Loading ambulances...
                                </div>
                            )}
                        </div>

                        {/* Right Side - Map and Details */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {/* Map */}
                            <div className="ambulance-map-container" style={{ height: '400px' }}>
                                <div ref={mapRef} className="ambulance-map"></div>
                                <div className="ambulance-map-controls">
                                    <button className="ambulance-map-btn" title="Zoom In" onClick={() => mapInstance.current?.zoomIn()}>
                                        <i className="fas fa-plus"></i>
                                    </button>
                                    <button className="ambulance-map-btn" title="Zoom Out" onClick={() => mapInstance.current?.zoomOut()}>
                                        <i className="fas fa-minus"></i>
                                    </button>
                                    <button className="ambulance-map-btn" title="Center" onClick={() => mapInstance.current?.setView([resolvedHospital.lat, resolvedHospital.lng], 13)}>
                                        <i className="fas fa-home"></i>
                                    </button>
                                </div>
                            </div>

                            {/* ETA Display - Show when ambulance + location are set */}
                            {selectedAmbulance && latitude && longitude && (
                                <div className="ambulance-eta-details" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                                    <div className="ambulance-detail-card">
                                        <div className="ambulance-detail-label">
                                            <i className="fas fa-hourglass-end"></i> ETA
                                        </div>
                                        <div className="ambulance-detail-value">
                                            {etaTimer || etaData?.duration || etaData?.estimatedMinutes || '--'}
                                        </div>
                                        <div className="ambulance-detail-unit">minutes</div>
                                    </div>

                                    <div className="ambulance-detail-card">
                                        <div className="ambulance-detail-label">
                                            <i className="fas fa-route"></i> Distance
                                        </div>
                                        <div className="ambulance-detail-value">
                                            {etaData?.distance && etaData.distance !== 'Calculating' ? etaData.distance : (routePath.length > 0 ? 'Ready' : '--')}
                                        </div>
                                        <div className="ambulance-detail-unit">km</div>
                                    </div>

                                    <div className="ambulance-detail-card">
                                        <div className="ambulance-detail-label">
                                            <i className="fas fa-traffic-light"></i> Traffic
                                        </div>
                                        <div className="ambulance-detail-value">
                                            {etaData?.trafficFactor ? (etaData.trafficFactor * 100).toFixed(0) : '80'}%
                                        </div>
                                        <div className="ambulance-detail-unit">delay</div>
                                    </div>

                                    <div className="ambulance-detail-card">
                                        <div className="ambulance-detail-label">
                                            <i className="fas fa-cloud"></i> Weather
                                        </div>
                                        <div className="ambulance-detail-value" style={{fontSize: '14px'}}>
                                            {etaData?.weatherCondition || 'Clear'}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Selected Ambulance Details - Only show auto-selected ambulance */}
                            {autoSelectedAmbulance && (
                                <div style={{ backgroundColor: '#fff3f0', padding: '16px', borderRadius: '12px', border: '2px solid #ff6b6b', boxShadow: '0 4px 12px rgba(255, 107, 107, 0.15)' }}>
                                    <h4 style={{ margin: '0 0 12px 0', fontSize: '16px', fontWeight: '700', color: '#ff6b6b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <i className="fas fa-ambulance" style={{ fontSize: '18px' }}></i> Ambulance Details (Selected for Routing)
                                    </h4>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', fontSize: '13px' }}>
                                        <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', borderLeft: '4px solid #667eea' }}>
                                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>ID</div>
                                            <div style={{ color: '#333', fontWeight: '700', fontSize: '14px' }}>{autoSelectedAmbulance.ambulanceId}</div>
                                        </div>
                                        <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', borderLeft: '4px solid #667eea' }}>
                                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Status</div>
                                            <div style={{ color: '#333', fontWeight: '700', fontSize: '14px' }}>{autoSelectedAmbulance.status.replace(/_/g, ' ').toUpperCase()}</div>
                                        </div>
                                        <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', borderLeft: '4px solid #667eea' }}>
                                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Registration</div>
                                            <div style={{ color: '#333', fontWeight: '700', fontSize: '14px' }}>{autoSelectedAmbulance.registrationNumber}</div>
                                        </div>
                                        {autoSelectedAmbulance.driver && (
                                            <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', borderLeft: '4px solid #667eea' }}>
                                                <div style={{ color: '#666', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Driver</div>
                                                <div style={{ color: '#333', fontWeight: '700', fontSize: '14px' }}>{autoSelectedAmbulance.driver.name}</div>
                                            </div>
                                        )}
                                        {autoSelectedAmbulance.currentLocation?.address && (
                                            <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', borderLeft: '4px solid #667eea' }}>
                                                <div style={{ color: '#666', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Location</div>
                                                <div style={{ color: '#333', fontWeight: '700', fontSize: '13px' }}>{autoSelectedAmbulance.currentLocation.address}</div>
                                            </div>
                                        )}
                                        <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', borderLeft: '4px solid #667eea' }}>
                                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Route</div>
                                            <div style={{ color: routePath.length > 0 ? '#27ae60' : '#e67e22', fontWeight: '700', fontSize: '14px' }}>{routePath.length > 0 ? '✓ Calculated' : 'Waiting...'}</div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Messages below everything */}
                    {(error || success) && (
                        <div style={{ marginTop: '16px' }}>
                            {error && <div className="ambulance-error"><i className="fas fa-exclamation-circle"></i> {error}</div>}
                            {success && <div className="ambulance-success"><i className="fas fa-check-circle"></i> {success}</div>}
                        </div>
                    )}
                </>
            )}

            {/* Manage Tab */}
            {activeTab === 'manage' && (
                <div style={{ background: 'rgba(255,255,255,0.1)', padding: '20px', borderRadius: '12px' }}>
                    <h3 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: '700' }}>
                        <i className="fas fa-plus-circle"></i> Add New Ambulance
                    </h3>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px', marginBottom: '16px' }}>
                        <input
                            type="text"
                            placeholder="Ambulance ID"
                            className="ambulance-input-field"
                            value={newAmbulance.ambulanceId}
                            onChange={(e) => setNewAmbulance({ ...newAmbulance, ambulanceId: e.target.value })}
                        />

                        <input
                            type="text"
                            placeholder="Registration Number"
                            className="ambulance-input-field"
                            value={newAmbulance.registrationNumber}
                            onChange={(e) => setNewAmbulance({ ...newAmbulance, registrationNumber: e.target.value })}
                        />

                        <input
                            type="text"
                            placeholder="Driver Name"
                            className="ambulance-input-field"
                            value={newAmbulance.driverName}
                            onChange={(e) => setNewAmbulance({ ...newAmbulance, driverName: e.target.value })}
                        />

                        <input
                            type="text"
                            placeholder="License Number"
                            className="ambulance-input-field"
                            value={newAmbulance.licenseNumber}
                            onChange={(e) => setNewAmbulance({ ...newAmbulance, licenseNumber: e.target.value })}
                        />

                        <input
                            type="text"
                            placeholder="Driver Phone"
                            className="ambulance-input-field"
                            value={newAmbulance.driverPhone}
                            onChange={(e) => setNewAmbulance({ ...newAmbulance, driverPhone: e.target.value })}
                        />
                    </div>

                    <button
                        className="ambulance-btn ambulance-btn-primary"
                        onClick={handleCreateAmbulance}
                        disabled={loading}
                        style={{ width: '100%' }}
                    >
                        <i className="fas fa-check"></i> {loading ? 'Creating...' : 'Create Ambulance'}
                    </button>
                </div>
            )}
        </div>
    );
};

export default AmbulanceETARoute;
