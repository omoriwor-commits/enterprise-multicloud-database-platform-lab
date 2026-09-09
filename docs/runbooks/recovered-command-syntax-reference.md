# Recovered Command and Syntax Reference

**Project:** Enterprise Multi-Cloud Database Platform Lab  
**Purpose:** Preserve the important commands, SQL, GoldenGate syntax, validation checks, and troubleshooting commands used during the OCI Oracle -> Azure GoldenGate -> Azure SQL Server implementation.  
**Important:** This file is intentionally separate from the existing README, checkpoint, project-history, and architecture files so those records are not disturbed.

> Security note: passwords, private keys, VPN pre-shared keys, current administrator source IPs, and other secrets are intentionally omitted. Replace placeholders only in your private lab session; do not commit secrets.

---

# 1. GoldenGate Hub — Core Paths and Existing Oracle Deployment

Existing Oracle GoldenGate home and deployment:

```bash
export OGG_HOME=/u01/ogg26ai_home
export OGG_DEPLOY=/u01/ogg26ai_deploy
```

Important Oracle deployment paths observed in the lab:

```text
/u01/ogg26ai_home
/u01/ogg26ai_deploy
/u01/ogg26ai_sm
```

Oracle deployment ports:

```text
9011  Service Manager
9012  Administration Server
9013  Distribution Server
9014  Receiver Server
9015  Performance Metrics Server
```

Existing Oracle Extract:

```text
EXTORA
```

Existing Oracle trail:

```text
./dirdat/ea
```

Useful service/process check:

```bash
ps -ef | grep -E 'ServiceManager|adminsrvr|distsrvr|recvsrvr|pmsrvr' | grep -v grep
```

Port check:

```bash
ss -lntp | grep -E ':(9011|9012|9013|9014|9015)\b'
```

---

# 2. Oracle Source Capture Checks

The source-side work validated ARCHIVELOG, FORCE LOGGING, supplemental logging, GoldenGate replication support, and source table logging.

Examples of the GoldenGate-side transaction logging commands used/validated:

```text
ADD TRANDATA HOLA.FOX
INFO TRANDATA HOLA.FOX
```

Extract statistics check:

```text
STATS EXTRACT EXTORA, TABLE HOLA.FOX
```

The observed capture evidence included insert/update operations and metadata records for `HOLA.FOX`.

Useful Oracle-side health checks to retain for rebuilds:

```sql
SELECT log_mode FROM v$database;
SELECT force_logging FROM v$database;
SHOW PARAMETER enable_goldengate_replication;
```

When validating supplemental logging:

```sql
SELECT supplemental_log_data_min
FROM v$database;
```

---

# 3. SQL Server Target — Database, Schema, Table, Login, and Roles

Target database used in the implemented lab:

```text
OGGTargetDB
```

Target table:

```text
HOLA.FOX
```

Validated SQL Server structure:

```text
ID          int           NOT NULL
NAME        varchar(100)  NULL
CREATED_AT  datetime2     NULL
STATUS      varchar(20)   NULL
```

Primary key:

```text
PK_FOX(ID)
```

GoldenGate login/user verification:

```sql
SELECT name, type_desc, is_disabled
FROM sys.server_principals
WHERE name = 'ogg_repl';
```

Database user verification:

```sql
USE OGGTargetDB;
GO

SELECT name, type_desc
FROM sys.database_principals
WHERE name = 'ogg_repl';
GO
```

Create the GoldenGate SQL login when rebuilding from scratch:

```sql
CREATE LOGIN ogg_repl
WITH PASSWORD = '<STRONG-LAB-PASSWORD>',
     CHECK_POLICY = ON;
GO
```

Create the database user:

```sql
USE OGGTargetDB;
GO

CREATE USER ogg_repl FOR LOGIN ogg_repl;
GO
```

Initial data access roles:

```sql
ALTER ROLE db_datareader ADD MEMBER ogg_repl;
ALTER ROLE db_datawriter ADD MEMBER ogg_repl;
GO
```

Create the dedicated GoldenGate schema if missing:

