# Enterprise Multi-Cloud Database Platform Lab — Project History, Troubleshooting, and Current State

**Project:** Enterprise Data Platform / Multi-Cloud Migration & Replication Lab  
**Repository:** `enterprise-multicloud-database-platform-lab`  
**Chronology covered:** August 2026 through September 6, 2026  
**Purpose:** Preserve the engineering history of the lab, including architecture decisions, implementation work, incidents, evidence, root causes, remediations, validation, and unresolved work.

> **Security note:** Passwords, pre-shared keys, private-key material, and current administrator source IP addresses are intentionally omitted from this public documentation.

---

## Final outcome — later than the dated checkpoints

I subsequently completed the OCI Oracle 26ai → Azure GoldenGate 26ai → Azure SQL Server 2022 one-way CDC implementation and personally verified INSERT, UPDATE and DELETE replication at the SQL Server target. This is the third migration in my connected three-stage lab path. The incident chronology and September checkpoints below record the earlier build and troubleshooting stages; their then-open tasks should not be mistaken for the final outcome. The sanitized final target-side validation logs and restart/reconciliation evidence have not yet been archived here and will be collected on a rerun.

## 1. Project Goal and Target Architecture

The lab is a production-style heterogeneous database engineering environment spanning multiple cloud providers. It is designed to practice database migration, CDC, cloud networking, GoldenGate administration, security, failure analysis, backup/recovery, validation, cutover, rollback, and operational runbooks.

```text
OCI
Oracle AI Database 26ai
VCN 10.50.0.0/16
Oracle host 10.50.10.178
        |
        | Route-based IPsec/IKEv2 + BGP
        v
Azure
VNet 10.60.0.0/16
        |
        +-- GoldenGate Hub 10.60.30.4
        |      |
        |      +-- remote capture from OCI Oracle
        |      +-- remote apply to Azure SQL Server
        |
        +-- SQL Server 2022 10.60.20.4

Future:
AWS PostgreSQL 10.70.0.0/16
GCP PostgreSQL 10.80.0.0/16
```

Selected GoldenGate model:

```text
Dedicated hub with remote capture and remote apply
```

Planned replication sequence:

```text
Oracle -> SQL Server one-way CDC
-> failure/restart/reconciliation testing
-> bidirectional/active-active-style lab
-> AWS PostgreSQL expansion
-> GCP PostgreSQL comparison
```

---

## 2. Azure Foundation and Addressing

### Governance and cost controls

Configured:

- Resource group: `rg-enterprise-data-platform-lab`
- Region: East US
- Monthly budget: `$50`
- Alert thresholds: 50%, 75%, 90%, 100%
- Tags:
  - `Environment=Lab`
  - `Project=EnterpriseDataPlatform`
  - `Workload=CrossCloudMigration`
  - `ManagedBy=Manual`

Azure Bastion, Azure Firewall, and Azure DDoS Network Protection were intentionally not used during the credit-sensitive lab build. Security is implemented through subnet separation, NSGs, host firewalls, VPN routing, and source-restricted rules.

### Cross-cloud CIDR standard

```text
OCI    10.50.0.0/16
Azure  10.60.0.0/16
AWS    10.70.0.0/16
GCP    10.80.0.0/16
```

### Azure VNet

```text
vnet-enterprise-data-platform-lab
10.60.0.0/16
```

Subnets:

```text
snet-management   10.60.10.0/24
snet-database     10.60.20.0/24
snet-goldengate   10.60.30.0/24
GatewaySubnet     10.60.254.0/27
```

The GoldenGate subnet was deliberately reserved rather than placing GoldenGate arbitrarily in a management or database subnet.

---

## 3. Azure SQL Server Build and DBA Baseline

Platform:

```text
VM:               vm-sqlserver-lab-01
Private IP:       10.60.20.4
OS:               Windows Server 2022
Database:         SQL Server 2022 Developer
VM size:          Standard_D2as_v7
```

Storage layout:

```text
F:\data\     user database data files
G:\log\      user database log files
H:\tempDb\   tempdb files
```

Validated DBA configuration:

```text
MAXDOP                         2
max server memory             5120 MB
optimize for ad hoc workloads enabled
TCP/IP                        enabled
Static SQL port               1433
Windows Authentication        validated
SQL Server Authentication     validated
```

Test database:

```text
LabTestDB data: F:\data\LabTestDB.mdf
LabTestDB log:  G:\log\LabTestDB_log.ldf
```

Private database access is enforced. A scoped rule permits the OCI Oracle host to test SQL Server connectivity:

```text
10.50.10.178/32 -> 10.60.20.4 TCP 1433
```

Broad Internet database rules such as `0.0.0.0/0 -> 1433` are intentionally avoided.

---

## 4. OCI Oracle Source Baseline

OCI compute/network:

```text
Instance:    rotez_instance_oci
Region:      us-chicago-1
OS:          Oracle Linux 9.8
Shape:       VM.Standard.E5.Flex
Private IP:  10.50.10.178
VCN:         Rotez_hybrid-lab-vcn
VCN CIDR:    10.50.0.0/16
Subnet:      public-subnet-lab
Subnet CIDR: 10.50.10.0/24
```

Oracle database validation:

```text
Oracle AI Database 26ai Enterprise Edition
Version:                         23.26.1.0.0
CDB:                             CDB23AI
PDB:                             PDB23AI
PDB service:                     pdb23ai
Database role:                   PRIMARY
Open mode:                       READ WRITE
ARCHIVELOG:                      enabled
FORCE LOGGING:                   YES
enable_goldengate_replication:   TRUE
minimal supplemental logging:    YES
Oracle listener:                 TCP 1521
```

`PDB23AI` was confirmed `READ WRITE`. The listener advertises service `pdb23ai` and is reachable privately from the Azure GoldenGate host.

The database account `GGADMIN` exists and was confirmed `OPEN`. Privilege revalidation and final GoldenGate database-login configuration remain part of the current workstream.

---

## 5. OCI ↔ Azure Site-to-Site VPN and BGP

A route-based IPsec/IKEv2 Site-to-Site VPN with BGP was built between OCI and Azure.

Azure side:

```text
VPN Gateway:  vng-enterprise-data-platform-lab
SKU:          VpnGw1AZ
VPN type:     Route-based
Azure ASN:    65515
Azure APIPA:  169.254.21.2
```

OCI side:

```text
DRG:          drg-azure-hybrid-lab
Attachment:   att-rotez-hybrid-lab-vcn
CPE:          cpe-azure-vpn-gateway
IPSec:        ipsec-oci-azure-lab
Tunnel:       Azure-Tunnel-1
OCI ASN:      31898
IKE:          IKEv2
```

### Incident 1 — VPN tunnel failed to establish correctly

**Symptom:** The tunnel configuration appeared structurally valid, but connectivity was not healthy.

**Evidence collected:**

- Azure Network Watcher VPN diagnostics
- Azure VPN Gateway health
- OCI tunnel status
- IKE state
- ESP/IPsec state
- BGP peer state
- Local Network Gateway settings
- route propagation
- shared-key consistency

**Root cause:** Pre-shared key mismatch between OCI and Azure.

**Remediation:** The PSK was corrected so both VPN peers used the same value.

**Validation:**

```text
IPSec tunnel:                  Up
IPv4 BGP:                      Up
Azure BGP peer:                Connected
Azure learned OCI route:       10.50.0.0/16
Azure advertised toward OCI:   10.60.0.0/16
VPN diagnostics:               Healthy
```

End-to-end private connectivity was then proven:

```text
OCI Oracle host 10.50.10.178
-> Azure SQL Server 10.60.20.4:1433
Result: SUCCESS
```

This incident established the troubleshooting model used throughout the project:

```text
Detect -> Collect Evidence -> Isolate Failure Domain -> Root Cause -> Remediate -> Validate -> Document RCA
```

---

## 6. GoldenGate Network Preparation and Hub Deployment

GoldenGate network objects:

```text
Subnet:  snet-goldengate 10.60.30.0/24
NSG:     nsg-goldengate-lab
```

