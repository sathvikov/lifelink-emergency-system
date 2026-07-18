import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';
import './MyHospital.css';

const MyHospital = () => {
  const { user } = useAuth();
  const [hospital, setHospital] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editMode, setEditMode] = useState(false);

  // Form states
  const [beds, setBeds] = useState({ totalBeds: 0, occupiedBeds: 0, availableBeds: 0 });
  const [doctors, setDoctors] = useState([]);
  const [resources, setResources] = useState([]);
  const [newDoctor, setNewDoctor] = useState({ name: '', department: '', availability: true });
  const [newResource, setNewResource] = useState({ name: '', category: '', totalUnits: 0, availableUnits: 0, unit: 'units' });

  // Fetch hospital details
  useEffect(() => {
    fetchHospitalDetails();
  }, [user]);

  const fetchHospitalDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (!user?.id) {
        throw new Error('User not logged in');
      }

      const { ok, data } = await apiFetch(`/api/hospital-communication/my-hospital/${user.id}`, { method: 'GET' });
      if (!ok) {
        throw new Error('Failed to fetch hospital details');
      }
      setHospital(data);
      setBeds(data.beds || { totalBeds: 0, occupiedBeds: 0, availableBeds: 0 });
      setDoctors(data.doctors || []);
      setResources(data.resources || []);
    } catch (err) {
      setError(err.message);
      console.error('[MyHospital] Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBedsChange = (e) => {
    const { name, value } = e.target;
    const numValue = parseInt(value) || 0;
    
    const updated = { ...beds, [name]: numValue };
    
    // Calculate available beds
    if (name === 'totalBeds' || name === 'occupiedBeds') {
      updated.availableBeds = updated.totalBeds - updated.occupiedBeds;
    }
    
    setBeds(updated);
  };

  const handleAddDoctor = () => {
    if (!newDoctor.name || !newDoctor.department) {
      alert('Please fill in all required fields');
      return;
    }
    setDoctors([...doctors, { ...newDoctor, _id: Date.now().toString() }]);
    setNewDoctor({ name: '', department: '', availability: true });
  };

  const handleRemoveDoctor = (id) => {
    setDoctors(doctors.filter(d => d._id !== id));
  };

  const handleAddResource = () => {
    if (!newResource.name || !newResource.category) {
      alert('Please fill in name and category');
      return;
    }
    
    const available = Math.min(newResource.availableUnits, newResource.totalUnits);
    setResources([...resources, { ...newResource, availableUnits: available, _id: Date.now().toString() }]);
    setNewResource({ name: '', category: '', totalUnits: 0, availableUnits: 0, unit: 'units' });
  };

  const handleRemoveResource = (id) => {
    setResources(resources.filter(r => r._id !== id));
  };

  const handleSaveHospital = async () => {
    try {
      setLoading(true);
      console.log('[MyHospital] Saving hospital details for user:', user.id);
      
      // Remove temporary IDs before sending to server (MongoDB will create real ObjectIds)
      const cleanDoctors = doctors.map(d => {
        const { _id, ...rest } = d;
        return rest;
      });

      const cleanResources = resources.map(r => {
        const { _id, ...rest } = r;
        return rest;
      });

      const payload = {
        beds,
        doctors: cleanDoctors,
        resources: cleanResources
      };

      console.log('[MyHospital] Payload:', payload);

      const { ok, status, data: updated } = await apiFetch(`/api/hospital-communication/my-hospital/${user.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });

      console.log('[MyHospital] Response status:', status);

      if (!ok) {
        console.error('[MyHospital] Error response:', updated);
        throw new Error(updated?.message || updated?.error || `Failed to save hospital details (${status})`);
      }
      console.log('[MyHospital] Hospital updated successfully:', updated);
      setHospital(updated);
      setEditMode(false);
      alert('Hospital details updated successfully!');
    } catch (err) {
      console.error('[MyHospital] Save error:', err.message);
      alert('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="my-hospital-container">
        <div className="loading">Loading hospital details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-hospital-container">
        <div className="error-message">Error: {error}</div>
        <button onClick={fetchHospitalDetails} className="btn-retry">Retry</button>
      </div>
    );
  }

  return (
    <div className="my-hospital-container">
      <div className="hospital-header">
        <h2>🏥 My Hospital</h2>
        <button 
          className={`btn-edit ${editMode ? 'btn-cancel' : ''}`}
          onClick={() => editMode ? setEditMode(false) : setEditMode(true)}
        >
          {editMode ? '✕ Cancel' : '✎ Edit'}
        </button>
      </div>

      {/* BEDS SECTION */}
      <div className="hospital-section">
        <h3>🛏️ Available Beds</h3>
        <div className="beds-grid">
          <div className="bed-card">
            <label>Total Beds</label>
            {editMode ? (
              <input
                type="number"
                name="totalBeds"
                value={beds.totalBeds}
                onChange={handleBedsChange}
                min="0"
              />
            ) : (
              <div className="bed-value">{beds.totalBeds}</div>
            )}
          </div>

          <div className="bed-card">
            <label>Occupied</label>
            {editMode ? (
              <input
                type="number"
                name="occupiedBeds"
                value={beds.occupiedBeds}
                onChange={handleBedsChange}
                min="0"
                max={beds.totalBeds}
              />
            ) : (
              <div className="bed-value">{beds.occupiedBeds}</div>
            )}
          </div>

          <div className="bed-card available">
            <label>Available</label>
            <div className="bed-value">{beds.availableBeds}</div>
          </div>
        </div>
      </div>

      {/* DOCTORS SECTION */}
      <div className="hospital-section">
        <h3>👨‍⚕️ Available Doctors</h3>
        
        {editMode && (
          <div className="add-item-form">
            <h4>Add Doctor</h4>
            <div className="form-row">
              <input
                type="text"
                placeholder="Doctor Name"
                value={newDoctor.name}
                onChange={(e) => setNewDoctor({ ...newDoctor, name: e.target.value })}
              />
              <input
                type="text"
                placeholder="Department"
                value={newDoctor.department}
                onChange={(e) => setNewDoctor({ ...newDoctor, department: e.target.value })}
              />
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={newDoctor.availability}
                  onChange={(e) => setNewDoctor({ ...newDoctor, availability: e.target.checked })}
                />
                Available
              </label>
              <button onClick={handleAddDoctor} className="btn-add">Add</button>
            </div>
          </div>
        )}

        <div className="items-list">
          {doctors.length === 0 ? (
            <p className="empty-state">No doctors added yet</p>
          ) : (
            doctors.map((doctor) => (
              <div key={doctor._id} className="item-card doctor-card">
                <div className="item-info">
                  <strong>{doctor.name}</strong>
                  <p>{doctor.department}</p>
                  <span className={`availability-badge ${doctor.availability ? 'available' : 'unavailable'}`}>
                    {doctor.availability ? '✓ Available' : '✗ Unavailable'}
                  </span>
                </div>
                {editMode && (
                  <button onClick={() => handleRemoveDoctor(doctor._id)} className="btn-remove">×</button>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* RESOURCES SECTION */}
      <div className="hospital-section">
        <h3>📦 Available Resources</h3>
        
        {editMode && (
          <div className="add-item-form">
            <h4>Add Resource</h4>
            <div className="form-row">
              <input
                type="text"
                placeholder="Resource Name"
                value={newResource.name}
                onChange={(e) => setNewResource({ ...newResource, name: e.target.value })}
              />
              <input
                type="text"
                placeholder="Category"
                value={newResource.category}
                onChange={(e) => setNewResource({ ...newResource, category: e.target.value })}
              />
              <input
                type="number"
                placeholder="Total Units"
                value={newResource.totalUnits}
                onChange={(e) => setNewResource({ ...newResource, totalUnits: parseInt(e.target.value) || 0 })}
                min="0"
              />
              <input
                type="number"
                placeholder="Available"
                value={newResource.availableUnits}
                onChange={(e) => setNewResource({ ...newResource, availableUnits: parseInt(e.target.value) || 0 })}
                min="0"
              />
              <input
                type="text"
                placeholder="Unit (units, liters, bottles...)"
                value={newResource.unit}
                onChange={(e) => setNewResource({ ...newResource, unit: e.target.value })}
              />
              <button onClick={handleAddResource} className="btn-add">Add</button>
            </div>
          </div>
        )}

        <div className="items-list">
          {resources.length === 0 ? (
            <p className="empty-state">No resources added yet</p>
          ) : (
            resources.map((resource) => (
              <div key={resource._id} className="item-card resource-card">
                <div className="item-info">
                  <strong>{resource.name}</strong>
                  <p>{resource.category}</p>
                  <p className="resource-units">
                    {resource.availableUnits} / {resource.totalUnits} {resource.unit} available
                  </p>
                </div>
                {editMode && (
                  <button onClick={() => handleRemoveResource(resource._id)} className="btn-remove">×</button>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {editMode && (
        <div className="form-actions">
          <button onClick={handleSaveHospital} className="btn-save">💾 Save Changes</button>
          <button onClick={() => setEditMode(false)} className="btn-cancel">Cancel</button>
        </div>
      )}
    </div>
  );
};

export default MyHospital;