```sql
USE OGGTargetDB;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'ogg_repl'
)
    EXEC('CREATE SCHEMA ogg_repl AUTHORIZATION ogg_repl');
GO
```

Grant the target Replicat account `db_owner` for the lab configuration:

```sql
ALTER ROLE db_owner ADD MEMBER ogg_repl;
GO
```

Verify schema and roles:

```sql
SELECT name
FROM sys.schemas
WHERE name = 'ogg_repl';

SELECT r.name AS role_name
FROM sys.database_role_members drm
JOIN sys.database_principals r
  ON drm.role_principal_id = r.principal_id
JOIN sys.database_principals u
  ON drm.member_principal_id = u.principal_id
WHERE u.name = 'ogg_repl';
```

Reset the SQL login password when necessary:

```sql
ALTER LOGIN ogg_repl
WITH PASSWORD = '<NEW-STRONG-LAB-PASSWORD>';
GO
```

---

# 4. GoldenGate Hub -> SQL Server Network Validation

Basic TCP test from the GoldenGate hub to SQL Server:

```bash
timeout 5 bash -c '</dev/tcp/10.60.20.4/1433' \
  && echo 'SQL 1433 REACHABLE' \
  || echo 'SQL 1433 NOT REACHABLE'
```

Target endpoint:

```text
10.60.20.4:1433
```

---

# 5. Correct GoldenGate MSSQL Linux Media Validation

Correct Linux x86-64 SQL Server GoldenGate package used:

```text
V1054820-01.zip
```

ZIP integrity test:

```bash
unzip -t /u01/software/V1054820-01.zip | tail -20
```

Inspect platform/content before installation:

```bash
unzip -l /u01/software/V1054820-01.zip | head -40
```

Correct archive identifier observed:

```text
ggs_Linux_x64_MSSQL_services_shiphome
```

Wrong Windows package identifier that must not be installed on Oracle Linux:

```text
ggs_Windows_x64_MSSQL_services_shiphome
```

Extraction:

```bash
unzip -q /u01/software/V1054820-01.zip \
-d /u01/software/gg26ai_Linux_sql
```

Verify installer/response files:

```bash
find /u01/software/gg26ai_Linux_sql -maxdepth 3 \
-type f \( -name runInstaller -o -name oggcore.rsp \) \
-print
```

---

# 6. MSSQL GoldenGate Software Installation

Installer response values used:

```text
INSTALL_OPTION=MSSQL
SOFTWARE_LOCATION=/u01/ogg26ai_mssql_home
INVENTORY_LOCATION=/u01/app/oraInventory
UNIX_GROUP_NAME=azureuser
```

Copy the supplied response file:

```bash
cp response/oggcore.rsp /home/azureuser/ogg26ai_mssql_install.rsp
```

Populate it:

```bash
sed -i \
-e 's|^INSTALL_OPTION=.*|INSTALL_OPTION=MSSQL|' \
-e 's|^SOFTWARE_LOCATION=.*|SOFTWARE_LOCATION=/u01/ogg26ai_mssql_home|' \
-e 's|^INVENTORY_LOCATION=.*|INVENTORY_LOCATION=/u01/app/oraInventory|' \
-e 's|^UNIX_GROUP_NAME=.*|UNIX_GROUP_NAME=azureuser|' \
/home/azureuser/ogg26ai_mssql_install.rsp
```

Verify response values:

```bash
grep -Ev '^[[:space:]]*(#|$)' /home/azureuser/ogg26ai_mssql_install.rsp
```

Installer execute permissions encountered during the lab:

```bash
chmod 755 runInstaller
chmod 755 install/.oui
```

Create/install target home with appropriate ownership:

```bash
sudo mkdir -p /u01/ogg26ai_mssql_home
sudo chown azureuser:azureuser /u01/ogg26ai_mssql_home
chmod 755 /u01/ogg26ai_mssql_home
```

Run installer:

```bash
./runInstaller -silent \
-responseFile /home/azureuser/ogg26ai_mssql_install.rsp \
-waitforcompletion
```

