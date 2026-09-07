# Checkpoint — Oracle 26ai to SQL Server 2022 CDC Progress

**Checkpoint date:** September 7, 2026  
**Workstream:** OCI Oracle 26ai -> Azure GoldenGate 26ai hub -> Azure SQL Server 2022  
**Model:** Dedicated GoldenGate hub with remote capture and remote apply

> Security note: passwords, private-key material, current administrator source IPs, and other secrets are intentionally omitted.

---

## 1. Current architecture

```text
OCI Oracle Database 26ai
10.50.10.178:1521
CDB23AI / PDB23AI
        |
        | remote database connection
        v
Azure GoldenGate hub
vm-goldengate-lab-01
10.60.30.4
        |
        | EXTORA -> local trail ./dirdat/ea
        |
        | planned remote Replicat
        v
Azure SQL Server 2022
vm-sqlserver-lab-01
10.60.20.4:1433
OGGTargetDB
HOLA.FOX
```

The design remains **remote Extract + remote Replicat from a central GoldenGate hub**. GoldenGate processes run on the hub; the Oracle and SQL Server database engines remain on their own database hosts.

---

## 2. Oracle source capture validation

Oracle source baseline:

```text
Database:       Oracle AI Database 26ai Enterprise Edition
Version:        23.26.1.0.0
CDB:            CDB23AI
PDB:            PDB23AI
Service:        pdb23ai
Listener:       TCP 1521
ARCHIVELOG:     enabled
FORCE LOGGING:  YES
enable_goldengate_replication: TRUE
```

GoldenGate Extract:

```text
Group:                 EXTORA
Status:                RUNNING
Capture mode:          Oracle Integrated Redo Logs, per-PDB
Trail output:          ./dirdat/ea
Checkpoint lag:        00:00:00 at validation
Encryption profile:    LocalWallet
```

Observed Extract statistics for `HOLA.FOX`:

```text
Total inserts:          1
Total updates:          1
Total deletes:          0
Total operations:       2
Total metadata records: 1
```

This proves that the Oracle source changes were captured by `EXTORA` and written to the GoldenGate trail.

---

## 3. Oracle FRA incident and capture-readiness impact

During source preparation, Oracle sessions stalled on:

```text
log file switch (archiving needed)
```

Evidence identified:

```text
DB_RECOVERY_FILE_DEST      /u03/fra
DB_RECOVERY_FILE_DEST_SIZE 10G
FRA used                   ~9.88G
Reclaimable                0
Archive destination        ERROR
ORA-19809                  limit exceeded for recovery files
```

The blocking background process was LGWR and was correctly **not killed**. Linux filesystem capacity was not exhausted; the issue was the Oracle FRA logical quota. The FRA filesystem also contains recovery areas for both `CDB23AI` and `RMAN26`, so direct OS deletion was rejected in favor of RMAN-aware recovery-area management.

Database health was restored sufficiently to proceed with GoldenGate source capture validation, as demonstrated by the later healthy running Extract and zero checkpoint lag.

---

## 4. SQL Server target VM and private access

Target platform:

```text
VM:          vm-sqlserver-lab-01
Private IP:  10.60.20.4
OS:          Windows Server 2022
Database:    SQL Server 2022 Developer
SQL port:    TCP 1433
VM size:     Standard_D2as_v7
```

The SQL Server VM has no directly assigned public IP. Administration therefore uses a controlled SSH tunnel through the GoldenGate hub instead of exposing RDP broadly.

### RDP troubleshooting

Initial test from the GoldenGate hub:

```text
10.60.30.4 -> 10.60.20.4:3389
Result: NOT REACHABLE
```

At the Windows guest level:

```text
Remote Desktop Services (TermService): Running
TCP 3389: Listening on 0.0.0.0 and ::
Windows Firewall Remote Desktop rules: Enabled / Allow
```

Azure Network Watcher IP Flow Verify initially showed the custom deny rule blocking the flow. A source-restricted NSG rule was added for:

```text
Source:      10.60.30.4/32
Destination: 10.60.20.4/32
Protocol:    TCP
Port:        3389
```

IP Flow Verify then returned **Access allowed**, and the GoldenGate hub test changed to:

```text
RDP 3389 REACHABLE
```

### SSH local-port forwarding

A local tunnel was built in MobaXterm:

```text
Local port:        13389
Destination:       10.60.20.4:3389
SSH jump host:     GoldenGate hub
SSH user:          azureuser
Private key:       local workstation key file
```

Windows RDP then connected through:

```text
127.0.0.1:13389
```

This provided access to the SQL Server VM without assigning a public IP to that VM.

---

## 5. SQL Server Management Studio validation

SQL Server Management Studio 20 is installed on the target VM.

Validated local connection:

```text
Server type:     Database Engine
Server:          local SQL Server instance
Authentication:  Windows Authentication
```

The target database already existed:

```text
OGGTargetDB
```

The target schema also already existed:

```text
HOLA
```

---

## 6. Target table validation

Existing SQL Server target table:

```text
OGGTargetDB.HOLA.FOX
```

Validated columns:

| Column | SQL Server type | Nullable |
|---|---|---|
| `ID` | `int` | NO |
| `NAME` | `varchar(100)` | YES |
| `CREATED_AT` | `datetime2` | YES |
| `STATUS` | `varchar(20)` | YES |

Primary key validation:

```text
Constraint: PK_FOX
Column:     ID
```

This matches the intended Oracle-to-SQL Server mapping baseline for the current CDC test.

---

## 7. GoldenGate target SQL login

A dedicated SQL Server login and database user were created for GoldenGate target apply:

```text
Server login:   ogg_repl
Type:           SQL_LOGIN
Disabled:       0
Database user:  ogg_repl
Database:       OGGTargetDB
Roles:          db_datareader, db_datawriter
```

The credential password is intentionally not stored in this repository.

GoldenGate hub connectivity to SQL Server was revalidated:

```text
10.60.30.4 -> 10.60.20.4:1433
Result: SQL 1433 REACHABLE
```

---

## 8. GoldenGate target-runtime discovery

An attempt to proceed with a `SQL_TGT` DB credential in the existing `DEP1` deployment was paused before submission so the installed GoldenGate runtime could be validated first.

Existing GoldenGate home:

```text
/u01/ogg26ai_home
```

Evidence from the install response file identifies this as the Oracle database build:

```text
Oracle GoldenGate for Oracle Database 23ai and lower supported versions
```

The home does contain:

```text
/u01/ogg26ai_home/lib/libadminclient_MSSQL.so
```

but does **not** contain the SQL Server ODBC runtime area expected for a Linux SQL Server GoldenGate target environment:

```text
/u01/ogg26ai_home/msodbc                NOT PRESENT
odbc.ini                               NOT FOUND
odbcinst.ini                           NOT FOUND
libmsodbcsql.so                        NOT FOUND
```

Engineering conclusion: the existing Oracle GoldenGate home remains the Oracle-source runtime. SQL Server target apply will use a **separate SQL Server-specific GoldenGate home/deployment on the same hub VM** while preserving the central remote-capture/remote-apply architecture.

Planned logical layout:

```text
/u01/ogg26ai_home
  Oracle GoldenGate runtime
  DEP1
  EXTORA

/u01/ogg_sqlserver_home
  SQL Server-specific GoldenGate runtime
  separate deployment
  Replicat -> 10.60.20.4:1433 / OGGTargetDB
```

---

## 9. SQL Server GoldenGate media-transfer incident

A previously downloaded GoldenGate package for Microsoft SQL Server was copied from the administrator workstation to the hub.

### First transfer attempt — incomplete

The first SCP transfer dropped around 53%. The hub-side file was only about 288 MB and failed ZIP validation with:

```text
End-of-central-directory signature not found
```

The incomplete file was removed before any extraction.

### Second transfer attempt — successful

MobaXterm SFTP was used for a complete transfer. Hub-side size was approximately 509 MB, and archive validation returned:

```text
No errors detected in compressed data
```

### Platform mismatch discovered

Inspection of the archive contents identified:

```text
ggs_Windows_x64_MSSQL_services_shiphome
setup.exe
oui.exe
```

Therefore the transferred media is **GoldenGate for Microsoft SQL Server on Windows x64**, not the required Linux x86-64 build for the Oracle Linux GoldenGate hub.

No installation was attempted from the mismatched media.

**Current blocker:** obtain the correct **Oracle GoldenGate 26ai for Microsoft SQL Server — Linux x86-64** distribution, verify its archive contents, and install it into a separate SQL Server GoldenGate home on the existing hub.

---

## 10. Current validated status

| Component | Status |
|---|---|
| OCI Oracle source | Ready / capture validated |
| OCI↔Azure VPN/BGP | Healthy |
| Azure GoldenGate Oracle home | Healthy |
| Service Manager systemd registration | Resolved |
| GoldenGate Microservices | Running |
| `EXTORA` | Running |
| `HOLA.FOX` Oracle capture | Insert/update captured |
| GoldenGate trail `ea` | Receiving records |
| Azure SQL Server | Running |
| SQL Server TCP 1433 from hub | Reachable |
| SQL Server private RDP through hub | Validated |
| `OGGTargetDB` | Present |
| SQL Server `HOLA.FOX` | Present and structurally validated |
| `PK_FOX` | Present on `ID` |
| `ogg_repl` login/user | Created and enabled |
| SQL Server Replicat | Not created yet |
| Correct Linux MSSQL GoldenGate runtime | Pending |

---

## 11. Next controlled steps

1. Obtain the **Linux x86-64 GoldenGate 26ai for Microsoft SQL Server** package.
2. Validate archive integrity and confirm the package identifies itself as Linux x86-64 MSSQL before extraction.
3. Install into a separate SQL Server GoldenGate home on `vm-goldengate-lab-01`.
4. Create a separate SQL Server-target GoldenGate deployment without disturbing Oracle `DEP1` / `EXTORA`.
5. Configure SQL Server ODBC/connectivity components.
6. Create the target credential/DB connection for `ogg_repl` without storing the password in GitHub.
7. Validate GoldenGate DB login to `OGGTargetDB`.
8. Configure Replicat mapping from Oracle `HOLA.FOX` to SQL Server `HOLA.FOX`.
9. Start Replicat and verify INSERT/UPDATE/DELETE delivery.
10. Reconcile source/target row counts and values.
11. Perform restart/recovery, lag, checkpoint, and failure-injection tests.
12. Document cutover/rollback and then continue toward AWS PostgreSQL.

---

## 12. Lessons reinforced by this checkpoint

- Verify package **platform and database family** before installation, not just file name or product family.
- Verify large transfer integrity before extraction.
- A central GoldenGate hub can run remote capture and remote apply, but the hub still requires the correct database-specific runtime/client components.
- Do not expose SQL Server RDP publicly when a controlled jump/tunnel path is available.
- Use Azure Network Watcher/IP Flow Verify to separate guest-OS, NSG, and routing failures.
- Do not kill Oracle background processes such as LGWR when the actual fault is FRA/archive pressure.
- Preserve working Oracle Extract state while introducing the heterogeneous target runtime separately.
