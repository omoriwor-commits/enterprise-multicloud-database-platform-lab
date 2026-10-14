## SQL Server GoldenGate Runtime — Completed

The correct Linux x86-64 GoldenGate package for Microsoft SQL Server was obtained and validated:

```text
V1054820-01.zip
GoldenGate 23.26.1.0.1
Linux x86-64 for Microsoft SQL Server
```

The dedicated SQL Server GoldenGate home is installed at:

```text
/u01/ogg26ai_mssql_home
```

Validated bundled components include:

```text
bin/replicat
bin/adminclient
msodbc/lib64/libmsodbcsql.so
msodbc/odbcinst.ini
msodbc/mssql_odbcini_template.ini
```

The earlier Windows-x64 package mismatch is retained in the dated project history as a troubleshooting case.

## ODBC / SQL Server Connectivity — Completed

Oracle Linux prerequisites installed:

```text
unixODBC-2.3.12-1.el9.x86_64
unixODBC-devel-2.3.12-1.el9.x86_64
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

Direct validation succeeded:

```text
isql -> Connected!
SELECT DB_NAME(); -> OGGTargetDB
```

A GoldenGate DB Connection was also created and validated in `MSSQLDEP`:

```text
Credential Domain: OracleGoldenGate
Credential Alias:  SQL_TGT
DSN:               SQL_TGT
User ID:           ogg_repl
```

GoldenGate itself can therefore authenticate to the target database.

## MSSQLDEP Deployment — Completed

The SQL Server-specific OGGCA deployment was created successfully after isolating the MSSQL shell environment from the Oracle `DEP1` environment.

All MSSQLDEP services were verified listening:

```text
9021 Service Manager
9022 Administration Server
9023 Distribution Server
9024 Receiver Server
9025 Performance Metrics Server
```

Management-plane troubleshooting also separated three layers cleanly:

```text
GoldenGate application -> healthy locally
Azure NSG             -> source-restricted 9022 rule added
Oracle Linux firewalld -> 9022/tcp added
```

The SQL Server Administration UI is now reachable and identifies itself as:

```text
Oracle GoldenGate 23.26.1.0.1 for Microsoft SQL Server (MSSQLDEP)
```

## Replicat Configuration (September 2026 snapshot)

Checkpoint table created:

```text
ogg_repl.ggs_checkpoint
```

At that point, Replicat creation had started with:

```text
Replicat Type: Classic Replicat
Process Name:  REPSQL
Description:   Oracle HOLA.FOX to SQL Server HOLA.FOX
```

Replicat options being prepared at that point:

```text
Trail name:          ea
Trail subdirectory:  dirdat
Target domain:       OracleGoldenGate
Target alias:        SQL_TGT
Checkpoint table:    ogg_repl.ggs_checkpoint
Begin:               Position in Trail
```

**September 2026 snapshot:** At the date of this configuration snapshot, trail positioning and Replicat target apply were still being prepared. I completed the implementation afterward; the rerun will capture the final target-side outputs.

## Archived Build Checkpoint — September 9, 2026

| Component | Status |
|---|---|
| OCI Oracle source | Ready / capture validated |
| OCI<->Azure VPN/BGP | Healthy |
| Oracle GoldenGate `DEP1` | Running |
| Oracle Extract `EXTORA` | Running |
| Oracle `HOLA.FOX` capture | Validated |
| Trail `./dirdat/ea` | Contains captured changes |
| Azure SQL Server | Running |
| SQL Server TCP 1433 from hub | Reachable |
| `OGGTargetDB.HOLA.FOX` | Present / validated |
| `ogg_repl` login/user/schema | Ready |
| Linux MSSQL GoldenGate runtime | Installed |
| unixODBC | Installed / validated |
| `SQL_TGT` DSN | Validated |
| MSSQLDEP | Running |
| MSSQL Administration UI | Reachable |
| GoldenGate `SQL_TGT` connection | Validated |
| `ogg_repl.ggs_checkpoint` | Created |
| `REPSQL` | Configuration in progress at September checkpoint |
| End-to-end Oracle -> SQL Server apply | Completed after this checkpoint — see Final outcome |

