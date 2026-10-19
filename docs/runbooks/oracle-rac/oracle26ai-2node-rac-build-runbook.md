# Oracle AI Database 26ai Two-Node RAC Build Runbook

**Last updated:** 2026-10-19

## Overview

This runbook builds a two-node Oracle AI Database 26ai RAC on Oracle Linux 9 in VirtualBox. It follows the same phases as my tested 19c runbook, updated for 26ai, with a Phase 0 added for the VirtualBox setup the 19c runbook assumed.

**Status:** Draft documentation with the two-node build and functional validation completed on 2026-10-19. Phases 0–10 are built; Phase 11 checks cover both instances/PDBs, archiving, SCAN connection distribution, new connections while RAC2 is stopped, and instance/service restoration. The SCAN availability test completion is user-confirmed; its raw connection transcript is not included in this repository. The 10:46 CDT health snapshot validates database and ASM collection with zero critical findings and four warnings. Remaining **Verify** items, HugePages configuration and the documented kernel/RU compatibility gap remain open. Phase 12 is an unexercised contingency reference.

**Baseline:** [Tested Oracle 19c two-node RAC build and troubleshooting runbook](oracle19c-2node-rac-build-and-troubleshooting.md).

**Scope:** Lab only. Firewall and SELinux shortcuts here are not for real environments. This runbook does not establish Oracle support for RAC in VirtualBox; verify the exact hardware, virtualization, OS/kernel and release-update combination against Oracle's current certification information.

**Related incident:** [Node 2 root-script VM freeze](https://github.com/omoriwor-commits/oracle-db-platform-automation/blob/docs/rac26-build-updates/Oracle-Database-Platform-Automation/incident-reports/2026-10-18-rac26-node2-root-script-vm-freeze.md). My first Grid root-script attempt on node 2 failed after a prolonged VM freeze. I subsequently confirmed VT-x with nested paging in both VM logs on October 18; raw evidence is still to be published.

### Lab layout

| Item | Node 1 | Node 2 |
| --- | --- | --- |
| VirtualBox VM name | rac26node1 | rac26node2 |
| Hostname | racnode1 | racnode2 |
| Public IP (host-only, 192.168.56.x) | 192.168.56.101 | 192.168.56.102 |
| VIP | 192.168.56.111 | 192.168.56.112 |
| Private interconnect (192.168.57.x) | 192.168.57.101 | 192.168.57.102 |
| ASM instance | +ASM1 | +ASM2 |
| DB instance | RAC1 | RAC2 |

SCAN: rac-scan on 192.168.56.120 to .122, resolved through `/etc/hosts`. Cluster name: raccluster, confirmed by the ASM client names (`RAC1:RAC:raccluster`) in `srvctl status asm -detail`. `cemutlo -n` shows it directly.

The VM name is only a VirtualBox label. Everything inside the OS, the installers and this runbook uses the hostname.

### VM sizing (as built)

| Resource | Per node | Notes |
| --- | --- | --- |
| RAM | 10 GB | Oracle minimum for Grid is 8 GB |
| vCPU | 2 | Host is a 4-core i5; two 2-vCPU VMs use every core, which is why host settings matter (Phase 0) |
| OS disk | 100 GB | One disk, LVM |

| Volume | Size | Holds |
| --- | --- | --- |
| /boot | 1 GB | Boot files. It was 72% used after updates; see Phase 1 step 10 |
| `ol-root` (/) | \~64 GB | OS and `/u01` (no separate /u01 mount) |
| `ol-home` (/home) | \~31 GB | User homes, evidence copies |
| `ol-swap` | \~4.9 GB | Swap partition |
| `/swapfile` | 5 GB | Added in Phase 1 so swap meets cluvfy's \~9.27 GB requirement for 10 GB RAM |

Memory is tight once the database is running. After DBCA each node had about 1.7 to 2.5 GB available and 1 to 2 GB of swap in use (SGA 2.8 GB, PGA 0.9 GB, plus ASM, Grid and the GNOME desktop). It works, but 12 GB per node, HugePages and booting to text mode (Phase 1 step 13) would all help.

Shared disks (VirtualBox: fixed size, type Shareable, attached to both VMs on the same SATA ports):

| SATA port | File | Size | Linux device (my build) | udev name | Disk group |
| --- | --- | --- | --- | --- | --- |
| 1 | data01.vdi | 40 GB | sdb | /dev/asm-disk2 | DATA |
| 2 | fra01.vdi | 30 GB | sdc | /dev/asm-disk3 | FRA |
| 3 | ocr01.vdi | 20 GB | sdd | /dev/asm-disk1 | OCR (OCR and voting files) |

Device letters follow the port order and can shift. Map disks by serial and size, never by sdX.

### Software paths

| Item | Path |
| --- | --- |
| Grid home | /u01/app/23.26/grid |
| Grid base | /u01/app/grid |
| DB home | /u01/app/oracle/product/23.26/dbhome_1 |
| DB base | /u01/app/oracle |
| Inventory | /u01/app/oraInventory |
| Staging | /u01/stage (grid:oinstall, 775) |

Media: `LINUX.X64_2326100_grid_home.zip` and `LINUX.X64_2326100_db_home.zip` from Oracle's 26ai Linux downloads page. File names change with the release update, so use the names you actually download.

**Outstanding kernel/RU compatibility gap:** My reported build runs Oracle Linux 9.8, UEK `6.12.0-207.111.5.4.el9uek.x86_64`, Grid 23.26.1 and SQL*Plus 23.26.1 on both nodes. The successful installation is an observed lab result, not certification. Oracle's [Grid](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/supported-oracle-linux-9-distributions-for-x86-64.html) and [Database](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/supported-oracle-linux-9-distributions-for-x86-64.html) guides document UEK8 support starting with RU 23.26.2. The database has now been created and is OPEN, but that does not close this gap. **Before further acceptance or failure testing, reconcile the running kernel and actual Grid/DB patch inventories with a documented compatible combination.** Select a documented supported kernel or plan compatible Grid and DB RUs using their patch READMEs; this runbook does not claim that either correction has been performed.

### What changed from the 19c runbook

- Phase 0 now covers VirtualBox networks, adapters, sizing, node 2 cloning, shared disks and host prerequisites.
- OS is Oracle Linux 9 (26ai Grid/RAC is certified on OL 9.2+ and OL 8.8+). No `CV_ASSUME_DISTID` workaround.
- Preinstall RPM is `oracle-ai-database-preinstall-26ai`, installed in Phase 1 before the reboot. It creates the oracle user and core groups, so Phase 2 creates only the ASM groups and the grid user.
- OSRACDBA maps to `racdba` instead of `dba`.
- Grid and DB software are unzipped on node 1 only; the installers copy them to node 2.
- GIMR is desupported in 26ai, so there is nothing to configure for it.
- ASM Filter Driver is desupported; udev rules stay the method here.
- The database must be a CDB; non-CDB is not available in 26ai.
- ASM shared disks are owned by the OSDBA for ASM group, `asmdba`, as in the 26ai guide and the 19c build.
- Cluster Time Synchronization Service (CTSS) is desupported, so chrony is the only time source.
- GUI installers run through MobaXterm X11 forwarding from a direct login as grid or oracle, instead of exporting DISPLAY to the host.
- The 26ai Grid installer has new screens: Automatic Self Correction, Failure Isolation and Management Options.

Sources: [26ai Grid hardware checklist (RAM)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/server-hardware-checklist-for-oracle-grid-infrastructure.html), [26ai Grid server configuration checklist (swap, CTSS)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/server-configuration-checklist-for-oracle-grid-infrastructure.html), [26ai device persistence for ASM (asmdba)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/configuring-device-persistence-manually-for-oracle-asm.html), [26ai OS configuration for Grid (signatures, clock source, THP)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/configuring-operating-systems-for-oracle-grid-infrastructure-on-linux.html), [Oracle 26ai Grid/RAC OS checklist](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/operating-system-checklist-for-oracle-grid-infrastructure-and-oracle-rac.html), [26ai Grid upgrade restrictions (GIMR, ASMFD)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/restrictions-for-oracle-grid-infrastructure-upgrades.html), [26ai OS configuration](https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/configuring-operating-systems-for-oracle-database-on-linux.html).

### Build sequence

Build node 1 through Phases 1, 2, 3 and 5, clone it to make node 2, attach the shared disks, then continue with Phase 4 and Phase 6 onward on both nodes. If you build node 2 from scratch instead, run every phase on both nodes in order.

### Working in MobaXterm

- Use multi-execution mode only for steps that must be identical on both nodes. Turn it off for single-node steps (disk wipe, installers, `ssh-copy-id`), and tick "Exclude" on any pane logged in as a different user.
- Don't paste commands that can prompt (`su -`, `ssh-copy-id`, root's `cp`, which is aliased to `cp -i`) as part of a larger block. A pending prompt swallows the next pasted line.

