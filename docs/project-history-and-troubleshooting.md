# Enterprise Multi-Cloud Database Platform Lab — Project History, Troubleshooting, and Current State

**Project:** Enterprise Data Platform / Multi-Cloud Migration & Replication Lab  
**Repository:** `enterprise-multicloud-database-platform-lab`  
**Chronology covered:** August 2026 through September 6, 2026  
**Purpose:** Preserve the engineering history of the lab, including architecture decisions, implementation work, incidents, evidence collected, root causes, remediations, validation, and unresolved work.

> Security note: passwords, pre-shared keys, private-key material, and other credentials are intentionally omitted from this public documentation.

---

## 1. Project Goal and Target Architecture

The lab was created to build a production-style heterogeneous database platform spanning multiple cloud providers and to practice migration, CDC, networking, database administration, failure analysis, security controls, and operational runbooks.

Primary topology:

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
        +----------------------+
        |                      |
        | Oracle remote        | SQL Server remote
        | capture/apply path   | apply/capture path
        |                      |
        v                      v
OCI Oracle                Azure SQL Server 2022
10.50.10.178              10.60.20.4

Future phases:
AWS PostgreSQL  10.70.0.0/16
GCP PostgreSQL  10.80.0.0/16
```

The selected GoldenGate model is a **dedicated hub with remote capture and remote apply**. The lab will first validate one-way Oracle-to-SQL Server CDC and later extend into bidirectional/active-active-style testing, conflict handling, restart/recovery, reconciliation, cutover, and rollback.

---

## 2. Initial Repository and Azure Foundation — August 21–25, 2026

The repository was initialized on August 21, 2026. The first implementation phase established the Azure landing zone and non-overlapping cloud CIDR plan.

### Azure governance and cost controls

Configured:

- Resource group: `rg-enterprise-data-platform-lab`
- Region: East US
- Monthly budget: `$50`
- Budget thresholds: 50%, 75%, 90%, 100%
- Tags:
  - `Environment=Lab`
  - `Project=EnterpriseDataPlatform`
  - `Workload=CrossCloudMigration`
  - `ManagedBy=Manual`

Paid Azure networking services such as Bastion, Firewall, and DDoS Network Protection were initially left disabled to preserve lab credits. Security instead relies on segmentation, NSGs, host firewalls, VPN routing, and source-restricted access.

### Cross-cloud CIDR standard

```text
OCI    10.50.0.0/16
Azure  10.60.0.0/16
AWS    10.70.0.0/16
GCP    10.80.0.0/16
```

This was established early to prevent future route overlap.

### Azure virtual network

Created:

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

A dedicated GoldenGate subnet was deliberately reserved instead of placing GoldenGate arbitrarily in an existing application or database subnet.

---

## 3. Azure SQL Server Build and DBA Baseline

A dedicated SQL Server VM was deployed in `snet-database`.

### Platform

```text
VM:               vm-sqlserver-lab-01
Private IP:       10.60.20.4
OS:               Windows Server 2022
Database:         SQL Server 2022 Developer
VM size:          Standard_D2as_v7
```

### Storage layout

```text
F:\data\     user database data files
G:\log\      user database log files
H:\tempDb\   tempdb files
```

A test database was created and its file placement verified:

```text
LabTestDB data: F:\data\LabTestDB.mdf
LabTestDB log:  G:\log\LabTestDB_log.ldf
```

### SQL Server configuration baseline

Validated/configured:

```text
MAXDOP                         2
max server memory             5120 MB
optimize for ad hoc workloads enabled
Instant File Initialization   enabled
TCP/IP                        enabled
Static SQL port               1433
```

SQL Server Authentication and Windows Authentication were tested. SQL Server Agent remains disabled because it is not currently needed for the GoldenGate connectivity phase.

### Network hardening

Database access was not exposed broadly. A specific NSG rule was created to permit Oracle-source-host testing to SQL Server:

```text
10.50.10.178/32 -> 10.60.20.4 TCP 1433
```

The lab explicitly avoids broad rules such as:

```text
0.0.0.0/0 -> TCP 1433
0.0.0.0/0 -> TCP 1521
```

---

## 4. OCI Source Baseline

### OCI compute/network

```text
Instance:    rotez_instance_oci
OS:          Oracle Linux 9.8
Shape:       VM.Standard.E5.Flex
Private IP:  10.50.10.178
VCN:         Rotez_hybrid-lab-vcn
VCN CIDR:    10.50.0.0/16
Subnet:      public-subnet-lab
Subnet CIDR: 10.50.10.0/24
```

The OCI source VNIC currently relies on the subnet security list plus the Oracle Linux firewall; no separate OCI NSG is attached to the VNIC.

### Oracle source database

Validated source state:

```text
Oracle AI Database 26ai Enterprise Edition
Version:                         23.26.1.0.0
CDB:                             CDB23AI
PDB:                             PDB23AI
PDB service:                     pdb23ai
Database role:                   PRIMARY
Open mode:                       READ WRITE
ARCHIVELOG:                      enabled
enable_goldengate_replication:   TRUE
minimal supplemental logging:    YES
Oracle listener:                 TCP 1521
```

GoldenGate is being designed around a **per-PDB Extract** using a local PDB user rather than a root common user.

For Oracle 23ai/26ai, the lab uses the modern role model rather than the older `DBMS_GOLDENGATE_AUTH.GRANT_ADMIN_PRIVILEGE` method. The capture account was validated with the appropriate capture role.

`STREAMS_POOL_SIZE` is currently left at `0`; it was not changed simply to satisfy old GoldenGate tuning patterns because the current per-PDB architecture does not require an unnecessary manual streams-pool setting.

---

## 5. OCI ↔ Azure Site-to-Site VPN and BGP

A route-based IPsec/IKEv2 VPN with BGP was implemented between OCI and Azure.

### Azure side

```text
VPN Gateway:  vng-enterprise-data-platform-lab
SKU:          VpnGw1AZ
VPN type:     Route-based
Azure ASN:    65515
```

### OCI side

```text
DRG:          drg-azure-hybrid-lab
Attachment:   att-rotez-hybrid-lab-vcn
CPE:          cpe-azure-vpn-gateway
IPSec:        ipsec-oci-azure-lab
Tunnel:       Azure-Tunnel-1
OCI ASN:      31898
IKE:          IKEv2
```

### Incident — VPN would not establish correctly

#### Symptoms

The tunnel did not establish as expected even though the basic configuration appeared structurally correct.

#### Troubleshooting

Azure Network Watcher and tunnel-health evidence were used to isolate the problem. The investigation validated:

- Azure VPN Gateway health
- OCI tunnel state
- IKE negotiation
- ESP/IPsec state
- BGP peer state
- Local Network Gateway configuration
- route propagation
- shared-key consistency

#### Root cause

The pre-shared key configured on the two sides did not match.

#### Resolution

The PSK was corrected so both peers used the same value.

#### Validation

After correction:

```text
IPSec tunnel: Up
IPv4 BGP:     Up
Azure peer:   Connected
Azure learns: 10.50.0.0/16
Azure advertises toward OCI: 10.60.0.0/16
```

End-to-end private connectivity from the OCI host to Azure SQL Server TCP 1433 was also validated.

This incident established the troubleshooting pattern used throughout the project:

```text
Detect -> Collect Evidence -> Isolate Failure Domain -> Root Cause -> Remediate -> Validate -> Document
```

---

## 6. Dedicated GoldenGate Hub Deployment in Azure

A dedicated Oracle Linux VM was deployed into the reserved GoldenGate subnet.

```text
VM:          vm-goldengate-lab-01
Private IP:  10.60.30.4
OS:          Oracle Linux 9.8
VM size:     Standard_D2as_v7
```

The GoldenGate subnet is associated with `nsg-goldengate-lab`.

Key intended flows:

```text
GoldenGate -> OCI Oracle      TCP 1521
GoldenGate -> Azure SQL       TCP 1433
Management -> GoldenGate      restricted SSH / management ports
```

A NAT Gateway was later associated with the GoldenGate subnet to provide outbound Internet access without making database listeners public.

A temporary public IP and source-restricted SSH access were introduced to support direct MobaXterm/X11 GUI work. This is a lab convenience and remains a hardening item; the target design is private/jump-host/VPN administration.

---

## 7. GoldenGate Remote Access and X11 Troubleshooting

### Initial access model

The GoldenGate VM originally had no direct public SSH path. Administration used the OCI VM as a jump host across the VPN.

Windows OpenSSH configuration used a ProxyCommand-style path from the workstation through OCI to the Azure GoldenGate private IP.

### Issue — Windows OpenSSH/X11 did not provide a usable DISPLAY

Native Windows OpenSSH successfully established SSH connectivity but did not create the expected X11 display environment for the Oracle GUI installers.

### Resolution

A temporary direct public-IP path was created with source-restricted NSG access. MobaXterm was then used with X11 forwarding.

Validation:

```text
DISPLAY=localhost:10.0
```

The GoldenGate installer and OGGCA GUI could then launch successfully.

### Security follow-up

The public IP and direct SSH rule are temporary. They should be removed after GUI-dependent configuration is complete.

---

## 8. First GoldenGate 26ai Installation and Post-Reboot Failure

GoldenGate 26ai Microservices was initially installed and configured with Service Manager plus the Administration, Distribution, Receiver, and Performance Metrics services.

After a reboot, Administration Server repeatedly crashed.

### Incident — Administration Server `std::bad_alloc`

#### Symptoms

Administration Server terminated during startup with an uncaught C++ exception:

```text
std::bad_alloc
```

The stack trace localized the failure around:

```text
trailfilecache::TrailFileCache
adminsrvr::TrailCache::initialize()
AdminServer::start()
```

#### Troubleshooting

The investigation checked:

- host RAM
- swap
- filesystem capacity
- GoldenGate logs
- core dump / stack trace
- repeated startup behavior

Host memory, swap, and disk capacity were healthy. The failure repeatedly occurred in the same Trail File Cache initialization path.

#### Decision / remediation

Because this was a fresh lab deployment and the failure appeared internal to the GoldenGate Administration Server rather than a host resource shortage, the deployment was deinstalled and rebuilt instead of spending excessive time on low-level binary debugging.

This was an intentional engineering tradeoff: preserve evidence, establish the failure locus, then rebuild a disposable lab deployment cleanly.

---

## 9. GoldenGate Reinstallation

The previous GoldenGate home was removed after deinstallation.

New software home:

```text
/u01/ogg26ai_home
```

New deployment name:

```text
DEP1
```

GoldenGate software installation completed successfully in silent mode. The Oracle inventory registered the new home.

### Issue — silent OGGCA response file rejected valid software home

A hand-edited response file was used with OGGCA silent mode and failed with:

```text
INS-85005
Specified GoldenGate software home invalid
```

However, the software home was known to be valid.

### Isolation

The GUI installer recognized the exact same software home without issue.

This proved that the installed GoldenGate home itself was not invalid. The problem was specific to the silent configuration path / response-file handling.

### Resolution

The configuration path was switched to the X11 GUI. The GUI generated a canonical OGGCA response file for the deployment, which was retained with restricted file permissions because it contains credentials.

---

## 10. Current GoldenGate 26ai Configuration

Service Manager configuration:

```text
Software Home:                     /u01/ogg26ai_home
Service Manager Deployment Home:  /u01/ogg26ai_deploy
Service Manager Port:             9011
Security:                         disabled for private lab
```

User deployment:

```text
Deployment Name:                  DEP1
OGG Deployment Home:              /u01/ogg26ai_sm
Administration Service:           9012
Distribution Service:             9013
Receiver Service:                 9014
Performance Metrics Service:      9015
Replication schema:               GGADMIN
Metrics datastore:                BDB
```

Important design distinction:

```text
Service Manager deployment tree: /u01/ogg26ai_deploy
DEP1 deployment tree:            /u01/ogg26ai_sm
```

These are intentionally separate.

---

## 11. Major Current Incident — OGGCA `INS-85038` During Daemon Registration

This is the primary unresolved GoldenGate issue as of September 6, 2026.

### Intended OGGCA sequence

The GUI configuration successfully reached:

```text
Create Deployment   -> Succeeded
Verify Deployment   -> Succeeded
Stop Deployment     -> requested
Register Service Manager as system service/daemon -> Pending
```

Then OGGCA failed with:

```text
INS-85038: Deployment removal failed
```

Detailed verification message:

```text
Verification failed.
Expected value: (NOT) 'running'
Actual value: 'running'

