# Enterprise Data Platform Lab — Multi-Cloud Migration & Replication Plan

**Checkpoint Date:** September 6, 2026  
**Project:** Enterprise Data Platform / Multi-Cloud Migration & Replication Lab

## 1. Target Architecture

```text
OCI
Oracle Database
10.50.0.0/16
      |
      |  Route-based IPsec/IKEv2 + BGP
      v
Azure
Dedicated Oracle GoldenGate 26ai Hub
10.60.30.0/24
      |
      |  Remote apply / later reverse capture
      v
Azure SQL Server 2022
10.60.20.0/24
      |
      |  Later migration / replication
      v
AWS
PostgreSQL Platform
10.70.0.0/16
      |
      |  Later expansion / comparison
      v
Google Cloud
PostgreSQL Platform
10.80.0.0/16
```

GoldenGate deployment model:

```text
Model 4 — Dedicated hub with remote capture and remote apply
```

The lab will practice:

- Unidirectional CDC
- Bidirectional / active-active-style replication patterns
- Failure, restart, lag, conflict, reconciliation, cutover, and rollback scenarios

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

The OCI VNIC currently uses the subnet security list plus the Oracle Linux host firewall.

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
```

The Oracle listener advertises `pdb23ai` and is reachable privately from the Azure GoldenGate VM.

---

## 3. Azure Foundation and Cost Controls

Resource group:

```text
rg-enterprise-data-platform-lab
Region: East US
```

Tags:

```text
Environment = Lab
Project     = EnterpriseDataPlatform
Workload    = CrossCloudMigration
ManagedBy   = Manual
```

Budget:

```text
budget-enterprise-data-platform-lab
Monthly budget: $50
Thresholds: 50%, 75%, 90%, 100%
```

Paid networking services intentionally not used unless required:

```text
Azure Bastion                 Disabled
Azure Firewall                Disabled
Azure DDoS Network Protection Disabled
```

Security controls rely on NSGs, host firewalls, private subnetting, VPN routing, and least-privilege source/destination rules.

---

## 4. Cross-Cloud IP Addressing Standard

```text
OCI      10.50.0.0/16
Azure    10.60.0.0/16
AWS      10.70.0.0/16
GCP      10.80.0.0/16
```

The addressing plan avoids CIDR overlap and supports routed multi-cloud connectivity.

---

## 5. Azure Network

VNet:

```text
vnet-enterprise-data-platform-lab
10.60.0.0/16
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

OCI ↔ Azure connectivity is established using IPsec/IKEv2 and BGP.

Validated routing state:

```text
Azure learns OCI:      10.50.0.0/16
Azure advertises:      10.60.0.0/16
IPSec:                 Up
IPv4 BGP:              Up
VPN diagnostics:       Healthy
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

Storage layout:

```text
F:\data\     user database data files
G:\log\      user database log files
H:\tempDb\   tempdb files
```

Test database:

```text
LabTestDB
Data file: F:\data\LabTestDB.mdf
Log file:  G:\log\LabTestDB_log.ldf
```

Private OCI Oracle VM → Azure SQL Server connectivity on TCP 1433 has been validated successfully.

---

## 7. GoldenGate Hub — Deployed

The dedicated GoldenGate hub is no longer a future item; it is deployed and operational.

```text
VM:            vm-goldengate-lab-01
Private IP:    10.60.30.4
OS:            Oracle Linux 9.8
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

Service Manager is registered as a Linux `systemd` service.

### GoldenGate Web Access

Local validation:

```text
9011 HTTP=200
9012 HTTP=200
```

Remote web access was initially blocked by the Azure inbound path. The final management path is:

```text
Administrator workstation
        -> Azure public IP
        -> Azure NSG
        -> Oracle Linux firewalld
        -> GoldenGate Service Manager :9011
```

Linux firewall rules were added for controlled management access on TCP 9011-9012, and the Azure NSG rule was restricted to the administrator public IP `/32` rather than `0.0.0.0/0`.

> TLS/HTTPS remains a management-plane hardening task.

---

## 8. GoldenGate OGGCA Incident — Root Cause and Resolution