---

## Phase 0: VirtualBox setup

The 19c runbook assumed this was already done. Every later phase depends on it.

### Host prerequisites (Windows)

1. **VirtualBox must use hardware VT-x, not "snail mode".** If Windows' hypervisor is running, VirtualBox falls back to running on top of it, which is much slower. Virtual Machine Platform (used by WSL2 and Docker Desktop) is enough to start it, even with the Hyper-V role disabled. On my host this froze node 2 for about 71 minutes during the Grid root script.

   After starting a VM, check its log (PowerShell):

   ```powershell
   Select-String -Path "C:\Users\<user>\VirtualBox VMs\<vm>\Logs\VBox.log" -Pattern "Snail|VT-x is not available|HMR3Init"
   ```

   Bad: `HM: HMR3Init: Attempting fall back to NEM: VT-x is not available` and `NEM: NEMR3Init: Snail execution mode is active!` Good: `HM: HMR3Init: VT-x w/ nested paging and unrestricted guest execution hw support`

   Fix (admin PowerShell), with all VMs powered off and Docker Desktop quit:

   ```powershell
   bcdedit /set hypervisorlaunchtype off
   bcdedit /enum | findstr /i hypervisorlaunchtype      # must show Off before you reboot
   ```

   Reboot, then confirm before starting any VM:

   ```powershell
   systeminfo | Select-String "Hyper-V" -Context 0,4
   Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard | Select-Object VirtualizationBasedSecurityStatus
   ```

   `systeminfo` should list the Hyper-V requirements, including "Virtualization Enabled In Firmware: Yes", and must not say "A hypervisor has been detected". VBS status should be 0.

   Docker Desktop and WSL2 won't start while the hypervisor is off. To turn it back on: `bcdedit /set hypervisorlaunchtype auto`, then reboot.

   Resolved 2026-10-18: both VMs' logs show VT-x with nested paging.
2. Set Windows to never sleep while the lab runs. My host suspended overnight during the build, and after an idle night the ASM alert log on node 1 showed `ORA-29770: The global enqueue process LMS0 ... is hung for more than 70 seconds` (and LMON) at 03:44, before any work started. **Verify** that against the host: search the VM's `VBox.log` for `HostSuspend|HostResume|unresponsive` around that time.
3. Before restarting a VM, copy its `VBox.log` if you need it as evidence. VirtualBox renames logs at every VM start and keeps only a few.

### VM build

1. Create one host-only network in VirtualBox (File, Tools, Network Manager) with DHCP disabled:

| Network | Host address | Purpose |
| --- | --- | --- |
| VirtualBox Host-Only Ethernet Adapter | 192.168.56.1 | Public, VIP and SCAN |

2. Create the node 1 VM (`rac26node1`) with the sizes above and three network adapters:

| Adapter | Attached to | Purpose |
| --- | --- | --- |
| 1 | Host-only adapter | Public (192.168.56.0/24) |
| 2 | Internal Network `rac26priv` | Private interconnect (192.168.57.0/24). VM-to-VM only; the host can't reach it |
| 3 | NAT | Internet access for dnf and downloads only |

Do not use a bridged Wi-Fi adapter for either cluster network.

3. Install Oracle Linux 9 on node 1 with the layout above.
4. After node 1 completes Phases 1, 2, 3 and 5, shut it down fully (not saved or paused) and clone it to `rac26node2`:

| Clone setting | Value |
| --- | --- |
| Clone type | Full Clone (a linked clone would make node 2's disk depend on node 1's) |
| MAC Address Policy | Generate new MAC addresses for all network adapters |
| Keep Disk Names / Keep Hardware UUIDs | Both unticked |
| Shared disks | Not attached yet |

Start node 2 with node 1 still off, and before anything else:

```bash
rm -f /etc/machine-id && systemd-machine-id-setup
rm -f /etc/ssh/ssh_host_* && ssh-keygen -A && systemctl restart sshd
hostnamectl set-hostname racnode2
```

A full clone copies node 1's machine-id (it confuses DHCP, logging and management tools; Clusterware doesn't use it) and its SSH host keys (both nodes would present the same identity). I missed the host keys at first and only caught them when both nodes showed the same ED25519 fingerprint in Phase 6.

Then set node 2's static IPs (.102, Phase 1) and profile values (+ASM2, RAC2, Phase 5). Keep node 1 off until node 2's IPs are changed.

Verify on both nodes; the values must differ:

```bash
cat /etc/machine-id
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

5. With both VMs powered off, create the three shared disks as fixed size, set each to type Shareable, and attach all three to both VMs on the same ports.

```powershell
VBoxManage createmedium disk --filename <path>\ocr01.vdi  --size 20480 --variant Fixed
VBoxManage createmedium disk --filename <path>\data01.vdi --size 40960 --variant Fixed
VBoxManage createmedium disk --filename <path>\fra01.vdi  --size 30720 --variant Fixed
VBoxManage modifymedium disk <path>\ocr01.vdi  --type shareable
VBoxManage modifymedium disk <path>\data01.vdi --type shareable
VBoxManage modifymedium disk <path>\fra01.vdi  --type shareable
```

Reusing disks: my build reused the shared disks from my deleted 19c cluster. Reused disks keep their serials and their old ASM headers, so the Phase 4 wipe is mandatory. Before wiping, open File, Tools, Media and confirm each disk is attached only to rac26node1 and rac26node2.

---

## Phase 1: OS prep on both nodes

Both nodes need Oracle Linux 9, static IPs on the public and private NICs, matching time, and name resolution for every RAC address before any Oracle software goes on.

0. Lab only: allow root SSH with a password. Oracle Linux 9 blocks it by default. Run from the VirtualBox console.

```bash
echo "PermitRootLogin yes" > /etc/ssh/sshd_config.d/01-permitrootlogin.conf
systemctl restart sshd
```

Add "disable root password SSH" to the hardening list for later.

1. Confirm the OS release and kernel.

```bash
cat /etc/oracle-release
uname -r
```

My build: Oracle Linux Server 9.8, UEK 6.12.0-207.111.5.4.el9uek.x86_64 on both nodes.

2. Set the hostname.

```bash
# node1
hostnamectl set-hostname racnode1
# node2
hostnamectl set-hostname racnode2
```

3. Set static IPs on the public and private NICs. Get the connection names first, then use the node 2 addresses (.102) on node 2. Leave the NAT adapter on DHCP.

```bash
nmcli con show
nmcli con mod "<public-con>"  ipv4.method manual ipv4.addresses 192.168.56.101/24 connection.autoconnect yes
nmcli con mod "<private-con>" ipv4.method manual ipv4.addresses 192.168.57.101/24 connection.autoconnect yes
nmcli con up "<public-con>"
nmcli con up "<private-con>"
ip -br addr
```

Expected: enp0s3 on 192.168.56.x, enp0s8 on 192.168.57.x, enp0s9 (NAT) on 10.0.4.15 on both nodes. The duplicate NAT address is normal, because each VM gets its own isolated NAT.

4. Add these entries to `/etc/hosts` on both nodes.

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

5. Test name resolution and reachability. VIPs and SCAN will not answer ping until Grid is running; that is expected.

```bash
for h in racnode1 racnode2 racnode1-vip racnode2-vip rac-scan racnode1-priv racnode2-priv; do getent hosts $h; done
ping -c 2 racnode1-priv; ping -c 2 racnode2-priv
```

6. Enable time sync and check it.

```bash
systemctl enable --now chronyd
chronyc tracking
chronyc sources -v
```

Do not continue until both nodes show a synced source. CTSS is desupported in 26ai, so chrony is the cluster's only time synchronization.

7. Lab only: stop the firewall and set SELinux to permissive.

```bash
systemctl disable --now firewalld
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config
getenforce
```

Record the SELinux mode you end up using.

8. Install the 26ai preinstall RPM, update packages, then reboot.

```bash
dnf install -y oracle-ai-database-preinstall-26ai
dnf -y update
reboot
```

9. Check the clock source and Transparent HugePages. Oracle recommends the `tsc` clock source in virtual machines and Transparent HugePages set to `madvise`. THP showed `always [madvise] never` on both nodes in my build (OL9 default). **Verify** the clock source.

```bash
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
cat /sys/kernel/mm/transparent_hugepage/enabled
```

If THP shows `[always]`, set it to madvise:

```bash
grubby --update-kernel=ALL --args="transparent_hugepage=madvise"
reboot
```

10. Keep `/boot` from filling up. It is only 1 GB, and every UEK update adds a kernel.

```bash
df -h /boot
rpm -q kernel-uek
grep installonly_limit /etc/dnf/dnf.conf
```

Set `installonly_limit=2` in `/etc/dnf/dnf.conf`, then remove old kernels with `dnf remove --oldinstallonly --setopt installonly_limit=2 kernel-uek`.

11. Disable avahi on both nodes. cluvfy fails it otherwise (PRVG-1359, PRVG-1360).

```bash
systemctl disable --now avahi-daemon.socket avahi-daemon.service
systemctl is-active avahi-daemon     # inactive
```

12. Add swap if it is below what cluvfy requires. With 10 GB RAM, cluvfy wanted about 9.27 GB and my swap partition was 4.9 GB (PRVF-7573). On both nodes, paste once only:

```bash
dd if=/dev/zero of=/swapfile bs=1M count=5120 status=progress
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap defaults 0 0' >> /etc/fstab
swapon --show
free -g
grep -c swapfile /etc/fstab      # must print 1
```

13. Optional (recommended on 10 GB VMs): boot to text mode. The GNOME desktop uses memory the database needs, and MobaXterm's X11 forwarding works without it. Not yet done in my build.

```bash
systemctl get-default                       # graphical.target
systemctl set-default multi-user.target     # takes effect at the next reboot
```

---

## Phase 2: Users, groups, limits

The preinstall RPM from Phase 1 does most of the work the 19c runbook did by hand. This phase checks what it created and adds only what it does not. UIDs and GIDs must match on both nodes.

1. Confirm the preinstall RPM is installed.

```bash
rpm -q oracle-ai-database-preinstall-26ai
```

2. Check what it created. **Verify** the exact GIDs; they must be identical on both nodes.

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

6. Verify kernel parameters set by the RPM.

```bash
sysctl fs.aio-max-nr fs.file-max kernel.shmmax kernel.shmall kernel.shmmni kernel.sem net.ipv4.ip_local_port_range
```

7. Create the grid limits file. The RPM sets limits for oracle only. I skipped this on my first pass, and cluvfy failed the soft stack limit (PRVG-0449) and maximum locked memory (PRVE-0059).

```bash
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

