# Enterprise Data Platform Lab — Multi-Cloud Migration & Replication Plan

**Checkpoint Date:** August 23, 2026
**Project:** Enterprise Data Platform / Multi-Cloud Migration & Replication Lab

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
      |
      |  Later expansion / comparison
      v
Google Cloud
PostgreSQL Platform
10.80.0.0/16
```

Oracle GoldenGate will be incorporated as the CDC / replication layer using a dedicated hub architecture.

Primary GoldenGate deployment model selected:

```text
Model 4 — Dedicated hub with remote capture and remote apply
```

The lab will deliberately practice both:

* Unidirectional CDC
* Bidirectional / active-active-style replication patterns
* Failure, restart, lag, conflict, reconciliation, cutover, and rollback scenarios

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
GCP      10.80.0.0/16
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

GoldenGate is planned as a dedicated hub rather than being installed directly on either database server.

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

The GoldenGate subnet has now been created and associated with a dedicated Network Security Group.

Current GoldenGate network objects:

```text
snet-goldengate
10.60.30.0/24

nsg-goldengate-lab
```

The subnet was created as a private subnet with no default outbound access, with no NAT gateway, route table, service endpoint, or subnet delegation configured at creation time.

### Selected GoldenGate Deployment Model

```text
Dedicated hub with remote capture and remote apply
```

Initial topology:

```text
OCI Oracle
    |
    | Remote Capture
    v
GoldenGate Hub
    |
    | Remote Apply
    v
