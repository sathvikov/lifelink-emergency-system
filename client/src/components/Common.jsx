// client/src/components/Common.jsx
import React from 'react';
import Card from './ui/Card';
// --- ADD THESE IMPORTS ---
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
);

// --- Card Container ---
export const DashboardCard = ({ children, className = "" }) => (
  <Card className={`min-w-0 ${className}`}>
    {children}
  </Card>
);

// --- Input Field ---
export const Input = ({ name, type, placeholder, icon, value, onChange, required = false }) => (
  <div className="relative">
    <span className="absolute left-0 top-0 h-full w-12 flex items-center justify-center pl-3 text-gray-400">
      <i className={`fas ${icon}`}></i>
    </span>
    <input
      name={name}
      type={type}
      placeholder={placeholder}
      value={value}
      required={required}
      onChange={onChange}
      className="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 focus:border-sky-500 focus:ring-2 focus:ring-sky-200 outline-none transition-all bg-gray-50/50"
    />
  </div>
);

// --- Loading Spinner ---
export const LoadingSpinner = () => (
  <div className="flex justify-center items-center p-10">
    <i className="fas fa-spinner fa-spin fa-3x text-sky-500"></i>
  </div>
);

// --- Status Pill (for tables) ---
export const StatusPill = ({ text, color }) => {
  const colors = {
    green: 'bg-green-100 text-green-800',
    yellow: 'bg-yellow-100 text-yellow-800',
    red: 'bg-red-100 text-red-800',
    blue: 'bg-sky-100 text-sky-800',
    gray: 'bg-gray-100 text-gray-800'
  };
  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full ${colors[color] || colors.gray}`}>
      {text}
    </span>
  );
};

// --- Tab Button ---
export const TabButton = ({ label, icon, isActive, onClick }) => (
  <button
    onClick={onClick}
    className={`flex-1 px-4 py-3 text-sm font-semibold text-center transition-colors duration-200 rounded-lg whitespace-nowrap ${
      isActive ? 'bg-white/70 text-sky-700 shadow-md' : 'text-gray-600 hover:bg-white/50'
    }`}
  >
    <i className={`fas ${icon} mr-2 hidden sm:inline`}></i>
    {label}
  </button>
);

// --- Stat Card ---
export const StatCard = ({ title, value, icon, color }) => (
  <DashboardCard>
    <div className={`text-3xl mb-2 ${color}`}>
      <i className={`fas ${icon}`}></i>
    </div>
    <p className="text-gray-600 text-sm font-medium">{title}</p>
    <p className="text-2xl font-bold text-gray-900">{value}</p>
  </DashboardCard>
);

// --- Progress Bar ---
export const ProgressBar = ({ value, colorClass = 'bg-sky-500' }) => (
  <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
    <div
      className={`${colorClass} h-2.5 rounded-full transition-all duration-500`}
      style={{ width: `${value}%` }}
    ></div>
  </div>
);

// --- Explainability Panel ---
export const ExplainabilityPanel = ({ meta }) => {
  if (!meta) return null;
  const confidence = Number.isFinite(meta.confidence) ? Math.round(meta.confidence * 100) : null;
  const reasoning = Array.isArray(meta.reasoning) ? meta.reasoning : [];
  const references = Array.isArray(meta.references) ? meta.references : [];

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 break-words">
      <div className="flex flex-wrap gap-2 mb-2">
        {confidence !== null && (
          <span className="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">
            Confidence: {confidence}%
          </span>
        )}
        {meta.command && (
          <span className="px-2 py-1 rounded-full bg-slate-200 text-slate-700 font-semibold">
            {meta.command}
          </span>
        )}
      </div>
      {reasoning.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">Reasoning</p>
          <ul className="mt-1 space-y-1">
            {reasoning.map((item) => (
              <li key={item} className="flex gap-2 break-words">
                <span>•</span>
                <span className="whitespace-pre-wrap break-words">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {references.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">References</p>
          <ul className="mt-1 space-y-1">
            {references.map((ref, idx) => (
              <li key={`${ref.title || 'ref'}-${idx}`} className="break-words whitespace-pre-wrap">
                <span className="font-semibold text-slate-700">{ref.title || 'Source'}:</span> {ref.detail || ref.url || ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// --- ADD THIS COMPONENT: SimpleBarChart ---
export const SimpleBarChart = ({ data, title, barColorClass }) => {
    // Convert 'bg-green-500' class to actual hex color if needed, or stick to a default
    // ChartJS needs hex/rgba colors, not tailwind classes
    const colorMap = {
        'bg-green-500': 'rgba(34, 197, 94, 0.7)',
        'bg-sky-500': 'rgba(14, 165, 233, 0.7)',
        'bg-red-500': 'rgba(239, 68, 68, 0.7)',
    };
    const bg = colorMap[barColorClass] || 'rgba(54, 162, 235, 0.5)';

    const chartData = {
        labels: data.map(d => d.label),
        datasets: [
            {
                label: title,
                data: data.map(d => d.value),
                backgroundColor: bg,
            },
        ],
    };

    const options = {
        responsive: true,
        plugins: {
            legend: { display: false },
            title: { display: !!title, text: title },
        },
    };

    return (
        <DashboardCard>
            <h3 className="font-bold text-lg text-gray-900 mb-4">{title}</h3>
            <Bar data={chartData} options={options} />
        </DashboardCard>
    );
};

  // --- ADD THIS COMPONENT: SimpleLineChart ---
  export const SimpleLineChart = ({ data, title, lineColor = 'rgba(37, 99, 235, 0.8)' }) => {
    const chartData = {
      labels: data.map((d) => d.label),
      datasets: [
        {
          label: title,
          data: data.map((d) => d.value),
          borderColor: lineColor,
          backgroundColor: 'rgba(37, 99, 235, 0.2)',
          tension: 0.3,
          pointRadius: 3,
          pointHoverRadius: 4,
          fill: true,
        },
      ],
    };

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: !!title, text: title },
      },
      scales: {
        y: {
          ticks: { precision: 0 },
          beginAtZero: true,
        },
      },
    };

    return (
      <DashboardCard>
        <h3 className="font-bold text-lg text-gray-900 mb-4">{title}</h3>
        <div style={{ height: 180 }}>
          <Line data={chartData} options={options} />
        </div>
      </DashboardCard>
    );
  };