# Enterprise Multi-Cloud Database Platform Lab

## Overview

This repository documents a hands-on multi-cloud database engineering lab focused on heterogeneous migration, Change Data Capture (CDC), database administration, cloud networking, security, troubleshooting, operational controls, and production-style runbooks across Oracle Cloud Infrastructure (OCI), Microsoft Azure, and later AWS/GCP.

The current workstream is:

```text
OCI Oracle 26ai
-> Oracle GoldenGate 26ai hub in Azure
-> Azure SQL Server 2022
```

> This is a self-directed lab environment. The repository deliberately records failures, troubleshooting evidence, root-cause analysis, remediation, validation, and unresolved work rather than presenting only successful end states.

## Target Architecture

```text
OCI
Oracle Database 26ai
10.50.0.0/16
        |
        | Route-based IPsec/IKEv2 + BGP
        v
Azure
Dedicated Oracle GoldenGate 26ai Hub
10.60.30.0/24
        |
        +-- Oracle runtime / DEP1
        |     Remote Integrated Extract EXTORA
        |     Trail ./dirdat/ea
        |
        +-- SQL Server runtime / MSSQLDEP
              Remote Replicat REPSQL (configuration in progress)
        |
        v
Azure SQL Server 2022
10.60.20.0/24
OGGTargetDB.HOLA.FOX

Future:
AWS PostgreSQL 10.70.0.0/16
GCP PostgreSQL 10.80.0.0/16
```

GoldenGate is deployed as a **dedicated hub with remote capture and remote apply**. The current phase is completing one-way Oracle-to-SQL Server CDC before restart/recovery, reconciliation, cutover, rollback, and later multi-cloud expansion.

## Documentation

- [Full project history, incidents, troubleshooting, resolutions, and current state](docs/project-history/project-history-and-troubleshooting.md)
- [September 9, 2026 Oracle-to-SQL Server Replicat preparation checkpoint](docs/checkpoints/2026-09-09-oracle-to-sqlserver-replicat-prep.md)
- [September 7, 2026 Oracle-to-SQL Server CDC checkpoint](docs/checkpoints/2026-09-07-oracle-to-sqlserver-cdc-progress.md)
- [Azure foundation and multi-cloud implementation plan](docs/azure/phase-1-azure-foundation.md)

## Current Environment

### OCI Oracle Source

```text
VCN:         Rotez_hybrid-lab-vcn
VCN CIDR:    10.50.0.0/16
Oracle VM:   10.50.10.178
Database:    Oracle AI Database 26ai Enterprise Edition
Version:     23.26.1.0.0
CDB:         CDB23AI
PDB:         PDB23AI
PDB service: pdb23ai
Listener:    TCP 1521
```

Validated source prerequisites include ARCHIVELOG, FORCE LOGGING, minimal supplemental logging, `enable_goldengate_replication=TRUE`, PDB `READ WRITE`, and GoldenGate capture-account preparation.

### Azure Network

```text
VNet:             vnet-enterprise-data-platform-lab  10.60.0.0/16
snet-management:  10.60.10.0/24
snet-database:    10.60.20.0/24
snet-goldengate:  10.60.30.0/24
GatewaySubnet:    10.60.254.0/27
```

OCI and Azure are connected through a route-based IPsec/IKEv2 VPN using BGP.

Validated routing/connectivity:

```text
IPsec tunnel                                   UP
BGP adjacency                                  UP
Azure learns OCI 10.50.0.0/16                 PASS
OCI/Azure route exchange                       PASS
Azure GoldenGate -> OCI Oracle TCP 1521        PASS
Azure GoldenGate -> Azure SQL TCP 1433         PASS
```

### Azure SQL Server Target

```text
VM:          vm-sqlserver-lab-01
Private IP:  10.60.20.4
OS:          Windows Server 2022
Database:    SQL Server 2022 Developer
VM size:     Standard_D2as_v7
SQL port:    TCP 1433
```

Target objects:

```text
Database:             OGGTargetDB
Application schema:   HOLA
Target table:         HOLA.FOX
Primary key:          PK_FOX(ID)
GoldenGate login:     ogg_repl
GoldenGate schema:    ogg_repl
Checkpoint table:     ogg_repl.ggs_checkpoint
```

Validated `ogg_repl` database roles currently include:

```text
db_owner
db_datareader
db_datawriter
```

The SQL Server VM remains privately managed. Administration uses a controlled SSH/RDP tunnel through the GoldenGate hub rather than assigning a public IP to SQL Server.