Key controlled paths:

```text
Management subnet -> GoldenGate TCP 22
GoldenGate subnet -> Azure SQL Server 10.60.20.4 TCP 1433
GoldenGate subnet -> OCI Oracle 10.50.10.178 TCP 1521
```

OCI security-list ingress was configured for:

```text
10.60.30.0/24 -> TCP 1521
```

Dedicated GoldenGate VM:

```text
VM:          vm-goldengate-lab-01
Private IP:  10.60.30.4
OS:          Oracle Linux 9.8
VM size:     Standard_D2as_v7
```

A NAT Gateway was associated later for outbound Internet access. Direct management access used a temporary public path with source-restricted NSG rules during GUI/X11 work.

---

## 7. GoldenGate Remote Administration and X11 Troubleshooting

### Incident 2 — Native Windows OpenSSH did not provide usable X11 forwarding

The initial administration model used the OCI host as a jump path to the private Azure GoldenGate VM. SSH itself worked, but native Windows OpenSSH did not create the required X11 display environment for Oracle GUI installers.

**Remediation:** A temporary direct public-IP path was created with source-restricted SSH access, and MobaXterm was used for X11 forwarding.

**Validation:**

```text
DISPLAY=localhost:10.0
```

GoldenGate installer and OGGCA GUI sessions could then launch successfully.

**Security follow-up:** The direct public administration path is a lab convenience and remains a hardening item; the long-term model should favor private/jump-host/VPN administration.

---

## 8. First GoldenGate 26ai Installation — Administration Server Crash

The first GoldenGate 26ai Microservices deployment initially installed successfully. After reboot, Administration Server repeatedly crashed.

### Incident 3 — `std::bad_alloc` in Administration Server

**Symptom:** `adminsrvr` terminated during startup with an uncaught C++ exception:

```text
std::bad_alloc
```

The stack localized around:

```text
trailfilecache::TrailFileCache
adminsrvr::TrailCache::initialize()
AdminServer::start()
```

**Troubleshooting:**

- RAM checked
- swap checked
- filesystem capacity checked
- GoldenGate logs reviewed
- crash/core evidence reviewed
- repeated startup behavior compared

Host memory, swap, and disk were healthy. The failure repeatedly occurred in the Trail File Cache initialization path.

**Engineering decision/remediation:** Because this was a disposable lab deployment and evidence pointed to an internal GoldenGate runtime failure rather than host resource exhaustion, the deployment was deinstalled and rebuilt cleanly instead of continuing low-value binary-level debugging.

---

## 9. GoldenGate Reinstallation and Silent OGGCA Failure

New software home:

```text
/u01/ogg26ai_home
```

Deployment:

```text
DEP1
```

GoldenGate software installation completed successfully and the Oracle inventory registered the home.

### Incident 4 — OGGCA silent response file returned `INS-85005`

**Symptom:** A hand-edited OGGCA response file failed with:

```text
INS-85005
Specified GoldenGate software home invalid
```

**Isolation:** The GUI accepted the exact same software home. Therefore the GoldenGate home itself was valid; the failure was specific to the silent response-file/configuration path.

**Remediation:** Configuration switched to X11 GUI mode. A canonical OGGCA-generated response file was retained with restricted permissions because it contains sensitive configuration data.

---

## 10. GoldenGate 26ai Runtime Configuration

Validated runtime version:

```text
Oracle GoldenGate 26ai
23.26.1.0.0
```

Current paths:

```text
GoldenGate software home:       /u01/ogg26ai_home
Service Manager deployment:     /u01/ogg26ai_deploy
User deployment:                DEP1
```

Microservices:

| Service | Port | Current Status |
|---|---:|---|
| Service Manager | 9011 | Running |
| Administration Service | 9012 | Running |
| Distribution Service | 9013 | Running |
| Receiver Service | 9014 | Running |
| Performance Metrics Service | 9015 | Running |

Service Manager is registered as:

```text
OracleGoldenGate.service
```

---

## 11. OGGCA Deployment Stop / Daemon Registration Failure — Resolved

