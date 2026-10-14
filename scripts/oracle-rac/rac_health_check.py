#!/usr/bin/env python3
"""
Oracle RAC Technical Health and Business Risk Summary
Python 3.6 compatible; no external modules required.

Recommended execution:
    chmod 750 rac_health_check.py
    ./rac_health_check.py

Optional overrides:
    DB_UNIQUE_NAME=RAC
    GRID_HOME=/u01/app/19.0.0/grid
    DB_HOME=/u01/app/oracle/product/19.0.0/dbhome_1
    ORACLE_BASE=/u01/app/oracle
"""

import glob
import os
import re
import shlex
import socket
import subprocess
import sys


DB_UNIQUE_NAME = os.getenv("DB_UNIQUE_NAME", "RAC")
GRID_HOME = os.getenv("GRID_HOME", "/u01/app/19.0.0/grid")

# Do not trust ORACLE_HOME when the script is run as grid; it usually points
# to the Grid home. DB_HOME is the explicit database-home override.
DB_HOME_OVERRIDE = os.getenv("DB_HOME")
DEFAULT_DB_HOME = "/u01/app/oracle/product/19.0.0/dbhome_1"
ORACLE_BASE = os.getenv("ORACLE_BASE", "/u01/app/oracle")

SSH_TIMEOUT = 8
ALERT_LOG_LINES = 300

findings = []


class Finding(object):
    def __init__(self, severity, category, message):
        self.severity = severity
        self.category = category
        self.message = message


def add(severity, category, message):
    findings.append(Finding(severity.upper(), category, message))


