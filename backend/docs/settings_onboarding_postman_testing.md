# Settings and Onboarding Postman Testing

Use this guide to verify the backend endpoints that support the settings tab and onboarding reset/update flow.

## Backend startup

```powershell
cd C:\Users\mrhan\Documents\Mentors\backend
docker compose up -d
.\.venv\Scripts\python.exe .\dev_server.py
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Import into Postman

Import both files:

- `backend/postman/settings-onboarding-local.postman_collection.json`
- `backend/postman/settings-onboarding-local.postman_environment.json`

Select the `Mentors Settings Local` environment before running requests.

## Recommended run order

Run the requests in this order:

1. `1. Issue Fresh Dev Token`
2. `2. Get Current User`
3. `3. Onboarding Status (Fresh User)`
4. `4. Save Initial Onboarding Profile`
5. `5. Select Recommended Mentor`
6. `6. Onboarding Status (Completed)`
7. `7. Update Learning Preferences`
8. `8. Onboarding Status (After Preference Update)`
9. `9. Reset Onboarding`
10. `10. Onboarding Status (After Reset)`
11. `11. Delete Current User`
12. `12. Get Current User (Deleted Account)`

## What this collection verifies

- A fresh dev user can be created and authenticated.
- A new user starts with `onboarded: false`.
- Saving an onboarding profile returns recommendation data.
- Selecting a mentor marks onboarding as complete.
- Updating learning preferences changes the saved profile while keeping the selected mentor.
- Reset clears onboarding profile and mentor selection.
- Account deletion blocks future authenticated access with the same token.

## Notes

- The collection saves `token`, `userId`, and `recommendedMentorId` automatically as collection variables.
- `4. Save Initial Onboarding Profile` stores the first recommended mentor id, and `5. Select Recommended Mentor` reuses it automatically.
- `11. Delete Current User` is intentionally near the end because it makes the issued token unusable afterward.
