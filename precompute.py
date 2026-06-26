from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

# Allow running against a local OpenMC source tree without pip install.
_REPO = Path.home() / "openmc"
if _REPO.is_dir() and str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO / "openmc"))
    sys.path.insert(0, str(_REPO))

import openmc  # noqa: E402


# Row strings only (auto-centered in the 15-column lattice).
CORE_ROWS = [
    "fffffffff",
    "frfrfrfrfrf",
    "fffffffffffff",
    "frfrfrfrfrfrfrf",
    "fffffffffffffff",
    "frfrfrfrfrfrfrf",
    "fffffffffffffff",
    "frfrfrfrfrfrfrf",
    "fffffffffffffff",
    "frfrfrfrfrfrfrf",
    "fffffffffffffff",
    "frfrfrfrfrfrfrf",
    "fffffffffffff",
    "frfrfrfrfrf",
    "fffffffff",
]


@dataclass(frozen=True)
class SimConfig:
    n_insertion_steps: int = 5
    pitch_cm: float = 1.26
    active_height_cm: float = 200.0
    fuel_radius_cm: float = 0.392
    rod_radius_cm: float = 0.45
    u235_enrichment: float = 0.045
    batches: int = 40
    inactive: int = 10
    particles: int = 5000
    perturbation: float = 1.0e-4
    all_fuel_sources: bool = False
    cr_filter: tuple[int, int] | None = None
    output: Path = Path("fission_coupling_table.csv")
    work_dir: Path = Path("openmc_run")
    seed: int = 42


def parse_core_map(rows: list[str]) -> tuple[np.ndarray, int, int]:
    """Return (grid, n_rows, n_cols) with entries 'f', 'r', or None."""
    width = max(len(row) for row in rows)
    n_rows = len(rows)
    grid = np.full((n_rows, width), None, dtype=object)
    for row_idx, body in enumerate(rows):
        offset = (width - len(body)) // 2
        for col, ch in enumerate(body):
            if ch not in ("f", "r"):
                raise ValueError(f"Invalid character {ch!r} at row {row_idx}, col {col}")
            grid[row_idx, offset + col] = ch
    return grid, n_rows, width


def iter_neighbors_5x5(row: int, col: int, n_rows: int, n_cols: int) -> Iterator[tuple[int, int]]:
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            rr, cc = row + dr, col + dc
            if 0 <= rr < n_rows and 0 <= cc < n_cols:
                yield rr, cc


def active_cells(grid: np.ndarray) -> list[tuple[int, int, str]]:
    return [
        (r, c, grid[r, c])
        for r in range(grid.shape[0])
        for c in range(grid.shape[1])
        if grid[r, c] is not None
    ]


def make_materials(cfg: SimConfig) -> openmc.Materials:
    fuel = openmc.Material(name="UO2 fuel")
    fuel.set_density("g/cm3", 10.4)
    fuel.add_element("U", 1.0, enrichment=cfg.u235_enrichment)
    fuel.add_element("O", 2.0)
    fuel.temperature = 900.0

    water = openmc.Material(name="Water")
    water.set_density("g/cm3", 0.7)
    water.add_element("H", 2.0)
    water.add_element("O", 1.0)
    water.add_s_alpha_beta("c_H_in_H2O")
    water.temperature = 600.0

    b4c = openmc.Material(name="B4C absorber")
    b4c.set_density("g/cm3", 2.52)
    b4c.add_element("B", 4.0)
    b4c.add_element("C", 1.0)
    b4c.temperature = 600.0

    return openmc.Materials([fuel, water, b4c])


def pin_center(row: int, col: int, n_rows: int, pitch: float) -> tuple[float, float]:
    """Return (x, y) pin center for grid indices (row 0 = top of core map)."""
    x = (col + 0.5) * pitch
    # OpenMC RectLattice: index 0 is the top (largest y) row.
    y = (n_rows - row - 0.5) * pitch
    return x, y


def mesh_index(row: int, col: int, n_rows: int, n_cols: int) -> int:
    """Map grid indices to raveled mesh tally (row 0 = top)."""
    mesh_row = n_rows - 1 - row
    return mesh_row * n_cols + col


def make_fuel_sources(
    grid: np.ndarray,
    cfg: SimConfig,
    pitch: float,
    z0: float,
    z1: float,
) -> list[openmc.IndependentSource]:
    """Point sources at fuel-pin centers (one per fuel lattice cell)."""
    n_rows, _ = grid.shape
    z_mid = 0.5 * (z0 + z1)
    sources: list[openmc.IndependentSource] = []
    for row, col, kind in active_cells(grid):
        if kind != "f":
            continue
        x, y = pin_center(row, col, n_rows, pitch)
        # Slight epsilon to avoid landing exactly on boundaries
        eps = 1.0e-6
        sources.append(
            openmc.IndependentSource(
                space=openmc.stats.Point((x + eps, y + eps, z_mid))
            )
        )
    if not sources:
        raise RuntimeError("No fuel pins found for initial source definition")
    return sources


