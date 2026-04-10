# Attendance API Documentation

Backend service: FastAPI (`backend/app/main.py`). Default base URL when running locally with Uvicorn is `http://localhost:8000`.

---

## 1. Overview
- **Purpose**: Manage user registration/login, capture attendance via QR and face recognition, and review logs.
- **Content Type**: JSON responses; requests use `application/json`, `multipart/form-data`, or `application/x-www-form-urlencoded` depending on the endpoint.
- **Authentication**: OAuth2 password flow issuing JWT access tokens.

---

## 2. Authentication & Authorization
1. Call **POST `/api/auth/login`** with form fields `username` and `password`.
2. The response contains `access_token` and `token_type` (`bearer`).
3. Send authenticated requests with header:  
   `Authorization: Bearer <access_token>`.
4. Admin-only routes additionally require the authenticated user to have `role = "admin"`.

If authentication fails, endpoints return HTTP 401 with `{"detail": "Could not validate credentials"}` or `{"detail": "Incorrect username or password"}`.

---

## 3. Error Responses
| Status | Description |
| ------ | ----------- |
| 400 | Validation errors (e.g., missing face data, duplicate usernames, incorrect current password). |
| 401 | Authentication failures or missing token. |
| 403 | Authenticated user lacks admin privileges. |
| 404 | Resource not found (user, face match, QR user). |
| 500 | Unexpected server-side issues (e.g., face recognition errors). |

Errors follow FastAPI default structure: `{"detail": "<message>"}`.

---

## 4. Data Models

### 4.1 User Object
Returned by several endpoints via `UserSchema`.
```json5
{
  "id": 1,
  "username": "alice",
  "fullname": "Alice Example",
  "role": "user"
}
```

