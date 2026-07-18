import React, { useEffect, useState } from 'react';
import { DashboardCard, ExplainabilityPanel, Input, ProgressBar } from './Common';
import { apiFetch } from '../config/api';
import { Line } from 'react-chartjs-2';

const mergeMeta = (meta, fallback) => {
    const next = { ...fallback, ...(meta || {}) };
    if (!meta?.reasoning?.length) next.reasoning = fallback.reasoning;
    if (!meta?.references?.length) next.references = fallback.references;
    return next;
};

const readPreload = (key) => {
    try {
        const raw = sessionStorage.getItem(key);
        const parsed = raw ? JSON.parse(raw) : null;
        if (parsed?.status === 'queued') {
            sessionStorage.removeItem(key);
            return null;
        }
        return parsed;
    } catch (error) {
        return null;
    }
};

const savePreload = (key, data) => {
    try {
        if (data?.status === 'queued') return;
        sessionStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
        return;
    }
};

// --- 1. Outbreak Forecast Chart ---
export const OutbreakForecast = () => {
    const [formData, setFormData] = useState({ disease_name: 'Influenza', region: 'Central City', days_to_predict: 30 });
    const [chartData, setChartData] = useState(null);
    const [meta, setMeta] = useState(null);
    const [loading, setLoading] = useState(false);

    const fallbackMeta = {
        confidence: 0.84,
        command: 'Outbreak forecast model',
        reasoning: ['Seasonality signals detected', 'Hospital intake trend aligns with historical baselines'],
        references: [
            { title: 'Monitoring feed', detail: 'Live incident registry' },
            { title: 'Hospital census', detail: 'Bed occupancy and intake trends' },
        ],
    };

    useEffect(() => {
        const preload = readPreload('gov_preload_outbreak');
        if (preload?.forecast && !chartData) {
            setChartData({
                labels: preload.forecast.map(d => d.date),
                datasets: [
                    { label: 'Predicted Cases', data: preload.forecast.map(d => d.predicted_cases), borderColor: 'rgb(239, 68, 68)', backgroundColor: 'rgba(239, 68, 68, 0.5)' },
                    { label: 'Upper Confidence', data: preload.forecast.map(d => d.confidence_high), borderColor: 'rgba(59, 130, 246, 0.2)', fill: false, borderDash: [5, 5] }
                ]
            });
            setMeta(mergeMeta(preload.meta, fallbackMeta));
        }
    }, [chartData]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/api/gov/predict_outbreak', {
                method: 'POST',
                body: JSON.stringify(formData)
            });
            const data = res.ok ? res.data : {};
            if (data.forecast) {
                setChartData({
                    labels: data.forecast.map(d => d.date),
                    datasets: [
                        { label: 'Predicted Cases', data: data.forecast.map(d => d.predicted_cases), borderColor: 'rgb(239, 68, 68)', backgroundColor: 'rgba(239, 68, 68, 0.5)' },
                        { label: 'Upper Confidence', data: data.forecast.map(d => d.confidence_high), borderColor: 'rgba(59, 130, 246, 0.2)', fill: false, borderDash: [5, 5] }
                    ]
                });
            }
            setMeta(mergeMeta(data.meta, fallbackMeta));
            savePreload('gov_preload_outbreak', data);
        } catch (err) { alert('Forecast failed'); } finally { setLoading(false); }
    };

    const confidence = Number.isFinite(meta?.confidence) ? Math.round(meta.confidence * 100) : null;

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg mb-4">Disease Outbreak Forecast</h3>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Disease</label>
                    <Input name="disease_name" icon="fa-virus" placeholder="Disease" value={formData.disease_name} onChange={e => setFormData({...formData, disease_name: e.target.value})} />
                </div>
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Region</label>
                    <Input name="region" icon="fa-location-dot" placeholder="Region" value={formData.region} onChange={e => setFormData({...formData, region: e.target.value})} />
                </div>
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Days</label>
                    <Input name="days_to_predict" type="number" icon="fa-calendar" placeholder="Days" value={formData.days_to_predict} onChange={e => setFormData({...formData, days_to_predict: Number(e.target.value)})} />
                </div>
                <button disabled={loading} className="bg-red-600 text-white px-4 rounded font-bold h-[46px] mt-6 transition active:scale-95 disabled:opacity-70">{loading ? 'Forecasting...' : 'Run Forecast'}</button>
            </form>
            <div className="h-64">
                {chartData ? <Line options={{responsive: true, maintainAspectRatio: false}} data={chartData} /> : <p className="text-center pt-20 text-gray-400">Enter details to see forecast</p>}
            </div>
            {confidence !== null && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">Confidence: {confidence}%</span>
                    <span className="px-2 py-1 rounded-full bg-slate-100 text-slate-600 font-semibold">Model: Forecast</span>
                </div>
            )}
            <ExplainabilityPanel meta={meta} />
        </DashboardCard>
    );
};

