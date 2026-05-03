# DXF Copper MVP Preflight

Date: 2026-05-03

## Scope

Active roadmap node: `Milestone 2: DXF-Compatible 3D Copper MVP`.

This preflight checks whether the repository and local AEDT/PyAEDT environment are ready to start V1 implementation. It does not build copper geometry and does not modify the legacy Sector3D phase-belt scaffold.

## Result

Status: `ready_with_constraints`

V1 can start with the `polyline_points` 2D-to-3D handshake. Final DXF import/export should wait until `ezdxf` is installed or a native AEDT DXF path is explicitly proven.

## Python Environment

- Default `python`: not usable. It resolves to `C:\Users\fjcy\AppData\Local\Microsoft\WindowsApps\python.exe` and fails with a WindowsApps access error.
- PyAEDT environment Python: `C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe`.
- Shapely: available, version `2.1.2`.
- ezdxf: not installed.
- ansys.aedt.core: available, version `0.26.2`.

Implication:

- Use the PyAEDT environment Python for tests and scripts unless a stable project-local Python is configured later.
- V1 pure geometry can use Shapely now.
- V1 should not require DXF export/import yet. Use `aedt_handshake_mode = "polyline_points"`.

## Local PyAEDT API Findings

Findings came from local source under:

`C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Lib\site-packages\ansys\aedt\core`

### 2D-To-3D Geometry

Available:

- `modeler.create_polyline(points, ..., cover_surface=False, close_surface=False, name=None, material=None, ...)`
- `modeler.thicken_sheet(assignment, thickness, both_sides=False)`

Relevant local source:

- `modeler\cad\primitives.py:7068` defines `create_polyline`.
- `modeler\cad\primitives.py:3200` defines `thicken_sheet`.

Recommended V1 path:

1. Generate 2D polygon points from Shapely output.
2. Create an AEDT closed covered sheet with `create_polyline(..., cover_surface=True, close_surface=True)`.
3. Thicken the sheet with `thicken_sheet(..., "0.3mm", both_sides=False)`.
4. Assign copper material after creation or during object creation if supported by the returned object path.

Do not rebuild the copper outline with AEDT booleans.

### Mesh Defense

Available:

- `mesh.assign_length_mesh(assignment, inside_selection=True, maximum_length=..., maximum_elements=..., name=...)`

Relevant local source:

- `modules\mesh.py:1095` defines `assign_length_mesh`.

Recommended V1 path:

- Assign a length mesh operation to the thickened copper object.
- Start with a conservative max length tied to copper thickness, such as `0.15mm` to `0.30mm`, then adjust after the first AEDT mesh attempt.
- Treat missing mesh assignment as a blocking field for `dxf_compatible_copper_ready`.

### DC Conduction

Available:

- `Maxwell3d(solution_type="DC Conduction")`
- `SolutionsMaxwell3D.DCConduction` resolves to `DC Conduction`.
- `create_setup(name="...", setup_type=None, **kwargs)` is available.
- `assign_voltage(assignment, amplitude=..., name=...)` is available.
- `assign_sink(assignment, name=...)` is available for 3D `DCConduction`, `ElectroDCConduction`, `ACConduction`, and `ElectricTransient`.

Relevant local source:

- `generic\aedt_constants.py:469` defines `DCConduction`.
- `generic\aedt_constants.py:476` defines `DC Conduction`.
- `modules\setup_templates.py:216` defines Maxwell `DCConduction` setup defaults.
- `maxwell.py:1084` defines `assign_voltage`.
- `maxwell.py:3737` defines `assign_sink`.

Recommended V1 DC sanity path:

1. Use a Maxwell 3D design with solution type `DC Conduction`.
2. Assign one terminal face with `assign_voltage(..., amplitude=1000, name="AutoDxfCopper_Voltage")`.
3. Assign the return face with `assign_sink(..., name="AutoDxfCopper_Sink")`.
4. Create a setup with `create_setup(name="AutoDxfCopper_DC")`.
5. Report current density continuity after solve.

Note: `assign_voltage` numeric amplitude is converted to millivolts in PyAEDT, so `1000` means `1000mV`. Use explicit strings if this becomes ambiguous.

## Open API Questions For First AEDT Run

- Exact face identification for terminal pads after `thicken_sheet` must be verified in AEDT. The V1 geometry should include terminal metadata that helps identify expected face centers or bounding boxes.
- Current density report expression names should be confirmed in AEDT after the first DC Conduction setup is created.
- Native DXF import/export is not proven by this preflight. Keep DXF export out of V1 blocking criteria until `ezdxf` or a native AEDT DXF route is validated.

## Blocking Issues

- Default `python` command is not usable. Use the PyAEDT environment Python path explicitly.
- `ezdxf` is not installed. This does not block V1 if `polyline_points` is used, but it blocks any claim of DXF export readiness.

## Non-Blocking Notes

- Shapely is available and suitable for V1 pure 2D geometry checks.
- PyAEDT contains the necessary public methods for the first sheet/thicken/mesh/DC Conduction attempt.
- Host/runtime can remain the execution transport.

## Recommended Next Step

Start Task 2 from `docs/superpowers/plans/2026-05-03-dxf-copper-mvp-prep.md`:

1. Create `tests/test_dxf_copper_geometry.py`.
2. Implement `scripts/dxf_copper_geometry.py` with the V1 contract skeleton.
3. Run tests with:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_geometry -v
```

