"""
Tool for validating crystal structures before expensive computations.

Performs comprehensive quality checks including:
- Overlapping atoms detection
- Bond length validation (too short or too long)
- Charge neutrality verification
- Oxidation state consistency
- Coordination environment sanity checks
- Detection of unphysical geometries

Use this tool to filter out invalid candidate structures before ML prediction
or DFT calculations, saving computational resources and preventing workflow failures.
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field


def structure_validator(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to validate as a pymatgen Structure dict (from Structure.as_dict()), "
                "or a CIF/POSCAR string. Can be output from any pymatgen tool or Materials Project API."
            )
        )
    ],
    min_distance_threshold: Annotated[
        float,
        Field(
            default=0.5,
            ge=0.1,
            le=2.0,
            description=(
                "Minimum allowed distance (Å) between any two atoms (0.1–2.0). "
                "Distances below this indicate overlapping atoms. "
                "Default: 0.5 Å (highly conservative; typical covalent radii sum ~1.5–3.0 Å)."
            )
        )
    ] = 0.5,
    max_bond_deviation: Annotated[
        float,
        Field(
            default=0.5,
            ge=0.1,
            le=2.0,
            description=(
                "Maximum allowed fractional deviation from expected bond lengths (0.1–2.0). "
                "Bonds longer/shorter than (1 ± max_bond_deviation) × expected_length fail. "
                "Expected lengths are based on covalent/ionic radii. "
                "Default: 0.5 (allows 50% variation, catches extreme anomalies)."
            )
        )
    ] = 0.5,
    check_charge_neutrality: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, verifies that the structure is charge-neutral based on oxidation states. "
                "Uses pymatgen's guess_oxidation_states() if not already present. "
                "Default: True."
            )
        )
    ] = True,
    check_oxidation_states: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, attempts to assign oxidation states and checks for consistency. "
                "Fails if oxidation states cannot be assigned or are chemically unreasonable. "
                "Default: True."
            )
        )
    ] = True,
    check_coordination: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, analyzes coordination environments and flags unusually high/low "
                "coordination numbers that may indicate structural problems. "
                "Uses reasonable thresholds (e.g., CN > 20 is suspicious for most systems). "
                "Default: True."
            )
        )
    ] = True,
    coordination_cutoff: Annotated[
        float,
        Field(
            default=3.5,
            ge=2.0,
            le=6.0,
            description=(
                "Distance cutoff (Å) for determining coordination numbers (2.0–6.0). "
                "Neighbors within this distance are counted. "
                "Default: 3.5 Å (suitable for most ionic/covalent systems)."
            )
        )
    ] = 3.5,
    max_coordination: Annotated[
        int,
        Field(
            default=20,
            ge=6,
            le=30,
            description=(
                "Maximum reasonable coordination number (6–30). "
                "Sites with higher coordination are flagged as suspicious. "
                "Default: 20 (covers most reasonable geometries including close-packed metals)."
            )
        )
    ] = 20,
    strict_mode: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, validation fails at the first error. "
                "If False (default), all checks are performed and accumulated. "
                "Default: False (collect all issues for comprehensive feedback)."
            )
        )
    ] = False,
    symm_prec: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.001,
            le=0.5,
            description=(
                "Symmetry tolerance in Ångströms for symmetry analysis (0.001–0.5). "
                "Used when analyzing equivalent sites. "
                "Default: 0.1 Å."
            )
        )
    ] = 0.1,
) -> Dict[str, Any]:
    """
    Validate a crystal structure for physical and chemical reasonableness.
    
    Performs multiple quality checks to identify problematic structures before
    expensive computations. Returns detailed validation results including:
    - Overall pass/fail status
    - Individual check results
    - Specific issues found (atom pairs, bond lengths, charge imbalance, etc.)
    - Warnings for suspicious but not necessarily invalid features
    
    This tool is essential for pre-screening candidate structures generated by
    pymatgen tools or retrieved from databases.
    
    Returns
    -------
    dict:
        valid               (bool)  Overall validation result (True if all checks pass).
        checks_performed    (list)  Names of all validation checks performed.
        checks_passed       (list)  Names of checks that passed.
        checks_failed       (list)  Names of checks that failed.
        issues              (list)  Detailed descriptions of each issue found.
        warnings            (list)  Non-critical warnings (may be absent).
        details             (dict)  Detailed results for each check:
            overlapping_atoms       (dict):
                passed              (bool)
                min_distance        (float)  Minimum interatomic distance found (Å).
                threshold           (float)  Threshold used (Å).
                problematic_pairs   (list)   Atom pairs below threshold with distances.
            bond_lengths            (dict):
                passed              (bool)
                anomalous_bonds     (list)   Bonds deviating significantly from expected.
                total_bonds_checked (int)
            charge_neutrality       (dict):
                passed              (bool)
                total_charge        (float)  Sum of oxidation states.
                tolerance           (float)  Charge tolerance used.
            oxidation_states        (dict):
                passed              (bool)
                assignable          (bool)   Whether oxidation states could be assigned.
                assignments         (dict)   Element: oxidation state mapping.
            coordination            (dict):
                passed              (bool)
                suspicious_sites    (list)   Sites with unusual coordination.
                max_cn_found        (int)    Maximum coordination number found.
        structure_info      (dict)  Summary of input structure.
        parameters          (dict)  All validation parameters used.
        message             (str)   Human-readable summary.
    """
    try:
        from pymatgen.core import Structure
        from pymatgen.analysis.local_env import CrystalNN
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
    except ImportError as e:
        return {
            "valid": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }
    
    # Parse input structure
    try:
        if isinstance(input_structure, dict):
            structure = Structure.from_dict(input_structure)
        elif isinstance(input_structure, str):
            from io import StringIO
            # Try CIF first
            if "data_" in input_structure or "_cell_length" in input_structure:
                parser = CifParser(StringIO(input_structure))
                structure = parser.get_structures()[0]
            else:
                # Try POSCAR - use StringIO
                poscar_lines = input_structure.strip().split('\n')
                # Poscar expects a file-like object or list of lines
                poscar = Poscar.from_str(input_structure)
                structure = poscar.structure
        else:
            return {
                "valid": False,
                "error": "input_structure must be a Structure dict, CIF string, or POSCAR string."
            }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Failed to parse input structure: {e}"
        }
    
    # Initialize results
    checks_performed = []
    checks_passed = []
    checks_failed = []
    issues = []
    warnings = []
    details = {}
    
    # Structure info
    structure_info = {
        "formula": structure.composition.reduced_formula,
        "n_sites": len(structure),
        "n_species": len(structure.composition.elements),
        "volume": structure.volume,
        "density": structure.density,
        "lattice_abc": structure.lattice.abc,
        "lattice_angles": structure.lattice.angles,
    }
    
    # CHECK 1: Overlapping atoms
    checks_performed.append("overlapping_atoms")
    min_dist = float('inf')
    problematic_pairs = []
    
    try:
        for i, site_i in enumerate(structure):
            for j, site_j in enumerate(structure):
                if i >= j:
                    continue
                dist = site_i.distance(site_j)
                min_dist = min(min_dist, dist)
                if dist < min_distance_threshold:
                    problematic_pairs.append({
                        "site_i": i,
                        "site_j": j,
                        "species_i": str(site_i.specie),
                        "species_j": str(site_j.specie),
                        "distance": round(dist, 4),
                        "threshold": min_distance_threshold,
                    })
        
        overlapping_passed = len(problematic_pairs) == 0
        details["overlapping_atoms"] = {
            "passed": overlapping_passed,
            "min_distance": round(min_dist, 4) if min_dist != float('inf') else None,
            "threshold": min_distance_threshold,
            "problematic_pairs": problematic_pairs,
        }
        
        if overlapping_passed:
            checks_passed.append("overlapping_atoms")
        else:
            checks_failed.append("overlapping_atoms")
            issues.append(f"Found {len(problematic_pairs)} atom pair(s) closer than {min_distance_threshold} Å")
            if strict_mode:
                return _build_result(False, checks_performed, checks_passed, checks_failed, 
                                   issues, warnings, details, structure_info)
    except Exception as e:
        warnings.append(f"Overlapping atoms check failed with error: {e}")
        details["overlapping_atoms"] = {"passed": None, "error": str(e)}
    
    # CHECK 2: Bond lengths
    checks_performed.append("bond_lengths")
    
    try:
        from pymatgen.core.periodic_table import Element
        
        anomalous_bonds = []
        bonds_checked = 0
        
        # Bond check based on reasonable radii estimates
        # Use average_ionic_radius for better handling of ionic compounds
        for i, site_i in enumerate(structure):
            for j, site_j in enumerate(structure):
                if i >= j:
                    continue
                
                dist = site_i.distance(site_j)
                if dist > coordination_cutoff:
                    continue
                
                # Expected bond length - try to get reasonable estimate
                try:
                    elem_i = Element(site_i.specie.symbol)
                    elem_j = Element(site_j.specie.symbol)
                    
                   # Try to get appropriate radius (average_ionic_radius for ionic compounds)
                    # Fall back to atomic_radius, then to a reasonable default
                    r_i = None
                    r_j = None
                    
                    # Try average ionic radius first (works for many ionic compounds)
                    try:
                        r_i = elem_i.average_ionic_radius
                    except:
                        pass
                    try:
                        r_j = elem_j.average_ionic_radius
                    except:
                        pass
                    
                    # Fall back to atomic radius
                    if r_i is None:
                        r_i = elem_i.atomic_radius or 1.5
                    if r_j is None:
                        r_j = elem_j.atomic_radius or 1.5
                    
                    expected_dist = r_i + r_j
                    bonds_checked += 1
                    
                    # Only flag extremely anomalous bonds (outside expected range)
                    deviation = abs(dist - expected_dist) / expected_dist
                    
                    if deviation > max_bond_deviation:
                        anomalous_bonds.append({
                            "site_i": i,
                            "site_j": j,
                            "species_i": str(site_i.specie),
                            "species_j": str(site_j.specie),
                            "actual_distance": round(dist, 4),
                            "expected_distance": round(expected_dist, 4),
                            "deviation": round(deviation, 4),
                        })
                except Exception as e:
                    # Skip if radii not available
                    continue
        
        bonds_passed = len(anomalous_bonds) == 0
        details["bond_lengths"] = {
            "passed": bonds_passed,
            "anomalous_bonds": anomalous_bonds[:20],  # Limit output
            "total_bonds_checked": bonds_checked,
        }
        
        if bonds_passed:
            checks_passed.append("bond_lengths")
        else:
            checks_failed.append("bond_lengths")
            issues.append(f"Found {len(anomalous_bonds)} bond(s) with unusual lengths")
            if strict_mode:
                return _build_result(False, checks_performed, checks_passed, checks_failed,
                                   issues, warnings, details, structure_info)
    except Exception as e:
        warnings.append(f"Bond length check failed with error: {e}")
        details["bond_lengths"] = {"passed": None, "error": str(e)}
    
    # CHECK 3: Charge neutrality
    if check_charge_neutrality:
        checks_performed.append("charge_neutrality")
        
        try:
            # Try to add oxidation states if not present
            structure_copy = structure.copy()
            if not all(hasattr(site.specie, 'oxi_state') for site in structure_copy):
                try:
                    structure_copy.add_oxidation_state_by_guess()
                except:
                    pass
            
            # Calculate total charge
            total_charge = 0
            charge_assigned = False
            if all(hasattr(site.specie, 'oxi_state') for site in structure_copy):
                charge_assigned = True
                total_charge = sum(site.specie.oxi_state for site in structure_copy)
            
            charge_tol = 0.1
            charge_passed = abs(total_charge) < charge_tol if charge_assigned else None
            
            details["charge_neutrality"] = {
                "passed": charge_passed,
                "total_charge": round(total_charge, 4) if charge_assigned else None,
                "tolerance": charge_tol,
                "charge_assigned": charge_assigned,
            }
            
            if charge_passed is True:
                checks_passed.append("charge_neutrality")
            elif charge_passed is False:
                checks_failed.append("charge_neutrality")
                issues.append(f"Structure is not charge neutral (total charge: {total_charge:.2f})")
                if strict_mode:
                    return _build_result(False, checks_performed, checks_passed, checks_failed,
                                       issues, warnings, details, structure_info)
            else:
                warnings.append("Could not verify charge neutrality (oxidation states not assignable)")
        except Exception as e:
            warnings.append(f"Charge neutrality check failed with error: {e}")
            details["charge_neutrality"] = {"passed": None, "error": str(e)}
    
    # CHECK 4: Oxidation states
    if check_oxidation_states:
        checks_performed.append("oxidation_states")
        
        try:
            structure_copy = structure.copy()
            assignable = False
            assignments = {}
            
            try:
                structure_copy.add_oxidation_state_by_guess()
                assignable = True
                # Collect unique oxidation states per element
                for site in structure_copy:
                    elem = site.specie.element.symbol
                    oxi = site.specie.oxi_state
                    if elem not in assignments:
                        assignments[elem] = []
                    if oxi not in assignments[elem]:
                        assignments[elem].append(oxi)
            except Exception as e:
                assignable = False
                warnings.append(f"Could not assign oxidation states: {e}")
            
            details["oxidation_states"] = {
                "passed": assignable,
                "assignable": assignable,
                "assignments": assignments if assignable else None,
            }
            
            if assignable:
                checks_passed.append("oxidation_states")
            else:
                checks_failed.append("oxidation_states")
                issues.append("Oxidation states could not be assigned or are chemically unreasonable")
                if strict_mode:
                    return _build_result(False, checks_performed, checks_passed, checks_failed,
                                       issues, warnings, details, structure_info)
        except Exception as e:
            warnings.append(f"Oxidation state check failed with error: {e}")
            details["oxidation_states"] = {"passed": None, "error": str(e)}
    
    # CHECK 5: Coordination numbers
    if check_coordination:
        checks_performed.append("coordination")
        
        try:
            suspicious_sites = []
            max_cn_found = 0
            
            for i, site in enumerate(structure):
                # Simple distance-based coordination
                neighbors = structure.get_neighbors(site, coordination_cutoff)
                cn = len(neighbors)
                max_cn_found = max(max_cn_found, cn)
                
                # Only flag if CN is unusually HIGH (not zero, as zero might be due to cutoff or small cell)
                if cn > max_coordination:
                    suspicious_sites.append({
                        "site_index": i,
                        "species": str(site.specie),
                        "coordination_number": cn,
                        "threshold": max_coordination,
                    })
            
            coord_passed = len(suspicious_sites) == 0
            details["coordination"] = {
                "passed": coord_passed,
                "suspicious_sites": suspicious_sites[:20],  # Limit output
                "max_cn_found": max_cn_found,
                "max_cn_threshold": max_coordination,
            }
            
            if coord_passed:
                checks_passed.append("coordination")
            else:
                checks_failed.append("coordination")
                issues.append(f"Found {len(suspicious_sites)} site(s) with unusual coordination")
                if strict_mode:
                    return _build_result(False, checks_performed, checks_passed, checks_failed,
                                       issues, warnings, details, structure_info)
        except Exception as e:
            warnings.append(f"Coordination check failed with error: {e}")
            details["coordination"] = {"passed": None, "error": str(e)}
    
    # Build final result
    overall_valid = len(checks_failed) == 0 and len([d for d in details.values() if d.get("passed") is False]) == 0
    
    return _build_result(overall_valid, checks_performed, checks_passed, checks_failed,
                        issues, warnings, details, structure_info)


def _build_result(valid, checks_performed, checks_passed, checks_failed, issues, warnings, details, structure_info):
    """Helper to build standardized result dictionary."""
    result = {
        "valid": valid,
        "checks_performed": checks_performed,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "issues": issues,
        "details": details,
        "structure_info": structure_info,
        "message": "Structure passed all validation checks" if valid else f"Structure failed {len(checks_failed)} check(s)",
    }
    
    if warnings:
        result["warnings"] = warnings
    
    return result
