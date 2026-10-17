# Oracle AI Database 26ai Two-Node RAC Build Runbook

**Last updated:** 2026-10-17

## Overview

This runbook builds a two-node Oracle AI Database 26ai RAC on Oracle Linux 9 in VirtualBox. It follows the phases of my tested 19c runbook, updated for 26ai, with Phase 0 added for the VirtualBox setup. Steps marked **Verify** are not yet tested in my lab, so confirm them on the first build.

**Status:** Draft, adapted from the 19c runbook. Not yet built end to end on 26ai.

**Baseline:** [Tested Oracle 19c two-node RAC build and troubleshooting runbook](oracle19c-2node-rac-build-and-troubleshooting.md).

**Scope:** Lab only. Firewall and SELinux shortcuts here are not for real environments. This runbook does not establish Oracle support for RAC in VirtualBox; verify the exact hardware, virtualization, OS/kernel and release-update combination against Oracle's current certification information.

### Lab layout

| Item                                | Node 1         | Node 2         |
| ----------------------------------- | -------------- | -------------- |
| VirtualBox VM name                  | rac26node1 | rac26node2 |
| Hostname (FQDN)                     | rac26node1.lab.test | rac26node2.lab.test |
| Public IP (host-only, 192.168.56.x) | 192.168.56.101 | 192.168.56.102 |
| VIP                                 | 192.168.56.111 | 192.168.56.112 |
| Private interconnect (192.168.57.x) | 192.168.57.101 | 192.168.57.102 |
| ASM instance                        | +ASM1          | +ASM2          |
| DB instance                         | RAC1           | RAC2           |

SCAN for this hosts-file lab: `rac-scan.lab.test` (`rac-scan`) on `192.168.56.120`, one SCAN VIP/listener. Cluster name: `raccluster`. A three-address SCAN requires a verified DNS/GNS configuration; repeated hosts-file entries are not a substitute for round-robin DNS.

**Verify** all example subnets are unused by the Windows host, VPNs and other VMs before assigning them. VIP and SCAN addresses must be reserved and unused; do not assign them manually to Linux interfaces.

### VM sizing

| Resource | Per node | Notes |
|---|---|---|
| RAM | 10 GiB (10240 MB) | Initial lab allocation on a 32 GiB host |
| vCPU | 2 | Four physical host cores are shared by both guests and Windows |
| OS/software disk | 100 GiB, dynamically allocated VDI | Separate disk for each node |

The current build uses **automatic partitioning**. The final filesystem layout has not yet been captured; do not claim a separate 60 GiB `/u01` filesystem exists. After installation, record:

```bash
df -hT
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
swapon --show
free -h
```

**Verify** sufficient free space in the filesystem that will contain `/u01`, installation staging, patching and logs before extracting software. Automatic partitioning may allocate substantial space to `/home`; resolve insufficient space before Grid installation. For 10 GiB RAM, plan 10 GiB total swap and validate the release-specific Grid checklist. If automatic swap is smaller, add verified persistent swap after installation; swap does not replace physical RAM.

For a future custom installation on a 100 GiB disk, a simple alternative is `/boot` 1 GiB, swap 10 GiB, and `/` using the remaining space (less partition/LVM overhead), with `/u01` under `/`. Do not add this custom layout on top of the current automatic installation.

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

Media examples: `LINUX.X64_2326100_grid_home.zip` and `LINUX.X64_2326100_db_home.zip` identify 23.26.1 images. They are examples, not a frozen recommendation for every OL9 kernel. **Verify** the exact Grid and Database image/RU, patch README, OS and running kernel before installation. Oracle documents OL9 UEK8 support starting with RU 23.26.2; do not install 23.26.1 unchanged on UEK8 and assume compatibility. Use a documented supported kernel or obtain/apply compatible updates according to their installation instructions. Keep matching intended Grid/Database patch levels on both nodes. Home directory names do not establish installed versions.

### What changed from the 19c runbook

