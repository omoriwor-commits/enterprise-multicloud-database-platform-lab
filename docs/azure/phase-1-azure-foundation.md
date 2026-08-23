# Enterprise Data Platform Lab — Azure Build Progress

**Checkpoint Date:** August 22, 2026
**Project:** Enterprise Data Platform / Cross-Cloud Migration Lab

## 1. Target Architecture

```text
OCI
Oracle Database
10.50.0.0/16
      |
      |  Cross-cloud connectivity
      v
Azure
SQL Server Platform
10.60.0.0/16
      |
      |  Later migration / replication
      v
AWS
PostgreSQL Platform
10.70.0.0/16
```

Future Oracle GoldenGate will be incorporated as the CDC / replication layer.

---

## 2. OCI Source Environment

### OCI Compute

* Instance: `rotez_instance_oci`
* Region: `us-chicago-1`
* Availability Domain: `AD-1`
* Fault Domain: `FD-2`
* OS: Oracle Linux 9
* Image: Oracle Linux 9.8
* Shape: `VM.Standard.E5.Flex`
* OCPU: `1`
* Memory: `12 GB`
* Public IPv4: `170.9.255.52`
* Private IPv4: `10.50.10.178`

### OCI Network

```text
VCN:
Rotez_hybrid-lab-vcn
10.50.0.0/16

Subnet:
public-subnet-lab
10.50.10.0/24

Oracle VM:
10.50.10.178
```

The OCI subnet is regional and currently public.

The OCI VNIC currently has no Network Security Group attached. Traffic is therefore controlled by the subnet security list plus the Oracle Linux host firewall.

---

## 3. Azure Subscription and Cost Controls

Azure subscription:

```text
Azure subscription 1
```

Status:

```text
Active
```

Azure credits observed:

```text
$200 remaining
```

No Pay-As-You-Go upgrade was performed.

### Budget

Created subscription-level budget:

```text
budget-enterprise-data-platform-lab
```

Monthly budget:

```text
$50
```

Alert thresholds:

| Threshold | Approximate Cost |
| --------- | ---------------: |
| 50%       |           $25.00 |
| 75%       |           $37.50 |
| 90%       |           $45.00 |
| 100%      |           $50.00 |

Budget alerts are based on **Actual Cost**.

Important:

> Azure budgets generate alerts but do not automatically stop resources.

VM shutdown/deallocation and other operational controls will therefore still be required.

---

## 4. Azure Resource Group

Created:

```text
rg-enterprise-data-platform-lab
```

Region:

```text
East US
```

Tags:

```text
Environment = Lab
Project     = EnterpriseDataPlatform
Workload    = CrossCloudMigration
ManagedBy   = Manual
```

---

## 5. Cross-Cloud IP Addressing Standard

The lab now uses deliberately separated private address spaces.

```text
OCI      10.50.0.0/16
Azure    10.60.0.0/16
AWS      10.70.0.0/16
```

This prevents CIDR overlap when VPN/routed connectivity is implemented.

---

## 6. Azure Virtual Network

Successfully deployed:

```text
vnet-enterprise-data-platform-lab
```

Region:

```text
East US
```

Address space:

```text
10.60.0.0/16
```

### Azure Subnets

#### Management

```text
snet-management
10.60.10.0/24
```

Purpose:

* Administration
* Management workloads
* Supporting platform services

#### Database

```text
snet-database
10.60.20.0/24
```

Purpose:

* SQL Server VM
* Database-tier workloads

#### VPN Gateway

```text
GatewaySubnet
10.60.254.0/27
```

Purpose:

* Reserved for future Azure VPN Gateway
* OCI ↔ Azure private connectivity

The Azure VPN Gateway itself has **not** been deployed yet because it is a billable resource.

---

## 7. Azure Network Security Decisions

During VNet creation, the following paid services were intentionally left disabled:

```text
Azure Bastion                 Disabled
Azure Firewall                Disabled
Azure DDoS Network Protection Disabled
```

This preserves Azure trial credits while still allowing security controls to be implemented through:

* Network Security Groups
* Windows Firewall
* SQL Server configuration
* Private subnetting
* VPN routing
* Least-privilege source/destination rules

Broad public database exposure will not be used.

Examples that must be avoided:

```text
0.0.0.0/0 -> TCP 1433
0.0.0.0/0 -> TCP 1521
```

---

## 8. GoldenGate Network Reservation

GoldenGate is planned for a later phase.

If GoldenGate is hosted in Azure, reserve:

```text
snet-goldengate
10.60.30.0/24
```

