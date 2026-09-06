# Enterprise Multi-Cloud Database Platform Lab

## Overview

This project is a hands-on multi-cloud database engineering lab designed to build and demonstrate practical experience with heterogeneous database migration, Change Data Capture (CDC), database administration, cloud infrastructure, security, automation, monitoring, and production-style troubleshooting across Oracle Cloud Infrastructure (OCI), Microsoft Azure, and Amazon Web Services (AWS).

## Target Architecture

OCI Oracle Database  
↓ Oracle GoldenGate / CDC  
Azure SQL Server  
↓ AWS DMS / CDC  
AWS PostgreSQL on EC2  
↓ Migration & Managed-Service Comparison  
Amazon RDS for PostgreSQL

## Project Objectives

- Build a secure multi-cloud database architecture across OCI, Azure, and AWS.
- Administer Oracle, Microsoft SQL Server, and PostgreSQL platforms.
- Implement heterogeneous database migration and CDC.
- Perform schema and datatype conversion between different database engines.
- Validate data consistency and replication health.
- Design migration cutover and rollback procedures.
- Implement monitoring, backup/recovery, security, and operational controls.
- Practice production incident troubleshooting and root-cause analysis.
- Automate repeatable database and infrastructure operations.
- Compare self-managed and managed database platforms.

## Project Phases

### Phase 1 — Azure Foundation

- Azure subscription and cost controls
- Resource Groups
- Virtual Networks and subnets
- Network Security Groups
- Identity and RBAC
- Windows Server VM
- Storage and managed disks
- Azure Monitor
- Network connectivity validation

### Phase 2 — SQL Server DBA Foundation

- SQL Server installation and configuration
- Instance and database architecture
- System databases
- MDF, NDF, and LDF files
- Filegroups
- Authentication, users, and roles
- Backup and recovery
- Recovery models
- SQL Server Agent
- Indexes and execution plans
- DMVs and Query Store
- Performance monitoring and troubleshooting

### Phase 3 — OCI Oracle to Azure SQL Server

Implement heterogeneous migration and CDC using Oracle GoldenGate.

- Validate OCI Oracle source
- Establish OCI-to-Azure connectivity
- Configure Oracle source requirements
- Supplemental logging
- Schema conversion
- Datatype mapping
- Initial data load
- GoldenGate Extract
- Trail management
- Replicat
- CDC
- Replication monitoring
- Data reconciliation
- Cutover and rollback testing

### Phase 4 — PostgreSQL DBA Foundation on AWS EC2

- Deploy Linux EC2 instance
- Install and configure PostgreSQL
- PostgreSQL cluster architecture
- Databases and schemas
- Roles and privileges
- postgresql.conf
- pg_hba.conf
- WAL
- MVCC
- VACUUM and autovacuum
- Backup and recovery
- Indexes
- EXPLAIN / EXPLAIN ANALYZE
- Logging and performance monitoring

### Phase 5 — Azure SQL Server to AWS PostgreSQL

Implement heterogeneous migration using AWS Database Migration Service (DMS).

- Configure SQL Server source
- Configure PostgreSQL target
- Establish cross-cloud connectivity
- Schema conversion
- Datatype mapping
- Initial/full load
- CDC
- DMS task monitoring
- Replication latency troubleshooting
- Data validation
- Cutover and rollback

### Phase 6 — PostgreSQL EC2 to Amazon RDS

Migrate PostgreSQL from a self-managed EC2 deployment to Amazon RDS for PostgreSQL.

Compare:

- Administrative control
- OS access
- Configuration management
- Backup and recovery
- Patching
- Monitoring
- Security
- Availability
- Operational overhead
- Cost

### Phase 7 — Production Failure Testing

Simulate and troubleshoot:

- Replication failures
- Network interruptions
- GoldenGate process failures
- AWS DMS task failures
- Replication lag
- Authentication failures
- Schema mismatches
- Datatype conversion failures
- Storage pressure
- Target database outages

Troubleshooting methodology:

**Detect → Collect Evidence → Isolate Failure Domain → Root Cause → Remediate → Validate → Document RCA**

### Phase 8 — Security, Governance and Resilience

