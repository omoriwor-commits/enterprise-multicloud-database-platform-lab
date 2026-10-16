# Oracle AI Database 26ai Two-Node RAC Build Runbook

**Last updated:** 2026-10-16

## Overview

This runbook builds a two-node Oracle AI Database 26ai RAC on Oracle Linux 9 in VirtualBox. It follows the same 12 phases as my tested 19c runbook, updated for 26ai. Steps marked **Verify** are not yet tested in my lab, so confirm them on the first build.

**Status:** Draft, adapted from the 19c runbook. Not yet built end to end on 26ai.

**Baseline:** [Tested Oracle 19c two-node RAC build and troubleshooting runbook](oracle19c-2node-rac-build-and-troubleshooting.md).

**Scope:** Lab only. Firewall and SELinux shortcuts here are not for real environments.

### Lab layout

| Item                                | Node 1         | Node 2         |
| ----------------------------------- | -------------- | -------------- |
| Hostname                            | racnode1       | racnode2       |
| Public IP (host-only, 192.168.56.x) | 192.168.56.101 | 192.168.56.102 |
| VIP                                 | 192.168.56.111 | 192.168.56.112 |
| Private interconnect (192.168.57.x) | 192.168.57.101 | 192.168.57.102 |
| ASM instance                        | +ASM1          | +ASM2          |
| DB instance                         | RAC1           | RAC2           |

SCAN: rac-scan on 192.168.56.120 to .122. Cluster name: raccluster.

### VM sizing

| Mount point | Size  | Purpose           |
| ----------- | ----- | ----------------- |
| /boot       | 1 GB  | Boot files        |
| /           | 30 GB | Operating system  |
| /u01        | 60 GB | Grid and DB homes |
| swap        | 8 GB  | Swap              |

Shared disks (VirtualBox: fixed size, type Shareable, attached to both VMs):

| Device   | Size  | Diskgroup                  |
| -------- | ----- | -------------------------- |
| /dev/sdb | 20 GB | OCR (OCR and voting files) |
| /dev/sdc | 40 GB | DATA                       |
| /dev/sdd | 20 GB | FRA                        |

### Software paths

| Item      | Path                                   |
| --------- | -------------------------------------- |
| Grid home | /u01/app/23.26/grid                    |
| Grid base | /u01/app/grid                          |
| DB home   | /u01/app/oracle/product/23.26/dbhome_1 |
| DB base   | /u01/app/oracle                        |
| Inventory | /u01/app/oraInventory                  |

Media: `LINUX.X64_2326100_grid_home.zip` and `LINUX.X64_2326100_db_home.zip` from Oracle's 26ai Linux downloads page. File names change with the release update, so use the names you actually download.

### What changed from the 19c runbook

- OS is Oracle Linux 9 (26ai Grid/RAC is certified on OL 9.2+ and OL 8.8+). No `CV_ASSUME_DISTID` workaround.
- Preinstall RPM is `oracle-ai-database-preinstall-26ai`. It creates the oracle user and core groups, so Phase 2 creates only the ASM groups and the grid user.
- OSRACDBA maps to `racdba` instead of `dba`.
- Grid and DB software are unzipped on node 1 only; the installers copy them to node 2.
- GIMR is desupported in 26ai, so there is nothing to configure for it.
- ASM Filter Driver is desupported; udev rules stay the method here.
- The database must be a CDB; non-CDB is not available in 26ai.
- Installation archives are digitally signed; Phase 7 adds an integrity check.

Sources: [Oracle 26ai Grid/RAC OS checklist](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/operating-system-checklist-for-oracle-grid-infrastructure-and-oracle-rac.html), [26ai Grid upgrade restrictions (GIMR, ASMFD)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/restrictions-for-oracle-grid-infrastructure-upgrades.html), [26ai OS configuration](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/configuring-operating-systems-for-oracle-database-on-linux.html).

---

## Phase 1: OS prep on both nodes

