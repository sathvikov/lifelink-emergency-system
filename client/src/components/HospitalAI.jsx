import React, { useState, useRef, useEffect } from 'react';
import { DashboardCard, ExplainabilityPanel, Input, LoadingSpinner, ProgressBar } from './Common';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { apiFetch } from '../config/api';

// Register ChartJS components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

// --- 1. Ambulance ETA Predictor ---
export const AmbulanceETAPredictor = ({ hospitalName }) => {
    const [formData, setFormData] = useState({ start_node: 'Downtown', end_node: 'Central City General', hour: '12' });
    const [result, setResult] = useState(null);
    const [meta, setMeta] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/api/hosp/predict_eta', {
                method: 'POST',
                body: JSON.stringify({
                    start_node: formData.start_node,
                    end_node: formData.end_node,
                    hour: parseInt(formData.hour)
                })
            });
            const data = res.ok ? res.data : { error: 'ETA prediction unavailable' };
            if (data.error) {
                setResult({ error: data.error });
            } else {
                setResult(data);
                setMeta(data.meta || null);
            }
        } catch (err) {
            console.error(err);
            setResult({ error: `Failed to predict ETA: ${err.message}` });
        } finally {
            setLoading(false);
        }
    };

    const locations = ['Downtown', 'Central City General', 'St. Jude Hospital', 'Mercy West', 'North Sector'];

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg text-gray-900 mb-4">Ambulance ETA & Route</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                    <div>
                        <label className="text-xs font-bold text-gray-600 mb-1 block">From</label>
                        <select value={formData.start_node} onChange={(e) => setFormData({...formData, start_node: e.target.value})} className="w-full p-2 border rounded bg-gray-50 text-sm">
                            {locations.map(n => <option key={n} value={n}>{n}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-600 mb-1 block">To</label>
                        <select value={formData.end_node} onChange={(e) => setFormData({...formData, end_node: e.target.value})} className="w-full p-2 border rounded bg-gray-50 text-sm">
                            {locations.map(n => <option key={n} value={n}>{n}</option>)}
                        </select>
                    </div>
                </div>
                <Input type="number" min="0" max="23" value={formData.hour} onChange={(e) => setFormData({...formData, hour: e.target.value})} label="Hour (0-23)" />
                <button type="submit" disabled={loading} className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded font-bold disabled:opacity-50">{loading ? 'Calculating...' : 'Predict ETA'}</button>
            </form>
            {result && (
                <div className="mt-4 p-3 bg-blue-50 border-l-4 border-blue-500 rounded">
                    {result.error ? (
                        <p className="text-sm font-semibold text-red-600"><i className="fas fa-exclamation-circle mr-2"></i>{result.error}</p>
                    ) : (
                        <>
                            <p className="text-lg font-bold text-blue-700">ETA: {result.eta_minutes} mins</p>
                            <p className="text-xs text-gray-600 mt-2">Base Time: {result.base_minutes} mins</p>
                            <p className="text-xs text-gray-600">Traffic Multiplier: {result.traffic_multiplier}x</p>
                            {result.route && <p className="text-xs text-gray-600 mt-2">Route: {result.route.join(' → ')}</p>}
                        </>
                    )}
                </div>
            )}
            <ExplainabilityPanel meta={meta} />
        </DashboardCard>
    );
};

// --- 2. Bed Forecast Predictor ---
export const BedForecastPredictor = ({ hospitalId }) => {
    const [formData, setFormData] = useState({ emergency_count: 50, disease_case_count: 30, current_bed_occupancy: 85 });
    const [result, setResult] = useState(null);
    const [meta, setMeta] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/api/hosp/predict_bed_forecast', {
                method: 'POST',
                body: JSON.stringify({
                    emergency_count: parseInt(formData.emergency_count),
                    disease_case_count: parseInt(formData.disease_case_count),
                    current_bed_occupancy: parseInt(formData.current_bed_occupancy),
                    hospital_id: 1
                })
            });
            const data = res.ok ? res.data : { error: 'Bed forecast unavailable' };
            if (data.error) {
                setResult({ error: data.error });
            } else {
                setResult(data);
                setMeta(data.meta || null);
            }
        } catch (err) {
            console.error(err);
            setResult({ error: `Failed to predict bed demand: ${err.message}` });
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg text-gray-900 mb-4">Bed Demand Forecast</h3>
            <form onSubmit={handleSubmit} className="space-y-3">
                <Input type="number" name="emergency_count" min="0" placeholder="Weekly Emergencies" value={formData.emergency_count} onChange={handleChange} />
                <Input type="number" name="disease_case_count" min="0" placeholder="Disease Cases" value={formData.disease_case_count} onChange={handleChange} />
                <Input type="number" name="current_bed_occupancy" min="0" max="100" placeholder="Current Occupancy %" value={formData.current_bed_occupancy} onChange={handleChange} />
                <button type="submit" disabled={loading} className="w-full bg-orange-500 hover:bg-orange-600 text-white py-2 rounded font-bold disabled:opacity-50">{loading ? 'Forecasting...' : 'Predict Demand'}</button>
            </form>
            {result && (
                <div className="mt-4 p-3 bg-orange-50 border-l-4 border-orange-500 rounded">
                    {result.error ? (
                        <p className="text-sm font-semibold text-red-600"><i className="fas fa-exclamation-circle mr-2"></i>{result.error}</p>
                    ) : (
                        <>
                            <p className="text-gray-600 text-sm">Predicted Demand:</p>
                            <p className="text-3xl font-bold text-orange-600">{result.predicted_bed_demand} Beds</p>
                        </>
                    )}
                </div>
            )}
            <ExplainabilityPanel meta={meta} />
        </DashboardCard>
    );
};