- IAM and RBAC
- Least privilege
- Network segmentation
- Encryption at rest
- TLS encryption in transit
- Secrets management
- Database auditing
- Backup validation
- RPO/RTO
- Disaster recovery considerations
- Change management
- Logging and evidence collection

### Phase 9 — Automation and Infrastructure as Code

Technologies:

- Bash
- PowerShell
- Python
- Azure CLI
- AWS CLI
- Terraform

Automation targets include infrastructure provisioning, database health checks, backup validation, replication monitoring, capacity monitoring, and connectivity testing.

### Phase 10 — Architecture Review

Compare Oracle OCI, Azure SQL Server, PostgreSQL EC2, and Amazon RDS PostgreSQL across:

- Architecture
- Availability
- Recoverability
- Performance
- Security
- Administration
- Automation
- Migration complexity
- Operational responsibility
- Cost
- Managed vs. self-managed database services

## Current Status

**Active Workstream:** Phase 3 — OCI Oracle to Azure SQL Server, with SQL Server DBA foundation work continuing in parallel.

### Completed — Azure Foundation

- Azure subscription and cost controls configured.
- Resource group created: `rg-enterprise-data-platform-lab`.
- Azure VNet created: `vnet-enterprise-data-platform-lab` (`10.60.0.0/16`).
- Subnets configured:
  - Management: `10.60.10.0/24`
  - Database: `10.60.20.0/24`
  - GoldenGate: `10.60.30.0/24`
  - GatewaySubnet: `10.60.254.0/27`
- Cross-cloud CIDR plan validated to avoid overlap:
  - OCI: `10.50.0.0/16`
  - Azure: `10.60.0.0/16`
  - AWS: `10.70.0.0/16`
- OCI-to-Azure site-to-site connectivity established using route-based IPsec/IKEv2 and BGP.
- VPN troubleshooting performed using Azure Network Watcher.
- Pre-shared-key mismatch identified and corrected.
- IKE/IPsec connectivity validated.

### Completed — Oracle GoldenGate 26ai on Azure

- Dedicated Oracle GoldenGate 26ai Microservices VM deployed in Azure.
- GoldenGate binary version validated: `23.26.1.0.0`.
- Oracle GoldenGate home: `/u01/ogg26ai_home`.
- Deployment home: `/u01/ogg26ai_deploy`.
- GoldenGate deployment created: `DEP1`.
- GoldenGate Service Manager registered as a Linux `systemd` service.
- GoldenGate Microservices validated:

| Service | Port | Status |
|---|---:|---|
| Service Manager | 9011 | Running |
| Administration Service | 9012 | Running |
| Distribution Service | 9013 | Running |
| Receiver Service | 9014 | Running |
| Performance Metrics Service | 9015 | Running |

- GoldenGate Service Manager web interface validated from an authorized remote workstation.
- Oracle Linux `firewalld` configured for controlled GoldenGate management access.
- Azure NSG access restricted to the administrator source IP rather than broad Internet exposure.

## Troubleshooting Case Study — OGGCA Deployment Stop Failure

### Incident

During Oracle GoldenGate Configuration Assistant (OGGCA) configuration, deployment validation failed because `DEP1` was still reported as running after a stop request.

```text
Verification failed.
Expected value: (NOT) 'running'
actual value: 'running'

Verification failed for REST call to:
/services/v2/deployments/DEP1
```

### Symptoms and Evidence

OGGCA issued the deployment stop request, but validation failed. Process and socket inspection showed that Service Manager could stop while the deployment Microservices remained active:

```text
adminsrvr
distsrvr
recvsrvr
pmsrvr
```

The services continued listening on ports `9012-9015` and were observed with `PPID 1`, indicating that they were no longer children of the active Service Manager process.

Evidence collection included:

- `systemctl status OracleGoldenGate`
- `ps -ef`
- process parent IDs
- `/proc/<PID>/cgroup`
- `ss -lntp`
- OGGCA configuration logs
- GoldenGate REST responses
- Admin Client service status

### Failure-Domain Isolation

The investigation followed the lab's production-style troubleshooting methodology:

**Detect → Collect Evidence → Isolate Failure Domain → Root Cause → Remediate → Validate → Document RCA**