During OGGCA deployment configuration, validation failed with:

```text
Verification failed.
Expected value: (NOT) 'running'
actual value: 'running'
```

Investigation showed that Service Manager could stop while `adminsrvr`, `distsrvr`, `recvsrvr`, and `pmsrvr` remained active and listening on ports 9012-9015. The detached services were observed with PPID 1.

Troubleshooting used:

```text
systemctl status OracleGoldenGate
ps -ef
/proc/<PID>/cgroup
ss -lntp
GoldenGate Admin Client
OGGCA logs
```

Controlled remediation:

```text
CONNECT http://127.0.0.1:9011 DEPLOYMENT DEP1 AS oggadmin
STOP ER *
STOP DISTPATH ALL
STOP SERVICE *
STATUS SERVICE *
```

Service Manager was then stopped cleanly with systemd, the OS state was verified, and OGGCA was rerun.

Final result:

```text
Start Service Manager                         Succeeded
Verify Service Manager                        Succeeded
Add Service Manager Administrator User        Succeeded
Install Plugin Service in Service Manager     Succeeded
Create Deployment                             Succeeded
Verify Deployment                             Succeeded
Stop Deployment                               Succeeded
Register Service Manager as a system service  Succeeded
```

After configuration, the GoldenGate deployment Microservices were again children of the active Service Manager process.

---

## 9. GoldenGate Hub → OCI Oracle Connectivity

The GoldenGate VM route to the OCI Oracle source was validated:

```text
Source:      10.60.30.4
Destination: 10.50.10.178
Next hop:    10.60.30.1
Interface:   eth0
```

TCP listener validation:

```text
GoldenGate 10.60.30.4
        -> IPSec/BGP
        -> OCI Oracle 10.50.10.178:1521

Result: TCP 1521 SUCCESS
```

A second test confirmed connection establishment to TCP 1521 with `curl telnet://`.

This proves the cross-cloud network path to the Oracle listener before GoldenGate Extract configuration.

---

## 10. Oracle FRA Incident — Database Hang During GoldenGate Preparation

While validating the Oracle GoldenGate database account, an `ALTER USER` statement appeared to hang.

### Symptoms

Many sessions were waiting on:

```text
log file switch (archiving needed)
```

The repeated `BLOCKING_SESSION` value was SID 16. Investigation identified SID 16 as the Oracle `LGWR` background process.

### Root Cause

The Fast Recovery Area was at its configured quota:

```text
db_recovery_file_dest      = /u03/fra
db_recovery_file_dest_size = 10G
FRA used                   = 9.88G
FRA reclaimable            = 0G
```

Archive destination status:

```text
STATUS: ERROR
ORA-19809: limit exceeded for recovery files
```

The Linux filesystem itself was not full:

```text
Filesystem size: 83G
Used:            54G
Available:       30G
```

Physical FRA usage included:

```text
/u03/fra/CDB23AI   ~9.9G
/u03/fra/RMAN26    ~7.9G
```

Failure chain:

```text
FRA reaches configured quota
        -> archiver cannot archive completed redo
        -> online redo log cannot be reused
        -> LGWR waits for log switch
        -> sessions wait on "log file switch (archiving needed)"
        -> foreground DDL appears to hang
```

### Remediation Plan

Immediate recovery:

```sql
ALTER SYSTEM SET db_recovery_file_dest_size=20G SCOPE=BOTH;
ALTER SYSTEM ARCHIVE LOG CURRENT;
```

Then validate archive destination status and confirm the wait condition clears.

Permanent cleanup should be performed with RMAN rather than deleting recovery files manually from the filesystem:

```text
SHOW RETENTION POLICY;
REPORT OBSOLETE;
LIST BACKUP OF ARCHIVELOG ALL;
CROSSCHECK ARCHIVELOG ALL;
DELETE EXPIRED ARCHIVELOG ALL;
```

Delete obsolete/backed-up recovery files only after RMAN validation.

### Troubleshooting Methodology

```text
Detect
-> Collect Evidence
-> Isolate Failure Domain
-> Root Cause
-> Remediate
-> Validate
-> Document RCA
```