def make_pin_universe(
    uid: int,
    kind: str,
    cfg: SimConfig,
    fuel_mat: openmc.Material,
    water_mat: openmc.Material,
    absorber_mat: openmc.Material,
    insertion_fraction: float,
    z0_plane: openmc.ZPlane,
    z1_plane: openmc.ZPlane,
) -> openmc.Universe:
    fuel_or_rod = openmc.ZCylinder(r=cfg.fuel_radius_cm if kind == "f" else cfg.rod_radius_cm)
    z_bounds = +z0_plane & -z1_plane

    cells = []

    if kind == "f":
        # Fuel region
        fuel_cell = openmc.Cell(fill=fuel_mat)
        fuel_cell.region = -fuel_or_rod & z_bounds
        cells.append(fuel_cell)

        # Moderator fills everything out to the edge of the lattice cell
        mod_cell = openmc.Cell(fill=water_mat)
        mod_cell.region = +fuel_or_rod & z_bounds
        cells.append(mod_cell)

    else:
        # Control rod channel: axial insertion (0 = fully withdrawn/water, 1 = fully inserted/B4C).
        frac = float(np.clip(insertion_fraction, 0.0, 1.0))
        z0 = z0_plane.z0
        z1 = z1_plane.z0
        z_insert = z0 + frac * (z1 - z0)

        if frac <= 0.0:
            rod_cell = openmc.Cell(fill=water_mat)
            rod_cell.region = -fuel_or_rod & z_bounds
            cells.append(rod_cell)
        elif frac >= 1.0:
            rod_cell = openmc.Cell(fill=absorber_mat)
            rod_cell.region = -fuel_or_rod & z_bounds
            cells.append(rod_cell)
        else:
            inserted = openmc.Cell(fill=absorber_mat)
            inserted.region = -fuel_or_rod & +z0_plane & -openmc.ZPlane(z0=z_insert)
            withdrawn = openmc.Cell(fill=water_mat)
            withdrawn.region = -fuel_or_rod & +openmc.ZPlane(z0=z_insert) & -z1_plane
            cells.extend([inserted, withdrawn])

        # Moderator fills everything out to the edge of the lattice cell
        mod_cell = openmc.Cell(fill=water_mat)
        mod_cell.region = +fuel_or_rod & z_bounds
        cells.append(mod_cell)

    root = openmc.Universe(universe_id=uid, cells=cells)

    # Keep fuel_cell handle for perturbation logic
    if kind == "f":
        root.fuel_cell = fuel_cell  # type: ignore[attr-defined]

    return root


def _first_cell(univ: openmc.Universe) -> openmc.Cell:
    return next(iter(univ.cells.values()))


def _walk_universes(univ: openmc.Universe) -> Iterator[openmc.Universe]:
    yield univ
    for cell in univ.cells.values():
        fill = cell.fill
        if isinstance(fill, openmc.Universe):
            yield from _walk_universes(fill)
        elif isinstance(fill, openmc.Lattice):
            for row in fill.universes:
                for u in row:
                    if u is not None:
                        yield from _walk_universes(u)


