# Remaining High Priority Parity Report

- Checked at: 2026-03-26T12:28:53.9024504+05:30
- Node base URL: http://127.0.0.1:3001
- FastAPI base URL: http://127.0.0.1:3002
- Total: 44
- Passed: 44
- Failed: 0

| Name | Method | Node Path | FastAPI Path | Status | Missing In FastAPI | Extra In FastAPI |
|---|---|---|---|---|---|---|
| dashboard_hospital_stats | GET | /api/dashboard/hospital/stats | /api/dashboard/hospital/stats | PASS | - | - |
| dashboard_hospital_alerts | GET | /api/dashboard/hospital/alerts | /api/dashboard/hospital/alerts | PASS | - | - |
| dashboard_hospital_alert_update | PUT | /api/dashboard/hospital/alert/69c4d7e3f0906a4a4473727e | /api/dashboard/hospital/alert/69c4d7e3f0906a4a4473727e | PASS | - | - |
| dashboard_admin_pending | GET | /api/dashboard/admin/pending-hospitals | /api/dashboard/admin/pending-hospitals | PASS | - | - |
| dashboard_admin_verify | PUT | /api/dashboard/admin/verify/69c4d7dcf0906a4a4473727b | /api/dashboard/admin/verify/69c4d7dcf0906a4a4473727b | PASS | - | - |
| dashboard_patient_admit | POST | /api/dashboard/hospital/patient/admit | /api/dashboard/hospital/patient/admit | PASS | - | - |
| dashboard_hospital_patients | GET | /api/dashboard/hospital/patients/697b92c00d68c645d33f821a | /api/dashboard/hospital/patients/697b92c00d68c645d33f821a | PASS | - | - |
| dashboard_resource_add | POST | /api/dashboard/hospital/resource/add | /api/dashboard/hospital/resource/add | PASS | - | - |
| dashboard_hospital_resources | GET | /api/dashboard/hospital/resources/697b92c00d68c645d33f821a | /api/dashboard/hospital/resources/697b92c00d68c645d33f821a | PASS | - | - |
| dashboard_notification_delete_alert | DELETE | /api/dashboard/notification/alert/69c4d7ebf0906a4a44737280 | /api/dashboard/notification/alert/69c4d7f0f0906a4a44737282 | PASS | - | - |
| dashboard_notification_delete_request | DELETE | /api/dashboard/notification/request/69c4d7f0f0906a4a44737286 | /api/dashboard/notification/request/69c4d7f0f0906a4a44737284 | PASS | - | - |
| ai_predict_health_risk | POST | /api/predict_health_risk | /api/predict_health_risk | PASS | - | - |
| ai_predict_user_cluster | POST | /api/predict_user_cluster | /api/predict_user_cluster | PASS | - | - |
| ai_predict_user_forecast | POST | /api/predict_user_forecast | /api/predict_user_forecast | PASS | - | - |
| ai_hosp_predict_severity | POST | /api/hosp/predict_severity | /api/hosp/predict_severity | PASS | - | - |
| ai_gov_predict_outbreak | POST | /api/gov/predict_outbreak | /api/gov/predict_outbreak | PASS | - | - |
| ai_gov_predict_severity | POST | /api/gov/predict_severity | /api/gov/predict_severity | PASS | - | - |
| ai_gov_predict_availability | POST | /api/gov/predict_availability | /api/gov/predict_availability | PASS | - | - |
| ai_gov_predict_allocation | POST | /api/gov/predict_allocation | /api/gov/predict_allocation | PASS | - | - |
| ai_gov_predict_policy_segment | POST | /api/gov/predict_policy_segment | /api/gov/predict_policy_segment | PASS | - | - |
| ai_gov_predict_performance_score | POST | /api/gov/predict_performance_score | /api/gov/predict_performance_score | PASS | - | - |
| ai_gov_predict_anomaly | POST | /api/gov/predict_anomaly | /api/gov/predict_anomaly | PASS | - | - |
| ai_hospital_patient_recovery | POST | /api/hospital/patient/recovery | /api/hospital/patient/recovery | PASS | - | - |
| ai_hospital_patient_stay | POST | /api/hospital/patient/stay | /api/hospital/patient/stay | PASS | - | - |
| ai_hospital_inventory_predict | POST | /api/hospital/inventory/predict | /api/hospital/inventory/predict | PASS | - | - |
| ai_ml_predict_eta | POST | /api/ml/predict-eta | /api/ml/predict-eta | PASS | - | - |
| hospital_triage | POST | /api/hospital/triage | /api/hospital/triage | PASS | - | - |
| hospital_eta | POST | /api/hospital/eta | /api/hospital/eta | PASS | - | - |
| hospital_bed_forecast | POST | /api/hospital/bed_forecast | /api/hospital/bed_forecast | PASS | - | - |
| hospital_staff | POST | /api/hospital/staff | /api/hospital/staff | PASS | - | - |
| hospital_donors | POST | /api/hospital/donors | /api/hospital/donors | PASS | - | - |
| hospital_performance | POST | /api/hospital/performance | /api/hospital/performance | PASS | - | - |
| hospital_predict_bed_forecast | POST | /api/hospital/predict_bed_forecast | /api/hospital/predict_bed_forecast | PASS | - | - |
| hospital_predict_staff_allocation | POST | /api/hospital/predict_staff_allocation | /api/hospital/predict_staff_allocation | PASS | - | - |
| hospital_predict_disease_forecast | POST | /api/hospital/predict_disease_forecast | /api/hospital/predict_disease_forecast | PASS | - | - |
| hospital_predict_recovery | POST | /api/hospital/predict_recovery | /api/hospital/predict_recovery | PASS | - | - |
| hospital_predict_stay_duration | POST | /api/hospital/predict_stay_duration | /api/hospital/predict_stay_duration | PASS | - | - |
| hospital_predict_performance | POST | /api/hospital/predict_performance | /api/hospital/predict_performance | PASS | - | - |
| hospital_inventory | POST | /api/hospital/inventory | /api/hospital/inventory | PASS | - | - |
| hospital_comm_delete_message | DELETE | /api/hospital-communication/message/69c4d7f1f0906a4a44737293 | /api/hospital-communication/message/69c4d7f1f0906a4a44737298 | PASS | - | - |
| ambulance_create | POST | /api/ambulance/create | /api/ambulance/create | PASS | - | - |
| ambulance_update_location | POST | /api/ambulance/6983639b69f63362f115349b/update-location | /api/ambulance/6983639b69f63362f115349b/update-location | PASS | - | - |
| ambulance_start_route | POST | /api/ambulance/6983639b69f63362f115349b/start-route | /api/ambulance/6983639b69f63362f115349b/start-route | PASS | - | - |
| ambulance_complete_route | POST | /api/ambulance/6983639b69f63362f115349b/complete-route | /api/ambulance/6983639b69f63362f115349b/complete-route | PASS | - | - |
