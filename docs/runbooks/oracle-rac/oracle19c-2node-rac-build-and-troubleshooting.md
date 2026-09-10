# Oracle 19c 2-Node RAC Build — Simple Real-World Runbook

**Status:** Tested and reused in the user's RAC lab.  
**Purpose:** Build Oracle 19c 2-node RAC from scratch in a clean, repeatable way.  
**Security:** Database passwords from the verified local runbook have been replaced with placeholders before publishing to GitHub.

---

## Assumptions

```text
Node1: racnode1
Node2: racnode2
```

### Partition Layout

| Mount Point | Size | Purpose |
|---|---:|---|
| `/boot` | 1 GB | Boot files |
| `/` | 30 GB | Operating system |
| `/u01` | 60 GB | Oracle software (Grid + DB homes) |
| `swap` | 8 GB | Swap |

Install:

```text
Development Tools
Graphical Administration Tools (optional but useful)
```

### Shared Disks

```text
/dev/sdb = OCR   (20G)
/dev/sdc = DATA  (40G)
/dev/sdd = FRA   (20G)
```

Check the Oracle preinstall package:

```bash
rpm -q oracle-database-preinstall-19c
```

If not installed:

```bash
dnf install -y oracle-database-preinstall-19c
```

### Software Paths

```text
Grid Home:  /u01/app/19.0.0/grid
Grid Base:  /u01/app/grid
DB Home:    /u01/app/oracle/product/19.0.0/dbhome_1
DB Base:    /u01/app/oracle
Inventory:  /u01/app/oraInventory
```

---

# Phase 1 — OS Prep on Both Nodes

## 1. Set Hostname

On node1:

```bash
hostnamectl set-hostname racnode1
```

On node2:

```bash
hostnamectl set-hostname racnode2
```

## 2. Update `/etc/hosts` on Both Nodes

Add:

```text
127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4
::1         localhost localhost.localdomain localhost6 localhost6.localdomain6

# Public
192.168.56.101  racnode1
192.168.56.102  racnode2

# VIP
192.168.56.111  racnode1-vip
192.168.56.112  racnode2-vip

# SCAN
192.168.56.120  rac-scan
192.168.56.121  rac-scan
192.168.56.122  rac-scan

# Private interconnect
192.168.57.101  racnode1-priv
192.168.57.102  racnode2-priv
```

## 3. Test Name Resolution

From both nodes:

```bash
getent hosts racnode1
getent hosts racnode2
getent hosts racnode1-vip
getent hosts racnode2-vip
getent hosts rac-scan
ping -c 3 racnode1
ping -c 3 racnode2
ping -c 3 racnode1-priv
ping -c 3 racnode2-priv
```

## 4. Configure Time Sync

On both nodes:

```bash
systemctl enable chronyd
systemctl start chronyd
chronyc tracking
chronyc sources -v
```

Do not continue until time synchronization looks healthy.

## 5. Disable Firewall and Set SELinux Permissive — Lab Only

```bash
systemctl stop firewalld
systemctl disable firewalld
setenforce 0
```

Edit:

```text
/etc/selinux/config
```

Set:

```text
SELINUX=permissive
```

> This is a lab procedure. Do not blindly disable these controls in a real environment.

---

# Phase 2 — Users, Groups, Kernel, Limits

Check existing groups:

```bash
grep -E "oinstall|dba|oper|asm|backupdba|dgdba|kmdba" /etc/group
```

## 6. Create Groups on Both Nodes

```bash
groupadd -g 54321 oinstall
groupadd -g 54322 dba
groupadd -g 54323 oper
groupadd -g 54324 backupdba
groupadd -g 54325 dgdba
groupadd -g 54326 kmdba
groupadd -g 54327 asmdba
groupadd -g 54328 asmoper
groupadd -g 54329 asmadmin
```

Verify:

```bash
grep -E "oinstall|dba|oper|asm" /etc/group
```

## 7. Create Users on Both Nodes

```bash
useradd -u 54330 -g oinstall -G asmadmin,asmdba,asmoper,dba grid
usermod -u 54331 -g oinstall -G dba,oper,backupdba,dgdba,kmdba,asmdba oracle
```

If ownership from an older UID must be corrected in the lab:

```bash
find / -user 1000 -exec chown oracle:oinstall {} \; 2>/dev/null
```

Verification:

```bash
id grid
id oracle

getent passwd grid
getent passwd oracle

getent group oinstall
getent group dba
getent group oper
getent group backupdba
getent group dgdba
getent group kmdba
getent group asmdba
getent group asmoper
getent group asmadmin
```

Set local passwords interactively:

```bash
passwd grid
passwd oracle
```

## 8. Set Kernel Parameters on Both Nodes

Edit `/etc/sysctl.conf` and add:

```text
fs.aio-max-nr = 1048576
fs.file-max = 6815744
kernel.shmall = 1073741824
kernel.shmmax = 4398046511104
kernel.shmmni = 4096
kernel.sem = 250 32000 100 128
net.ipv4.ip_local_port_range = 9000 65500
net.core.rmem_default = 262144
net.core.rmem_max = 4194304
net.core.wmem_default = 262144
net.core.wmem_max = 1048576
```

Apply:

```bash
sysctl -p
```

## 9. Set Limits on Both Nodes

Edit `/etc/security/limits.conf` and add:

```text
grid   soft   nproc    2047
grid   hard   nproc    16384
grid   soft   nofile   1024
grid   hard   nofile   65536
grid   soft   stack    10240
grid   hard   stack    32768

oracle soft   nproc    2047
oracle hard   nproc    16384
oracle soft   nofile   1024
oracle hard   nofile   65536
oracle soft   stack    10240
oracle hard   stack    32768
```

## 10. Verify `pam_limits`

Check:

```text
/etc/pam.d/login
/etc/pam.d/sshd
```

Ensure:

```text
session required pam_limits.so
```

---

# Phase 3 — Directories

## 11. Create Directories on Both Nodes

```bash
mkdir -p /u01/app/19.0.0/grid
mkdir -p /u01/app/grid
mkdir -p /u01/app/oracle/product/19.0.0/dbhome_1
mkdir -p /u01/app/oracle
mkdir -p /u01/app/oraInventory
```

## 12. Set Ownership

```bash
chown -R grid:oinstall /u01/app/19.0.0
chown -R grid:oinstall /u01/app/grid
chown -R oracle:oinstall /u01/app/oracle
chown -R grid:oinstall /u01/app/oraInventory

chmod -R 775 /u01/app
chmod 755 /u01
```

Verify:

```bash
ls -ld /u01
ls -ld /u01/app
ls -ld /u01/app/*
ls -ld /u01/app/19.0.0/grid
ls -ld /u01/app/oracle/product/19.0.0/dbhome_1
```

Final permission check:

```bash
namei -om /u01/app/19.0.0/grid
namei -om /u01/app/oracle/product/19.0.0/dbhome_1
```

---

# Phase 4 — Shared Disks and UDEV

## 13. Confirm Shared Disks on Both Nodes

```bash
lsblk
```

Expected:

```text
sdb
sdc
sdd
```

## 14. Clean Disks Once Before Build

Only if rebuilding from scratch:

```bash
dd if=/dev/zero of=/dev/sdb bs=1M count=100
dd if=/dev/zero of=/dev/sdc bs=1M count=100
dd if=/dev/zero of=/dev/sdd bs=1M count=100
```

> Do not run this after OCR/voting is in use unless rebuilding everything.

## 15. Create One UDEV Rules File on Both Nodes

File:

```text
/etc/udev/rules.d/99-oracle-asm.rules
```

Contents from the tested lab:

```text
ENV{ID_SERIAL}=="VBOX_HARDDISK_VBad2fb43e-20e7527f", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk1"
ENV{ID_SERIAL}=="VBOX_HARDDISK_VBacc322ce-7f043f0b", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk2"
ENV{ID_SERIAL}=="VBOX_HARDDISK_VBbae5fb9c-482333b5", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk3"
```

These serials are specific to this VirtualBox lab. Recheck identifiers before reusing on another environment.

## 16. Reload UDEV Rules

```bash
udevadm control --reload-rules
udevadm trigger
```

## 17. Verify Devices

```bash
ls -l /dev/asm*
ls -l /dev/sdb /dev/sdc /dev/sdd
```

Expected:

```text
/dev/asm-disk1 -> sdb
/dev/asm-disk2 -> sdc
/dev/asm-disk3 -> sdd
```

The tested runbook recorded the expected device mode as `660`. Verify actual owner/group on both nodes before proceeding.

Keep only one ASM rules file. Do not maintain duplicate rules files.

---

# Phase 5 — User Environment

## 18. `grid` `.bash_profile` on Node1

```bash
export TMP=/tmp
export TMPDIR=$TMP

export ORACLE_HOSTNAME=racnode1
export ORACLE_BASE=/u01/app/grid
export ORACLE_HOME=/u01/app/19.0.0/grid
export GRID_HOME=$ORACLE_HOME

export ORACLE_SID=+ASM1
export ORACLE_TERM=xterm
export PATH=$ORACLE_HOME/bin:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib

export NLS_DATE_FORMAT="DD-MON-YYYY HH24:MI:SS"
export EDITOR=vi
export CV_ASSUME_DISTID=OL7
```

## 19. `grid` `.bash_profile` on Node2