Validate SQL Server-specific runtime files:

```bash
find /u01/ogg26ai_mssql_home -maxdepth 3 \
\( -name 'libmsodbcsql.so' \
   -o -name 'mssql_odbcini_template.ini' \
   -o -name 'libadminclient_MSSQL.so' \) \
-print
```

Verify GoldenGate binaries:

```bash
ls -l /u01/ogg26ai_mssql_home/bin/replicat \
      /u01/ogg26ai_mssql_home/bin/adminclient
```

Find OGGCA:

```bash
find /u01/ogg26ai_mssql_home -type f \
\( -name 'oggca.sh' -o -name 'oggca' \) \
-print 2>/dev/null
```

---

# 7. unixODBC Prerequisites

Check whether unixODBC packages are installed:

```bash
rpm -q unixODBC unixODBC-devel
```

Check tools:

```bash
which odbcinst
which isql
```

Enable Oracle Linux 9 CodeReady Builder when `unixODBC-devel` is unavailable:

```bash
sudo dnf config-manager --enable ol9_codeready_builder
```

Verify repository:

```bash
dnf repolist | grep codeready
```

Install prerequisites:

```bash
sudo dnf install -y unixODBC unixODBC-devel
```

Revalidate:

```bash
rpm -q unixODBC unixODBC-devel
which odbcinst
which isql
```

---

# 8. SQL Server ODBC Configuration

Bundled ODBC directory:

```text
/u01/ogg26ai_mssql_home/msodbc
```

Files observed:

```text
lib64/libmsodbcsql.so
odbcinst.ini
mssql_odbcini_template.ini
```

Create working `odbc.ini`:

```bash
cp /u01/ogg26ai_mssql_home/msodbc/mssql_odbcini_template.ini \
   /u01/ogg26ai_mssql_home/msodbc/odbc.ini
```

Back up before editing:

```bash
cp /u01/ogg26ai_mssql_home/msodbc/odbc.ini \
   /u01/ogg26ai_mssql_home/msodbc/odbc.ini.template.bak
```

Implemented DSN:

```ini
[SQL_TGT]
Driver = Microsoft ODBC Driver for SQL Server
Server = tcp:10.60.20.4,1433
Database = OGGTargetDB
Encrypt = yes
TrustServerCertificate = yes
```

Environment variables used for MSSQL GoldenGate:

```bash
export OGG_HOME=/u01/ogg26ai_mssql_home
export ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc
export ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini
export LD_LIBRARY_PATH=/u01/ogg26ai_mssql_home/msodbc/lib64:/u01/ogg26ai_mssql_home/lib/instantclient:/u01/ogg26ai_mssql_home/lib
```

Clear Oracle-deployment-specific variables when launching MSSQL OGGCA from the same shell:

```bash
unset OGG_DEPLOY
unset OGG_ETC_HOME
unset OGG_VAR_HOME
unset TNS_ADMIN
```

Verify environment:

```bash
env | grep -E '^(OGG_HOME|ODBCSYSINI|ODBCINI|LD_LIBRARY_PATH)='
```

ODBC subsystem validation:

```bash
ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc \
ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini \
odbcinst -j
```

Driver query:

```bash
ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc \
ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini \
odbcinst -q -d
```

DSN query:

```bash
ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc \
ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini \
odbcinst -q -s
```

Password-safe SQL Server login test:

```bash
read -s -p "SQL Server password: " PW
echo
```

```bash
ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc \
ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini \
isql -v SQL_TGT ogg_repl "$PW"
```

Inside `isql`:

```sql
SELECT DB_NAME();
```

Expected database:

```text
OGGTargetDB
```

Exit and clear password variable:

```text
quit
```

```bash
unset PW
```

---

# 9. MSSQL GoldenGate Deployment — OGGCA

Dedicated SQL Server GoldenGate paths:

```text
Software home:    /u01/ogg26ai_mssql_home
Service Manager:  /u01/ogg26ai_mssql_deploy
Deployment home:  /u01/ogg26ai_mssql_sm
Deployment name:  MSSQLDEP
```

