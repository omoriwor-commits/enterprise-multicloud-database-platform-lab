# Enterprise Data Platform Lab — Multi-Cloud Migration & Replication Plan

**Checkpoint Date:** August 25, 2026

> Dated record. Status items below reflect August to September 2026. For the current state, see the [README Final outcome](../../README.md#final-outcome).
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

The Azure VPN Gateway has now been deployed for the OCI ↔ Azure Site-to-Site VPN lab.

```text
Gateway:      vng-enterprise-data-platform-lab
SKU:          VpnGw1AZ
VPN type:     Route-based
Azure ASN:    65515
Azure APIPA:  169.254.21.2
Public IP:    <redacted>
```

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
            │ OCI ↔ Azure Site-to-Site VPN / BGP
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
    └── vng-enterprise-data-platform-lab
        SKU: VpnGw1AZ
        VPN type: Route-based
        Azure ASN: 65515
        Azure APIPA: 169.254.21.2
        Public IP: <redacted>

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
* [x] Azure Local Network Gateway `lng-oci-tunnel1` created for OCI Tunnel 1
* [x] Azure VPN connection `conn-azure-to-oci-tunnel1` created with OCI-generated PSK
* [x] OCI IPSec Tunnel 1 status validated Up
* [x] OCI IPv4 BGP status validated Up
* [x] Azure VPN Gateway / VPN connection health validated Healthy
* [x] Azure BGP peer to OCI validated Connected
* [x] Azure learned OCI route `10.50.0.0/16` over eBGP
* [x] Azure advertised `10.60.0.0/16` toward OCI
* [x] Database NSG rule `Allow-SQL-From-OCI-Oracle` created for `10.50.10.178/32 -> 10.60.20.4:1433`
* [x] SQL Server TCP/IP protocol validated Enabled
* [x] SQL Server static TCP port validated as `1433`
* [x] SQL Server listener validated on TCP `1433`
* [x] End-to-end OCI Oracle VM -> Azure SQL Server TCP `1433` connectivity validated successfully

### Not Yet Deployed

* [x] OCI ↔ Azure Site-to-Site VPN established
* [x] Azure VPN Gateway deployed
* [x] OCI DRG `drg-azure-hybrid-lab` created
* [x] OCI VCN attachment `att-rotez-hybrid-lab-vcn` created
* [x] OCI route `10.60.0.0/16 -> drg-azure-hybrid-lab` created
* [x] OCI CPE `cpe-azure-vpn-gateway` created for Azure VPN public IP
* [x] OCI Site-to-Site VPN `ipsec-oci-azure-lab` created
* [x] OCI BGP tunnel `Azure-Tunnel-1` created with IKEv2
* [x] Azure Local Network Gateway for OCI Tunnel 1
* [x] Azure VPN connection using OCI-generated PSK
* [x] IPSec tunnel status Up
* [x] BGP session status Up
* [x] BGP route exchange validated in Azure
* [x] OCI Oracle VM -> Azure SQL Server TCP `1433` private connectivity validated
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

Deploy the dedicated GoldenGate hub compute instance into `snet-goldengate` (`10.60.30.0/24`). Because the OCI security list and Azure GoldenGate NSG rules are already scoped to the GoldenGate subnet, the correct reverse-path validation must originate from that subnet rather than from the Azure SQL Server VM.

After the GoldenGate hub is deployed, validate:

```text
GoldenGate hub (10.60.30.0/24)
        -> IPSec / BGP
        -> OCI Oracle 10.50.10.178:1521
```

Success criteria:

* GoldenGate VM receives a private IP in `10.60.30.0/24`
* SSH administration works only from the approved management path
* OCI Oracle listener is reachable on TCP `1521`
* Azure SQL Server is reachable on TCP `1433`
* No public database listener exposure is introduced
* Host firewalls are validated after NSG/security-list validation

Once both database endpoints are reachable from the GoldenGate hub, proceed with GoldenGate Microservices installation, credential configuration, and remote-capture/remote-apply setup.

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
* SQL Server TCP `1433` from OCI Oracle VM `10.50.10.178/32`
* Explicit deny rule ahead of broad VNet inbound defaults
* No unrestricted Internet exposure for SQL Server TCP `1433`

The GoldenGate subnet and its dedicated NSG are deployed. The Azure outbound Oracle listener rule from the GoldenGate subnet to the OCI Oracle host on TCP `1521` has also been implemented. OCI ↔ Azure routed connectivity is now established: Azure VPN Gateway, OCI DRG, VCN attachment, OCI route, CPE, OCI Site-to-Site VPN, Azure Local Network Gateway, and Azure VPN connection are all deployed. IPSec and IPv4 BGP are Up, Azure VPN diagnostics report the connection as Healthy, Azure learns the OCI `10.50.0.0/16` route, and Azure advertises `10.60.0.0/16` toward OCI.

The OCI Oracle VM to Azure SQL Server database path has also been validated end to end:

```text
Source:      10.50.10.178
Destination: 10.60.20.4
Protocol:    TCP
Port:        1433
Result:      SUCCESS
```

SQL Server TCP/IP is enabled, `IPAll` is configured with static TCP port `1433`, and the SQL Server process is listening on TCP `1433`.

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

### OCI ↔ Azure VPN Implementation Detail

Azure VPN Gateway created:

```text
Name:          vng-enterprise-data-platform-lab
SKU:           VpnGw1AZ
VPN type:      Route-based
VNet:          vnet-enterprise-data-platform-lab
GatewaySubnet: 10.60.254.0/27
BGP:           Enabled
Azure ASN:     65515
Azure APIPA:   169.254.21.2
Public IP:     <redacted>
```

OCI DRG created:

```text
Name: drg-azure-hybrid-lab
```

OCI VCN attachment created:

```text
Attachment:     att-rotez-hybrid-lab-vcn
VCN:            Rotez_hybrid-lab-vcn
VCN route type: VCN CIDR blocks
State:          Attached
```

OCI route added:

```text
Destination: 10.60.0.0/16
Target:      drg-azure-hybrid-lab
Description: Route-To-Azure-VNet
```

OCI CPE created to represent the Azure VPN Gateway:

```text
Name:      cpe-azure-vpn-gateway
IP:        <redacted>
Vendor:    Other
```

OCI Site-to-Site VPN created:

```text
Name:        ipsec-oci-azure-lab
DRG:         drg-azure-hybrid-lab
Static route: 0.0.0.0/0
VPN version: v2
```

OCI Tunnel 1 configuration:

```text
Name:                     Azure-Tunnel-1
Routing type:             BGP dynamic routing
IKE version:              IKEv2
Oracle VPN public IP:     <redacted>
Oracle BGP ASN:           31898
Customer/Azure BGP ASN:   65515
CPE/Azure inside IP:      169.254.21.2/30
Oracle inside IP:         169.254.21.1/30
IPSec status:             Up
IPv4 BGP status:          Up
```

The OCI-generated shared secret is intentionally not recorded in this runbook. It must be stored privately and entered into the Azure VPN connection configuration.

Azure peer objects created:

```text
Local Network Gateway: lng-oci-tunnel1
VPN Connection:        conn-azure-to-oci-tunnel1
IKE:                   IKEv2
BGP:                   Enabled
Azure BGP address:     169.254.21.2
OCI BGP peer:          169.254.21.1
```

Azure BGP validation:

```text
Peer status: Connected
OCI route learned by Azure: 10.50.0.0/16
Azure route advertised to OCI: 10.60.0.0/16
```

Azure Network Watcher VPN troubleshoot validation:

```text
VPN gateway: Healthy
VPN connection: Healthy
```

Database-path validation:

```text
OCI Oracle VM 10.50.10.178
        -> IPSec / BGP
        -> Azure SQL Server 10.60.20.4:1433

TCP 1433 SUCCESS
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

What I actually completed (as of October 2026):

> I built a cross-cloud lab that replicates Oracle AI Database 26ai on OCI into SQL Server 2022 on Azure through a dedicated GoldenGate 26ai hub. I set up the OCI-Azure IPsec/IKEv2 VPN with BGP, tracked down a pre-shared-key mismatch, worked through GoldenGate install and lifecycle failures, and diagnosed an FRA exhaustion that stalled redo archiving. I verified one-way INSERT, UPDATE and DELETE apply; sanitized target-side logs will be published after the rerun. AWS and Google Cloud PostgreSQL are planned, not built.

Bidirectional replication, conflict handling, reconciliation, cutover and rollback testing in the list above are planned, not done.
