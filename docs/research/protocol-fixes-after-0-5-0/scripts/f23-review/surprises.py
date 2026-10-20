"""What the library itself meets in every catcher of the lane."""
from validation import mutants
plain = mutants.baselines()
found = mutants.surprises(plain)
print("surprises:", found or "none")
for search in mutants.CATCHERS:
    print(f"{search.name}: {len(plain[search.name])} violations met on the library")
