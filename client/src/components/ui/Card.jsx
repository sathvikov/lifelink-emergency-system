import React from 'react';

const Card = ({ children, className = '' }) => (
    <div className={`bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-lg border border-white/60 min-w-0 max-w-full overflow-hidden ${className}`}>
        {children}
    </div>
);

export default Card;
