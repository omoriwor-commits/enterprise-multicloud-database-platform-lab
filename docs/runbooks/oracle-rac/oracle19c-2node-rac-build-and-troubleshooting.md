# Oracle 19c 2-Node RAC Build and Troubleshooting Runbook

**Version:** Recovered from the user's existing RAC runbook and reviewed supplements  
**Platform:** Oracle Linux 8 + VirtualBox  
**Purpose:** Build and validate a repeatable Oracle 19c two-node RAC lab environment.

> Security note: passwords are intentionally omitted from this GitHub version. Use secure local values during execution.

---

## 1. Lab Design

### VirtualBox layout

```text
Adapter 1: Host-Only Adapter (192.168.56.x) — RAC Public Network
Adapter 2: Internal Network "privnet" (192.168.57.x) — Private Interconnect
Adapter 3: NAT (DHCP) — Internet Access
```

### Public network

```text
192.168.56.101  racnode1.com  racnode1
192.168.56.102  racnode2.com  racnode2
```

### VIP

```text
192.168.56.111  racnode1-vip.com
192.168.56.112  racnode2-vip.com
```

### SCAN

```text
192.168.56.120  rac-scan.com
```

For a lab without DNS, use a single SCAN IP. Prefer DNS in production-like environments.

### Private interconnect

```text
192.168.57.101  racnode1-priv
192.168.57.102  racnode2-priv
```

### Oracle network classification

```text
enp0s3  Public
enp0s8  Private Interconnect
enp0s9  NAT only — do not select as a Cluster network
```

### Filesystem layout

```text
/boot  1G
/      30G
swap   8G
/u01   60G
```

### Shared disks

```text
/dev/sdb  OCR/VOTING  20G
/dev/sdc  DATA        40G
/dev/sdd  FRA         20G
```

### Oracle software locations

```text
Grid Base:    /u01/app/grid
Grid Home:    /u01/app/19.0.0/grid
Oracle Base:  /u01/app/oracle
Oracle Home:  /u01/app/oracle/product/19.0.0/dbhome_1
Inventory:    /u01/app/oraInventory
```

---

## 2. Operating System Preparation

Install Oracle Linux 8 Minimal and Development Tools.

Install the Oracle prerequisite package:

```bash
dnf install -y oracle-database-preinstall-19c
```

Configure hostnames on each node as appropriate:

```bash
hostnamectl set-hostname racnode1.com
```

or:

```bash
hostnamectl set-hostname racnode2.com
```

Configure `/etc/hosts` with the public, VIP, SCAN, and private addresses shown above.

Validate name resolution before Grid installation:

```bash
getent hosts racnode1
getent hosts racnode2
getent hosts racnode1-vip
getent hosts racnode2-vip
getent hosts rac-scan
getent hosts racnode1-priv
getent hosts racnode2-priv
```

Configure and validate `chronyd`:

```bash
chronyc tracking
chronyc sources -v
```

Lab-only settings used in the original build included disabling `firewalld` and setting SELinux to permissive. These are not production recommendations.

Create required OS groups:

```text
oinstall
dba
oper
backupdba
dgdba
kmdba
asmdba
asmoper
asmadmin
```

Create users:

```text
grid
oracle
```

Create Oracle directories:

```bash
mkdir -p /u01/app/grid
mkdir -p /u01/app/19.0.0/grid
mkdir -p /u01/app/oracle
mkdir -p /u01/app/oracle/product/19.0.0/dbhome_1
mkdir -p /u01/app/oraInventory
```

Configure:

```text
kernel parameters
resource limits
PAM
udev
.bash_profile for grid and oracle
passwordless SSH between RAC nodes
```

ASM device aliases used in the lab:

```text
asm-disk1
asm-disk2
asm-disk3
```

For production, use persistent device identifiers. Simple `KERNEL=="sdX"` rules are suitable only for controlled labs.

---

## 3. Network Recovery with nmcli

If the network profiles need to be rebuilt, delete the old profiles first:

```bash
nmcli connection delete enp0s3
nmcli connection delete enp0s8
nmcli connection delete enp0s9
```

Example for `racnode2`:

```bash
nmcli connection add type ethernet ifname enp0s3 con-name enp0s3 \
  ipv4.method manual ipv4.addresses 192.168.56.102/24
nmcli connection modify enp0s3 ipv4.never-default yes
```

```bash
nmcli connection add type ethernet ifname enp0s8 con-name enp0s8 \
  ipv4.method manual ipv4.addresses 192.168.57.102/24
nmcli connection modify enp0s8 ipv4.never-default yes
```

```bash
nmcli connection add type ethernet ifname enp0s9 con-name enp0s9 \
  ipv4.method auto
```

Bring connections up:

```bash
nmcli connection up enp0s3
nmcli connection up enp0s8
nmcli connection up enp0s9
```

Validate:

```bash
ip addr
ip route
nmcli device status
```

Internet test:

```bash
ping -c 3 8.8.8.8
ping -c 3 google.com
```

For `racnode1`, use `.101` addresses instead of `.102` for the public and private interfaces.

---

## 4. Grid Infrastructure Preparation

Before installation verify:

```text
SSH
shared disks
ASM devices
public/private network
chronyd
name resolution
```

Install `cvuqdisk` as required.

Run cluster verification before Grid installation:

```bash
/u01/app/19.0.0/grid/runcluvfy.sh stage -pre crsinst
```

Launch Grid Infrastructure installer:

```bash
./gridSetup.sh
```

Choose:

```text
Configure Grid Infrastructure for a Cluster
Cluster Name: raccluster
ASM storage
OCR diskgroup
Public network:  192.168.56.x
Private network: 192.168.57.x
```

Run root scripts when prompted:

```text
orainstRoot.sh
grid/root.sh
```

Run on both nodes in the sequence instructed by the installer.

---

## 5. Grid / Cluster Validation

Validate Clusterware:

```bash
crsctl check crs
crsctl stat res -t
olsnodes -n
ocrcheck
crsctl query css votedisk
asmcmd lsdg
```

Expected ASM disk groups:

```text
OCR
DATA
FRA
```

---

## 6. Oracle Database Software Installation

As the Oracle software owner:

```bash
./runInstaller
```

Choose:

```text
Install database software only
Oracle Real Application Clusters database installation
```

Run the database-home root script on both nodes when prompted:

```bash
/u01/app/oracle/product/19.0.0/dbhome_1/root.sh
```

Verify the database home:

```bash
$ORACLE_HOME/bin/sqlplus -v
$ORACLE_HOME/OPatch/opatch lsinventory
```

---

## 7. DBCA — Create the Two-Node RAC Database

Launch DBCA on `racnode1` as `oracle`:

```bash
dbca
```

Choose:

```text
Create Database
Oracle Real Application Cluster (RAC) database
Administrator Managed
Advanced configuration
```

Database configuration:

```text
Global database name: RAC
Instance on node1:    RAC1
Instance on node2:    RAC2
Storage type:         ASM
Datafiles:            +DATA
Fast Recovery Area:   +FRA
Container Database:   YES
PDB name:             RACPDB1
Character set:        AL32UTF8
```

Use secure passwords locally; do not store database passwords in GitHub.

Example lab memory sizing from the recovered notes:

```text
SGA: 1024 MB
PGA: 512 MB
```

Review the DBCA summary and create the database.

---

## 8. Post-Build Database Validation

Connect as SYSDBA:

```bash
sqlplus / as sysdba
```

Run:

```sql
SELECT name, cdb FROM v$database;
SHOW PDBS;
SELECT instance_name, host_name
FROM gv$instance
ORDER BY inst_id;
SELECT name, open_mode
FROM v$pdbs;
```

Expected baseline:

```text
Database:  RAC
CDB:       YES
PDB:       RACPDB1
Instances: RAC1 and RAC2
```

Validate `srvctl`:

```bash
srvctl config database -d RAC
srvctl status database -d RAC
```

Validate Clusterware again:

```bash
crsctl stat res -t
```

Validate ASM contents:

```bash
asmcmd ls +DATA
asmcmd ls +FRA
```

---

## 9. DBCA Failure / Cleanup Procedure

If DBCA offers to revert a failed creation, choose **YES**.

Inspect ASM first:

```bash
asmcmd ls +DATA
asmcmd ls +FRA
```

Check whether RAC directories remain:

```bash
asmcmd ls +DATA/RAC
asmcmd ls +FRA/RAC
```

If stale RAC directories remain after confirming they belong only to the failed database creation:

```bash
asmcmd rm -rf +DATA/RAC
asmcmd rm -rf +FRA/RAC
```

Check local database residue:

```bash
ps -ef | grep pmon
cat /etc/oratab | grep RAC
ls $ORACLE_HOME/dbs | grep -i RAC
```

If stale database-home files remain:

```bash
rm -f $ORACLE_HOME/dbs/*RAC*
```

Check Clusterware database registration:

```bash
srvctl config database -d RAC
```

If a stale database configuration exists:

```bash
srvctl remove database -d RAC -force
```

Do not wipe OCR, voting, DATA, or FRA disks after Grid Infrastructure is successfully built unless intentionally rebuilding the entire cluster.

---

## 10. Final Validation Checklist

```bash
crsctl check crs
crsctl stat res -t
olsnodes -n
ocrcheck
crsctl query css votedisk
asmcmd lsdg
srvctl status database -d RAC
srvctl config database -d RAC
```

Recommended evidence capture:

```bash
mkdir -p /root/rac_build_evidence
```

Store validation outputs there during rebuild/troubleshooting sessions.

---

## 11. Build Rules Preserved from the Lab

1. **Grid first, database second.**
2. Keep one authoritative udev rules file.
3. Do not wipe OCR/data disks after Grid build unless rebuilding everything.
4. Install the database home using **Oracle Real Application Clusters database installation**.
5. Use **Advanced DBCA** for the first build.
6. Keep shared-disk mappings fixed and documented.
7. Validate Clusterware, OCR, voting disks, ASM, database registration, and both RAC instances before declaring the build complete.
8. Do not embed passwords in reusable documentation.

---

## 12. Source-Recovery Notes

This GitHub runbook was reconstructed from the user's existing `Oracle19c_RAC_Runbook_v2.txt` plus the reviewed/current-lab supplements. The current-lab correction is authoritative for networking: the private interconnect is `192.168.57.101/102`, not the older `10.0.0.101/102` values. The SCAN entry is the single lab SCAN IP `192.168.56.120`.
