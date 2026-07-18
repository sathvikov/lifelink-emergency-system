import React, { useState } from 'react';
import { apiFetch } from '../config/api';
import { DashboardCard, ExplainabilityPanel, Input } from './Common';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, BarChart, Bar } from 'recharts';

const AuthorityAI = () => {
    const [policyData, setPolicyData] = useState(null);
    const [ambulanceData, setAmbulanceData] = useState(null);
    const [severityData, setSeverityData] = useState(null);
    const [anomalyData, setAnomalyData] = useState(null);
    const [outbreakData, setOutbreakData] = useState(null);

    const [loading, setLoading] = useState({});

    const [inputs, setInputs] = useState({
        rate: '10.2', time: '15.5', occupancy: '85',
        emergencies: '5', nearestCap: '65',
        type: 'Accident', region: 'Central City', density: '5000', resTime: '15',
        anomRegion: 'Central City', dailyCount: '50', admissions: '20', reports: '30',
        disease: 'COVID-19', outRegion: 'Central City'
    });

    const triggerML = async (endpoint, payload, setter, key) => {
        // Clear old result and set loading
        setter(null);
        setLoading(prev => ({ ...prev, [key]: true }));

        try {
            const { ok, status, data } = await apiFetch(`/api/gov/${endpoint}`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            if (!ok) {
                console.error(`API Error [${endpoint}]: Status ${status}`);
                throw new Error(`API Error: ${status}`);
            }
            console.log(`API Success [${endpoint}]:`, data);
            
            if (data.error) {
                throw new Error(data.error);
            }

            setter({ ...data, _ts: Date.now() });
        } catch (err) {
            console.error(`Error in ${key}:`, err.message);
            // Show error instead of dummy data
            setter({ 
                error: true,
                message: `Failed to load ${key} data: ${err.message}`,
                _ts: Date.now() 
            });
        } finally {
            setLoading(prev => ({ ...prev, [key]: false }));
        }
    };

    return (
        <div className="space-y-6 animate-fade-in pb-20">
            {/* Error Boundary */}
            {(() => {
                try {
                    return (
                        <>
            
            {/* SECTION 1: Policy & Performance */}
            <DashboardCard className="border-t-8 border-indigo-600">
                <h3 className="font-bold text-xl text-slate-800 mb-2">Policy & Performance Insights</h3>
                <p className="text-xs text-slate-500 mb-6">Enter regional metrics to generate AI-driven policy insights.</p>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase mb-1">Emergency Rate</label>
                        <Input value={inputs.rate} onChange={e => setInputs({...inputs, rate: e.target.value})} icon="fa-users" />
                    </div>
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase mb-1">Avg. Response Time</label>
                        <Input value={inputs.time} onChange={e => setInputs({...inputs, time: e.target.value})} icon="fa-stopwatch" />
                    </div>
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase mb-1">Bed Occupancy %</label>
                        <Input value={inputs.occupancy} onChange={e => setInputs({...inputs, occupancy: e.target.value})} icon="fa-bed" />
                    </div>
                    <button onClick={() => triggerML('predict_performance_score', { emergency_rate: inputs.rate, avg_response_time: inputs.time, hospital_bed_occupancy: inputs.occupancy }, setPolicyData, 'policy')} 
                        className="bg-indigo-600 text-white py-3 rounded-xl font-bold shadow-lg hover:bg-indigo-700 active:scale-95 transition-all">
                        {loading.policy ? <i className="fas fa-spinner fa-spin"></i> : 'Generate Insights'}
                    </button>
                </div>
                {policyData && (
                    policyData.error ? (
                        <div className="mt-6 p-4 bg-red-50 rounded-xl border-l-4 border-red-500 text-red-700">
                            <p className="font-bold">{policyData.message || 'Failed to load performance data'}</p>
                        </div>
                    ) : (
                        <>
                            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4 animate-slide-in-up">
                                <div className="p-4 bg-slate-50 rounded-xl border-l-4 border-indigo-500">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Performance Score</p>
                                    <p className="text-xl font-bold text-indigo-700">{policyData.predicted_performance_score || 0}</p>
                                </div>
                                <div className="p-4 bg-slate-50 rounded-xl border-l-4 border-orange-500">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Health Outcome Score</p>
                                    <p className="text-xl font-bold text-orange-600">{Math.round((policyData.predicted_performance_score || 0) * 1.2) % 100}</p>
                                </div>
                            </div>
                            <ExplainabilityPanel meta={policyData.meta} />
                        </>
                    )
                )}
            </DashboardCard>

            {/* SECTION 2: Ambulance & Severity */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h4 className="font-bold text-slate-800 mb-4">Ambulance Allocation Optimizer</h4>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Active Emergencies</label>
                            <Input value={inputs.emergencies} onChange={e => setInputs({ ...inputs, emergencies: e.target.value })} />
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Hospital Capacity %</label>
                            <Input value={inputs.nearestCap} onChange={e => setInputs({ ...inputs, nearestCap: e.target.value })} />
                        </div>
                    </div>
                    <button onClick={() => triggerML('predict_allocation', { emergency_count: parseInt(inputs.emergencies), hospital_capacity_percent: parseInt(inputs.nearestCap) }, setAmbulanceData, 'ambulance')}
                        className="w-full bg-sky-500 text-white py-3 rounded-xl font-bold hover:bg-sky-600 active:scale-95 transition-all">
                        {loading.ambulance ? <i className="fas fa-spinner fa-spin"></i> : 'Get Recommendation'}
                    </button>
                    {ambulanceData && (
                        ambulanceData.error ? (
                            <div className="mt-4 p-4 bg-red-50 rounded-xl border-l-4 border-red-500 text-red-700">
                                <p className="font-bold">{ambulanceData.message || 'Failed to get ambulance recommendation'}</p>
                            </div>
                        ) : (
                            <>
                                <div className="mt-4 p-4 bg-blue-50 rounded-xl border-l-4 border-blue-500 flex items-center gap-3 animate-slide-in-up">
                                    <i className="fas fa-ambulance text-blue-600 text-2xl"></i>
                                    <div>
                                        <p className="text-[10px] font-bold text-blue-400 uppercase">AI Recommendation</p>
                                        <p className="font-bold text-blue-800">{ambulanceData.optimal_action || `Recommended: ${ambulanceData.action_id} ambulance(s)`}</p>
                                    </div>
                                </div>
                                <ExplainabilityPanel meta={ambulanceData.meta} />
                            </>
                        )
                    )}
                </DashboardCard>

                <DashboardCard>
                    <h4 className="font-bold text-slate-800 mb-4">Emergency Severity Prediction</h4>
                    <div className="grid grid-cols-4 gap-4 mb-4">
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Emergency Type</label>
                            <select className="p-3 border rounded-xl bg-gray-50 text-sm w-full" value={inputs.type} onChange={e => setInputs({ ...inputs, type: e.target.value })}>
                                <option>Accident</option>
                                <option>Cardiac</option>
                                <option>Stroke</option>
                            </select>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Region</label>
                            <Input value={inputs.region} onChange={e => setInputs({ ...inputs, region: e.target.value })} />
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Population Density</label>
                            <Input value={inputs.density} onChange={e => setInputs({ ...inputs, density: e.target.value })} />
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Response Time (min)</label>
                            <Input value={inputs.resTime} onChange={e => setInputs({ ...inputs, resTime: e.target.value })} />
                        </div>
                    </div>
                    <button onClick={() => triggerML('predict_severity', { emergency_type: inputs.type, region: inputs.region, population_density: parseInt(inputs.density), avg_response_time_min: parseInt(inputs.resTime) }, setSeverityData, 'severity')}
                        className="w-full bg-indigo-500 text-white py-3 rounded-xl font-bold hover:bg-indigo-600 active:scale-95 transition-all">
                        {loading.severity ? <i className="fas fa-spinner fa-spin"></i> : 'Predict Severity'}
                    </button>
                    {severityData && (
                        severityData.error ? (
                            <div className="mt-4 p-4 bg-red-50 rounded-xl border-l-4 border-red-500 text-red-700">
                                <p className="font-bold">{severityData.message || 'Failed to predict severity'}</p>
                            </div>
                        ) : (
                            <>
                                <div className="mt-4 p-4 bg-red-50 rounded-xl border-l-4 border-red-500 animate-slide-in-up">
                                    <p className="text-[10px] font-bold text-red-400 uppercase">AI Prediction Result</p>
                                    <p className="text-xl font-bold text-red-700">{severityData.predicted_severity || severityData.status}</p>
                                    <p className="text-[10px] text-slate-400 mt-1 italic">Last Calculated: {new Date().toLocaleTimeString()}</p>
                                </div>
                                <ExplainabilityPanel meta={severityData.meta} />
                            </>
                        )
                    )}
                </DashboardCard>
            </div>

            {/* SECTION 3: Anomaly Detector */}
            <DashboardCard className="max-w-md">
                <h4 className="font-bold text-slate-800 mb-4">Data Anomaly Detector</h4>
                <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="col-span-2">
                        <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Region</label>
                        <Input value={inputs.anomRegion} onChange={e => setInputs({ ...inputs, anomRegion: e.target.value })} />
                    </div>
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Admissions</label>
                        <Input value={inputs.admissions} onChange={e => setInputs({ ...inputs, admissions: e.target.value })} />
                    </div>
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Incident Reports</label>
                        <Input value={inputs.reports} onChange={e => setInputs({ ...inputs, reports: e.target.value })} />
                    </div>
                </div>
                <button onClick={() => triggerML('predict_anomaly', { daily_emergency_count: parseInt(inputs.admissions), hospital_admissions: parseInt(inputs.admissions), disease_reports: parseInt(inputs.reports), region: inputs.anomRegion }, setAnomalyData, 'anomaly')}
                    className="w-full bg-orange-500 text-white py-3 rounded-xl font-bold hover:bg-orange-600 active:scale-95 transition-all">
                    {loading.anomaly ? <i className="fas fa-spinner fa-spin"></i> : 'Check for Anomaly'}
                </button>
                {anomalyData && (
                    anomalyData.error ? (
                        <div className="mt-4 p-4 bg-red-50 rounded-xl border-l-4 border-red-500 text-red-700">
                            <p className="font-bold">{anomalyData.message || 'Failed to check for anomalies'}</p>
                        </div>
                    ) : (
                        <>
                            <div className={`mt-4 p-4 rounded-xl border-l-4 flex items-center gap-3 animate-slide-in-up ${(anomalyData.is_anomaly || anomalyData.anomaly) ? 'bg-red-50 border-red-500' : 'bg-green-50 border-green-500'}`}>
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white ${(anomalyData.is_anomaly || anomalyData.anomaly) ? 'bg-red-500' : 'bg-green-500'}`}>
                                    <i className={`fas ${(anomalyData.is_anomaly || anomalyData.anomaly) ? 'fa-exclamation' : 'fa-check'}`}></i>
                                </div>
                                <div>
                                    <p className={`text-[10px] font-bold uppercase ${(anomalyData.is_anomaly || anomalyData.anomaly) ? 'text-red-400' : 'text-green-400'}`}>AI Anomaly Result</p>
                                    <p className={`font-bold ${(anomalyData.is_anomaly || anomalyData.anomaly) ? 'text-red-700' : 'text-green-700'}`}>{anomalyData.message}</p>
                                </div>
                            </div>
                            <ExplainabilityPanel meta={anomalyData.meta} />
                        </>
                    )
                )}
            </DashboardCard>

            {/* SECTION 4: Outbreak Forecast & Bar Charts */}
            <DashboardCard className="border-t-8 border-orange-500">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="font-bold text-xl text-slate-800">Regional Outbreak Forecast</h3>
                    <div className="flex gap-4">
                        <Input value={inputs.outRegion} onChange={e => setInputs({...inputs, outRegion: e.target.value})} placeholder="Region" />
                        <select className="p-2 border rounded-lg text-sm bg-white" value={inputs.disease} onChange={e => setInputs({...inputs, disease: e.target.value})}>
                            <option>COVID-19</option>
                            <option>Influenza</option>
                        </select>
                        <button onClick={() => triggerML('predict_outbreak', { disease_name: inputs.disease, region: inputs.outRegion, days_to_predict: 30 }, setOutbreakData, 'outbreak')}
                            className="bg-orange-600 text-white px-6 py-2 rounded-xl font-bold shadow-lg flex items-center gap-2 transition-all active:scale-95">
                            {loading.outbreak ? <i className="fas fa-spinner fa-spin"></i> : <><i className="fas fa-sync-alt"></i> Forecast Outbreak</>}
                        </button>
                    </div>
                </div>

                {outbreakData ? (
                    outbreakData.error ? (
                        <div className="p-6 bg-red-50 rounded-xl border border-red-200">
                            <p className="text-red-600 font-bold">{outbreakData.message || 'Failed to generate outbreak forecast'}</p>
                            <p className="text-red-500 text-sm mt-2">Please check the disease name and region. Available: COVID-19, Influenza in Central City.</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
                            {/* Area Chart: 7 cols - Shows predicted cases over time */}
                            <div className="lg:col-span-7 bg-slate-50 p-4 rounded-2xl h-80">
                                <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">Daily Case Projection - {outbreakData.disease_name} in {outbreakData.region}</p>
                                <ResponsiveContainer width="100%" height="90%">
                                    <AreaChart data={(outbreakData.forecast || []).slice(0, 30).map(f => ({ day: f.date, val: f.predicted_cases }))}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="day" style={{ fontSize: '10px' }} />
                                        <YAxis style={{ fontSize: '10px' }} />
                                        <Tooltip />
                                        <Area type="monotone" dataKey="val" stroke="#f97316" fill="#ffedd5" strokeWidth={3} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Stats: 5 cols - Shows forecast summary */}
                            <div className="lg:col-span-5 bg-slate-50 p-4 rounded-2xl h-80 flex flex-col justify-between">
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase mb-4">Forecast Summary</p>
                                    {outbreakData.forecast && outbreakData.forecast.length > 0 && (
                                        <>
                                            <div className="mb-3 p-3 bg-orange-50 rounded-lg border-l-4 border-orange-500">
                                                <p className="text-[10px] text-slate-400">Latest Prediction</p>
                                                <p className="text-lg font-bold text-orange-600">{outbreakData.forecast[outbreakData.forecast.length - 1].predicted_cases} cases</p>
                            </div>
                                            <div className="mb-3 p-3 bg-blue-50 rounded-lg border-l-4 border-blue-500">
                                                <p className="text-[10px] text-slate-400">Peak Expected</p>
                                                <p className="text-lg font-bold text-blue-600">{Math.max(...outbreakData.forecast.map(f => f.predicted_cases)) || 'N/A'} cases</p>
                                            </div>
                                            <div className="p-3 bg-green-50 rounded-lg border-l-4 border-green-500">
                                                <p className="text-[10px] text-slate-400">Forecast Period</p>
                                                <p className="text-lg font-bold text-green-600">{outbreakData.forecast.length} days</p>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>

                            {/* Confidence Range: 12 cols */}
                            <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="p-4 bg-yellow-50 rounded-xl border border-yellow-100">
                                    <h5 className="text-[10px] font-bold text-yellow-700 uppercase">Confidence Range (Day 30)</h5>
                                    {outbreakData.forecast && outbreakData.forecast.length > 0 && (
                                        <p className="text-sm font-bold text-slate-800 mt-1">Low: {outbreakData.forecast[outbreakData.forecast.length - 1].confidence_low} | High: {outbreakData.forecast[outbreakData.forecast.length - 1].confidence_high}</p>
                                    )}
                                </div>
                                <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
                                    <h5 className="text-[10px] font-bold text-slate-700 uppercase">Data Quality</h5>
                                    <p className="text-sm font-bold text-slate-800 mt-1">Real ML Prediction</p>
                                </div>
                                <div className="p-4 bg-indigo-50 rounded-xl border border-indigo-200">
                                    <h5 className="text-[10px] font-bold text-indigo-700 uppercase">Update Frequency</h5>
                                    <p className="text-sm font-bold text-slate-800 mt-1">Click to refresh</p>
                                </div>
                            </div>
                        </div>
                    )
                ) : (
                    <div className="h-64 flex flex-col items-center justify-center border-2 border-dashed rounded-2xl bg-slate-50 text-slate-400">
                        <i className="fas fa-chart-bar text-4xl mb-2"></i>
                        <p className="font-medium">Click Forecast Outbreak to generate ML predictions</p>
                    </div>
                )}
                {outbreakData && !outbreakData.error && (
                    <ExplainabilityPanel meta={outbreakData.meta} />
                )}
            </DashboardCard>
                        </>
                    );
                } catch (error) {
                    console.error("AuthorityAI Render Error:", error);
                    return (
                        <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
                            <p className="text-red-600 font-bold">Error rendering dashboard</p>
                            <p className="text-red-500 text-sm">{error.message}</p>
                        </div>
                    );
                }
            })()}
        </div>
    );
};

export default AuthorityAI;