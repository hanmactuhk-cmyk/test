# Flow Studio Automation 0.2.0

Desktop Electron controller + Playwright/CDP automation engine.

Features: multi Chrome profiles, prompt queue, concurrent workers, progress, completed/error states, MP4 preview, TXT/CSV/JSON/XLSX import, pause/stop, network response/download capture.

Important: Flow's final video delivery mechanism must be verified against the live account. If Flow does not expose a direct MP4 response/download, the capture layer must be adapted to the observed API/asset flow rather than guessing.

For local development: npm install && npm start.
For EXE: push to GitHub and run Actions workflow; artifact contains installer/portable builds.