### Azure GoldenGate Hub

```text
VM:         vm-goldengate-lab-01
Private IP: 10.60.30.4
OS:         Oracle Linux 9.8
```

Two database-specific GoldenGate runtimes now coexist on the same hub.

#### Oracle deployment

```text
Software home:                 /u01/ogg26ai_home
Deployment:                    DEP1
Service Manager port:          9011
Administration Service port:   9012
Distribution Service port:     9013
Receiver Service port:         9014
Performance Metrics port:      9015
Extract:                       EXTORA
Trail:                         ./dirdat/ea
```

#### Microsoft SQL Server deployment

```text
Software home:                 /u01/ogg26ai_mssql_home
Service Manager home:          /u01/ogg26ai_mssql_deploy
User deployment home:          /u01/ogg26ai_mssql_sm
Deployment:                    MSSQLDEP
Service Manager port:          9021
Administration Service port:   9022
Distribution Service port:     9023
Receiver Service port:         9024
Performance Metrics port:      9025
Replication schema:            ogg_repl
```

Both deployments are running independently.

## Oracle Extract Validation

```text
Extract:               EXTORA
Status:                RUNNING
Checkpoint lag:        00:00:00 at validation
Capture:               Oracle Integrated Redo Logs, per-PDB
Trail:                 ./dirdat/ea
Encryption profile:    LocalWallet
```

Observed `HOLA.FOX` statistics:

```text
Inserts:          1
Updates:          1
Deletes:          0
Operations:       2
Metadata records: 1
```

This proves Oracle source changes are being captured and written to the GoldenGate trail.

## SQL Server GoldenGate Runtime — Completed

The correct Linux x86-64 GoldenGate package for Microsoft SQL Server was obtained and validated:

```text
V1054820-01.zip
GoldenGate 23.26.1.0.1
Linux x86-64 for Microsoft SQL Server
```

The dedicated SQL Server GoldenGate home is installed at:

```text
/u01/ogg26ai_mssql_home
```

Validated bundled components include:

```text
bin/replicat
bin/adminclient
msodbc/lib64/libmsodbcsql.so
msodbc/odbcinst.ini
msodbc/mssql_odbcini_template.ini
```

The earlier Windows-x64 package mismatch is retained in the dated project history as a troubleshooting case.

## ODBC / SQL Server Connectivity — Completed

Oracle Linux prerequisites installed:

```text
unixODBC-2.3.12-1.el9.x86_64
unixODBC-devel-2.3.12-1.el9.x86_64
```

Configured DSN:

```ini
[SQL_TGT]
Driver = Microsoft ODBC Driver for SQL Server
Server = tcp:10.60.20.4,1433
Database = OGGTargetDB
Encrypt = yes
TrustServerCertificate = yes
```

Direct validation succeeded:

```text
isql -> Connected!
SELECT DB_NAME(); -> OGGTargetDB
```

A GoldenGate DB Connection was also created and validated in `MSSQLDEP`:

```text
Credential Domain: OracleGoldenGate
Credential Alias:  SQL_TGT
DSN:               SQL_TGT
User ID:           ogg_repl
```

GoldenGate itself can therefore authenticate to the target database.

## MSSQLDEP Deployment — Completed

The SQL Server-specific OGGCA deployment was created successfully after isolating the MSSQL shell environment from the Oracle `DEP1` environment.

All MSSQLDEP services were verified listening:

```text
9021 Service Manager
9022 Administration Server
9023 Distribution Server
9024 Receiver Server
9025 Performance Metrics Server
```

Management-plane troubleshooting also separated three layers cleanly:

```text
GoldenGate application -> healthy locally
Azure NSG             -> source-restricted 9022 rule added
Oracle Linux firewalld -> 9022/tcp added
```

The SQL Server Administration UI is now reachable and identifies itself as:

```text
Oracle GoldenGate 23.26.1.0.1 for Microsoft SQL Server (MSSQLDEP)
```

## Replicat Preparation — In Progress

Checkpoint table created:

```text
ogg_repl.ggs_checkpoint
```

Replicat creation has started with:

```text
Replicat Type: Classic Replicat
Process Name:  REPSQL
Description:   Oracle HOLA.FOX to SQL Server HOLA.FOX
```

Current Replicat Options being prepared:

```text
Trail name:          ea
Trail subdirectory:  dirdat
Target domain:       OracleGoldenGate
Target alias:        SQL_TGT
Checkpoint table:    ogg_repl.ggs_checkpoint
Begin:               Position in Trail
```

