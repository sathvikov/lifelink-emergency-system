import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';
import { DashboardCard, ExplainabilityPanel, Input, ProgressBar } from './Common';

// --- FIX: Define this OUTSIDE the main component ---
const LabeledInput = ({ label, name, type, placeholder, icon, value, onChange }) => (
    <div className="mb-3">
        <label className="block text-sm font-semibold text-gray-700 mb-1 ml-1">{label}</label>
        <Input 
            name={name} 
            type={type} 
            placeholder={placeholder} 
            icon={icon} 
            value={value} 
            onChange={onChange} // Ensure onChange is passed down
        />
    </div>
);

const HealthRiskCalculator = () => {
    const { user } = useAuth();
    const [formData, setFormData] = useState({
        age: '45', bmi: '28.5', blood_pressure: '140', heart_rate: '75',
        has_condition: '1', lifestyle_factor: 'Sedentary', symptoms: ''
    });
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [history, setHistory] = useState([]);
    const [saveMessage, setSaveMessage] = useState('');
    const [aiInsight, setAiInsight] = useState(null);
    const [aiLoading, setAiLoading] = useState(false);

    const historyKey = useMemo(
        () => (user?.id ? `lifelink:health-risk:${user.id}` : 'lifelink:health-risk'),
        [user?.id]
    );

    const loadHistory = async () => {
        if (!user?.id) return;
        try {
            const res = await apiFetch(`/api/health/risk/history/${user.id}`, { method: 'GET' });
            if (res.ok && Array.isArray(res.data?.data)) {
                setHistory(res.data.data.map((item) => ({
                    id: item._id || item.id,
                    date: item.createdAt,
                    risk_level: item.risk_level,
                    risk_score: item.risk_score,
                    bmi: item.payload?.bmi,
                    blood_pressure: item.payload?.blood_pressure,
                    heart_rate: item.payload?.heart_rate,
                    lifestyle: item.payload?.lifestyle_factor
                })));
                return;
            }
        } catch (err) {
            // Fallback to local storage
        }
        try {
            const stored = localStorage.getItem(historyKey);
            const parsed = stored ? JSON.parse(stored) : [];
            setHistory(Array.isArray(parsed) ? parsed : []);
        } catch (err) {
            setHistory([]);
        }
    };

    useEffect(() => {
        loadHistory();
    }, [historyKey]);

    const numeric = (value, fallback = 0) => {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    };

    const bmiCategory = useMemo(() => {
        const bmi = numeric(formData.bmi);
        if (bmi >= 30) return 'Obese';
        if (bmi >= 25) return 'Overweight';
        if (bmi >= 18.5) return 'Normal';
        return 'Underweight';
    }, [formData.bmi]);

    const bpCategory = useMemo(() => {
        const bp = numeric(formData.blood_pressure);
        if (bp >= 140) return 'High';
        if (bp >= 120) return 'Elevated';
        return 'Normal';
    }, [formData.blood_pressure]);

    const riskDrivers = useMemo(() => {
        const drivers = [];
        if (numeric(formData.age) >= 60) drivers.push('Age 60+');
        if (numeric(formData.bmi) >= 30) drivers.push('BMI over 30');
        if (numeric(formData.blood_pressure) >= 140) drivers.push('High blood pressure');
        if (numeric(formData.heart_rate) >= 100) drivers.push('High resting heart rate');
        if (formData.has_condition === '1') drivers.push('Existing condition');
        if (['Sedentary', 'Unhealthy'].includes(formData.lifestyle_factor)) drivers.push('Lifestyle risk');
        return drivers;
    }, [formData]);

    const guidance = useMemo(() => {
        const tips = ['Stay hydrated and follow medical advice.'];
        if (bmiCategory === 'Overweight' || bmiCategory === 'Obese') tips.push('Aim for gentle daily movement and balanced meals.');
        if (bpCategory === 'High') tips.push('Reduce sodium and monitor blood pressure twice a week.');
        if (formData.lifestyle_factor === 'Sedentary') tips.push('Add two short walks to your day.');
        if (formData.has_condition === '1') tips.push('Keep medications and care plan accessible.');
        return tips;
    }, [bmiCategory, bpCategory, formData.lifestyle_factor, formData.has_condition]);

    const riskScore = useMemo(() => {
        if (!result) return null;
        const score = numeric(result.risk_score || result.riskScore, null);
        if (score !== null) return Math.round(score);
        return result.risk_level === 'High' ? 78 : 32;
    }, [result]);

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/v2/ml/health-risk', {
                method: 'POST',
                body: JSON.stringify({
                    ...formData,
                    user_id: user?.id || null,
                    fast: true
                }),
                timeoutMs: 15000
            });
            if (!res.ok) {
                const fallback = await apiFetch('/api/predict_health_risk', {
                    method: 'POST',
                    body: JSON.stringify({
                        ...formData,
                        user_id: user?.id || null
                    })
                });
                if (!fallback.ok) {
                    throw new Error(fallback.data?.error || fallback.data?.detail || 'Prediction failed');
                }
                setResult(fallback.data || {});
                loadHistory();
                return;
            }
            setResult(res.data || {});
            loadHistory();
        } catch (err) {
            alert('Prediction Failed');
        } finally {
            setLoading(false);
        }
    };

    const handleAiInsight = async () => {
        if (!formData.symptoms && !result) return;
        setAiLoading(true);
        try {
            const query = `Provide a brief condition prediction and early warning advice for symptoms: ${formData.symptoms || 'none'}; vitals: age ${formData.age}, bmi ${formData.bmi}, bp ${formData.blood_pressure}, hr ${formData.heart_rate}.`;
            const res = await apiFetch('/v2/agents/ask', {
                method: 'POST',
                body: JSON.stringify({ query })
            });
            if (res.ok) {
                setAiInsight(res.data?.answer || 'No additional insights found.');
            } else {
                setAiInsight('AI insights unavailable right now.');
            }
        } catch (err) {
            setAiInsight('AI insights unavailable right now.');
        } finally {
            setAiLoading(false);
        }
    };

    const handleSaveAssessment = () => {
        if (!result) return;
        setSaveMessage('Assessment saved.');
        setTimeout(() => setSaveMessage(''), 1400);
        loadHistory();
    };

    return (
        <DashboardCard>
            <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Inputs will now maintain focus perfectly */}
                    <LabeledInput label="Age (Years)" name="age" type="number" placeholder="45" icon="fa-calendar" value={formData.age} onChange={handleChange} />
                    <LabeledInput label="BMI (Body Mass Index)" name="bmi" type="number" placeholder="28.5" icon="fa-weight" value={formData.bmi} onChange={handleChange} />
                    <LabeledInput label="Systolic BP (mmHg)" name="blood_pressure" type="number" placeholder="120" icon="fa-heartbeat" value={formData.blood_pressure} onChange={handleChange} />
                    <LabeledInput label="Heart Rate (BPM)" name="heart_rate" type="number" placeholder="75" icon="fa-heart" value={formData.heart_rate} onChange={handleChange} />
                    
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-1 ml-1">Existing Conditions</label>
                        <select name="has_condition" value={formData.has_condition} onChange={handleChange} className="w-full p-3 bg-gray-50 border rounded-lg focus:ring-2 focus:ring-sky-200 outline-none">
                            <option value="1">Yes (Diabetes, Hypertension, etc.)</option>
                            <option value="0">No / None</option>
                        </select>
                    </div>
                    
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-1 ml-1">Lifestyle / Activity</label>
                        <select name="lifestyle_factor" value={formData.lifestyle_factor} onChange={handleChange} className="w-full p-3 bg-gray-50 border rounded-lg focus:ring-2 focus:ring-sky-200 outline-none">
                            <option value="Sedentary">Sedentary (Low Activity)</option>
                            <option value="Average">Average</option>
                            <option value="Healthy">Active / Athletic</option>
                            <option value="Unhealthy">Unhealthy Habits</option>
                        </select>
                    </div>

                    <div className="md:col-span-2">
                        <label className="block text-sm font-semibold text-gray-700 mb-1 ml-1">Symptoms (Optional)</label>
                        <textarea
                            name="symptoms"
                            value={formData.symptoms}
                            onChange={handleChange}
                            rows={3}
                            className="w-full p-3 bg-gray-50 border rounded-lg focus:ring-2 focus:ring-sky-200 outline-none"
                            placeholder="e.g., chest pain, dizziness, shortness of breath"
                        />
                    </div>
                </div>
                <button type="submit" disabled={loading} className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 rounded-lg font-bold shadow-md hover:scale-[1.02] transition-transform">
                    {loading ? 'Analyzing Vitals...' : 'Calculate Health Risk'}
                </button>
            </form>

            {result && (
                <div className="mt-6 space-y-4 animate-fade-in">
                    <div className={`p-4 rounded-lg border-l-4 ${result.risk_level === 'High' ? 'border-red-500 bg-red-50' : 'border-green-500 bg-green-50'} shadow-sm`}>
                        <h4 className="font-bold text-gray-900">AI Analysis Result:</h4>
                        <p className={`text-2xl font-bold ${result.risk_level === 'High' ? 'text-red-600' : 'text-green-600'}`}>
                            {result.risk_level} Risk Level
                        </p>
                        <p className="text-sm text-gray-600 mt-1">Based on provided vitals, please consult a doctor for verification.</p>
                        {riskScore !== null && (
                            <div className="mt-3">
                                <p className="text-xs font-semibold text-gray-500">Risk score</p>
                                <ProgressBar value={Math.min(100, Math.max(0, riskScore))} colorClass={result.risk_level === 'High' ? 'bg-red-500' : 'bg-green-500'} />
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                        <div className="bg-slate-50 border rounded-lg p-3">
                            <p className="text-xs text-gray-500">BMI Category</p>
                            <p className="font-semibold text-gray-800">{bmiCategory}</p>
                        </div>
                        <div className="bg-slate-50 border rounded-lg p-3">
                            <p className="text-xs text-gray-500">Blood Pressure</p>
                            <p className="font-semibold text-gray-800">{bpCategory}</p>
                        </div>
                    </div>

                    <div className="bg-white/70 border rounded-lg p-3">
                        <p className="text-sm font-semibold text-gray-800 mb-2">Risk drivers</p>
                        {riskDrivers.length ? (
                            <div className="flex flex-wrap gap-2">
                                {riskDrivers.map((driver) => (
                                    <span key={driver} className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full">
                                        {driver}
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-gray-500">No high risk drivers detected.</p>
                        )}
                        {result?.drivers?.length ? (
                            <div className="flex flex-wrap gap-2 mt-2">
                                {result.drivers.map((driver) => (
                                    <span key={`ml-${driver}`} className="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full">
                                        {driver}
                                    </span>
                                ))}
                            </div>
                        ) : null}
                    </div>

                    <div className="bg-white/70 border rounded-lg p-3">
                        <p className="text-sm font-semibold text-gray-800 mb-2">Recommendations</p>
                        <ul className="text-xs text-gray-600 space-y-1">
                            {guidance.map((tip) => (
                                <li key={tip}>{tip}</li>
                            ))}
                        </ul>
                    </div>

                    <div className="bg-white/70 border rounded-lg p-3">
                        <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold text-gray-800">AI Condition Insights</p>
                            <button type="button" onClick={handleAiInsight} disabled={aiLoading} className="text-xs font-semibold text-indigo-600">
                                {aiLoading ? 'Analyzing…' : 'Generate'}
                            </button>
                        </div>
                        <p className="text-xs text-gray-600 mt-2">{aiInsight || 'Generate an AI suggestion based on symptoms and vitals.'}</p>
                    </div>

                    {result?.explanation && (
                        <div className="bg-white/70 border rounded-lg p-3">
                            <p className="text-sm font-semibold text-gray-800 mb-2">AI Explanation</p>
                            <p className="text-xs text-gray-600">{result.explanation}</p>
                        </div>
                    )}

                    <ExplainabilityPanel meta={result?.meta} />

                    <div className="flex items-center justify-between text-xs text-gray-500">
                        <button type="button" className="text-indigo-600 font-semibold" onClick={handleSaveAssessment}>Save assessment</button>
                        {saveMessage && <span>{saveMessage}</span>}
                    </div>
                </div>
            )}

            {history.length > 0 && (
                <div className="mt-6">
                    <h4 className="text-sm font-bold text-gray-800 mb-2">Recent Assessments</h4>
                    <div className="flex items-end gap-2 mb-3">
                        {history.slice(0, 6).map((entry) => (
                            <div key={entry.id} className="flex-1">
                                <div
                                    className="w-full bg-slate-200 rounded-sm"
                                    style={{ height: `${Math.min(100, Math.max(10, entry.risk_score || 0))}px` }}
                                ></div>
                            </div>
                        ))}
                    </div>
                    <div className="space-y-2 text-xs text-gray-600">
                        {history.map((entry) => (
                            <div key={entry.id} className="flex items-center justify-between bg-slate-50 border rounded-lg px-3 py-2">
                                <div>
                                    <p className="font-semibold text-gray-800">{entry.risk_level}</p>
                                    <p>{new Date(entry.date).toLocaleDateString()} • BMI {entry.bmi}</p>
                                </div>
                                <span className="text-gray-500">{entry.risk_score ?? 'N/A'}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </DashboardCard>
    );
};

export default HealthRiskCalculator;