import React from 'react';
import ModuleWorkbench from './ModuleWorkbench';

const ModulePanel = ({ moduleKey, title, description, realtimeChannel }) => (
    <ModuleWorkbench
        moduleKey={moduleKey}
        title={title}
        description={description}
        realtimeChannel={realtimeChannel}
    />
);

export default ModulePanel;