- OS is Oracle Linux 9; support depends on the exact kernel and Grid/Database RU, not only the OL9 label. No `CV_ASSUME_DISTID` workaround.
- Preinstall RPM is `oracle-ai-database-preinstall-26ai`. It creates the oracle user and core groups, so Phase 2 creates only the ASM groups and the grid user.
- OSRACDBA maps to `racdba` instead of `dba`.
- Grid and DB software are unzipped on node 1 only; the installers copy them to node 2.
- GIMR is desupported in 26ai, so there is nothing to configure for it.
- ASM Filter Driver is desupported; udev rules stay the method here.
- The database must be a CDB; non-CDB is not available in 26ai.
- Installation archives are digitally signed; Phase 7 requires checksum and signature verification.
- ASM devices use `grid:asmdba` ownership and persistent disk identities.
- GUI installers use authenticated SSH X11 forwarding; no hardcoded host DISPLAY address.
- Time synchronization must be verified through chrony; CTSS is desupported in 26ai.

Sources: [Oracle 26ai Grid/RAC OS checklist](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/operating-system-checklist-for-oracle-grid-infrastructure-and-oracle-rac.html), [26ai Grid upgrade restrictions (GIMR, ASMFD)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/restrictions-for-oracle-grid-infrastructure-upgrades.html), [26ai OS configuration](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/configuring-operating-systems-for-oracle-database-on-linux.html).

### Build sequence

Build node 1 through Phases 1, 2, 3 and 5 before creating node 2 as a powered-off full clone. Then complete node 2 identity/network changes, attach fresh shared disks and run Phase 4 and Phases 6 onward. Checks requiring node 2 wait until node 2 exists. If building node 2 independently, complete all preparation phases on both nodes.

## Phase 0: VirtualBox setup

1. **Verify** the host has adequate free SSD space and memory. Keep unrelated database VMs stopped during the initial build. Store VMs outside OneDrive.
2. Use the following three adapters on each node, with Cable Connected enabled:

| Adapter | Attached to | Purpose |
|---|---|---|
| 1 | VirtualBox Host-only Adapter | Public cluster network and Windows management access |
| 2 | Internal Network, exact name `rac26priv` | Private interconnect |
| 3 | NAT | Outbound updates, downloads and GitHub; excluded from Grid cluster interfaces |
| 4 | Disabled | Not used |

**Verify** the host-only network has host address `192.168.56.1/24` and DHCP disabled. The internal network does not require a Windows host adapter or host address. Use the same internal-network name on both VMs. Leave promiscuous mode at Deny.

3. Create `rac26node1` with the sizing above, a new OS disk, the OL9 x86-64 Full ISO, and Skip Unattended Installation selected. Install Server with GUI, create an administrator account such as `labadmin`, and keep password-based root SSH disabled. Configure the selected automatic disk layout.
4. **Verify** record the completed node 1 inventory before cloning. Shut down Linux cleanly. Make a **full clone** named `rac26node2`, generating new MAC addresses for every adapter. Do not clone after Grid installation or after attaching ASM disks.
5. Boot the clone isolated from the public/private networks initially to avoid duplicate IP addresses. From its console, as root, regenerate machine identity:

```bash
rm -f /etc/machine-id /var/lib/dbus/machine-id
systemd-machine-id-setup
ln -s /etc/machine-id /var/lib/dbus/machine-id
```

**Verify** machine IDs differ between nodes. On node 2 regenerate SSH host keys before accepting remote connections:

```bash
rm -f /etc/ssh/ssh_host_*
ssh-keygen -A
systemctl restart sshd
```

Set node 2 hostname, static addresses and Phase 5 SID/profile values before reconnecting its cluster adapters. Verify interface/profile mapping against the new MAC addresses. Reset any copied grid/oracle user SSH keys before Phase 6 so each node/user has a distinct key.

6. **Verify** with both VMs powered off, create three **new, fixed-size, Shareable** VDI disks. The following PowerShell example creates files under a new lab-only directory; stop if those filenames already exist:

```powershell
$VBoxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
$DiskDir = "C:\RAC26ai\shared"
New-Item -ItemType Directory -Force -Path $DiskDir
& $VBoxManage createmedium disk --filename "$DiskDir\rac26-ocr.vdi" --size 20480 --variant Fixed
& $VBoxManage createmedium disk --filename "$DiskDir\rac26-data.vdi" --size 40960 --variant Fixed
& $VBoxManage createmedium disk --filename "$DiskDir\rac26-fra.vdi" --size 20480 --variant Fixed
& $VBoxManage modifymedium disk "$DiskDir\rac26-ocr.vdi" --type shareable
& $VBoxManage modifymedium disk "$DiskDir\rac26-data.vdi" --type shareable
& $VBoxManage modifymedium disk "$DiskDir\rac26-fra.vdi" --type shareable
```

Check every command succeeded before proceeding. Attach the **same three disk files** to both VMs at matching SATA ports (for example OCR 1, DATA 2, FRA 3; OS disk at 0). Compare full paths and VirtualBox UUIDs on both VMs. Matching filenames or capacities alone do not prove shared storage. Do not attach disks belonging to other database/GoldenGate VMs.

---

## Phase 1: OS prep on both nodes

Both nodes need Oracle Linux 9, static public/private cluster interfaces plus NAT for outbound access, matching time, and consistent name resolution before any Oracle software goes on. OS commands in Phases 1–4 require root privileges; use `sudo -i` from the administrator account rather than enabling password-based root SSH.

1. Confirm the OS release and kernel on both nodes.

```bash
cat /etc/oracle-release
uname -r
```

2. Set the hostname.

```bash
# node1
hostnamectl set-hostname rac26node1.lab.test
# node2
hostnamectl set-hostname rac26node2.lab.test
```

3. **Verify** connection-to-interface mapping using `nmcli device status`, `nmcli connection show` and MAC addresses. Configure the actual public/private connection names below on node 1; use .102 on node 2. Execute from the console because changing connections can disconnect SSH. Leave the NAT profile on DHCP and make it the only default route.

```bash
nmcli con mod "<public-con>" ipv4.method manual ipv4.addresses 192.168.56.101/24 ipv4.gateway "" ipv4.dns "" ipv4.never-default yes connection.autoconnect yes
nmcli con mod "<private-con>" ipv4.method manual ipv4.addresses 192.168.57.101/24 ipv4.gateway "" ipv4.dns "" ipv4.never-default yes connection.autoconnect yes
nmcli con up "<public-con>"
nmcli con up "<private-con>"
ip -br addr
ip route
```

Replace the angle-bracket connection placeholders; do not run them literally. Verify no stale .101 address remains on node 2.

Add these entries to `/etc/hosts` on both nodes; preserve required localhost entries and remove conflicting old RAC entries.

```text
127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4
::1         localhost localhost.localdomain localhost6 localhost6.localdomain6

# Public
192.168.56.101  rac26node1.lab.test rac26node1
192.168.56.102  rac26node2.lab.test rac26node2

# VIP
192.168.56.111  rac26node1-vip.lab.test rac26node1-vip
192.168.56.112  rac26node2-vip.lab.test rac26node2-vip

# SCAN
192.168.56.120  rac-scan.lab.test rac-scan

# Private interconnect
192.168.57.101  rac26node1-priv
192.168.57.102  rac26node2-priv
```

4. Test name resolution and reachability from both nodes. VIPs and SCAN will not answer ping until Grid is running; that is expected.

```bash
for h in rac26node1 rac26node2 rac26node1-vip rac26node2-vip rac-scan rac26node1-priv rac26node2-priv; do getent hosts $h; done
ping -c 3 rac26node1
ping -c 3 rac26node2
ping -c 3 rac26node1-priv
ping -c 3 rac26node2-priv
```

5. Enable time sync and check it.

```bash
systemctl enable --now chronyd
chronyc tracking
chronyc sources -v
```

Do not continue to Grid until both nodes show a synchronized source. CTSS is desupported in 26ai; this build uses chrony. Verify synchronization again after cloning and rebooting.

6. Lab only: stop the firewall and set SELinux to permissive.