Verification failed for REST call to:
/services/v2/deployments/DEP1
```

### What the logs proved

The OGGCA logs showed that `DEP1` creation itself completed successfully:

```text
Deployment (DEP1) creation succeeded.
ALL DONE.
```

The stop REST request also returned success. OGGCA then immediately verified state and still saw `running`.

Service-level evidence showed:

- Administration Server stopped successfully.
- Distribution Server began stopping and actually exited normally, but Service Manager status lagged.
- Performance Metrics Server stopped successfully.
- Receiver Server began stopping and later exited normally.

Later task-history evidence in Service Manager resources showed the deployment services eventually completed with:

```text
status: stopped
exitCode: 0
```

Therefore the failure was not a permanent inability to stop the services.

### Root cause / best current interpretation

The evidence supports a **timing/state-reconciliation failure**:

```text
OGGCA sends stop request
        |
        v
Microservices begin normal shutdown
        |
        v
OGGCA checks deployment status before Service Manager has fully reconciled all child-service state
        |
        v
REST still reports deployment as running
        |
        v
OGGCA verification window expires
        |
        v
INS-85038
```

The stop request itself succeeded; OGGCA's verification occurred too early relative to service-state reconciliation.

### Why daemon registration did not complete

Oracle's daemon-registration workflow requires OGGCA to finish stopping the deployment before proceeding to the registration-script stage. Because OGGCA failed during stop verification, it never reached that stage.

Current filesystem evidence:

```text
/u01/ogg26ai_deploy
  etc/
  var/