Azure SQL Server
```

After one-way CDC is stable, extend the same topology for bidirectional testing:

```text
OCI Oracle <-> GoldenGate Hub <-> Azure SQL Server
```

This second stage will include deliberate testing of:

* Loop prevention
* Primary-key / identity / sequence collision controls
* Simultaneous DML
* Conflict detection and resolution strategy
* Replication lag
* Extract / Replicat restart and recovery
* Reconciliation after interruption
* Controlled cutover and rollback

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
│   10.60.30.0/24
│   └── nsg-goldengate-lab
│
└── GatewaySubnet
    10.60.254.0/27
    └── Azure VPN Gateway [NOT DEPLOYED]

AWS
10.70.0.0/16
└── PostgreSQL [FUTURE PHASE]

Google Cloud
10.80.0.0/16
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
* [x] `snet-goldengate` created
* [x] GoldenGate subnet CIDR validated as `10.60.30.0/24`
* [x] GoldenGate subnet created as private subnet with no default outbound access
* [x] `nsg-goldengate-lab` created
* [x] `nsg-goldengate-lab` associated to `snet-goldengate`
* [x] Inbound SSH rule created from Azure management subnet to GoldenGate subnet
* [x] Outbound SQL Server rule created from GoldenGate subnet to Azure SQL Server TCP `1433`
* [x] OCI security list ingress rule created from Azure GoldenGate subnet `10.60.30.0/24` to Oracle listener TCP `1521`
* [x] Azure outbound Oracle listener rule created from GoldenGate subnet `10.60.30.0/24` to OCI Oracle `10.50.10.178` on TCP `1521`

### Not Yet Deployed

* [ ] OCI ↔ Azure VPN
* [ ] GoldenGate
* [ ] Dedicated GoldenGate hub compute
* [ ] GoldenGate remote capture from OCI Oracle
* [ ] GoldenGate remote apply to Azure SQL Server
* [ ] Oracle → SQL Server migration/CDC
* [ ] Bidirectional Oracle ↔ SQL Server replication lab
* [ ] Conflict / loop prevention testing
* [ ] Replication failure and restart testing
* [ ] AWS PostgreSQL environment
* [ ] Azure → AWS connectivity
* [ ] SQL Server → PostgreSQL migration/replication
* [ ] Google Cloud PostgreSQL environment
* [ ] Multi-cloud PostgreSQL comparison
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

The GoldenGate subnet and its dedicated NSG are now deployed. The Azure outbound Oracle listener rule from the GoldenGate subnet to the OCI Oracle host on TCP `1521` has also been implemented. The next major step is OCI ↔ Azure routed connectivity / VPN implementation.

OCI-side listener access has now also been implemented in the default security list for `Rotez_hybrid-lab-vcn`:

```text
Source CIDR:       10.60.30.0/24
Protocol:          TCP
Source port:       All
Destination port:  1521
Description:       Allow-Azure-GoldenGate-To-Oracle
```

The matching Azure outbound control has now been implemented from `snet-goldengate` to the OCI Oracle private IP `10.50.10.178` on TCP `1521`.

### OCI Security List Implementation Detail

Navigation used:

```text
OCI Console
-> Networking
-> Virtual Cloud Networks
-> Rotez_hybrid-lab-vcn
-> Security
-> Default Security List for Rotez_hybrid-lab-vcn
-> Security rules
-> Add Ingress Rules
```

Configured rule:

```text
Stateless:              No
Source Type:            CIDR
Source CIDR:            10.60.30.0/24
IP Protocol:            TCP
Source Port Range:      All
Destination Port Range: 1521
Description:            Allow-Azure-GoldenGate-To-Oracle
```

Validation result:

```text
Ingress rule present:
10.60.30.0/24 -> TCP 1521
```

---

## 11A. Step-by-Step Build Record — Azure GoldenGate Network Preparation

This section preserves the exact implementation sequence used in the Azure portal so the environment can be rebuilt later.

### Step 1 — Open the Azure VNet

Navigate to:

```text
Azure Portal
-> Virtual networks
-> vnet-enterprise-data-platform-lab
```

Validated VNet:

```text
Name:          vnet-enterprise-data-platform-lab
Address space: 10.60.0.0/16
Region:        East US
```

Existing subnets before GoldenGate subnet creation:

```text
GatewaySubnet       10.60.254.0/27
snet-management     10.60.10.0/24
snet-database       10.60.20.0/24
```

### Step 2 — Create the GoldenGate subnet

Navigate to:

```text
vnet-enterprise-data-platform-lab
-> Settings
-> Subnets
-> + Subnet
```

Enter:

```text
Subnet purpose:     Default
Name:               snet-goldengate
IPv4 address space: 10.60.0.0/16
Starting address:   10.60.30.0
Size:               /24
```

Azure resolves the subnet range as:

```text
10.60.30.0 - 10.60.30.255
```

Keep:

```text
Private subnet:          Enabled
NAT gateway:             None
Network security group:  None
Route table:             None
Service endpoints:       None
Subnet delegation:       None
```

Click:

```text
Add
```

Validation result:

```text
GatewaySubnet       10.60.254.0/27
snet-management     10.60.10.0/24
snet-database       10.60.20.0/24
snet-goldengate     10.60.30.0/24
```

### Step 3 — Create the GoldenGate Network Security Group

Navigate to:

```text
Azure Portal
-> Network security groups
-> Create
```

Enter:

```text
Subscription:    Azure subscription 1
Resource group:  rg-enterprise-data-platform-lab
Name:            nsg-goldengate-lab
Region:          East US
```

Then:

```text
Review + create
-> Validation passed
-> Create
```

No custom security rules were added during NSG creation.

### Step 4 — Associate the NSG with the GoldenGate subnet

Navigate to:

```text
nsg-goldengate-lab
-> Settings
-> Subnets
-> Associate
```

Select:

```text
Virtual network: vnet-enterprise-data-platform-lab
Subnet:          snet-goldengate
```

Validation:

```text
NSG:      nsg-goldengate-lab
Subnet:   snet-goldengate
CIDR:     10.60.30.0/24
VNet:     vnet-enterprise-data-platform-lab
```

### Step 5 — Create management SSH inbound rule

Purpose:

Allow Linux administration of the future GoldenGate hub only from the Azure management subnet.

Navigate to:

```text
nsg-goldengate-lab
-> Inbound security rules
-> + Add
```

Configure:

```text
Source:                 IP Addresses
Source IP/CIDR:         10.60.10.0/24
Source port ranges:     *
Destination:            IP Addresses
Destination IP/CIDR:    10.60.30.0/24
Service:                Custom
Destination port:       22
Protocol:               TCP
Action:                 Allow
Priority:               100
Name:                   Allow-SSH-From-Management
```

Validated deployed rule:

```text
Priority:     100
Name:         Allow-SSH-From-Management
Port:         22
Protocol:     TCP
Source:       10.60.10.0/24
Destination:  10.60.30.0/24
Action:       Allow
```

### Step 6 — Create outbound SQL Server rule

Purpose:

Allow the GoldenGate hub to connect to the Azure SQL Server listener for remote apply and later reverse-direction testing.

Navigate to:

```text
nsg-goldengate-lab
-> Outbound security rules
-> + Add
```

Configure:

```text
Source:                 IP Addresses
Source IP/CIDR:         10.60.30.0/24
Source port ranges:     *
Destination:            IP Addresses
Destination IP:         10.60.20.4
Service:                Custom
Destination port:       1433
Protocol:               TCP
Action:                 Allow
Priority:               100
Name:                   Allow-SQL-To-AzureDB
```

Validated deployed rule:

```text
Priority:     100
Name:         Allow-SQL-To-AzureDB
Port:         1433
Protocol:     TCP
Source:       10.60.30.0/24
Destination:  10.60.20.4
Action:       Allow
```

### Step 7 — Create GoldenGate to OCI Oracle outbound rule

Navigate to:

```text
nsg-goldengate-lab
-> Outbound security rules
-> + Add
```

Configured:

```text
Source:                 IP Addresses
Source IP/CIDR:         10.60.30.0/24
Source port ranges:     *
Destination:            IP Addresses
Destination IP:         10.50.10.178
Service:                Custom
Destination port:       1521
Protocol:               TCP
Action:                 Allow
Priority:               110
Name:                   Allow-Oracle-To-OCI
```

Purpose:

```text
GoldenGate Hub -> OCI Oracle listener TCP 1521
```

Validated deployed rule:

```text
Priority:     110
Name:         Allow-Oracle-To-OCI
Port:         1521
Protocol:     TCP
Source:       10.60.30.0/24
Destination:  10.50.10.178
Action:       Allow
```

This is the future remote-capture database path. The NSG rule alone does not establish cross-cloud reachability; OCI ↔ Azure routing/VPN, OCI security controls, Oracle listener configuration, and host firewalls must also permit the flow.

### Security principles used during this build

```text
Do not expose TCP 22 to 0.0.0.0/0.
Do not expose SQL Server TCP 1433 to 0.0.0.0/0.
Do not expose Oracle TCP 1521 to 0.0.0.0/0.
Use private CIDRs and least-privilege source/destination rules.
Use the management subnet as the administrative trust boundary.
Keep database and GoldenGate workloads in separate subnets and NSGs.
```

Current GoldenGate network-security state:

```text
Azure Management 10.60.10.0/24
        |
        | TCP 22
        v
