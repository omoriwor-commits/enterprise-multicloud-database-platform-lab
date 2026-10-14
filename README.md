# Enterprise Multi-Cloud Database Platform Lab

## Overview

This repository documents my Oracle-to-SQL Server migration across OCI and Azure using GoldenGate 26ai, including the cloud networking, troubleshooting and validation behind it.

This is **Migration 3 — Oracle 26ai (OCI) to Azure SQL Server 2022: Heterogeneous Cross-Cloud Migration & GoldenGate Replication**, the final stage of my three-stage path (19c → 26ai on-prem, on-prem → OCI, OCI → Azure SQL Server 2022).

My completed implementation architecture is:

```text
OCI Oracle 26ai
-> Oracle GoldenGate 26ai hub in Azure
-> Azure SQL Server 2022
```

> This is a self-directed lab environment. The repository deliberately records failures, troubleshooting evidence, root-cause analysis, remediation and validation rather than presenting only successful end states.

## Final outcome

**Completed:** I completed the third stage of my migration path from Oracle AI Database 26ai on OCI, through the Azure GoldenGate 26ai hub, to Azure SQL Server 2022. I verified end-to-end target apply of INSERT, UPDATE and DELETE operations; the results matched the intended one-way CDC behavior.

**Build history:** The September build checkpoints show earlier stages when Extract, trails, networking, SQL Server access and Replicat preparation were being validated. They remain dated snapshots, not the final status. Detailed incident diagnoses and remedies are preserved in the [project history](docs/project-history/project-history-and-troubleshooting.md), including VPN/BGP negotiation, GoldenGate startup and OGGCA lifecycle, management access, SQL Server connectivity, and Oracle FRA exhaustion.

**Evidence to publish on rerun:** Sanitized final Replicat reports, source/target DML comparisons, lag/checkpoint observations and restart/reconciliation outputs.

## Architecture

```text
OCI SOURCE (10.50.0.0/16)                AZURE (10.60.0.0/16)
+---------------------------+            +-------------------------------------+
| Oracle AI Database 26ai   |            | Dedicated GoldenGate hub           |
| CDB23AI / PDB23AI         |-- IPsec -->| OL 9.8 / snet-goldengate           |
| Oracle listener TCP 1521  |  BGP route |                                     |
+---------------------------+            | DEP1: EXTORA / REMOTE capture       |
                                         |       trail ea                      |
                                         | MSSQLDEP: REPSQL / REMOTE apply     |
                                         +------------------+------------------+
                                                            |
                                                            | ODBC SQL_TGT / TCP 1433
                                                            v
                                         +-------------------------------------+
                                         | Azure SQL Server 2022               |
                                         | OGGTargetDB / HOLA.FOX              |
                                         | snet-database (private)             |
                                         +-------------------------------------+
```

The deployment uses **remote Integrated Extract for Oracle source capture** from the Azure GoldenGate hub and **remote Replicat apply to SQL Server 2022** from the dedicated SQL Server GoldenGate runtime on that hub. GoldenGate's Oracle and SQL Server software deployments are separate; the hub accesses the OCI source and Azure SQL Server over the private network.

## Documentation

- [September 2026 build snapshot](docs/checkpoints/2026-09-build-snapshot.md)
- [OCI Oracle → Azure SQL Server GoldenGate rerun playbook](docs/oci-to-azure-goldengate-rerun-playbook.md) — ordered build gates, diagnostics, source/target validation and evidence capture.
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

`ogg_repl` was granted `db_owner` for the lab build. Before any production use I would scope it down to only the permissions Replicat needs.

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

## September Checkpoint: Extract Capture (before Replicat apply)

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

This September snapshot confirmed source capture to the trail. Final end-to-end apply of INSERT, UPDATE and DELETE was validated later (see Final outcome).

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

- Database listeners are not publicly exposed; no 0.0.0.0/0 rules for 1433 or 1521.
- Management access is restricted to known source addresses.
- SQL Server RDP stays private and is reached through an SSH tunnel.
- Only the GoldenGate management port needed for browser administration is open.
- Passwords, PSKs, private keys and credential-store secrets are kept out of GitHub.
- The GoldenGate management plane does not yet use TLS/HTTPS; I would add it before any production-like use.

## Rerun

The step-by-step rebuild and evidence capture are in the [rerun playbook](docs/oci-to-azure-goldengate-rerun-playbook.md).