8. Confirm limits as each user, from a root shell (root's `su -` should not ask for a password).

```bash
su - grid -c 'ulimit -s; ulimit -l; ulimit -n; ulimit -u'      # 10240 / unlimited / 1024 / 16384
su - oracle -c 'ulimit -s; ulimit -l'                          # 10240 / RPM value
```

Limits apply to new logins only, so exit and reopen any existing grid shell.

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

ASM needs the same three disks, with the same stable names and grid ownership, on both nodes. udev rules do this; ASM Filter Driver is desupported in 26ai, so do not use it.

1. Confirm both nodes see the same disks with the same serials.

```bash
lsblk -o NAME,SIZE,SERIAL
```

Match disks by serial and size (20G OCR, 40G DATA, 30G FRA), not by letter.

2. Wipe headers once, from node 1 only. Turn MobaXterm multi-execution mode **off** first. Use the by-id paths so a shifted device letter can't send `dd` to the wrong disk.

```bash
ls -l /dev/disk/by-id/ | grep VBOX
dd if=/dev/zero of=/dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_ocr_disk>  bs=1M count=100
dd if=/dev/zero of=/dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_data_disk> bs=1M count=100
dd if=/dev/zero of=/dev/disk/by-id/ata-VBOX_HARDDISK_<serial_of_fra_disk>  bs=1M count=100
```

Never run this after OCR and voting files are on the disks unless you are rebuilding everything. On reused 19c disks, skipping the wipe leaves them showing as MEMBER instead of CANDIDATE.

3. Check the ID_SERIAL format udev uses:

```bash
udevadm info --query=property --name=/dev/sdd | grep ID_SERIAL=
```

It returns `VBOX_HARDDISK_<serial>`. If you reuse disks from an earlier build, the serials match the old ones; new disks get new serials.

4. Create one rules file, `/etc/udev/rules.d/99-oracle-asm.rules`, on both nodes (multi-exec is fine here).

```text
ENV{ID_SERIAL}=="VBOX_HARDDISK_<serial_of_ocr_disk>",  OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk1"
ENV{ID_SERIAL}=="VBOX_HARDDISK_<serial_of_data_disk>", OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk2"
ENV{ID_SERIAL}=="VBOX_HARDDISK_<serial_of_fra_disk>",  OWNER="grid", GROUP="asmdba", MODE="0660", SYMLINK+="asm-disk3"
```

The 26ai Grid Infrastructure Installation Guide sets ASM devices to the installation owner and the OSDBA for Oracle ASM group (`asmdba`), mode 0660. My 19c build used the same group. Older guides (12.2) used the OSASM group, `asmadmin`, which is where many community guides get it from.

5. Reload, wait for udev to finish, then check on both nodes.

```bash
udevadm control --reload-rules && udevadm trigger && udevadm settle
ls -lL /dev/asm-disk*
md5sum /etc/udev/rules.d/99-oracle-asm.rules
```

Without `udevadm settle`, my first `ls` ran before udev finished and found nothing.

Expected on both nodes, with my port order:

```text
brw-rw---- grid asmdba 8, 48  /dev/asm-disk1   (sdd, 20G OCR)
brw-rw---- grid asmdba 8, 16  /dev/asm-disk2   (sdb, 40G DATA)
brw-rw---- grid asmdba 8, 32  /dev/asm-disk3   (sdc, 30G FRA)
```

The `md5sum` must match on both nodes. That proves final rule 2 (one identical rules file).

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

Check from root on each node (node 2 is a clone, so confirm its values changed):

```bash
su - grid -c 'echo $ORACLE_HOSTNAME $ORACLE_SID $ORACLE_HOME'
su - oracle -c 'echo $ORACLE_HOSTNAME $ORACLE_SID $ORACLE_HOME'
```

---

## Phase 6: Passwordless SSH

Both grid and oracle need SSH without a password from every node to every node, including itself, on both public and private names. Do this before Phase 7, because `runcluvfy.sh` needs it already working.

Run four passes, one user and one node at a time: grid on racnode1, grid on racnode2, oracle on racnode1, oracle on racnode2. Multi-exec off.

1. As root, type `su - grid` (or `su - oracle`) on its own line and wait for the prompt. When I pasted a block starting with `su -`, the rest of the block ran as root.
2. Paste only lines that can't prompt:

```bash
ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa
ssh-keyscan -t ed25519 racnode1 racnode2 racnode1-priv racnode2-priv 2>/dev/null >> ~/.ssh/known_hosts
ssh-keygen -lf ~/.ssh/known_hosts
```

Check the fingerprints: racnode1 and racnode1-priv match each other, racnode2 and racnode2-priv match each other, and node 1 differs from node 2. If both nodes show the same fingerprint, node 2 still has node 1's host keys (Phase 0 step 4).

3. Run these one at a time, entering that user's password:

```bash
ssh-copy-id racnode1
```

```bash
ssh-copy-id racnode2
```

4. Turn off GSSAPI for the RAC hostnames. On OL9 the SSH client tries Kerberos first, which added about 1.3 seconds to every login (1.96 s against 0.67 s) and made the database installer show `INS-06009` (slow SSH).

```bash
cat >> ~/.ssh/config <<'EOF'
Host racnode1 racnode2 racnode1-priv racnode2-priv
    GSSAPIAuthentication no
EOF
chmod 600 ~/.ssh/config
```

Do this in each of the four passes. Copying the file with `scp` from the node you're on only covers the other node.

5. Check, then `exit`:

```bash
for h in racnode1 racnode2 racnode1-priv racnode2-priv; do ssh -o BatchMode=yes $h hostname; done
time ssh racnode2 date      # well under 1 second
```

Final check as root on both nodes (multi-exec is fine). Each node must print eight hostnames with no prompts:

```bash
for u in grid oracle; do
  echo "== $u =="
  su - $u -c 'for h in racnode1 racnode2 racnode1-priv racnode2-priv; do ssh -o BatchMode=yes $h hostname; done'
done
```

Root does not need SSH equivalence. The installers run root scripts with the root password.

Stay on OL9 for this build. Oracle-Base hit a passwordless SSH failure building 26ai RAC on OL10, traced in comments to OpenSSH 10.x.

---

## Phase 7: Grid Infrastructure install

Grid goes in from node 1 and is copied to node 2 by the installer. Do not continue to ASM or the database until `crsctl` shows both nodes healthy.

1. Download the media to node 1. Either use a browser and upload to `/u01/stage`, or download directly on the node with the signed link from Oracle's page:

```bash
cd /u01/stage
wget -c -O LINUX.X64_2326100_grid_home.zip "<signed download link>"
```

Use capital `-O`. Lowercase `-o` writes wget's log to that name and saves the zip under the URL's name instead. Never publish the link's `AuthParam` token.

Check sizes and checksums against Oracle's 26ai Linux download page. Both matched in my build:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| LINUX.X64_2326100_grid_home.zip | 1,089,544,451 | `2deb199610357780ebb4d1213d6aa52df1694c7b12bd21f9e02dc3f9c992cd61` |
| LINUX.X64_2326100_db_home.zip | 2,406,058,543 | `2a5d2583df076209e624dff750829f9a562473c27c8f926d546cf9ad2a1a2efd` |

```bash
sha256sum /u01/stage/LINUX.X64_2326100_*.zip
```

**Verify** (optional) The archives are also signed; `jarsigner -verify <zip>` should report `jar verified.` if a JDK is available.

2. As grid, unzip into the empty Grid home on node 1 only.

```bash
ls -A /u01/app/23.26/grid        # must be empty
cd /u01/app/23.26/grid
unzip -q /u01/stage/LINUX.X64_2326100_grid_home.zip
ls -l gridSetup.sh runcluvfy.sh
```

3. Install cvuqdisk on both nodes as root (use `su -`, not `su`). Copy the RPM to node 2 as grid, which already has passwordless SSH.

```bash
# racnode1, root
CVUQDISK_GRP=oinstall rpm -ivh /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm
# racnode1, grid
scp /u01/app/23.26/grid/cv/rpm/cvuqdisk-*.rpm racnode2:/tmp/
# racnode2, root
CVUQDISK_GRP=oinstall rpm -ivh /tmp/cvuqdisk-*.rpm
# both nodes
ls -l /usr/sbin/cvuqdisk          # -rwsr-xr-x root oinstall
```

The `NOKEY` signature warning from `rpm` is expected. My build installed cvuqdisk-1.0.10-1.

4. As grid, run the cluster pre-check on the two cluster networks only, so it skips the NAT adapter, and fix every failure before installing.

```bash
cd /u01/app/23.26/grid
./runcluvfy.sh stage -pre crsinst -n racnode1,racnode2 \
  -networks enp0s3:192.168.56.0:PUBLIC/enp0s8:192.168.57.0:cluster_interconnect \
  -verbose 2>&1 | tee /tmp/cluvfy_pre_crsinst.log
grep -iE "FAILED|WARNING" /tmp/cluvfy_pre_crsinst.log
```

What my first run failed, and the fix:

| Failure | Fix |
| --- | --- |
| Swap size (PRVF-7573) | Phase 1 step 12 |
| Soft stack limit (PRVG-0449), max locked memory (PRVE-0059) | Phase 2 step 7 |
| avahi-daemon running (PRVG-1359/1360) | Phase 1 step 11 |
| Node connectivity on enp0s9 (NAT) | Use `-networks` as above |

The clean run reports "Pre-check for cluster services setup was successful." INFORMATION items (RPM database and cgroup checks need root; ORAchk skipped) are fine.

5. Log in to node 1 as grid directly through MobaXterm (a new SSH session with username grid and X11 forwarding ticked). Do not use `su - grid` from a root session; X11 forwarding doesn't carry over. Confirm, then launch the installer.

```bash
whoami; hostname; echo $DISPLAY     # grid, racnode1, localhost:10.0
cd /u01/app/23.26/grid
./gridSetup.sh
```

The `xauth: file /home/grid/.Xauthority does not exist` message on the first X11 login is normal.

6. Installer screens as they appeared in 26ai:

| Screen | Value |
| --- | --- |
| Configuration Option | Configure Oracle Grid Infrastructure for a New Cluster |
| Cluster Configuration | Configure cluster to manage Oracle RAC databases. Not Extended. |
| Grid Plug and Play | Create Local SCAN. Cluster name `raccluster` (the installer's default was `racnode-cluster`). SCAN `rac-scan`, port 1521. No GNS. |
| Cluster Node Information | racnode1 / racnode1-vip, racnode2 / racnode2-vip. SSH connectivity: Test, not Setup. |
| Network Interface Usage | enp0s3 192.168.56.0 Public; enp0s8 192.168.57.0 ASM & Private; enp0s9 10.0.4.0 and its IPv6 subnet Do Not Use |
| Storage Option | Use Oracle Flex ASM for storage. Don't tick the separate OCR backup disk group. |
| Create ASM Disk Group | OCR, External, AU 4 MB, discovery path `/dev/asm-disk*`, select `/dev/asm-disk1` only. All three disks showed Candidate. |
| ASM Password | Same password for SYS and ASMSNMP. Never in GitHub. |
| Automatic Self Correction | Off. New in 26ai; I want changes to be deliberate and documented. |
| Failure Isolation | Do not use IPMI (VirtualBox has none) |
| Management Options | No Enterprise Manager registration |
| Operating System Groups | OSASM `asmadmin`, OSDBA for ASM `asmdba`, OSOPER for ASM `asmoper` |
| Installation Location | Oracle base `/u01/app/grid` |
| Root script execution | Automatic with root credentials (what I used), or manual |
| Prerequisite Checks | Only DNS/NIS name service fails (SCAN in /etc/hosts). Ignore All. |

There is no GIMR option; GIMR is desupported in 26ai.

My earlier builds used `oinstall` for every OS group. This build uses role-separated ASM groups as in the installation guide.

Notes from my build:

- ASM password: I used a simple lab password and accepted `INS-30011`. Don't reuse it anywhere real, and change it before this lab connects to anything outside my PC.
- `INS-40109` (Oracle base not empty) appeared because cluvfy had written `/u01/app/grid/diag`. Check `ls -la /u01/app/grid` on both nodes; if it only holds today's `diag`, answer Yes.

7. If you run the root scripts manually, use a fresh `su -` root login. Node 1 must finish completely before node 2 starts; never run them in parallel.

```bash
/u01/app/oraInventory/orainstRoot.sh     # node 1, then node 2
/u01/app/23.26/grid/root.sh              # node 1 to completion, then node 2
```

Root script logs: `/u01/app/grid/crsdata/<node>/crsconfig/rootcrs_<node>_*.log`. Use `tail -n 15`, not `tail -15`, when a wildcard can match more than one file. A successful run ends with `CLSRSC-325: Configure Oracle Grid Infrastructure for a Cluster ... succeeded`.

```bash
F=/u01/app/grid/crsdata/racnode2/crsconfig/rootcrs_racnode2_<timestamp>.log
grep -E 'CLSRSC-325|Executed stage' $F
grep -iE 'CLSRSC-[0-9]+:.*(fail|error)' $F      # should print nothing
```

In my build, node 1's root script succeeded at 09:39. Node 2's first run failed at `StartCluster` with `CLSRSC-117` because its VM was frozen (Phase 0 host prerequisites); a rerun at 10:57 completed all stages, with `StartCluster` in 42 seconds.

8. Expected end of install: `INS-43080` ("Some of the configuration assistants failed") with exit status -1. The post-install CVU fails only `PRVH-1558` and `PRVG-1101`, because SCAN is not in DNS. Everything else passes (CRS, OCR and ASM integrity, voting disk, clock synchronization, VIP subnet).

Check how the session ended:

```bash
LOG=$(ls -t /tmp/GridSetupActions*/gridSetupActions*.log | head -1)
grep -iE 'SEVERE|INS-[0-9]+|failed' $LOG | tail -n 25
```

9. Response file: `/u01/app/23.26/grid/install/response/grid_<timestamp>.rsp`. 26ai leaves the password keys empty (`sysasmPassword=`, `asmsnmpPassword=`), but check before keeping it, and restrict it:

```bash
grep -iE 'password' /u01/app/23.26/grid/install/response/grid_*.rsp
chmod 600 /u01/app/23.26/grid/install/response/grid_*.rsp
```

It records every GUI choice, so it's the starting point for a silent install (`gridSetup.sh -silent -responseFile ...`) in the automation project.

10. Copy evidence out of `/tmp` before any reboot:

```bash
mkdir -p /home/grid/evidence/phase07
cp -r /tmp/GridSetupActions* /tmp/cluvfy_pre_crsinst*.log /home/grid/evidence/phase07/
chown -R grid:oinstall /home/grid/evidence
```

11. As grid, verify the cluster.

```bash
crsctl check cluster -all
crsctl stat res -t
crsctl query crs activeversion
olsnodes -n -s
ocrcheck
srvctl status scan_listener
cemutlo -n
```

Expected: `crsctl check cluster -all` lists **both** nodes with CRS, CSS and EVM online; both nodes Active; ASM, OCR disk group, node listeners, node VIPs, three SCAN VIPs and listeners, ASM network, ONS and CVU ONLINE. `ora.helper`, `ora.cdp1` to `ora.cdp3`, `ora.cvuhelper` and `ora.rhpserver` OFFLINE is normal.

I observed three SCAN VIPs/listeners with this hosts-file configuration. That observation does not establish reliable three-address resolution for every server or client. Oracle recommends DNS/GNS for SCAN; the hosts-file exception affects server validation as well as clients. Confirm resolution and actual service routing in each environment.

After my node 2 freeze, `crsctl check cluster -all` showed only the local node and cluster-wide commands failed with `CRS-4405`. A clean stop of both nodes (Appendix A) and a fresh start cleared it.

Sources: [26ai Grid CLI install](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/installing-grid-using-command-line-interface.html), [26ai Grid upgrade with setup wizard (root script automation)](https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/running-oui-to-upgrade-grid-infrastructure-from-an-earlier-release.html).

---

## Phase 8: ASM disk groups

Create DATA and FRA from node 1 as grid. I used the `asmca` GUI from the X11-forwarded grid session; the SQL below does the same.

1. Check disk visibility.

```bash
sqlplus / as sysasm
```

```sql
SET LINESIZE 150
COLUMN path FORMAT a20
SELECT path, header_status, mount_status, ROUND(total_mb/1024) gb FROM v$asm_disk ORDER BY path;
```

Expected: asm-disk1 MEMBER (OCR); asm-disk2 and asm-disk3 CANDIDATE, CLOSED.

2. Create the disk groups, either in `asmca` (Disk Groups, Create; External; AU 4 MB; one disk each) or in SQL:

```sql
CREATE DISKGROUP DATA EXTERNAL REDUNDANCY DISK '/dev/asm-disk2';
CREATE DISKGROUP FRA  EXTERNAL REDUNDANCY DISK '/dev/asm-disk3';
```

`asmca` mounts them on both nodes. If you use SQL, mount them on node 2:

```bash
srvctl start diskgroup -diskgroup DATA -node racnode2
srvctl start diskgroup -diskgroup FRA -node racnode2
```

3. Verify.

```sql
COLUMN name FORMAT a8
SELECT name, compatibility, database_compatibility, allocation_unit_size/1048576 au_mb FROM v$asm_diskgroup ORDER BY name;
SELECT inst_id, name, state FROM gv$asm_diskgroup ORDER BY name, inst_id;
```

My build:

| Disk group | Size | compatible.asm | compatible.rdbms | AU | State |
| --- | --- | --- | --- | --- | --- |
| DATA | 40 GB | 23.0.0.0.0 | 19.0.0.0.0 | 4 MB | Mounted on instances 1 and 2 |
| FRA | 30 GB | 23.0.0.0.0 | 19.0.0.0.0 | 4 MB | Mounted on instances 1 and 2 |
| OCR | 20 GB | 23.0.0.0.0 | 19.0.0.0.0 | 4 MB | Mounted on instances 1 and 2 |

After creation, all three disks show MEMBER, CACHED.

`compatible.rdbms` 19.0 lets databases from 19c onwards use these disk groups, so the 26ai database works as is. `compatible.asm` must be at least `compatible.rdbms`. Both can be raised later with `ALTER DISKGROUP ... SET ATTRIBUTE` if a feature needs it, but never lowered.

---

## Phase 9: Database software install

Install software only, as a RAC home, from node 1. The installer copies it to node 2.

1. Log in to node 1 as oracle directly through MobaXterm with X11 forwarding (not `su - oracle`).

```bash
whoami; hostname; echo $DISPLAY; echo $ORACLE_HOME
```

`DISPLAY` was `localhost:11.0` for me, because the grid session already used `:10`.

2. Check the DB home is empty, then unzip on node 1 only.

```bash
ls -ld $ORACLE_HOME          # oracle oinstall
ls -A $ORACLE_HOME | head    # must print nothing
cd $ORACLE_HOME
unzip -q /u01/stage/LINUX.X64_2326100_db_home.zip
ls -l runInstaller
```

3. Launch the installer.

```bash
./runInstaller
```

| Screen | Value |
| --- | --- |
| Configuration Option | Set Up Software Only |
| Database Installation Options | Oracle Real Application Clusters database installation |
| Nodes Selection | racnode1 and racnode2 both listed and ticked. SSH connectivity: Test, not Setup. |
| Installation Location | Oracle base `/u01/app/oracle`, software location `/u01/app/oracle/product/23.26/dbhome_1` |
| Operating System Groups | OSDBA `dba`, OSOPER `oper` (the screen left it blank), OSBACKUPDBA `backupdba`, OSDGDBA `dgdba`, OSKMDBA `kmdba`, OSRACDBA `racdba` |
| Root script process | Automatic with root credentials (what I used) |
| Prerequisite Checks | HugePages Existence (warning) and SCAN DNS/NIS (failed) only. Ignore All. |
| Summary | Enterprise Edition (Set Up Software Only), both nodes listed |

There was no separate edition screen; check the edition on the Summary. Do not choose single-instance installation. A RAC database cannot be created from a single-instance home.

Notes from my build:

- racnode2 appearing in the node list confirmed the Grid inventory registration from Phase 7.
- `INS-06009` (SSH performance slow) appeared at Nodes Selection, even though the SSH test passed. The cause was GSSAPI; Phase 6 step 4 fixes it.
- HugePages: deferred until after DBCA, so they can be sized to the real SGA.

4. The install took about 12 minutes once the host ran VT-x. Root scripts ran on racnode1 first, then racnode2, with no errors. The finish screen reports "The registration of Oracle AI Database was successful."
5. Verify on both nodes as oracle. A non-login `ssh` command doesn't load `.bash_profile`, so set `ORACLE_HOME` for the remote check:

```bash
$ORACLE_HOME/bin/sqlplus -v
ls -l $ORACLE_HOME/bin/oracle
ssh racnode2 'ORACLE_HOME=/u01/app/oracle/product/23.26/dbhome_1 /u01/app/oracle/product/23.26/dbhome_1/bin/sqlplus -v'
ssh racnode2 ls -l /u01/app/oracle/product/23.26/dbhome_1/bin/oracle
```

My build, on both nodes: SQL\*Plus Release 23.26.1.0.0, and `-rwsr-s--x oracle asmdba 542070280 .../bin/oracle`. The `asmdba` group and the setuid and setgid bits let database processes open the ASM disks, which udev gives to `grid:asmdba` 0660.

---

## Phase 10: Create the 2-node RAC database with DBCA

Before starting, stop the cluster cleanly (Appendix A), shut down both VMs and take a VirtualBox snapshot of each (for example `phase9-db-software-installed`). Shareable disks are left out of snapshots, so a snapshot protects each node's OS and Oracle homes but not the ASM contents. Preserve consistent powered-off copies of the shared disks and necessary VM configuration for a complete rollback; restoring OS snapshots alone after ASM/OCR changes can leave inconsistent state. Backup completion is not claimed here.

Run DBCA as oracle on node 1 from the same X11-forwarded session as Phase 9.

```bash
echo $DISPLAY
dbca
```

DBCA screens as they appeared in 26ai:

| Screen | Value |
| --- | --- |
| Database Operation | Create a database |
| Creation Mode | Advanced configuration. The greyed-out Typical settings showed the FRA defaulting to `+OCR`. |
| Deployment Type | Database type: Oracle Real Application Cluster (RAC) database. Database Management Policy: Automatic. Template: General Purpose or Transaction Processing. |
| Nodes Selection | racnode1, racnode2 |
| Database Identification | Global database name RAC, SID prefix RAC (instances RAC1, RAC2). Container database with one PDB, RACPDB1. |
| Storage Option | ASM, datafiles in `+DATA/{DB_UNIQUE_NAME}/` |
| Fast Recovery Option | `+FRA` (change it if it shows `+OCR`), size 25600 MB, Enable archiving ticked |
| Data Vault Option | Database Vault and Label Security off |
| Configuration Options | Automatic Shared Memory Management, SGA 2844 MB, PGA 949 MB (the DBCA default for 10 GB VMs). Character sets AL32UTF8 / AL16UTF16. Sizing and connection mode left at defaults. |
| Management Options | Defaults; no Enterprise Manager Cloud Control registration |
| User Credentials | Same administrative password for all accounts. Never in GitHub. |
| Creation Option | Create database. Generate database creation scripts ticked (`{ORACLE_BASE}/admin/{DB_UNIQUE_NAME}/scripts`). **Post DB creation scripts left empty.** |
| Prerequisite Checks | HugePages Existence and SCAN DNS/NIS only. Ignore All. |
| Summary | Check, save the response file, then Finish |

Notes from my build:

- 26ai has no "Admin Managed / Policy Managed" choice; policy-managed databases are gone, and srvctl reports "Database is administrator managed". Database Management Policy is a different setting: Automatic means Clusterware starts the database with the cluster and restarts it on failure. Rank only matters with several databases competing for resources.
- The FRA size defaulted to about 15 GB. 25600 MB uses most of the 30 GB FRA disk group but stays below its real size.
- ASMM rather than Automatic Memory Management, because AMM doesn't work with HugePages.
- I typed the scripts folder into "Post DB creation scripts" by mistake and got `DBT-13002: The specified custom script (/u01/app/oracle/admin/RAC/scripts) does not exist`. That field is for SQL scripts to run after creation; leave it empty.
- The Summary listed `cluster_database: true`, `compatible: 23.6.0` (above the disk groups' compatible.rdbms 19.0), separate threads and undo tablespaces per instance, and four 200 MB redo log groups (two per thread). It didn't state the archive mode directly; Phase 11 confirms it.

Progress and logs:

- DBCA restores the template's datafiles into `+DATA` with RMAN, then creates the PDB, then the second instance. Logs are in `/u01/app/oracle/cfgtoollogs/dbca/RAC/`: `trace.log_<timestamp>` from the start, `CloneRmanRestore1R.log` during the restore. `RAC.log` only appears later.
- My run took about 25 minutes (04:59 to 05:23) and ended with "Database creation complete". Memory on node 1 rose to about 7.4 of 9.3 GB in use during the build.
- The finish screen notes that all accounts except SYS, SYSTEM and DBSNMP are locked. Leave them locked and unlock only what you need.

Results:

- Spfile and password file in `+DATA` (`+DATA/RAC/PARAMETERFILE/spfile...`, `+DATA/RAC/PASSWORD/pwdrac...`), shared by both instances.
- Database resource `ora.rac.db` with management policy AUTOMATIC, PDB resource `ora.rac.racpdb1.pdb`, and a service `RAC_RACPDB1` created by DBCA, running on both instances.

After DBCA:

1. Restrict the response files: `chmod 600 /home/oracle/*.rsp`.
2. **Verify** Configure HugePages sized to the SGA (2844 MB SGA in 2 MB pages is about 1,422 pages; Oracle's script in MOS note 401749.1 gives the exact figure with the instances running), set `vm.nr_hugepages` in `/etc/sysctl.d/`, restart the instances, and confirm with `grep Huge /proc/meminfo` and the instance alert log. Not yet done in my build.

---

## Phase 11: Post-build validation

The build is done when both instances are open, the PDB is open on both, archiving works, clients connect through SCAN, and the database survives losing an instance. Save the output of each check as evidence, with passwords and serials removed.

Run database tools as oracle and ASM and Clusterware tools as grid (Appendix A). As oracle, `asmcmd` fails with `ASMCMD-8102` and `crsctl` isn't on the PATH.

1. Cluster view of the database (as oracle):

```bash
srvctl config database -db RAC
srvctl status database -db RAC
srvctl status scan_listener
```

My build: instances RAC1 on racnode1 and RAC2 on racnode2, both running the `RAC_RACPDB1` service; management policy AUTOMATIC; disk groups FRA and DATA; three SCAN listeners up.

2. Instances, PDB and archiving (as oracle, `sqlplus / as sysdba`):

```sql
SET LINESIZE 150 PAGESIZE 50
COLUMN name FORMAT a12
COLUMN instance_name FORMAT a10
SELECT banner_full FROM v$version;
SELECT inst_id, instance_name, host_name, status FROM gv$instance ORDER BY inst_id;
SELECT inst_id, name, open_mode FROM gv$pdbs ORDER BY name, inst_id;
ARCHIVE LOG LIST
```

My build: RAC1 and RAC2 OPEN; PDB$SEED READ ONLY and RACPDB1 READ WRITE on both instances; ARCHIVELOG with automatic archival to `USE_DB_RECOVERY_FILE_DEST`.

3. Prove archiving writes into the FRA from both threads:

```sql
ALTER SYSTEM ARCHIVE LOG CURRENT;
COLUMN name FORMAT a70
SELECT thread#, sequence#, name FROM v$archived_log ORDER BY first_time DESC FETCH FIRST 4 ROWS ONLY;
```

My build: archive logs for thread 1 and thread 2 under `+FRA/RAC/ARCHIVELOG/<date>/`.

4. Cluster resources and ASM (as grid):

```bash
crsctl stat res -t
asmcmd lsdg
```

Expected: `ora.rac.db` Open on both nodes, `ora.rac.racpdb1.pdb` READ WRITE on both, `ora.rac.rac_racpdb1.svc` ONLINE on both, DATA, FRA and OCR disk groups ONLINE on both. After DBCA in my build: DATA 35,920 of 40,960 MB free, FRA 29,428 of 30,720 MB, and OCR 20,116 of 20,480 MB in the 10:46 CDT snapshot.

5. Run the RAC health check script as grid (`scripts/oracle-rac/rac_health_check.py`). It discovers the Grid and database homes and bases itself, so no overrides are needed on 26ai.

```bash
./rac_health_check.py --db RAC --pdb RACPDB1 --dbca-node racnode1 2>&1 | tee ~/rac_health_$(date +%Y%m%d_%H%M).log
printf 'script_exit=%s\n' "${PIPESTATUS[0]}"
```

Use `${PIPESTATUS[0]}`; plain `$?` after a pipe is the exit code of `tee`. Revision `2026-10-19.3` was run as grid on racnode1 at 10:46 CDT on October 19. OS, Clusterware, database and ASM coverage were collected; local alerts were sampled on node 1 only. Both database instances were OPEN/ACTIVE, RACPDB1 was READ WRITE on both, all three disk groups were mounted on both ASM instances, and all six disk observations were MEMBER/CACHED/ONLINE/NORMAL. Result: REVIEW REQUIRED, zero critical findings, four warnings, exit 1. Warnings cover database/ASM alert history and the UEK8/23.26.1 compatibility flag on each node. Earlier DBCA-time errors are retained for correlation; their initiating causes are not established by this snapshot. See the [latest health evidence](../../evidence/oracle-rac/2026-10-19-rac26-health-check-v3.md).

To date an alert-log entry, print the timestamp line that precedes it:

```bash
awk '/^20[0-9][0-9]-/{ts=$0} /ORA-29770/{print ts"  "$0}' /u01/app/grid/diag/asm/+asm/+ASM1/trace/alert_+ASM1.log
```

6. Connect through SCAN to the PDB service several times; connections should land on both instances. Read SYSTEM's password once (this line prompts, so run it on its own), then run the loop:

```bash
read -s -p "SYSTEM password: " PW; echo
```

```bash
for i in 1 2 3 4 5 6; do
sqlplus -s /nolog <<EOF
connect system/"$PW"@//rac-scan:1521/racpdb1
set heading off feedback off
select sys_context('USERENV','INSTANCE_NAME') from dual;
exit
EOF
done
```

Don't use `sqlplus system@//... <<< "SELECT ..."`: sqlplus reads the password from the same input, takes the SELECT line as the password and fails with `SP2-0306`. Connecting inside sqlplus also keeps the password out of the process list. Run `unset PW` when you're done.

My build: RAC1, RAC1, RAC1, RAC2, RAC2, RAC2. This is observed connection distribution, not a guarantee of alternation or proof that every client resolves all three SCAN addresses. The listener routes connections according to service registration and load information.

7. Instance stop and restart (as oracle). In 26ai, stopping an instance that is running a PDB and service needs `-force`; without it, Clusterware refuses with `CRS-2974: unable to act on resource 'ora.rac.racpdb1.pdb' ... because that would require stopping or relocating resource 'ora.rac.rac_racpdb1.svc' but the appropriate force flag was not specified`.

```bash
srvctl stop instance -db RAC -instance RAC2 -force
srvctl status database -db RAC
srvctl status service -db RAC
# run the step 6 loop again: every connection should land on RAC1
srvctl start instance -db RAC -instance RAC2
srvctl status database -db RAC
srvctl status service -db RAC
```

My build: with RAC2 stopped, RAC1 kept running and `RAC_RACPDB1` ran on RAC1 only. After the restart, both instances ran and the service came back on RAC1 and RAC2 by itself. Completed: I subsequently confirmed the SCAN connection test while RAC2 was down. This completion is user-reported; the raw connection transcript remains to be attached. This was a controlled instance-stop/new-connection test; transparent existing-session or transaction failover and unplanned node loss were not established.

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
2. Keep one udev rules file, identical on both nodes (check with `md5sum`).
3. Never wipe OCR or data disks after the build unless rebuilding everything.
4. Install the DB home as a RAC installation, never single-instance.
5. Use Advanced DBCA for the first build and save the response files.
6. Keep disk mapping, UIDs and GIDs fixed and documented. Map disks by serial, never by sdX.
7. Do not guess after a failure; read the logs and clean residue before retrying.
8. Never commit passwords, download tokens, disk serials, machine-ids, MAC addresses or VM UUIDs to GitHub.
9. Stay on OL9 until 26ai RAC on OL10 is proven in your lab.
10. Check `VBox.log` for snail mode before any long step (root scripts, installers, DBCA).
11. Turn multi-execution mode off for single-node steps, and don't paste commands that can prompt as part of a block.
12. Run ASM and Clusterware tools as grid, database tools as oracle.
13. Keep the Windows host awake while the cluster runs.
14. Clear every **Verify** in this runbook, then change Status to Tested.

---

## Appendix A: Operating the cluster

**Which user runs what.** Role separation means each tool belongs to one owner.

| Task | User | Why |
| --- | --- | --- |
| `crsctl`, `olsnodes`, `asmcmd`, `sqlplus / as sysasm`, `asmca` | grid | Grid home binaries; SYSASM needs the asmadmin group |
| `sqlplus / as sysdba` on RAC, `dbca`, `srvctl ... database` | oracle | Database home binaries |
| `crsctl stop/start crs`, root scripts | root | Starts and stops the whole stack on a node |
| `rac_health_check.py` | grid | Needs SYSASM, and grid is also in dba |

A non-login `ssh racnode2 '<command>'` doesn't load `.bash_profile`, so set `ORACLE_HOME` in the command when you check the other node.

**Stop the whole cluster cleanly (as root):**

```bash
/u01/app/23.26/grid/bin/crsctl stop cluster -all     # stops the stack on both nodes
/u01/app/23.26/grid/bin/crsctl stop crs              # on each node; also stops High Availability Services
/u01/app/23.26/grid/bin/crsctl check crs             # CRS-4639: Could not contact Oracle High Availability Services
shutdown -h now
```

If `stop cluster -all` fails (for example with `CRS-4405`), stop each node with `crsctl stop crs`. When I stopped node 1 first, the cluster moved its SCAN VIPs and listeners to node 2, which shows SCAN failover working.

**Node VIP stuck "FAILED OVER" after a restart.** If one node comes up well before the other, the first node may host the second node's VIP, and the second node's listener stays OFFLINE.

```bash
srvctl config vip -node racnode2                         # VIP name: racnode2-vip
srvctl relocate vip -vip racnode2-vip -node racnode2
crsctl stat res ora.racnode2.vip ora.LISTENER.lsnr -t   # VIP ONLINE on racnode2; listener ONLINE on both
```

The listener restarts automatically when its VIP comes home; `PRCZ-4054 ... already running` from a later `srvctl start listener` is harmless. After the host fix, both nodes started together and the VIPs stayed on their own nodes.

## Appendix B: Evidence kept from this build

Published: [initial cluster/database transcript](../../evidence/oracle-rac/2026-10-19-rac26-initial-cluster-and-database-health.md), [revision 2026-10-19.3 health assessment](../../evidence/oracle-rac/2026-10-19-rac26-health-check-v3.md), and its sanitized terminal transcript. Other evidence below is locally retained unless separately linked.

| Phase | Evidence |
| --- | --- |
| 0 | VBox.log lines before (snail mode) and after (VT-x with nested paging) the host fix |
| 4 | `ls -lL /dev/asm-disk*` and `md5sum` of the rules file from both nodes |
| 6 | Eight-hostname SSH check from both nodes |
| 7 | Media checksums; both cluvfy pre-check logs (failed, then clean); root script logs from both nodes, including node 2's failed and successful runs; installer log; `crsctl stat res -t`; response file with no passwords |
| 8 | Disk group compatibility and mount status |
| 9 | `sqlplus -v` and `ls -l bin/oracle` from both nodes |
| 10 | DBCA summary and finish screens; generated scripts in `/u01/app/oracle/admin/RAC/scripts`; DBCA logs in `/u01/app/oracle/cfgtoollogs/dbca/RAC/` |
| 11 | `srvctl` status, `gv$instance` / `gv$pdbs` / `ARCHIVE LOG LIST`, archived logs from both threads, `crsctl stat res -t`, `asmcmd lsdg`, health check log |

Redact the Windows username path, MAC addresses, VM UUIDs, machine-ids, disk serials and X11 cookies before publishing any of it.