The next controlled task is verifying the trail-position fields, completing the Replicat parameter file, starting `REPSQL`, and validating end-to-end apply.

## Current Status — September 9, 2026

| Component | Status |
|---|---|
| OCI Oracle source | Ready / capture validated |
| OCI<->Azure VPN/BGP | Healthy |
| Oracle GoldenGate `DEP1` | Running |
| Oracle Extract `EXTORA` | Running |
| Oracle `HOLA.FOX` capture | Validated |
| Trail `./dirdat/ea` | Contains captured changes |
| Azure SQL Server | Running |
| SQL Server TCP 1433 from hub | Reachable |
| `OGGTargetDB.HOLA.FOX` | Present / validated |
| `ogg_repl` login/user/schema | Ready |
| Linux MSSQL GoldenGate runtime | Installed |
| unixODBC | Installed / validated |
| `SQL_TGT` DSN | Validated |
| MSSQLDEP | Running |
| MSSQL Administration UI | Reachable |
| GoldenGate `SQL_TGT` connection | Validated |
| `ogg_repl.ggs_checkpoint` | Created |
| `REPSQL` | Configuration in progress |
| End-to-end Oracle -> SQL Server apply | Pending |

## Major Troubleshooting Cases Recorded

| Incident | Root Cause / Best Evidence | Outcome |
|---|---|---|
| OCI<->Azure VPN did not establish correctly | Pre-shared-key mismatch | Corrected; IPsec and BGP validated |
| GoldenGate Administration Server issue after reboot | Service/process state and prior deployment condition | Clean recovery/reinstall path established |
| OGGCA stop/daemon-registration failure | Deployment services remained active after Service Manager stop | Controlled service shutdown; systemd registration succeeded |
| Oracle SQL appeared hung | FRA quota exhausted; archive could not progress | FRA/RMAN recovery path established; capture validated |
| SQL Server private RDP unreachable | Azure NSG deny rule blocked 3389 | Source-restricted rule + SSH/RDP tunnel validated |
| First SQL Server media SCP upload failed | Transfer dropped; incomplete ZIP | Corrupt copy removed and re-uploaded |
| SQL Server GoldenGate media wrong platform | Windows-x64 archive downloaded | Correct Linux x86-64 package obtained |
| OGGCA reported empty `ODBCSYSINI` in silent flow | SQL Server deployment/silent validation path plus environment contamination | MSSQL environment isolated; GUI OGGCA completed successfully |
| `unixODBC` tools unavailable | `unixODBC` and `unixODBC-devel` missing | Required OL9 repositories enabled; packages installed |
| MSSQL Administration UI unreachable publicly | Azure NSG + Oracle Linux firewalld path | Source-restricted NSG rule + `9022/tcp` firewalld rule; UI validated |

Detailed chronology and evidence are maintained in the project history and dated checkpoint documents.

## Security Controls

- No broad public database-listener exposure.
- Do not permit `0.0.0.0/0 -> 1433` or `0.0.0.0/0 -> 1521`.
- Restrict management access to known source addresses.
- Keep passwords, PSKs, private keys, and credential-store secrets out of GitHub.
- Keep SQL Server RDP private where a controlled jump/tunnel path is available.
- Open only the GoldenGate management port currently required for browser administration.
- Add TLS/HTTPS before treating the GoldenGate management plane as production-like.

## Current Next Steps

1. Complete `REPSQL` Replicat Options and verify the correct trail start position.
2. Complete the Replicat parameter file for Oracle `HOLA.FOX` -> SQL Server `HOLA.FOX`.
3. Start `REPSQL` and inspect report/log output.
4. Verify existing captured trail records apply correctly.
5. Generate controlled INSERT, UPDATE, and DELETE transactions on Oracle.
6. Validate delivery into SQL Server.
7. Reconcile source/target row counts and values.
8. Test Replicat stop/start and checkpoint recovery.
9. Measure lag and verify no duplicate apply after restart.
10. Document cutover/rollback and failure-injection results.
11. Continue into AWS PostgreSQL after Oracle-to-SQL Server CDC is stable.

## Troubleshooting Method

```text
Detect
  -> Collect Evidence
  -> Isolate Failure Domain
  -> Identify Root Cause
  -> Remediate
  -> Validate
  -> Prevent Recurrence
  -> Document RCA
```

This repository will continue to be updated incrementally with implementation procedures, architecture diagrams, commands, validation evidence, troubleshooting cases, migration runbooks, rollback procedures, and lessons learned.