```bash
systemctl disable --now firewalld
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config
getenforce
```

Record the SELinux mode you end up using. My October 2026 19c node 2 incident ended with SELinux disabled and an unconfirmed root cause, so note it rather than changing it silently later.

7. **Verify** install the 26ai preinstall RPM before creating Oracle users manually. Review the proposed package transaction and any kernel changes against the selected Grid/Database RU before updating. Do not blindly boot a new kernel family with older installation media.

```bash
dnf install oracle-ai-database-preinstall-26ai
dnf check-update
grubby --default-kernel
```

After choosing and applying a compatible package/kernel update set, reboot and record:

```bash
cat /etc/oracle-release
uname -r
rpm -q kernel kernel-uek
grubby --info=DEFAULT
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
cat /sys/kernel/mm/transparent_hugepage/enabled
df -hT
swapon --show
```

**Verify** both nodes have the same intended kernel/packages. Oracle recommends `tsc` for virtual x86-64 environments, where available and suitable. Oracle's current checklist and detailed guide differ in THP wording; verify the selected release's guidance, record the chosen setting and validate it after reboot rather than silently switching between `never`, `madvise` and `always`.

---

## Phase 2: Users, groups, limits

The 26ai preinstall RPM does most of the work the 19c runbook did by hand. Phase 1 installed it; this phase checks what it created and adds only what it does not. UIDs and GIDs must match on both nodes.

1. Confirm Phase 1 installed the preinstall RPM on both nodes.

```bash
rpm -q oracle-ai-database-preinstall-26ai
```

Before each groupadd/useradd, verify the name and numeric ID are unused or already match the intended identity. Stop on conflicts; do not renumber existing accounts blindly.

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

2. **Verify** each candidate against VirtualBox path/UUID, guest serial, size, existing signatures and mount state before provisioning. Linux `sdX` letters can change; the table is an example, not authorization to erase those device names.

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL
wipefs -n /dev/sdb /dev/sdc /dev/sdd
findmnt
```

New empty VDI disks do not require a routine `dd` wipe. If a disk contains a signature, stop and establish its ownership and intended reuse before a separate reviewed cleanup. Never erase the OS disk, an unknown device, or an existing ASM member.

3. Get each disk's serial. The 19c serials will not match new VMs.

```bash
for d in sdb sdc sdd; do echo -n "$d: "; udevadm info --query=property --name=/dev/$d | grep ID_SERIAL=; done
```

4. Create one rules file, `/etc/udev/rules.d/99-oracle-asm.rules`, on both nodes with your serials.

```text
SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="<serial_of_sdb>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk1"
SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="<serial_of_sdc>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk2"
SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="<serial_of_sdd>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk3"
```

Use `grid:asmdba`, mode 0660, consistently on both nodes, following the 26ai device-persistence guidance. **Verify** identities and permissions on the actual block devices, not only the symlinks. Restrict rules to whole block disks with `SUBSYSTEM=="block", ENV{DEVTYPE}=="disk"`.

5. Reload and verify on both nodes.

```bash
udevadm control --reload-rules
udevadm trigger
ls -l /dev/asm-disk*
ls -l /dev/sdb /dev/sdc /dev/sdd
```

Expected: asm-disk1 to sdb, asm-disk2 to sdc, asm-disk3 to sdd, owner grid, group asmdba, mode 660. Keep only one ASM rules file.

---

## Phase 5: User environments

Only the hostname and SID differ between nodes. `CV_ASSUME_DISTID` from the 19c runbook is removed because 26ai supports OL9 natively.

**grid `~/.bash_profile`** (node1 shown; on node2 use rac26node2 and +ASM2):

```bash
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=rac26node1
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

**oracle `~/.bash_profile`** (node1 shown; on node2 use rac26node2 and RAC2):

```bash
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=rac26node1
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
test -f ~/.ssh/id_rsa || ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa
ssh-copy-id rac26node1
ssh-copy-id rac26node2
```

Option B is to let the installer do it. 26ai documents automatic SSH configuration during installation (the SSH connectivity step in `gridSetup.sh` and `runInstaller`).

