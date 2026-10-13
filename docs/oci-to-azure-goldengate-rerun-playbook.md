# OCI Oracle 26ai → Azure SQL Server 2022: GoldenGate Rerun Playbook

**Implementation history:** The original OCI-to-Azure implementation is reported complete by the project owner. The dated September 2026 checkpoint documents connectivity, source capture, trails and Replicat preparation, not the final target-apply evidence. This playbook is for reproducing the deployment, collecting new outputs and making any differences explicit.

## 1. Scope and recorded topology

- **Source:** OCI Compute VM, self-managed Oracle AI Database 26ai, Oracle Linux 9.8; CDB `CDB23AI`, PDB `PDB23AI`, listener TCP 1521.
- **Network:** OCI VCN `10.50.0.0/16` ↔ Azure VNet `10.60.0.0/16`, route-based IKEv2/IPsec VPN with BGP.
- **GoldenGate hub:** Azure Oracle Linux 9.8 VM `vm-goldengate-lab-01` in `10.60.30.0/24`.
- **Oracle GG runtime:** `DEP1` on Oracle GoldenGate 26ai; Extract `EXTORA`; local trail prefix `ea`; Administration port 9012.
- **SQL Server GG runtime:** `MSSQLDEP` on hub, SQL Server-target distribution; Administration port 9022; Replicat planned/previously named `REPSQL`.
- **Target:** Azure Windows Server 2022, SQL Server 2022 Developer, database `OGGTargetDB`, schema/table `HOLA.FOX`, TCP 1433, private SQL VM subnet `10.60.20.0/24`.
- **SQL target connectivity:** DSN `SQL_TGT`, checkpoint table `ogg_repl.ggs_checkpoint`.

Do **not** transplant the recorded IP addresses, users, process names, wallet contents, or deployment home directories without reconciling them with the new environment. The September checkpoint contains historical details only.

## 2. Sequence and checkpoints

| Phase | Action | Required gate before advancing |
|---|---|---|
| A | OCI and Azure infrastructure | Confirm approved compartments/subscriptions, region, quotas, budgets and private connectivity |
| B | VPN and BGP | Tunnels established, correct routes both directions, only required ports accessible |
| C | Oracle and SQL target readiness | Database services healthy, source supplemental logging and privileges verified, SQL Server target schema ready |
| D | GoldenGate runtimes | Oracle and MSSQL software homes/deployments healthy; correctly scoped credentials and service endpoints |
| E | Initial-load decision | Source-consistent target baseline and approved SCN/CSN instantiation boundary established |
| F | Oracle Integrated Extract | Capture registered, source trail receiving changes, parameter/report checks pass |
| G | Trail delivery and SQL Server Replicat | Distribution/Receiver trail paths verified; target Replicat is configured, started and checkpointing |
| H | CDC/DDL acceptance | Target rows and supported object changes are validated, not inferred from RUNNING status |
| I | Recovery and handover | Restart/catch-up tests, reconciliation, cleanup and final evidence committed |

## 3. Preflight commands — read only

On each Oracle host:

~~~bash
hostnamectl
cat /etc/oracle-release
df -h
ip -brief address
ip route
~~~

On OCI Oracle SQL*Plus as an authorized account:

~~~sql
SELECT banner_full FROM v$version;
SELECT name, open_mode, database_role, log_mode, force_logging FROM v$database;
SELECT con_id, name, open_mode FROM v$pdbs;
SHOW PARAMETER enable_goldengate_replication
SELECT supplemental_log_data_min FROM v$database;
SELECT current_scn FROM v$database;
~~~

Record the execution timestamp and active container. Some queries require CDB/root privileges. **The current SCN query is inventory only; it is not a safe or sufficient initial-load instantiation boundary.**

Network controls must permit precisely scoped TCP 1521 (hub→Oracle), TCP 1433 (hub→SQL Server), necessary GoldenGate endpoint ports, and routing/NAT as required. Do not expose listener ports or GG Admin services broadly to the Internet.

~~~bash
# From the GG hub; use actual private IPs/FQDNs.
nc -vz <OCI_ORACLE_PRIVATE_IP> 1521
nc -vz <AZURE_SQL_PRIVATE_IP> 1433
~~~

Also validate BGP learned prefixes and IPsec security-association state in both cloud consoles; open TCP does not alone prove route resilience.

## 4. Source database and GoldenGate preparation

Use Oracle's **26ai** database privileges, database registration requirements, supplemental logging rules, container-specific capture topology and Oracle GoldenGate 26ai documented procedures. Do not copy Oracle 19c grant syntax to 26ai indiscriminately.

Record:

~~~text
CDB / PDB / database unique name:
Extract account and privilege verification:
Source tables and keys:
TRANDATA / supplemental logging verification:
Integrated Extract registration:
Extract parameter file (redacted):
Trail prefix and physical deployment trail directory:
INFO EXTRACT / report / checkpoint:
~~~

Typical inspection using Admin Client after authenticating to the correct Oracle deployment:

~~~text
INFO EXTRACT EXTORA, DETAIL
STATS EXTRACT EXTORA
VIEW REPORT EXTORA
~~~

Collect real reports. Do not recreate or reposition an existing Extract at an arbitrary SCN to “fix” lag.

## 5. RMAN / Data Pump and baseline synchronization

**RMAN and Data Pump were used for initial-load work in the local Oracle 26ai→OCI project**, confirmed by the project owner. Do not assume the identical tools or sequence apply automatically to heterogeneous **Oracle→SQL Server** loading. Select a SQL Server-compatible baseline method for the Azure target and reconcile datatype mapping, schema, constraints and identity/LOB handling.