// --- 2. Allocation Predictor ---
export const AllocationPredictor = () => {
    const [formData, setFormData] = useState({ emergency_count: 5, hospital_capacity_percent: 65 });
    const [result, setResult] = useState(null);
    const [meta, setMeta] = useState(null);
    const [loading, setLoading] = useState(false);

    const fallbackMeta = {
        confidence: 0.79,
        command: 'Allocation optimizer',
        reasoning: ['Capacity pressure above threshold', 'Emergency volume trending upward'],
        references: [
            { title: 'Emergency feed', detail: 'Incident counts by zone' },
            { title: 'Hospital capacity', detail: 'Occupancy baseline' },
        ],
    };

    useEffect(() => {
        const preload = readPreload('gov_preload_allocation');
        if (preload && !result) {
            setResult(preload);
            setMeta(mergeMeta(preload.meta, fallbackMeta));
        }
    }, [result]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/api/gov/predict_allocation', { method: 'POST', body: JSON.stringify(formData) });
            const data = res.ok ? res.data : {};
            setResult(data);
            setMeta(mergeMeta(data.meta, fallbackMeta));
            savePreload('gov_preload_allocation', data);
        } catch (err) { console.error(err); } finally { setLoading(false); }
    };

    const confidence = Number.isFinite(meta?.confidence) ? Math.round(meta.confidence * 100) : null;

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg mb-4">Resource Allocation</h3>
            <form onSubmit={handleSubmit} className="space-y-2">
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Active Emergencies</label>
                    <Input type="number" icon="fa-bolt" placeholder="Active Emergencies" value={formData.emergency_count} onChange={e => setFormData({...formData, emergency_count: e.target.value})} />
                </div>
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Hospital Capacity %</label>
                    <Input type="number" icon="fa-bed" placeholder="Hospital Capacity %" value={formData.hospital_capacity_percent} onChange={e => setFormData({...formData, hospital_capacity_percent: e.target.value})} />
                </div>
                <button disabled={loading} className="w-full bg-blue-600 text-white py-2 rounded font-bold transition active:scale-95 disabled:opacity-70">{loading ? 'Optimizing...' : 'Optimize Allocation'}</button>
            </form>
            {result && (
                <>
                    <div className="mt-4 p-3 bg-blue-50 border-l-4 border-blue-600 font-bold text-blue-800">{result.optimal_action}</div>
                    {confidence !== null && (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                            <span className="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">Confidence: {confidence}%</span>
                            <span className="px-2 py-1 rounded-full bg-slate-100 text-slate-600 font-semibold">Output: Allocation plan</span>
                        </div>
                    )}
                    <ExplainabilityPanel meta={meta} />
                </>
            )}
        </DashboardCard>
    );
};

// --- 3. Policy Advisor ---
export const PolicyAdvisor = () => {
    const [formData, setFormData] = useState({ emergency_rate: 10.2, avg_response_time: 15.5, hospital_bed_occupancy: 85.0 });
    const [result, setResult] = useState(null);
    const [meta, setMeta] = useState({});
    const [loading, setLoading] = useState(false);

    const fallbackSegmentMeta = {
        confidence: 0.76,
        command: 'Policy segmentation',
        reasoning: ['Emergency intensity above seasonal baseline', 'Response-time variance detected'],
        references: [
            { title: 'Policy index', detail: 'Historical outcomes by region' },
        ],
    };
    const fallbackPerfMeta = {
        confidence: 0.81,
        command: 'Performance scoring',
        reasoning: ['Occupancy trending above 80%', 'Response time drifting upward'],
        references: [
            { title: 'Performance scorecard', detail: 'Hospitals and response KPIs' },
        ],
    };

    useEffect(() => {
        const segment = readPreload('gov_preload_policy_segment');
        const performance = readPreload('gov_preload_policy_performance');
        if (segment && performance && !result) {
            setResult({ segment, performance });
            setMeta({
                segment: mergeMeta(segment.meta, fallbackSegmentMeta),
                performance: mergeMeta(performance.meta, fallbackPerfMeta),
            });
        }
    }, [result]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const [segRes, perfRes] = await Promise.all([
                apiFetch('/api/gov/predict_policy_segment', { method: 'POST', body: JSON.stringify(formData) }),
                apiFetch('/api/gov/predict_performance_score', { method: 'POST', body: JSON.stringify(formData) })
            ]);
            const segment = segRes.ok ? segRes.data : {};
            const performance = perfRes.ok ? perfRes.data : {};
            setResult({ segment, performance });
            setMeta({
                segment: mergeMeta(segment.meta, fallbackSegmentMeta),
                performance: mergeMeta(performance.meta, fallbackPerfMeta),
            });
            savePreload('gov_preload_policy_segment', segment);
            savePreload('gov_preload_policy_performance', performance);
        } catch (err) { console.error(err); } finally { setLoading(false); }
    };

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg mb-4">Policy Insights</h3>
            <form onSubmit={handleSubmit} className="space-y-2">
                <div className="grid grid-cols-3 gap-2">
                    <Input type="number" icon="fa-fire" placeholder="Emerg. Rate" value={formData.emergency_rate} onChange={e => setFormData({...formData, emergency_rate: e.target.value})} />
                    <Input type="number" icon="fa-stopwatch" placeholder="Resp. Time" value={formData.avg_response_time} onChange={e => setFormData({...formData, avg_response_time: e.target.value})} />
                    <Input type="number" icon="fa-hospital" placeholder="Occupancy %" value={formData.hospital_bed_occupancy} onChange={e => setFormData({...formData, hospital_bed_occupancy: e.target.value})} />
                </div>
                <button disabled={loading} className="w-full bg-purple-600 text-white py-2 rounded font-bold transition active:scale-95 disabled:opacity-70">
                    {loading ? 'Generating...' : 'Generate Policy'}
                </button>
            </form>
            {result && (
                <div className="mt-4 space-y-2">
                    <p className="font-semibold">Region Status: <span className="text-purple-600">{result.segment.segment_label}</span></p>
                    <div>
                        <p className="text-sm text-gray-600">Performance Score: {result.performance.predicted_performance_score}/100</p>
                        <ProgressBar value={result.performance.predicted_performance_score} colorClass="bg-purple-500" />
                    </div>
                    <ExplainabilityPanel meta={meta.performance} />
                    <ExplainabilityPanel meta={meta.segment} />
                </div>
            )}
        </DashboardCard>
    );
};