No critical Oracle background process was killed. In particular, `LGWR` was identified as a symptom-bearing blocker, not the root cause.

---

## 11. Current Security Controls

### GoldenGate NSG

```text
nsg-goldengate-lab
Associated subnet: snet-goldengate 10.60.30.0/24
```

Key controls:

```text
Management subnet -> GoldenGate TCP 22
GoldenGate subnet -> SQL Server 10.60.20.4 TCP 1433
GoldenGate subnet -> OCI Oracle 10.50.10.178 TCP 1521
Restricted administrator source -> GoldenGate TCP 9011-9012
```

### OCI Listener Security

OCI security-list ingress allows:

```text
10.60.30.0/24 -> TCP 1521
```

### Database Exposure Standard

Avoid:

```text
0.0.0.0/0 -> TCP 22
0.0.0.0/0 -> TCP 1433
0.0.0.0/0 -> TCP 1521
```

Use private CIDRs and least-privilege source/destination rules.

---

## 12. Current Project Status

### Completed

- [x] Azure subscription and cost controls
- [x] Resource group and governance tags
- [x] Cross-cloud CIDR design
- [x] Azure VNet and subnet architecture
- [x] Database NSG
- [x] SQL Server VM deployment
- [x] SQL Server 2022 DBA baseline
- [x] SQL Server static listener TCP 1433
- [x] OCI ↔ Azure Site-to-Site VPN
- [x] OCI DRG and VCN attachment
- [x] Azure VPN Gateway
- [x] IPsec/IKEv2 tunnel
- [x] BGP session and route exchange
- [x] OCI Oracle -> Azure SQL Server TCP 1433 validation
- [x] GoldenGate subnet and NSG
- [x] Dedicated GoldenGate hub compute
- [x] GoldenGate 26ai Microservices installation
- [x] DEP1 deployment
- [x] Service Manager systemd registration
- [x] Administration, Distribution, Receiver, and Metrics services validated
- [x] GoldenGate web interface access validated
- [x] OGGCA stop-state incident diagnosed and resolved
- [x] OCI Oracle source baseline validated
- [x] Oracle FORCE LOGGING enabled
- [x] Minimal supplemental logging validated
- [x] `enable_goldengate_replication=TRUE` validated
- [x] OCI Oracle listener service `pdb23ai` validated
- [x] GoldenGate hub -> OCI Oracle TCP 1521 validated
- [x] Oracle FRA exhaustion incident root cause identified

### In Progress

- [ ] Restore/validate Oracle FRA and archive health
- [ ] Clean FRA safely using RMAN
- [ ] Validate GoldenGate database account privileges
- [ ] Configure GoldenGate credential store / database connection
- [ ] Configure Oracle Extract
- [ ] Configure trail files
- [ ] Prepare SQL Server schema mapping
- [ ] Configure SQL Server Replicat
- [ ] Initial load and CDC validation

### Future Phases

- [ ] Bidirectional Oracle ↔ SQL Server replication
- [ ] Loop-prevention testing
- [ ] Conflict detection/resolution testing
- [ ] Replication failure/restart testing
- [ ] AWS PostgreSQL environment
- [ ] Azure/OCI ↔ AWS connectivity
- [ ] PostgreSQL migration/replication
- [ ] Google Cloud PostgreSQL environment
- [ ] Multi-cloud PostgreSQL comparison
- [ ] Monitoring and operational runbooks
- [ ] Backup/recovery validation
- [ ] Cutover/rollback testing

---

## 13. Immediate Next Step

The GoldenGate hub is already deployed, so the previous checkpoint's instruction to deploy the hub is complete.

The immediate sequence is now:

```text
1. Resolve Oracle FRA pressure and confirm archiving is healthy
2. Validate the dedicated GoldenGate Oracle database account
3. Configure GoldenGate database credentials
4. Test GoldenGate database login to PDB23AI
5. Configure Oracle Extract
6. Configure trail files
7. Prepare SQL Server schema and target credentials
8. Configure Replicat
9. Perform initial load and CDC validation
```