Before starting Replicat on an existing target:

1. Identify supported consistent source snapshot/export method and record its transaction boundary.
2. Load the SQL Server baseline using the actual validated heterogeneous migration approach.
3. Check primary keys, table structure, row counts, representative data and source/target datatype conversions.
4. Determine the supported GoldenGate instantiation/start position using release-specific documentation and the recorded baseline boundaries.
5. Confirm that no changes will be skipped or replayed twice.

**Never use `BEGIN NOW`, `ATCSN`, or `AFTERCSN` blindly after importing populated target data.** Record the exact instantiation procedure and verify its Oracle and SQL Server applicability.

## 6. Trail shipping and SQL Server Replicat

Prior environment details are useful signposts, not guaranteed reusable configuration:

~~~text
Oracle deployment: DEP1
Extract: EXTORA
Source trail: ea (historical file representation ./dirdat/ea)
SQL Server deployment: MSSQLDEP
DSN: SQL_TGT
Target database: OGGTargetDB
Source/target: HOLA.FOX
Target Replicat: REPSQL
Checkpoint: ogg_repl.ggs_checkpoint
~~~

Verify the **current** Microservices deployment trail paths and the Distribution/Receiver route. A source `ea` trail prefix may not be the same as the Receiver's destination trail prefix; capture both actual locations. Check supported Oracle-to-SQL Server delivery/Replicat mode and its required SQL Server driver, credentials, tables, trail compatibility, mapping and checkpoint setup using release-specific documentation.

On the **SQL Server GG deployment** through Admin Client:

~~~text
INFO REPLICAT REPSQL, DETAIL
STATS REPLICAT REPSQL
VIEW REPORT REPSQL
~~~

If REPSQL has not yet been created in the rebuilt environment, use the supported `ADD REPLICAT` syntax for that exact GoldenGate version, target, deployment and instantiation position. Do not copy a command from the Oracle Integrated Replicat procedure into the SQL Server deployment.

## 7. CDC acceptance: target-side proof

Use isolated, nonproduction test rows with a unique run identifier. Commit one change at a time, record timestamps, and check both source and target.

| Operation | Required evidence |
|---|---|
| INSERT | New keyed row appears at SQL Server target with matching mapped values |
| UPDATE | Same keyed row receives the expected new values |
| DELETE | Keyed row removed from target and transaction recorded at source |
| DROP (DDL) | Only if this exact Oracle→SQL Server path supports and is configured for the intended DDL; verify target metadata, not just Oracle execution |

A successfully executed DROP on Oracle **does not prove** GoldenGate replicated that DDL to SQL Server. If heterogeneous DDL propagation is unsupported or excluded by the configuration, document the separate target schema change procedure rather than claim automated DDL replication.

At each gate, capture Extract/Replicat reports, checkpoints, source and target SQL results, row reconciliation, any conflicts, and real measured end-to-end lag. Then stop/start Replicat under change control and prove that recovery does not lose or duplicate committed changes.

## 8. Troubleshooting quick index

| Symptom | Investigate |
|---|---|
| VPN/BGP fails | IKE/IPsec parameters, PSK, advertised prefixes, route tables and Azure/OCI gateways |
| Source stops advancing | ARCHIVELOG/FRA capacity, Extract report, DB connectivity, trail storage |
| Target SQL connection fails | `SQL_TGT` ODBC DSN, Microsoft driver, TCP 1433, service permissions and TLS |
| SQL GG deployment fails | Installed platform package, service manager/OGGCA state, `ODBCSYSINI`, environment isolation |
| Trail not delivered | Distribution path auth, Receiver service, trail target location, firewall |
| Replicat abends | Report/discard files, SQL Server constraint/key or mapping error, unsupported datatype, checkpoint position |
| Rows diverge | Instantiation/CSN boundary, transformations, ignored errors, collisions, missed DML or unsupported DDL |

Relevant historical evidence: [project history](project-history-and-troubleshooting.md), [September 7 checkpoint](checkpoints/2026-09-07-oracle-to-sqlserver-cdc-progress.md), [September 9 checkpoint](checkpoints/2026-09-09-oracle-to-sqlserver-replicat-prep.md).

## 9. Evidence package after rerun

Place sanitized real artifacts under a new dated folder, e.g. `evidence/YYYY-MM-DD-oci-azure-rerun/`:

~~~text
README.md                # run ID, architecture, actual success/failure gates
inventory.md             # versions, CDB/PDB, network and deployment names
network-validation.md    # VPN/BGP, route checks, tested ports
baseline.md              # loading method and supported instantiation boundary
extract-validation.md    # Extract report/lag/sequence
replicat-validation.md   # Replicat status, checkpoint, report
dml-validation.md        # INSERT UPDATE DELETE source + SQL Server target
ddl-validation.md        # supported DDL behavior and observed outcome
recovery-validation.md   # stop/start/catch-up results
issues.md                # failures, investigation and resolutions
~~~

Never commit passwords, wallet files, client private keys, real customer data or unredacted endpoint secrets.

## Documentation

- [GoldenGate 26ai core docs](https://docs.oracle.com/en/database/goldengate/core/26/coredoc/index.html)
- [GoldenGate 26ai command reference](https://docs.oracle.com/en/database/goldengate/core/26/gclir/index.html)
- [OCI VCN field guide](https://github.com/omoriwor-commits/DovOps_T/blob/main/OCI/engineering/01-vcn-public-private-subnets-internet-nat-gateways.md)
