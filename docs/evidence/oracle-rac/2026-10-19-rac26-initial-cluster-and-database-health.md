# Oracle 26ai RAC — Initial Cluster and Database Health

**Date:** 2026-10-19  
**Environment:** Independent two-node Oracle RAC / VirtualBox lab  
**Source:** Terminal output supplied by Rotimi Omoriwo in chat. SQL*Plus displayed Mon Oct 19 06:48:39 2026; the terminal output did not specify its timezone.  
**Record type:** Formatted transcript of selected output, not an original log file or independent collection. Column wrapping and resource layout have been normalized; values below are transcribed from the supplied output.

## Commands represented

```bash
crsctl check cluster -all
crsctl stat res -t
```

```sql
SELECT inst_id, instance_name, host_name, status
FROM gv$instance ORDER BY inst_id;

SELECT inst_id, name, open_mode
FROM gv$pdbs ORDER BY name, inst_id;
```

## Cluster services

| Node | CRS-4537 CRS | CRS-4529 CSS | CRS-4533 EVM |
|---|---|---|---|
| racnode1 | ONLINE | ONLINE | ONLINE |
| racnode2 | ONLINE | ONLINE | ONLINE |

## Database and PDB SQL results

The SQL*Plus and connected Oracle AI Database Enterprise Edition banners both reported version `23.26.1.0.0`. This is version evidence, not a complete patch inventory or a claim of production employment.

| INST_ID | INSTANCE_NAME | HOST_NAME | STATUS |
|---:|---|---|---|
| 1 | RAC1 | racnode1 | OPEN |
| 2 | RAC2 | racnode2 | OPEN |

| INST_ID | NAME | OPEN_MODE |
|---:|---|---|
| 1 | PDB$SEED | READ ONLY |
| 2 | PDB$SEED | READ ONLY |
| 1 | RACPDB1 | READ WRITE |
| 2 | RACPDB1 | READ WRITE |

## Clusterware resources

Every listed resource below was STABLE. For ONLINE rows, target and state were both ONLINE; for OFFLINE rows, target and state were both OFFLINE.

| Resource | Nodes / placement | State and details |
|---|---|---|
| ora.LISTENER.lsnr | racnode1, racnode2 | ONLINE |
| ora.chad | racnode1, racnode2 | ONLINE |
| ora.helper | racnode1, racnode2 | OFFLINE, IDLE |
| ora.net1.network | racnode1, racnode2 | ONLINE |
| ora.ons | racnode1, racnode2 | ONLINE |
| ora.ASMNET1LSNR_ASM.lsnr (ora.asmgroup) | racnode1, racnode2 | ONLINE |
| ora.DATA.dg (ora.asmgroup) | racnode1, racnode2 | ONLINE |
| ora.FRA.dg (ora.asmgroup) | racnode1, racnode2 | ONLINE |
| ora.OCR.dg (ora.asmgroup) | racnode1, racnode2 | ONLINE |
| ora.asm (ora.asmgroup) | racnode1, racnode2 | ONLINE, Started |
| ora.asmnet1.asmnetwork (ora.asmgroup) | racnode1, racnode2 | ONLINE |
| ora.LISTENER_SCAN1.lsnr | racnode1 | ONLINE |
| ora.LISTENER_SCAN2.lsnr | racnode1 | ONLINE |
| ora.LISTENER_SCAN3.lsnr | racnode2 | ONLINE |
| ora.cdp1.cdp, ora.cdp2.cdp, ora.cdp3.cdp | No server shown | OFFLINE |
| ora.cvu | racnode1 | ONLINE |
| ora.cvuhelper | No server shown | OFFLINE |
| ora.rac.db | racnode1, racnode2 | ONLINE, Open; HOME=/u01/app/oracle/product/23.26/dbhome_1 |
| ora.rac.rac_racpdb1.svc | racnode1, racnode2 | ONLINE |
| ora.rac.racpdb1.pdb | racnode1, racnode2 | ONLINE, READ WRITE |
| ora.racnode1.vip | racnode1 | ONLINE |
| ora.racnode2.vip | racnode2 | ONLINE |
| ora.rhpserver | No server shown | OFFLINE |
| ora.scan1.vip | racnode1 | ONLINE |
| ora.scan2.vip | racnode1 | ONLINE |
| ora.scan3.vip | racnode2 | ONLINE |

The OFFLINE resources have OFFLINE targets in this output; they are not shown as failed ONLINE-target resources. Their state does not by itself establish a cluster fault or prove every optional feature is configured.

## What this establishes

One RAC database has two open instances, RAC1 and RAC2. RACPDB1 is READ WRITE on both. ASM/storage, database/service, node VIP/listener and SCAN resources are online as listed. The output contains no reported failed resource state.

## What remains unverified

- Client login to the intended PDB application service through SCAN, including name resolution.
- ARCHIVELOG mode, backup and restore/recovery validation.
- Database/PDB/service startup persistence and instance/node failure behavior.
- Transparent session or transaction failover, which requires separate configuration and testing.
- Exact installed cluster name and complete Grid/DB patch inventories.
- Resolution of the reported UEK8/23.26.1 compatibility gap. Database OPEN is not certification.

No password, token, disk serial, machine-id, MAC, VM UUID or Windows username path was included in this formatted record. Hostnames, database/service names and installation paths are retained as lab context.

See the [26ai RAC build runbook](../../runbooks/oracle-rac/oracle26ai-2node-rac-build-runbook.md).
