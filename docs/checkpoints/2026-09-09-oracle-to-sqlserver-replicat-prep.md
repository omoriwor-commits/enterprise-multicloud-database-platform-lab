# Checkpoint — Oracle 26ai to SQL Server 2022 Replicat Preparation

**Checkpoint date:** September 9, 2026  
**Workstream:** OCI Oracle 26ai -> Azure GoldenGate 26ai hub -> Azure SQL Server 2022  
**Architecture:** Remote Extract + remote Replicat from one Azure GoldenGate hub

> Security note: passwords, private keys, PSKs, and current administrator source IPs are intentionally omitted.

---

## 1. Current architecture

```text
OCI Oracle Database 26ai
10.50.10.178:1521
CDB23AI / PDB23AI
        |
        | remote Integrated Extract
        v
Azure GoldenGate hub
vm-goldengate-lab-01
10.60.30.4
        |
        +-- Oracle runtime / DEP1
        |     EXTORA -> ./dirdat/ea
        |
        +-- SQL Server runtime / MSSQLDEP
              REPSQL (being configured)
        |
        | remote apply
        v
Azure SQL Server 2022
10.60.20.4:1433
OGGTargetDB
HOLA.FOX
```

The central-hub model remains intact: GoldenGate processes run on the Azure hub while Oracle and SQL Server remain on their own database hosts.

---

## 2. Oracle source capture remains healthy

Validated Oracle Extract state:

```text
Extract:               EXTORA
Capture mode:          Integrated, per-PDB
Trail:                 ./dirdat/ea
Checkpoint lag:        00:00:00 at validation
Source table:          HOLA.FOX
Observed inserts:      1
Observed updates:      1
Observed deletes:      0
Observed operations:   2
Metadata records:      1
```

Oracle capture therefore remains proven before target apply is introduced.

---

## 3. Correct Linux SQL Server GoldenGate media obtained

The correct package was downloaded and validated:

```text
V1054820-01.zip
Oracle GoldenGate 23.26.1.0.1
Linux x86-64 for Microsoft SQL Server
```

Archive validation returned no errors, and the extracted shiphome identified itself as:

```text
ggs_Linux_x64_MSSQL_services_shiphome
```

This replaced the earlier Windows-x64 package mismatch.

---

## 4. Separate SQL Server GoldenGate home installed

A dedicated Microsoft SQL Server GoldenGate home was installed on the existing hub:

```text
/u01/ogg26ai_mssql_home
```

Installation completed successfully with Oracle Universal Installer.

Validated SQL Server runtime components include:

```text
/u01/ogg26ai_mssql_home/bin/replicat
/u01/ogg26ai_mssql_home/bin/adminclient
/u01/ogg26ai_mssql_home/lib/libadminclient_MSSQL.so
/u01/ogg26ai_mssql_home/msodbc/lib64/libmsodbcsql.so
/u01/ogg26ai_mssql_home/msodbc/odbcinst.ini
/u01/ogg26ai_mssql_home/msodbc/mssql_odbcini_template.ini
```

The existing Oracle home remains unchanged:

```text
/u01/ogg26ai_home
```

---

## 5. unixODBC prerequisite resolved

Initial OGGCA work exposed a missing Linux prerequisite:

```text
unixODBC        NOT INSTALLED
unixODBC-devel  NOT INSTALLED
```

Oracle Linux 9 CodeReady Builder was enabled, then the packages were installed:

```text
unixODBC-2.3.12-1.el9.x86_64
unixODBC-devel-2.3.12-1.el9.x86_64
```

Validation:

```text
odbcinst -> available
isql     -> available
```

---

## 6. SQL Server DSN and ODBC connectivity validated

The GoldenGate-supplied template was copied to:

```text
/u01/ogg26ai_mssql_home/msodbc/odbc.ini
```

Configured DSN:

```ini
[SQL_TGT]
Driver = Microsoft ODBC Driver for SQL Server
Server = tcp:10.60.20.4,1433
Database = OGGTargetDB
Encrypt = yes
TrustServerCertificate = yes
```