```

There is no generated:

```text
/u01/ogg26ai_deploy/bin
registerServiceManager.sh
```

`systemctl` also shows no GoldenGate systemd service unit registered.

### Current process state

OS validation now shows **no DEP1 child microservices running**:

```bash
ps -ef | grep -E 'adminsrvr|distsrvr|recvsrvr|pmsrvr' | grep -v grep
```

Result: no processes.

Service Manager itself is still running:

```text
/u01/ogg26ai_home/bin/ServiceManager
PPID 1
```

Its cgroup placement showed that it is detached from the shell but is **not** managed by an `OracleGoldenGate.service` systemd unit.

### REST authorization observation

A later direct request to:

```text
/services/v2/deployments/DEP1
```

using the configured user returned:

```text
OGG-12062
Authenticated user is not authorized for this request
```

The authorization catalog endpoint itself was accessible and listed the available GoldenGate roles. This is being treated as a separate authorization/interface question and not as evidence that DEP1 is running.

### DNS/hostname check

The Service Manager hostname resolves correctly through Azure internal DNS:

```text
vm-goldengate-lab-01.internal.cloudapp.net -> 10.60.30.4
```

Therefore `/etc/hosts` is not the cause of `INS-85038`.

### Backup before further repair

Before any invasive repair, both GoldenGate configuration trees were backed up:

```text
/u01/ogg26ai_deploy
/u01/ogg26ai_sm
```

Backup archive:

```text
/home/azureuser/ogg_DEP1_before_daemon_fix_20260905.tar.gz
```

Runtime Unix sockets were correctly ignored by `tar`.

### Current status of this incident

**Not yet fully resolved.**

Verified state:

```text
GoldenGate software home        valid
DEP1 creation                    succeeded
DEP1 child services              stopped
Service Manager                  running
Systemd daemon registration      not completed
registerServiceManager.sh        not generated
Reinstall/recreate               NOT being performed yet
```

The next repair step is to verify the exact GoldenGate maintenance build and determine whether the installed version is affected by a known OGGCA daemon-registration/stop-state defect before deciding between patching and a controlled configuration retry.

---

## 12. GoldenGate Web-Access Troubleshooting

GoldenGate management services responded locally but initially could not be reached from the administrator workstation.

### Isolation path

```text
Workstation
   -> Azure public IP / routing
   -> Azure NSG
   -> Oracle Linux firewalld
   -> GoldenGate management service
