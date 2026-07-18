import React, { useState } from 'react';
import { apiFetch } from '../config/api';
import { DashboardCard, Input, LoadingSpinner } from './Common';

const AuthorityResources = () => {
    const [loading, setLoading] = useState(false);
    const [prediction, setPrediction] = useState(null);
    const [formData, setFormData] = useState({
        region: 'Central City',
        resourceType: 'Blood O+',
        month: '11',
        frequency: '150',
        currentStock: '75'
    });

    const handlePredict = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const { ok, data } = await apiFetch('/api/gov/predict_availability', {
                method: 'POST',
                body: JSON.stringify({
                    month: parseInt(formData.month),
                    donation_frequency: parseInt(formData.frequency),
                    hospital_stock_level: parseInt(formData.currentStock),
                    region: formData.region,
                    resource_type: formData.resourceType
                })
            });
            if (!ok) {
                setPrediction({ error: data?.message || 'Prediction request failed' });
            } else if (data.error) {
                setPrediction({ error: data.error });
            } else {
                setPrediction({
                    forecast_message: `Predicted Availability Score: ${data.predicted_availability_score}% - Resource availability is ${data.predicted_availability_score > 70 ? 'Strong' : data.predicted_availability_score > 40 ? 'Moderate' : 'Low'} for the selected parameters.`
                });
            }
        } catch (err) {
            console.error("Prediction Error:", err);
            setPrediction({ error: `Failed to get prediction: ${err.message}` });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
            {/* Table: Regional Resource Allocation */}
            <DashboardCard>
                <h3 className="font-bold text-xl text-slate-800 mb-6 flex items-center gap-2">
                    <i className="fas fa-truck-ramp-box text-blue-500"></i> Regional Resource Allocation
                </h3>
                <div className="overflow-hidden rounded-xl border border-slate-100">
                    <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-4 py-3 font-bold text-slate-600">Hospital</th>
                                <th className="px-4 py-3 font-bold text-slate-600">Critical Item</th>
                                <th className="px-4 py-3 font-bold text-slate-600">Stock Level</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {[
                                { h: 'City General', item: 'O- Blood', stock: '12%' },
                                { h: 'St. Jude', item: 'Ventilators', stock: '8%' },
                                { h: 'Mercy West', item: 'PPE Kits', stock: '15%' }
                            ].map((row, i) => (
                                <tr key={i} className="hover:bg-slate-50/50 transition">
                                    <td className="px-4 py-3 font-medium">{row.h}</td>
                                    <td className="px-4 py-3 text-red-600 font-bold">{row.item}</td>
                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <div className="w-full bg-slate-200 rounded-full h-1.5">
                                                <div className="bg-red-500 h-1.5 rounded-full" style={{ width: row.stock }}></div>
                                            </div>
                                            <span className="text-[10px] font-bold">{row.stock}</span>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </DashboardCard>

            {/* AI Form: Availability Forecast */}
            <DashboardCard className="bg-gradient-to-br from-white to-green-50/30">
                <h3 className="font-bold text-xl text-slate-800 mb-2 flex items-center gap-2">
                    <i className="fas fa-crystal-ball text-green-600"></i> Resource Availability Forecast
                </h3>
                <p className="text-xs text-slate-500 mb-6">AI prediction based on donation frequency and seasonal demand.</p>
                
                <form onSubmit={handlePredict} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <Input label="Region" icon="fa-map-pin" value={formData.region} onChange={e => setFormData({...formData, region: e.target.value})} />
                        <Input label="Resource Type" icon="fa-droplet" value={formData.resourceType} onChange={e => setFormData({...formData, resourceType: e.target.value})} />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <Input label="Month (1-12)" type="number" icon="fa-calendar" value={formData.month} onChange={e => setFormData({...formData, month: e.target.value})} />
                        <Input label="Donation Frequency" type="number" icon="fa-hand-holding-medical" value={formData.frequency} onChange={e => setFormData({...formData, frequency: e.target.value})} />
                    </div>
                    <Input label="Current Regional Stock (%)" type="number" icon="fa-boxes-stacked" value={formData.currentStock} onChange={e => setFormData({...formData, currentStock: e.target.value})} />
                    
                    <button className="w-full bg-green-600 hover:bg-green-700 text-white py-3 rounded-xl font-bold shadow-lg transition transform active:scale-95">
                        {loading ? <i className="fas fa-spinner fa-spin"></i> : 'Predict Availability'}
                    </button>
                </form>

                {prediction && (
                    <div className="mt-6 p-4 bg-white border border-green-100 rounded-xl shadow-inner animate-slide-in-up">
                        {prediction.error ? (
                            <div className="text-sm font-semibold text-red-600">
                                <i className="fas fa-exclamation-circle mr-2"></i>
                                {prediction.error}
                            </div>
                        ) : (
                            <>
                                <p className="text-xs font-bold text-slate-400 uppercase mb-2">AI Forecast Result</p>
                                <div className="text-lg font-bold text-green-700">
                                    {prediction.forecast_message}
                                </div>
                            </>
                        )}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export default AuthorityResources;