Before automation, verify destination host-key fingerprints through each VM console and accept them interactively for the exact public hostnames used below. Do not disable host-key checking. Verify from both nodes, as both users. Each command must return the date without a password or host-key prompt:

```bash
for h in rac26node1 rac26node2; do ssh -o BatchMode=yes "$h" date; done
```

Private aliases are used for interconnect tests, not this public-hostname SSH loop. If another tool uses FQDNs or private aliases, prepare and test their host-key entries separately. Stay with the selected OL9 baseline; do not infer unsupported platforms from a third-party anecdote.

---

## Phase 7: Grid Infrastructure install

Grid goes in from node 1 and is copied to node 2 by the installer. Do not continue to ASM or the database until `crsctl` shows both nodes healthy.

1. Check media integrity on node 1. Compare against the checksum on Oracle's download page. **Verify** the signature and Oracle signer/certificate chain using the 26ai install guide section "Verifying Digital Signature and Integrity of Installation Archive Files". Substitute the actual media filenames throughout this runbook.

```bash
sha256sum LINUX.X64_2326100_grid_home.zip LINUX.X64_2326100_db_home.zip
jarsigner -verify -verbose -certs LINUX.X64_2326100_grid_home.zip
jarsigner -verify -verbose -certs LINUX.X64_2326100_db_home.zip
```

`jarsigner` requires a suitable Java JDK; verification can be performed on another trusted machine before transferring the same verified bytes. Require the expected signature result and review signer/trust warnings; merely printing a SHA256 hash or seeing `jar verified` does not establish that the signer is trusted Oracle media.

2. As grid, unzip into the Grid home on node 1 only.

```bash
cd /u01/app/23.26/grid
unzip -q /path/to/LINUX.X64_2326100_grid_home.zip
```

3. Install cvuqdisk locally as root on both nodes. Transfer the RPM through the administrator account, then use sudo on node 2. Root SSH is not required. **Verify** the exact RPM filename before running; the command below shows the local installation on each node.

```bash
export CVUQDISK_GRP=oinstall
rpm -ivh /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm
```

On node 2, after transferring the verified RPM to `/tmp`, run from the administrator session:

```bash
sudo env CVUQDISK_GRP=oinstall rpm -ivh /tmp/cvuqdisk-*.rpm
```

4. As grid, run the cluster pre-check and fix every failure before installing.

```bash
cd /u01/app/23.26/grid
./runcluvfy.sh stage -pre crsinst -n rac26node1,rac26node2 -verbose
```

**Verify** and classify each prerequisite finding. A DNS-related finding may reflect this explicitly chosen single-address hosts-file lab; document the exact finding and consequence before proceeding. Do not blanket-ignore DNS, interface, connectivity or swap failures.

5. **Verify** log in directly as grid to node 1 with MobaXterm SSH X11 forwarding enabled. Verify the forwarded DISPLAY and an X client before launching. Do not hardcode DISPLAY or use an unauthenticated Windows X listener.

```bash
echo "$DISPLAY"
cd /u01/app/23.26/grid
./gridSetup.sh
```

6. Installer selections.

| Screen                | Value                                                              |
| --------------------- | ------------------------------------------------------------------ |
| Configuration option  | Configure Oracle Grid Infrastructure for a New Cluster             |
| Cluster name          | raccluster                                                         |
| SCAN name and port    | rac-scan.lab.test, 1521                                                     |
| Nodes                 | rac26node1 / rac26node1-vip, rac26node2 / rac26node2-vip                   |
| SSH connectivity      | Test (or Setup if you chose Option B in Phase 6)                   |
| Network interfaces    | 192.168.56.0 = Public, 192.168.57.0 = ASM & Private; actual NAT subnet = Do Not Use                |
| Storage               | Oracle ASM                                                         |
| Diskgroup             | OCR, External redundancy, /dev/asm-disk1                           |
| Disk discovery string | `/dev/asm-disk*`                                                   |
| ASM passwords         | Secure local values, never committed to GitHub                     |
| OS groups             | OSASM = asmadmin, OSDBA for ASM = asmdba, OSOPER for ASM = asmoper |
| Oracle base           | /u01/app/grid                                                      |
| Inventory             | /u01/app/oraInventory                                              |
| Root scripts          | Run manually as root from the administrator sudo session when prompted     |

