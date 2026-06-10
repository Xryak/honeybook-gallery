Client-Facing Flow from Link to Gallery View

Runs entirely locally. Based on seeds and mocks. Data stored in-memory or in a local DB like SQLite.

Endpoints

POST /galleries/:id/otp - generate and "send" (log to console) a 6-digit code, 10 min expiry

POST /galleries/:id/verify - verify code, return session token

GET /galleries/:id (authed) - return gallery metadata + photo list

POST /galleries/:id/favourite (authed) - marks a photo as favourite

Frontend

OTP entry → grid view of thumbnails (seed with ~20 placeholder images) → click to favorite, visually distinct selected state.

Out of scope

Real email sending (log the code instead)

Real image upload (seed photos in a fixture)

Real infrastructure (no cloud, no CDN, no external services)