The environment was validated with:

```text
ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc
ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini
```

`odbcinst` confirmed both the bundled driver and `SQL_TGT` DSN.

A direct `isql` test using the dedicated SQL login succeeded:

```text
Connected!
SELECT DB_NAME();
-> OGGTargetDB
```

This proved the full path:

```text
GoldenGate hub
-> unixODBC
-> Microsoft ODBC Driver 18
-> SQL_TGT DSN
-> 10.60.20.4:1433
-> ogg_repl
-> OGGTargetDB
```

---

## 7. MSSQLDEP created successfully with OGGCA GUI

Silent OGGCA repeatedly returned an `ODBCSYSINI` validation error even when the shell values were supplied correctly. The deployment was therefore created through the SQL Server-specific OGGCA GUI after cleaning the shell environment.

Dedicated SQL Server deployment:

```text
Deployment:                    MSSQLDEP
Software home:                 /u01/ogg26ai_mssql_home
Service Manager home:          /u01/ogg26ai_mssql_deploy
User deployment home:          /u01/ogg26ai_mssql_sm
Service Manager port:          9021
Administration Service port:   9022
Distribution Service port:     9023
Receiver Service port:         9024
Performance Metrics port:      9025
Replication schema:            ogg_repl
Security:                      disabled for lab phase
```

The MSSQL deployment was intentionally created as a separate Service Manager and was not registered as the same system daemon used by Oracle `DEP1`.

OGGCA completed with:

```text
The configuration of The Oracle GoldenGate Deployment was successful.
```

---

## 8. MSSQLDEP runtime validation

Process validation showed both GoldenGate stacks running independently.

Oracle deployment:

```text
/u01/ogg26ai_home/bin/ServiceManager
/u01/ogg26ai_home/bin/adminsrvr
DEP1
```

SQL Server deployment:

```text
/u01/ogg26ai_mssql_home/bin/ServiceManager
/u01/ogg26ai_mssql_home/bin/adminsrvr
/u01/ogg26ai_mssql_home/bin/distsrvr
/u01/ogg26ai_mssql_home/bin/recvsrvr
/u01/ogg26ai_mssql_home/bin/pmsrvr
MSSQLDEP
```

All target ports were listening:

```text
9021 Service Manager
9022 Administration Server
9023 Distribution Server
9024 Receiver Server
9025 Performance Metrics Server
```

---

## 9. Management-plane access troubleshooting resolved

The MSSQL Administration Server returned HTTP 200 locally on the VM private address:

```text
http://10.60.30.4:9022/
HTTP/1.1 200 OK
```

Public-browser access initially failed because Oracle Linux `firewalld` allowed only the existing Oracle web ports:

```text
9011/tcp
9012/tcp
```

A source-restricted Azure NSG rule was created for TCP 9022, and `firewalld` was updated to allow:

```text
9022/tcp
```

The browser then successfully opened:

```text
Oracle GoldenGate 23.26.1.0.1 for Microsoft SQL Server (MSSQLDEP)
```

Only the Administration Server is exposed for browser administration; the remaining MSSQLDEP ports are not broadly opened publicly.

---

## 10. SQL Server GoldenGate credential and metadata schema

Dedicated SQL login/database user:

```text
Login:          ogg_repl
Database user:  ogg_repl
Database:       OGGTargetDB
Enabled:        yes
```

A dedicated schema was created:

```text
ogg_repl
```

Validated database roles:

```text
db_owner
db_datareader
db_datawriter
```

The password is not stored in GitHub.

---

## 11. GoldenGate DB connection validated

A DB Connection was created in **MSSQLDEP**:

```text
Credential Domain: OracleGoldenGate
Credential Alias:  SQL_TGT
Connection Type:   Data Source Name (DSN)
DSN:               SQL_TGT
User ID:           ogg_repl
```

GoldenGate successfully connected to the target database, exposing database-management functions for:

```text
Checkpoint
Trandata
Heartbeat
```