// --- 3. Staff Allocator ---
export const StaffAllocator = () => {
    const [formData, setFormData] = useState({ patient_load: 'Medium', department: 'ER', shift: 'Day' });
    const [result, setResult] = useState(null);
    const [meta, setMeta] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/api/hosp/predict_staff_allocation', {
                method: 'POST',
                body: JSON.stringify({
                    patient_load: formData.patient_load,
                    department: formData.department,
                    shift: formData.shift
                })
            });
            const data = res.ok ? res.data : { error: 'Staff allocation unavailable' };
            if (data.error) {
                setResult({ error: data.error });
            } else {
                setResult(data);
                setMeta(data.meta || null);
            }
        } catch (err) {
            console.error(err);
            setResult({ error: `Failed to get allocation: ${err.message}` });
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg text-gray-900 mb-4">AI Staff Allocation</h3>
            <form onSubmit={handleSubmit} className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                    <div>
                        <label className="text-xs font-bold text-gray-600 mb-1 block">Department</label>
                        <select value={formData.department} onChange={e => setFormData({...formData, department: e.target.value})} className="w-full p-2 border rounded text-sm">
                            <option value="ER">ER</option>
                            <option value="ICU">ICU</option>
                            <option value="Ward">Ward</option>
                            <option value="Surgery">Surgery</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-600 mb-1 block">Patient Load</label>
                        <select value={formData.patient_load} onChange={e => setFormData({...formData, patient_load: e.target.value})} className="w-full p-2 border rounded text-sm">
                            <option value="Low">Low</option>
                            <option value="Medium">Medium</option>
                            <option value="High">High</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-600 mb-1 block">Shift</label>
                        <select value={formData.shift} onChange={e => setFormData({...formData, shift: e.target.value})} className="w-full p-2 border rounded text-sm">
                            <option value="Day">Day</option>
                            <option value="Night">Night</option>
                            <option value="Evening">Evening</option>
                        </select>
                    </div>
                </div>
                <button type="submit" disabled={loading} className="w-full bg-purple-600 hover:bg-purple-700 text-white py-2 rounded font-bold disabled:opacity-50">{loading ? 'Calculating...' : 'Get Allocation'}</button>
            </form>
            {result && (
                <div className="mt-4 p-3 bg-purple-50 border-l-4 border-purple-500 rounded">
                    {result.error ? (
                        <p className="text-sm font-semibold text-red-600"><i className="fas fa-exclamation-circle mr-2"></i>{result.error}</p>
                    ) : (
                        <p className="font-bold text-purple-700 text-center">
                            <i className="fas fa-users mr-2"></i>
                            {typeof result.allocation_decision === 'string' ? result.allocation_decision.replace(/_/g, ' ') : 'Allocation: ' + String(result.allocation_decision)}
                        </p>
                    )}
                </div>
            )}
            <ExplainabilityPanel meta={meta} />
        </DashboardCard>
    );
};

// --- 4. Disease Forecast Chart ---
export const HospitalDiseaseForecast = ({ hospitalId }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [selectedDisease, setSelectedDisease] = useState('Influenza');
    const [daysForecast, setDaysForecast] = useState(7);
    const [meta, setMeta] = useState(null);

    const fetchForecast = async (disease = selectedDisease, days = daysForecast) => {
        setLoading(true);
        setError(null);
        try {
            const res = await apiFetch('/api/hosp/predict_disease_forecast', {
                method: 'POST',
                body: JSON.stringify({
                    hospital_id: hospitalId || 1,
                    disease_name: disease,
                    days_to_predict: parseInt(days)
                })
            });
            const json = res.ok ? res.data : { error: 'Forecast unavailable' };
            if (json.error) {
                setError(json.error);
                setData(null);
                setMeta(null);
            } else if (json.forecast && json.forecast.length > 0) {
                setData({
                    labels: json.forecast.map(d => d.date),
                    datasets: [{
                        label: `Predicted ${disease} Cases`,
                        data: json.forecast.map(d => d.predicted_cases),
                        borderColor: disease === 'Influenza' ? 'rgb(239, 68, 68)' : 'rgb(59, 130, 246)',
                        backgroundColor: disease === 'Influenza' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4,
                    }]
                });
                setError(null);
                setMeta(json.meta || null);
            } else {
                setError('No forecast data available');
                setData(null);
                setMeta(null);
            }
        } catch (err) {
            console.error(err);
            setError(`Failed to fetch forecast: ${err.message}`);
            setData(null);
        } finally {
            setLoading(false);
        }
    };

    React.useEffect(() => {
        if (hospitalId) {
            fetchForecast();
        }
    }, [hospitalId]);

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg text-gray-900 mb-4">Disease Forecast</h3>
            <div className="mb-4 flex gap-2">
                <select value={selectedDisease} onChange={(e) => {setSelectedDisease(e.target.value); fetchForecast(e.target.value, daysForecast);}} className="p-2 border rounded text-sm flex-1">
                    <option value="Influenza">Influenza</option>
                    <option value="COVID-19">COVID-19</option>
                    <option value="Dengue">Dengue</option>
                </select>
                <input type="number" min="1" max="30" value={daysForecast} onChange={(e) => {setDaysForecast(e.target.value); fetchForecast(selectedDisease, e.target.value);}} placeholder="Days" className="p-2 border rounded text-sm w-20" />
            </div>
            {loading && <LoadingSpinner />}
            {error && <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700"><i className="fas fa-exclamation-circle mr-2"></i>{error}</div>}
            {data && (
                <div className="h-64">
                    <Line options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'top' } } }} data={data} />
                </div>
            )}
            <ExplainabilityPanel meta={meta} />
        </DashboardCard>
    );
};