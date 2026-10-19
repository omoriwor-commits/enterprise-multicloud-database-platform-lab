# Oracle AI Database 26ai Two-Node RAC Build Runbook

**Last updated:** 2026-10-19

## Overview

This runbook builds a two-node Oracle AI Database 26ai RAC on Oracle Linux 9 in VirtualBox. It follows the phases of my tested 19c runbook, updated for 26ai, with Phase 0 added for the VirtualBox setup. I completed the two-node RAC build through database creation between October 17 and October 19, 2026. The supplied October 19 terminal output confirms RAC1/RAC2 OPEN, RACPDB1 READ WRITE on both instances, and the database service ONLINE on both nodes. Remaining **Verify** items and the rest of Phase 11 acceptance testing are not yet confirmed. No database restart/failover or SCAN client test is claimed from resource status alone.

**Status:** Draft. Phases 0–10 completed from 2026-10-17 to 2026-10-19. Initial Phase 11 cluster, ASM, instance, PDB and service checks are confirmed by supplied terminal output. Remaining Phase 11 acceptance checks are pending; Phase 12 failure cleanup has not been exercised. Outstanding **Verify** items and the kernel/RU compatibility gap remain open.

**Baseline:** [Tested Oracle 19c two-node RAC build and troubleshooting runbook](oracle19c-2node-rac-build-and-troubleshooting.md).

**Scope:** Lab only. Firewall and SELinux shortcuts here are not for real environments. This runbook does not establish Oracle support for RAC in VirtualBox; verify the exact hardware, virtualization, OS/kernel and release-update combination against Oracle's current certification information.

