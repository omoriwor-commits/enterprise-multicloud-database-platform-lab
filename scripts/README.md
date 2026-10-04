# Automation and Operational Scripts

This directory contains reusable scripts developed for database platform operations and health validation.

## Data Guard

- [dataguard_health_check.sh](dataguard/dataguard_health_check.sh)

Purpose: operational health checking for Oracle Data Guard environments.

## Oracle RAC

- [rac_health_fixed.py](oracle-rac/rac_health_fixed.py)

Purpose: Oracle RAC health and operational validation.

## Organization Standard

New automation should be grouped by platform or function:

```text
scripts/
├── dataguard/
├── oracle-rac/
├── goldengate/
├── monitoring/
└── utilities/
```

Only create a new category when a real script is added.

## Security

Scripts must not contain:

- plaintext database passwords
- SSH private keys
- cloud access keys
- VPN pre-shared keys
- production tokens
- wallet secrets

Use environment variables, credential stores, or platform-native secret management where appropriate.