There is no GIMR option to set; GIMR is desupported in 26ai.

7. Run the root scripts as root (from the administrator session using `sudo -i`) when prompted. Node 1 must finish before node 2 starts.

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

3. Mount them on node 2 (as grid on rac26node2).

```bash
srvctl start diskgroup -diskgroup DATA -node rac26node2
srvctl start diskgroup -diskgroup FRA -node rac26node2
```

4. Verify from either node.

```sql
SELECT inst_id, name, state, total_mb, free_mb FROM gv$asm_diskgroup ORDER BY name, inst_id;
SELECT name, compatibility, database_compatibility FROM v$asm_diskgroup;
```

Expected: OCR, DATA and FRA MOUNTED on both instances. **Verify** diskgroup Clusterware registration and startup persistence; if `srvctl` cannot find a newly SQL-created group, configure the resource through ASMCA or the documented matching-release procedure before retrying. Do not recreate or format the disks.

**Verify** record compatibility before DBCA. Oracle documents new 26ai defaults of `compatible.asm=23.0` and `compatible.rdbms=19.0` when omitted. `compatible.asm` must be at least `compatible.rdbms`, and the database COMPATIBLE must meet the diskgroup RDBMS requirement. Raising attributes is irreversible; do not raise them merely to silence an unrelated DBCA error. You can create/manage the groups through `asmca` instead of SQL.

---

## Phase 9: Database software install

Install software only, as a RAC home, from node 1. The installer copies it to node 2.

1. As oracle, unzip on node 1 only.

```bash
cd /u01/app/oracle/product/23.26/dbhome_1
unzip -q /path/to/LINUX.X64_2326100_db_home.zip
```

2. **Verify** log in directly as oracle using SSH X11 forwarding, confirm DISPLAY, change to the DB home and launch the installer.

```bash
echo "$DISPLAY"
cd /u01/app/oracle/product/23.26/dbhome_1
./runInstaller
```

3. Installer selections.

| Screen                          | Value                                                  |
| ------------------------------- | ------------------------------------------------------ |
| Configuration option            | Set Up Software Only                                   |
| Database installation option    | Oracle Real Application Clusters database installation |
| Nodes                           | rac26node1, rac26node2 (SSH test passes)                   |
| Edition                         | Enterprise Edition                                     |
| Oracle base                     | /u01/app/oracle                                        |
| OSDBA / OSOPER                  | dba / oper                                             |
| OSBACKUPDBA / OSDGDBA / OSKMDBA | backupdba / dgdba / kmdba                              |
| OSRACDBA                        | racdba (19c runbook used dba)                          |
| Root scripts                    | Run manually as root from the administrator sudo session when prompted       |

Do not choose single-instance installation. A RAC database cannot be created from a single-instance home.

4. Run the root script as root (via `sudo -i`) on node 1, then node 2.

```bash
/u01/app/oracle/product/23.26/dbhome_1/root.sh
```

5. Verify on both nodes as oracle.

```bash
sqlplus -v
$ORACLE_HOME/OPatch/opatch lspatches
ssh rac26node2 ls /u01/app/oracle/product/23.26/dbhome_1/bin/oracle
```

---

## Phase 10: Create the 2-node RAC database with DBCA

Run DBCA as oracle on node 1 with Advanced Configuration from a verified SSH X11 session. The result is a container database RAC with one PDB, RACPDB1.

```bash
echo "$DISPLAY"
dbca
```

| Screen                            | Value                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------ |
| Operation                         | Create a database                                                                    |
| Mode                              | Advanced configuration                                                               |
| Database type                     | Oracle Real Application Cluster (RAC) database                                       |
| Management                        | Admin Managed                                                                        |
| Template                          | General Purpose or Transaction Processing                                            |
| Nodes                             | rac26node1, rac26node2                                                                   |
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

