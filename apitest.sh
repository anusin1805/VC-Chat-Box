curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key="AQ.Ab8RN6J883WSqN2FmLmTdXbW62-MLBMX1-hcuM2_wPYorSwbwg" \
-H 'Content-Type: application/json' \
-X POST \
-d '{
  "contents": [{
    "parts":[{"text": "Hello, is this working?"}]
  }]
}'
