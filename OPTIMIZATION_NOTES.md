# PRAHARI AUTO and UI optimization notes

## AUTO tracking refinement in this patch

- Added a configurable exponential low-pass filter on image-space tracking errors (`error_filter_alpha`, default 0.35).
- AUTO control now feeds filtered errors into the Aimer, reducing response to frame-to-frame detector jitter.
- Lock tolerance checks use the filtered error, so the lock indication is less sensitive to small detection fluctuations.
- On target loss, the controller resets filter and PID state and commands a stop, avoiding stale derivative/filter state being carried into a reacquisition.
- The filter alpha is clamped to 0.05–1.0. Smaller values smooth more but add lag; larger values react faster but filter less.

## UI refinement in this patch

- Updated theme tokens to a restrained, higher-contrast engineering-console palette.
- Reduced glass/blur decoration and added consistent borders and panel surfaces.
- Tightened typography hierarchy and button/input treatment.
- Preserved the existing React component structure, API contract and operator controls.

## Before running AUTO on hardware

1. Keep the physical motor power cut accessible.
2. Verify camera and detector behavior in simulation first.
3. Verify axis direction/signs at low speeds with the camera mount clear.
4. Tune PID values conservatively; the default gains are not a guarantee of safe or stable movement for every assembly.
5. Validate target loss, camera disconnect, soft-limit behavior, emergency stop, and calibration on the actual assembly.
6. Use real physical safeguards; software limits are not substitutes for mechanical limit switches.

## Test status

- Control, safety and detector tests passed in the development run.
- The full suite had one failure in `tests/test_server.py`: the test expects `/api/telemetry` to return 401, but the current configured server is loopback-only, and the code intentionally bypasses token checks for loopback. This mismatch was not changed as part of the AUTO/UI patch.
- Frontend build was attempted but could not be completed because the local npm dependency install timed out and `vite/client` types were missing. Re-run `npm ci` and `npm run build` in `web/` on your machine.
