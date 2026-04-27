# First Responders Check In Prototype

Local Flask prototype for a simple site register / punch-card style check in and check out system.

## Features

- Register a person once with name and radio number
- Check people in and out without logins
- Store optional comments with each action
- Persist all history in SQLite for later analysis
- Reset the live "currently on site" state automatically on the first request after midnight
- View the last 500 recorded events in the history screen

## Run locally

```powershell
python app.py
```

Then open `http://127.0.0.1:17000`.

## Deployment setup

Run the interactive deployment helper after copying the project to a server:

```powershell
python deploy_config.py
```

It writes a local `.env` file with server-specific settings, creates the database folder if needed, initializes the SQLite schema, and updates `desktop_launcher/launcher-url.txt`.

The configurable settings are:

- `FIRST_RESPONDERS_DATABASE`: full path to the SQLite database file
- `FIRST_RESPONDERS_HOST`: host/interface Flask binds to
- `FIRST_RESPONDERS_PORT`: port Flask listens on
- `FIRST_RESPONDERS_TIMEZONE`: timezone used for dates and reset logic
- `FIRST_RESPONDERS_ADMIN_PASSWORD`: admin area password
- `FIRST_RESPONDERS_SECRET_KEY`: Flask session signing key
- `FIRST_RESPONDERS_DEBUG`: enables or disables Flask debug mode

## Data model

- `people`: master list of names and radio numbers plus current on-site status
- `check_events`: immutable event history including timestamp, event type, and comments
- `app_state`: stores the last date the overnight reset was applied

By default the SQLite database file is created in `data/checkin.db`. A deployment can override this with `FIRST_RESPONDERS_DATABASE` in `.env`. For this prototype the app uses an in-memory SQLite journal mode to reduce sync-lock issues in OneDrive-backed folders.