**Related incident:** [Node 2 root-script VM freeze](https://github.com/omoriwor-commits/oracle-db-platform-automation/blob/docs/rac26-build-updates/Oracle-Database-Platform-Automation/incident-reports/2026-10-18-rac26-node2-root-script-vm-freeze.md). My first Grid root-script attempt on node 2 failed after a prolonged VM freeze. I subsequently confirmed VT-x with nested paging in both VM logs on October 18; raw evidence is still to be published.

### Lab layout

| Item                                | Node 1         | Node 2         |
| ----------------------------------- | -------------- | -------------- |
| VirtualBox VM name                  | rac26node1 | rac26node2 |
| OS hostname                         | racnode1 | racnode2 |
| Public IP (host-only, 192.168.56.x) | 192.168.56.101 | 192.168.56.102 |
| VIP                                 | 192.168.56.111 | 192.168.56.112 |
| Private interconnect (192.168.57.x) | 192.168.57.101 | 192.168.57.102 |
| ASM instance                        | +ASM1          | +ASM2          |
| DB instance                         | RAC1 (OPEN)    | RAC2 (OPEN)    |

SCAN: `rac-scan`, with hosts-file entries `192.168.56.120` through `192.168.56.122`. I observed three SCAN VIPs/listeners in this build. This is a lab observation, not a guarantee that repeated hosts-file entries provide correct resolution for every node or client. Oracle recommends DNS/GNS for SCAN; see the Phase 7 checks. Intended cluster name: `raccluster`; **Verify** the installed name with `cemutlo -n`.

**Verify** all example subnets are unused by the Windows host, VPNs and other VMs before assigning them. VIP and SCAN addresses must be reserved and unused; do not assign them manually to Linux interfaces.

### VM sizing

| Resource | Per node | Notes |
|---|---|---|
| RAM | 10 GiB (10240 MB) | Initial lab allocation on a 32 GiB host |
| vCPU | 2 | Four physical host cores are shared by both guests and Windows |
| OS/software disk | 100 GiB, dynamically allocated VDI | Separate disk for each node |

I used automatic partitioning on each 100 GB OS disk. The observed layout was:

| Volume / mount | Approximate size | Purpose |
|---|---:|---|
| `ol-root`, `/` | 64 GB | OS and `/u01`; no separate `/u01` mount |
| `ol-home`, `/home` | 31 GB | User homes |
| `ol-swap` | 4.9 GB | Initial swap; supplemented in Phase 1 |
| `/boot` | 1 GB | Boot files |

Record free space before staging, patching or extracting software:

```bash
df -hT
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
swapon --show
free -h
```

Shared disks are fixed size, Shareable, and attached at the same SATA ports on both VMs. These are the disks I reused from the deleted 19c cluster:

| SATA port | VDI file | Size | Observed device | Intended diskgroup / alias |
|---|---|---:|---|---|
| 1 | `data01.vdi` | 40 GB | `/dev/sdb` | DATA / `asm-disk2` |
| 2 | `fra01.vdi` | 30 GB | `/dev/sdc` | FRA / `asm-disk3` |
| 3 | `ocr01.vdi` | 20 GB | `/dev/sdd` | OCR / `asm-disk1` |

Device letters depend on controller port order and can shift. Map disks by serial and size, never by `sdX` alone. DATA and FRA were candidates before Phase 8. I have now created and mounted all three diskgroups on both ASM instances; see Phase 8.

### Software paths

| Item      | Path                                   |
| --------- | -------------------------------------- |
| Grid home | /u01/app/23.26/grid                    |
| Grid base | /u01/app/grid                          |
| DB home   | /u01/app/oracle/product/23.26/dbhome_1 |
| DB base   | /u01/app/oracle                        |
| Inventory | /u01/app/oraInventory                  |
| Staging | /u01/stage (`grid:oinstall`, mode 775) |

Media examples: `LINUX.X64_2326100_grid_home.zip` and `LINUX.X64_2326100_db_home.zip` identify 23.26.1 images. They are examples, not a frozen recommendation for every OL9 kernel. **Verify** the exact Grid and Database image/RU, patch README, OS and running kernel before installation. Oracle documents OL9 UEK8 support starting with RU 23.26.2; do not install 23.26.1 unchanged on UEK8 and assume compatibility. Use a documented supported kernel or obtain/apply compatible updates according to their installation instructions. Keep matching intended Grid/Database patch levels on both nodes. Home directory names do not establish installed versions.

**Outstanding kernel/RU compatibility gap:** My reported build runs Oracle Linux 9.8, UEK `6.12.0-207.111.5.4.el9uek.x86_64`, Grid 23.26.1 and SQL*Plus 23.26.1 on both nodes. The successful installation is an observed lab result, not certification. Oracle's [Grid](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/supported-oracle-linux-9-distributions-for-x86-64.html) and [Database](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/supported-oracle-linux-9-distributions-for-x86-64.html) guides document UEK8 support starting with RU 23.26.2. The database has now been created and is OPEN, but that does not close this gap. **Before further acceptance or failure testing, reconcile the running kernel and actual Grid/DB patch inventories with a documented compatible combination.** Select a documented supported kernel or plan compatible Grid and DB RUs using their patch READMEs; this runbook does not claim that either correction has been performed.

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

Build node 1 through Phases 1, 2, 3 and 5 before creating node 2 as a powered-off full clone. Then complete node 2 identity/network changes, attach the verified reused shared disks and run Phase 4 and Phases 6 onward. Checks requiring node 2 wait until node 2 exists. If building node 2 independently, complete all preparation phases on both nodes.

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
4. Record the completed node 1 inventory, then shut down Linux cleanly. With node 1 fully powered off and shared disks not yet attached, make a **Full Clone** named `rac26node2`. Choose "Generate new MAC addresses for all network adapters" and leave **Keep Disk Names** and **Keep Hardware UUIDs** unticked. Do not clone after Grid installation.
5. Keep node 1 off until node 2's IPs have changed. On node 2 only, from its console as root, reset the copied identities before anything else:

```bash
rm -f /var/lib/dbus/machine-id
rm -f /etc/machine-id && systemd-machine-id-setup
ln -s /etc/machine-id /var/lib/dbus/machine-id
rm -f /etc/ssh/ssh_host_* && ssh-keygen -A && systemctl restart sshd
hostnamectl set-hostname racnode2
```

Removing the D-Bus copy prevents `systemd-machine-id-setup` from reusing that copied ID; restore it as a symlink afterward. Stop if the two nodes still show the same ID. A full clone copies the machine-id, which can confuse DHCP, logging and management tools; Clusterware does not use it for cluster identity. It also copies SSH host keys, making both nodes present the same SSH identity; I caught this because both nodes showed the same ED25519 fingerprint.

Set node 2's public/private addresses to `.102` and Phase 5 profiles to `+ASM2` / `RAC2`. Check interface/profile mapping after MAC regeneration. On each node, inspect these locally and confirm the values differ between nodes; do not publish the IDs or fingerprints:

```bash
cat /etc/machine-id
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Reset any copied grid/oracle user SSH keys before Phase 6 so each user/node has its own key.

6. With both VMs off, attach the same `data01.vdi`, `fra01.vdi` and `ocr01.vdi` files, fixed size and Shareable, at ports 1, 2 and 3 respectively on both nodes. The OS disk stays at port 0. Confirm full paths and identities in VirtualBox's Media manager, without publishing live identifiers.

These disks came from my deleted 19c cluster and carried old ASM headers. The Phase 4 wipe was mandatory **once before provisioning this fresh build**. Before any wipe, confirm that each disk is attached only to `rac26node1` and `rac26node2`. Do not repeat the wipe now that Grid/OCR is installed.

### Host prerequisites — VT-x confirmed in my build

For this build I want VirtualBox using hardware VT-x rather than Hyper-V "snail mode". Check each VM's log after starting it, from PowerShell:

```powershell
Select-String -Path "<VM folder>\Logs\VBox.log" -Pattern "Snail|VT-x is not available|HMR3Init"
```

My logs showed `VT-x is not available` and `Snail execution mode is active`. Windows Virtual Machine Platform for WSL2/Docker Desktop can start the Windows hypervisor even without a running Hyper-V guest. VirtualBox documents performance degradation with Hyper-V; the exact Windows feature responsible on my host still needs confirmation.

Quit Docker Desktop, shut down the lab VMs, then run from an elevated Windows terminal and reboot Windows:

```powershell
bcdedit /set hypervisorlaunchtype off
```

To undo that boot setting, use `bcdedit /set hypervisorlaunchtype auto` and reboot. Check Virtualization-Based Security, Core Isolation/Memory Integrity and the Windows virtualization features too; changing them affects WSL2/Docker availability and may affect host security. See [VirtualBox Hyper-V troubleshooting](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/Troubleshooting.html).

The first `bcdedit` attempt did not remove snail mode. **Resolved in my build on 2026-10-18:** I subsequently confirmed that both VM logs showed VT-x with nested paging and unrestricted guest execution. This is my reported log result; the before/after logs have not been supplied or published with this update. Do not treat a boot-setting value alone as proof that the Windows hypervisor is absent.

Before starting a VM after the Windows reboot, inspect the boot setting, hypervisor detection and VBS state from an elevated PowerShell session:

```powershell
bcdedit /enum | findstr /i hypervisorlaunchtype
systeminfo | Select-String "Hyper-V" -Context 0,4
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard | Select-Object VirtualizationBasedSecurityStatus
```

For my selected native-VT-x configuration, `hypervisorlaunchtype` should be Off, systeminfo should not report a detected hypervisor, and VBS should not be running. Confirm the VM's fresh VBox.log reports VT-x/nested paging after startup. Displayed wording varies by Windows/VirtualBox version; keep host and VM evidence together.

Set Windows to never sleep while the lab runs; my host suspended overnight. Copy each VM's `VBox.log` before its next start if it is needed as evidence, because VirtualBox rotates logs at VM start. Redact Windows paths as `C:\Users\<user>\...` and remove IDs, MACs and VM UUIDs before publishing.

---

## Phase 1: OS prep on both nodes

Both nodes need Oracle Linux 9, static public/private cluster interfaces plus NAT for outbound access, matching time, and consistent name resolution before any Oracle software goes on. OS commands in Phases 1–4 require root privileges; use `sudo -i` from the administrator account rather than enabling password-based root SSH.

1. Confirm the OS release and kernel on both nodes.

```bash
cat /etc/oracle-release
uname -r
```

My reported OS/kernel on both nodes: Oracle Linux Server 9.8 and UEK `6.12.0-207.111.5.4.el9uek.x86_64`. The Software paths kernel/RU compatibility gap remains open after database creation. My build temporarily allowed password-based root SSH; the procedure here continues to use the administrator account and `sudo -i`. Remove that temporary root-password access during hardening; do not enable it just to follow the runbook.

2. Set the hostname.

```bash
# node1
hostnamectl set-hostname racnode1
# node2
hostnamectl set-hostname racnode2
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

Replace the angle-bracket connection placeholders; do not run them literally. Verify no stale .101 address remains on node 2. My NAT adapter showed `10.0.4.15` on each VM; duplicate guest addresses are normal when the VMs use separate per-VM NAT networks, not a shared NAT Network.

Add these entries to `/etc/hosts` on both nodes; preserve required localhost entries and remove conflicting old RAC entries.

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

Do not continue to Grid until both nodes show a synchronized source. CTSS is desupported in 26ai; this build uses chrony. Verify synchronization again after cloning and rebooting.

6. Lab only: stop the firewall and set SELinux to permissive.

```bash
systemctl disable --now firewalld
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config
getenforce
```

Record the SELinux mode you end up using. My October node 2 incident ended with SELinux disabled and an unconfirmed root cause, so note it rather than changing it silently later.

Before Grid prerequisites, disable avahi on both nodes. I missed this initially and cluvfy reported PRVG-1359 / PRVG-1360:

```bash
systemctl disable --now avahi-daemon.socket avahi-daemon.service
```

7. **Verify** install the 26ai preinstall RPM before creating Oracle users manually. Review the proposed package transaction and any kernel changes against the selected Grid/Database RU before updating. Do not blindly boot a new kernel family with older installation media.

```bash
dnf install oracle-ai-database-preinstall-26ai
dnf check-update
grubby --default-kernel
```

My 1 GB `/boot` was 72% used. Before a full `dnf update`, set the existing `installonly_limit` entry to `2` under `[main]` in `/etc/dnf/dnf.conf` (add it only if absent). Inspect installed UEK packages and `/boot` usage, then select obsolete UEK versions for removal through `dnf`, reviewing the transaction first. Never remove the running kernel or the selected working fallback; if both must be retained, keep them and resolve space before updating. Do not use wildcard removal. Kernel/RU compatibility still takes priority over installing the newest kernel.

```bash
df -h /boot
uname -r
rpm -q kernel-uek
grubby --info=ALL
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

**Verify** both nodes have the same intended kernel/packages, and record clock source and THP state. Oracle recommends `tsc` for suitable virtual x86-64 environments. The [26ai Grid OS guide](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/configuring-operating-systems-for-oracle-grid-infrastructure-on-linux.html) recommends THP `madvise` for UEK7 and later. The actual clock source and THP state have not been confirmed in the supplied build record. Plan any persistent setting change against the selected kernel/RU, then verify it after reboot; explicit HugePages sizing is a separate task.

### Swap correction used in this build

Automatic partitioning provided about 4.9 GB swap; cluvfy required about 9.27 GB for the 10 GB RAM allocation. I added a 5 GB swap file on each node. This is a **one-time provisioning step**, not a command block to rerun blindly. The guard refuses an existing file or fstab entry; investigate partial setup instead of overwriting it.

```bash
if [ -e /swapfile ] || grep -Eq '^[[:space:]]*/swapfile[[:space:]]' /etc/fstab; then
    echo 'STOP: /swapfile already exists or is registered; inspect current swap.'
else
    dd if=/dev/zero of=/swapfile bs=1M count=5120 &&
    chmod 600 /swapfile &&
    mkswap /swapfile &&
    swapon /swapfile &&
    printf '%s\n' '/swapfile none swap defaults 0 0' >> /etc/fstab
fi
swapon --show
free -g
grep -c swapfile /etc/fstab
```

Expected: the original swap plus `/swapfile`, sufficient total swap for cluvfy, and exactly `1` matching fstab line. Check both nodes and confirm swap survives the next controlled reboot.

---

## Phase 2: Users, groups, limits

The preinstall RPM from Phase 1 does most of the work the 19c runbook did by hand. This phase checks what it created and adds only what it does not. UIDs and GIDs must match on both nodes.

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

7. Check limits. The RPM sets limits for oracle only, so add `/etc/security/limits.d/99-grid.conf` on both nodes. I missed this file on the first pass; cluvfy failed soft stack (PRVG-0449) and maximum locked memory (PRVE-0059).

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

8. As root, confirm limits in a fresh login on both nodes. `su - grid` run as root should not prompt for a password.

```bash
su - grid -c 'ulimit -s; ulimit -l; ulimit -n; ulimit -u'
su - oracle -c 'ulimit -u; ulimit -n; ulimit -s'
```

Expected grid values, in order: `10240`, `unlimited`, `1024`, `16384`. Check both nodes before rerunning cluvfy.

---

## Phase 3: Directories and ownership

Create the same tree on both nodes. Grid owns its home, base and the inventory; oracle owns the DB base and home.

```bash
mkdir -p /u01/app/23.26/grid
mkdir -p /u01/app/grid
mkdir -p /u01/app/oracle/product/23.26/dbhome_1
mkdir -p /u01/app/oraInventory
mkdir -p /u01/stage

chown -R grid:oinstall /u01/app/23.26
chown -R grid:oinstall /u01/app/grid
chown -R grid:oinstall /u01/app/oraInventory
chown -R oracle:oinstall /u01/app/oracle
chown grid:oinstall /u01/stage

chmod -R 775 /u01/app
chmod 775 /u01/stage
chmod 755 /u01
```

Verify the full path permissions:

```bash
namei -om /u01/app/23.26/grid
namei -om /u01/app/oracle/product/23.26/dbhome_1
```

---

## Phase 4: Shared disks and udev

ASM needs the same three disks with persistent identities on both nodes. I used udev; ASM Filter Driver is desupported in 26ai.

1. Check the disks on **both nodes** and compare serials and sizes with VirtualBox's Media manager. The observed letters follow my SATA port order; they are not permanent identities.

```bash
lsblk -o NAME,SIZE,SERIAL
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt
udevadm info --query=property --name=/dev/sdd | grep ID_SERIAL=
```

`ID_SERIAL` has the form `VBOX_HARDDISK_<serial>`. OCR is 20 GB (`sdd` in this build), DATA 40 GB (`sdb`), and FRA 30 GB (`sdc`). If you reuse disks from an earlier build, the serials will match the old ones; new disks get new serials. Keep actual serials private.

2. **Fresh-build cleanup only, node 1 only, MobaXterm multi-execution OFF.** I reused disks from the deleted 19c cluster, so removing their old headers was mandatory before installing Grid. Confirm the VDI files belong only to `rac26node1` and `rac26node2`, that no retained database uses them, and that the devices/partitions are unmounted and unused on either node. Inspect signatures without changing them:

```bash
wipefs -n /dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_ocr_disk>
wipefs -n /dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_data_disk>
wipefs -n /dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_fra_disk>
```

Only after confirming the mapping and intentional disposal of the old cluster, replace the placeholders with the exact local by-id paths and clear the first 100 MiB once, on node 1:

```bash
dd if=/dev/zero of=/dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_ocr_disk> bs=1M count=100 conv=fsync
dd if=/dev/zero of=/dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_data_disk> bs=1M count=100 conv=fsync
dd if=/dev/zero of=/dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_fra_disk> bs=1M count=100 conv=fsync
```

Never use transient `sdX` names for this wipe. Never repeat it after OCR/voting files or database data are installed; the completed Phase 7 build must skip this destructive provisioning step.

3. Inspect ID_SERIAL on both nodes and match each whole disk to its role:

```bash
for d in sdb sdc sdd; do udevadm info --query=property --name=/dev/$d | grep ID_SERIAL=; done
```

4. Create one identical `/etc/udev/rules.d/99-oracle-asm.rules` on both nodes. Replace placeholders locally; keep the `VBOX_HARDDISK_` prefix exactly as returned by udev:

```text
SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="VBOX_HARDDISK_<serial_of_ocr_disk>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk1"
SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="VBOX_HARDDISK_<serial_of_data_disk>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk2"
SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="VBOX_HARDDISK_<serial_of_fra_disk>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk3"
```

The [26ai Grid Infrastructure Installation Guide](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/configuring-device-persistence-manually-for-oracle-asm.html) sets ASM devices to the installation owner and the OSDBA for Oracle ASM group (`asmdba`), mode 0660. My 19c build used the same group. [Older guides (12.2)](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/cwlin/configuring-device-persistence-manually-for-oracle-asm.html) used the OSASM group, `asmadmin`.

5. Reload and wait for udev on both nodes. My first `ls` ran too early and found nothing:

```bash
udevadm control --reload-rules
udevadm trigger
udevadm settle
ls -lL /dev/asm-disk*
md5sum /etc/udev/rules.d/99-oracle-asm.rules
```

Expected block-device permissions: `brw-rw----`, owner `grid`, group `asmdba`. The rules-file checksums must match on both nodes. `asm-disk1` is OCR 20 GB, `asm-disk2` DATA 40 GB and `asm-disk3` FRA 30 GB; verify the actual backing devices rather than assuming their letters.

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

I configured passwordless SSH for grid and oracle on each node before Phase 7; `runcluvfy.sh` needs it already working. Repeat the flow for **each user on each node**, including self-connections.

1. As root, run `su - grid` (or `su - oracle`) **on its own line**, then wait for that user's prompt. Do not paste a block beginning with `su -`: on my first attempt the remaining commands ran as root. Confirm `whoami` before proceeding.

2. Paste only these non-interactive lines. Keep an existing intended key rather than overwriting it:

```bash
test -f ~/.ssh/id_rsa || ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa
ssh-keyscan -t ed25519 racnode1 racnode2 racnode1-priv racnode2-priv 2>/dev/null >> ~/.ssh/known_hosts
ssh-keygen -lf ~/.ssh/known_hosts
```

Before trusting the scanned keys, compare their fingerprints with each VM's local console output from Phase 0. Node 1's public/private entries must match each other; node 2's entries must match each other; the two nodes must differ. Consistency in `ssh-keyscan` alone does not authenticate the hosts. Remove only a confirmed stale entry if the clone's old key is still present; do not disable host-key checking.

3. Run each command separately and finish any prompt before the next command:

```bash
ssh-copy-id racnode1
```

```bash
ssh-copy-id racnode2
```

4. As the current grid/oracle user, verify all four aliases without password or host-key prompts:

```bash
for h in racnode1 racnode2 racnode1-priv racnode2-priv; do ssh -o BatchMode=yes "$h" hostname; done
```

After completing both users, run this final check as root on **both nodes**. It must succeed and print eight hostnames per node:

```bash
for user in grid oracle; do
    su - "$user" -c 'for h in racnode1 racnode2 racnode1-priv racnode2-priv; do ssh -o BatchMode=yes "$h" hostname || exit 1; done' || break
done
```

### SSH performance correction found during Phase 9

The database installer reported INS-06009 even though its SSH connectivity test passed. In my timing comparison, login took about 1.96 seconds with GSSAPI and 0.67 seconds without it. Disabling GSSAPI for the four RAC aliases removed that delay in my lab; this is an observed correction, not a diagnosis for every slow SSH login.

For grid and oracle on **each node**, edit `~/.ssh/config` and add or update the matching Host stanza. Inspect existing matching `Host`/`Match` rules first: SSH generally uses the first obtained setting, so appending duplicate blocks may not override an earlier value. Keep the change limited to the RAC aliases; see the [OpenSSH client configuration reference](https://man.openbsd.org/ssh_config):

```text
Host racnode1 racnode2 racnode1-priv racnode2-priv
    GSSAPIAuthentication no
```

```bash
chmod 600 ~/.ssh/config
for h in racnode1 racnode2 racnode1-priv racnode2-priv; do
    ssh -G "$h" | grep '^gssapiauthentication '
    ssh -o BatchMode=yes "$h" hostname
done
time ssh -o BatchMode=yes racnode2 date
```

Expected effective setting: `gssapiauthentication no` for each alias, and prompt-free logins. Recheck from both users on both nodes. My measured sub-second result is a reference, not a universal pass threshold. Do not disable host-key checking or assume a successful login excludes DNS, CPU or other sources of delay.

---

## Phase 7: Grid Infrastructure install

I installed Grid from node 1; the installer copied the home to node 2. This phase completed on October 18, 2026 after the node 2 root-script retry described below. I subsequently completed DATA/FRA diskgroup creation, the RAC software-only installation and database creation in Phases 8–10.

1. Download media in a browser or with wget. Replace the placeholders locally; never commit a signed link or its AuthParam token. Capital `-O` selects the output file; lowercase `-o` selects wget's log:

```bash
mkdir -p /u01/stage
wget -c -O /u01/stage/<file> "<signed link>"
```

I checked both hashes against Oracle's 26ai Linux download page during the build. These exact hashes and byte sizes were also confirmed against the [published download page](https://www.oracle.com/database/technologies/oracle26ai-linux-downloads.html) during this documentation update:

| Archive | Bytes | SHA-256 |
|---|---:|---|
| `LINUX.X64_2326100_db_home.zip` | 2,406,058,543 | `2a5d2583df076209e624dff750829f9a562473c27c8f926d546cf9ad2a1a2efd` |
| `LINUX.X64_2326100_grid_home.zip` | 1,089,544,451 | `2deb199610357780ebb4d1213d6aa52df1694c7b12bd21f9e02dc3f9c992cd61` |

```bash
sha256sum /u01/stage/LINUX.X64_2326100_grid_home.zip /u01/stage/LINUX.X64_2326100_db_home.zip
```

**Verify** the digital signature and Oracle signer/certificate chain using the matching installation guide. This separate signature check is retained; its execution is not established by the build record supplied for this revision:

```bash
jarsigner -verify -verbose -certs /u01/stage/LINUX.X64_2326100_grid_home.zip
jarsigner -verify -verbose -certs /u01/stage/LINUX.X64_2326100_db_home.zip
```

`jarsigner` needs a suitable JDK and may be run on another trusted machine before transferring the same verified bytes. Review signer/trust warnings; `jar verified` alone does not establish trusted Oracle provenance. Keep the kernel/RU compatibility gate in Software paths even though the base-image hashes match.

2. As grid, unzip into the Grid home on node 1 only:

```bash
cd /u01/app/23.26/grid
unzip -q /u01/stage/LINUX.X64_2326100_grid_home.zip
```

3. Install cvuqdisk on both nodes. As grid on node 1, transfer the RPM to node 2:

```bash
scp /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm racnode2:/tmp/
```

As root on node 1:

```bash
export CVUQDISK_GRP=oinstall
rpm -ivh /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm
```

On node 2, from the administrator sudo session:

```bash
sudo env CVUQDISK_GRP=oinstall rpm -ivh /tmp/cvuqdisk-*.rpm
```

The RPM emitted a `NOKEY` signature warning in my build. That warning means the signing key is not available locally; it is not proof of authenticity or a reason to accept arbitrary RPMs. Use only the RPM from the verified Oracle archive. Check on both nodes:

```bash
ls -l /usr/sbin/cvuqdisk
```

Expected: `-rwsr-xr-x`, owner `root`, group `oinstall`. My installed package was `cvuqdisk-1.0.10-1`.

4. As grid, run the cluster pre-check with explicit cluster interfaces so the NAT adapter is excluded:

```bash
cd /u01/app/23.26/grid
./runcluvfy.sh stage -pre crsinst -n racnode1,racnode2 -networks enp0s3:192.168.56.0:PUBLIC/enp0s8:192.168.57.0:cluster_interconnect -verbose
```

INFORMATION entries for skipped root-only checks and ORAchk were expected; they are not passed checks. Resolve avahi, swap, limits, storage, SSH and interface failures before installing. I accepted only the documented SCAN DNS/NIS limitation below.

5. Log in **directly as grid** through MobaXterm SSH with X11 forwarding. Do not launch the GUI through `su - grid` from a root session, hardcode DISPLAY or use unauthenticated X access:

```bash
echo "$DISPLAY"
cd /u01/app/23.26/grid
./gridSetup.sh
```

6. These are the screens and selections from my 26ai build:

| Screen | Selection / observation |
|---|---|
| Configuration Option | New Cluster |
| Cluster Configuration | Manage Oracle RAC databases; not Extended |
| Grid Plug and Play | Create Local SCAN; intended cluster `raccluster` (default was `racnode-cluster`); SCAN `rac-scan`, port 1521; no GNS |
| Network Interface Usage | `enp0s3` Public; `enp0s8` ASM & Private; `enp0s9` IPv4 `10.0.4.0` and IPv6 Do Not Use |
| Storage Option | Flex ASM; separate OCR backup disk group not selected |
| ASM disk group | OCR, External redundancy, AU 4 MB; discovery `/dev/asm-disk*`; select `/dev/asm-disk1` only. All three disks showed Candidate |
| ASM password | Local lab value; INS-30011 accepted. Never publish or reuse it; change it before connecting the lab externally |
| Automatic Self Correction | Off; I want changes to be deliberate and documented |
| Failure Isolation / Management | No IPMI; no EM registration |
| OS groups | OSASM `asmadmin`; OSDBA for ASM `asmdba`; OSOPER for ASM `asmoper` |
| Installation Location | Base `/u01/app/grid`; INS-40109 appeared because cluvfy had written `$ORACLE_BASE/diag`; I checked the directory on both nodes before proceeding |
| Root scripts | Automatic option with root credentials, entered locally |
| Prerequisite checks | Only DNS/NIS name service failed because SCAN was in `/etc/hosts`; I selected Ignore All for that recorded finding only |

Earlier builds used `oinstall` for all Grid roles; this build uses role separation. There is no GIMR option in 26ai. **Verify** the actual cluster name with `cemutlo -n`; I skipped the Summary screen, so `raccluster` is still the intended value until checked. Do not use Ignore All if any additional prerequisite fails.

7. I used automatic root-script execution. For manual execution, use root (`sudo -i` from the administrator session) and run these when prompted on node 1 **to completion**, then node 2; never in parallel:

```bash
/u01/app/oraInventory/orainstRoot.sh
/u01/app/23.26/grid/root.sh
```

Node 2's first root script failed with CLSRSC-117 after the VM froze for about 71 minutes. The retry succeeded. See the [October 18 incident report](https://github.com/omoriwor-commits/oracle-db-platform-automation/blob/docs/rac26-build-updates/Oracle-Database-Platform-Automation/incident-reports/2026-10-18-rac26-node2-root-script-vm-freeze.md); I later confirmed native VT-x in both VM logs on October 18.

Inspect root-script logs without relying on ambiguous `tail -15` parsing when the wildcard matches several files:

```bash
tail -n 15 /u01/app/grid/crsdata/racnode1/crsconfig/rootcrs_racnode1_*.log
tail -n 15 /u01/app/grid/crsdata/racnode2/crsconfig/rootcrs_racnode2_*.log
```

The installer ended with `INS-43080`, exit status `-1`. I traced the post-install CVU failure to PRVH-1558 / PRVG-1101, SCAN missing from DNS; the other post-install checks passed in my record. Treat a different failure set as a new incident, not an expected warning.

I kept `/u01/app/23.26/grid/install/response/grid_<timestamp>.rsp`, checked the short password keys (`sysasmPassword=`, `asmsnmpPassword=`) were empty, and set mode 600. Do not publish the whole response file without another secret review; it is useful later for a silent install.

8. As grid, check both nodes and preserve the actual results:

```bash
crsctl check cluster -all
crsctl stat res -t
crsctl query crs activeversion
olsnodes -n -s
ocrcheck
srvctl config scan
srvctl status scan_listener
cemutlo -n
```

`crsctl check cluster -all` must list both nodes. In my resource table, ASM, OCR, node listeners/VIPs, three SCAN VIPs/listeners, ASM network, ONS and CVU were ONLINE. `ora.helper`, `ora.cdp1`–`ora.cdp3`, `ora.cvuhelper` and `ora.rhpserver` were OFFLINE; that was acceptable for this lab's configured features, not a blanket rule for other clusters. Compare target/state/details before diagnosing a resource as failed. At this Phase 7 checkpoint, DATA/FRA diskgroups had not been created. Phase 8 records their subsequent creation; the October 19 Phase 11 output now also confirms both database instances OPEN.

### SCAN resolution and the lab exception

I observed three SCAN VIP/listener resources after using three `/etc/hosts` entries. Confirm resource configuration with `srvctl config scan`, and check `getent hosts rac-scan` on both nodes and each client. Resource count does not prove correct client resolution or connection distribution.

[Oracle's SCAN DNS guidance](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/confirming-the-dns-configuration-for-scan.html) recommends against hosts-file SCAN configuration and describes its single-address limitation. My observed resource count does not change that guidance: the hosts-file exception affects server validation as well as clients. Configure and verify DNS/GNS before treating three-address SCAN resolution as a reproducible supported setup.

### Preserve Phase 7 evidence

Before any reboot, copy installer and cluvfy logs from `/tmp` to `/home/grid/evidence/phase07/`. Identify exact log paths first, then copy each intended file; root's `cp` may be aliased to `cp -i`, so `command cp` avoids an unexpected prompt. For example, as root with real source paths substituted:

```bash
install -d -o grid -g oinstall -m 700 /home/grid/evidence/phase07
command cp -a /tmp/<installer-log> /home/grid/evidence/phase07/
command cp -a /tmp/<cluvfy-log> /home/grid/evidence/phase07/
```

Check copied files, grant grid access to the intended copies if needed, and redact before publishing. The raw logs were not supplied with this documentation update; results here record my build account, not independent replay of the lab.

## Operating the cluster

I tested Clusterware/SCAN operations before creating a database. Run Clusterware stop/start commands as root. If `crsctl stop cluster -all` fails with CRS-4405, stop locally on each node:

```bash
crsctl stop crs
crsctl check crs
```

CRS-4639 confirms the local High Availability Services could not be contacted after stopping. Once both nodes are stopped, start CRS on each node and recheck cluster membership/resources:

```bash
crsctl start crs
crsctl check cluster -all
crsctl stat res -t
```

After my restart, node 2's VIP stayed FAILED OVER on node 1. With node 2 healthy, I used srvctl as grid:

```bash
srvctl config vip -node racnode2
srvctl relocate vip -vip racnode2-vip -node racnode2
crsctl stat res ora.racnode2.vip ora.LISTENER.lsnr -t
```

The listener restarted when its VIP returned. PRCZ-4054, "already running", was harmless in that confirmed state; verify the listener before dismissing it elsewhere. Stopping node 1 first relocated its SCAN VIPs/listeners to node 2, demonstrating SCAN resource failover. This earlier SCAN resource relocation did not test database or application-service failover; it happened before database creation. After the host correction, I started both nodes together and observed each VIP staying on its own node.

---

## Phase 8: ASM diskgroups

I created DATA and FRA from the X11-forwarded grid session on node 1 using `asmca` (Disk Groups → Create), selecting External redundancy, AU 4 MB and one intended disk per group. ASMCA mounted the groups on both nodes. These are reported build results; sanitized outputs are still to be published.

1. Before creation, check disk identity and header state. Do not rerun CREATE against the completed groups:

```bash
sqlplus / as sysasm
```

```sql
SET LINESIZE 150
COLUMN path FORMAT a20
SELECT path, header_status, mount_status, ROUND(total_mb/1024) gb
FROM v$asm_disk ORDER BY path;
```

Before creation, OCR (`asm-disk1`) was MEMBER and DATA/FRA (`asm-disk2` / `asm-disk3`) were CANDIDATE, CLOSED. After creation, all three disks showed MEMBER, CACHED.

2. For a future fresh build, the SQL alternative is below. **Verify** the resulting AU size, attributes, Clusterware registration and startup persistence if using SQL; ASMCA manages resource integration that a bare SQL command should not be assumed to perform:

```sql
CREATE DISKGROUP DATA EXTERNAL REDUNDANCY DISK '/dev/asm-disk2';
CREATE DISKGROUP FRA  EXTERNAL REDUNDANCY DISK '/dev/asm-disk3';
```

If using the SQL route, start registered diskgroups on node 2:

```bash
srvctl start diskgroup -diskgroup DATA -node racnode2
srvctl start diskgroup -diskgroup FRA -node racnode2
```

If srvctl cannot find a newly SQL-created group, configure the resource through ASMCA or the documented matching-release procedure. Do not recreate or format the disks.

3. Verify the actual group attributes and both ASM instances:

```sql
COLUMN name FORMAT a8
SELECT name, compatibility, database_compatibility,
       allocation_unit_size/1048576 au_mb
FROM v$asm_diskgroup ORDER BY name;
SELECT inst_id, name, state FROM gv$asm_diskgroup ORDER BY name, inst_id;
```

My build results:

| Diskgroup | Size | compatible.asm | compatible.rdbms | AU | State |
|---|---:|---|---|---|---|
| DATA | 40 GB | 23.0.0.0.0 | 19.0.0.0.0 | 4 MB | MOUNTED on ASM instances 1 and 2 |
| FRA | 30 GB | 23.0.0.0.0 | 19.0.0.0.0 | 4 MB | MOUNTED on ASM instances 1 and 2 |
| OCR | 20 GB | 23.0.0.0.0 | 19.0.0.0.0 | 4 MB | MOUNTED on ASM instances 1 and 2 |

`compatible.asm` must be at least `compatible.rdbms`, and the database COMPATIBLE must meet the diskgroup RDBMS requirement. The observed 19.0 RDBMS requirement does not itself require raising the attributes for 26ai. Raising them is irreversible; do not change them just to silence an unrelated DBCA error. **Verify** startup persistence at the next controlled restart; current mounts do not prove reboot recovery.

---

## Phase 9: Database software install

I installed the RAC database home in software-only mode from node 1. The installer copied the home to node 2; that software-install phase did not create a database. Database creation was completed afterward in Phase 10. Both nodes reported SQL*Plus 23.26.1.0.0. The kernel/RU compatibility gate remains open despite successful installation.

1. Log in directly to node 1 as oracle using MobaXterm SSH X11 forwarding. Do not launch through `su - oracle` from root:

```bash
whoami
hostname
echo "$DISPLAY"
echo "$ORACLE_HOME"
```

My DISPLAY was `localhost:11.0` while the grid session used `:10`; use the authenticated value assigned to the current session, not a hardcoded display number.

2. On a fresh software installation, confirm the DB home is empty before extracting. Skip extraction for the completed home:

```bash
ls -ld "$ORACLE_HOME"
ls -A "$ORACLE_HOME"
cd "$ORACLE_HOME"
unzip -q /u01/stage/LINUX.X64_2326100_db_home.zip
ls -l runInstaller
```

Expected initial home ownership: `oracle:oinstall`. Do not delete an existing home to make this check pass.

3. Run the installer as oracle:

```bash
./runInstaller
```

| Screen | Selection / observation |
|---|---|
| Configuration Option | Set Up Software Only |
| Database Installation Options | Oracle Real Application Clusters database installation |
| Nodes Selection | racnode1 and racnode2 listed and selected; SSH Test, not Setup |
| Installation Location | Base `/u01/app/oracle`; home `/u01/app/oracle/product/23.26/dbhome_1` |
| OS groups | OSDBA `dba`, OSOPER `oper`, OSBACKUPDBA `backupdba`, OSDGDBA `dgdba`, OSKMDBA `kmdba`, OSRACDBA `racdba` |
| Root script process | Automatic with root credentials entered locally |
| Prerequisite Checks | HugePages Existence warning and SCAN DNS/NIS failure only in my run; I recorded and accepted those findings |
| Summary | Enterprise Edition, Set Up Software Only, both nodes listed |

There was no separate edition screen in my run; I checked Enterprise Edition on the Summary. The OSOPER field was initially blank, so select `oper` deliberately. Do not choose single-instance installation. Node 2's presence in the installer showed Grid inventory registration, not complete database readiness. Accept no additional prerequisite failure without diagnosing it; installer success does not resolve the UEK8/RU gap.

INS-06009 reported slow SSH even though connectivity passed. The Phase 6 GSSAPI correction reduced the measured delay. I deferred explicit HugePages configuration until the intended SGA is known; size and verify it before database acceptance. THP and explicit HugePages are separate settings.

4. With VT-x active, installation took about 12 minutes. Root scripts completed on node 1, then node 2, with no errors in my record. The finish screen reported "The registration of Oracle AI Database was successful." If running manually on a future build, execute `$ORACLE_HOME/root.sh` as root on node 1 to completion, then node 2, when prompted.

5. Verify both homes as oracle. A non-login SSH command does not load `.bash_profile`, so use explicit paths/environment for remote checks:

```bash
"$ORACLE_HOME/bin/sqlplus" -v
ls -l "$ORACLE_HOME/bin/oracle"
ssh racnode2 'ORACLE_HOME=/u01/app/oracle/product/23.26/dbhome_1 /u01/app/oracle/product/23.26/dbhome_1/bin/sqlplus -v'
ssh racnode2 ls -l /u01/app/oracle/product/23.26/dbhome_1/bin/oracle
```

Both nodes reported SQL*Plus 23.26.1.0.0. The observed Oracle executable was 542070280 bytes, owner `oracle`, group `asmdba`, mode `-rwsr-s--x`. Preserve installer-managed executable ownership/mode; do not generalize these observations into a blanket chmod/chown procedure. The group permits the intended ASM disk access in this role-separated lab.

**Verify** actual patch inventories before choosing the kernel/RU correction. SQL*Plus version and directory names are not complete patch inventories. Run the matching Grid and DB OPatch inventory commands as their respective software owners on each node; retain sanitized output:

```bash
"$ORACLE_HOME/OPatch/opatch" lspatches
```

---

## Phase 10: Create the 2-node RAC database with DBCA

**Database creation completed on 2026-10-19.** I reported setup complete, then supplied SQL and Clusterware output confirming RAC1 and RAC2 OPEN, RACPDB1 READ WRITE on both, and the database service ONLINE on both nodes. See the [initial health evidence](../../evidence/oracle-rac/2026-10-19-rac26-initial-cluster-and-database-health.md). A DBCA completion log, response-file review and confirmation of every planned setting have not been supplied. Successful creation does not resolve the Software paths kernel/RU compatibility gap.

The procedure below is retained for a future fresh build; do not rerun database creation against the completed RAC database. For a pre-DBCA checkpoint, stop the cluster cleanly and shut down both VMs before making backups. A VirtualBox snapshot protects only the disks it includes: [Shareable ASM disks are not snapshotted](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/storage.html). If using snapshots, also preserve consistent powered-off copies of all shared disk files and necessary VM configuration; restoring node OS snapshots alone after ASM/OCR changes can leave an inconsistent cluster. No snapshot or backup is claimed as completed here.

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

**Initial checks confirmed on 2026-10-19; acceptance testing remains in progress.** The supplied terminal output shows:

| Check | Confirmed result |
|---|---|
| Cluster services | CRS, CSS and EVM ONLINE on racnode1 and racnode2 |
| ASM and storage resources | ASM and DATA/FRA/OCR ONLINE on both nodes |
| Database instances | RAC1 on racnode1 OPEN; RAC2 on racnode2 OPEN |
| PDB | RACPDB1 READ WRITE on instances 1 and 2; PDB$SEED READ ONLY on both |
| Database service | `ora.rac.rac_racpdb1.svc` ONLINE on both nodes |
| Network resources | Both node VIPs/listeners and three SCAN VIPs/listeners ONLINE |

The [formatted evidence record](../../evidence/oracle-rac/2026-10-19-rac26-initial-cluster-and-database-health.md) is transcribed from the supplied terminal excerpt. It is not an independently collected log. These results establish an open two-node RAC database with an open PDB and online service. They do not establish client connectivity through SCAN, ARCHIVELOG mode, backup/recovery success, restart persistence, transparent session failover or certification. The checks below remain the acceptance procedure; retain actual results rather than treating expected output as evidence.

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

**Not yet run.** Diagnose first and preserve the DBCA, alert, Clusterware and ASM logs before changing state. A failed DBCA operation does not automatically require wiping files or removing cluster registration.

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
11. Turn MobaXterm multi-execution off for single-node steps (disk wiping, installers and ssh-copy-id); exclude panes logged in as another user.
12. Do not paste commands that can prompt (`su -`, `ssh-copy-id`, root's interactive `cp`, `rm -i`) as part of a block.
13. Check VBox.log for snail mode before any long step.


## References for this revision

- [26ai Grid OL9 kernel/RU requirements](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/supported-oracle-linux-9-distributions-for-x86-64.html)
- [26ai Grid operating-system checklist and virtualization reference](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/operating-system-checklist-for-oracle-grid-infrastructure-and-oracle-rac.html)
- [26ai SCAN requirements](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/about-the-scan.html)
- [26ai ASM device persistence](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/configuring-device-persistence-manually-for-oracle-asm.html)
- [26ai ASM creation and default compatibility values](https://docs.oracle.com/en/database/oracle/oracle-database/26/ostmg/create-diskgroups.html)

## Evidence kept from this build

| Phase | Evidence I report keeping |
|---|---|
| 0 | Before/after VBox.log: snail mode, then VT-x with nested paging |
| 4 | Actual ASM device permissions and identical udev rules-file checksums from both nodes |
| 6 | Eight-hostname SSH check on each node; SSH timing comparison |
| 7 | Media checksums, failed/clean pre-checks, both root-script logs including node 2's retry, installer/resource outputs and locally checked response file |
| 8 | Diskgroup compatibility, AU size and mount status on both ASM instances |
| 9 | SQL*Plus version and Oracle executable metadata from both nodes |
| 10–11 | Supplied October 19 cluster/resource status and GV$INSTANCE/GV$PDBS results; [formatted evidence record](../../evidence/oracle-rac/2026-10-19-rac26-initial-cluster-and-database-health.md) committed with this revision |

**Evidence status:** I completed the build through Phase 10 by 2026-10-19. The supplied terminal excerpt now substantiates initial Phase 11 health checks: both database instances OPEN, RACPDB1 READ WRITE on both, ASM resources and the database service ONLINE on both nodes. A formatted transcript of those results is included; installer/root-script logs, full patch inventories, screenshots and the other locally retained evidence have not been supplied or added. Installed cluster name, digital-signature execution, clock/THP state and kernel/RU compatibility remediation remain unconfirmed. SCAN client connectivity, ARCHIVELOG mode, backup/recovery and database restart/failover results remain unverified. Phase 12 cleanup is a contingency procedure, not a requirement to delete a working database or a claim that a failed DBCA path was tested. Status remains Draft pending the outstanding checks.

Before publishing evidence, redact credentials, signed download tokens, Windows username paths, machine-ids/boot IDs, MACs, VM UUIDs, disk serials and X11 cookies.