```

### Remediation

The required GoldenGate management ports were opened in the active Oracle Linux firewall zone and Azure NSG rules were restricted to the administrator's source IP rather than the entire Internet.

Remote GoldenGate web access was then validated.

### Security note

The lab currently uses non-TLS management during build/troubleshooting. TLS/HTTPS is a required hardening task before this is treated as production-like.

---

## 13. Oracle Source Connectivity from GoldenGate

The OCI security list permits the Azure GoldenGate subnet to reach Oracle listener TCP 1521.

From the Azure GoldenGate VM, TCP connectivity to the Oracle source was validated successfully:

```text
10.60.30.4 -> 10.50.10.178:1521
```

This proves the cross-cloud path for the future Oracle GoldenGate source connection:

```text
GoldenGate VM
  -> Azure VNet
  -> Azure VPN Gateway
  -> IPsec/IKEv2 tunnel
  -> OCI DRG
  -> OCI VCN
  -> OCI security controls
  -> Oracle listener
```

The current GoldenGate deployment environment references:

```text
TNS_ADMIN=/u01/ogg26ai_home/network/admin
```

That directory did not originally exist and was created later. A `tnsnames.ora` alias still needs to be deliberately configured and validated before `DBLOGIN` / Extract configuration. This is a separate replication-preparation task and did **not** cause `INS-85038`.

---

## 14. Oracle Database Hang / FRA Exhaustion Incident

During Oracle-source preparation, an administrative SQL statement appeared to hang.

### Symptom

A foreground operation such as account/password management did not return promptly.

Database wait analysis showed many sessions waiting on:

```text
log file switch (archiving needed)
```

Multiple sessions pointed to a blocking session that mapped to the Oracle `LGWR` background process.

### Troubleshooting evidence

The investigation used:

- `V$SESSION`
- `V$PROCESS`
- `ARCHIVE LOG LIST`
- `V$RECOVERY_FILE_DEST`
- `V$ARCHIVE_DEST`
- `V$ARCHIVE_DEST_STATUS`
- `df -h`
- `du -sh`

### Root cause

The Fast Recovery Area was configured as:

```text
db_recovery_file_dest      = /u03/fra
db_recovery_file_dest_size = 10G
```

Oracle reported the FRA effectively at its configured quota, with no immediately reclaimable space, and the archive destination reported:

```text
ORA-19809: limit exceeded for recovery files
```

The underlying Linux filesystem still had significant free space. This proved the issue was **Oracle FRA quota exhaustion**, not a physically full filesystem.

### Failure chain

```text
FRA reaches configured limit
        -> ARCn cannot archive redo
        -> completed online redo cannot be reused
        -> LGWR cannot progress through log switch
        -> sessions wait on "log file switch (archiving needed)"
        -> SQL operations appear hung