GoldenGate subnet 10.60.30.0/24
        |
        | TCP 1433
        v
Azure SQL Server 10.60.20.4

GoldenGate subnet 10.60.30.0/24
        |
        | TCP 1521 over OCI-Azure routed connectivity
        v
OCI Oracle 10.50.10.178
```

---

## 12. Next Major Phase

```text
OCI ↔ Azure connectivity
 ↓
Oracle → SQL Server schema assessment / migration
 ↓
GoldenGate one-way CDC
 ↓
Bidirectional Oracle ↔ SQL Server replication
 ↓
Failure / conflict / restart / reconciliation testing
 ↓
AWS PostgreSQL
 ↓
Google Cloud PostgreSQL
```

---

## 13. Migration and Replication Method

Because Oracle and SQL Server are heterogeneous database platforms, the migration will not use RMAN, Data Guard, or a direct Data Pump restore into SQL Server.

Planned method:

| Phase             | Method                                                                            | Objective                                                 |
| ----------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Assessment        | SQL Server Migration Assistant for Oracle or equivalent schema assessment tooling | Identify datatype, PL/SQL, object, and compatibility gaps |
| Schema conversion | Oracle-to-SQL Server conversion                                                   | Build equivalent SQL Server schema                        |
| Initial load      | Bulk / migration tooling                                                          | Establish synchronized baseline data                      |
| CDC               | Oracle GoldenGate                                                                 | Capture and apply ongoing transactional changes           |
| Validation        | Row counts, object checks, sample reconciliation, transaction testing             | Prove target correctness                                  |
| Cutover           | Controlled write stop, drain replication, final validation                        | Practice near-zero-downtime transition                    |
| Rollback          | Preserve source and reverse operational decision if required                      | Demonstrate recovery discipline                           |

Key datatype / object conversion areas to practice:

```text
Oracle NUMBER      -> SQL Server int / bigint / decimal
Oracle VARCHAR2    -> SQL Server varchar / nvarchar
Oracle DATE        -> SQL Server datetime2
Oracle CLOB        -> SQL Server varchar(max) / nvarchar(max)
Oracle sequences   -> SQL Server sequence / identity strategy
Oracle PL/SQL      -> SQL Server T-SQL redesign where required
```

---

## 14. Hands-On Execution Plan

### Stage 1 — Secure Connectivity

1. Finalize OCI ↔ Azure connectivity design.
2. Configure routes, NSGs / security lists, host firewalls, and listener access.
3. Validate Oracle listener reachability from Azure.
4. Validate SQL Server listener reachability from the GoldenGate / management path.

### Stage 2 — GoldenGate Hub

1. Create `snet-goldengate`.
2. Deploy dedicated GoldenGate hub compute.
3. Install GoldenGate Microservices.
4. Configure secure credentials and service connectivity.
5. Verify remote access to Oracle TCP 1521 and SQL Server TCP 1433.

### Stage 3 — Unidirectional Replication

```text
OCI Oracle -> Azure SQL Server
```

Practice:

* Schema assessment and conversion
* Initial data load
* Remote capture
* Remote apply
* INSERT / UPDATE / DELETE replication
* Checkpoint and lag monitoring
* Process stop / start
* Failure recovery
* Data reconciliation
* Cutover and rollback drill

### Stage 4 — Bidirectional Replication

```text
OCI Oracle <-> Azure SQL Server
```

Practice:

* Capture and apply in both directions
* Loop prevention
* Key / sequence / identity strategy
* Simultaneous updates
* Conflict scenarios
* Conflict-resolution rules
* Restart after outage
* Reconciliation after divergence
* Controlled active-active-style testing

### Stage 5 — AWS Expansion

```text
OCI Oracle
    |