Both nodes need Oracle Linux 9, two NICs (public and private), matching time, and name resolution for every RAC address before any Oracle software goes on.

1. Confirm the OS release and kernel on both nodes.

```bash
cat /etc/oracle-release
uname -r
```

2. Set the hostname.

```bash
# node1
hostnamectl set-hostname racnode1
# node2
hostnamectl set-hostname racnode2
```

3. Add these entries to `/etc/hosts` on both nodes.

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

4. Test name resolution and reachability from both nodes. VIPs and SCAN will not answer ping until Grid is running; that is expected.

```bash
for h in racnode1 racnode2 racnode1-vip racnode2-vip rac-scan racnode1-priv racnode2-priv; do getent hosts $h; done
ping -c 3 racnode1
ping -c 3 racnode2
ping -c 3 racnode1-priv
ping -c 3 racnode2-priv
```

5. Enable time sync and check it.

```bash
systemctl enable --now chronyd
chronyc tracking
chronyc sources -v
```

Do not continue until both nodes show a synced source.

6. Lab only: stop the firewall and set SELinux to permissive.

```bash
systemctl disable --now firewalld
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config
getenforce
```

Record the SELinux mode you end up using. My October node 2 incident ended with SELinux disabled and an unconfirmed root cause, so note it rather than changing it silently later.

7. Update packages and reboot both nodes.

```bash
dnf -y update
reboot
```

---

## Phase 2: Preinstall RPM, users, groups, limits

The 26ai preinstall RPM does most of the work the 19c runbook did by hand. Run it first, then add only what it does not create. UIDs and GIDs must match on both nodes.

1. Install the preinstall RPM on both nodes.

```bash
dnf install -y oracle-ai-database-preinstall-26ai
```

2. Check what it created. **Verify** the exact GIDs on your build; they must be identical on both nodes.

```bash
id oracle
getent group oinstall dba oper backupdba dgdba kmdba racdba
```

3. Create only the ASM groups (skip any that already exist).

```bash
groupadd -g 54327 asmdba
groupadd -g 54328 asmoper
groupadd -g 54329 asmadmin
```

4. Create the grid user and add oracle to asmdba.

```bash
useradd -u 54330 -g oinstall -G asmadmin,asmdba,asmoper,dba,racdba grid
usermod -a -G asmdba oracle
id grid
id oracle
```

5. Set passwords interactively.

```bash
passwd grid
passwd oracle
```

6. Verify kernel parameters set by the RPM. These replace the manual `sysctl.conf` edits from the 19c runbook.

```bash
sysctl fs.aio-max-nr fs.file-max kernel.shmmax kernel.shmall kernel.shmmni kernel.sem net.ipv4.ip_local_port_range
```

7. Check limits. The RPM sets limits for oracle only, so add a file for grid.

```bash
ls /etc/security/limits.d/
cat > /etc/security/limits.d/99-grid.conf <<'EOF'
grid   soft   nproc    16384
grid   hard   nproc    16384
grid   soft   nofile   1024
grid   hard   nofile   65536
grid   soft   stack    10240
grid   hard   stack    32768
grid   soft   memlock  unlimited
grid   hard   memlock  unlimited
EOF
```

8. Confirm limits as each user.

```bash
su - grid -c 'ulimit -u; ulimit -n; ulimit -s'
su - oracle -c 'ulimit -u; ulimit -n; ulimit -s'
```

---

## Phase 3: Directories and ownership

Create the same tree on both nodes. Grid owns its home, base and the inventory; oracle owns the DB base and home.

```bash
mkdir -p /u01/app/23.26/grid
mkdir -p /u01/app/grid
mkdir -p /u01/app/oracle/product/23.26/dbhome_1
mkdir -p /u01/app/oraInventory

chown -R grid:oinstall /u01/app/23.26
chown -R grid:oinstall /u01/app/grid
chown -R grid:oinstall /u01/app/oraInventory
chown -R oracle:oinstall /u01/app/oracle

chmod -R 775 /u01/app
chmod 755 /u01
```