def build_model(
    grid: np.ndarray,
    cfg: SimConfig,
    cr_insertions: dict[tuple[int, int], float],
) -> openmc.Model:
    """Build OpenMC model; cr_insertions maps (row,col) -> fraction inserted."""
    # FIX: Clear the ID registry for clean loop iterations
    openmc.reset_auto_ids()

    n_rows, n_cols = grid.shape
    pitch = cfg.pitch_cm

    mats = make_materials(cfg)
    fuel_mat, water_mat, b4c_mat = mats[0], mats[1], mats[2]

    # Instantiate the axial planes ONCE to avoid coincident tracking artifacts
    z0 = -0.5 * cfg.active_height_cm
    z1 = 0.5 * cfg.active_height_cm
    z0_plane = openmc.ZPlane(z0=z0)
    z1_plane = openmc.ZPlane(z0=z1)

    universes: list[list[openmc.Universe | None]] = [[None] * n_cols for _ in range(n_rows)]
    uid = 1000
    pin_meta: dict[tuple[int, int], dict] = {}

    for r, c, kind in active_cells(grid):
        insertion = cr_insertions.get((r, c), 0.0) if kind == "r" else 0.0
        univ = make_pin_universe(uid, kind, cfg, fuel_mat, water_mat, b4c_mat, insertion, z0_plane, z1_plane)
        universes[r][c] = univ
        pin_meta[(r, c)] = {
            "kind": kind,
            "uid": uid,
            "fuel_mat_id": fuel_mat.id if kind == "f" else None,
        }
        uid += 1

    # Outside core: water-filled pin cells for boundary moderation.
    for r in range(n_rows):
        for c in range(n_cols):
            if universes[r][c] is None:
                uid += 1
                dummy = make_pin_universe(uid, "f", cfg, fuel_mat, water_mat, b4c_mat, 0.0, z0_plane, z1_plane)
                _first_cell(dummy).fill = water_mat
                universes[r][c] = dummy

    ll_x = 0.0
    ll_y = 0.0
    lattice = openmc.RectLattice(name="Core lattice")
    lattice.lower_left = (ll_x, ll_y)
    lattice.pitch = (pitch, pitch)
    lattice.universes = universes

    # Explicit box from (0,0) to (n_cols*pitch, n_rows*pitch) to match lattice and mesh
    x_min = 0.0
    x_max = n_cols * pitch
    y_min = 0.0
    y_max = n_rows * pitch

    x0 = openmc.XPlane(x0=x_min, boundary_type="vacuum")
    x1 = openmc.XPlane(x0=x_max, boundary_type="vacuum")
    y0 = openmc.YPlane(y0=y_min, boundary_type="vacuum")
    y1 = openmc.YPlane(y0=y_max, boundary_type="vacuum")
    
    # Configure shared global planes as vacuum boundaries
    z0_plane.boundary_type = "vacuum"
    z1_plane.boundary_type = "vacuum"

    core_cell = openmc.Cell(name="Core", fill=lattice)
    core_cell.region = +x0 & -x1 & +y0 & -y1 & +z0_plane & -z1_plane

    root = openmc.Universe(cells=[core_cell])
    geometry = openmc.Geometry(root)

    settings = openmc.Settings()
    settings.run_mode = "eigenvalue"
    settings.batches = cfg.batches
    settings.inactive = cfg.inactive
    settings.particles = cfg.particles
    settings.seed = cfg.seed
    settings.source = make_fuel_sources(grid, cfg, pitch, z0, z1)

    mesh = openmc.RegularMesh(name="Pin fission mesh")
    mesh.dimension = (n_cols, n_rows)
    mesh.lower_left = (ll_x, ll_y)
    mesh.upper_right = (n_cols * pitch, n_rows * pitch)
    mesh_filter = openmc.MeshFilter(mesh)

    tally = openmc.Tally(name="Pin fission rates")
    tally.filters = [mesh_filter]
    tally.scores = ["fission"]

    model = openmc.Model(
        geometry=geometry,
        settings=settings,
        materials=mats,
        tallies=openmc.Tallies([tally]),
    )
    model._pin_meta = pin_meta  # type: ignore[attr-defined]
    model._fuel_mat = fuel_mat  # type: ignore[attr-defined]
    model._grid = grid  # type: ignore[attr-defined]
    return model


def run_fission_rates(model: openmc.Model, work_dir: Path) -> np.ndarray:
    work_dir.mkdir(parents=True, exist_ok=True)
    prev = Path.cwd()
    os.chdir(work_dir)
    try:
        statepoint = model.run(output=True)
        with openmc.StatePoint(statepoint) as sp:
            t = sp.get_tally(name="Pin fission rates")
            rates = t.get_slice(scores=["fission"]).mean.ravel()
            return rates.copy()
    finally:
        os.chdir(prev)

def apply_source_perturbation(model: openmc.Model, row: int, col: int, eps: float) -> None:
    """Increase nu-fission in one fuel pin by a relative amount eps."""
    meta = model._pin_meta[(row, col)]  # type: ignore[attr-defined]
    if meta["kind"] != "f":
        return
    univ = None
    for u in _walk_universes(model.geometry.root_universe):
        if u.id == meta["uid"]:
            univ = u
            break
    if univ is None:
        raise RuntimeError(f"Universe {meta['uid']} not found")
    fuel_cell = getattr(univ, "fuel_cell", _first_cell(univ))
    mat = fuel_cell.fill
    if not isinstance(mat, openmc.Material):
        raise RuntimeError("Expected material fill in fuel cell")
        
    clone = mat.clone()
    clone.name = f"{mat.name} perturbed"
    
    nuclides_to_add = []
    for nuclide in clone.nuclides:
        new_percent = nuclide.percent * (1.0 + eps)
        nuclides_to_add.append((nuclide.name, new_percent, nuclide.percent_type))
        
    clone._nuclides = []
    for name, percent, percent_type in nuclides_to_add:
        clone.add_nuclide(name, percent, percent_type=percent_type)
        
    fuel_cell.fill = clone
    
    # FIX: Register the new material with the model
    model.materials.append(clone)

def fuel_pins_in_5x5(grid: np.ndarray, row: int, col: int) -> list[tuple[int, int]]:
    return [
        (r, c)
        for r, c in iter_neighbors_5x5(row, col, *grid.shape)
        if grid[r, c] == "f"
    ]


