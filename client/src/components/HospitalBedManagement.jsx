import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';
import { DashboardCard, LoadingSpinner } from './Common';

const buildQuery = (params) => {
    const searchParams = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return;
        searchParams.append(key, String(value));
    });
    const query = searchParams.toString();
    return query ? `?${query}` : '';
};

const HospitalBedManagement = () => {
    const { user } = useAuth();
    const [beds, setBeds] = useState({ totalBeds: 0, occupiedBeds: 0, availableBeds: 0 });
    const [bedBreakdown, setBedBreakdown] = useState(null);
    const [allocations, setAllocations] = useState([]);
    const [allocationSearch, setAllocationSearch] = useState('');
    const [allocationSortBy, setAllocationSortBy] = useState('createdAt');
    const [allocationSortDir, setAllocationSortDir] = useState('desc');
    const [allocationForm, setAllocationForm] = useState({ patientName: '', bedType: 'ICU', override: false });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [forecast, setForecast] = useState(null);
    const [mutualAid, setMutualAid] = useState([]);
    const [bedUpdatedAt, setBedUpdatedAt] = useState(null);
    const [transferStatus, setTransferStatus] = useState('');

    const hospitalId = user?._id || user?.id;

    const load = async () => {
        if (!hospitalId) {
            setBeds({ totalBeds: 0, occupiedBeds: 0, availableBeds: 0 });
            setBedBreakdown(null);
            setAllocations([]);
            setForecast(null);
            setMutualAid([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const allocationQuery = buildQuery({
                hospitalId,
                search: allocationSearch,
                sort_by: allocationSortBy,
                sort_dir: allocationSortDir
            });
            const [res, allocationRes, resourceRes, forecastRes] = await Promise.all([
                apiFetch(`/api/hospital-communication/my-hospital/${hospitalId}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/emergency/bed-allocation${allocationQuery}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/ceo/resources?hospitalId=${hospitalId}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/ceo/beds/forecast?hospitalId=${hospitalId}`, { method: 'GET' })
            ]);
            const data = res.ok ? res.data : null;
            const resourceBeds = resourceRes.ok ? resourceRes.data?.beds : null;
            const derivedBeds = resourceBeds ? {
                totalBeds: resourceBeds.total || 0,
                occupiedBeds: resourceBeds.occupied || 0,
                availableBeds: resourceBeds.available || 0,
            } : null;
            const currentBeds = data?.beds || derivedBeds || { totalBeds: 0, occupiedBeds: 0, availableBeds: 0 };
            setBeds(currentBeds);
            setBedUpdatedAt(data?.updatedAt || null);
            setAllocations(allocationRes.ok ? (allocationRes.data?.data || []) : []);
            setBedBreakdown(resourceRes.ok ? resourceRes.data?.beds : null);
            setForecast(forecastRes.ok ? forecastRes.data : null);

        } catch (err) {
            setBeds({ totalBeds: 0, occupiedBeds: 0, availableBeds: 0 });
            setAllocations([]);
            setBedBreakdown(null);
            setForecast(null);
            setMutualAid([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [hospitalId, allocationSearch, allocationSortBy, allocationSortDir]);

    useEffect(() => {
        let isActive = true;
        if (!hospitalId) {
            setMutualAid([]);
            return () => { isActive = false; };
        }
        const fetchAid = async () => {
            try {
                const aidRes = await apiFetch('/api/hospital-communication/mutual-aid/recommendations', {
                    method: 'POST',
                    body: JSON.stringify({
                        hospitalId,
                        resourceType: 'beds',
                        requiredUnits: 3,
                        urgency: 'high'
                    })
                });
                if (isActive) {
                    setMutualAid(aidRes.ok ? (aidRes.data?.data || []) : []);
                }
            } catch (err) {
                if (isActive) {
                    setMutualAid([]);
                }
            }
        };
        fetchAid();
        return () => {
            isActive = false;
        };
    }, [hospitalId]);

    const handleSave = async () => {
        if (!hospitalId) return;
        setSaving(true);
        try {
            const availableBeds = Math.max(0, Number(beds.totalBeds) - Number(beds.occupiedBeds));
            const payload = { beds: { ...beds, availableBeds } };
            const res = await apiFetch(`/api/hospital-communication/my-hospital/${hospitalId}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                setBeds(res.data?.beds || payload.beds);
            }
        } finally {
            setSaving(false);
        }
    };

    const handleAllocate = async () => {
        if (!hospitalId || !allocationForm.patientName) return;
        try {
            const res = await apiFetch('/api/hospital-ops/emergency/bed-allocation', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    patientName: allocationForm.patientName,
                    bedType: allocationForm.bedType,
                    override: allocationForm.override
                })
            });
            if (res.ok) {
                setAllocations((prev) => [res.data, ...prev]);
                setAllocationForm({ patientName: '', bedType: 'ICU', override: false });
            }
        } catch (err) {
            // No-op
        }
    };

    const handleTransfer = async (targetId, requiredUnits) => {
        if (!hospitalId || !targetId) return;
        setTransferStatus('Sending transfer request...');
        try {
            const res = await apiFetch('/api/hospital-communication/transfer/request', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    resourceType: 'beds',
                    requiredUnits: requiredUnits || 1,
                    urgency: 'high'
                })
            });
            if (res.ok) {
                setTransferStatus('Transfer request sent.');
            } else {
                setTransferStatus('Transfer request failed.');
            }
        } catch (err) {
            setTransferStatus('Transfer request failed.');
        }
        setTimeout(() => setTransferStatus(''), 4000);
    };

    return (
        <DashboardCard>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-lg font-bold text-gray-900">Bed Management</h3>
                    <p className="text-sm text-gray-500">Track occupancy and adjust bed availability in real time.</p>
                </div>
                <button className="text-xs text-slate-600" onClick={load}>Refresh</button>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-4">
                    {bedUpdatedAt && (
                        <div className="text-xs text-gray-400">Bed status updated {new Date(bedUpdatedAt).toLocaleString()}</div>
                    )}
                    {bedBreakdown && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div className="bg-white/70 border rounded p-3">
                                <p className="text-xs text-gray-500">ICU</p>
                                <p className="text-lg font-bold text-gray-900">{bedBreakdown.icu?.occupied || 0}/{bedBreakdown.icu?.total || 0}</p>
                            </div>
                            <div className="bg-white/70 border rounded p-3">
                                <p className="text-xs text-gray-500">Emergency</p>
                                <p className="text-lg font-bold text-gray-900">{bedBreakdown.emergency?.occupied || 0}/{bedBreakdown.emergency?.total || 0}</p>
                            </div>
                            <div className="bg-white/70 border rounded p-3">
                                <p className="text-xs text-gray-500">General</p>
                                <p className="text-lg font-bold text-gray-900">{bedBreakdown.general?.occupied || 0}/{bedBreakdown.general?.total || 0}</p>
                            </div>
                        </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="bg-white/70 border rounded p-4">
                            <p className="text-xs text-gray-500">Total Beds</p>
                            <p className="text-2xl font-bold text-gray-900">{beds.totalBeds}</p>
                        </div>
                        <div className="bg-white/70 border rounded p-4">
                            <p className="text-xs text-gray-500">Occupied</p>
                            <p className="text-2xl font-bold text-orange-600">{beds.occupiedBeds}</p>
                        </div>
                        <div className="bg-white/70 border rounded p-4">
                            <p className="text-xs text-gray-500">Available</p>
                            <p className="text-2xl font-bold text-green-600">{beds.availableBeds}</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <input
                            className="p-2 border rounded"
                            type="number"
                            value={beds.totalBeds}
                            onChange={(e) => setBeds({ ...beds, totalBeds: Number(e.target.value) })}
                            placeholder="Total beds"
                        />
                        <input
                            className="p-2 border rounded"
                            type="number"
                            value={beds.occupiedBeds}
                            onChange={(e) => setBeds({ ...beds, occupiedBeds: Number(e.target.value) })}
                            placeholder="Occupied beds"
                        />
                        <button className="bg-indigo-600 text-white rounded" onClick={handleSave} disabled={saving}>
                            {saving ? 'Saving...' : 'Update Beds'}
                        </button>
                    </div>

                    <div className="border-t pt-4">
                        <h4 className="font-bold text-gray-800 mb-3">Assign Bed</h4>
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                            <input
                                className="p-2 border rounded"
                                placeholder="Patient name"
                                value={allocationForm.patientName}
                                onChange={(e) => setAllocationForm({ ...allocationForm, patientName: e.target.value })}
                            />
                            <select
                                className="p-2 border rounded"
                                value={allocationForm.bedType}
                                onChange={(e) => setAllocationForm({ ...allocationForm, bedType: e.target.value })}
                            >
                                <option>ICU</option>
                                <option>Emergency</option>
                                <option>General</option>
                            </select>
                            <label className="flex items-center gap-2 text-sm text-gray-600">
                                <input
                                    type="checkbox"
                                    checked={allocationForm.override}
                                    onChange={(e) => setAllocationForm({ ...allocationForm, override: e.target.checked })}
                                />
                                Override
                            </label>
                            <button className="bg-slate-900 text-white rounded" onClick={handleAllocate}>
                                Assign
                            </button>
                        </div>
                    </div>

                    <div className="border-t pt-4">
                        <h4 className="font-bold text-gray-800 mb-3">Bed Forecast</h4>
                        {!forecast ? (
                            <div className="text-sm text-gray-500">Forecast unavailable.</div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                <div className="bg-white/70 border rounded p-3">
                                    <p className="text-xs text-gray-500">Expected discharges (24h)</p>
                                    <p className="text-xl font-bold text-gray-900">{forecast.expectedDischarges24h || 0}</p>
                                </div>
                                <div className="bg-white/70 border rounded p-3">
                                    <p className="text-xs text-gray-500">Active allocations</p>
                                    <p className="text-xl font-bold text-gray-900">{forecast.allocationCount || 0}</p>
                                </div>
                                <div className="bg-white/70 border rounded p-3">
                                    <p className="text-xs text-gray-500">Predicted demand</p>
                                    <p className="text-xl font-bold text-gray-900">{forecast.forecast?.predicted_bed_demand ?? 0}</p>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="border-t pt-4">
                        <h4 className="font-bold text-gray-800 mb-3">Overflow Routing</h4>
                        {transferStatus && (
                            <div className="text-xs text-indigo-600 mb-2">{transferStatus}</div>
                        )}
                        {mutualAid.length === 0 ? (
                            <div className="text-sm text-gray-500">No mutual aid recommendations yet.</div>
                        ) : (
                            <div className="space-y-2">
                                {mutualAid.map((item) => (
                                    <div key={item.hospitalId} className="border rounded p-3 flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-gray-800">{item.name}</p>
                                            <p className="text-xs text-gray-500">Available beds {item.availableBeds}</p>
                                        </div>
                                        <button
                                            className="text-xs text-indigo-600"
                                            onClick={() => handleTransfer(item.hospitalId, 2)}
                                        >
                                            Request transfer
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="border-t pt-4">
                        <h4 className="font-bold text-gray-800 mb-3">Recent Allocations</h4>
                        <div className="flex flex-col md:flex-row gap-2 mb-3">
                            <input
                                className="p-2 border rounded w-full"
                                placeholder="Search allocations"
                                value={allocationSearch}
                                onChange={(e) => setAllocationSearch(e.target.value)}
                            />
                            <select
                                className="p-2 border rounded"
                                value={allocationSortBy}
                                onChange={(e) => setAllocationSortBy(e.target.value)}
                            >
                                <option value="createdAt">Newest</option>
                                <option value="status">Status</option>
                                <option value="bedType">Bed Type</option>
                            </select>
                            <select
                                className="p-2 border rounded"
                                value={allocationSortDir}
                                onChange={(e) => setAllocationSortDir(e.target.value)}
                            >
                                <option value="desc">Desc</option>
                                <option value="asc">Asc</option>
                            </select>
                        </div>
                        {allocations.length === 0 ? (
                            <div className="text-sm text-gray-500">No allocations yet.</div>
                        ) : (
                            <div className="space-y-2">
                                {allocations.slice(0, 6).map((item) => (
                                    <div key={item._id || item.id} className="border rounded p-3 flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-gray-800">{item.patientName}</p>
                                            <p className="text-xs text-gray-500">{item.bedType} • {item.status || 'Assigned'}</p>
                                        </div>
                                        <button
                                            className="text-xs text-green-600"
                                            onClick={async () => {
                                                await apiFetch(`/api/hospital-ops/emergency/bed-allocation/${item._id || item.id}`, {
                                                    method: 'PATCH',
                                                    body: JSON.stringify({ status: 'Released' })
                                                });
                                                setAllocations((prev) => prev.map((row) => (row._id || row.id) === (item._id || item.id) ? { ...row, status: 'Released' } : row));
                                            }}
                                        >
                                            Release
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </DashboardCard>
    );
};

export default HospitalBedManagement;