```

### Correct remediation approach

The safe recovery path is:

1. Increase the FRA quota when filesystem capacity permits.
2. Force/retest archival.
3. Confirm the archive destination clears the error.
4. Review FRA contents with RMAN.
5. Delete obsolete/expired or safely backed-up recovery files through RMAN, not by blindly deleting files from the operating system.

Representative commands used/planned:

```sql
ALTER SYSTEM SET db_recovery_file_dest_size=20G SCOPE=BOTH;
ALTER SYSTEM ARCHIVE LOG CURRENT;
```

RMAN validation/cleanup workflow:

```text
SHOW RETENTION POLICY;
REPORT OBSOLETE;
CROSSCHECK ARCHIVELOG ALL;
DELETE EXPIRED ARCHIVELOG ALL;
```

The important operational lesson was not to kill `LGWR`. `LGWR` was the visible blocker in the wait chain, but the root cause was downstream archive/FRA capacity pressure.

---

## 15. Oracle GoldenGate Source Account / Capture Preparation

The GoldenGate database user in `PDB23AI` was validated as open and usable.

The design uses Oracle 23ai/26ai role-based GoldenGate privileges. Capture is prepared around the appropriate capture role rather than the deprecated/disabled legacy admin-privilege package path.

Candidate replication object:

```text
HOLA.FOX
```

The GoldenGate user successfully queried the object remotely and observed 14 rows.

Still pending before Extract creation:

```text
ADD TRANDATA HOLA.FOX
```

or broader schema-level supplemental logging if the final replication scope requires it.

---

## 16. What Has Been Validated End-to-End

The following infrastructure paths have been proven independently:

```text
OCI Oracle VM -> Azure SQL Server TCP 1433           PASS
Azure GoldenGate VM -> OCI Oracle TCP 1521           PASS
Azure internal DNS for GoldenGate hostname           PASS
OCI <-> Azure IPsec/IKEv2                            UP
OCI <-> Azure BGP                                    UP
Azure learns OCI 10.50.0.0/16                        PASS
OCI/Azure route path for lab networks                PASS
GoldenGate software installation                     PASS
DEP1 creation                                        PASS
DEP1 shutdown at OS level                            PASS
```

The remaining blocker before advancing into replication configuration is the incomplete Oracle-supported Service Manager daemon-registration workflow.

---

## 17. Issues Encountered and Engineering Outcomes

| Incident | Failure Domain | Root Cause / Best Evidence | Outcome |
|---|---|---|---|
| OCI↔Azure VPN initially unhealthy | Network/security | PSK mismatch | Corrected; IPsec and BGP validated Up |
| Native Windows SSH unsuitable for OGGCA GUI X11 | Management tooling | X11 display not established as needed | MobaXterm direct X11 path used |
| First GoldenGate Admin Server crash after reboot | GoldenGate runtime | Repeated `std::bad_alloc` in TrailFileCache initialization; host resources healthy | Clean deinstall/reinstall chosen |
| Silent OGGCA `INS-85005` | Configuration tooling | Hand-edited response path rejected otherwise valid software home | Switched to GUI; home validated |
| GoldenGate web UI inaccessible remotely | Network/host firewall | NSG/firewalld path not fully open | Source-restricted management rules added |
| OGGCA `INS-85038` during daemon registration | GoldenGate lifecycle/state reconciliation | Stop succeeded but OGGCA verified `running` before all service state reconciled | DEP1 now stopped; daemon registration still unresolved |
| `/services/v2/deployments/DEP1` returns `OGG-12062` for tested user | GoldenGate authorization | Authenticated user lacks authorization for that resource | Separate authorization check; not treated as DEP1 runtime evidence |
| Oracle SQL operations appeared hung | Oracle redo/archive/FRA | FRA quota exhausted; ARCn unable to archive; LGWR waits | FRA capacity/RMAN remediation path established |
| Current `TNS_ADMIN` points to initially absent directory | GoldenGate DB connectivity preparation | Network admin directory/tnsnames not yet built | Directory created; alias/config still pending |

---

## 18. Current State — September 6, 2026

### Completed / validated

- Azure resource group, VNet, subnet segmentation, NSGs, budget controls
- SQL Server 2022 VM and baseline DBA configuration
- SQL listener on TCP 1433
- OCI Oracle 26ai source baseline
- OCI↔Azure site-to-site VPN
- IKEv2/IPsec tunnel health
- BGP adjacency and route exchange
- OCI Oracle -> Azure SQL TCP connectivity
- Dedicated Azure GoldenGate hub VM
- NAT-based GoldenGate outbound access
- Temporary source-restricted direct SSH/X11 path
- GoldenGate 26ai software reinstallation
- `DEP1` creation
- Azure GoldenGate -> OCI Oracle listener connectivity
- Oracle GoldenGate source account baseline
- Evidence-driven FRA incident RCA
- Backup of GoldenGate Service Manager and DEP1 configuration before further daemon-repair work

### Active blocker

```text
OGGCA INS-85038 during deployment stop verification
        -> OGGCA never reached daemon-registration script stage
        -> OracleGoldenGate systemd service not registered
