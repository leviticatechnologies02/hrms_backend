import sys

with open('app/api/v1/endpoints/onboarding.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('app/api/v1/endpoints/onboarding.py', 'w', encoding='utf-8') as f:
    f.writelines(lines[:1873])

print("File truncated successfully.")