This confirms the GoldenGate runtime itself—not only `isql`—can authenticate to SQL Server.

---

## 12. Checkpoint table created

A dedicated Replicat checkpoint table was created successfully:

```text
ogg_repl.ggs_checkpoint
```

This provides database-backed Replicat checkpoint state for recovery/restart testing.

---

## 13. Replicat configuration now in progress

Replicat creation has started in the MSSQLDEP Administration Server.

Selected values:

```text
Replicat type:  Classic Replicat
Process name:   REPSQL
Description:    Oracle HOLA.FOX to SQL Server HOLA.FOX
```

Current wizard position:

```text
Step 2 - Replicat Options
```

Target values being configured:

```text
Trail name:          ea
Trail subdirectory:  dirdat
Target domain:       OracleGoldenGate
Target alias:        SQL_TGT
Checkpoint table:    ogg_repl.ggs_checkpoint
Begin:               Position in Trail
```

The next controlled step is to verify the trail-position fields before completing Replicat creation.

---

## 14. Current status

| Component | Status |
|---|---|
| OCI Oracle source | Ready / capture validated |
| OCI<->Azure VPN/BGP | Healthy |
| Oracle GoldenGate home | Healthy |
| Oracle deployment `DEP1` | Running |
| Oracle Extract `EXTORA` | Running |
| Oracle `HOLA.FOX` capture | Validated |
| Trail `./dirdat/ea` | Contains captured changes |
| SQL Server target | Running |
| SQL Server TCP 1433 from hub | Reachable |
| `OGGTargetDB.HOLA.FOX` | Present and structurally validated |
| `ogg_repl` SQL login/user | Enabled |
| `ogg_repl` schema | Created |
| `ogg_repl` db_owner | Validated |
| Linux MSSQL GoldenGate home | Installed |
| unixODBC / unixODBC-devel | Installed |
| `SQL_TGT` DSN | Validated |
| Direct `isql` login | Validated |
| MSSQLDEP | Running |
| MSSQLDEP ports 9021-9025 | Listening |
| MSSQL Administration UI | Reachable |
| GoldenGate `SQL_TGT` DB connection | Validated |
| Checkpoint table | Created |
| `REPSQL` Replicat | Configuration in progress |
| End-to-end Oracle->SQL Server apply | Pending |

---

## 15. Next controlled steps

1. Complete `REPSQL` Replicat Options and verify trail start position.
2. Complete the Replicat parameter file with the `HOLA.FOX` source-to-target mapping.
3. Start `REPSQL` and inspect report/log output before generating new source changes.
4. Verify previously captured trail records are applied as intended.
5. Generate controlled INSERT, UPDATE, and DELETE transactions on Oracle `HOLA.FOX`.
6. Validate delivery into SQL Server `HOLA.FOX`.
7. Reconcile source/target row counts and column values.
8. Test Replicat stop/start and checkpoint recovery.
9. Measure lag and verify no duplicate apply after restart.
10. Document cutover/rollback behavior.
11. Continue toward AWS PostgreSQL after Oracle-to-SQL Server CDC is stable.

---

## 16. Key lessons from this phase

- Heterogeneous GoldenGate deployments require the correct database-family runtime even when hosted on the same hub VM.
- Package platform must be verified from archive contents, not inferred from product family alone.
- `unixODBC` and `unixODBC-devel` are operational prerequisites for this Linux SQL Server GoldenGate path.
- Direct `isql` validation is useful for isolating DSN/driver/authentication failures before troubleshooting OGGCA or Replicat.
- A second GoldenGate deployment should be isolated from the existing Oracle deployment by home, deployment directories, ports, and service-manager lifecycle.
- Shell environment contamination can make OGGCA inherit the wrong Oracle-home library paths.
- Local HTTP 200 tests, Azure NSG inspection, and `firewalld` inspection cleanly separate application, cloud-network, and guest-firewall failures.
- GoldenGate metadata belongs in a dedicated replication schema rather than the application schema.
- Preserve secrets outside source control.
