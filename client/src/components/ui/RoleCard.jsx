import React from 'react';

const RoleCard = ({ title, description, icon, onSelect }) => (
    <button
        type="button"
        onClick={onSelect}
        className="text-left bg-white/80 backdrop-blur-xl p-5 sm:p-6 rounded-2xl shadow-lg border border-white/60 hover:-translate-y-1 transition-all"
    >
        <div className="text-sky-600 text-2xl sm:text-3xl mb-3 sm:mb-4">
            <i className={`fas ${icon}`}></i>
        </div>
        <h3 className="text-base sm:text-lg font-semibold text-slate-900">{title}</h3>
        <p className="text-xs sm:text-sm text-slate-600 mt-2">{description}</p>
    </button>
);

export default RoleCard;
