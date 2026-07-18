// Production: set VITE_API_URL in Vercel to your Render backend URL (e.g. https://your-app.onrender.com)
// Development: falls back to localhost:3010 if not set
const raw = import.meta.env.VITE_API_URL;
const devFallback = 'http://localhost:3010';
const DATA_MODE_KEY = 'lifelink_data_mode';
export const API_BASE_URL =
  typeof raw === 'string' && raw.trim() !== ''
    ? raw.replace(/\/+$/, '') // strip trailing slashes
    : import.meta.env.DEV
      ? devFallback
      : '';

export const getDataMode = () => {
  if (typeof window === 'undefined') return 'real';
  return localStorage.getItem(DATA_MODE_KEY) || 'real';
};

export const isDemoMode = () => getDataMode() === 'demo';

export const getAuthToken = () => (
  sessionStorage.getItem('lifelink_token') || localStorage.getItem('lifelink_token')
);

const responseCache = new Map();
const inflightRequests = new Map();
const DEFAULT_TTL_MS = 120000;
const DEFAULT_TIMEOUT_MS = 12000;

const demoRandom = (min, max) => Math.round(min + Math.random() * (max - min));
const demoFloat = (min, max, decimals = 2) => {
  const value = min + Math.random() * (max - min);
  return Number(value.toFixed(decimals));
};

const demoMonthlySeries = (base = 8200000, step = 520000) => {
  const now = new Date();
  return Array.from({ length: 6 }).map((_, idx) => {
    const date = new Date(now.getFullYear(), now.getMonth() - (5 - idx), 1);
    const label = date.toLocaleString('en-US', { month: 'short' });
    return {
      label,
      value: base + idx * step,
      monthKey: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
    };
  });
};

const demoDailySeries = (base = 1200000, step = 90000) => {
  const now = new Date();
  return Array.from({ length: 7 }).map((_, idx) => {
    const date = new Date(now.getTime() - (6 - idx) * 86400000);
    return {
      label: date.toLocaleString('en-US', { weekday: 'short' }),
      value: base + idx * step,
      dayKey: date.toISOString().slice(0, 10)
    };
  });
};

const demoHospitals = (count = 24) => Array.from({ length: count }).map((_, idx) => {
  const bedsTotal = demoRandom(220, 420);
  const bedsAvailable = demoRandom(30, Math.max(40, Math.floor(bedsTotal * 0.35)));
  return {
    id: `demo-hosp-${idx + 1}`,
    name: `Demo Medical Center ${idx + 1}`,
    city: 'Bengaluru',
    state: 'Karnataka',
    lat: demoFloat(12.85, 13.05, 4),
    lng: demoFloat(77.45, 77.75, 4),
    beds_total: bedsTotal,
    beds_available: bedsAvailable,
    load_score: Number((1 - bedsAvailable / bedsTotal).toFixed(2)),
    verified: idx % 3 !== 0,
  };
});

const demoAmbulances = (count = 36) => Array.from({ length: count }).map((_, idx) => ({
  id: `demo-amb-${idx + 1}`,
  code: `AMB-${100 + idx}`,
  lat: demoFloat(12.86, 13.02, 4),
  lng: demoFloat(77.49, 77.72, 4),
  status: ['available', 'assigned', 'offline'][idx % 3],
  verified: idx % 4 !== 0,
}));

const demoAmbulanceAssignments = () => ([
  {
    id: 'demo-assignment-1',
    ambulanceId: 'AMB-101',
    ambulanceUserId: 'demo-ambulance-user',
    patient: 'Riya S',
    emergencyType: 'Cardiac arrest',
    status: 'Active',
    etaMinutes: 11,
    pickup: 'Majestic, Bengaluru',
    destination: "St. Martha's Hospital",
    pickupLocation: { latitude: 12.9716, longitude: 77.5946, address: 'Majestic, Bengaluru' },
    destinationLocation: { latitude: 12.9686, longitude: 77.5995, address: "St. Martha's Hospital" },
    patientVitals: { heartRate: 122, oxygen: 88, bp: '92/58' },
  },
  {
    id: 'demo-assignment-2',
    ambulanceId: 'AMB-102',
    ambulanceUserId: 'demo-ambulance-user',
    patient: 'Arun K',
    emergencyType: 'Road accident',
    status: 'En Route',
    etaMinutes: 14,
    pickup: 'Shivajinagar, Bengaluru',
    destination: 'Bowring Hospital',
    pickupLocation: { latitude: 12.985, longitude: 77.605, address: 'Shivajinagar, Bengaluru' },
    destinationLocation: { latitude: 12.9785, longitude: 77.5971, address: 'Bowring Hospital' },
    patientVitals: { heartRate: 108, oxygen: 92, bp: '104/66' },
  },
]);

const demoAmbulancePatientInfo = () => demoAmbulanceAssignments().map((item) => ({
  id: item.id,
  patient: item.patient,
  emergencyType: item.emergencyType,
  status: item.status,
  patientVitals: item.patientVitals,
}));

const demoAmbulanceHistory = () => ([
  {
    id: 'demo-history-1',
    patient: 'Meera T',
    emergencyType: 'Trauma',
    status: 'Completed',
    destination: 'Victoria Hospital',
    updatedAt: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'demo-history-2',
    patient: 'Vikram P',
    emergencyType: 'Respiratory distress',
    status: 'Completed',
    destination: 'Bowring Hospital',
    updatedAt: new Date(Date.now() - 5400000).toISOString(),
  },
]);

const demoAmbulanceEmergencyStatus = () => ({
  count: 4,
  severityCounts: { Critical: 2, High: 1, Medium: 1, Low: 0 },
  alerts: [
    {
      id: 'demo-alert-1',
      message: 'Multi-vehicle collision reported',
      emergencyType: 'Critical',
      locationDetails: 'Majestic, Bengaluru',
      location: { lat: 12.9716, lng: 77.5946 },
    },
    {
      id: 'demo-alert-2',
      message: 'Severe asthma attack',
      emergencyType: 'High',
      locationDetails: 'Cubbon Park, Bengaluru',
      location: { lat: 12.9763, lng: 77.5929 },
    },
  ],
});

const demoAmbulanceFleet = () => ([
  {
    ambulanceId: 'AMB-101',
    status: 'en_route',
    currentLocation: { latitude: 12.9716, longitude: 77.5946, address: 'Majestic, Bengaluru' },
    activeRoute: {
      destinationLocation: { latitude: 12.9686, longitude: 77.5995, address: "St. Martha's Hospital" },
    },
  },
  {
    ambulanceId: 'AMB-102',
    status: 'available',
    currentLocation: { latitude: 12.985, longitude: 77.605, address: 'Shivajinagar, Bengaluru' },
  },
  {
    ambulanceId: 'AMB-103',
    status: 'at_location',
    currentLocation: { latitude: 12.9812, longitude: 77.5718, address: 'Malleshwaram, Bengaluru' },
  },
]);

const demoDistanceKm = (lat1, lng1, lat2, lng2) => {
  if (![lat1, lng1, lat2, lng2].every((value) => Number.isFinite(value))) return 5;
  const toRad = (value) => (value * Math.PI) / 180;
  const r = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return r * c;
};

const demoRoute = (startLat, startLng, endLat, endLng, includeGeometry) => {
  const distanceKm = demoDistanceKm(startLat, startLng, endLat, endLng);
  const durationSeconds = Math.max(300, Math.round((distanceKm / 35) * 3600));
  const geometry = includeGeometry ? {
    type: 'LineString',
    coordinates: Array.from({ length: 8 }).map((_, idx) => {
      const t = idx / 7;
      const lat = startLat + (endLat - startLat) * t;
      const lng = startLng + (endLng - startLng) * t;
      return [lng, lat];
    }),
  } : undefined;
  return {
    status: 'ok',
    distance_meters: Math.round(distanceKm * 1000),
    duration_seconds: durationSeconds,
    ...(geometry ? { geometry } : {}),
  };
};

