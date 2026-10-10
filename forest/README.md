# FOREST: public showcase and VPS monitor

- GitHub Pages `/forest/`: `index.html`, `css/showcase.css`, `js/showcase.js`. Public project introduction and an isolated, in-memory simulation. No operational API requests or saved mission changes.
- VPS web root `/`: nginx serves `monitor.html`. `js/monitor-entry.js` checks the same-origin `/api/health` before loading the existing application. GitHub Pages hosts are explicitly blocked from loading this operational app.
- Existing `app.js`, `store.js`, weather, observation history and app styles remain the operational frontend. Telemetry and forest images are currently demonstration data; API connectivity does not imply a connected physical drone.
- Start/reload the existing Docker web service after updating `nginx/default.conf`. Keep existing localhost port bindings and access controls. The frontend health gate is not authentication; protect operational access separately.
- The public simulation uses fixed values (54% to 92%, 15m to 8m), not measured model performance. Jetson/ROS 2/PX4 integration and field validation are planned.

Static preview: serve this repository and open `/forest/`. All showcase assets use relative URLs and work under GitHub Pages repository paths. No external map API or build step is required.
