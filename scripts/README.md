# Automation and Operational Scripts

This directory contains reusable scripts developed for database platform operations and health validation.

## Data Guard

- [dataguard_health_check.sh](dataguard/dataguard_health_check.sh)

Purpose: collect Oracle Data Guard operational evidence. SQL, role-discovery and broker errors now fail collection. Exit 0 means collection completed; lag/gap values still require DBA interpretation. Seven fake-tool regression tests cover unavailable databases, malformed discovery, SQL and broker errors. Live primary/standby validation remains pending.

Run: `python3 -m unittest discover -s scripts/dataguard/tests -v`.

## Oracle RAC

- [rac_health_check.py](oracle-rac/rac_health_check.py)

Purpose: Oracle RAC health and operational validation.

Revision `2026-10-19.3` was live-tested on the two-node 26ai lab on October 19, 2026. Run as the authorized Grid owner (`grid` in this lab) for SYSASM; database SQL also requires existing OS SYSDBA authorization.

```bash
./oracle-rac/rac_health_check.py --version
./oracle-rac/rac_health_check.py --db RAC --pdb RACPDB1 --dbca-node racnode1 2>&1 | tee ~/rac_health.log
printf 'script_exit=%s\n' "${PIPESTATUS[0]}"
```

Grid and database homes/bases are discovered independently. Overrides and sampling options are listed by `--help`. Exit codes: 0 no findings in completed checks; 1 warnings/incomplete coverage; 2 critical findings; 3 configuration error. Database/ASM global views cover both instances; alert and DBCA history are local only. Run on node 2 for its local alert history; omit `--dbca-node racnode1` there unless reviewing creation-node expectations deliberately. A snapshot does not test SCAN client login, failover or backup recoverability.

[Latest 26ai health evidence](../docs/evidence/oracle-rac/2026-10-19-rac26-health-check-v3.md). The 54 regression tests run with `python3 -m unittest discover -s scripts/oracle-rac/tests -v`.