### Incident 5 — OGGCA expected `DEP1` to be stopped but still saw `running`

During OGGCA configuration, deployment stop verification failed with:

```text
Verification failed.
Expected value: (NOT) 'running'
Actual value: 'running'
```

Earlier attempts also surfaced `INS-85038` during the daemon-registration workflow because OGGCA could not complete its required stopped-state validation.

### Evidence collected

The investigation used:

```text
systemctl status OracleGoldenGate
ps -ef
/proc/<PID>/cgroup
ss -lntp
OGGCA logs
GoldenGate Admin Client
Service Manager REST/service state
```

A key observation was that Service Manager could be inactive while deployment services remained alive:

```text
adminsrvr
distsrvr
pmsrvr
recvsrvr
```

Ports `9012-9015` were still listening. Those services had become independent of the stopped Service Manager process and were observed with `PPID 1`.

The systemd unit used process-oriented lifecycle behavior, so stopping Service Manager did not by itself prove the entire deployment tree was down.

### Root cause

The failure was a **deployment lifecycle/state mismatch**: OGGCA required `DEP1` to be fully stopped, but one or more deployment Microservices remained active after Service Manager shutdown. OGGCA therefore correctly continued to observe the deployment as running.

The evidence did not justify reinstalling GoldenGate again or killing arbitrary processes.

### Controlled remediation

Service Manager was started and the deployment was controlled through Admin Client:

```text
CONNECT http://127.0.0.1:9011 DEPLOYMENT DEP1 AS oggadmin
```

The controlled shutdown sequence was:

```text
STOP ER *
STOP DISTPATH ALL
STOP SERVICE *
STATUS SERVICE *
```

At this point no Extract/Replicat groups and no Distribution Paths existed, so the expected warnings about absent ER groups/distpaths were non-fatal.

All four deployment Microservices were stopped. Service Manager was then stopped through systemd, and OS/socket checks confirmed the GoldenGate processes and ports were down.

### Final resolution

OGGCA was rerun. The configuration completed successfully:

```text
Start Service Manager                         Succeeded
Verify Service Manager                        Succeeded
Add Service Manager Administrator User        Succeeded
Install Plugin Service in Service Manager     Succeeded
Create Deployment                             Succeeded
Verify Deployment                             Succeeded
Stop Deployment                               Succeeded
Register Service Manager as system service    Succeeded
```

### Post-resolution validation

Healthy process hierarchy was observed:

```text
ServiceManager
  +-- adminsrvr
  +-- distsrvr
  +-- pmsrvr
  +-- recvsrvr
```

The child services were again parented by the active Service Manager rather than detached under PID 1.

**Status: RESOLVED.**

This supersedes earlier notes that described OGGCA daemon registration as an unresolved blocker.

---

## 12. GoldenGate Web Access Troubleshooting — Resolved

### Incident 6 — GoldenGate worked locally but browser access failed remotely

Local HTTP checks succeeded:

```text
9011 HTTP=200
9012 HTTP=200
```

Initial `curl -I` tests returned HTTP 405 because GoldenGate rejected the HTTP `HEAD` method; this did not indicate a network failure. Normal HTTP `GET` checks returned 200.

Remote Windows tests to the GoldenGate public IP showed:

```text
TcpTestSucceeded : False
```

for TCP 9011 and 9012.

### Failure-domain isolation

```text
Administrator workstation
-> Azure public IP
-> Azure NSG
-> Oracle Linux firewalld
-> GoldenGate listener
```

GoldenGate was already listening on `*` and the application was healthy locally, so the fault domain moved outward to host firewall and Azure networking.

### Linux firewall remediation

The active firewalld zone was `public`. Controlled access was added:

```bash
sudo firewall-cmd --permanent --zone=public --add-port=9011/tcp
sudo firewall-cmd --permanent --zone=public --add-port=9012/tcp
sudo firewall-cmd --reload
```

### Azure NSG remediation

A source-restricted inbound NSG rule was added for TCP 9011-9012 using the administrator's current public IP as a `/32`, rather than opening the management plane to `0.0.0.0/0`.

