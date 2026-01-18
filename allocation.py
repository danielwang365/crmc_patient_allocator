"""
Patient allocation algorithm for the Patient Allocator application.
Implements the original Streamlit allocation strategy.
"""

from models import Physician


def allocate_patients(
    physicians: list[Physician],
    n_total_new_patients: int,
    n_A_new_patients: int,
    n_B_new_patients: int,
    n_N_new_patients: int,
    new_start_number: int,
    minimum_patients: int = 10,
    n_step_down_patients: int = 0,
    maximum_patients: int = 1000
):
    """
    Allocate patients to physicians using the original Streamlit algorithm.

    Algorithm Flow:
    1. Calculate total patients to distribute
    2. Sort all working physicians by total patients (low to high)
    3. Allocate to new physicians until they reach new_start_number
    4. Round-robin distribution to non-new physicians
    5. Step-down allocation (AFTER regular) using Gained+Traded formula
    6. Final verification for new physicians
    7. Minimum patients check with redistribution

    Returns a dictionary with results and summary statistics.
    """
    # Store initial patient counts for even distribution later
    initial_counts = {p.name: p.total_patients for p in physicians}

    # Store initial pool sizes for tracking
    initial_A_pool = n_A_new_patients
    initial_B_pool = n_B_new_patients
    initial_N_pool = n_N_new_patients

    # Make team lists
    team_A = [p for p in physicians if p.team == 'A']
    team_B = [p for p in physicians if p.team == 'B']
    team_N = [p for p in physicians if p.team == 'N']

    # Helper function to check if physician can take more patients
    def can_take_patient(physician):
        return physician.total_patients < maximum_patients

    # Store initial stepdown counts for gained calculation
    initial_stepdown_counts = {p.name: p.step_down_patients for p in physicians}

    # Helper function to check if physician can take a step down patient
    # Only limit the gained stepdown to 1, not the total stepdown
    def can_take_step_down(physician):
        initial_sd = initial_stepdown_counts.get(physician.name, 0)
        gained_stepdown = physician.step_down_patients - initial_sd
        return gained_stepdown < 1

    # ========== ALLOCATION LOGIC ==========
    # Step 1: Calculate total patients to distribute
    total_to_distribute = n_A_new_patients + n_B_new_patients + n_N_new_patients + n_step_down_patients

    # Step 2: Get all working physicians and sort by total patients (low to high)
    all_working = [p for p in physicians if p.is_working]
    all_working.sort(key=lambda x: x.total_patients)

    remaining = total_to_distribute

    # Step 3: Allocate to new physicians until they reach new_start_number
    new_physicians = [p for p in all_working if p.is_new]
    for physician in new_physicians:
        if physician.total_patients >= new_start_number:
            continue
        needed = new_start_number - physician.total_patients
        to_give = min(needed, remaining)
        for _ in range(to_give):
            physician.add_patient()
            remaining -= 1

    # Step 4: Get non-new physicians for general distribution
    non_new = [p for p in all_working if not p.is_new]
    num_non_new = len(non_new)

    # Track allocation order for minimum check function
    allocation_order = []

    if remaining > 0 and num_non_new > 0:
        # Round-robin: while remaining >= num_non_new, give +1 to ALL non-new physicians
        while remaining >= num_non_new:
            for physician in non_new:
                if can_take_patient(physician):
                    physician.add_patient()
                    remaining -= 1
                    allocation_order.append(physician)

        # Now remaining < num_non_new
        # Give remaining to physicians with lowest totals (for even distribution)
        if remaining > 0:
            non_new.sort(key=lambda x: x.total_patients)
            for physician in non_new:
                if remaining <= 0:
                    break
                if can_take_patient(physician):
                    physician.add_patient()
                    remaining -= 1
                    allocation_order.append(physician)

    # ========== STEP-DOWN ALLOCATION ==========
    # Step 1: Calculate "Gained + Traded" for each team (after regular allocation)
    # Step 2: Calculate trades between teams
    # Step 3: StepDown for Team A = (Gained + Traded for Team A) - (Traded B→A + Team A Pool)
    # Step 4: Remaining StepDown goes to Team B and Team N
    # Step 5: Allocate to physicians with lowest stepdown count (max 1 per physician)

    # Filter to only working physicians
    working_team_A = [p for p in team_A if p.is_working]
    working_team_B = [p for p in team_B if p.is_working]
    working_team_N = [p for p in team_N if p.is_working]

    # Calculate gained for each physician (current total - initial total)
    team_A_gained = sum(p.total_patients - initial_counts.get(p.name, p.total_patients) for p in working_team_A)
    team_B_gained = sum(p.total_patients - initial_counts.get(p.name, p.total_patients) for p in working_team_B)

    # Calculate traded patients
    traded_A_to_B = sum(p.traded_patients for p in working_team_B)  # B received from A
    traded_B_to_A = sum(p.traded_patients for p in working_team_A)  # A received from B

    # Total "Gained + Traded" for each team
    team_A_gained_plus_traded = team_A_gained + traded_B_to_A
    team_B_gained_plus_traded = team_B_gained + traded_A_to_B

    # Calculate how many step-down patients Team A should get
    # StepDown for Team A = (Gained + Traded for Team A) - (Traded B→A + Team A Pool)
    stepdown_for_A = team_A_gained_plus_traded - (traded_B_to_A + n_A_new_patients)
    stepdown_for_A = max(0, min(stepdown_for_A, n_step_down_patients))

    # Remaining goes to Team B and Team N
    stepdown_for_B_and_N = n_step_down_patients - stepdown_for_A

    # Allocate step-down to Team A (sorted by lowest stepdown count)
    team_A_sorted = sorted(working_team_A, key=lambda x: initial_stepdown_counts.get(x.name, x.step_down_patients))
    remaining_A = stepdown_for_A

    for physician in team_A_sorted:
        if remaining_A <= 0:
            break
        if can_take_step_down(physician):
            physician.add_patient(is_step_down=True)
            remaining_A -= 1

    # Allocate step-down to Team B and Team N (combined, sorted by lowest stepdown count)
    team_B_and_N = working_team_B + working_team_N
    team_B_and_N_sorted = sorted(team_B_and_N, key=lambda x: initial_stepdown_counts.get(x.name, x.step_down_patients))
    remaining_B_N = stepdown_for_B_and_N

    for physician in team_B_and_N_sorted:
        if remaining_B_N <= 0:
            break
        if can_take_step_down(physician):
            physician.add_patient(is_step_down=True)
            remaining_B_N -= 1

    # Final verification: Ensure new physicians who started at/above new_start_number have gained 0 patients
    for physician in physicians:
        if physician.is_new:
            initial_total = initial_counts.get(physician.name, physician.total_patients)
            current_total = physician.total_patients
            gained = current_total - initial_total

            if initial_total >= new_start_number:
                if gained > 0:
                    excess = gained
                    for _ in range(excess):
                        physician.remove_patient()
                    physician.set_total_patients(initial_total)

    # ========== MINIMUM PATIENTS CHECK ==========
    # Check if any physicians are below minimum_patients and redistribute if needed
    all_working = [p for p in physicians if p.is_working]
    below_minimum = [p for p in all_working if p.total_patients < minimum_patients]

    if below_minimum:
        # Calculate total shortfall
        total_shortfall = sum(minimum_patients - p.total_patients for p in below_minimum)

        # Use allocation_order (most recent first when reversed) to determine source physicians
        if allocation_order:
            allocation_index = {}
            for idx, physician in enumerate(reversed(allocation_order)):
                if physician not in allocation_index:
                    allocation_index[physician] = idx

            # Get all physicians above minimum, sort by: highest total first, then most recent allocation
            potential_sources = [p for p in all_working if p.total_patients > minimum_patients]
            potential_sources.sort(key=lambda x: (-x.total_patients, allocation_index.get(x, 999)))

            # Redistribute: take from physicians with highest total (and most recent allocation)
            # and give to physicians below minimum
            below_minimum_sorted = sorted(below_minimum, key=lambda x: x.total_patients)
            used_sources = set()

            for target_physician in below_minimum_sorted:
                if target_physician.total_patients >= minimum_patients:
                    continue

                needed = minimum_patients - target_physician.total_patients

                for source_physician in potential_sources:
                    if needed <= 0:
                        break
                    if source_physician in used_sources:
                        continue
                    if source_physician.total_patients > minimum_patients and can_take_patient(target_physician):
                        source_physician.remove_patient()
                        target_physician.add_patient()
                        used_sources.add(source_physician)
                        needed -= 1

                    if target_physician.total_patients >= minimum_patients:
                        break

    # Calculate results with gains
    results = []
    for physician in physicians:
        original_total = initial_counts.get(physician.name, 0)
        original_stepdown = initial_stepdown_counts.get(physician.name, 0)
        gained = physician.total_patients - original_total
        gained_stepdown = physician.step_down_patients - original_stepdown

        results.append({
            "name": physician.name,
            "yesterday": physician.yesterday,
            "team": physician.team,
            "is_new": physician.is_new,
            "is_buffer": physician.is_buffer,
            "is_working": physician.is_working,
            "original_total_patients": original_total,
            "total_patients": physician.total_patients,
            "original_step_down": original_stepdown,
            "step_down_patients": physician.step_down_patients,
            "transferred_patients": physician.transferred_patients,
            "traded_patients": physician.traded_patients,
            "gained": gained,
            "gained_step_down": gained_stepdown,
            "gained_plus_traded": gained + physician.traded_patients
        })

    # Calculate summary statistics
    team_a_results = [r for r in results if r["team"] == "A"]
    team_b_results = [r for r in results if r["team"] == "B"]
    team_n_results = [r for r in results if r["team"] == "N"]

    summary = {
        "team_a_total": sum(r["total_patients"] for r in team_a_results),
        "team_b_total": sum(r["total_patients"] for r in team_b_results),
        "team_n_total": sum(r["total_patients"] for r in team_n_results),
        "team_a_gained": sum(r["gained"] for r in team_a_results),
        "team_b_gained": sum(r["gained"] for r in team_b_results),
        "team_n_gained": sum(r["gained"] for r in team_n_results),
        "team_a_stepdown_gained": sum(r["gained_step_down"] for r in team_a_results),
        "team_b_stepdown_gained": sum(r["gained_step_down"] for r in team_b_results),
        "team_n_stepdown_gained": sum(r["gained_step_down"] for r in team_n_results),
        "team_a_traded": sum(r["traded_patients"] for r in team_a_results),
        "team_b_traded": sum(r["traded_patients"] for r in team_b_results),
        "total_census": sum(r["total_patients"] for r in results),
        "total_stepdown": sum(r["step_down_patients"] for r in results),
        "total_gained": sum(r["gained"] for r in results)
    }

    return {
        "results": results,
        "summary": summary,
        "remaining_pools": {
            "n_total_new_patients": n_total_new_patients,
            "n_A_new_patients": n_A_new_patients,
            "n_B_new_patients": n_B_new_patients,
            "n_N_new_patients": n_N_new_patients,
            "n_step_down_patients": n_step_down_patients
        }
    }
