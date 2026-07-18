// client/src/main.jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' 

// We wrap the app in AuthProvider so user data is available everywhere
import { AuthProvider } from './context/AuthContext';
import { DataModeProvider } from './context/DataModeContext';

ReactDOM.createRoot(document.getElementById('root')).render(
  <DataModeProvider>
    <AuthProvider>
      <App />
    </AuthProvider>
  </DataModeProvider>,
)