### Public-IP clarification

The GoldenGate VM had a NIC-associated public IP used for inbound management. A separate NAT Gateway public IP was identified as outbound SNAT only and was not used as the browser destination.

### Validation

The GoldenGate Service Manager web UI loaded successfully and showed `DEP1` with Administration, Distribution, Performance Metrics, and Receiver services all running.

**Status: RESOLVED.**

**Hardening follow-up:** HTTP connectivity is proven; TLS/HTTPS is still required before treating the management plane as production-like.

---

## 13. GoldenGate Hub -> OCI Oracle Listener Connectivity — Validated

From the Azure GoldenGate VM:

```text
Source:      10.60.30.4
Destination: 10.50.10.178
Route:       via 10.60.30.1 dev eth0
```

TCP test:

```text
GoldenGate 10.60.30.4
-> IPsec/BGP
-> OCI Oracle 10.50.10.178:1521

TCP 1521 SUCCESS
```

A second test using `curl telnet://10.50.10.178:1521` established the TCP connection.

This validates the network path through:

```text
Azure GoldenGate VM
-> Azure VNet
-> Azure VPN Gateway
-> IPsec/IKEv2 + BGP
-> OCI DRG
-> OCI VCN
-> OCI security controls
-> Oracle listener
```

`sqlplus` and `tnsping` were not installed on the GoldenGate VM, so database-service authentication will be tested through GoldenGate/native database connectivity rather than by installing unnecessary client tooling solely for this check.

---

## 14. GoldenGate Patch Investigation — No Patch Applied

During troubleshooting, a large Windows download named:

```text
V1054592-01.zip
```

was initially suspected to be a GoldenGate patch. It was verified to be an Oracle AI Database 26ai base image rather than the required GoldenGate maintenance patch.

The installed runtime remained:

```text
23.26.1.0.0
```

`OPatch lsinventory` showed no interim patches. Because the OGGCA lifecycle issue was later resolved operationally, patching was separated from the incident and not treated as a required remediation for that failure.

**Status:** Patch work intentionally paused until a specific GoldenGate patch and its README are obtained and evaluated.

---

## 15. Oracle Database Hang / FRA Exhaustion Incident — RCA Complete, Recovery Still To Be Validated

### Incident 7 — `ALTER USER` appeared to hang

While preparing the GoldenGate source account, an account-management DDL statement did not return promptly.

Wait analysis showed many sessions waiting on:

```text
log file switch (archiving needed)
```

Many sessions reported:

```text
BLOCKING_SESSION = 16
```

SID 16 was identified as the Oracle `LGWR` background process.

### Important distinction

`LGWR` was the visible blocker in the wait chain, but it was **not the root cause** and was not killed.

### Evidence collected

The investigation used:

- `V$SESSION`
- `V$PROCESS`
- `ARCHIVE LOG LIST`
- `V$RECOVERY_FILE_DEST`
- `V$ARCHIVE_DEST`
- `V$ARCHIVE_DEST_STATUS`
- `df -h /u03`
- `du -sh /u03/fra`

### Root cause

Fast Recovery Area configuration:

```text
db_recovery_file_dest      = /u03/fra
db_recovery_file_dest_size = 10G
```

Oracle FRA usage:

```text
Limit:        10G
Used:         9.88G
Reclaimable:  0G
Files:        60
```

Archive destination:

```text
STATUS: ERROR
ORA-19809: limit exceeded for recovery files
```

Linux filesystem capacity:

```text
Filesystem size: 83G
Used:            54G
Available:       30G
```

Physical FRA directories included approximately:

```text
/u03/fra/CDB23AI   9.9G
/u03/fra/RMAN26    7.9G
```

This proved the incident was an **Oracle FRA quota exhaustion problem**, not an actually full Linux filesystem.

### Failure chain

```text
FRA reaches configured Oracle quota
-> ARCn cannot archive completed redo
-> online redo log cannot be reused
-> LGWR cannot complete required log switch
-> sessions wait on "log file switch (archiving needed)"
-> foreground SQL/DDL appears hung
```

### Chosen remediation approach

