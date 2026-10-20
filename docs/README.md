# Documentation Index

This directory contains the design records, implementation notes, checkpoints, troubleshooting cases, runbooks, and project history for the Enterprise Multi-Cloud Database Platform Lab.

## Architecture

- [Multi-Cloud Migration and Replication Plan](architecture/multicloud-migration-replication-plan.md)

## Azure

- [Phase 1 — Azure Foundation](azure/phase-1-azure-foundation.md)

## Rerun

- [OCI Oracle to Azure SQL Server GoldenGate Rerun Playbook](oci-to-azure-goldengate-rerun-playbook.md)

## Checkpoints

- [2026-09-07 — Oracle to SQL Server CDC Progress](checkpoints/2026-09-07-oracle-to-sqlserver-cdc-progress.md)
- [2026-09-09 — Oracle to SQL Server Replicat Preparation](checkpoints/2026-09-09-oracle-to-sqlserver-replicat-prep.md)
- [September 2026 Build Snapshot](checkpoints/2026-09-build-snapshot.md)

## GoldenGate Troubleshooting

- [GoldenGate 26ai OGGCA Daemon Registration Troubleshooting](goldengate/troubleshooting/goldengate-26ai-oggca-daemon-registration-troubleshooting.md)

## Project History

- [Project History and Troubleshooting](project-history/project-history-and-troubleshooting.md)

## Runbooks

- [Recovered Command Syntax Reference](runbooks/recovered-command-syntax-reference.md)
- [Oracle 19c Two-Node RAC Build and Troubleshooting](runbooks/oracle-rac/oracle19c-2node-rac-build-and-troubleshooting.md)
- [Oracle 26ai Two-Node RAC Build Runbook (tested; open Verify items listed)](runbooks/oracle-rac/oracle26ai-2node-rac-build-runbook.md)

## Documentation Standard

New documents should be placed by purpose:

```text
docs/
├── architecture/       # target-state design and topology
├── azure/              # Azure-specific implementation notes
├── checkpoints/        # dated progress snapshots
├── goldengate/         # GoldenGate-specific documentation
├── project-history/    # chronological history and RCA
└── runbooks/           # repeatable operational procedures
```

Do not place credentials, private keys, PSKs, passwords, or production secrets in documentation.