The next technical gate is **healthy Oracle redo/archive processing**. GoldenGate capture configuration should not proceed while the source database is experiencing archive destination errors.

---

## 14. Migration and Replication Method

Because Oracle and SQL Server are heterogeneous platforms, the migration will not use RMAN, Data Guard, or a direct Data Pump restore into SQL Server.

| Phase | Method | Objective |
|---|---|---|
| Assessment | SQL Server Migration Assistant for Oracle or equivalent tooling | Identify datatype, PL/SQL, object, and compatibility gaps |
| Schema conversion | Oracle-to-SQL Server conversion | Build equivalent SQL Server schema |
| Initial load | Bulk / migration tooling | Establish synchronized baseline data |
| CDC | Oracle GoldenGate | Capture and apply ongoing transactional changes |
| Validation | Row counts, object checks, sample reconciliation, transaction testing | Prove target correctness |
| Cutover | Controlled write stop, drain replication, final validation | Practice near-zero-downtime transition |
| Rollback | Preserve source and reverse operational decision if required | Demonstrate recovery discipline |

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

## 15. Hands-On Execution Plan

### Stage 1 — Secure Connectivity — Completed

- OCI ↔ Azure routing and VPN
- NSGs/security lists
- Listener access
- Oracle TCP 1521 validation
- SQL Server TCP 1433 validation

### Stage 2 — GoldenGate Hub — Substantially Completed

- Dedicated VM deployed
- GoldenGate Microservices installed
- DEP1 configured
- Web interface validated
- Remote Oracle network path validated

Remaining:

- Database credential configuration
- Extract configuration
- Target SQL Server GoldenGate connectivity

### Stage 3 — Unidirectional Replication

```text
OCI Oracle -> Azure SQL Server
```

Practice:

- Schema assessment and conversion
- Initial data load
- Remote capture
- Remote apply
- INSERT / UPDATE / DELETE replication
- Checkpoint and lag monitoring
- Process stop/start
- Failure recovery
- Data reconciliation
- Cutover and rollback drill

### Stage 4 — Bidirectional Replication

```text
OCI Oracle <-> Azure SQL Server
```

Practice:

- Capture/apply in both directions
- Loop prevention
- Key/sequence/identity strategy
- Simultaneous updates
- Conflict scenarios
- Conflict-resolution strategy
- Restart after outage
- Reconciliation after divergence

### Stage 5 — AWS Expansion

Build PostgreSQL in `10.70.0.0/16`, extend connectivity, and compare self-managed versus managed database options.

### Stage 6 — Google Cloud Expansion

Build PostgreSQL in `10.80.0.0/16` using Compute Engine or Cloud SQL and extend the architecture without CIDR overlap.

---

## 16. Experience Outcome

The lab is intended to produce operational evidence sufficient to explain:

- Why the dedicated GoldenGate hub model was selected
- How remote capture and remote apply work
- How heterogeneous Oracle → SQL Server migration differs from Oracle → Oracle migration
- How one-way CDC is configured and validated
- How bidirectional replication changes the design
- How loops and write conflicts are controlled
- How GoldenGate behaves during interruption and restart
- How to diagnose infrastructure and database-side blocking conditions
- How to detect and reconcile divergence
- How to design cutover and rollback
- How networking, security, credentials, and database privileges affect CDC
- How the architecture can extend across OCI, Azure, AWS, and Google Cloud

Interview-level project summary:

> Built a heterogeneous multi-cloud database migration and replication lab spanning OCI Oracle, Azure SQL Server, Oracle GoldenGate, AWS PostgreSQL, and Google Cloud PostgreSQL. Implemented OCI-Azure IPsec/BGP connectivity, deployed a dedicated GoldenGate 26ai Microservices hub with remote database connectivity, validated source and target network paths, and performed production-style troubleshooting of GoldenGate lifecycle, Azure access-control, and Oracle FRA/redo incidents. The lab is progressing into Oracle-to-SQL Server CDC, followed by bidirectional replication, failure recovery, conflict handling, reconciliation, cutover, and rollback testing.