Because `/u03` still had substantial physical free space, the immediate recovery approach is to increase the FRA quota, then validate archive recovery:

```sql
ALTER SYSTEM SET db_recovery_file_dest_size=20G SCOPE=BOTH;
ALTER SYSTEM ARCHIVE LOG CURRENT;
```

After archive health is restored, FRA cleanup will be performed through RMAN rather than deleting recovery files manually from the OS:

```text
SHOW RETENTION POLICY;
REPORT OBSOLETE;
LIST BACKUP OF ARCHIVELOG ALL;
CROSSCHECK ARCHIVELOG ALL;
DELETE EXPIRED ARCHIVELOG ALL;
```

Any deletion of obsolete or backed-up archive logs must be based on RMAN evidence and recovery requirements.

**Current status:** Root cause confirmed. Recovery/cleanup commands still require execution and post-change validation before this incident is marked fully resolved.

---

## 16. Current GoldenGate Source Preparation

Current source readiness:

```text
CDB23AI PRIMARY / READ WRITE
PDB23AI READ WRITE
ARCHIVELOG enabled
FORCE LOGGING YES
minimal supplemental logging YES
enable_goldengate_replication TRUE
listener TCP 1521 reachable from GoldenGate
GGADMIN account OPEN
```

Still pending before Extract configuration:

```text
1. Restore and validate archive/FRA health
2. Revalidate final GGADMIN GoldenGate privileges
3. Configure GoldenGate database credential/alias
4. Validate GoldenGate database login to PDB23AI
5. Configure TRANDATA / SCHEMATRANDATA for replication scope
6. Register/configure Extract
7. Configure trail files
8. Prepare SQL Server target mapping and credentials
9. Configure Replicat
10. Run initial load and INSERT/UPDATE/DELETE CDC validation
```

---

## 17. End-to-End Validations Completed

```text
OCI <-> Azure IPsec/IKEv2                           PASS
OCI <-> Azure BGP                                   PASS
Azure learns OCI 10.50.0.0/16                       PASS
Azure advertises 10.60.0.0/16                       PASS
OCI Oracle VM -> Azure SQL Server TCP 1433          PASS
GoldenGate VM -> OCI Oracle TCP 1521                PASS
GoldenGate Service Manager local HTTP 9011          PASS
GoldenGate Administration local HTTP 9012           PASS
GoldenGate remote web access                        PASS
GoldenGate DEP1 creation                            PASS
GoldenGate controlled deployment shutdown           PASS
OGGCA Service Manager systemd registration          PASS
GoldenGate Microservice managed process hierarchy   PASS
Oracle source ARCHIVELOG                            PASS
Oracle source FORCE LOGGING                         PASS
Oracle minimal supplemental logging                 PASS
Oracle enable_goldengate_replication                PASS
Oracle listener service pdb23ai                     PASS
```

---

## 18. Incident / Remediation Register

| Incident | Failure Domain | Root Cause / Best Evidence | Remediation | Status |
|---|---|---|---|---|
| OCI↔Azure VPN unhealthy | Network/VPN | PSK mismatch | Corrected shared key; revalidated IKE/IPsec/BGP | Resolved |
| Windows OpenSSH unusable for installer X11 | Management tooling | Required X11 display not established | Temporary source-restricted direct SSH + MobaXterm X11 | Resolved for build |
| GoldenGate Admin Server `std::bad_alloc` | GoldenGate runtime | Repeatable TrailFileCache initialization crash; host resources healthy | Clean deinstall/rebuild | Resolved by rebuild |
| OGGCA `INS-85005` valid home rejected | Configuration tooling | Silent response-file path issue; GUI accepted same home | Used GUI/canonical response configuration | Resolved |
| OGGCA stop verification / `INS-85038` | GoldenGate lifecycle | DEP1 child services remained running independently after Service Manager stop | Controlled `STOP SERVICE *`, systemd stop, OS validation, rerun OGGCA | Resolved |
| GoldenGate web UI unreachable remotely | Azure/host networking | Azure NSG and firewalld inbound path incomplete | Opened 9011-9012 locally and source-restricted Azure NSG | Resolved |
| NAT IP confused with VM inbound public IP | Network addressing | NAT Gateway IP is outbound SNAT, not NIC inbound destination | Used NIC-associated public IP for browser test | Resolved |
| `curl -I` returned 405 | Application protocol test | GoldenGate rejected HEAD, while GET worked | Retested with normal HTTP GET | Resolved |
| Suspected GoldenGate patch ZIP was wrong product | Patch management | Download was Oracle AI Database base image, not GoldenGate patch | Patch work paused; require correct patch/README | Resolved identification |
| Oracle DDL appeared hung | Oracle redo/archive | FRA quota exhausted; `ORA-19809`; LGWR waiting on archive progress | Increase FRA, restore archiving, RMAN cleanup | RCA complete; remediation pending validation |