GoldenGate Hub
    |
Azure SQL Server
    |
AWS PostgreSQL
```

Objectives:

* Build PostgreSQL environment in AWS
* Practice SQL Server / Oracle to PostgreSQL migration concepts
* Compare self-managed versus managed database options
* Extend routing, security, monitoring, and runbooks

### Stage 6 — Google Cloud Expansion

```text
Google Cloud VPC
10.80.0.0/16
```

Preferred target:

* PostgreSQL on Compute Engine or Cloud SQL for PostgreSQL

Objectives:

* Add a fourth cloud without CIDR overlap
* Compare PostgreSQL operating models across AWS and GCP
* Extend the migration / replication architecture without changing the core GoldenGate hub pattern

---

## 15. Estimated Hands-On Schedule

Expected time for the OCI Oracle ↔ Azure SQL Server portion:

| Lab Day | Focus                                                             |
| ------- | ----------------------------------------------------------------- |
| 1       | OCI ↔ Azure connectivity design and routing                       |
| 2       | Secure connectivity, ports, firewalls, listener validation        |
| 3       | GoldenGate hub deployment and configuration                       |
| 4       | Oracle → SQL Server schema assessment and initial migration setup |
| 5       | One-way CDC and DML validation                                    |
| 6       | One-way failure, restart, lag, and recovery exercises             |
| 7       | Configure reverse SQL Server → Oracle path                        |
| 8       | Loop prevention and key / sequence strategy                       |
| 9       | Conflict, simultaneous-update, outage, and reconciliation testing |
| 10      | Cutover / rollback drill, documentation, and Git evidence         |

Working expectation:

```text
7–10 focused lab days
```

At approximately 2–3 hours per day, allow roughly 10–14 calendar days so that troubleshooting and documentation are not skipped.

---

## 16. Experience Outcome

The objective is not merely to deploy working replication. The lab must produce enough operational evidence to confidently explain:

* Why the GoldenGate deployment model was selected
* How remote capture and remote apply work
* How heterogeneous Oracle → SQL Server migration differs from Oracle → Oracle migration
* How one-way CDC is configured and validated
* How bidirectional replication changes the design
* How loops and write conflicts are controlled
* How GoldenGate behaves during interruption and restart
* How to detect and reconcile divergence
* How to design cutover and rollback
* How networking, security, credentials, and database privileges affect CDC
* How the architecture can extend across OCI, Azure, AWS, and Google Cloud

The intended interview-level project summary is:

> Built a heterogeneous multi-cloud database migration and replication lab using OCI Oracle, Azure SQL Server, Oracle GoldenGate, AWS PostgreSQL, and Google Cloud PostgreSQL. Implemented a dedicated GoldenGate hub with remote capture and remote apply, validated one-way CDC, extended the topology to bidirectional replication, and tested failure recovery, conflict handling, reconciliation, cutover, and rollback.