The failure was isolated to deployment lifecycle control: the deployment services had remained alive independently after Service Manager shutdown, causing OGGCA's stopped-state verification to fail.

### Remediation

Service Manager was brought up and `DEP1` was controlled through GoldenGate Admin Client:

```text
CONNECT http://127.0.0.1:9011 DEPLOYMENT DEP1 AS oggadmin
```

The controlled shutdown sequence was:

```text
STOP ER *
STOP DISTPATH ALL
STOP SERVICE *
STATUS SERVICE *
```

At this stage there were no Extract or Replicat groups and no Distribution Paths configured. The deployment Microservices were successfully stopped and verified.

Service Manager was then stopped cleanly:

```bash
sudo systemctl stop OracleGoldenGate
```

OS-level validation confirmed that Service Manager and all four deployment services were down and ports `9011-9015` were closed.

### Resolution

OGGCA was rerun after the controlled shutdown. All configuration actions completed successfully, including the operation that had previously failed:

```text
Start Service Manager                         Succeeded
Verify Service Manager                        Succeeded
Add Service Manager Administrator User        Succeeded
Install Plugin Service in Service Manager     Succeeded
Create Deployment                             Succeeded
Verify Deployment                             Succeeded
Stop Deployment                               Succeeded
Register Service Manager as a system service  Succeeded
```

After configuration, GoldenGate restarted in a healthy managed state. The deployment Microservices were verified as child processes of the active Service Manager process rather than detached processes under PID 1.

## Troubleshooting Case Study — GoldenGate Web Access

### Initial Condition

GoldenGate responded successfully from the VM itself:

```text
9011 HTTP=200
9012 HTTP=200
```

but remote browser access initially failed.

The network path was isolated as:

```text
Administrator Workstation
        ↓
Azure Public IP
        ↓
Azure Network Security Group
        ↓
Oracle Linux firewalld
        ↓
GoldenGate Service Manager / Administration Service
```

### Linux Firewall Remediation

The active `firewalld` zone was `public`. Controlled access was enabled for the management interfaces:

```bash
sudo firewall-cmd --permanent --zone=public --add-port=9011/tcp
sudo firewall-cmd --permanent --zone=public --add-port=9012/tcp
sudo firewall-cmd --reload
```

### Azure NSG Remediation

An Azure inbound NSG rule was configured for TCP ports `9011-9012`, restricted to the administrator's current public source IP using a `/32` rule. The GoldenGate management ports were not opened broadly to `0.0.0.0/0`.

Remote Service Manager access was then successfully validated.

> **Security note:** Current HTTP access proves connectivity and management functionality. TLS/HTTPS remains a hardening task before treating the management plane as production-like.

## Current GoldenGate Architecture

```text
Azure GoldenGate VM

Service Manager :9011
       |
       +-- DEP1
            |
            +-- Administration Service   :9012
            +-- Distribution Service     :9013
            +-- Receiver Service         :9014
            +-- Performance Metrics      :9015
```

### Current GoldenGate Validation State

```text
Service Manager        RUNNING
Administration Service RUNNING
Distribution Service   RUNNING
Receiver Service       RUNNING
Performance Metrics    RUNNING
```

The GoldenGate Service Manager web interface has been successfully validated.

## Next Steps

1. Validate the OCI Oracle source database for GoldenGate capture.
2. Confirm source database supplemental logging requirements.
3. Create GoldenGate database credentials and credential-store entries.
4. Validate Oracle source connectivity from the Azure GoldenGate hub.
5. Configure source Extract.
6. Configure trail files.
7. Continue Azure SQL Server target preparation and DBA foundation work.
8. Perform Oracle-to-SQL Server schema and datatype mapping.
9. Configure target Replicat.
10. Begin initial-load and CDC validation.
11. Configure TLS/HTTPS for the GoldenGate management plane.
12. Continue documenting validation evidence, troubleshooting cases, migration runbooks, and rollback procedures.

---

This repository will be updated incrementally with architecture diagrams, implementation procedures, commands, validation evidence, troubleshooting scenarios, migration runbooks, rollback procedures, automation, and lessons learned as the project progresses.