def compute_coupling_table(cfg: SimConfig) -> Path:
    if not os.environ.get("OPENMC_CROSS_SECTIONS"):
        raise EnvironmentError(
            "Set OPENMC_CROSS_SECTIONS to your cross_sections.xml before running.\n"
            "Example:\n"
            "  export OPENMC_CROSS_SECTIONS=/path/to/cross_sections.xml"
        )

    grid, n_rows, n_cols = parse_core_map(CORE_ROWS)
    fuel_pins = [(r, c) for r, c, k in active_cells(grid) if k == "f"]
    cr_pins = [(r, c) for r, c, k in active_cells(grid) if k == "r"]
    if cfg.cr_filter is not None:
        if cfg.cr_filter not in cr_pins:
            raise ValueError(f"Control rod {cfg.cr_filter} not found in core map")
        cr_pins = [cfg.cr_filter]

    cfg.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cr_row",
        "cr_col",
        "cr_insertion_step",
        "cr_insertion_fraction",
        "source_row",
        "source_col",
        "dest_row",
        "dest_col",
        "delta_fission_rate_per_one_fission_per_s",
    ]

    with cfg.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for cr_row, cr_col in cr_pins:
            source_pins = fuel_pins if cfg.all_fuel_sources else fuel_pins_in_5x5(grid, cr_row, cr_col)
            for step in range(cfg.n_insertion_steps + 1):
                fraction = step / cfg.n_insertion_steps if cfg.n_insertion_steps else 0.0
                insertions = {(cr_row, cr_col): fraction}

                model = build_model(grid, cfg, insertions)
                baseline = run_fission_rates(model, cfg.work_dir / f"cr_{cr_row}_{cr_col}_step_{step}")

                for src_r, src_c in source_pins:
                    pert_model = build_model(grid, cfg, insertions)
                    apply_source_perturbation(pert_model, src_r, src_c, cfg.perturbation)
                    perturbed = run_fission_rates(
                        pert_model,
                        cfg.work_dir / f"cr_{cr_row}_{cr_col}_step_{step}_src_{src_r}_{src_c}",
                    )

                    delta_src = (
                        perturbed[mesh_index(src_r, src_c, n_rows, n_cols)]
                        - baseline[mesh_index(src_r, src_c, n_rows, n_cols)]
                    )
                    if abs(delta_src) < 1.0e-30:
                        continue
                    scale = 1.0 / delta_src

                    for dst_r, dst_c in iter_neighbors_5x5(src_r, src_c, n_rows, n_cols):
                        if grid[dst_r, dst_c] is None:
                            continue
                        idx = mesh_index(dst_r, dst_c, n_rows, n_cols)
                        delta = (perturbed[idx] - baseline[idx]) * scale
                        writer.writerow(
                            {
                                "cr_row": cr_row,
                                "cr_col": cr_col,
                                "cr_insertion_step": step,
                                "cr_insertion_fraction": fraction,
                                "source_row": src_r,
                                "source_col": src_c,
                                "dest_row": dst_r,
                                "dest_col": dst_c,
                                "delta_fission_rate_per_one_fission_per_s": delta,
                            }
                        )

    return cfg.output


def parse_args(argv: list[str] | None = None) -> SimConfig:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "-n",
        "--n-steps",
        type=int,
        default=5,
        help="Number of discrete control-rod insertion steps (0..n)",
    )
    p.add_argument("--batches", type=int, default=40)
    p.add_argument("--inactive", type=int, default=10)
    p.add_argument("--particles", type=int, default=5000)
    p.add_argument(
        "--perturbation",
        type=float,
        default=1.0e-4,
        help="Relative nu-fission increase used for finite-difference sensitivity",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("fission_coupling_table.csv"),
        help="Output CSV path",
    )
    p.add_argument(
        "--work-dir",
        type=Path,
        default=Path("openmc_run"),
        help="Directory for OpenMC XML/statepoint files",
    )
    p.add_argument(
        "--all-fuel-sources",
        action="store_true",
        help="Perturb every fuel pin in the core (default: only fuel pins in 5x5 around each CR)",
    )
    p.add_argument(
        "--cr",
        nargs=2,
        type=int,
        metavar=("ROW", "COL"),
        help="Run only for one control rod lattice position",
    )
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    return SimConfig(
        n_insertion_steps=args.n_steps,
        batches=args.batches,
        inactive=args.inactive,
        particles=args.particles,
        perturbation=args.perturbation,
        all_fuel_sources=args.all_fuel_sources,
        cr_filter=tuple(args.cr) if args.cr else None,
        output=args.output,
        work_dir=args.work_dir,
        seed=args.seed,
    )


def main() -> None:
    cfg = parse_args()
    out = compute_coupling_table(cfg)
    print(f"Wrote coupling table to {out.resolve()}")


if __name__ == "__main__":
    main()