```bash
export TMP=/tmp
export TMPDIR=$TMP

export ORACLE_HOSTNAME=racnode2
export ORACLE_BASE=/u01/app/grid
export ORACLE_HOME=/u01/app/19.0.0/grid
export GRID_HOME=$ORACLE_HOME

export ORACLE_SID=+ASM2
export ORACLE_TERM=xterm
export PATH=$ORACLE_HOME/bin:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib

export NLS_DATE_FORMAT="DD-MON-YYYY HH24:MI:SS"
export EDITOR=vi
export CV_ASSUME_DISTID=OL7
```

## 20. `oracle` `.bash_profile` on Node1

```bash
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=racnode1
export ORACLE_UNQNAME=RAC
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1
export ORACLE_SID=RAC1
export ORACLE_TERM=xterm
export PATH=$ORACLE_HOME/bin:$PATH
```

## 21. `oracle` `.bash_profile` on Node2

```bash
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=racnode2
export ORACLE_UNQNAME=RAC
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1
export ORACLE_SID=RAC2
export ORACLE_TERM=xterm
export PATH=$ORACLE_HOME/bin:$PATH
```

---

# Phase 6 — Passwordless SSH

## 22. Configure Passwordless SSH for `grid` and `oracle`

Do this for both users.

As `grid` on node1:

```bash
ssh-keygen -t rsa
ssh-copy-id racnode1
ssh-copy-id racnode2
```

As `oracle` on node1:

```bash
ssh-keygen -t rsa
ssh-copy-id racnode1
ssh-copy-id racnode2
```

Verify:

```bash
ssh racnode1 date
ssh racnode2 date
```

---

# Phase 7 — Grid Install

## 23. Unzip Grid Software on Both Nodes

As `grid`:

```bash
cd /u01/app/19.0.0/grid
unzip LINUX.X64_193000_grid_home.zip
```

## 24. Install `cvuqdisk`

As root:

```bash
cd /u01/app/19.0.0/grid/cv/rpm
rpm -ivh cvuqdisk-1.0.10-1.rpm
```

Then as `grid`:

```bash
cd $GRID_HOME
./runcluvfy.sh stage -pre crsinst -n racnode1,racnode2 -verbose
```

## 25. Launch Grid Installer on Node1 as `grid`

```bash
export DISPLAY=192.168.56.1:0.0
xhost +

cd /u01/app/19.0.0/grid
./gridSetup.sh
```

## 26. Grid Installer Selections

Choose:

```text
Configure Oracle Grid Infrastructure for a Cluster
```

Cluster Name:

```text
raccluster
```

SCAN Name:

```text
rac-scan
```

SCAN Port:

```text
1521
```

Nodes:

```text
racnode1
racnode2
```

Network classification:

```text
public interfaces  = public
private interfaces = private
```

Storage:

```text
ASM
```

Disk discovery string:

```text
/dev/asm-disk*
```

Create OCR diskgroup using:

```text
/dev/asm-disk1
```

Inventory:

```text
/u01/app/oraInventory
```

ASM groups:

```text
ASM admin = asmadmin
ASM oper  = asmoper
ASM dba   = asmdba
```

## 27. Fix Prerequisites if Needed

```text
chrony must be running
cvuqdisk must be installed
swap warning can be ignored in this lab if intentionally sized
DNS warning was tolerated in this tested lab because /etc/hosts was used
```

## 28. Run Root Scripts When Prompted

As root:

```bash
/u01/app/oraInventory/orainstRoot.sh
/u01/app/19.0.0/grid/root.sh
```

Run on node1 first, then node2 when prompted.

## 29. Verify Cluster

As `grid`:

```bash
crsctl check crs
crsctl stat res -t
olsnodes -n
ocrcheck
```

Expected:

```text
CRS online
CSS online
EVMD online
both nodes visible
OCR integrity check succeeded
```

---

# Phase 8 — ASM Diskgroups

## 30. Login as `grid`

```bash
sqlplus / as sysasm
```

## 31. Verify Disk Visibility

```sql
SELECT path, header_status, mount_status
FROM v$asm_disk;
```

## 32. Create DATA Diskgroup

```sql
CREATE DISKGROUP DATA EXTERNAL REDUNDANCY
DISK '/dev/asm-disk2'
ATTRIBUTE 'compatible.asm'='19.0','compatible.rdbms'='19.0';
```

## 33. Create FRA Diskgroup

```sql
CREATE DISKGROUP FRA EXTERNAL REDUNDANCY
DISK '/dev/asm-disk3'
ATTRIBUTE 'compatible.asm'='19.0','compatible.rdbms'='19.0';
```

## 34. Verify Diskgroups

```sql
SELECT name, state, total_mb, free_mb
FROM v$asm_diskgroup
ORDER BY name;
```

Expected:

```text
OCR   MOUNTED
DATA  MOUNTED
FRA   MOUNTED
```

---

# Phase 9 — DB Software Install

## 35. Unzip DB Software on Both Nodes

As `oracle`:

```bash
cd /u01/app/oracle/product/19.0.0/dbhome_1
unzip LINUX.X64_193000_db_home.zip
```

## 36. Launch DB Installer on Node1 as `oracle`

```bash
cd /u01/app/oracle/product/19.0.0/dbhome_1
./runInstaller
```

## 37. Critical Installer Selections

Choose:

```text
Install database software only
Oracle Real Application Clusters database installation
```

Do **not** choose:

```text
Single instance database installation
```

## 38. Select Nodes

```text
racnode1
racnode2
```

## 39. OS Groups

```text
OSDBA       = dba
OSOPER      = oper
OSBACKUPDBA = backupdba
OSDGDBA     = dgdba
OSKMDBA     = kmdba
OSRACDBA    = dba
ASMDBA      = asmdba
```

## 40. Run Root Scripts When Prompted

As root:

```bash
/u01/app/oracle/product/19.0.0/dbhome_1/root.sh
```

Run on node1 and node2.

## 41. Verify DB Home

As `oracle`:

```bash
$ORACLE_HOME/bin/sqlplus -v
$ORACLE_HOME/OPatch/opatch lsinventory
```

---

# Phase 10 — DBCA Create 2-Node RAC Database

## 42. Launch DBCA on Node1 as `oracle`

```bash
dbca
```

## 43. Choose Creation Mode

```text
Create Database
```

## 44. Deployment Type

```text
Oracle Real Application Cluster (RAC) database
Configuration type: Admin Managed
```

## 45. Use Advanced Configuration

Do not use Typical for the first build.

## 46. Database Name

```text
Global database name: RAC
Instances:
  RAC1 on node1
  RAC2 on node2
```

## 47. Storage

```text
Storage type:       ASM
Datafiles:          +DATA
Fast Recovery Area: +FRA
```

## 48. Database Architecture

```text
Create as Container Database = YES
PDB name = RACPDB1
```

## 49. Character Set

```text
AL32UTF8
```

## 50. Passwords

The tested private runbook contained actual lab credentials. They are deliberately not committed to GitHub.

Use secure local values:

```text
SYS      = <SECURE_LOCAL_PASSWORD>
SYSTEM   = <SECURE_LOCAL_PASSWORD>
PDBADMIN = <SECURE_LOCAL_PASSWORD>
```

## 51. Memory

Example lab settings used in the runbook:

```text
SGA = 1024 MB
PGA = 512 MB
```

## 52. Create Database

Review the summary and click **Finish / Create**.

---

# Phase 11 — Post-Build Validation

## 53. Verify Database

As `oracle`:

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

Expected:

```text
DB name   = RAC
CDB       = YES
PDB       = RACPDB1
Instances = RAC1 and RAC2
```

## 54. Verify `srvctl`

```bash
srvctl config database -d RAC
srvctl status database -d RAC
```

## 55. Verify ASM Usage

```bash
asmcmd ls +DATA
asmcmd ls +FRA
```

---

# Phase 12 — If DBCA Fails

## 56. If GUI Asks to Revert

Choose:

```text
YES
```

## 57. Clean Partial Residue

```bash
asmcmd ls +DATA
asmcmd ls +FRA
```

If `RAC/` remains and it belongs only to the failed DBCA attempt:

```bash
asmcmd rm -rf +DATA/RAC
asmcmd rm -rf +FRA/RAC
```

## 58. Check Local Residue

```bash
ps -ef | grep pmon
cat /etc/oratab | grep RAC
ls $ORACLE_HOME/dbs | grep -i RAC
```

Remove stale files if needed:

```bash
rm -f $ORACLE_HOME/dbs/*RAC*
```

## 59. Check `srvctl`

```bash
srvctl config database -d RAC
```

If stale configuration exists:

```bash
srvctl remove database -d RAC -force
```

---

# Final Rules

1. Grid first, database second.
2. Keep one UDEV rules file only.
3. Do not wipe OCR/data disks after build unless rebuilding everything.
4. For RAC DB creation, the DB home must be installed using **Oracle Real Application Clusters database installation**.
5. Use Advanced DBCA for the first build.
6. Keep disk mapping fixed and documented.
7. Do not guess after failure; clean residue before retry.
8. Never commit passwords or other live credentials to GitHub.

---

## Provenance

This file replaces the earlier reconstructed RAC document with the user's tested and reused runbook as the authoritative implementation reference. Formatting was converted to Markdown and the embedded database passwords were sanitized; the implementation sequence, lab values, commands, installer selections, and recovery steps were otherwise retained from the tested runbook.
