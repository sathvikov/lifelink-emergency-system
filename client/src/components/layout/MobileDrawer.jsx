import React, { useEffect } from 'react';

const MobileDrawer = ({ open, onClose, children }) => {
  useEffect(() => {
    if (!open) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape') {
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        aria-label="Close menu"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/40"
      />
      <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-white shadow-2xl border-r border-slate-200">
        {children}
      </div>
    </div>
  );
};

export default MobileDrawer;
