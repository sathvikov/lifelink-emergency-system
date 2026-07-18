import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from '../config/api';
import { DashboardCard, LoadingSpinner, ProgressBar } from './Common';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { useDataMode } from '../context/DataModeContext';

const AIExpansionPanel = ({ role, moduleKey, subRole, title, description, entityId, autoRefresh = true }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const previousSummaryRef = useRef({});
    const [previousSummary, setPreviousSummary] = useState({});
    const roleKey = role || 'public';
    const isPublic = roleKey === 'public';
    const normalizedModule = (moduleKey || 'overview').toLowerCase();
    const { mode } = useDataMode();

    const moduleMatches = (segments) => segments.some((segment) => normalizedModule.includes(segment));
    const toNumber = (value) => {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    };
    const summaryItem = (label, value, source) => ({
        label,
        value: toNumber(value),
        ...(source ? { source } : {}),
    });
    const summaryHasValues = (summary) => Array.isArray(summary) && summary.some((item) => toNumber(item.value) > 0);

    const buildSignalGraph = (summary) => {
        const signals = Array.isArray(summary) ? summary.slice(0, 6) : [];
        if (!signals.length) return { nodes: [], edges: [] };

        const nodes = [];
        const edges = [];
        const coreId = 'ai-core';

        nodes.push({
            id: coreId,
            position: { x: 0, y: 0 },
            data: { label: 'AI Core' },
            style: {
                background: '#0f172a',
                color: '#fff',
                borderRadius: 14,
                padding: 10,
                fontSize: 12,
                fontWeight: 700,
            },
        });

        const radius = 170;
        signals.forEach((item, index) => {
            const angle = (index / signals.length) * Math.PI * 2;
            const id = `signal-${index}`;
            const value = Number(item.value) || 0;
            nodes.push({
                id,
                position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
                data: { label: `${item.label}\n${value}` },
                style: {
                    background: '#f1f5f9',
                    color: '#0f172a',
                    borderRadius: 12,
                    padding: 8,
                    fontSize: 11,
                    fontWeight: 600,
                    border: '1px solid #cbd5f5',
                    textAlign: 'center',
                    whiteSpace: 'pre-line',
                },
            });
            edges.push({
                id: `edge-${id}`,
                source: coreId,
                target: id,
                animated: true,
                style: { stroke: '#38bdf8', strokeWidth: 2 },
            });
        });

        return { nodes, edges };
    };

    const buildSparkline = (value, previous) => {
        const start = Number.isFinite(previous) ? previous : value * 0.85;
        const diff = value - start;
        return Array.from({ length: 6 }).map((_, index) => start + (diff * (index / 5)));
    };

    const updatePreviousSummary = (summary) => {
        if (!Array.isArray(summary)) return;
        const next = {};
        summary.forEach((item) => {
            next[item.label] = toNumber(item.value);
        });
        previousSummaryRef.current = next;
    };

    const buildPublicSummary = async () => {
        if (!entityId) return null;

        const wantsDonor = moduleMatches(['donor']);
        const wantsRecords = moduleMatches(['medical-records', 'records']);

        const [dashboardRes, donorRes, recordsRes] = await Promise.all([
            apiFetch(`/api/dashboard/public/${entityId}/full`, { method: 'GET' }),
            wantsDonor ? apiFetch('/api/donors/forecast', { method: 'GET' }) : Promise.resolve(null),
            wantsRecords ? apiFetch(`/api/health/records/${entityId}`, { method: 'GET' }) : Promise.resolve(null),
        ]);

        const dashboard = dashboardRes?.ok ? (dashboardRes.data || {}) : {};
        const alerts = dashboard.alerts || [];
        const requests = dashboard.resourceRequests || [];
        const donations = dashboard.donationHistory || [];
        const messages = dashboard.hospitalMessages || [];
        const riskTimeline = dashboard.riskTimeline || [];
        const anomalies = dashboard.anomalies || [];
        const vitalsMetrics = dashboard.latestVitals?.metrics || {};
        const heartRate = vitalsMetrics.heart_rate || 0;
        const oxygen = vitalsMetrics.oxygen || 0;
        const recordsCount = recordsRes?.ok ? (recordsRes.data?.count || 0) : 0;

        const donorForecast = donorRes?.ok ? (donorRes.data || {}) : {};
        const supply = donorForecast.supply || 0;
        const demand = donorForecast.demand || 0;
        const demandIndex = donorForecast.demand_index || 0;
        const availabilityScore = donorForecast.availability_score || 0;

        if (moduleMatches(['donor'])) {
            return [
                summaryItem('Active donors', supply, 'Donor forecast'),
                summaryItem('Demand index', demandIndex || demand, 'Requests'),
                summaryItem('Availability score', availabilityScore, 'Forecast model'),
            ];
        }

        if (moduleMatches(['health-risk'])) {
            return [
                summaryItem('Risk checks', riskTimeline.length, 'Health risk history'),
                summaryItem('Vitals anomalies', anomalies.length, 'Vitals scan'),
                summaryItem('Heart rate', heartRate, 'Latest vitals'),
            ];
        }

        if (moduleMatches(['health-dashboard', 'health'])) {
            return [
                summaryItem('Vitals updates', riskTimeline.length || alerts.length, 'Health timeline'),
                summaryItem('Oxygen', oxygen, 'Latest vitals'),
                summaryItem('Alerts', alerts.length, 'SOS feed'),
            ];
        }

        if (moduleMatches(['medical-records', 'records'])) {
            return [
                summaryItem('Records logged', recordsCount, 'Health records'),
                summaryItem('Donations', donations.length, 'Donation history'),
                summaryItem('Messages', messages.length, 'Hospital messages'),
            ];
        }

        if (moduleMatches(['emergency', 'sos'])) {
            return [
                summaryItem('SOS alerts', alerts.length, 'Emergency feed'),
                summaryItem('Risk flags', anomalies.length, 'Vitals scan'),
                summaryItem('Open requests', requests.length, 'Resource requests'),
            ];
        }

        return [
            summaryItem('SOS alerts', alerts.length, 'Emergency feed'),
            summaryItem('Resource requests', requests.length, 'Requests'),
            summaryItem('Donations', donations.length, 'Donation history'),
        ];
    };

    const buildHospitalSummary = async () => {
        if (!entityId) return null;

        const [metricsRes, feedRes] = await Promise.all([
            apiFetch(`/api/hospital-ops/ceo/global-metrics?hospitalId=${entityId}`, { method: 'GET' }),
            apiFetch(`/api/hospital-ops/emergency/feed?hospitalId=${entityId}`, { method: 'GET' }),
        ]);

        const metrics = metricsRes?.ok ? (metricsRes.data || {}) : {};
        const feed = feedRes?.ok ? (feedRes.data?.data || []) : [];

        const patientsTotal = metrics.patients?.total || 0;
        const beds = metrics.beds || {};
        const staff = metrics.staff || {};
        const revenue = metrics.revenue || {};
        const emergencyActive = metrics.emergency?.active ?? feed.length;
        const emergencyCritical = metrics.emergency?.critical ?? feed.filter((item) => item.severity === 'Critical').length;
        const inbound = metrics.ambulance?.inbound || 0;
        const outbound = metrics.ambulance?.outbound || 0;
        const staffCoverage = metrics.kpiSignals?.staffCoverage || 0;

        if (moduleMatches(['bed', 'icu'])) {
            return [
                summaryItem('Occupied beds', beds.occupied || 0, 'Bed census'),
                summaryItem('Available beds', beds.available || 0, 'Bed census'),
                summaryItem('ICU occupied', beds.icu?.occupied || 0, 'ICU census'),
            ];
        }

        if (moduleMatches(['emergency', 'ambulance', 'live-emergency'])) {
            return [
                summaryItem('Active emergencies', emergencyActive, 'Emergency feed'),
                summaryItem('Critical cases', emergencyCritical, 'Severity signals'),
                summaryItem('Ambulance inbound', inbound, 'Ambulance ops'),
            ];
        }

        if (moduleMatches(['finance', 'billing', 'revenue', 'insurance'])) {
            return [
                summaryItem('Daily revenue', revenue.daily || 0, 'Billing ledger'),
                summaryItem('Weekly revenue', revenue.weekly || 0, 'Billing ledger'),
                summaryItem('Monthly revenue', revenue.monthly || 0, 'Billing ledger'),
            ];
        }

        if (moduleMatches(['staff'])) {
            return [
                summaryItem('Staff on duty', staff.available || 0, 'Roster'),
                summaryItem('Total staff', staff.total || 0, 'Roster'),
                summaryItem('Coverage %', staffCoverage, 'KPI signal'),
            ];
        }

        return [
            summaryItem('Patients today', patientsTotal, 'Admissions'),
            summaryItem('Available beds', beds.available || 0, 'Bed census'),
            summaryItem('Active emergencies', emergencyActive, 'Emergency feed'),
        ];
    };

    const buildAmbulanceSummary = async () => {
        const wantsHistory = moduleMatches(['history']);
        const [assignmentsRes, emergencyRes, historyRes] = await Promise.all([
            apiFetch('/api/ambulance/assignments', { method: 'GET' }),
            apiFetch('/api/ambulance/emergency-status', { method: 'GET' }),
            wantsHistory ? apiFetch('/api/ambulance/history', { method: 'GET' }) : Promise.resolve(null),
        ]);

        const assignmentsCount = assignmentsRes?.ok ? (assignmentsRes.data?.count || 0) : 0;
        const emergencyCount = emergencyRes?.ok ? (emergencyRes.data?.count || 0) : 0;
        const severity = emergencyRes?.ok ? (emergencyRes.data?.severityCounts || {}) : {};
        const critical = severity.Critical || 0;
        const high = severity.High || 0;
        const historyCount = historyRes?.ok ? (historyRes.data?.count || 0) : 0;

        if (moduleMatches(['emergency'])) {
            return [
                summaryItem('Open alerts', emergencyCount, 'Emergency feed'),
                summaryItem('Critical', critical, 'Severity count'),
                summaryItem('High priority', high, 'Severity count'),
            ];
        }

        if (moduleMatches(['history'])) {
            return [
                summaryItem('Completed trips', historyCount, 'Dispatch history'),
                summaryItem('Active assignments', assignmentsCount, 'Assignments'),
                summaryItem('Open alerts', emergencyCount, 'Emergency feed'),
            ];
        }

        return [
            summaryItem('Active assignments', assignmentsCount, 'Assignments'),
            summaryItem('Open alerts', emergencyCount, 'Emergency feed'),
            summaryItem('Critical cases', critical, 'Severity count'),
        ];
    };

    const buildGovernmentSummary = async () => {
        const wantsCompliance = moduleMatches(['compliance', 'audit', 'policy', 'verification']);
        const wantsEmergencies = moduleMatches(['emergency', 'monitor', 'command', 'disaster']);
        const wantsSimulation = moduleMatches(['simulation', 'recovery']);
        const wantsAI = moduleMatches(['ai', 'ml']);
        const useDefault = !wantsCompliance && !wantsEmergencies && !wantsSimulation && !wantsAI;

        const [overviewRes, feedRes, decisionRes, anomalyRes, pendingRes] = await Promise.all([
            apiFetch('/v2/government/command/overview', { method: 'GET' }),
            apiFetch('/v2/government/monitoring/feed', { method: 'GET' }),
            apiFetch('/v2/government/decision/engine', { method: 'POST' }),
            apiFetch('/v2/government/predictions/anomaly', { method: 'GET' }),
            apiFetch('/v2/government/verification/pending', { method: 'GET' }),
        ]);

        const overview = overviewRes?.ok ? overviewRes.data : { hospitals: 0, ambulances: 0, emergencies: 0 };
        const feed = feedRes?.ok ? (feedRes.data?.data || []) : [];
        const decisions = decisionRes?.ok ? (decisionRes.data?.decisions || []) : [];
        const anomaly = anomalyRes?.ok ? anomalyRes.data?.prediction : null;
        const pending = pendingRes?.ok ? (pendingRes.data?.data || []).length : 0;

        const criticalAlerts = feed.filter((alert) => String(alert.severity || '').toLowerCase() === 'critical').length;
        const anomalyCount = anomaly?.anomaly_hours?.length || 0;

        if (wantsCompliance) {
            return [
                summaryItem('Policy actions', decisions.length, 'Decision queue'),
                summaryItem('Pending verifications', pending, 'Compliance review'),
                summaryItem('Anomaly spikes', anomalyCount, 'Risk monitoring'),
            ];
        }

        if (wantsAI) {
            return [
                summaryItem('Policy actions', decisions.length, 'Decision queue'),
                summaryItem('Anomaly spikes', anomalyCount, 'Risk monitoring'),
                summaryItem('Emergencies active', overview.emergencies || 0, 'Live incidents'),
            ];
        }

        if (wantsSimulation) {
            return [
                summaryItem('Simulation phases', decisions.length, 'Decision playbooks'),
                summaryItem('Emergencies active', overview.emergencies || 0, 'Live incidents'),
                summaryItem('Critical alerts', criticalAlerts, 'Severity signals'),
            ];
        }

        if (wantsEmergencies || useDefault) {
            return [
                summaryItem('Emergencies active', overview.emergencies || 0, 'Emergency feed'),
                summaryItem('Hospitals tracked', overview.hospitals || 0, 'Hospital registry'),
                summaryItem('Ambulances active', overview.ambulances || 0, 'Fleet registry'),
            ];
        }

        return [
            summaryItem('Emergencies active', overview.emergencies || 0, 'Emergency feed'),
            summaryItem('Policy actions', decisions.length, 'Decision queue'),
            summaryItem('Anomaly spikes', anomalyCount, 'Risk monitoring'),
        ];
    };

    const buildFallbackSummary = async () => {
        switch (roleKey) {
            case 'public':
                return buildPublicSummary();
            case 'hospital':
                return buildHospitalSummary();
            case 'ambulance':
                return buildAmbulanceSummary();
            case 'government':
                return buildGovernmentSummary();
            default:
                return null;
        }
    };

    useEffect(() => {
        if (data || !moduleKey) return;
        try {
            const cacheKey = `gov_ai_insights_${mode || 'real'}_${roleKey}_${subRole || 'default'}_${moduleKey}`;
            const cached = sessionStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                if (parsed && parsed.data_summary) {
                    setData(parsed);
                    setLoading(false);
                }
            }
        } catch (error) {
            return;
        }
    }, [data, moduleKey, roleKey, subRole, mode]);

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            setLoading(true);
            setError('');
            try {
                const params = new URLSearchParams({
                    role: role || 'public',
                    module_key: moduleKey || 'overview',
                });
                if (subRole) {
                    params.set('sub_role', subRole);
                }
                const res = await apiFetch(`/v2/ai/insights?${params.toString()}`, {
                    method: 'GET',
                    ttlMs: 20000,
                    staleWhileRevalidate: true,
                });
                const aiData = res.ok ? res.data : null;
                const needsFallback = !summaryHasValues(aiData?.data_summary);
                const fallbackSummary = needsFallback ? await buildFallbackSummary() : null;

                if (isActive) {
                    if (fallbackSummary?.length) {
                        const merged = {
                            ...(aiData || {}),
                            data_summary: fallbackSummary,
                            timestamp: aiData?.timestamp || new Date().toISOString(),
                        };
                        setData(merged);
                        setError('');
                        if (roleKey === 'government') {
                            const cacheKey = `gov_ai_insights_${mode || 'real'}_${roleKey}_${subRole || 'default'}_${moduleKey}`;
                            sessionStorage.setItem(cacheKey, JSON.stringify(merged));
                        }
                    } else if (aiData) {
                        setData(aiData);
                        setError('');
                        if (roleKey === 'government') {
                            const cacheKey = `gov_ai_insights_${mode || 'real'}_${roleKey}_${subRole || 'default'}_${moduleKey}`;
                            sessionStorage.setItem(cacheKey, JSON.stringify(aiData));
                        }
                    } else {
                        setError(res.data?.detail || 'AI insights unavailable');
                    }
                }
            } catch (err) {
                if (isActive) {
                    const fallbackSummary = await buildFallbackSummary();
                    if (fallbackSummary?.length) {
                        const fallbackData = {
                            data_summary: fallbackSummary,
                            timestamp: new Date().toISOString(),
                            cards: [],
                        };
                        setData(fallbackData);
                        setError('');
                        if (roleKey === 'government') {
                            const cacheKey = `gov_ai_insights_${mode || 'real'}_${roleKey}_${subRole || 'default'}_${moduleKey}`;
                            sessionStorage.setItem(cacheKey, JSON.stringify(fallbackData));
                        }
                    } else {
                        setError('AI insights unavailable');
                    }
                }
            } finally {
                if (isActive) setLoading(false);
            }
        };
        load();
        if (!autoRefresh) {
            return () => {
                isActive = false;
            };
        }
        const refreshMs = isPublic ? 25000 : 40000;
        const interval = setInterval(() => {
            load();
        }, refreshMs);
        return () => {
            isActive = false;
            clearInterval(interval);
        };
    }, [role, moduleKey, subRole, entityId, autoRefresh, mode]);

    useEffect(() => {
        if (!data?.data_summary?.length) return;
        setPreviousSummary(previousSummaryRef.current || {});
        updatePreviousSummary(data.data_summary);
    }, [data?.data_summary]);

    const signalGraph = useMemo(() => buildSignalGraph(data?.data_summary), [data?.data_summary]);

    return (
        <DashboardCard>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="font-bold text-lg text-gray-900">{title || 'AI Expansion'}</h3>
                    <p className="text-sm text-gray-500">{description || 'Futuristic AI capabilities aligned to this module.'}</p>
                </div>
                <span className="text-xs text-gray-400">{data?.timestamp ? new Date(data.timestamp).toLocaleString() : ''}</span>
            </div>
            {data?.data_summary?.length ? (
                <div className="mb-4">
                    <div className="flex items-center justify-between mb-3">
                        <p className="text-xs text-gray-500">Live signals</p>
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            Live refresh
                        </div>
                    </div>
                    {(() => {
                        const maxValue = data.data_summary.reduce((max, item) => {
                            const value = Number(item.value) || 0;
                            return value > max ? value : max;
                        }, 0);
                        const previous = previousSummary || {};
                        return (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                {data.data_summary.map((item, index) => {
                                    const value = Number(item.value) || 0;
                                    const prevValue = previous[item.label];
                                    const delta = Number.isFinite(prevValue) ? value - prevValue : 0;
                                    const percent = maxValue ? Math.round((value / maxValue) * 100) : 0;
                                    const sparkline = buildSparkline(value, prevValue);
                                    const sparkMax = Math.max(...sparkline, 1);
                                    return (
                                        <div key={`${item.label}-${index}`} className="bg-white border border-slate-200 rounded-lg p-3">
                                            <div className="flex items-center justify-between">
                                                <p className="text-xs text-gray-500">{item.label}</p>
                                                <span className={`text-[10px] ${delta >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                    {delta >= 0 ? '+' : ''}{delta}
                                                </span>
                                            </div>
                                            <p className="text-2xl font-bold text-gray-900">{value}</p>
                                            <div className="flex items-end gap-1 h-8 mt-2">
                                                {sparkline.map((point, idx) => (
                                                    <span
                                                        key={`${item.label}-spark-${idx}`}
                                                        className="w-1 rounded-sm bg-sky-500/70"
                                                        style={{ height: `${Math.max(10, Math.round((point / sparkMax) * 100))}%` }}
                                                    ></span>
                                                ))}
                                            </div>
                                            <div className="mt-2">
                                                <ProgressBar value={percent} colorClass="bg-sky-500" />
                                            </div>
                                            {item.source && <p className="text-[10px] text-gray-400 mt-1">{item.source}</p>}
                                        </div>
                                    );
                                })}
                            </div>
                        );
                    })()}
                </div>
            ) : null}
            {data?.data_summary?.length ? (
                <div className="mb-4">
                    <p className="text-xs text-gray-500 mb-2">Signal graph</p>
                    <div className="h-[220px] border rounded-lg bg-white">
                        {signalGraph.nodes.length ? (
                            <ReactFlow
                                nodes={signalGraph.nodes}
                                edges={signalGraph.edges}
                                fitView
                                nodesDraggable={false}
                                nodesConnectable={false}
                                zoomOnScroll={false}
                            >
                                <Background color="#e2e8f0" gap={16} />
                                <Controls showInteractive={false} />
                            </ReactFlow>
                        ) : (
                            <div className="h-full flex items-center justify-center text-sm text-gray-400">
                                Signals will appear as the AI feed updates.
                            </div>
                        )}
                    </div>
                </div>
            ) : null}
            {data?.narrative ? (
                <div className="mb-4 border border-slate-200 rounded-lg bg-white/70 p-3 min-w-0 max-w-full overflow-hidden break-words">
                    <p className="text-xs text-gray-500">AI summary</p>
                    <h4 className="font-semibold text-gray-900 mt-1 break-words">{data.narrative.headline}</h4>
                    <p className="text-sm text-gray-700 mt-2 break-words whitespace-normal leading-relaxed">{data.narrative.summary}</p>
                    {Array.isArray(data.narrative.next_steps) && data.narrative.next_steps.length > 0 ? (
                        <div className="flex flex-wrap gap-2 mt-3">
                            {data.narrative.next_steps.map((step, index) => (
                                <span key={`${step}-${index}`} className="text-[11px] bg-emerald-50 text-emerald-700 px-2 py-1 rounded-full break-words whitespace-normal max-w-full">
                                    {step}
                                </span>
                            ))}
                        </div>
                    ) : null}
                </div>
            ) : null}
            {loading ? (
                <LoadingSpinner />
            ) : error ? (
                <div className="text-sm text-gray-500">{error}</div>
            ) : data?.cards?.length ? (
                <div>
                    <p className="text-xs text-gray-500 mb-2">AI playbook</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {data.cards.map((card, index) => (
                            <div key={`${card.title}-${index}`} className="border rounded-lg p-3 bg-white/70 min-w-0 max-w-full overflow-hidden break-words">
                                <div className="flex items-start justify-between gap-3">
                                    <h4 className="font-semibold text-gray-800 text-sm leading-snug break-words">{card.title}</h4>
                                    <span className="text-[10px] text-gray-400 whitespace-nowrap">{Math.round((card.confidence || 0.7) * 100)}%</span>
                                </div>
                                <p className="text-xs text-gray-600 mt-1 break-words whitespace-normal leading-relaxed">{card.summary}</p>
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {(card.outputs || []).slice(0, 3).map((item) => (
                                        <span key={item} className="text-[11px] bg-blue-50 text-blue-700 px-2 py-1 rounded-full break-words whitespace-normal max-w-full">
                                            {item}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : data?.data_summary?.length ? (
                <div className="text-sm text-gray-500">More AI expansion cards will appear as additional signals are added.</div>
            ) : (
                <div className="text-sm text-gray-500">No AI expansions defined for this module yet.</div>
            )}
        </DashboardCard>
    );
};

export default AIExpansionPanel;
