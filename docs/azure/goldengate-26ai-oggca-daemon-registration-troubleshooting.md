# Oracle GoldenGate 26ai — OGGCA Daemon Registration Troubleshooting

**Checkpoint Date:** September 5, 2026  
**Environment:** Azure GoldenGate Hub  
**GoldenGate Version:** 23.26.1.0.0  
**Deployment:** `DEP1`

## Problem Summary

Oracle GoldenGate Configuration Assistant (OGGCA) successfully created and verified deployment `DEP1`, but failed during the transition to register Service Manager as a Linux system service/daemon.

The GUI reported:

```text
[INS-85038] Deployment removal failed.

Verification failed. Expected value: (NOT) 'running', actual value: 'running'
Verification failed for REST call to '/services/v2/deployments/DEP1'
```

The OGGCA workflow showed:

```text
Create Deployment:                             Succeeded
Verify Deployment:                             Succeeded
Stop Deployment:                               Failed during verification
Register Service Manager as system daemon:     Not reached initially
```

## What Was Actually Blocking OGGCA

The stop REST request itself succeeded, but OGGCA verified the deployment state before Service Manager had fully reconciled the child-service stop state.

Service Manager logs showed the microservices did stop, but some status transitions completed after OGGCA's verification window had already expired.

Later task-history evidence showed successful stops with exit code `0` for:

```text
adminsrvr
distsrvr
recvsrvr
pmsrvr
```

This established that the failure was a timing/state-reconciliation problem rather than a permanent inability to stop the deployment.

## OS-Level Validation

The following command returned no processes:

```bash
ps -ef | grep -E 'adminsrvr|distsrvr|recvsrvr|pmsrvr' | grep -v grep
```

Therefore all four `DEP1` microservices were confirmed stopped.

Service Manager itself remained running:

```bash
ps -ef | grep '[S]erviceManager'
```

Observed process:

```text
/u01/ogg26ai_home/bin/ServiceManager
```

with PPID `1`.

This means Service Manager was detached from the interactive shell, but this alone did not prove it was registered as a systemd service.

## Hostname Resolution Check

OGGCA configured Service Manager using:

```text
vm-goldengate-lab-01.internal.cloudapp.net
```

`/etc/hosts` contained only localhost entries, but Azure DNS resolved the hostname correctly:

```bash
getent hosts vm-goldengate-lab-01.internal.cloudapp.net
```

Result:

```text
10.60.30.4 vm-goldengate-lab-01.internal.cloudapp.net
```

DNS/hostname resolution was therefore eliminated as the cause.

## REST Authorization Observation

A direct request to:

```text
/services/v2/deployments/DEP1
```

using `oggadmin` returned:

```text
OGG-12062
Authenticated user is not authorized for this request.
```

However, the authorization catalog endpoint was accessible and listed the standard GoldenGate roles:

```text
All
User
Operator
Administrator
Security
```

This REST authorization behavior was treated separately from the original OGGCA stop-verification failure.

## Configuration Backup

Before making corrective changes, the Service Manager and deployment configuration trees were backed up:

```bash
tar -czf /home/azureuser/ogg_DEP1_before_daemon_fix_20260905.tar.gz \
/u01/ogg26ai_deploy \
/u01/ogg26ai_sm
```

Backup validation:

```text
/home/azureuser/ogg_DEP1_before_daemon_fix_20260905.tar.gz
198K
```

Unix socket warnings during `tar` were expected and ignored.

## GoldenGate Version

Version check:

```bash
/u01/ogg26ai_home/bin/adminclient -v
```

Result:

```text
Oracle GoldenGate Administration Client for Oracle
Version 23.26.1.0.0
OGGCORE_23.26.1.0.0OGGRU_LINUX.X64_260117.1830_FBO
```

## Registration Artifact Discovery

An earlier search showed no registration script before OGGCA progressed far enough.

After the configuration workflow was retried and advanced further, the registration artifacts were found:

```bash
find /u01/ogg26ai_deploy /u01/ogg26ai_home \
-type f \( -name 'registerServiceManager.sh' -o -name 'oggInst.loc' \) \
-print 2>/dev/null
```

Result:

```text
/u01/ogg26ai_deploy/bin/registerServiceManager.sh
/u01/ogg26ai_home/lib/utl/install/templates/oggInst.loc
```

This is an important state change: OGGCA did eventually create `registerServiceManager.sh`, proving that the workflow progressed beyond the earlier stop-verification failure.

## Current GUI State

The OGGCA configuration screen reached 100% and reported:

```text
Setup completed with overall status as Succeeded
```

A popup then reported:

```text
The GoldenGate Inventory Locator (to be created by the script) was not found.

Are you sure you want to continue?
```

This means the next task is no longer to troubleshoot `DEP1` shutdown. The immediate task is to execute/validate the generated Service Manager registration script with the required privileges so that the GoldenGate Inventory Locator and system service registration are created correctly.

## Current State

```text
GoldenGate software home:       /u01/ogg26ai_home
Service Manager deployment:     /u01/ogg26ai_deploy
User deployment home:           /u01/ogg26ai_sm
Deployment name:                 DEP1
Service Manager port:            9011
Administration Server port:      9012
Distribution Server port:        9013
Receiver Server port:            9014
Performance Metrics port:        9015
GoldenGate version:              23.26.1.0.0
DEP1 child services:             Stopped during daemon-registration transition
registerServiceManager.sh:       Present
GoldenGate inventory locator:    Pending creation/validation
```

## Root Cause / Troubleshooting Conclusion

The original `INS-85038` was caused by OGGCA seeing a stale `running` deployment state during its stop-verification window even though the GoldenGate child services subsequently stopped successfully.

The troubleshooting sequence proved:

1. Deployment creation itself was successful.
2. The stop request itself was successful.
3. Child processes eventually stopped with successful exit codes.
4. DNS was healthy.
5. Service Manager remained available.
6. No destructive reinstall or deployment deletion was required.
7. A subsequent OGGCA run progressed far enough to generate `registerServiceManager.sh`.

## Next Action

Run and validate the generated Service Manager registration script according to Oracle GoldenGate 26ai's daemon-registration workflow, then confirm:

```bash
systemctl status OracleGoldenGate
```

and verify that Service Manager can be controlled through systemd without losing the existing `DEP1` configuration.

Do not delete `DEP1`, remove the GoldenGate homes, or rebuild the deployment unless the supported registration workflow fails and a controlled rollback is required.
