import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';
import { DashboardCard, ExplainabilityPanel, LoadingSpinner, StatusPill } from './Common';

const defaultScenario = {
    emergencyDelta: 0,
    staffDelta: 0,
    plannedDischarges: 0
};

const HospitalAnalytics = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [insights, setInsights] = useState(null);
    const [loading, setLoading] = useState(true);
    const [scenario, setScenario] = useState(defaultScenario);
    const [simulating, setSimulating] = useState(false);
    const cacheKey = hospitalId ? `hospital_ai_${hospitalId}` : 'hospital_ai';

    const loadInsights = async (withSpinner = false) => {
        if (!hospitalId) {
            setInsights(null);
            setLoading(false);
            return;
        }
        const showSpinner = withSpinner === true && !insights;
        if (showSpinner) setLoading(true);
        try {
            const res = await apiFetch(`/api/hospital-ops/ceo/ai-insights?hospitalId=${hospitalId}`, { method: 'GET' });
            setInsights(res.ok ? res.data : null);
            if (res.ok) {
                localStorage.setItem(cacheKey, JSON.stringify(res.data || {}));
            }
        } finally {
            if (showSpinner) setLoading(false);
        }
    };

    const simulate = async () => {
        if (!hospitalId) return;
        setSimulating(true);
        try {
            const payload = {
                hospitalId,
                emergencyDelta: Number(scenario.emergencyDelta || 0),
                staffDelta: Number(scenario.staffDelta || 0),
                plannedDischarges: Number(scenario.plannedDischarges || 0)
            };
            const res = await apiFetch('/api/hospital-ops/ceo/ai-insights/simulate', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                setInsights(res.data);
            }
        } finally {
            setSimulating(false);
        }
    };

    useEffect(() => {
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setInsights(parsed || null);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        loadInsights(!hasCache);
    }, [hospitalId]);

    if (loading && !insights) {
        return <LoadingSpinner />;
    }

    if (!hospitalId) {
        return (
            <DashboardCard>
                <div className="text-sm text-gray-500">Hospital profile not loaded yet.</div>
            </DashboardCard>
        );
    }

    const spikeRisk = insights?.emergency_spike_risk || 'Low';
    const spikeColor = spikeRisk === 'High' ? 'red' : spikeRisk === 'Medium' ? 'yellow' : 'green';

    return (
        <div className="space-y-6 animate-fade-in pb-10">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-2">AI Recommendations</h3>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-500">Predicted inflow (24h)</span>
                            <span className="font-semibold text-gray-900">{insights?.predicted_inflow || 0}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-500">Emergency spike risk</span>
                            <StatusPill text={spikeRisk} color={spikeColor} />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Overloaded departments</p>
                            <div className="flex flex-wrap gap-2 mt-1">
                                {(insights?.overloaded_departments || []).length === 0 ? (
                                    <span className="text-xs text-gray-400">None detected</span>
                                ) : (
                                    insights.overloaded_departments.map((dept) => (
                                        <span key={dept} className="text-xs bg-red-50 text-red-700 px-2 py-1 rounded-full">
                                            {dept}
                                        </span>
                                    ))
                                )}
                            </div>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Staff redistribution</p>
                            <p className="text-sm font-semibold text-gray-900">{insights?.staff_redistribution || 'No change recommended'}</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Bed allocation strategy</p>
                            <p className="text-sm font-semibold text-gray-900">{insights?.bed_allocation_strategy || 'Maintain current plan'}</p>
                        </div>
                    </div>
                    <ExplainabilityPanel meta={insights?.meta} />
                </DashboardCard>

                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-2">Scenario Simulator</h3>
                    <div className="grid grid-cols-1 gap-3">
                        <label className="text-xs text-gray-500">Expected emergency change</label>
                        <input
                            type="number"
                            className="p-2 border rounded"
                            value={scenario.emergencyDelta}
                            onChange={(e) => setScenario({ ...scenario, emergencyDelta: Number(e.target.value) })}
                        />
                        <label className="text-xs text-gray-500">Staff availability delta</label>
                        <input
                            type="number"
                            className="p-2 border rounded"
                            value={scenario.staffDelta}
                            onChange={(e) => setScenario({ ...scenario, staffDelta: Number(e.target.value) })}
                        />
                        <label className="text-xs text-gray-500">Planned discharges</label>
                        <input
                            type="number"
                            className="p-2 border rounded"
                            value={scenario.plannedDischarges}
                            onChange={(e) => setScenario({ ...scenario, plannedDischarges: Number(e.target.value) })}
                        />
                        <button
                            className="bg-indigo-600 text-white rounded px-4 py-2"
                            onClick={simulate}
                            disabled={simulating}
                        >
                            {simulating ? 'Simulating...' : 'Run Scenario'}
                        </button>
                    </div>
                </DashboardCard>
            </div>

            <DashboardCard>
                <h3 className="font-bold text-lg text-gray-900 mb-2">Cost Pressure Signals</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                        <p className="text-xs text-gray-500">Cost pressure index</p>
                        <p className="text-xl font-bold text-gray-900">{insights?.cost_pressure_index ?? 0}</p>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                        <p className="text-xs text-gray-500">Margin at risk</p>
                        <p className="text-xl font-bold text-gray-900">₹{insights?.margin_at_risk ?? 0}</p>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                        <p className="text-xs text-gray-500">Optimization focus</p>
                        <p className="text-sm font-semibold text-gray-900">{insights?.cost_optimization || 'Maintain procurement plan'}</p>
                    </div>
                </div>
                <div className="mt-4">
                    <p className="text-xs text-gray-500 mb-2">Top cost drivers</p>
                    {(insights?.top_cost_drivers || []).length === 0 ? (
                        <div className="text-sm text-gray-500">No major cost drivers detected.</div>
                    ) : (
                        <div className="space-y-2">
                            {insights.top_cost_drivers.map((item) => (
                                <div key={item.category} className="flex items-center justify-between border rounded px-3 py-2 text-sm">
                                    <span className="text-gray-600">{item.category}</span>
                                    <span className="font-semibold text-gray-900">₹{item.amount}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </DashboardCard>

            <DashboardCard>
                <h3 className="font-bold text-lg text-gray-900 mb-2">Operational Notes</h3>
                <div className="space-y-2">
                    {(insights?.insight_notes || []).length === 0 ? (
                        <div className="text-sm text-gray-500">No operational notes yet.</div>
                    ) : (
                        (insights?.insight_notes || []).map((note, idx) => (
                            <div key={`${note}-${idx}`} className="text-sm text-gray-700 bg-slate-50 border border-slate-200 rounded px-3 py-2">
                                {note}
                            </div>
                        ))
                    )}
                </div>
            </DashboardCard>
        </div>
    );
};

export default HospitalAnalytics;
