"""Include unavailable/reserved filesystem bytes in the nominal-capacity estimate.

The available-free-space target and every runner guard remain unchanged.
Keep the original capture and plan; calculate this correction from its snapshot.
"""
import json
from pathlib import Path

root=Path(__file__).resolve().parent
inventory=json.loads((root/'space-inventory.json').read_text())
target=root/'space-plan.json'
with (root/'space-plan.initial.json').open('xb') as out:out.write(target.read_bytes())
plan=json.loads(target.read_text())
unavailable=inventory['filesystem_total_bytes']-inventory['filesystem_used_bytes']-inventory['filesystem_free_bytes']
assert unavailable>=0
plan.pop('minimum_total_capacity_with_current_data_retained_bytes')
plan['recorded_unavailable_or_reserved_bytes']=unavailable
plan['same_filesystem_total_capacity_lower_bound_bytes']=inventory['filesystem_total_bytes']+plan['additional_free_bytes_to_that_target']
plan['nominal_capacity_note']='Lower bound assuming the recorded unavailable/reserved bytes stay constant. Use measured available free bytes after resize/staging; reserved/metadata allocation can grow.'
plan['correction']='Original plan retained in space-plan.initial.json. Include total-used-available gap in nominal capacity estimate; available-free target and runtime thresholds unchanged.'
target.write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps({'unavailable_or_reserved_bytes':unavailable,
    'same_filesystem_total_capacity_lower_bound_bytes':plan['same_filesystem_total_capacity_lower_bound_bytes'],
    'operational_free_target_bytes':plan['conservative_target_free_bytes_before_future_staging']},indent=2))