---

## 19. Current State — September 6, 2026

### Completed / validated

- Azure governance, cost budget, VNet, subnets, and NSGs
- SQL Server 2022 deployment and baseline DBA configuration
- SQL Server listener TCP 1433
- OCI Oracle 26ai source baseline
- OCI↔Azure route-based IPsec/IKEv2 Site-to-Site VPN
- BGP adjacency and route exchange
- PSK mismatch incident diagnosis and remediation
- OCI Oracle -> Azure SQL Server private TCP 1433 connectivity
- Dedicated Azure GoldenGate hub VM
- GoldenGate 26ai software installation/reinstallation
- GoldenGate `DEP1`
- Service Manager systemd registration
- Administration, Distribution, Receiver, and Metrics services running
- OGGCA deployment-stop incident resolved
- GoldenGate web-access incident resolved
- Azure GoldenGate -> OCI Oracle TCP 1521 connectivity
- Oracle `FORCE LOGGING` enabled
- Oracle minimal supplemental logging validated
- `enable_goldengate_replication=TRUE` validated
- FRA exhaustion root cause identified

### Active technical gate

```text
Oracle FRA / archive destination health
```

The source archive subsystem must be healthy before GoldenGate Extract work continues.

### Replication tasks not yet completed

- FRA recovery validation and RMAN cleanup
- final GoldenGate database privilege validation
- credential store/database alias
- GoldenGate DBLOGIN to `PDB23AI`
- TRANDATA/SCHEMATRANDATA
- Extract
- trail files
- SQL Server target schema/datatype conversion
- Replicat
- initial-load synchronization
- INSERT/UPDATE/DELETE CDC test
- lag/restart/recovery testing
- reconciliation
- cutover/rollback
- bidirectional replication
- TLS hardening
- AWS PostgreSQL phase
- GCP PostgreSQL phase

---

## 20. Immediate Next Engineering Sequence

```text
1. Relieve FRA pressure
2. Force/retest archiving
3. Confirm archive destination is VALID and ORA-19809 is cleared
4. Review/clean FRA safely through RMAN
5. Revalidate GGADMIN privileges
6. Configure GoldenGate database credentials
7. Validate database login to PDB23AI
8. Configure TRANDATA/SCHEMATRANDATA
9. Configure Extract and trails
10. Prepare SQL Server target schema/credentials
11. Configure Replicat
12. Perform initial load and CDC validation
```

---

## 21. Engineering Principles Demonstrated

This project deliberately preserves failures rather than hiding them. The objective is to demonstrate a repeatable platform/database troubleshooting method:

```text
1. Define the intended architecture.
2. Build least-privilege network boundaries.
3. Validate one layer at a time.
4. Capture logs, waits, routes, sockets, process trees, and service state.
5. Separate symptoms from root cause.
6. Avoid destructive action until evidence justifies it.
7. Apply the smallest controlled remediation.
8. Validate at the same layer where the failure was observed.
9. Preserve rollback/configuration backups.
10. Document the RCA and operational lesson.
```

That methodology has been applied to VPN negotiation, GoldenGate installation/runtime failures, OGGCA lifecycle failures, remote management access, X11 tooling, patch identification, cross-cloud listener connectivity, and Oracle FRA exhaustion.
