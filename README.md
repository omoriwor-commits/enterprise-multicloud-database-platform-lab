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
        +-- Remote Extract from OCI Oracle
        +-- GoldenGate trail
        +-- Planned remote Replicat to SQL Server
        |
        v
Azure SQL Server 2022
10.60.20.0/24

Future:
AWS PostgreSQL 10.70.0.0/16
GCP PostgreSQL 10.80.0.0/16
```

GoldenGate is deployed as a **dedicated hub with remote capture and remote apply**. The current phase is validating one-way Oracle-to-SQL Server CDC before failure/restart, reconciliation, cutover, rollback, and later multi-cloud expansion.

## Documentation

- [Full project history, incidents, troubleshooting, resolutions, and current state](docs/project-history-and-troubleshooting.md)
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

A VPN pre-shared-key mismatch was diagnosed using tunnel-health evidence and Azure Network Watcher, corrected, and the tunnel/BGP session were validated afterward.

### Azure SQL Server Target

```text
VM:          vm-sqlserver-lab-01
Private IP:  10.60.20.4
OS:          Windows Server 2022
Database:    SQL Server 2022 Developer
VM size:     Standard_D2as_v7
SQL port:    TCP 1433
```

DBA baseline includes dedicated data/log/tempdb storage, MAXDOP 2, max server memory 5120 MB, optimize-for-ad-hoc enabled, TCP/IP enabled, and validated local administration through SSMS 20.

GoldenGate target objects are prepared:

```text
Database:       OGGTargetDB
Schema:         HOLA
Table:          HOLA.FOX
Primary key:    PK_FOX(ID)
GoldenGate user ogg_repl
```

Target table structure:

```text
ID          int           NOT NULL
NAME        varchar(100)  NULL
CREATED_AT  datetime2     NULL
STATUS      varchar(20)   NULL
```

The SQL Server VM is managed privately. A source-restricted SSH/RDP tunnel through the GoldenGate hub was validated rather than assigning a public IP directly to the SQL Server VM.

### Azure GoldenGate Hub

```text
VM:                            vm-goldengate-lab-01
Private IP:                    10.60.30.4
OS:                            Oracle Linux 9.8
GoldenGate Oracle home:        /u01/ogg26ai_home
Service Manager deployment:    /u01/ogg26ai_deploy
Deployment:                    DEP1
Service Manager port:          9011
Administration Service port:   9012
Distribution Service port:     9013
Receiver Service port:         9014
Performance Metrics port:      9015
```

## Current GoldenGate Status — September 7, 2026

The previous OGGCA stop/daemon-registration blocker is **resolved**.

Service Manager is registered as:

```text
OracleGoldenGate.service
```

The healthy process hierarchy is:

```text
ServiceManager
  +-- adminsrvr
  +-- distsrvr
  +-- pmsrvr
  +-- recvsrvr
```

All core GoldenGate Microservices are running.

### Oracle Extract validation

Extract group:

```text
EXTORA
```

Validated state:

```text
Status:                RUNNING
Checkpoint lag:        00:00:00 at validation
Capture:               Oracle Integrated Redo Logs, per-PDB
Trail:                 ./dirdat/ea
Encryption profile:    LocalWallet
```

Observed statistics for `HOLA.FOX`:

```text
Inserts:          1
Updates:          1
Deletes:          0
Operations:       2
Metadata records: 1
```

This proves Oracle source changes are being captured and written to the GoldenGate trail.

## SQL Server Replicat Preparation

The project confirmed an important heterogeneous-runtime requirement.

The current home:

```text
/u01/ogg26ai_home
```

is the **Oracle database GoldenGate build**. Although it contains an MSSQL-related admin-client library, it does not contain the expected Linux SQL Server ODBC runtime area:

```text
msodbc            NOT PRESENT
odbc.ini          NOT FOUND
odbcinst.ini      NOT FOUND
libmsodbcsql.so   NOT FOUND
```

Therefore the Oracle source runtime remains intact for `DEP1` / `EXTORA`, and the SQL Server target will use a **separate SQL Server-specific GoldenGate home/deployment on the same hub VM**.

Planned layout:

```text
/u01/ogg26ai_home
  Oracle GoldenGate runtime
  DEP1
  EXTORA