Planned Azure allocation:

```text
10.60.10.0/24    Management
10.60.20.0/24    SQL Server
10.60.30.0/24    GoldenGate
10.60.254.0/27   VPN Gateway
```

The GoldenGate subnet has **not yet been created**.

Before GoldenGate deployment, determine:

* GoldenGate hosting location
* Static private IP requirements
* Oracle listener connectivity
* SQL Server connectivity
* GoldenGate Microservices ports
* OCI/Azure routing
* NSG rules
* Host firewall rules
* TLS requirements
* Credential management

---

## 9. Current Cross-Cloud Network Map

```text
OCI
Rotez_hybrid-lab-vcn
10.50.0.0/16
│
└── public-subnet-lab
    10.50.10.0/24
    │
    └── rotez_instance_oci
        10.50.10.178
        Oracle Database
            │
            │ Future VPN / routed connectivity
            ▼
Azure
vnet-enterprise-data-platform-lab
10.60.0.0/16
│
├── snet-management
│   10.60.10.0/24
│
├── snet-database
│   10.60.20.0/24
│   └── vm-sqlserver-lab-01
│       Private IP: 10.60.20.4
│       Public IP: 168.62.51.6
│       SQL Server 2022 Developer
│       Windows Server 2022
│       Standard_D2as_v7
│
├── snet-goldengate
│   10.60.30.0/24 [PLANNED]
│
└── GatewaySubnet
    10.60.254.0/27
    └── Azure VPN Gateway [NOT DEPLOYED]

AWS
10.70.0.0/16
└── PostgreSQL [FUTURE PHASE]
```

---

## 10. Current Project Status

### Completed

* [x] Azure subscription verified
* [x] Azure credits verified
* [x] Subscription-level cost budget created
* [x] Budget alerts configured
* [x] Resource group created
* [x] Governance tags applied
* [x] OCI network CIDR documented
* [x] OCI Oracle host private IP documented
* [x] Azure VNet addressing designed
* [x] CIDR overlap avoided
* [x] Azure VNet created
* [x] Management subnet created
* [x] Database subnet created
* [x] GatewaySubnet created
* [x] Paid Azure network services intentionally disabled
* [x] Database NSG created and associated to `snet-database`
* [x] SQL Server VM deployed
* [x] SQL Server 2022 Developer validated as running
* [x] Windows Authentication validated
* [x] SQL Server Authentication validated with `sqladminlab`
* [x] `sqladminlab` verified as `sysadmin`
* [x] MAXDOP configured to `2`
* [x] Max server memory configured to `5120 MB`
* [x] Optimize for ad hoc workloads enabled
* [x] tempdb validated on `H:\tempDb`
* [x] Default user database data path validated as `F:\data\`
* [x] Default user database log path validated as `G:\log\`
* [x] Test database `LabTestDB` created successfully
* [x] `LabTestDB` data file validated on `F:\data\LabTestDB.mdf`
* [x] `LabTestDB` log file validated on `G:\log\LabTestDB_log.ldf`
* [x] VM auto-shutdown enabled for 11:00 PM Central Time

### Not Yet Deployed

* [ ] Azure outbound connectivity design
* [ ] OCI ↔ Azure VPN
* [ ] GoldenGate
* [ ] Oracle → SQL Server migration/CDC
* [ ] AWS PostgreSQL environment
* [ ] Azure → AWS connectivity
* [ ] SQL Server → PostgreSQL migration/replication
* [ ] Monitoring and operational runbooks
* [ ] Backup/recovery validation
* [ ] Cutover/rollback testing

---

## 11. Immediate Next Step

Move into cross-cloud connectivity preparation between OCI and Azure.

Current Azure database-tier controls include:

```text
nsg-database-lab
```

Associated subnet:

```text
snet-database
10.60.20.0/24
```

Validated NSG behavior includes:

* RDP from Azure management subnet `10.60.10.0/24`
* SQL Server TCP `1433` from Azure management subnet `10.60.10.0/24`
* Temporary RDP from the administrator public IP using a `/32` source rule
* Explicit deny rule ahead of broad VNet inbound defaults
* No unrestricted Internet exposure for SQL Server TCP `1433`

Next connectivity work will determine whether to deploy a site-to-site VPN immediately or use a lower-cost interim path while preserving Azure trial credits.

---

## 12. Next Major Phase

```text
OCI ↔ Azure connectivity
 ↓
Oracle → SQL Server migration
 ↓
GoldenGate CDC
 ↓
AWS PostgreSQL
```
