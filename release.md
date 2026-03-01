# Release 0.2.3

## Added
- **Browserless:** Replaced `BROWSERLESS_LAUNCH_OPTS_BASE64` with individual, human-readable environment variables for easier configuration.
- **CI:** Added frontend Biome lint/format checks and Dependabot support for GitHub Actions dependencies.

## Changed
- **Dependencies:** Updated frontend dependencies — React 18 → 19, react-router-dom 6 → 7, @vitejs/plugin-react 4 → 5.

## Fixed
- **CI:** Simplified CI workflow, fixed linting issues, and added automated dependency update configuration.
- **Browserless:** Improved startup timeout handling for more reliable browser connections.

