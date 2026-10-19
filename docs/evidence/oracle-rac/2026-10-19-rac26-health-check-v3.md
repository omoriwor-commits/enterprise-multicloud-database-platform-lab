# Oracle 26ai RAC health check — revision 2026-10-19.3

Collected: 2026-10-19 10:46:23 CDT, racnode1, as grid. Source: terminal output supplied by Rotimi Omoriwo. This record is not an independently collected session. The [terminal transcript](2026-10-19-rac26-health-check-v3.txt) has the shell listing, invocation and final prompt removed; the report and exit status are retained.

## Observed results

| Check | Result |
|---|---|
| OS collection | racnode1 and racnode2 collected |
| Clusterware | CRS, CSS and EVM online on both nodes |
| Database | RAC1 and RAC2 OPEN / ACTIVE; version 23.26.1.0.0 |
| PDB | RACPDB1 READ WRITE on both |
| Service | RAC_RACPDB1 running on RAC1 and RAC2 |
| Archiving | ARCHIVELOG; FRA +FRA, reported use 4.4% |
| ASM | +ASM1 and +ASM2 running; cluster name raccluster in client names |
| Disk groups | DATA, FRA and OCR MOUNTED on both ASM instances; zero offline disks |
| Disks | All six instance/disk observations MEMBER, CACHED, ONLINE, NORMAL |
| CPU | Node 1 mean 63.4%, node 2 mean 15.4%, about three seconds each |
| Paging | No swap-in/out observed in sampled intervals |
| THP / HugePages | madvise on both; explicit HugePages_Total 0 |
| Assessment | REVIEW REQUIRED; zero critical findings, four warnings; exit 1 |

The four warnings comprise local database alert history, local ASM alert history and the UEK8/23.26.1 compatibility flag on each node. Alert matching-line counts are not incident counts. Earlier file/redo errors occurred during the DBCA period; the snapshot does not establish each initiating cause. The 03:44 ASM hang requires separate correlation with host evidence. Node 1 SELinux troubleshooting processes consumed substantial CPU; this does not establish why they ran or explain the earlier hang.

Oracle's [Grid](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/supported-oracle-linux-9-distributions-for-x86-64.html) and [Database](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/supported-oracle-linux-9-distributions-for-x86-64.html) guides specify OL9 UEK8 support starting with RU 23.26.2. Reported 23.26.1 inventories do not close that gap.

## Separate manual validation

Rotimi confirmed completion of the SCAN connection test with RAC2 stopped after reporting instance/service stop and restoration. The runbook records observed baseline connections to RAC1 and RAC2 and archive output from both threads. The raw SCAN connection/instance-stop transcript is not attached here. This is a controlled new-connection availability result; no transparent existing-session/transaction failover, unplanned node loss or backup recovery outcome is claimed.

## Scope and tests

The script collects global database/ASM views but reviews local alert and DBCA history only. This run covers node 1 local history; node 2 local alert history needs a separate run. Automated tests cover parsing, discovery, coverage failures, resource states, time windows, CPU/paging sampling and private JSON output. All 54 tests passed locally before publication; the supplied transcript establishes a separate live lab run.

The transcript retains private lab IPs, hostnames, software paths and process IDs. No password, signed download token, private key, disk serial, machine-id, MAC, VM UUID or Windows username path is included. A password-file pathname is metadata, not its contents.
