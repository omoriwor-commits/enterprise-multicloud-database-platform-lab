# Enterprise Data Platform Lab — Multi-Cloud Migration & Replication Plan

**Checkpoint Date:** September 6, 2026  

> Dated record. Status sections below are historical; see the [README Final outcome](../../README.md#final-outcome) for the current state.
**Project:** Enterprise Data Platform / Multi-Cloud Migration & Replication Lab

## 1. Target Architecture

```text
OCI
Oracle AI Database 26ai
10.50.0.0/16
      |
      | Route-based IPsec/IKEv2 + BGP
      v
Azure
Dedicated Oracle GoldenGate 26ai Hub
10.60.30.4 / snet-goldengate 10.60.30.0/24
      |
      | Remote apply / later reverse capture
      v
Azure SQL Server 2022
10.60.20.4 / snet-database 10.60.20.0/24
      |
      | Later migration / replication
      v
AWS PostgreSQL
10.70.0.0/16
      |
      | Later comparison / expansion
      v
Google Cloud PostgreSQL
10.80.0.0/16
```

Selected GoldenGate deployment model:

```text
Model 4 — Dedicated hub with remote capture and remote apply
```

The lab is designed to practice:

- Unidirectional CDC
- Bidirectional / active-active-style replication patterns
- Failure, restart, lag, conflict, reconciliation, cutover, and rollback scenarios
- Evidence-based network/database/platform troubleshooting

---

## 2. OCI Source Environment

### OCI Compute

```text
Instance:       rotez_instance_oci
Region:         us-chicago-1
Availability:   AD-1 / FD-2
OS:             Oracle Linux 9.8
Shape:          VM.Standard.E5.Flex
OCPU:           1
Memory:         12 GB
Private IPv4:   10.50.10.178
```

### OCI Network

```text
VCN:            Rotez_hybrid-lab-vcn
VCN CIDR:       10.50.0.0/16
Subnet:         public-subnet-lab
Subnet CIDR:    10.50.10.0/24
Oracle VM:      10.50.10.178
```

The OCI VNIC currently relies on the subnet security list plus the Oracle Linux host firewall.

### Oracle Source Database Baseline

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
GGADMIN account:                 OPEN
```

The Oracle listener advertises `pdb23ai` and is reachable privately from the Azure GoldenGate VM.

---

## 3. Azure Foundation and Cost Controls

```text
Resource group: rg-enterprise-data-platform-lab
Region:         East US
Budget:         $50/month
Alerts:         50%, 75%, 90%, 100%
```

Tags:

```text
Environment = Lab
Project     = EnterpriseDataPlatform
Workload    = CrossCloudMigration
ManagedBy   = Manual
```

Paid services intentionally not used unless required:

```text
Azure Bastion                 Disabled
Azure Firewall                Disabled
Azure DDoS Network Protection Disabled
```

Security relies on segmentation, NSGs, host firewalls, private routing, and least-privilege source/destination rules.

---

## 4. Cross-Cloud IP Addressing Standard

```text
OCI      10.50.0.0/16
Azure    10.60.0.0/16
AWS      10.70.0.0/16
GCP      10.80.0.0/16
```

No CIDR overlap is permitted.

---

## 5. Azure Network and VPN

```text
VNet: vnet-enterprise-data-platform-lab
CIDR: 10.60.0.0/16
```

Subnets:

```text
snet-management    10.60.10.0/24
snet-database      10.60.20.0/24
snet-goldengate    10.60.30.0/24
GatewaySubnet      10.60.254.0/27
```

VPN Gateway:

```text
Name:          vng-enterprise-data-platform-lab
SKU:           VpnGw1AZ
VPN type:      Route-based
Azure ASN:     65515
Azure APIPA:   169.254.21.2
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

Validated state:

```text
IPSec:                       Up
IPv4 BGP:                    Up
Azure BGP peer:              Connected
Azure learns OCI route:      10.50.0.0/16
Azure advertises to OCI:     10.60.0.0/16
VPN diagnostics:             Healthy
```

### VPN Incident — PSK Mismatch

The tunnel initially failed despite otherwise plausible configuration. Azure Network Watcher, IKE/ESP state, BGP status, route propagation, and peer settings were checked. The root cause was a pre-shared-key mismatch. After correcting the PSK, IPsec and BGP came Up and route exchange was validated.

Private database-path validation:

```text
OCI Oracle 10.50.10.178
-> Azure SQL Server 10.60.20.4:1433
Result: SUCCESS
```

---

## 6. Azure SQL Server Platform

```text
VM:          vm-sqlserver-lab-01
Private IP:  10.60.20.4
OS:          Windows Server 2022
Database:    SQL Server 2022 Developer
VM size:     Standard_D2as_v7
```

Validated configuration:

```text
TCP/IP enabled
Static TCP port 1433
MAXDOP 2
max server memory 5120 MB
optimize for ad hoc workloads enabled
```

Storage:

```text
F:\data\     user data files
G:\log\      user log files
H:\tempDb\   tempdb files
```

Test database:

```text
LabTestDB
Data file: F:\data\LabTestDB.mdf
Log file:  G:\log\LabTestDB_log.ldf
```

---

## 7. GoldenGate Hub — Deployed and Operational

```text
VM:            vm-goldengate-lab-01
Private IP:    10.60.30.4
OS:            Oracle Linux 9.8
VM size:       Standard_D2as_v7
GoldenGate:    Oracle GoldenGate 26ai Microservices
Version:       23.26.1.0.0
OGG home:      /u01/ogg26ai_home
Deployment:    DEP1
```

Microservices:

| Service | Port | Status |
|---|---:|---|
| Service Manager | 9011 | Running |
| Administration Service | 9012 | Running |
| Distribution Service | 9013 | Running |
| Receiver Service | 9014 | Running |
| Performance Metrics Service | 9015 | Running |

Service Manager is registered as `OracleGoldenGate.service` under systemd.

### GoldenGate network controls

```text
nsg-goldengate-lab
Associated subnet: snet-goldengate 10.60.30.0/24
```

Key flows:

```text
Management subnet -> GoldenGate TCP 22
GoldenGate -> Azure SQL Server 10.60.20.4 TCP 1433
GoldenGate -> OCI Oracle 10.50.10.178 TCP 1521
Restricted admin source /32 -> GoldenGate TCP 9011-9012
```

OCI listener security-list rule:

```text
10.60.30.0/24 -> TCP 1521
```

---

## 8. GoldenGate Installation and Troubleshooting Record

### 8.1 X11 / Remote Administration Issue

Native Windows OpenSSH provided shell access but did not establish the usable X11 display needed for Oracle GUI installers.

**Remediation:** A temporary source-restricted direct SSH path was used with MobaXterm X11 forwarding.

**Validation:**

```text
DISPLAY=localhost:10.0
```

The GoldenGate installer and OGGCA GUI launched successfully.

### 8.2 First Administration Server Crash — `std::bad_alloc`

After the first deployment and reboot, `adminsrvr` repeatedly terminated with:

```text
std::bad_alloc
```

The failure localized around Trail File Cache initialization. RAM, swap, and disk were healthy.

**Remediation:** Because the deployment was disposable and the fault appeared internal to the fresh GoldenGate runtime, evidence was preserved and the deployment was cleanly deinstalled/rebuilt.

### 8.3 Silent OGGCA `INS-85005`

A hand-edited silent response file reported:

```text
INS-85005
Specified GoldenGate software home invalid
```

The GUI accepted the same software home, proving the home itself was valid.

**Remediation:** Switched to the X11 GUI/canonical response-file path.

### 8.4 OGGCA Stop-State / `INS-85038` Incident — Resolved

OGGCA failed deployment-stop verification:

```text
Expected value: (NOT) 'running'
Actual value: 'running'
```

Evidence showed Service Manager could stop while:

```text
adminsrvr
distsrvr
pmsrvr
recvsrvr
```

remained alive and listening on 9012-9015, with detached services observed under `PPID 1`.

Troubleshooting used:

```text
systemctl status OracleGoldenGate
ps -ef
/proc/<PID>/cgroup
ss -lntp
OGGCA logs
GoldenGate Admin Client
```

Controlled remediation:

```text
CONNECT http://127.0.0.1:9011 DEPLOYMENT DEP1 AS oggadmin
STOP ER *
STOP DISTPATH ALL
STOP SERVICE *
STATUS SERVICE *
```

After all child services were confirmed stopped, Service Manager was stopped with systemd and OS/socket state was validated. OGGCA was rerun.

Final OGGCA result:

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

Post-fix, the deployment Microservices were children of the active Service Manager rather than detached under PID 1.

**Status: RESOLVED.**

### 8.5 GoldenGate Web Access Incident — Resolved

Local tests returned HTTP 200 on ports 9011 and 9012, proving the applications were healthy. Remote Windows `Test-NetConnection` failed on both ports.

`curl -I` returned HTTP 405 because GoldenGate rejected the HEAD method; normal GET requests returned HTTP 200. The 405 was not a network outage.

Failure-domain isolation:

```text
Workstation
-> Azure public-IP path
-> Azure NSG
-> Oracle Linux firewalld
-> GoldenGate listeners
```

Linux firewall remediation:

```bash
sudo firewall-cmd --permanent --zone=public --add-port=9011/tcp
sudo firewall-cmd --permanent --zone=public --add-port=9012/tcp
sudo firewall-cmd --reload
```

Azure remediation:

- Added source-restricted `/32` NSG rule for TCP 9011-9012.
- Did not expose the management plane to `0.0.0.0/0`.
- Distinguished the NIC-associated inbound public IP from the NAT Gateway public IP, which is outbound SNAT only.

**Validation:** Service Manager web UI loaded successfully and showed all four DEP1 Microservices running.

**Status: RESOLVED.**

### 8.6 Patch Identification Detour

A downloaded file named `V1054592-01.zip` was initially considered as a possible GoldenGate patch. It was verified to be an Oracle AI Database 26ai base image, not the GoldenGate maintenance patch.

The GoldenGate runtime remains `23.26.1.0.0`; no interim patch was applied as part of the OGGCA remediation.

**Status:** Patch work intentionally deferred until the exact required GoldenGate patch and README are available.

---

## 9. GoldenGate Hub -> OCI Oracle Connectivity — Validated

Route from the GoldenGate VM:

```text
10.50.10.178 via 10.60.30.1 dev eth0 src 10.60.30.4
```

Listener test:

```text
GoldenGate 10.60.30.4
-> IPsec/BGP
-> OCI Oracle 10.50.10.178:1521

TCP 1521 SUCCESS
```

A `curl telnet://10.50.10.178:1521` test also established the TCP connection.

This proves the complete cross-cloud listener path before Extract configuration.

`sqlplus` and `tnsping` were not present on the GoldenGate VM; no unnecessary client install was performed solely for this connectivity test.

---

## 10. Oracle FRA / Redo Incident — RCA Complete, Recovery Validation Pending

While validating the GoldenGate source account, an `ALTER USER` operation appeared to hang.

### Symptom

Many sessions waited on:

```text
log file switch (archiving needed)
```

Many showed `BLOCKING_SESSION = 16`. SID 16 was identified as `LGWR`.

### Root Cause

```text
db_recovery_file_dest      = /u03/fra
db_recovery_file_dest_size = 10G
FRA used                   = 9.88G
FRA reclaimable            = 0G
Archive destination        = ERROR
ORA-19809                  = limit exceeded for recovery files
```

The Linux filesystem itself had about 30 GB available, proving the root cause was Oracle FRA quota exhaustion rather than a full OS filesystem.

Physical FRA usage included:

```text
/u03/fra/CDB23AI   ~9.9G
/u03/fra/RMAN26    ~7.9G
```

Failure chain:

```text
FRA quota exhausted
-> ARCn cannot archive redo
-> completed online redo cannot be reused
-> LGWR cannot progress through required log switch
-> sessions wait on "log file switch (archiving needed)"
-> foreground SQL/DDL appears hung
```

`LGWR` was not killed because it was a symptom-bearing blocker, not the root cause.

### Remediation selected

Immediate recovery:

```sql
ALTER SYSTEM SET db_recovery_file_dest_size=20G SCOPE=BOTH;
ALTER SYSTEM ARCHIVE LOG CURRENT;
```

Then validate archive destination recovery.

Permanent cleanup through RMAN:

```text
SHOW RETENTION POLICY;
REPORT OBSOLETE;
LIST BACKUP OF ARCHIVELOG ALL;
CROSSCHECK ARCHIVELOG ALL;
DELETE EXPIRED ARCHIVELOG ALL;
```

Manual `rm` deletion inside FRA is intentionally avoided.

**Recorded incident status:** Root cause confirmed; executed remediation and incident-specific post-change output are not included in this retained record. Later migration completion is reported separately. Do not infer the exact recovery sequence from that later outcome.

---

## 11. Current Security Principles

Do not use broad public rules for database or GoldenGate administration:

```text
Avoid 0.0.0.0/0 -> TCP 22
Avoid 0.0.0.0/0 -> TCP 1433
Avoid 0.0.0.0/0 -> TCP 1521
Avoid broad public GoldenGate management exposure
```

Use:

- private CIDRs
- least-privilege NSG/security-list rules
- source-restricted administration
- separate management/database/GoldenGate subnets
- host firewalls
- TLS/HTTPS as a GoldenGate hardening follow-up

---

## 12. Current Project Status

> **Status note — 2026-10-18:** The checklist below preserves the September 6 checkpoint. I subsequently completed one-way Oracle-to-SQL Server INSERT, UPDATE and DELETE apply; final sanitized target-side evidence remains to be published. AWS and Google Cloud PostgreSQL are planned, not built. See the [current outcome](../../README.md#final-outcome).

### Completed / Validated

- [x] Azure subscription, budget, and cost controls
- [x] Resource group and governance tags
- [x] Cross-cloud non-overlapping CIDR design
- [x] Azure VNet and subnet segmentation
- [x] Database NSG
- [x] SQL Server VM deployment
- [x] SQL Server 2022 DBA baseline
- [x] SQL Server static listener TCP 1433
- [x] OCI DRG and VCN attachment
- [x] Azure VPN Gateway
- [x] OCI↔Azure route-based IPsec/IKEv2 Site-to-Site VPN
- [x] BGP adjacency and route exchange
- [x] VPN PSK mismatch diagnosed and remediated
- [x] OCI Oracle -> Azure SQL Server TCP 1433 private validation
- [x] GoldenGate subnet and dedicated NSG
- [x] Dedicated GoldenGate hub compute
- [x] GoldenGate 26ai Microservices installation/reinstallation
- [x] DEP1 deployment
- [x] Service Manager systemd registration
- [x] Administration, Distribution, Receiver, and Metrics services validated
- [x] X11 installer-access issue resolved
- [x] Administration Server `std::bad_alloc` incident isolated and remediated by rebuild
- [x] Silent OGGCA `INS-85005` path issue isolated
- [x] OGGCA stop-state / `INS-85038` incident resolved
- [x] GoldenGate web interface network-access incident resolved
- [x] GoldenGate local HTTP 9011/9012 validated
- [x] GoldenGate remote web interface validated
- [x] OCI Oracle source baseline validated
- [x] Oracle FORCE LOGGING enabled
- [x] Minimal supplemental logging validated
- [x] `enable_goldengate_replication=TRUE` validated
- [x] OCI Oracle listener service `pdb23ai` validated
- [x] GoldenGate hub -> OCI Oracle TCP 1521 validated
- [x] `GGADMIN` account confirmed OPEN
- [x] Oracle FRA exhaustion root cause identified
- [x] Incorrect patch package identification corrected

### In Progress

- [ ] Increase/recover FRA and validate archive destination health
- [ ] Clean FRA safely using RMAN
- [ ] Revalidate final GoldenGate database account privileges
- [ ] Configure GoldenGate credential store/database alias
- [ ] Validate GoldenGate database login to `PDB23AI`
- [ ] Configure TRANDATA/SCHEMATRANDATA
- [ ] Configure Oracle Extract
- [ ] Configure trail files
- [ ] Prepare SQL Server schema/datatype mapping
- [ ] Configure SQL Server target credentials/connectivity for GoldenGate
- [ ] Configure Replicat
- [ ] Initial load and CDC validation

### Future

- [ ] Replication lag/failure/restart exercises
- [ ] Data reconciliation
- [ ] Cutover/rollback drill
- [ ] Bidirectional Oracle ↔ SQL Server replication
- [ ] Loop prevention
- [ ] Conflict detection/resolution
- [ ] TLS/HTTPS hardening for GoldenGate management plane
- [ ] Remove temporary direct public administration path when no longer needed
- [ ] AWS PostgreSQL environment
- [ ] Azure/OCI ↔ AWS connectivity
- [ ] PostgreSQL migration/replication
- [ ] GCP PostgreSQL environment
- [ ] Multi-cloud PostgreSQL comparison
- [ ] Monitoring and operational runbooks

---

## 13. Current Technical Gate and Immediate Next Sequence

The GoldenGate hub itself is no longer the blocker. OGGCA registration and web access are working.

The current technical gate is Oracle redo/archive health.

```text
1. Relieve FRA pressure
2. Force/retest archiving
3. Confirm archive destination is VALID and ORA-19809 is gone
4. Review and clean FRA with RMAN
5. Revalidate GGADMIN privileges
6. Configure GoldenGate credential/database alias
7. Validate database login to PDB23AI
8. Configure TRANDATA / SCHEMATRANDATA
9. Configure Extract
10. Configure trail files
11. Prepare SQL Server target schema and credentials
12. Configure Replicat
13. Perform initial load and INSERT/UPDATE/DELETE CDC validation
```

---

## 14. Troubleshooting and Remediation Register

| Incident | Failure Domain | Root Cause / Evidence | Remediation | Status |
|---|---|---|---|---|
| OCI↔Azure VPN initially unhealthy | Network/VPN | PSK mismatch | Corrected PSK; revalidated IKE/IPsec/BGP | Resolved |
| Windows OpenSSH unsuitable for OGGCA X11 | Management tooling | Usable X11 display not established | Temporary restricted direct SSH + MobaXterm X11 | Resolved for build |
| `adminsrvr` `std::bad_alloc` after reboot | GoldenGate runtime | Repeatable TrailFileCache initialization failure; host resources healthy | Clean deinstall/rebuild | Resolved by rebuild |
| OGGCA `INS-85005` | Configuration tooling | Silent response-file path rejected valid home; GUI accepted same home | Switched to GUI/canonical response workflow | Resolved |
| OGGCA stop-state / `INS-85038` | GoldenGate lifecycle | Deployment child services remained active after Service Manager stop | Controlled service shutdown, OS validation, rerun OGGCA | Resolved |
| GoldenGate UI unreachable remotely | Azure/host networking | NSG + firewalld inbound path incomplete | Opened 9011-9012 locally and source-restricted Azure NSG | Resolved |
| HTTP 405 during `curl -I` | Protocol test | HEAD method rejected; GET returned 200 | Retested using normal GET | Resolved |
| NAT Gateway IP mistaken for inbound VM destination | Network addressing | NAT IP is outbound SNAT only | Used NIC-associated public IP for inbound browser test | Resolved |
| Wrong ZIP considered as GoldenGate patch | Patch management | File was Oracle AI Database base image | Patch work paused pending correct patch/README | Resolved identification |
| Oracle DDL appeared hung | Oracle redo/archive | FRA quota exhausted; `ORA-19809`; LGWR waiting on archive progress | Increase FRA, restore archiving, RMAN cleanup | RCA complete; validation pending |

---

## 15. Migration and Replication Method

Because Oracle and SQL Server are heterogeneous platforms, migration will not use RMAN, Data Guard, or a direct Data Pump restore into SQL Server.

| Phase | Method | Objective |
|---|---|---|
| Assessment | SQL Server Migration Assistant for Oracle or equivalent | Identify datatype, PL/SQL, object, and compatibility gaps |
| Schema conversion | Oracle-to-SQL Server conversion | Build equivalent SQL Server schema |
| Initial load | Bulk/migration tooling | Establish synchronized baseline |
| CDC | Oracle GoldenGate | Capture and apply ongoing transactional changes |
| Validation | Row counts, object checks, reconciliation, transaction testing | Prove target correctness |
| Cutover | Controlled write stop, drain replication, final validation | Practice near-zero-downtime transition |
| Rollback | Preserve source and reverse decision if required | Demonstrate recovery discipline |

Key conversion areas:

```text
Oracle NUMBER      -> SQL Server int / bigint / decimal
Oracle VARCHAR2    -> SQL Server varchar / nvarchar
Oracle DATE        -> SQL Server datetime2
Oracle CLOB        -> SQL Server varchar(max) / nvarchar(max)
Oracle sequences   -> SQL Server sequence / identity strategy
Oracle PL/SQL      -> SQL Server T-SQL redesign where required
```

---

## 16. Hands-On Execution Plan

### Stage 1 — Secure Connectivity — Completed

- OCI↔Azure VPN and BGP
- routing
- NSGs/security lists
- Oracle listener TCP 1521 path
- SQL Server TCP 1433 path

### Stage 2 — GoldenGate Hub — Completed at Platform Level

- Dedicated Azure Linux VM
- GoldenGate 26ai Microservices
- DEP1
- systemd Service Manager registration
- management UI
- Oracle network path
- lifecycle troubleshooting

### Stage 3 — Unidirectional Replication

```text
OCI Oracle -> Azure SQL Server
```

Practice:

- schema assessment/conversion
- initial load
- remote capture
- remote apply
- INSERT/UPDATE/DELETE CDC
- checkpoints and lag
- stop/start/restart
- failure recovery
- reconciliation
- cutover/rollback

### Stage 4 — Bidirectional Replication

```text
OCI Oracle <-> Azure SQL Server
```

Practice:

- capture/apply both directions
- loop prevention
- key/sequence/identity strategy
- simultaneous updates
- conflicts
- restart after outage
- reconciliation after divergence

### Stage 5 — AWS Expansion

Build PostgreSQL in `10.70.0.0/16`, extend connectivity, and compare self-managed versus managed deployment patterns.

### Stage 6 — Google Cloud Expansion

Build PostgreSQL in `10.80.0.0/16` using Compute Engine or Cloud SQL and extend the architecture without CIDR overlap.

---

## 17. Experience Outcome

The lab should provide enough operational evidence to explain:

- Why a dedicated GoldenGate hub was selected
- How remote capture and remote apply work
- How heterogeneous Oracle -> SQL Server migration differs from Oracle -> Oracle migration
- How one-way CDC is configured and validated
- How bidirectional replication changes the design
- How loops and write conflicts are controlled
- How GoldenGate behaves during service interruption and restart
- How to isolate network, host-firewall, application, database, and redo/archive failure domains
- How to diagnose FRA-related database stalls without killing critical background processes
- How to reconcile divergence
- How to design cutover and rollback
- How networking, security, credentials, and database privileges affect CDC
- How the architecture extends to AWS and GCP

Interview-level summary (updated October 2026):

> I built a cross-cloud lab that replicates Oracle AI Database 26ai on OCI into SQL Server 2022 on Azure through a dedicated GoldenGate 26ai hub. I set up the OCI-Azure IPsec/IKEv2 VPN with BGP, tracked down a pre-shared-key mismatch, worked through GoldenGate install and lifecycle failures, and diagnosed an FRA exhaustion that stalled redo archiving. I verified one-way INSERT, UPDATE and DELETE apply; sanitized target-side logs will be published after the rerun. AWS and Google Cloud PostgreSQL are planned, not built.
