# Coordination Board

## Global Rules
- Sector3D must remain coreless axial-flux.
- Stator route is rigid PCB support + double-sided flat copper active conductors.
- Do not reuse iron-core assumptions.
- Do not commit AEDT runtime/generated outputs unless explicitly requested.

## Active Threads
| Thread | Branch | Owns | Status | Last Commit | Blockers |
|---|---|---|---|---|---|
| Integration | main | merge/review/coordination | active | current HEAD | no agent branch has unique commits to merge |
| Host Runtime | agent/host-runtime | host/queue/launchers | integrated | 0ab4a6a | no unique host-runtime commits pending in this Sector3D branch context |
| Sector3D Geometry | agent/sector3d-geometry | 3D geometry scaffold | active | pending local commit | rotating-band geometry is live-verified; latest local open/save-flow patch still needs a fresh in-AEDT rerun after host restart |
| Sector3D Solve | agent/sector3d-solve | excitation/setup/reports/solve | blocked | 8b31b49 | needs valid sector geometry; latest excitation artifact has no winding/current excitations assigned |
| Linear2D | agent/linear2d | 2D screening/ranking | waiting |  |  |
| DOE Ranking | agent/doe-ranking | search space/DOE/ranking | waiting |  |  |
| Docs Review | agent/docs-review | docs/contracts/review | waiting |  |  |

## Integration Review
- 2026-04-23: `git pull` and `git fetch --all --prune` found all local agent branches at `0ab4a6a` with no unique commits beyond `origin/main`.
- No merge performed this round because no agent branch had commits ahead of `main`.
- Physical constraint review found the active config still requires coreless axial-flux, rigid PCB support, double-sided flat copper active conductors, axial magnets, expanded air-region/fringing review, rotating band, and master/slave sector periodicity.
- Generated AEDT/report outputs remain untracked and must not be staged by integration: `reports/sector3d_model_build.md`, `reports/sector3d_excitation_assignment.md`, `templates/sector3d_template.aedt`, plus runtime/log/artifact/export/aedt project outputs.
- 2026-04-23 Sector3D Geometry: patched scaffold code to generate a 2-pole / 30-degree SSDR periodic-sector geometry instead of a full-annulus helper. Live AEDT rebuild wrote a pre-template-save `artifacts/sector3d_model_build.json` with `sector_geometry.geometry_scope = periodic_sector`.
- 2026-04-24 Sector3D Geometry: latest live build/apply artifacts show the Maxwell-compatible rotating band path is working end to end at the geometry/setup level: `artifacts/sector3d_model_build.json` recorded `motion_band_objects[0].role = rotating_band_double_rotor_container`, and `artifacts/sector3d_transient_setup.json` recorded `band_object_exists = true` and `motion_assigned = true`.
- 2026-04-24 Sector3D Geometry: latest local code patch removes the silent blank-project fallback for existing working `.aedt` files and stops queue builds from `SaveAs`-switching the active working project into the template path; this still needs one fresh host rerun after restart to verify the file-lock prompt is gone in practice.