const demoTraffic = (startLat, startLng, endLat, endLng) => {
  const distanceKm = demoDistanceKm(startLat, startLng, endLat, endLng);
  const baseDuration = Math.max(300, Math.round((distanceKm / 40) * 3600));
  const trafficFactor = demoFloat(1.05, 1.35, 2);
  const adjustedDuration = Math.round(baseDuration * trafficFactor);
  const precipitation = demoFloat(0, 1.2, 1);
  const wind = demoRandom(8, 32);
  return {
    status: 'ok',
    provider: 'simulation',
    base_duration_seconds: baseDuration,
    adjusted_duration_seconds: adjustedDuration,
    factors: { time: demoFloat(1.0, 1.3, 2), weather: demoFloat(1.0, 1.2, 2) },
    weather: {
      status: 'ok',
      temperature_c: demoRandom(24, 32),
      precipitation_mm: precipitation,
      wind_kph: wind,
      is_raining: precipitation > 0.4,
    },
  };
};

const parseCoordsFromText = (value) => {
  if (!value || typeof value !== 'string') return null;
  const parts = value.split(',').map((item) => Number(item.trim()));
  if (parts.length !== 2) return null;
  if (!Number.isFinite(parts[0]) || !Number.isFinite(parts[1])) return null;
  return { lat: parts[0], lng: parts[1] };
};

const demoIncidents = (count = 10) => Array.from({ length: count }).map((_, idx) => ({
  id: `demo-inc-${idx + 1}`,
  type: ['Cardiac', 'Accident', 'Fire', 'Trauma'][idx % 4],
  severity: ['Critical', 'High', 'Medium', 'Low'][idx % 4],
  lat: demoFloat(12.86, 13.02, 4),
  lng: demoFloat(77.49, 77.72, 4),
  occurred_at: new Date(Date.now() - idx * 1000 * 60 * 7).toISOString(),
}));

const demoGovernmentInsights = () => ({
  data_summary: [
    { label: 'Emergencies active', value: demoRandom(36, 78), source: 'Incident feed' },
    { label: 'Hospitals tracked', value: demoRandom(220, 360), source: 'Hospital registry' },
    { label: 'Ambulances active', value: demoRandom(420, 680), source: 'Fleet registry' },
  ],
  cards: [
    {
      title: 'Rapid response activation',
      summary: 'Deploy surge teams to Central and South zones based on severity spikes.',
      confidence: 0.86,
      outputs: ['Activate surge roster', 'Increase ICU buffer', 'Notify dispatch'],
    },
    {
      title: 'Resource diversion plan',
      summary: 'Route non-critical cases to partner hospitals with low load.',
      confidence: 0.81,
      outputs: ['Divert 12 cases', 'Open 14 beds', 'Alert logistics'],
    },
  ],
  timestamp: new Date().toISOString(),
});

const demoHospitalMetrics = () => ({
  patients: {
    total: demoRandom(260, 420),
    by_department: {
      Emergency: demoRandom(60, 120),
      ICU: demoRandom(24, 48),
      General: demoRandom(110, 170),
      Pediatrics: demoRandom(20, 50),
    },
  },
  beds: {
    total: 340,
    occupied: demoRandom(220, 300),
    available: demoRandom(40, 100),
    icu: { occupied: demoRandom(24, 40) },
    emergency: { occupied: demoRandom(40, 70) },
    general: { occupied: demoRandom(140, 200) },
  },
  staff: { total: 260, available: demoRandom(180, 230) },
  revenue: { daily: demoRandom(1200000, 2400000), weekly: demoRandom(8400000, 14000000) },
  emergency: { active: demoRandom(24, 40), critical: demoRandom(10, 18) },
  ambulance: { inbound: demoRandom(12, 22), outbound: demoRandom(10, 20) },
  kpiSignals: {
    occupancyRate: demoRandom(72, 92),
    staffCoverage: demoRandom(78, 94),
    revenueTrend: 'Upward',
    emergencyLoad: demoRandom(22, 46),
  },
  benchmarks: {
    region: 'South Zone',
    internal: { avgOccupancyRate: demoRandom(70, 85) },
    external: { readmissionRate: demoRandom(4, 8) + '%', avgLos: demoRandom(3, 6) + 'd' },
  },
  ai: {
    anomalies: ['ICU load above baseline', 'ER wait time trending up'],
  },
});

const demoHospitalInsights = () => ({
  predicted_inflow: demoRandom(24, 48),
  emergency_spike_risk: ['Low', 'Medium', 'High'][demoRandom(0, 2)],
  overloaded_departments: ['Emergency', 'Radiology'],
  staff_redistribution: 'Shift 6 nurses to ER for evening spike',
  bed_allocation_strategy: 'Reserve 12 ICU beds for incoming trauma cases',
  cost_pressure_index: demoRandom(52, 78),
  margin_at_risk: demoRandom(120000, 220000),
  cost_optimization: 'Reduce overtime in elective units by 6%',
  top_cost_drivers: [
    { category: 'Pharmacy', amount: demoRandom(42000, 68000) },
    { category: 'Diagnostics', amount: demoRandom(22000, 44000) },
  ],
  insight_notes: ['Prep ICU surge roster for late-night peak', 'Accelerate discharge planning in Ward B'],
  meta: {
    confidence: 0.83,
    reasoning: ['Historical inflow pattern', 'Current bed occupancy'],
    references: [{ title: 'Operations log', detail: 'Last 7-day inflow trend' }],
  },
});

