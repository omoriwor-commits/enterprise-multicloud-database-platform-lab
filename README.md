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

Detect → Collect Evidence → Isolate Failure Domain → Root Cause → Remediate → Validate → Document RCA

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

**Current Phase:** Phase 1 — Azure Foundation

### Next Steps

1. Configure Azure subscription and cost controls.
2. Create the Azure Resource Group.
3. Design the VNet and subnet architecture.
4. Configure Network Security Groups.
5. Deploy the Windows Server / SQL Server environment.
6. Validate networking, security, storage, and connectivity.
7. Begin SQL Server DBA administration exercises.

---

This repository will be updated incrementally with architecture diagrams, implementation procedures, commands, validation evidence, troubleshooting scenarios, migration runbooks, rollback procedures, automation, and lessons learned as the project progresses.
