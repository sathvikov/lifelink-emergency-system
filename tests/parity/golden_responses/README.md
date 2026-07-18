# Golden Responses

Purpose:
Store baseline JSON responses from the current Express backend for parity comparison with FastAPI.

Suggested files:
- auth_signup_201.json
- auth_login_200.json
- dashboard_public_full_200.json
- alerts_create_201.json
- notifications_200.json
- compatibility_200.json
- analyze_report_200.json
- hospital_predict_bed_forecast_200.json
- ambulance_list_200.json

Capture workflow:
1. Start current Express backend.
2. Run requests from tests/smoke/lifelink_smoke.http.
3. Save representative successful and failure responses here.
4. Use same requests against FastAPI and diff responses.
