# vendorfiles/

This directory contains **versioned, vendored copies** of third-party frontend
libraries and assets used by Chesser.

These files are **not served directly** by the application. Instead, selected
files are copied into `static/` as stable, active versions that Django serves
via WhiteNoise.

## Purpose

The goals of `vendorfiles/` are:

- reproducibility (exact upstream versions are pinned)
- auditability (upgrades are explicit and reversible)
- minimal frontend tooling (no npm or bundler at runtime)

Each subdirectory typically corresponds to a specific upstream version of a
dependency.

## Updating dependencies

Vendored dependencies should not be edited manually.

To update or refresh vendored files, use:

```sh
bin/update-vendor.sh
```

This script fetches pinned versions from upstream sources and updates the
corresponding files in both `vendorfiles/` and `static/`.

## Notes

- `static/` contains the **currently active** copies used by the app.
- `vendorfiles/` exists primarily for reference and controlled upgrades.