Verify the full path permissions:

```bash
namei -om /u01/app/23.26/grid
namei -om /u01/app/oracle/product/23.26/dbhome_1
```

---

## Phase 4: Shared disks and udev

ASM needs the same three disks, with the same stable names and grid ownership, on both nodes. udev rules do this; ASM Filter Driver is desupported in 26ai, so do not use it.

1. Confirm both nodes see the shared disks.

```bash
lsblk
```

Expected: sdb (20 GB), sdc (40 GB), sdd (20 GB).

2. Wipe headers once, from node 1 only, and only on a fresh build.

```bash
dd if=/dev/zero of=/dev/sdb bs=1M count=100
dd if=/dev/zero of=/dev/sdc bs=1M count=100
dd if=/dev/zero of=/dev/sdd bs=1M count=100
```

Never run this after OCR and voting files are on the disks unless you are rebuilding everything.

3. Get each disk's serial. The 19c serials will not match new VMs.

```bash
for d in sdb sdc sdd; do echo -n "$d: "; udevadm info --query=property --name=/dev/$d | grep ID_SERIAL=; done
```

4. Create one rules file, `/etc/udev/rules.d/99-oracle-asm.rules`, on both nodes with your serials.

```text
ENV{ID_SERIAL}=="<serial_of_sdb>", OWNER="grid", GROUP="asmadmin", MODE="0660", SYMLINK+="asm-disk1"
ENV{ID_SERIAL}=="<serial_of_sdc>", OWNER="grid", GROUP="asmadmin", MODE="0660", SYMLINK+="asm-disk2"
ENV{ID_SERIAL}=="<serial_of_sdd>", OWNER="grid", GROUP="asmadmin", MODE="0660", SYMLINK+="asm-disk3"
```

The 19c build used `GROUP="asmdba"` and worked. This runbook uses asmadmin, the group Oracle's examples use for ASM devices. Pick one and keep it consistent on both nodes.

5. Reload and verify on both nodes.

```bash
udevadm control --reload-rules
udevadm trigger
ls -l /dev/asm-disk*
ls -l /dev/sdb /dev/sdc /dev/sdd
```

Expected: asm-disk1 to sdb, asm-disk2 to sdc, asm-disk3 to sdd, owner grid, group asmadmin, mode 660. Keep only one ASM rules file.

---

## Phase 5: User environments

Only the hostname and SID differ between nodes. `CV_ASSUME_DISTID` from the 19c runbook is removed because 26ai supports OL9 natively.

**grid `~/.bash_profile`** (node1 shown; on node2 use racnode2 and +ASM2):

```bash
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=racnode1
export ORACLE_BASE=/u01/app/grid
export ORACLE_HOME=/u01/app/23.26/grid
export GRID_HOME=$ORACLE_HOME
export ORACLE_SID=+ASM1
export ORACLE_TERM=xterm
export PATH=$ORACLE_HOME/bin:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib
export NLS_DATE_FORMAT="DD-MON-YYYY HH24:MI:SS"
export EDITOR=vi
```

**oracle `~/.bash_profile`** (node1 shown; on node2 use racnode2 and RAC2):

```bash
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=racnode1
export ORACLE_UNQNAME=RAC
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=/u01/app/oracle/product/23.26/dbhome_1
export ORACLE_SID=RAC1
export ORACLE_TERM=xterm
export PATH=$ORACLE_HOME/bin:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib
```

Reload and check:

```bash
source ~/.bash_profile
echo $ORACLE_HOME $ORACLE_SID
```

---

## Phase 6: Passwordless SSH

Both grid and oracle need SSH without a password from every node to every node, including itself. The 19c runbook only set it up from node 1; do both nodes here.

Option A is manual setup. Run as grid on node1, then as grid on node2, then repeat both as oracle:

```bash
ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa
ssh-copy-id racnode1
ssh-copy-id racnode2
```

Option B is to let the installer do it. 26ai documents automatic SSH configuration during installation (the SSH connectivity step in `gridSetup.sh` and `runInstaller`).

Verify from both nodes, as both users. Each command must return the date with no password or host-key prompt:

```bash
for h in racnode1 racnode2 racnode1-priv racnode2-priv; do ssh -o BatchMode=yes $h date; done
```

Stay on OL9 for this build. Oracle-Base hit a passwordless SSH failure building 26ai RAC on OL10, traced in comments to OpenSSH 10.x.

---

## Phase 7: Grid Infrastructure install

Grid goes in from node 1 and is copied to node 2 by the installer. Do not continue to ASM or the database until `crsctl` shows both nodes healthy.

1. Check media integrity on node 1. Compare against the checksum on Oracle's download page. **Verify** the signature step in the 26ai install guide section "Verifying Digital Signature and Integrity of Installation Archive Files".

```bash
sha256sum LINUX.X64_2326100_grid_home.zip LINUX.X64_2326100_db_home.zip
```

2. As grid, unzip into the Grid home on node 1 only.

```bash
cd /u01/app/23.26/grid
unzip -q /path/to/LINUX.X64_2326100_grid_home.zip
```

3. As root, install cvuqdisk on both nodes. Copy the RPM to node 2 first.

```bash
export CVUQDISK_GRP=oinstall
rpm -ivh /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm
scp /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm racnode2:/tmp/
ssh racnode2 "CVUQDISK_GRP=oinstall rpm -ivh /tmp/cvuqdisk-*.rpm"
```

4. As grid, run the cluster pre-check and fix every failure before installing.

```bash
cd /u01/app/23.26/grid
./runcluvfy.sh stage -pre crsinst -n racnode1,racnode2 -verbose
```

Tolerable in this lab: the DNS/SCAN warning (SCAN is in /etc/hosts, not DNS) and a swap warning if swap was sized on purpose.

5. As grid on node 1, launch the installer.

```bash
export DISPLAY=192.168.56.1:0.0
cd /u01/app/23.26/grid
./gridSetup.sh
```

6. Installer selections.

| Screen                | Value                                                              |
| --------------------- | ------------------------------------------------------------------ |
| Configuration option  | Configure Oracle Grid Infrastructure for a New Cluster             |
| Cluster name          | raccluster                                                         |
| SCAN name and port    | rac-scan, 1521                                                     |
| Nodes                 | racnode1 / racnode1-vip, racnode2 / racnode2-vip                   |
| SSH connectivity      | Test (or Setup if you chose Option B in Phase 6)                   |
| Network interfaces    | 192.168.56.0 = Public, 192.168.57.0 = ASM & Private                |
| Storage               | Oracle ASM                                                         |
| Diskgroup             | OCR, External redundancy, /dev/asm-disk1                           |
| Disk discovery string | `/dev/asm-disk*`                                                   |
| ASM passwords         | Secure local values, never committed to GitHub                     |
| OS groups             | OSASM = asmadmin, OSDBA for ASM = asmdba, OSOPER for ASM = asmoper |
| Oracle base           | /u01/app/grid                                                      |
| Inventory             | /u01/app/oraInventory                                              |
| Root scripts          | Automatically run, with root password (Oracle recommends this)     |

There is no GIMR option to set; GIMR is desupported in 26ai.

7. If you did not choose automatic root scripts, run them as root when prompted. Node 1 must finish before node 2 starts.

```bash
/u01/app/oraInventory/orainstRoot.sh
/u01/app/23.26/grid/root.sh
```

8. As grid, verify the cluster.

```bash
crsctl check cluster -all
crsctl stat res -t
crsctl query crs activeversion
olsnodes -n -s
ocrcheck
srvctl status scan_listener
```

Expected: CRS, CSS and EVM online on both nodes, both nodes Active, OCR integrity check succeeded, active version 23.x.