Ports:

```text
9021  Service Manager
9022  Administration Server
9023  Distribution Server
9024  Receiver Server
9025  Performance Metrics Server
```

Create required top-level directories when permissions prevent OGGCA from writing under `/u01`:

```bash
sudo mkdir -p /u01/ogg26ai_mssql_deploy
sudo mkdir -p /u01/ogg26ai_mssql_sm
sudo chown -R azureuser:azureuser /u01/ogg26ai_mssql_deploy
sudo chown -R azureuser:azureuser /u01/ogg26ai_mssql_sm
```

Check port availability before deployment creation:

```bash
sudo ss -lntp | grep -E ':(9021|9022|9023|9024|9025)\b'
```

Launch GUI OGGCA from the MSSQL environment:

```bash
export OGG_HOME=/u01/ogg26ai_mssql_home
export ODBCSYSINI=/u01/ogg26ai_mssql_home/msodbc
export ODBCINI=/u01/ogg26ai_mssql_home/msodbc/odbc.ini
export LD_LIBRARY_PATH=/u01/ogg26ai_mssql_home/msodbc/lib64:/u01/ogg26ai_mssql_home/lib/instantclient:/u01/ogg26ai_mssql_home/lib

/u01/ogg26ai_mssql_home/bin/oggca.sh
```

Implemented OGGCA environment variables:

```text
OGG_HOME=/u01/ogg26ai_mssql_home
ODBCSYSINI=${OGG_HOME}/msodbc
ODBCINI=${OGG_HOME}/msodbc/odbc.ini
LD_LIBRARY_PATH=${OGG_HOME}/msodbc/lib64:${OGG_HOME}/lib/instantclient:${OGG_HOME}/lib
```

Replication schema entered during MSSQL deployment configuration:

```text
ogg_repl
```

Verify the new deployment services:

```bash
ps -ef | grep -E 'ServiceManager|adminsrvr|distsrvr|recvsrvr|pmsrvr' | grep -v grep
```

Verify ports:

```bash
ss -lntp | grep -E ':(9021|9022|9023|9024|9025)\b'
```

---

# 10. Linux firewalld — GoldenGate Management Ports

Check firewall state:

```bash
sudo firewall-cmd --state
```

List open ports:

```bash
sudo firewall-cmd --list-ports
```

List services:

```bash
sudo firewall-cmd --list-services
```

The old Oracle management ports were already present:

```text
9011/tcp 9012/tcp
```

Open only the MSSQL Administration Server port needed for browser administration:

```bash
sudo firewall-cmd --permanent --add-port=9022/tcp
```

Reload:

```bash
sudo firewall-cmd --reload
```

Verify:

```bash
sudo firewall-cmd --list-ports
```

Expected lab result:

```text
9011/tcp 9012/tcp 9022/tcp
```

---

# 11. GoldenGate MSSQL Web-Service Validation

Local HEAD request used during troubleshooting:

```bash
curl -I --max-time 5 http://127.0.0.1:9022/
```

A `405 Method Not Allowed` on `HEAD` still proved that the service was responding.

Private-interface GET request:

```bash
curl -v --max-time 10 http://10.60.30.4:9022/
```

Successful result observed:

```text
HTTP/1.1 200 OK
```

This isolated public-browser access failures to Azure NSG/firewalld rather than GoldenGate itself.

---

# 12. Azure NSG Rule Pattern for MSSQL GoldenGate Admin UI

The implemented rule was source-restricted and destination-restricted.

Pattern:

```text
Source:              IP Addresses
Source CIDR:         <CURRENT-ADMIN-IP>/32
Source port:         *
Destination:         IP Addresses
Destination CIDR:    10.60.30.4/32
Destination port:    9022
Protocol:            TCP
Action:              Allow
Priority:            320
Name:                Allow-OGG-MSSQL-Admin-From-Home
```

Do not commit a changing residential/public administrator IP into reusable scripts; substitute it at execution time.

---

# 13. GoldenGate SQL_TGT DB Connection

