import React, { useState } from 'react';
import { API_BASE_URL } from '../config/api';

const ApiTest = () => {
  const [results, setResults] = useState({
    health: null,
    debug: null,
    list: null
  });
  const [userId, setUserId] = useState('');
  const [loading, setLoading] = useState(false);

  const testEndpoint = async (endpoint, name) => {
    try {
      setLoading(true);
      const url = `${API_BASE_URL}/api/hospital-communication${endpoint}`;
      console.log(`Testing ${name}: ${url}`);
      
      const response = await fetch(url);
      const data = await response.json();
      
      setResults(prev => ({
        ...prev,
        [name]: {
          status: response.status,
          data: data
        }
      }));
    } catch (error) {
      setResults(prev => ({
        ...prev,
        [name]: {
          error: error.message
        }
      }));
    } finally {
      setLoading(false);
    }
  };

  const testListEndpoint = async () => {
    if (!userId) {
      alert('Please enter a user/hospital ID');
      return;
    }
    await testEndpoint(`/list/${userId}`, 'list');
  };

  return (
    <div style={{padding: '20px', fontFamily: 'monospace'}}>
      <h1>API Test Page</h1>
      
      <div style={{marginBottom: '20px', padding: '10px', backgroundColor: '#f0f0f0'}}>
        <h3>1. Health Check</h3>
        <button onClick={() => testEndpoint('/health', 'health')} disabled={loading}>
          Test /health
        </button>
        {results.health && (
          <pre style={{backgroundColor: '#fff', padding: '10px', marginTop: '10px'}}>
            {JSON.stringify(results.health, null, 2)}
          </pre>
        )}
      </div>

      <div style={{marginBottom: '20px', padding: '10px', backgroundColor: '#f0f0f0'}}>
        <h3>2. Debug Status</h3>
        <button onClick={() => testEndpoint('/debug/status', 'debug')} disabled={loading}>
          Test /debug/status
        </button>
        {results.debug && (
          <pre style={{backgroundColor: '#fff', padding: '10px', marginTop: '10px'}}>
            {JSON.stringify(results.debug, null, 2)}
          </pre>
        )}
      </div>

      <div style={{marginBottom: '20px', padding: '10px', backgroundColor: '#f0f0f0'}}>
        <h3>3. List Hospitals (requires user ID)</h3>
        <input 
          type="text" 
          placeholder="Enter your user ID" 
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          style={{marginRight: '10px', padding: '5px'}}
        />
        <button onClick={testListEndpoint} disabled={loading}>
          Test /list/:userId
        </button>
        {results.list && (
          <pre style={{backgroundColor: '#fff', padding: '10px', marginTop: '10px'}}>
            {JSON.stringify(results.list, null, 2)}
          </pre>
        )}
      </div>

      <div style={{padding: '10px', backgroundColor: '#e8f4f8', borderRadius: '5px'}}>
        <h3>Instructions:</h3>
        <ol>
          <li>Click "Test /health" - Should return {'{status: "ok"}'}</li>
          <li>Click "Test /debug/status" - Should return hospital and message counts</li>
          <li>Enter your user ID (from browser console when you login) and click "Test /list/:userId"</li>
          <li>Check what hospitals are returned</li>
        </ol>
      </div>
    </div>
  );
};

export default ApiTest;