const demoHospitalOpsData = (() => {
  const departments = ['Emergency', 'ICU', 'General', 'Cardiology', 'Orthopedics', 'Neurology', 'Pediatrics', 'Radiology', 'Surgery', 'Oncology'];
  const roles = ['Doctor', 'Nurse', 'Technician', 'Support', 'Consultant'];
  const shifts = ['Day', 'Evening', 'Night'];
  const now = Date.now();
  const pastIso = (hours) => new Date(now - hours * 3600000).toISOString();
  const futureIso = (hours) => new Date(now + hours * 3600000).toISOString();

  const staff = Array.from({ length: 240 }).map((_, idx) => ({
    _id: `demo-staff-${idx + 1}`,
    name: `Staff ${idx + 1}`,
    department: departments[idx % departments.length],
    role: roles[idx % roles.length],
    availability: idx % 5 !== 0,
    createdAt: pastIso(idx % 720),
  }));

  const invoices = Array.from({ length: 360 }).map((_, idx) => ({
    _id: `demo-inv-${idx + 1}`,
    patientName: `Patient ${idx + 1}`,
    department: departments[idx % departments.length],
    amount: 15000 + (idx % 18) * 2400,
    status: idx % 3 === 0 ? 'Paid' : 'Unpaid',
    createdAt: pastIso(idx % 900),
    paidAt: idx % 3 === 0 ? pastIso(idx % 240) : null,
  }));

  const claims = Array.from({ length: 240 }).map((_, idx) => ({
    _id: `demo-claim-${idx + 1}`,
    invoiceId: invoices[idx % invoices.length]._id,
    insurer: idx % 2 === 0 ? 'Star Health' : 'Care Plus',
    amount: 28000 + (idx % 10) * 2800,
    status: idx % 4 === 0 ? 'Approved' : 'Submitted',
    createdAt: pastIso(idx % 1000),
  }));

  const bedTypes = ['ICU', 'Emergency', 'General', 'Ward'];
  const bedAllocations = Array.from({ length: 160 }).map((_, idx) => ({
    _id: `demo-alloc-${idx + 1}`,
    patientName: `Patient ${idx + 1}`,
    bedType: bedTypes[idx % bedTypes.length],
    status: idx % 6 === 0 ? 'Waiting' : 'Assigned',
    notes: 'Auto allocation',
    createdAt: pastIso(idx % 200),
  }));

  const reportTemplates = [
    { reportKey: 'weekly-ops', name: 'Weekly Operations Summary' },
    { reportKey: 'icu-performance', name: 'ICU Performance Review' },
    { reportKey: 'finance-snapshot', name: 'Finance Snapshot' },
  ];
  const reports = reportTemplates.map((template, idx) => ({
    id: `demo-report-${idx + 1}`,
    reportKey: template.reportKey,
    name: template.name,
    status: 'Ready',
    generatedAt: pastIso((idx + 1) * 24),
  }));
  const ingestedReports = ['Vendor Audit Notes', 'Patient Feedback Digest', 'Safety Drill Summary', 'Clinical Quality Review', 'Supply Chain Risk', 'Ambulance KPI Snapshot']
    .map((name, idx) => ({
      _id: `demo-ingest-${idx + 1}`,
      name,
      category: idx % 2 === 0 ? 'Quality' : 'Compliance',
      summary: `${name} summary`,
      generatedAt: pastIso((idx + 1) * 12),
    }));

  const resourceCatalog = [
    { name: 'IV Kits', category: 'Supplies', unit: 'kits', base: 320 },
    { name: 'Dialysis Filters', category: 'Equipment', unit: 'filters', base: 80 },
    { name: 'Ventilator Circuits', category: 'Consumables', unit: 'sets', base: 140 },
    { name: 'Oxygen Masks', category: 'Consumables', unit: 'units', base: 260 },
    { name: 'Surgical Gloves', category: 'Supplies', unit: 'boxes', base: 480 },
    { name: 'Glucose Monitors', category: 'Supplies', unit: 'units', base: 220 },
  ];
  const resources = Array.from({ length: 42 }).map((_, idx) => {
    const ref = resourceCatalog[idx % resourceCatalog.length];
    const quantity = ref.base + (idx % 6) * 25;
    return {
      _id: `demo-res-${idx + 1}`,
      name: `${ref.name} ${idx + 1}`,
      category: ref.category,
      quantity,
      minThreshold: Math.max(12, Math.round(quantity * 0.2)),
      unit: ref.unit,
    };
  });

  const equipmentCatalog = [
    { name: 'MRI Scanner', category: 'Imaging', base: 4 },
    { name: 'CT Scanner', category: 'Imaging', base: 3 },
    { name: 'Ventilators', category: 'ICU', base: 48 },
    { name: 'ECG Machines', category: 'Cardiology', base: 18 },
    { name: 'Ultrasound', category: 'Imaging', base: 12 },
    { name: 'Infusion Pumps', category: 'ICU', base: 36 },
  ];
  const equipment = Array.from({ length: 28 }).map((_, idx) => {
    const ref = equipmentCatalog[idx % equipmentCatalog.length];
    return {
      _id: `demo-eq-${idx + 1}`,
      name: `${ref.name} ${idx + 1}`,
      category: ref.category,
      quantity: ref.base + (idx % 4),
      status: idx % 6 === 0 ? 'Maintenance' : 'Available',
      minThreshold: Math.max(1, Math.round(ref.base * 0.2)),
    };
  });

  const vendors = Array.from({ length: 12 }).map((_, idx) => ({
    _id: `demo-vendor-${idx + 1}`,
    resourceName: resourceCatalog[idx % resourceCatalog.length].name,
    category: resourceCatalog[idx % resourceCatalog.length].category,
    vendorName: `Vendor ${idx + 1}`,
    leadTimeDays: 4 + (idx % 10),
  }));

  const opdDoctors = Array.from({ length: 48 }).map((_, idx) => ({
    _id: `demo-opd-doc-${idx + 1}`,
    name: `Dr. OPD ${idx + 1}`,
    specialty: departments[idx % departments.length],
    availability: idx % 5 !== 0,
    shift: shifts[idx % shifts.length],
    normalizedShift: shifts[idx % shifts.length],
    schedule: 'Mon-Sat',
  }));

  const opdAppointments = Array.from({ length: 280 }).map((_, idx) => ({
    _id: `demo-opd-appt-${idx + 1}`,
    patient: `Patient ${idx + 1}`,
    doctor: opdDoctors[idx % opdDoctors.length].name,
    time: futureIso((idx % 160) + 6),
    status: idx % 6 === 0 ? 'Completed' : 'Scheduled',
    appointmentType: idx % 3 === 0 ? 'Follow-up' : 'New',
    channel: idx % 4 === 0 ? 'Online' : 'Walk-in',
    expectedDurationMinutes: 15 + (idx % 4) * 10,
    reason: 'Routine check',
    notes: 'Auto generated',
    seasonTag: 'Monsoon',
    slotHour: new Date(futureIso((idx % 160) + 6)).getHours(),
    createdAt: pastIso(idx % 240),
  }));

  const opdQueue = Array.from({ length: 180 }).map((_, idx) => ({
    _id: `demo-opd-queue-${idx + 1}`,
    patientName: `Patient ${idx + 1}`,
    reason: 'General check',
    priority: idx % 7 === 0 ? 'High' : 'Normal',
    status: idx % 3 === 0 ? 'In Service' : 'Waiting',
    assignedDoctor: opdDoctors[idx % opdDoctors.length].name,
    notes: 'Queue flow',
    checkInAt: pastIso(idx % 12),
    serviceStartedAt: idx % 3 === 0 ? pastIso(idx % 6) : null,
  }));

  const opdConsultations = Array.from({ length: 200 }).map((_, idx) => ({
    _id: `demo-opd-consult-${idx + 1}`,
    patient: `Patient ${idx + 1}`,
    doctor: opdDoctors[idx % opdDoctors.length].name,
    notes: 'Clinical notes summary.',
    date: new Date(now - (idx % 30) * 86400000).toISOString().slice(0, 10),
    status: idx % 4 === 0 ? 'Closed' : 'Open',
    summary: 'Consultation summary.',
    aiSummary: 'Follow-up in 2 weeks.',
    keywords: ['follow-up', 'review'],
    followUpPlan: 'Schedule follow-up',
    followUpDate: new Date(now + (idx % 14) * 86400000).toISOString().slice(0, 10),
    createdAt: pastIso(idx % 240),
  }));

  const icuPatients = Array.from({ length: 60 }).map((_, idx) => ({
    _id: `demo-icu-${idx + 1}`,
    name: `ICU Patient ${idx + 1}`,
    oxygen: 90 + (idx % 8),
    heartRate: 84 + (idx % 40),
    bp: `${110 + (idx % 20)}/${70 + (idx % 15)}`,
    status: idx % 5 === 0 ? 'Critical' : 'Stable',
    createdAt: pastIso(idx % 120),
  }));

  const icuAlerts = Array.from({ length: 40 }).map((_, idx) => ({
    _id: `demo-icu-alert-${idx + 1}`,
    message: `Vitals fluctuation ${idx + 1}`,
    severity: idx % 3 === 0 ? 'High' : 'Medium',
    status: idx % 4 === 0 ? 'Resolved' : 'Active',
    createdAt: pastIso(idx % 48),
  }));

  const radiologyRequests = Array.from({ length: 160 }).map((_, idx) => ({
    _id: `demo-rad-req-${idx + 1}`,
    patient: `Patient ${idx + 1}`,
    scan: idx % 2 === 0 ? 'CT Scan' : 'MRI Scan',
    status: idx % 4 === 0 ? 'In Progress' : 'Queued',
    createdAt: pastIso(idx % 96),
  }));

  const radiologyReports = Array.from({ length: 120 }).map((_, idx) => ({
    _id: `demo-rad-rep-${idx + 1}`,
    patient: `Patient ${idx + 1}`,
    scan: idx % 2 === 0 ? 'CT Scan' : 'MRI Scan',
    fileName: `scan_${idx + 1}.pdf`,
    notes: 'No acute findings',
    status: 'Uploaded',
    createdAt: pastIso(idx % 72),
  }));

  const otSurgeries = Array.from({ length: 160 }).map((_, idx) => ({
    _id: `demo-ot-${idx + 1}`,
    patient: `Patient ${idx + 1}`,
    procedure: idx % 2 === 0 ? 'Ortho Fixation' : 'Cardiac Cath',
    time: futureIso((idx % 72) + 4),
    status: idx % 5 === 0 ? 'Completed' : 'Scheduled',
    createdAt: pastIso(idx % 72),
  }));

  const otAllocations = Array.from({ length: 120 }).map((_, idx) => ({
    _id: `demo-ot-alloc-${idx + 1}`,
    department: departments[idx % departments.length],
    patient_load: idx % 3 === 0 ? 'High' : 'Medium',
    shift: shifts[idx % shifts.length],
    allocation_decision: 'Auto scheduled OT team',
    createdAt: pastIso(idx % 60),
  }));

  const departmentPerformance = departments.map((dept, idx) => ({
    department: dept,
    patients: 48 + (idx % 6) * 18,
    avgTreatmentMinutes: 28 + (idx % 6) * 4,
    dischargeRate: 62 + (idx % 5) * 5,
    delayRate: 8 + (idx % 4) * 3,
    score: 68 + (idx % 6) * 4,
    throughputPerHour: 3.5 + (idx % 5) * 0.6,
    queueLength: 6 + (idx % 10),
  }));
  const bottlenecks = departmentPerformance.filter((item) => item.delayRate > 12).map((item) => item.department);

  const financeSummary = (() => {
    const monthlySeries = demoMonthlySeries(8200000, 620000);
    const dailySeries = demoDailySeries(1200000, 90000);
    const totalRevenue = monthlySeries.reduce((sum, row) => sum + row.value, 0);
    const totalExpenses = Math.round(totalRevenue * 0.62);
    const profit = totalRevenue - totalExpenses;
    return {
      totalRevenue,
      totalExpenses,
      profit,
      departmentBreakdown: departments.slice(0, 6).map((dept, idx) => ({ department: dept, amount: 900000 + idx * 220000 })),
      expenseBreakdown: [
        { category: 'Supplies', amount: 1320000 },
        { category: 'Equipment', amount: 980000 },
        { category: 'Staffing', amount: 1680000 },
        { category: 'Facilities', amount: 720000 },
      ],
      dailySeries,
      monthlySeries,
      fraudAlerts: ['Invoice amount exceeded threshold in ER', 'High-cost ICU claim flagged'],
      payerDelayDays: 18.6,
      delinquentPayers: 24,
    };
  })();

  const payerDelays = {
    averageDelayDays: 18,
    insurers: [
      { insurer: 'Star Health', avgDelayDays: 16 },
      { insurer: 'Care Plus', avgDelayDays: 21 },
      { insurer: 'MediAssist', avgDelayDays: 19 },
    ],
  };

  const staffSkillSummary = {
    skills: [
      { skill: 'Trauma', count: 46 },
      { skill: 'ICU', count: 52 },
      { skill: 'Cardiology', count: 38 },
      { skill: 'Radiology', count: 26 },
      { skill: 'Surgery', count: 34 },
    ],
    recommendations: ['Add 6 ICU nurses', 'Cross-train ER techs'],
  };

  const staffOptimizer = {
    recommendations: [
      { department: 'Emergency', action: 'Add 4 nurses', reason: 'High queue length' },
      { department: 'Radiology', action: 'Add 2 technicians', reason: 'Scan backlog' },
    ],
  };

  const resourcesOverview = {
    beds: {
      total: 340,
      occupied: 260,
      available: 80,
      icu: { total: 48, occupied: 34 },
      emergency: { total: 56, occupied: 42 },
      general: { total: 236, occupied: 184 },
    },
    resources,
    equipment,
    staff: {
      total: staff.length,
      available: staff.filter((item) => item.availability).length,
      byDepartment: departments.map((dept) => ({
        department: dept,
        total: staff.filter((item) => item.department === dept).length,
        available: staff.filter((item) => item.department === dept && item.availability).length,
      })),
    },
    vendors,
    shortages: resources.filter((item) => item.quantity <= item.minThreshold + 5).slice(0, 6),
  };

  const bedForecast = {
    expectedDischarges24h: 46,
    allocationCount: bedAllocations.length,
    forecast: { predicted_bed_demand: 290 },
  };

  const opdInsights = {
    totalAppointments: opdAppointments.length,
    next7Days: 96,
    next30Days: 220,
    peakDay: 'Wed',
    peakHour: 11,
    seasonCoverageScore: 82,
    demandScore: 76,
    weekdayVolume: [
      { label: 'Mon', value: 40 },
      { label: 'Tue', value: 46 },
      { label: 'Wed', value: 52 },
      { label: 'Thu', value: 44 },
      { label: 'Fri', value: 48 },
      { label: 'Sat', value: 32 },
      { label: 'Sun', value: 18 },
    ],
    seasonCoverage: [
      { label: 'Monsoon', value: 38 },
      { label: 'Summer', value: 42 },
      { label: 'Winter', value: 36 },
      { label: 'Spring', value: 40 },
    ],
  };

  const consultationInsights = {
    total: opdConsultations.length,
    followUps: 58,
    summaryCoverage: 84,
    topKeywords: [
      { label: 'follow-up', value: 68 },
      { label: 'cardio', value: 42 },
      { label: 'pain', value: 36 },
    ],
  };

  const doctorCoverage = {
    availabilityRate: 82,
    specialtyCoverage: departments.slice(0, 6).map((dept, idx) => ({
      specialty: dept,
      available: 6 + (idx % 4),
      total: 10 + (idx % 4),
    })),
    shiftCoverage: shifts.map((shift, idx) => ({ shift, count: 14 + idx * 4 })),
    coverageGaps: ['Pediatrics night shift', 'Radiology weekend'],
  };

  const icuVitals = {
    average_oxygen: 94,
    average_heart_rate: 96,
    critical_patients: 12,
    patient_count: icuPatients.length,
  };

  const icuRisk = {
    risk_score: 0.62,
    risk_level: 'Medium',
    recommendations: ['Increase monitoring frequency', 'Review ventilator settings'],
  };

  const alerts = Array.from({ length: 40 }).map((_, idx) => ({
    _id: `demo-alert-${idx + 1}`,
    message: `Operational alert ${idx + 1}`,
    priority: idx % 5 === 0 ? 'High' : 'Medium',
    status: idx % 4 === 0 ? 'resolved' : 'pending',
    createdAt: pastIso(idx % 72),
  }));

  const ambulances = Array.from({ length: 24 }).map((_, idx) => ({
    _id: `demo-amb-${idx + 1}`,
    ambulanceId: `AMB-${100 + idx}`,
    status: idx % 4 === 0 ? 'en_route' : 'available',
    driver: { name: `Driver ${idx + 1}` },
  }));

  const analytics = Array.from({ length: 90 }).map((_, idx) => ({
    _id: `demo-analytics-${idx + 1}`,
    eventType: idx % 2 === 0 ? 'bed_forecast' : 'staff_load',
    value: 0.4 + (idx % 10) * 0.05,
    createdAt: pastIso(idx % 120),
  }));

  const predictions = Array.from({ length: 120 }).map((_, idx) => ({
    _id: `demo-pred-${idx + 1}`,
    model: idx % 2 === 0 ? 'icu_risk' : 'opd_no_show',
    risk_score: 0.25 + (idx % 12) * 0.05,
    createdAt: pastIso(idx % 96),
  }));

  const departmentsList = departments.map((name, idx) => ({
    _id: `demo-dept-${idx + 1}`,
    name,
    createdAt: pastIso(idx * 12),
  }));

  const messages = Array.from({ length: 10 }).map((_, idx) => ({
    _id: `demo-msg-${idx + 1}`,
    messageType: 'resource',
    subject: `Resource request ${idx + 1}`,
    details: 'Requesting supplies.',
    requestDetails: { urgencyLevel: 'medium', resourceName: resourceCatalog[idx % resourceCatalog.length].name, resourceQuantity: 8 + idx },
    status: idx % 3 === 0 ? 'approved' : 'pending',
    createdAt: pastIso(idx * 24),
  }));

  const agreements = Array.from({ length: 6 }).map((_, idx) => ({
    _id: `demo-agree-${idx + 1}`,
    dataTypes: ['beds', 'resources', 'staff'],
    status: 'active',
    createdAt: pastIso(idx * 48),
  }));

  return {
    departments,
    staff,
    invoices,
    claims,
    bedAllocations,
    reports,
    ingestedReports,
    resourcesOverview,
    bedForecast,
    opdAppointments,
    opdDoctors,
    opdQueue,
    opdConsultations,
    opdInsights,
    consultationInsights,
    doctorCoverage,
    icuPatients,
    icuAlerts,
    icuVitals,
    icuRisk,
    radiologyRequests,
    radiologyReports,
    otSurgeries,
    otAllocations,
    departmentPerformance,
    bottlenecks,
    financeSummary,
    payerDelays,
    staffSkillSummary,
    staffOptimizer,
    alerts,
    ambulances,
    analytics,
    predictions,
    departmentsList,
    messages,
    agreements,
  };
})();