GoldenGate DB Connection values used in `MSSQLDEP`:

```text
Credential Domain:  OracleGoldenGate
Credential Alias:   SQL_TGT
Connection Type:    Data Source Name (DSN)
Data Source Name:   SQL_TGT
User ID:            ogg_repl
Password:           <NOT STORED>
```

Do not use:

```text
ogg_repl@OGGTargetDB
```

as the User ID entry. The target database is already defined in the `SQL_TGT` DSN.

After successful connection, the GoldenGate UI exposed:

```text
Checkpoint
Trandata
Heartbeat
```

---

# 14. GoldenGate Checkpoint Table

Checkpoint table created in SQL Server target database:

```text
ogg_repl.ggs_checkpoint
```

This is the checkpoint table to select when configuring the SQL Server Replicat.

---

# 15. Current Replicat Configuration — REPSQL

Replicat selected:

```text
Type:         Classic Replicat
Process Name: REPSQL
Description:  Oracle HOLA.FOX to SQL Server HOLA.FOX
```

Target connection:

```text
Credential Domain: OracleGoldenGate
Credential Alias:  SQL_TGT
```

Checkpoint table:

```text
ogg_repl.ggs_checkpoint
```

Source trail currently associated with Oracle Extract:

```text
./dirdat/ea
```

Replicat mapping goal:

```text
Oracle HOLA.FOX
        ->
SQL Server HOLA.FOX
```

Expected MAP/TARGET syntax when the Replicat parameter page is reached:

```text
MAP HOLA.FOX, TARGET HOLA.FOX;
```

Do not treat the replication project as complete until `REPSQL` is created, started, and INSERT/UPDATE/DELETE delivery is validated end-to-end.

---

# 16. Useful General Troubleshooting Commands Recovered from the Lab

Search GoldenGate logs/files by modification time:

```bash
find /u01/ogg26ai_deploy/var/log -type f \
-printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n'
```

Inspect response-file active values:

```bash
grep -Ev '^[[:space:]]*(#|$)' <response-file>
```

Search installer metadata for MSSQL install type:

```bash
grep -Ri "INSTALL_OPTION" . | grep -Ei 'mssql|sql|install_option' | head -40
grep -Ri "MSSQL" . | head -40
```

Find relevant runtime components:

```bash
find /u01/ogg26ai_mssql_home -type f \
\( -name 'oggca.sh' -o -name 'oggca' \) \
-print 2>/dev/null
```

Check a Linux user's groups:

```bash
id azureuser
```

Check directory ownership:

```bash
ls -ld /u01/ogg26ai_mssql_home
ls -ld /u01/ogg26ai_mssql_deploy /u01/ogg26ai_mssql_sm
```

---

# 17. Commands Intentionally Not Preserved with Real Values

The following should never be committed with live values:

```text
SQL Server passwords
GoldenGate administrator passwords
Private SSH keys
VPN pre-shared keys
OCI/Azure secrets
Current residential/public management IPs
Any credential-store secret
```

Use placeholders such as:

```text
<STRONG-LAB-PASSWORD>
<CURRENT-ADMIN-IP>/32
<SECRET-NOT-STORED>
```

---

# 18. Recovery Status

This file is a recovered command reference assembled from the lab work already performed and documented. It is intentionally independent of the existing repository documentation.

Recovered areas include:

- Oracle source capture checks and GoldenGate transaction logging commands
- SQL Server target login/user/schema/role SQL
- GoldenGate hub-to-SQL Server connectivity tests
- MSSQL GoldenGate Linux media validation
- MSSQL GoldenGate software installation
- unixODBC installation
- ODBC DSN setup and testing
- OGGCA MSSQL deployment configuration
- MSSQL deployment service/port checks
- firewalld troubleshooting
- Azure NSG rule pattern
- `SQL_TGT` creation parameters
- checkpoint table naming
- current `REPSQL` configuration baseline

This file should continue to receive important reproducible syntax as the remaining replication, validation, failure/recovery, restart, reconciliation, and AWS PostgreSQL phases are completed.
