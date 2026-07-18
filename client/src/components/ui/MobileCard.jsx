import React from 'react';

const MobileCard = ({ children, className = '' }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm min-w-0 max-w-full overflow-hidden break-words ${className}`}>
    {children}
  </div>
);

export default MobileCard;
