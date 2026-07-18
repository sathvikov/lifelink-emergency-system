import React from 'react';

const ResponsiveNavbar = ({
  title = 'LifeLink',
  subtitle,
  onLogoClick,
  onMenuClick,
  onSearchToggle,
  isSearchOpen,
}) => (
  <header className="lg:hidden sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200">
    <div className="flex items-center justify-between h-14 px-4">
      <button
        type="button"
        aria-label="Open menu"
        onClick={onMenuClick}
        className="p-2 rounded-lg text-slate-600 hover:bg-slate-100"
      >
        <i className="fas fa-bars"></i>
      </button>

      <button onClick={onLogoClick} className="flex items-center gap-2">
        <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg shadow">
          <i className="fas fa-heartbeat text-base"></i>
        </div>
        <div className="text-left">
          <p className="text-sm font-bold text-slate-900 font-display leading-tight">{title}</p>
          {subtitle && (
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
              {subtitle}
            </p>
          )}
        </div>
      </button>

      <button
        type="button"
        aria-label="Toggle search"
        aria-pressed={isSearchOpen}
        onClick={onSearchToggle}
        className={`p-2 rounded-lg text-slate-600 hover:bg-slate-100 ${isSearchOpen ? 'bg-slate-100' : ''}`}
      >
        <i className="fas fa-magnifying-glass"></i>
      </button>
    </div>
  </header>
);

export default ResponsiveNavbar;