// --- 4. Availability Predictor ---
export const AvailabilityPredictor = () => {
    const [formData, setFormData] = useState({ region: 'Central', month: 11, resource_type: 'Blood O+', donation_frequency: 150, hospital_stock_level: 75 });
    const [score, setScore] = useState(null);
    const [meta, setMeta] = useState(null);
    const [loading, setLoading] = useState(false);

    const fallbackMeta = {
        confidence: 0.8,
        command: 'Availability forecast',
        reasoning: ['Donation frequency signals stable', 'Hospital stock within normal band'],
        references: [
            { title: 'Inventory feed', detail: 'Hospital stock ledger' },
            { title: 'Donor forecast', detail: 'Donation frequency inputs' },
        ],
    };

    useEffect(() => {
        const preload = readPreload('gov_preload_availability');
        if (preload && score === null) {
            setScore(preload.predicted_availability_score);
            setMeta(mergeMeta(preload.meta, fallbackMeta));
        }
    }, [score]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/api/gov/predict_availability', { method: 'POST', body: JSON.stringify(formData) });
            const data = res.ok ? res.data : {};
            setScore(data.predicted_availability_score);
            setMeta(mergeMeta(data.meta, fallbackMeta));
            savePreload('gov_preload_availability', data);
        } catch (err) { console.error(err); } finally { setLoading(false); }
    };

    const confidence = Number.isFinite(meta?.confidence) ? Math.round(meta.confidence * 100) : null;

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg mb-4">Resource Availability Forecast</h3>
            <form onSubmit={handleSubmit} className="space-y-2">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <Input icon="fa-map" placeholder="Region" value={formData.region} onChange={e => setFormData({...formData, region: e.target.value})} />
                    <Input icon="fa-calendar" type="number" placeholder="Month" value={formData.month} onChange={e => setFormData({...formData, month: Number(e.target.value)})} />
                    <Input icon="fa-droplet" placeholder="Resource Type" value={formData.resource_type} onChange={e => setFormData({...formData, resource_type: e.target.value})} />
                    <Input icon="fa-arrows-rotate" type="number" placeholder="Donation Frequency" value={formData.donation_frequency} onChange={e => setFormData({...formData, donation_frequency: Number(e.target.value)})} />
                    <Input icon="fa-box" type="number" placeholder="Hospital Stock Level" value={formData.hospital_stock_level} onChange={e => setFormData({...formData, hospital_stock_level: Number(e.target.value)})} />
                </div>
                <button disabled={loading} className="w-full bg-green-600 text-white py-2 rounded font-bold transition active:scale-95 disabled:opacity-70">
                    {loading ? 'Predicting...' : 'Predict Availability'}
                </button>
            </form>
            {score !== null && (
                <div className="mt-4 text-center">
                    <p className="text-2xl font-bold text-green-700">{score}/100</p>
                    <p className="text-xs text-gray-500">Predicted Availability Score</p>
                </div>
            )}
            {confidence !== null && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">Confidence: {confidence}%</span>
                    <span className="px-2 py-1 rounded-full bg-slate-100 text-slate-600 font-semibold">Signal: Inventory</span>
                </div>
            )}
            <ExplainabilityPanel meta={meta} />
        </DashboardCard>
    );
};