```

### Replication tasks not yet completed

- GoldenGate credential-store alias
- validated `DBLOGIN USERIDALIAS`
- `tnsnames.ora` / TNS alias validation
- `ADD TRANDATA` / `ADD SCHEMATRANDATA`
- Extract registration
- Extract process
- local/remote trail configuration
- SQL Server GoldenGate target connectivity/ODBC preparation
- target schema/datatype conversion
- Replicat
- Oracle-to-SQL Server INSERT/UPDATE/DELETE CDC test
- reconciliation
- cutover/rollback test
- bidirectional replication
- TLS hardening of GoldenGate management plane
- removal of temporary direct public administration path
- AWS PostgreSQL phase

---

## 19. Immediate Next Engineering Step

Do **not** reinstall or delete `DEP1` merely because the OGGCA GUI reported `INS-85038`.

The evidence already proves that:

```text
DEP1 was created successfully
all DEP1 microservices can stop cleanly
Service Manager remains available
systemd registration alone is incomplete
```

The next controlled step is to identify the exact installed GoldenGate maintenance build and compare it against Oracle's fixes for OGGCA Service Manager daemon-registration / stop-verification defects. If the installed build is affected, patching the GoldenGate home should be evaluated before any destructive recreate path.

After the daemon-registration issue is resolved, resume the replication workstream in this order:

```text
Oracle source health
-> TNS / DBLOGIN
-> credential store
-> TRANDATA
-> Extract
-> trail
-> SQL Server target preparation
-> Replicat
-> initial load / CDC
-> reconciliation
-> cutover and rollback
```

---

## 20. Engineering Principles Demonstrated by the Lab

This project deliberately records failures rather than hiding them. The objective is to demonstrate how a database/platform engineer reasons through failures:

```text
1. Establish the intended architecture.
2. Build with least-privilege network boundaries.
3. Validate one layer at a time.
4. Capture logs, waits, process state, routes, sockets, and service state.
5. Separate symptoms from root cause.
6. Avoid destructive actions until evidence justifies them.
7. Validate the fix at the same layer where failure was observed.
8. Preserve a rollback path and configuration backup.
9. Document the RCA and operational lesson.
```

That methodology has already been applied to VPN negotiation, GoldenGate lifecycle failures, remote management access, X11 tooling, Oracle FRA exhaustion, and cross-cloud listener connectivity.