Repeated connections are observations, not proof of alternating distribution. Confirm which instances advertise the PDB service and record actual routing. **Verify** create a deliberate application service associated with RACPDB1 through the matching-release SRVCTL procedure, with the intended instance placement, then use that service for availability testing. Record its configuration and status.

5. **Verify** instance-stop availability test: establish a baseline through the configured application service; stop RAC2, then make a **new** SCAN connection and confirm it reaches RAC1 with the PDB READ WRITE. Keep a separate existing test session to observe whether it disconnects; do not claim transparent session/transaction failover unless explicitly configured and demonstrated. Avoid application writes during this first test.

```bash
srvctl stop instance -db RAC -instance RAC2
srvctl status database -db RAC
srvctl start instance -db RAC -instance RAC2
```

After restart, recheck both instances, PDB open modes and service placement. **Verify** save PDB open state as appropriate, perform a controlled node reboot one node at a time, and confirm Clusterware, ASM, database, PDB and service recovery. Restart testing and node failure simulation are distinct tests.

---

## Phase 12: If DBCA fails, and final rules

Diagnose first and preserve the DBCA, alert, Clusterware and ASM logs before changing state. A failed DBCA operation does not automatically require wiping files or removing cluster registration.

1. Identify the exact failed database DB_UNIQUE_NAME, instances, diskgroup paths and resource names. Confirm no retained database uses them.
2. **Verify** use DBCA's supported rollback/delete workflow for the failed database where applicable; review its deletion summary and collect output.
3. Inspect remaining resources and files without deleting them:

```bash
srvctl config database -db RAC
srvctl status database -db RAC
ps -ef | grep '[p]mon'
grep -w RAC /etc/oratab
ls -l "$ORACLE_HOME/dbs"
```

As grid, inspect ASM paths:

```bash
asmcmd ls +DATA
asmcmd ls +FRA
```

4. **Verify** only if supported cleanup leaves confirmed orphan registration, review the installed SRVCTL help and remove the exact orphan resource. Resource removal is not proof that database files are removed.
5. If files remain, inventory exact paths and dependencies, confirm the failed database is stopped, and delete only explicitly identified artifacts. No wildcard `rm`, blanket ASM tree removal or OCR/voting-disk cleanup belongs in the routine retry procedure.
6. Resolve the original cause, rerun prerequisite/storage checks and then retry DBCA. Record the failed attempt and remediation.

### Final rules

1. Grid first, database second.
2. Keep one udev rules file, identical on both nodes.
3. Never wipe OCR or data disks after the build unless rebuilding everything.
4. Install the DB home as a RAC installation, never single-instance.
5. Use Advanced DBCA for the first build and save the response files.
6. Keep disk mapping, UIDs and GIDs fixed and documented.
7. Diagnose failures and preserve logs; remove only verified orphan artifacts before retrying.
8. Never commit passwords, disk serials or other live values to GitHub.
9. Stay on OL9 until 26ai RAC on OL10 is proven in your lab.
10. Resolve every **Verify** with recorded results during the first build. Change Status to Tested only after the complete procedure and acceptance tests have passed.


## References for this revision

- [26ai Grid OL9 kernel/RU requirements](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/supported-oracle-linux-9-distributions-for-x86-64.html)
- [26ai Grid operating-system checklist and virtualization reference](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/operating-system-checklist-for-oracle-grid-infrastructure-and-oracle-rac.html)
- [26ai SCAN requirements](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/about-the-scan.html)
- [26ai ASM device persistence](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/configuring-device-persistence-manually-for-oracle-asm.html)
- [26ai ASM creation and default compatibility values](https://docs.oracle.com/en/database/oracle/oracle-database/26/ostmg/create-diskgroups.html)

**Evidence status:** Preparation is in progress; no build evidence is published yet. Final installed OS layout, running kernel, node 2, shared-disk mapping, Grid installation and database validation remain to be recorded. This revision is not evidence of a completed 26ai cluster.