Alternative for later: 26ai also supports a command-line Grid install (`gridSetup.sh -silent` with a response file). That fits the automation project better than the GUI once the manual build works.

Sources: [26ai Grid CLI install](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/installing-grid-using-command-line-interface.html), [26ai Grid upgrade with setup wizard (root script automation)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/running-oui-to-upgrade-grid-infrastructure-from-an-earlier-release.html).

---

## Phase 8: ASM diskgroups

Create DATA and FRA from node 1 as grid, then mount them on node 2. The 19c runbook hardcoded compatible values of 19.0; here they are left at the 26ai defaults and checked afterward.

1. Connect and check disk visibility.

```bash
sqlplus / as sysasm
```

```sql
SELECT path, header_status, mount_status FROM v$asm_disk ORDER BY path;
```

Expected: asm-disk2 and asm-disk3 show CANDIDATE or PROVISIONED; asm-disk1 is MEMBER (OCR).

2. Create the diskgroups.

```sql
CREATE DISKGROUP DATA EXTERNAL REDUNDANCY DISK '/dev/asm-disk2';
CREATE DISKGROUP FRA  EXTERNAL REDUNDANCY DISK '/dev/asm-disk3';
```

3. Mount them on node 2 (as grid on racnode2).

```bash
srvctl start diskgroup -diskgroup DATA -node racnode2
srvctl start diskgroup -diskgroup FRA -node racnode2
```

4. Verify from either node.

```sql
SELECT inst_id, name, state, total_mb, free_mb FROM gv$asm_diskgroup ORDER BY name, inst_id;
SELECT name, compatibility, database_compatibility FROM v$asm_diskgroup;
```

Expected: OCR, DATA and FRA MOUNTED on both instances. Record the compatibility values in your build notes. You can also create the diskgroups with the `asmca` GUI instead of SQL.

---

## Phase 9: Database software install

Install software only, as a RAC home, from node 1. The installer copies it to node 2.

1. As oracle, unzip on node 1 only.

```bash
cd /u01/app/oracle/product/23.26/dbhome_1
unzip -q /path/to/LINUX.X64_2326100_db_home.zip
```

2. Launch the installer.

```bash
export DISPLAY=192.168.56.1:0.0
./runInstaller
```

3. Installer selections.

| Screen                          | Value                                                  |
| ------------------------------- | ------------------------------------------------------ |
| Configuration option            | Set Up Software Only                                   |
| Database installation option    | Oracle Real Application Clusters database installation |
| Nodes                           | racnode1, racnode2 (SSH test passes)                   |
| Edition                         | Enterprise Edition                                     |
| Oracle base                     | /u01/app/oracle                                        |
| OSDBA / OSOPER                  | dba / oper                                             |
| OSBACKUPDBA / OSDGDBA / OSKMDBA | backupdba / dgdba / kmdba                              |
| OSRACDBA                        | racdba (19c runbook used dba)                          |
| Root scripts                    | Automatically run, or run manually when prompted       |

Do not choose single-instance installation. A RAC database cannot be created from a single-instance home.

4. If running root scripts manually, run on node 1, then node 2.

```bash
/u01/app/oracle/product/23.26/dbhome_1/root.sh
```

5. Verify on both nodes as oracle.

```bash
sqlplus -v
$ORACLE_HOME/OPatch/opatch lspatches
ssh racnode2 ls /u01/app/oracle/product/23.26/dbhome_1/bin/oracle
```

---

## Phase 10: Create the 2-node RAC database with DBCA

Run DBCA as oracle on node 1 with Advanced Configuration. The result is a container database RAC with one PDB, RACPDB1.

```bash
export DISPLAY=192.168.56.1:0.0
dbca
```