const demoPublicDashboard = () => ({
  alerts: demoIncidents(6).map((item) => ({
    id: item.id,
    message: `${item.type} incident reported`,
    emergencyType: item.severity,
    priority: item.severity,
    createdAt: item.occurred_at,
    location: { lat: item.lat, lng: item.lng, area: 'Central Zone' },
  })),
  resourceRequests: [
    { id: 'req-1', requestType: 'Blood O+', createdAt: new Date().toISOString(), status: 'Open' },
    { id: 'req-2', requestType: 'ICU Bed', createdAt: new Date(Date.now() - 3600000).toISOString(), status: 'In Review' },
  ],
  donationHistory: [
    { id: 'don-1', donationDate: new Date(Date.now() - 86400000).toISOString(), units: 1 },
  ],
  hospitalMessages: [
    { id: 'msg-1', message: 'Follow-up appointment scheduled', createdAt: new Date().toISOString() },
  ],
  riskTimeline: Array.from({ length: 5 }).map((_, idx) => ({ id: `risk-${idx}`, risk: demoRandom(10, 40) })),
  anomalies: ['Oxygen levels trending low in the evening'],
  latestVitals: { metrics: { heart_rate: 84, oxygen: 97 } },
});

const getDemoResponse = (path, method) => {
  const lower = path.toLowerCase();

  if (lower.startsWith('/v2/ai/insights')) return demoGovernmentInsights();

  if (lower.startsWith('/v2/government/command/overview')) {
    return { hospitals: 260, ambulances: 520, emergencies: demoRandom(32, 60) };
  }
  if (lower.startsWith('/v2/government/decision/engine')) {
    return {
      decisions: [
        {
          event: 'Emergency spike',
          location: 'Central Zone',
          reason: '18 incidents in 20 minutes',
          confidence: 0.92,
          suggested_action: 'Deploy 3 ambulances',
          impact: 'High',
        },
        {
          event: 'Hospital overload',
          location: 'South Zone',
          reason: 'Bed occupancy above 85%',
          confidence: 0.87,
          suggested_action: 'Reserve 20 beds and reroute',
          impact: 'High',
        },
      ]
    };
  }
  if (lower.startsWith('/v2/government/predictions/anomaly')) {
    return { prediction: { anomaly_hours: ['08:00', '14:00', '21:00'] } };
  }
  if (lower.startsWith('/v2/government/monitoring/summary')) {
    return {
      active_emergencies: demoRandom(18, 38),
      avg_response_minutes: demoRandom(8, 16),
      resource_utilization: demoRandom(62, 86),
      ambulances: { total: 184, available: demoRandom(60, 110) },
    };
  }
  if (lower.startsWith('/v2/government/monitoring/feed')) {
    const feed = demoIncidents(12);
    return { count: feed.length, data: feed };
  }
  if (lower.startsWith('/v2/government/resources/hospitals')) {
    const hospitals = demoHospitals(36);
    return { count: hospitals.length, data: hospitals };
  }
  if (lower.startsWith('/v2/government/resources/ambulances')) {
    const ambulances = demoAmbulances(48);
    return { count: ambulances.length, data: ambulances };
  }
  if (lower.startsWith('/v2/government/verification/pending')) {
    return {
      count: 4,
      data: [
        { id: 'demo-ver-1', entity_type: 'hospital', entity_id: 'demo-hosp-1', notes: 'Pending compliance audit', created_at: new Date().toISOString() },
        { id: 'demo-ver-2', entity_type: 'ambulance', entity_id: 'demo-amb-2', notes: 'License verification', created_at: new Date().toISOString() },
      ],
    };
  }
  if (lower.startsWith('/v2/government/policy/actions')) {
    return {
      count: 2,
      data: [
        { id: 'demo-policy-1', title: 'Increase ER coverage', action: 'Activate surge staff', status: 'In Review' },
        { id: 'demo-policy-2', title: 'Open pop-up clinics', action: 'Deploy mobile unit', status: 'Approved' },
      ],
    };
  }
  if (lower.startsWith('/v2/government/disaster/recent')) {
    return {
      count: 3,
      data: [
        { id: 'demo-dis-1', disaster_type: 'road_accident_cluster', zone: 'Zone A', severity: 'Critical', lat: 12.96, lng: 77.58, started_at: new Date().toISOString() },
        { id: 'demo-dis-2', disaster_type: 'flood_alert', zone: 'Zone B', severity: 'High', lat: 12.99, lng: 77.62, started_at: new Date(Date.now() - 3600000).toISOString() },
      ],
    };
  }
  if (lower.startsWith('/v2/government/disaster/detect')) {
    return { status: 'ok', disaster: { id: 'demo-dis-9', type: 'cluster_detected', severity: 'High' } };
  }
  if (lower.startsWith('/v2/government/disaster/trigger')) {
    return { status: 'ok', disaster_id: 'demo-dis-trigger' };
  }
  if (lower.startsWith('/v2/government/disaster/broadcast')) {
    return { status: 'ok', delivered: demoRandom(1200, 2600) };
  }
  if (lower.startsWith('/v2/government/simulation/start')) {
    return { status: 'running', session_id: `demo-sim-${Date.now()}` };
  }
  if (lower.startsWith('/v2/government/simulation/multi-phase')) {
    return { status: 'ok', summary: { total: demoRandom(60, 140) } };
  }
  if (lower.startsWith('/v2/government/simulation/after-action')) {
    return {
      report: {
        summary: { total: demoRandom(60, 140), critical: demoRandom(8, 20), response_gap_minutes: demoRandom(6, 14) },
        recommendations: ['Deploy surge ICU teams', 'Activate mobile triage unit', 'Increase standby ambulances'],
      },
    };
  }

  const hospitalOps = demoHospitalOpsData;

  if (lower.startsWith('/api/hospital-ops/ceo/global-metrics')) return demoHospitalMetrics();
  if (lower.startsWith('/api/hospital-ops/ceo/ai-insights')) return demoHospitalInsights();
  if (lower.startsWith('/api/hospital-ops/ceo/department-performance/logs') && method === 'POST') {
    return { status: 'ok' };
  }
  if (lower.startsWith('/api/hospital-ops/ceo/department-performance')) {
    return {
      count: hospitalOps.departmentPerformance.length,
      departments: hospitalOps.departmentPerformance,
      bottlenecks: hospitalOps.bottlenecks,
    };
  }
  if (lower.startsWith('/api/hospital-ops/ceo/resources')) return hospitalOps.resourcesOverview;
  if (lower.startsWith('/api/hospital-ops/ceo/beds/forecast')) return hospitalOps.bedForecast;
  if (lower.startsWith('/api/hospital-ops/ceo/benchmarks')) {
    return {
      count: 4,
      data: [
        { metric: 'avg_occupancy', value: 79.5, source: 'ops_feed' },
        { metric: 'avg_wait_minutes', value: 26.4, source: 'ops_feed' },
        { metric: 'staff_coverage', value: 86.9, source: 'ops_feed' },
        { metric: 'opd_utilization', value: 72.3, source: 'ops_feed' },
      ],
    };
  }
  if (lower.startsWith('/api/hospital-ops/ceo/ambulance/coordination')) {
    return {
      activeAssignments: demoRandom(12, 22),
      availableUnits: demoRandom(14, 26),
      guidance: ['Increase coverage near Central Zone', 'Standby units ready for surge'],
      multiVehiclePlan: [{ recommendation: 'Deploy 3 units to Zone B' }],
    };
  }

  if (lower.startsWith('/api/hospital-ops/emergency/bed-allocation')) {
    if (method === 'POST') {
      return {
        _id: `demo-alloc-${Date.now()}`,
        patientName: 'Demo Patient',
        bedType: 'ICU',
        status: 'Assigned',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.bedAllocations.length, data: hospitalOps.bedAllocations };
  }
  if (lower.startsWith('/api/hospital-ops/emergency/feed')) {
    const feed = demoIncidents(16).map((item) => ({
      id: item.id,
      patientName: `Patient ${item.id.slice(-2)}`,
      location: 'Ward A',
      symptoms: 'Chest pain',
      severity: item.severity,
      status: 'Unassigned',
    }));
    return { data: feed };
  }
  if (lower.startsWith('/api/hospital-ops/emergency/intake')) {
    return { data: demoIncidents(14) };
  }

  if (lower.startsWith('/api/hospital-ops/finance/revenue')) return hospitalOps.financeSummary;
  if (lower.startsWith('/api/hospital-ops/finance/claims')) {
    return { count: hospitalOps.claims.length, data: hospitalOps.claims };
  }
  if (lower.startsWith('/api/hospital-ops/finance/payer-delays')) return hospitalOps.payerDelays;
  if (lower.startsWith('/api/hospital-ops/finance/invoices')) {
    if (method === 'POST') {
      return {
        _id: `demo-inv-${Date.now()}`,
        patientName: 'Demo Patient',
        department: 'General',
        amount: 42000,
        status: 'Unpaid',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.invoices.length, data: hospitalOps.invoices };
  }

  if (lower.startsWith('/api/hospital-ops/staff/skills/summary')) return hospitalOps.staffSkillSummary;
  if (lower.startsWith('/api/hospital-ops/staff/optimizer')) return hospitalOps.staffOptimizer;
  if (lower.startsWith('/api/hospital-ops/staff')) {
    if (method === 'POST') {
      return {
        _id: `demo-staff-${Date.now()}`,
        name: 'Demo Staff',
        department: 'Emergency',
        role: 'Nurse',
        availability: true,
      };
    }
    return { count: hospitalOps.staff.length, data: hospitalOps.staff };
  }

  if (lower.startsWith('/api/hospital-ops/reports/ingest') && method === 'POST') {
    return {
      _id: `demo-ingest-${Date.now()}`,
      name: 'Ingested Report',
      category: 'General',
      summary: 'Demo ingested report summary.',
      generatedAt: new Date().toISOString(),
    };
  }
  if (lower.startsWith('/api/hospital-ops/reports/ingested')) {
    return { count: hospitalOps.ingestedReports.length, data: hospitalOps.ingestedReports };
  }
  if (lower.startsWith('/api/hospital-ops/reports/generate') && method === 'POST') {
    return { status: 'ok' };
  }
  if (lower.startsWith('/api/hospital-ops/reports')) {
    return { count: hospitalOps.reports.length, data: hospitalOps.reports };
  }

  if (lower.startsWith('/api/hospital-ops/opd/appointments/insights')) return hospitalOps.opdInsights;
  if (lower.startsWith('/api/hospital-ops/opd/appointments')) {
    if (method === 'POST') {
      return {
        _id: `demo-opd-appt-${Date.now()}`,
        patient: 'Demo Patient',
        doctor: 'Dr. OPD 1',
        time: new Date(Date.now() + 7200000).toISOString(),
        status: 'Scheduled',
        appointmentType: 'New',
        channel: 'Walk-in',
        expectedDurationMinutes: 20,
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.opdAppointments.length, data: hospitalOps.opdAppointments };
  }
  if (lower.startsWith('/api/hospital-ops/opd/doctors/coverage')) return hospitalOps.doctorCoverage;
  if (lower.startsWith('/api/hospital-ops/opd/doctors')) {
    if (method === 'POST') {
      return {
        _id: `demo-opd-doc-${Date.now()}`,
        name: 'Dr. Demo',
        specialty: 'Emergency',
        availability: true,
        shift: 'Morning',
        normalizedShift: 'Morning',
        schedule: 'Mon-Fri',
      };
    }
    return { count: hospitalOps.opdDoctors.length, data: hospitalOps.opdDoctors };
  }
  if (lower.startsWith('/api/hospital-ops/opd/queue')) {
    return { count: hospitalOps.opdQueue.length, data: hospitalOps.opdQueue };
  }
  if (lower.startsWith('/api/hospital-ops/opd/consultations/insights')) return hospitalOps.consultationInsights;
  if (lower.startsWith('/api/hospital-ops/opd/consultations')) {
    if (method === 'POST') {
      return {
        _id: `demo-opd-consult-${Date.now()}`,
        patient: 'Demo Patient',
        doctor: 'Dr. OPD 1',
        notes: 'Demo consultation notes',
        status: 'Open',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.opdConsultations.length, data: hospitalOps.opdConsultations };
  }

  if (lower.startsWith('/api/hospital-ops/icu/risk') && method === 'POST') return hospitalOps.icuRisk;
  if (lower.startsWith('/api/hospital-ops/icu/vitals')) return hospitalOps.icuVitals;
  if (lower.startsWith('/api/hospital-ops/icu/patients')) {
    return { count: hospitalOps.icuPatients.length, data: hospitalOps.icuPatients };
  }
  if (lower.startsWith('/api/hospital-ops/icu/alerts')) {
    if (method === 'POST') {
      return {
        _id: `demo-icu-alert-${Date.now()}`,
        message: 'Demo ICU alert',
        severity: 'High',
        status: 'Active',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.icuAlerts.length, data: hospitalOps.icuAlerts };
  }

  if (lower.startsWith('/api/hospital-ops/radiology/requests')) {
    if (method === 'POST') {
      return {
        _id: `demo-rad-req-${Date.now()}`,
        patient: 'Demo Patient',
        scan: 'CT Scan',
        status: 'Queued',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.radiologyRequests.length, data: hospitalOps.radiologyRequests };
  }
  if (lower.startsWith('/api/hospital-ops/radiology/reports')) {
    if (method === 'POST') {
      return {
        _id: `demo-rad-rep-${Date.now()}`,
        patient: 'Demo Patient',
        scan: 'MRI Scan',
        fileName: 'scan_demo.pdf',
        status: 'Uploaded',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.radiologyReports.length, data: hospitalOps.radiologyReports };
  }

  if (lower.startsWith('/api/hospital-ops/ot/surgeries')) {
    if (method === 'POST') {
      return {
        _id: `demo-ot-${Date.now()}`,
        patient: 'Demo Patient',
        procedure: 'Ortho Fixation',
        time: new Date(Date.now() + 14400000).toISOString(),
        status: 'Scheduled',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.otSurgeries.length, data: hospitalOps.otSurgeries };
  }
  if (lower.startsWith('/api/hospital-ops/ot/allocations')) {
    if (method === 'POST') {
      return {
        _id: `demo-ot-alloc-${Date.now()}`,
        department: 'Surgery',
        patient_load: 'High',
        shift: 'Day',
        allocation_decision: 'Auto scheduled OT team',
        createdAt: new Date().toISOString(),
      };
    }
    return { count: hospitalOps.otAllocations.length, data: hospitalOps.otAllocations };
  }

  if (lower.startsWith('/api/hospital-ops/alerts')) {
    return { count: hospitalOps.alerts.length, data: hospitalOps.alerts };
  }
  if (lower.startsWith('/api/hospital-ops/analytics')) {
    return { count: hospitalOps.analytics.length, data: hospitalOps.analytics };
  }
  if (lower.startsWith('/api/hospital-ops/predictions')) {
    return { count: hospitalOps.predictions.length, data: hospitalOps.predictions };
  }
  if (lower.startsWith('/api/hospital-ops/departments')) {
    return { count: hospitalOps.departmentsList.length, data: hospitalOps.departmentsList };
  }
  if (lower.startsWith('/api/hospital-ops/messages')) {
    return { count: hospitalOps.messages.length, data: hospitalOps.messages };
  }
  if (lower.startsWith('/api/hospital-ops/network/agreements')) {
    return { count: hospitalOps.agreements.length, data: hospitalOps.agreements };
  }
  if (lower.startsWith('/api/hospital-ops/ambulances')) {
    return { count: hospitalOps.ambulances.length, data: hospitalOps.ambulances };
  }

  if (lower.startsWith('/api/hospital-ops/')) {
    return { data: [], count: 0 };
  }

  if (lower.startsWith('/api/hospital-communication/my-hospital/')) {
    return {
      beds: { totalBeds: 340, occupiedBeds: 260, availableBeds: 80 },
      updatedAt: new Date().toISOString(),
    };
  }
  if (lower.startsWith('/api/hospital-communication/mutual-aid/recommendations')) {
    return {
      count: 4,
      data: [
        { id: 'aid-1', hospital: 'Partner Hospital A', distanceKm: 3.2, availableBeds: 18 },
        { id: 'aid-2', hospital: 'Partner Hospital B', distanceKm: 5.8, availableBeds: 24 },
        { id: 'aid-3', hospital: 'Partner Hospital C', distanceKm: 7.4, availableBeds: 12 },
        { id: 'aid-4', hospital: 'Partner Hospital D', distanceKm: 9.1, availableBeds: 20 },
      ],
    };
  }
  if (lower.startsWith('/api/hospital-communication/transfer/request')) {
    return { status: 'ok', request_id: `demo-transfer-${Date.now()}` };
  }

  if (lower.startsWith('/api/ambulance/assignments')) {
    const data = demoAmbulanceAssignments();
    return { count: data.length, data };
  }
  if (lower.startsWith('/api/ambulance/patient-info')) {
    const data = demoAmbulancePatientInfo();
    return { count: data.length, data };
  }
  if (lower.includes('/api/ambulance/') && lower.endsWith('/predict-eta')) {
    return {
      success: true,
      data: {
        etaPrediction: { estimatedMinutes: demoRandom(8, 16), trafficFactor: demoFloat(0.7, 0.95, 2) }
      }
    };
  }
  if (lower.includes('/api/ambulance/') && lower.endsWith('/start-route')) {
    return { success: true, status: 'tracking' };
  }
  if (lower.startsWith('/api/ambulance/create')) {
    return { success: true, status: 'created' };
  }
  if (lower.startsWith('/api/ambulance/emergency-status')) {
    return demoAmbulanceEmergencyStatus();
  }
  if (lower.startsWith('/api/ambulance/history')) {
    const data = demoAmbulanceHistory();
    return { count: data.length, data };
  }
  if (lower.startsWith('/api/ambulance')) {
    const data = demoAmbulanceFleet();
    return { success: true, count: data.length, data };
  }

  if (lower.startsWith('/v2/integrations/maps/geocode')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const query = (params.get('query') || '').toLowerCase();
    const lookup = [
      { key: 'majestic', lat: 12.9716, lng: 77.5946, display: 'Majestic, Bengaluru' },
      { key: 'cubbon', lat: 12.9763, lng: 77.5929, display: 'Cubbon Park, Bengaluru' },
      { key: 'st. martha', lat: 12.9686, lng: 77.5995, display: "St. Martha's Hospital" },
      { key: 'bowring', lat: 12.9785, lng: 77.5971, display: 'Bowring Hospital' },
      { key: 'shivajinagar', lat: 12.985, lng: 77.605, display: 'Shivajinagar, Bengaluru' },
      { key: 'mg road', lat: 12.9747, lng: 77.6134, display: 'MG Road, Bengaluru' },
    ];
    const match = lookup.find((item) => query.includes(item.key));
    const location = match || {
      lat: demoFloat(12.92, 12.99, 4),
      lng: demoFloat(77.55, 77.63, 4),
      display: params.get('query') || 'Bengaluru',
    };
    return { status: 'ok', provider: 'demo', location };
  }

  if (lower.startsWith('/v2/integrations/traffic')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const origin = parseCoordsFromText(params.get('origin')) || { lat: 12.9716, lng: 77.5946 };
    const destination = parseCoordsFromText(params.get('destination')) || { lat: 12.9686, lng: 77.5995 };
    return demoTraffic(origin.lat, origin.lng, destination.lat, destination.lng);
  }

  if (lower.startsWith('/v2/route')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const startLat = Number(params.get('start_lat'));
    const startLng = Number(params.get('start_lng'));
    const endLat = Number(params.get('end_lat'));
    const endLng = Number(params.get('end_lng'));
    const includeGeometry = params.get('include_geometry') === 'true' || params.get('include_geometry') === '1';
    return demoRoute(startLat, startLng, endLat, endLng, includeGeometry);
  }

  if (lower.startsWith('/api/hosp/predict_eta')) {
    return {
      eta_minutes: demoRandom(8, 16),
      base_minutes: demoRandom(6, 10),
      traffic_multiplier: demoFloat(1.1, 1.6, 2),
      route: ['Downtown', 'Central City General'],
      meta: { confidence: 0.84, reasoning: ['Traffic signals moderate'], references: [] },
    };
  }
  if (lower.startsWith('/api/hosp/predict_bed_forecast')) {
    return { predicted_bed_demand: demoRandom(40, 90), meta: { confidence: 0.8 } };
  }
  if (lower.startsWith('/api/hosp/predict_staff_allocation')) {
    return { allocation_decision: 'Increase staff by 3 in ER', meta: { confidence: 0.78 } };
  }
  if (lower.startsWith('/api/hosp/predict_disease_forecast')) {
    return {
      forecast: Array.from({ length: 7 }).map((_, idx) => ({
        date: new Date(Date.now() + idx * 86400000).toISOString().slice(0, 10),
        predicted_cases: demoRandom(20, 60),
      })),
      meta: { confidence: 0.82 },
    };
  }

  if (lower.startsWith('/api/gov/predict_outbreak')) {
    return {
      forecast: Array.from({ length: 7 }).map((_, idx) => ({
        date: new Date(Date.now() + idx * 86400000).toISOString().slice(0, 10),
        predicted_cases: demoRandom(30, 80),
        confidence_high: demoRandom(60, 120),
      })),
      meta: { confidence: 0.83 },
    };
  }
  if (lower.startsWith('/api/gov/predict_allocation')) {
    return { optimal_action: 'Deploy 4 ambulances to Central Zone', meta: { confidence: 0.8 } };
  }
  if (lower.startsWith('/api/gov/predict_policy_segment')) {
    return { segment_label: 'High Risk', meta: { confidence: 0.76 } };
  }
  if (lower.startsWith('/api/gov/predict_performance_score')) {
    return { predicted_performance_score: demoRandom(62, 88), meta: { confidence: 0.8 } };
  }
  if (lower.startsWith('/api/gov/predict_availability')) {
    return { predicted_availability_score: demoRandom(60, 92), meta: { confidence: 0.82 } };
  }

  if (lower.startsWith('/api/dashboard/public/') && lower.includes('/full')) return demoPublicDashboard();
  if (lower.startsWith('/api/notifications/')) {
    return { stats: { recent_critical_alerts: demoRandom(2, 6), total_sos_calls: demoRandom(14, 32) } };
  }
  if (lower.startsWith('/api/donors/forecast')) return { supply: demoRandom(120, 220), demand: demoRandom(140, 240), demand_index: demoRandom(30, 80), availability_score: demoRandom(60, 90) };
  if (lower.startsWith('/api/donors')) return demoHospitals(6).map((item, idx) => ({
    id: `donor-${idx + 1}`,
    name: `Donor ${idx + 1}`,
    bloodGroup: ['O+', 'A+', 'B+', 'AB+'][idx % 4],
    distance: demoFloat(1.2, 8.4, 1),
  }));
  if (lower.startsWith('/api/family/members')) {
    if (method === 'POST') {
      return { id: `fam-${Date.now()}`, name: 'Demo Member', relation: 'Sibling', phone: '900000003' };
    }
    return { data: [
      { id: 'fam-1', name: 'Riya', relation: 'Sister', phone: '900000001' },
      { id: 'fam-2', name: 'Rohit', relation: 'Father', phone: '900000002' },
    ] };
  }

  if (lower.startsWith('/v2/public/health/summary')) return { status: 'ok', health_score: demoRandom(62, 88), uptime: '99.98%' };
  if (lower.startsWith('/v2/public/sos/')) {
    return {
      id: 'demo-sos-1',
      status: 'Dispatched',
      ambulance: { eta: demoRandom(6, 12), location: { lat: 12.971, lng: 77.594 } },
    };
  }
  if (lower.startsWith('/v2/public/sos')) {
    return { sos_id: 'demo-sos-1', status: 'queued' };
  }
  if (lower.startsWith('/v2/public/donors/match')) {
    return {
      donors: Array.from({ length: 6 }).map((_, idx) => ({
        id: `demo-donor-${idx + 1}`,
        name: `Donor ${idx + 1}`,
        blood_group: ['O+', 'A+', 'B+', 'AB+'][idx % 4],
        distance_km: demoFloat(1.2, 6.8, 1),
        score: demoRandom(70, 96),
      })),
    };
  }
  if (lower.startsWith('/v2/public/donors/notify')) {
    return { status: 'ok', notified: demoRandom(4, 12) };
  }
  if (lower.startsWith('/api/requests')) {
    return { status: 'ok', data: [{ id: 'req-demo', request_type: 'blood', status: 'Open' }] };
  }
  if (lower.startsWith('/api/analyze_report_file')) {
    return { status: 'ok', summary: 'Demo OCR analysis: no critical anomalies detected.', risk_score: demoRandom(12, 28) };
  }
  if (lower.startsWith('/api/analyze_report')) {
    return { status: 'ok', summary: 'Demo analysis: no critical anomalies detected.', risk_score: demoRandom(12, 28) };
  }
  if (lower.startsWith('/api/predict_user_forecast')) {
    return { forecast: Array.from({ length: 5 }).map((_, idx) => ({ day: `D${idx + 1}`, value: demoRandom(60, 90) })) };
  }
  if (lower.startsWith('/api/predict_user_cluster')) {
    return { cluster: 'Moderate Risk', confidence: 0.76 };
  }
  if (lower.startsWith('/api/check_compatibility')) {
    return { compatible: true, score: demoRandom(70, 95) };
  }
  if (lower.startsWith('/v2/ml/health-risk')) return { risk_score: demoRandom(12, 38), status: 'Low', meta: { confidence: 0.83 } };
  if (lower.startsWith('/api/predict_health_risk')) return { risk_score: demoRandom(20, 48), risk_level: 'Moderate', meta: { confidence: 0.78 } };
  if (lower.startsWith('/api/health/risk/history')) {
    return { data: Array.from({ length: 4 }).map((_, idx) => ({
      id: `risk-${idx + 1}`,
      createdAt: new Date(Date.now() - idx * 86400000).toISOString(),
      risk_level: ['Low', 'Moderate', 'High'][idx % 3],
      risk_score: demoRandom(18, 70),
      payload: { bmi: demoRandom(22, 30), blood_pressure: demoRandom(118, 148), heart_rate: demoRandom(68, 92), lifestyle_factor: 'Average' },
    })) };
  }
  if (lower.startsWith('/v2/ml/heatmap')) return { data: demoIncidents(12) };
  if (lower.startsWith('/v2/agents/ask')) return { answer: 'Demo response: actionable insights with confidence 0.84.', confidence: 0.84, contextUsed: [] };
  if (lower.startsWith('/v2/search')) return { query: 'demo', results: { users: [], alerts: [], ambulances: [], hospitals: demoHospitals(4) } };

  if (method === 'POST' || method === 'PATCH' || method === 'PUT') {
    return { status: 'ok', demo: true };
  }
  if (method === 'GET') {
    return { data: [], demo: true };
  }
  return null;
};

export const apiFetch = async (path, options = {}) => {
  const method = (options.method || 'GET').toUpperCase();
  const url = `${API_BASE_URL}${path}`;
  const dataMode = getDataMode();
  const useCache = dataMode !== 'demo' && method === 'GET' && options.cache !== 'no-store' && options.cache !== false;
  const ttlMs = Number.isFinite(options.ttlMs) ? options.ttlMs : DEFAULT_TTL_MS;
  const cacheKey = options.cacheKey || `${dataMode}:${method}:${url}`;
  const staleWhileRevalidate = options.staleWhileRevalidate !== false;

  if (dataMode === 'demo') {
    const demoData = getDemoResponse(path, method);
    if (demoData) {
      return { ok: true, status: 200, data: demoData, demo: true };
    }
  }

  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {})
  };
  const token = getAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const cacheEntry = useCache ? responseCache.get(cacheKey) : null;
  if (cacheEntry) {
    const age = Date.now() - cacheEntry.timestamp;
    if (age <= ttlMs) {
      return { ...cacheEntry.value, fromCache: true };
    }
    if (staleWhileRevalidate && !inflightRequests.has(cacheKey)) {
      const refreshPromise = performFetch().finally(() => inflightRequests.delete(cacheKey));
      inflightRequests.set(cacheKey, refreshPromise);
    }
    if (staleWhileRevalidate) {
      return { ...cacheEntry.value, fromCache: true, stale: true };
    }
  }

  if (useCache && inflightRequests.has(cacheKey)) {
    return inflightRequests.get(cacheKey);
  }

  const fetchPromise = performFetch();
  if (useCache) {
    inflightRequests.set(cacheKey, fetchPromise);
  }
  const result = await fetchPromise;
  if (useCache) {
    inflightRequests.delete(cacheKey);
  }
  return result;

  async function performFetch() {
    const controller = new AbortController();
    const timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : DEFAULT_TIMEOUT_MS;
    const timeoutId = timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;
    if (options.signal) {
      if (options.signal.aborted) {
        controller.abort();
      } else {
        options.signal.addEventListener('abort', () => controller.abort(), { once: true });
      }
    }

    try {
      const res = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      const data = await res.json().catch(() => ({}));
      const payload = { ok: res.ok, status: res.status, data };

      if (useCache) {
        responseCache.set(cacheKey, { timestamp: Date.now(), value: payload });
      }
      if (method !== 'GET') {
        responseCache.clear();
      }

      return payload;
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    }
  }
};
