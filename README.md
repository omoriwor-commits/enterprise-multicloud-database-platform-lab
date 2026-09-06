# Enterprise Multi-Cloud Database Platform Lab

## Overview

This repository documents a hands-on multi-cloud database engineering lab focused on heterogeneous migration, Change Data Capture (CDC), database administration, cloud networking, security, troubleshooting, operational controls, and production-style runbooks across Oracle Cloud Infrastructure (OCI), Microsoft Azure, and later AWS/GCP.

The current workstream is **OCI Oracle 26ai -> Oracle GoldenGate 26ai hub in Azure -> SQL Server 2022 in Azure**.

> This is a self-directed lab environment. The repository deliberately records failures, troubleshooting evidence, root-cause analysis, remediation, and unresolved work rather than presenting only successful end states.

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
        v
Azure SQL Server 2022
10.60.20.0/24

Future:
AWS PostgreSQL 10.70.0.0/16
GCP PostgreSQL 10.80.0.0/16
```

GoldenGate is deployed as a **dedicated hub with remote capture and remote apply**. The lab will validate one-way CDC first and later extend into bidirectional replication, failure/restart scenarios, reconciliation, cutover, rollback, and conflict handling.

## Documentation

- [Full project history, incidents, troubleshooting, resolutions, and current state](docs/project-history-and-troubleshooting.md)
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

Validated source prerequisites include ARCHIVELOG, minimal supplemental logging, `enable_goldengate_replication=TRUE`, PDB `READ WRITE`, and GoldenGate capture-account baseline preparation.

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
OCI Oracle host -> Azure SQL TCP 1433          PASS
Azure GoldenGate -> OCI Oracle TCP 1521        PASS
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

DBA baseline includes dedicated data/log/tempdb storage, MAXDOP 2, max server memory 5120 MB, optimize-for-ad-hoc enabled, TCP/IP enabled, and a validated `LabTestDB`.

### Azure GoldenGate Hub

```text
VM:                            vm-goldengate-lab-01
Private IP:                    10.60.30.4
OS:                            Oracle Linux 9.8
GoldenGate software home:      /u01/ogg26ai_home
Service Manager deployment:    /u01/ogg26ai_deploy
DEP1 deployment home:          /u01/ogg26ai_sm
Service Manager port:          9011
Administration Service port:   9012
Distribution Service port:     9013
Receiver Service port:         9014
Performance Metrics port:      9015
```

## Current GoldenGate Status — September 6, 2026

GoldenGate software installation is valid and OGGCA successfully **created and verified `DEP1`**. The current blocker is the Service Manager daemon-registration transition.

OGGCA failed with:

```text
INS-85038: Deployment removal failed

Verification failed.
Expected value: (NOT) 'running'
Actual value: 'running'
```

Detailed log and Service Manager task-history analysis showed that the stop request itself succeeded and the DEP1 microservices subsequently exited normally with `status=stopped` and `exitCode=0`. OGGCA performed its stopped-state verification before Service Manager had fully reconciled the service state.

Current verified process state:

```text
Administration Service   stopped
Distribution Service     stopped
Receiver Service         stopped
Performance Metrics      stopped
Service Manager          running
OracleGoldenGate systemd service registration  NOT completed
```

The daemon-registration script was not generated because OGGCA never advanced beyond the failed stop-verification phase.

**Important:** the project is **not** currently claiming that Service Manager has been successfully registered as a Linux systemd service. Earlier documentation that stated registration had completed was superseded by the deeper log/process investigation and has now been corrected.

Before additional repair work, both configuration trees were backed up. The next controlled step is to verify the exact GoldenGate maintenance build and evaluate known OGGCA stop/daemon-registration fixes before considering any destructive recreate path.

## Major Troubleshooting Cases Recorded

| Incident | Root Cause / Best Evidence | Outcome |
|---|---|---|
| OCI↔Azure VPN did not establish correctly | Pre-shared-key mismatch | Corrected; IPsec and BGP validated |
| Windows OpenSSH did not provide usable X11 for GUI configuration | Management-tool/X11 limitation | MobaXterm X11 path used |
| First GoldenGate Administration Server crashed after reboot | Repeated `std::bad_alloc` in TrailFileCache initialization; host resources healthy | Clean deinstall/reinstall chosen |
| Silent OGGCA returned `INS-85005` for valid software home | Silent response-file/configuration path issue | GUI path validated home and continued configuration |
| GoldenGate web UI inaccessible remotely | NSG/firewalld management path | Source-restricted rules applied and access validated |
| OGGCA `INS-85038` | Stop succeeded but state verification occurred before full reconciliation | DEP1 now stopped; systemd registration remains unresolved |
| Oracle SQL appeared hung | FRA quota exhausted; archive could not progress; LGWR waited on log switch | FRA/RMAN remediation path established |
| GoldenGate TNS directory initially absent | Database-connectivity preparation incomplete | Directory created; alias validation still pending |

The detailed chronology and evidence are maintained in [docs/project-history-and-troubleshooting.md](docs/project-history-and-troubleshooting.md).

## Security Controls

The lab follows these rules:

- No broad public database-listener exposure.
- Do not permit `0.0.0.0/0 -> 1433` or `0.0.0.0/0 -> 1521`.
- Restrict temporary management access to known source addresses.
- Keep passwords, PSKs, private keys, and response-file credentials out of GitHub.
- Treat temporary public SSH/X11 access as lab-only and remove it after GUI work.
- Add TLS/HTTPS to the GoldenGate management plane before treating it as production-like.

## Current Next Steps

1. Verify the exact installed GoldenGate maintenance build.
2. Determine whether the build is affected by known OGGCA daemon-registration/stop-verification defects and patch if appropriate.
3. Complete Oracle-supported Service Manager daemon registration without unnecessarily deleting the valid `DEP1` deployment.
4. Revalidate Oracle source/FRA health.
5. Build and validate `TNS_ADMIN` / `tnsnames.ora` connectivity.
6. Configure GoldenGate credential-store alias and `DBLOGIN`.
7. Configure `TRANDATA` / schema supplemental logging for the replication scope.
8. Create Extract and trail.
9. Prepare the SQL Server GoldenGate target path and schema/datatype mappings.
10. Configure Replicat and validate Oracle-to-SQL Server INSERT/UPDATE/DELETE CDC.
11. Perform reconciliation, failure/restart, cutover, and rollback testing.
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