### 4.2 Token Object
```json5
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### 4.3 Attendance Record
Used by `/api/user/history` (direct SQLAlchemy serialization) and admin log mapping.
```json5
{
  "id": 10,
  "user_id": 1,
  "method": "qr",        // or "face"
  "attendance_type": "in", // toggles between "in" and "out"
  "timestamp": "2026-04-09T08:30:00+07:00"
}
```

### 4.4 Admin Log Item
```json5
{
  "id": 10,
  "username": "alice",
  "fullname": "Alice Example",
  "method": "face",
  "type": "out",
  "time": "2026-04-09T17:15:00+07:00"
}
```

---

## 5. Endpoint Reference

### 5.1 Authentication

#### POST `/api/auth/register`
- **Description**: Create a user account; optionally upload a reference face image (JPEG/PNG).
- **Auth**: None.
- **Request (multipart/form-data)**:
  - `username` (string, required)
  - `password` (string, required)
  - `fullname` (string, required)
  - `role` (string, optional, defaults to `user`; set to `admin` for administrators)
  - `file` (UploadFile, optional) – stored in `backend/app/faces/{username}.jpg`. Validated to contain exactly one face.
- **Responses**:
  - `200 OK` – returns User object.
  - `400 Bad Request` – username exists, no face detected, or invalid image.

#### POST `/api/auth/login`
- **Description**: Issue JWT access token using OAuth2 password flow.
- **Auth**: None.
- **Request (`application/x-www-form-urlencoded`)**:
  - `username`
  - `password`
- **Response**: Token object.

### 5.2 Attendance Capture

#### POST `/api/attendance/qr`
- **Description**: Scan a QR code image; QR text must equal a username.
- **Auth**: None (legacy kiosk/standalone client).
- **Request (multipart/form-data)**:
  - `file` – image containing the QR code.
- **Response**:
  ```json5
  {
    "status": "success",
    "user": "Alice Example",
    "type": "in",
    "time": "2026-04-09T08:30:01.123456"
  }
  ```
- **Errors**: `400` if no QR detected; `404` if username not found.

#### GET `/api/attendance/token`
- **Description**: Generate a 60-second challenge token for the dashboard to display as a QR code.
- **Auth**: Admin bearer token (`get_admin_user` dependency).
- **Response**:
  ```json
  { "token": "<opaque-string>", "expires_in": 60 }
  ```

#### POST `/api/attendance/verify-token`
- **Description**: Mobile client submits the scanned challenge token; the authenticated user is recorded present.
- **Auth**: Bearer token (any authenticated user).
- **Request (`application/x-www-form-urlencoded`)**:
  - `token` (string, required)
- **Response**:
  ```json5
  {
    "status": "success",
    "user": "Alice Example",
    "type": "out",
    "time": "2026-04-09T17:15:01.000Z"
  }
  ```
- **Errors**: `400` if the token is invalid/expired.

#### POST `/api/attendance/face`
- **Description**: Match a captured face photo against the authenticated user's stored reference photo.
- **Auth**: Bearer token; the user must already have uploaded a face photo.
- **Request (multipart/form-data)**:
  - `file` – new capture to compare.
- **Response**:
  ```json
  {
    "status": "success",
    "user": "Alice Example",
    "type": "in",
    "time": "2026-04-09T08:30:01.123456",
    "similarity": 0.87
  }
  ```
- **Errors**: `400` when the user has no stored photo, `403` if similarity < 60%, `500` for processing errors.

### 5.3 User Endpoints

All user endpoints require `Authorization: Bearer <token>`.

#### GET `/api/user/profile`
- **Description**: Fetch current user's profile.
- **Response**: User object.

#### GET `/api/user/history`
- **Description**: List the authenticated user's attendance records (latest first).
- **Response**: Array of Attendance Record objects.

#### POST `/api/user/upload-face`
- **Description**: Upload & crop a face reference photo stored as binary in the database.
- **Request (multipart/form-data)**:
  - `file` – JPEG/PNG containing a single face.
- **Behavior**: Regular users can upload only once; admins may overwrite.
- **Response**: Updated User object.

#### GET `/api/user/face-photo`
- **Description**: Download the authenticated user's stored face photo (JPEG). Returns `404` if none.

#### POST `/api/user/change-password`
- **Description**: Change the authenticated user's password.
- **Request (multipart/form-data or form-urlencoded)**:
  - `current_password`
  - `new_password`
- **Response**:
  ```json
  { "message": "Password updated successfully" }
  ```
- **Errors**: `400` if current password invalid.

### 5.4 Admin Endpoints

Require the bearer token of a user with `role = "admin"` (checked via `get_admin_user` dependency).

#### GET `/api/admin/users`
- **Description**: List every user account. Automatically filters out binary face data and password hashes for stability.
- **Response**: Array of User objects.

#### PUT `/api/admin/user/{user_id}`
- **Description**: Update user basic info.
- **Auth**: Admin only.
- **Request (application/json)**:
  - `fullname` (string, optional)
  - `role` (string, optional: "admin" or "user")
  - `password` (string, optional) – if provided, the user's password will be re-hashed.
- **Response**: `{"status": "success", "message": "User <username> updated"}`.
- **Errors**: `400` if attempting to downgrade the super admin (`admin`).

#### POST `/api/admin/user/{user_id}/force-attendance`
- **Description**: Manually record an attendance entry for a user without face/QR verification.
- **Auth**: Admin only.
- **Query Params**:
  - `attendance_type` (string, required): must be `in` or `out`.
- **Response**: `{"status": "success", "message": "Attendance <type> forced for <username>"}`.

#### GET `/api/admin/user/{user_id}/logs`
- **Description**: Attendance history for a specific user.
- **Response**: Array of Attendance Records for that user.

#### GET `/api/admin/logs`
- **Description**: Retrieve attendance entries for all users with joined profile info.
- **Query Params**: Optional `start_date` and `end_date` (`YYYY-MM-DD`) to filter by day.
- **Response**: Array of Admin Log Items ordered by newest timestamp.

#### DELETE `/api/admin/user/{user_id}`
- **Description**: Permanently delete a user (super admin `admin` is protected).
- **Response**: `{"status": "success", "message": "User <username> deleted"}`.

#### Face Photo Management
- **GET `/api/admin/user/{user_id}/face`**: Download a user's stored face photo (JPEG). Returns `404` if missing.
- **POST `/api/admin/user/{user_id}/face`**: Replace the face photo. Request body mirrors `/api/user/upload-face`.
- **DELETE `/api/admin/user/{user_id}/face`**: Remove a user's stored face photo.

---

## 6. Usage Notes
1. **Attendance Toggle**: `record_attendance` automatically alternates between `in` and `out` for each user per day. The first record of the day is `in`.
2. **Image Handling**: Face reference photos are stored directly in the `users.face_image` BLOB column. Clients fetch them via `/api/user/face-photo` or admin equivalents.
3. **Token Expiry**: Configurable via environment variable `ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440 = 24h). See `backend/app/core/config.py`.
4. **Database Support**: Configurable for SQLite (default), PostgreSQL, or MySQL via `.env` (`DATABASE_URL` or component parts). Ensure the correct driver is installed; see `backend/requirements.txt`.
5. **CORS**: All origins/methods/headers are allowed to support browser clients; restrict in production if needed (`backend/app/main.py`).
6. **QR Challenge Flow**: `GET /api/attendance/token` issues 60s tokens the dashboard should refresh periodically; mobile clients must call `/api/attendance/verify-token` before expiry.

---

## 7. Local Development Checklist
1. Copy `backend/.env.example` → `backend/.env` and fill secrets.
2. Install backend dependencies: `pip install -r backend/requirements.txt`.
3. Launch API: `cd backend && uvicorn app.main:app --reload`.
4. Visit `http://localhost:8000/docs` for auto-generated Swagger UI derived from this API implementation.

---

For questions or contributions, edit the corresponding FastAPI endpoints in `backend/app/main.py` and update this file accordingly.
