# Hospital and Ambulance Parity Report

- Checked at: 2026-03-26T10:01:22.6033967+05:30
- Node base URL: http://127.0.0.1:3001
- FastAPI base URL: http://127.0.0.1:3002
- Total: 20
- Passed: 20
- Failed: 0

| Name | Method | Path | Status Match | Missing In FastAPI | Extra In FastAPI |
|---|---|---|---|---|---|
| hospital_comm_health | GET | /api/hospital-communication/health | PASS | - | - |
| hospital_comm_debug | GET | /api/hospital-communication/debug/status | PASS | - | - |
| hospital_comm_list | GET | /api/hospital-communication/list/69c4b686babfc450e429ceb1 | PASS | - | - |
| hospital_comm_details | GET | /api/hospital-communication/details/69c4b687babfc450e429ceb4 | PASS | - | - |
| hospital_comm_send | POST | /api/hospital-communication/send-message | PASS | - | - |
| hospital_comm_messages | GET | /api/hospital-communication/messages/69c4b687babfc450e429ceb4 | PASS | - | - |
| hospital_comm_sent | GET | /api/hospital-communication/sent-messages/69c4b686babfc450e429ceb1 | PASS | - | - |
| hospital_comm_patch | PATCH | /api/hospital-communication/message/69c4b687babfc450e429ceb7 | PASS | - | - |
| hospital_comm_reply | POST | /api/hospital-communication/message/69c4b687babfc450e429ceb7/reply | PASS | - | - |
| hospital_comm_my | GET | /api/hospital-communication/my-hospital/69c4b686babfc450e429ceb1 | PASS | - | - |
| hospital_comm_my_put | PUT | /api/hospital-communication/my-hospital/69c4b686babfc450e429ceb1 | PASS | - | - |
| hospital_predict_eta | POST | /api/hospital/predict_eta | PASS | - | - |
| hosp_predict_eta_alias | POST | /api/hosp/predict_eta | PASS | - | - |
| ambulance_list | GET | /api/ambulance/ | PASS | - | - |
| ambulance_hospital_list | GET | /api/ambulance/hospital/697b92c00d68c645d33f821a | PASS | - | - |
| ambulance_details | GET | /api/ambulance/6983639b69f63362f115349b | PASS | - | - |
| ambulance_predict_eta | POST | /api/ambulance/6983639b69f63362f115349b/predict-eta | PASS | - | - |
| ambulance_get_route | POST | /api/ambulance/6983639b69f63362f115349b/get-route | PASS | - | - |
| ambulance_status | PUT | /api/ambulance/6983639b69f63362f115349b/status | PASS | - | - |
| ambulance_metrics | GET | /api/ambulance/6983639b69f63362f115349b/metrics | PASS | - | - |