/u01/ogg_sqlserver_home
  SQL Server-specific GoldenGate runtime
  separate target deployment
  Replicat -> 10.60.20.4:1433 / OGGTargetDB
```

This preserves the intended architecture: **remote Extract and remote Replicat from one central hub**.

## Current Media Blocker

A GoldenGate for Microsoft SQL Server package was transferred to the hub and validated successfully as a ZIP, but archive inspection showed:

```text
ggs_Windows_x64_MSSQL_services_shiphome
setup.exe
oui.exe
```

The package is therefore the **Windows x64 MSSQL build**, not the required Linux x86-64 build for the Oracle Linux hub.

No installation was attempted from the mismatched media.

The immediate blocker is obtaining the correct:

```text
Oracle GoldenGate 26ai for Microsoft SQL Server
Platform: Linux x86-64
```

## Major Troubleshooting Cases Recorded

| Incident | Root Cause / Best Evidence | Outcome |
|---|---|---|
| OCI↔Azure VPN did not establish correctly | Pre-shared-key mismatch | Corrected; IPsec and BGP validated |
| Windows OpenSSH did not provide usable X11 for GUI configuration | Management-tool/X11 limitation | MobaXterm X11 path used |
| First GoldenGate Administration Server crashed after reboot | Repeated `std::bad_alloc` in TrailFileCache initialization; host resources healthy | Clean deinstall/reinstall chosen |
| Silent OGGCA returned `INS-85005` for valid software home | Silent response-file/configuration path issue | GUI path validated home and continued configuration |
| GoldenGate web UI inaccessible remotely | NSG/firewalld management path | Source-restricted rules applied and access validated |
| OGGCA stop/daemon-registration failure | Deployment services remained active after Service Manager stop | Controlled service shutdown; OGGCA rerun; systemd registration succeeded |
| Oracle SQL appeared hung | FRA quota exhausted; archive could not progress; LGWR waited on log switch | FRA/RMAN recovery path established; capture later validated |
| SQL Server private RDP unreachable | Azure NSG deny rule blocked 3389 | Source-restricted rule + IP Flow Verify; SSH/RDP tunnel validated |
| First SQL Server media SCP upload failed | Transfer dropped around 53%; incomplete ZIP | Corrupt copy removed and re-uploaded via SFTP |
| SQL Server GoldenGate media was wrong platform | Archive identified Windows x64 MSSQL build | Installation stopped; Linux x86-64 package required |

Detailed chronology and evidence are maintained in the project history and dated checkpoint documents.

## Security Controls

The lab follows these rules:

- No broad public database-listener exposure.
- Do not permit `0.0.0.0/0 -> 1433` or `0.0.0.0/0 -> 1521`.
- Restrict temporary management access to known source addresses.
- Keep passwords, PSKs, private keys, and credential-store secrets out of GitHub.
- Keep SQL Server RDP private where a controlled jump/tunnel path is available.
- Treat temporary public SSH/X11 access as lab-only and remove it after GUI work.
- Add TLS/HTTPS to the GoldenGate management plane before treating it as production-like.

## Current Next Steps

1. Obtain the **Linux x86-64 GoldenGate 26ai for Microsoft SQL Server** distribution.
2. Validate package integrity and platform before extraction.
3. Install the SQL Server GoldenGate runtime into a separate home on the existing hub.
4. Create a separate SQL Server-target deployment without disturbing Oracle `DEP1` / `EXTORA`.
5. Configure SQL Server ODBC/connectivity components.
6. Create the GoldenGate target DB connection/credential for `ogg_repl` without committing secrets.
7. Validate GoldenGate login to `OGGTargetDB`.
8. Configure Replicat mapping from Oracle `HOLA.FOX` to SQL Server `HOLA.FOX`.
9. Start Replicat and validate INSERT/UPDATE/DELETE CDC.
10. Perform source/target reconciliation and lag/checkpoint validation.
11. Perform restart/recovery, cutover, rollback, and failure-injection testing.
12. Continue into AWS PostgreSQL after the Oracle-to-SQL Server path is stable.

## Troubleshooting Method

The project uses a consistent evidence-driven incident workflow:

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