def run(cmd, timeout=45, env=None):
    try:
        process = subprocess.run(
            cmd,
            shell=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            executable="/bin/bash",
            env=env
        )
        return process.returncode, (process.stdout + process.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "Command timed out: {0}".format(cmd)
    except OSError as exc:
        return 127, str(exc)


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def discover_nodes():
    rc, out = run("{0}/bin/olsnodes -n -s".format(GRID_HOME))
    nodes = []

    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if parts:
                nodes.append(parts[0])

    if not nodes:
        nodes = [socket.gethostname().split(".")[0]]
        add("WARNING", "Cluster", "Could not discover all RAC nodes with olsnodes")

    return nodes


def discover_db_home():
    if DB_HOME_OVERRIDE:
        return DB_HOME_OVERRIDE

    rc, out = run(
        "{0}/bin/srvctl config database -db {1}".format(
            GRID_HOME, shlex.quote(DB_UNIQUE_NAME)
        )
    )

    if rc == 0:
        for line in out.splitlines():
            if line.startswith("Oracle home:"):
                candidate = line.split(":", 1)[1].strip()
                if candidate:
                    return candidate

    return DEFAULT_DB_HOME


def local_db_sid():
    rc, out = run(
        r"""ps -eo args | awk '
        /ora_pmon_/ && !/awk/ {
            sub(/^.*ora_pmon_/, "");
            if ($0 !~ /^\+ASM/) {
                print;
                exit
            }
        }'"""
    )
    return out.strip() if rc == 0 and out.strip() else None


def local_asm_sid():
    rc, out = run(
        r"""ps -eo args | awk '
        /asm_pmon_\+ASM/ && !/awk/ {
            sub(/^.*asm_pmon_/, "");
            print;
            exit
        }'"""
    )
    return out.strip() if rc == 0 and out.strip() else None


def sqlplus(query, sid, home, sysasm=False):
    if not sid:
        return 1, "ORACLE_SID could not be determined"

    role = "sysasm" if sysasm else "sysdba"
    env = os.environ.copy()
    env["ORACLE_HOME"] = home
    env["ORACLE_SID"] = sid
    env["PATH"] = "{0}/bin:{1}".format(home, env.get("PATH", ""))

    sql_text = """set heading off feedback off pages 0 lines 32767 trimspool on verify off echo off
whenever sqlerror exit sql.sqlcode
{0}
exit
""".format(query)

    try:
        process = subprocess.run(
            ["{0}/bin/sqlplus".format(home), "-s", "/", "as", role],
            input=sql_text,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            env=env
        )
        return process.returncode, (process.stdout + process.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "SQL*Plus command timed out"
    except OSError as exc:
        return 127, str(exc)


def check_os(nodes):
    section("OPERATING SYSTEM HEALTH")
    local = socket.gethostname().split(".")[0]

    for node in nodes:
        print("\n--- {0} ---".format(node))

        command = (
            "top -b -n1 | head -5; "
            "echo __MEM__; free -m; "
            "echo __DF__; df -P -x tmpfs -x devtmpfs"
        )

        if node == local:
            rc, out = run(command)
        else:
            rc, out = run(
                "ssh -o BatchMode=yes -o ConnectTimeout={0} {1} {2}".format(
                    SSH_TIMEOUT,
                    shlex.quote(node),
                    shlex.quote(command)
                )
            )

        print(out)

        if rc != 0:
            add("CRITICAL", "OS:{0}".format(node), "Unable to collect OS metrics")
            continue

        cpu_match = re.search(r"(?:%Cpu\(s\)|Cpu\(s\)):\s*(.+)", out)
        if cpu_match:
            values = {}
            for value, key in re.findall(
                r"([\d.]+)\s*([a-zA-Z]+)", cpu_match.group(1)
            ):
                values[key.lower()] = float(value)

            if values.get("us", 0) + values.get("sy", 0) >= 70:
                add("WARNING", "OS:{0}".format(node), "CPU utilization is high")
            if values.get("wa", 0) >= 20:
                add("WARNING", "OS:{0}".format(node), "I/O wait is high")
            if values.get("st", 0) >= 5:
                add("WARNING", "OS:{0}".format(node), "VM steal time is high")

        for line in out.splitlines():
            if re.match(r"^/dev/", line):
                parts = line.split()
                if len(parts) >= 6 and parts[4].endswith("%"):
                    use = int(parts[4][:-1])
                    if use >= 90:
                        add(
                            "CRITICAL",
                            "OS:{0}".format(node),
                            "Filesystem {0} is {1}% full".format(parts[5], use)
                        )
                    elif use >= 80:
                        add(
                            "WARNING",
                            "OS:{0}".format(node),
                            "Filesystem {0} is {1}% full".format(parts[5], use)
                        )


def check_cluster(nodes):
    section("CLUSTERWARE AND NETWORK HEALTH")

    checks = [
        ("Cluster status", "{0}/bin/crsctl check cluster -all".format(GRID_HOME)),
        ("Cluster nodes", "{0}/bin/olsnodes -n -s -t".format(GRID_HOME)),
        ("Cluster resources", "{0}/bin/crsctl stat res -t".format(GRID_HOME)),
        ("SCAN status", "{0}/bin/srvctl status scan".format(GRID_HOME)),
        ("SCAN listeners", "{0}/bin/srvctl status scan_listener".format(GRID_HOME)),
        ("Node listeners", "{0}/bin/srvctl status listener".format(GRID_HOME))
    ]

    for title, cmd in checks:
        print("\n--- {0} ---".format(title))
        rc, out = run(cmd)
        print(out)

        if rc != 0:
            severity = "CRITICAL" if title.startswith("Cluster") else "WARNING"
            add(severity, "Clusterware", "{0} check failed".format(title))

    print("\n--- VIP status ---")
    vip_failed = False

    for node in nodes:
        rc, out = run(
            "{0}/bin/srvctl status vip -node {1}".format(
                GRID_HOME, shlex.quote(node)
            )
        )
        print(out)

        if rc != 0:
            vip_failed = True

    if vip_failed:
        add("WARNING", "Clusterware", "VIP status check failed")


def check_database(sid, db_home):
    section("RAC DATABASE HEALTH")

    checks = [
        (
            "Database configuration",
            "{0}/bin/srvctl config database -db {1}".format(
                GRID_HOME, shlex.quote(DB_UNIQUE_NAME)
            )
        ),
        (
            "Database status",
            "{0}/bin/srvctl status database -db {1} -verbose".format(
                GRID_HOME, shlex.quote(DB_UNIQUE_NAME)
            )
        ),
        (
            "Database services",
            "{0}/bin/srvctl status service -db {1}".format(
                GRID_HOME, shlex.quote(DB_UNIQUE_NAME)
            )
        )
    ]

    for title, cmd in checks:
        print("\n--- {0} ---".format(title))
        rc, out = run(cmd)
        print(out or "No output")

        # No configured user services is not a database failure.
        if rc != 0 and title != "Database services":
            severity = "CRITICAL" if title == "Database status" else "WARNING"
            add(severity, "Database", "{0} check failed".format(title))

    if not sid:
        add("CRITICAL", "Database", "Could not determine local database SID")
        return

    query = """
select inst_id||'|'||instance_name||'|'||host_name||'|'||
       status||'|'||database_status
from gv$instance
order by inst_id;

select 'CDB|'||name||'|'||open_mode
from v$database;

select 'PDB|'||inst_id||'|'||name||'|'||open_mode
from gv$pdbs
order by inst_id,con_id;
"""

    rc, out = sqlplus(query, sid, db_home, sysasm=False)

    print("\n--- SQL validation ---")
    print(out)

    if rc != 0:
        add("CRITICAL", "Database", "SQL health query failed")
        return

    for line in out.splitlines():
        parts = [item.strip() for item in line.split("|")]

        if len(parts) == 5 and parts[0].isdigit():
            if parts[3] != "OPEN":
                add(
                    "CRITICAL",
                    "Database",
                    "Instance {0} is {1}".format(parts[1], parts[3])
                )
            if parts[4] != "ACTIVE":
                add(
                    "WARNING",
                    "Database",
                    "Instance {0} status is {1}".format(parts[1], parts[4])
                )

        elif len(parts) == 3 and parts[0] == "CDB":
            if parts[2] != "READ WRITE":
                add(
                    "CRITICAL",
                    "Database",
                    "CDB {0} is {1}".format(parts[1], parts[2])
                )

        elif len(parts) == 4 and parts[0] == "PDB":
            pdb_name = parts[2]
            open_mode = parts[3]

            if pdb_name == "PDB$SEED":
                if open_mode != "READ ONLY":
                    add(
                        "WARNING",
                        "PDB",
                        "{0} is {1}".format(pdb_name, open_mode)
                    )
            elif open_mode != "READ WRITE":
                add(
                    "WARNING",
                    "PDB",
                    "{0} is {1}".format(pdb_name, open_mode)
                )


def check_asm(asm_sid):
    section("ASM HEALTH")

    for title, cmd in [
        ("ASM status", "{0}/bin/srvctl status asm -detail".format(GRID_HOME)),
        ("ASM disk groups", "{0}/bin/asmcmd lsdg".format(GRID_HOME))
    ]:
        print("\n--- {0} ---".format(title))
        rc, out = run(cmd)
        print(out)

        if rc != 0:
            add("CRITICAL", "ASM", "{0} check failed".format(title))

    if not asm_sid:
        add("CRITICAL", "ASM", "Could not determine local ASM SID")
        return

    query = """
select inst_id||'|'||name||'|'||state||'|'||
       total_mb||'|'||free_mb||'|'||offline_disks
from gv$asm_diskgroup
order by inst_id,name;

select inst_id||'|'||path||'|'||header_status||'|'||
       mount_status||'|'||mode_status||'|'||state
from gv$asm_disk
order by inst_id,path;
"""

    rc, out = sqlplus(query, asm_sid, GRID_HOME, sysasm=True)

    print("\n--- ASM SQL validation ---")
    print(out)

    if rc != 0:
        add("CRITICAL", "ASM", "ASM SQL health query failed")
        return

    for line in out.splitlines():
        parts = [item.strip() for item in line.split("|")]

        if len(parts) == 6 and parts[1].startswith("/dev/"):
            if parts[2:] != ["MEMBER", "CACHED", "ONLINE", "NORMAL"]:
                add(
                    "CRITICAL",
                    "ASM",
                    "{0} unhealthy on ASM instance {1}".format(
                        parts[1], parts[0]
                    )
                )

        elif len(parts) == 6 and not parts[1].startswith("/dev/"):
            if parts[2] != "MOUNTED":
                add(
                    "CRITICAL",
                    "ASM",
                    "Disk group {0} is {1} on ASM instance {2}".format(
                        parts[1], parts[2], parts[0]
                    )
                )

            if parts[5] != "0":
                add(
                    "CRITICAL",
                    "ASM",
                    "Disk group {0} has {1} offline disks".format(
                        parts[1], parts[5]
                    )
                )

            try:
                free_pct = int(parts[4]) / float(int(parts[3])) * 100
                if free_pct < 10:
                    add(
                        "CRITICAL",
                        "ASM",
                        "Disk group {0} free space is {1:.1f}%".format(
                            parts[1], free_pct
                        )
                    )
                elif free_pct < 20:
                    add(
                        "WARNING",
                        "ASM",
                        "Disk group {0} free space is {1:.1f}%".format(
                            parts[1], free_pct
                        )
                    )
            except (ValueError, ZeroDivisionError):
                pass


def check_dbca_and_alerts():
    section("DBCA AND ALERT LOG REVIEW")

    dbca_root = os.path.join(ORACLE_BASE, "cfgtoollogs", "dbca")
    logs = []

    if os.path.isdir(dbca_root):
        for root, _, files in os.walk(dbca_root):
            for filename in files:
                if (
                    filename.endswith(".log")
                    or filename.startswith("trace.log_")
                    or filename.endswith(".trace")
                ):
                    logs.append(os.path.join(root, filename))

    if logs:
        latest = max(logs, key=os.path.getmtime)
        print("Latest DBCA log: {0}".format(latest))

        rc, out = run(
            "grep -E "
            "'DBCA_PROGRESS|overall status|Database creation complete|FATAL|SEVERE' "
            "{0} | tail -20".format(shlex.quote(latest))
        )
        print(out or "No completion marker found")

        lower = out.lower()
        if "overall status as failed" in lower:
            add("CRITICAL", "DBCA", "Latest DBCA execution ended with failure")
    else:
        print("No DBCA logs found")

    alert_logs = glob.glob(
        "{0}/diag/rdbms/*/*/trace/alert_*.log".format(ORACLE_BASE)
    )

    pattern = re.compile(
        r"ORA-\d{5}|TNS-\d{5}|RMAN-\d{5}|CRS-\d{4}|"
        r"WARNING:|Errors in file|Process .* died|"
        r"diskgroup .* incomplete|I/O error",
        re.I
    )

    for log in alert_logs:
        rc, out = run(
            "tail -{0} {1}".format(ALERT_LOG_LINES, shlex.quote(log))
        )

        matches = [
            line.strip()
            for line in out.splitlines()
            if pattern.search(line)
            and "If any errors are encountered" not in line
        ]

        print("\n--- {0} ---".format(log))

        if matches:
            print("\n".join(matches[-20:]))
            add(
                "WARNING",
                "AlertLog",
                "Recent alert-log findings in {0}".format(
                    os.path.basename(log)
                )
            )
        else:
            print("No recent matching Oracle errors found")


def executive_summary():
    section("EXECUTIVE SUMMARY")

    critical = [item for item in findings if item.severity == "CRITICAL"]
    warnings = [item for item in findings if item.severity == "WARNING"]

    if critical:
        print("Business status: CRITICAL")
        print(
            "One or more RAC conditions may affect availability, application "
            "connectivity, storage access, or failover capability."
        )
        print(
            "Immediate technical investigation is required to reduce the risk "
            "of service disruption or extended recovery time."
        )
        print("\nImmediate business risks:")
        for item in critical[:5]:
            print("- {0}".format(item.message))

    elif warnings:
        print("Business status: AT RISK")
        print(
            "The RAC service is currently operational, but warning conditions "
            "were detected."
        )
        print(
            "These conditions may reduce performance, resilience, capacity, "
            "or recoverability if not addressed."
        )
        print("\nKey operational risks:")
        for item in warnings[:5]:
            print("- {0}".format(item.message))

    else:
        print("Business status: HEALTHY")
        print(
            "The Oracle RAC database and supporting infrastructure are "
            "operating normally across the cluster."
        )
        print(
            "Database instances, ASM storage, Clusterware resources, listeners, "
            "and operating system resources are available with no major issues "
            "detected."
        )
        print("\nBusiness impact:")
        print("- Database services are available.")
        print("- RAC failover capability is intact.")
        print("- Shared ASM storage is accessible.")
        print("- No immediate availability or capacity risk was identified.")

    print("\nCritical findings: {0}".format(len(critical)))
    print("Warnings: {0}".format(len(warnings)))


def final_report():
    section("FINAL TECHNICAL INTERPRETATION")

    critical = [item for item in findings if item.severity == "CRITICAL"]
    warnings = [item for item in findings if item.severity == "WARNING"]

    status = "CRITICAL" if critical else "WARNING" if warnings else "HEALTHY"
    print("Overall technical status: {0}".format(status))

    for item in findings:
        print(
            "[{0:<8}] [{1}] {2}".format(
                item.severity, item.category, item.message
            )
        )

    return 2 if critical else 1 if warnings else 0


def main():
    db_home = discover_db_home()

    print("=" * 78)
    print("ORACLE RAC TECHNICAL HEALTH AND BUSINESS RISK SUMMARY")
    print("=" * 78)
    print("Host: {0}".format(socket.gethostname()))
    print("Database: {0}".format(DB_UNIQUE_NAME))
    print("Grid home: {0}".format(GRID_HOME))
    print("Database home: {0}".format(db_home))
    print("Oracle base: {0}".format(ORACLE_BASE))

    nodes = discover_nodes()
    db_sid = local_db_sid()
    asm_sid = local_asm_sid()

    print("Cluster nodes: {0}".format(", ".join(nodes)))
    print("Local DB SID: {0}".format(db_sid or "UNKNOWN"))
    print("Local ASM SID: {0}".format(asm_sid or "UNKNOWN"))

    check_os(nodes)
    check_cluster(nodes)
    check_database(db_sid, db_home)
    check_asm(asm_sid)
    check_dbca_and_alerts()
    executive_summary()

    return final_report()


if __name__ == "__main__":
    sys.exit(main())
