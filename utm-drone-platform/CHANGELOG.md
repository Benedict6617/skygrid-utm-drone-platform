# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - Initial release

### Added
- Operator registration/authentication (JWT).
- Drone fleet registration and status management.
- Flight plan submission and full pre-flight review pipeline (LAANC, geofencing, weather, strategic deconfliction, ATC coordination).
- Dynamic geofencing: polygon and circular TFRs/restricted areas with altitude and time-window scoping.
- Strategic (pre-flight) and tactical (in-flight, DAA-driven) deconfliction engine.
- Automatic emergency landing zone assignment on battery-critical, lost-link, or critical DAA conditions.
- Weather service integration with configurable go/no-go safety thresholds.
- Traditional ATC coordination detection and message logging for near-airport operations.
- Mock implementations of all three external integrations (LAANC, weather, ATC) so the platform runs fully offline for development and demos.
- Realistic sample dataset: three operator businesses, six drones, four reference airports, five geofences, six emergency landing zones, and six sample flight plans.
- Docker and docker-compose setup.
- Pytest suite covering geo utilities, LAANC mock behavior, deconfliction logic, geofence checking, emergency zone selection, and end-to-end API flows.