| Screen                            | Value                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------ |
| Operation                         | Create a database                                                                    |
| Mode                              | Advanced configuration                                                               |
| Database type                     | Oracle Real Application Cluster (RAC) database                                       |
| Management                        | Admin Managed                                                                        |
| Template                          | General Purpose or Transaction Processing                                            |
| Nodes                             | racnode1, racnode2                                                                   |
| Global database name / SID prefix | RAC / RAC (instances RAC1, RAC2)                                                     |
| Container database                | Yes (the only option in 26ai), PDB name RACPDB1                                      |
| Storage                           | ASM, datafiles in +DATA                                                              |
| Fast Recovery Area                | +FRA, archiving enabled                                                              |
| Character set                     | AL32UTF8                                                                             |
| Memory                            | Start from the 19c lab values (SGA 1024 MB, PGA 512 MB) and raise them if DBCA warns |
| Passwords                         | Secure local values for SYS, SYSTEM, PDBADMIN; never committed to GitHub             |

**Verify** the memory settings. I have not confirmed a 26ai minimum for RAC, and small VMs may need more SGA than the 19c build used.

Review the summary page, save the response file for the automation project, then click Finish.

---

## Phase 11: Post-build validation

The build is done when both instances are open, the PDB is open on both, and a client connects through SCAN. Save the output of each check as evidence, with passwords and serials removed.

1. Cluster and database resources (as oracle):

```bash
srvctl config database -db RAC
srvctl status database -db RAC
srvctl config scan
srvctl status scan_listener
```

2. Instances, version and PDB (as oracle, `sqlplus / as sysdba`):

```sql
SELECT banner_full FROM v$version;
SELECT name, cdb, log_mode FROM v$database;
SELECT inst_id, instance_name, host_name, status FROM gv$instance ORDER BY inst_id;
SELECT inst_id, name, open_mode FROM gv$pdbs ORDER BY name, inst_id;
```

Expected: version 23.26.x, CDB = YES, ARCHIVELOG, RAC1 and RAC2 OPEN, RACPDB1 READ WRITE on both instances.

3. ASM usage (as grid):

```bash
asmcmd ls +DATA
asmcmd ls +FRA
asmcmd lsdg
```

4. Connect through SCAN to the PDB service:

```bash
sqlplus system@//rac-scan:1521/racpdb1
```

```sql
SELECT sys_context('USERENV','INSTANCE_NAME') FROM dual;
```

Repeat a few times; connections should land on both instances.

5. Failover check: stop one instance and confirm the other keeps serving.

```bash
srvctl stop instance -db RAC -instance RAC2
srvctl status database -db RAC
srvctl start instance -db RAC -instance RAC2
```

---

## Phase 12: If DBCA fails, and final rules

Clean every trace of a failed DBCA run before retrying; guessing on a dirty cluster wastes more time than the cleanup.

1. If DBCA offers to revert, choose Yes.
2. Remove ASM residue, only if it belongs to the failed attempt (as grid):

```bash
asmcmd ls +DATA
asmcmd ls +FRA
asmcmd rm -rf +DATA/RAC
asmcmd rm -rf +FRA/RAC
```

3. Check local residue on both nodes (as oracle):

```bash
ps -ef | grep pmon
grep RAC /etc/oratab
ls $ORACLE_HOME/dbs | grep -i rac
rm -f $ORACLE_HOME/dbs/*RAC*
```

4. Remove stale cluster registration:

```bash
srvctl config database -db RAC
srvctl remove database -db RAC -force
```

### Final rules

1. Grid first, database second.
2. Keep one udev rules file, identical on both nodes.
3. Never wipe OCR or data disks after the build unless rebuilding everything.
4. Install the DB home as a RAC installation, never single-instance.
5. Use Advanced DBCA for the first build and save the response files.
6. Keep disk mapping, UIDs and GIDs fixed and documented.
7. Do not guess after a failure; clean residue before retrying.
8. Never commit passwords, disk serials or other live values to GitHub.
9. Stay on OL9 until 26ai RAC on OL10 is proven in your lab.
10. Clear every **Verify** in this runbook during the first build, then change Status to Tested
