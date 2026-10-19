#!/usr/bin/env python3
r"""Read-only Oracle RAC health snapshot, revision 2026-10-19.3.

Python 3.6+; standard library only. Designed for the supplied 26ai lab and
retains 19c-compatible discovery. Not a certification or failover test.

Run as grid for SYSASM; database SQL also requires authorized OS SYSDBA
membership (already configured for grid in this lab). Do not add privileges
just to obtain a green report. Oracle-only runs report incomplete ASM checks.

    chmod 750 rac_health_check.py
    ./rac_health_check.py --db RAC --pdb RACPDB1 --alert-hours 24
    ./rac_health_check.py --db RAC --pdb RACPDB1 --dbca-node racnode1
    ./rac_health_check.py --json-out ~/rac_health_$(date +%Y%m%d_%H%M%S).json
    ./rac_health_check.py 2>&1 | tee health.log
    printf 'script_exit=%s\n' "${PIPESTATUS[0]}"

Grid home: --grid-home / GRID_HOME, then /etc/oracle/olr.loc.
DB home: --db-home / DB_HOME, then srvctl config database.
Bases: --grid-base / GRID_BASE and --db-base / DB_BASE, then each home's
orabase utility. Inherited ORACLE_HOME/ORACLE_BASE are not discovery inputs.
Local text-alert paths prefer V$DIAG_INFO; conventional 19c/26ai ADR paths
are a fallback. DBCA supports trace.log_<timestamp>, .log and .trace files.

OS is collected from discovered/configured nodes. Database/ASM global views
are cluster-wide observations. Alert/DBCA review is LOCAL ONLY: run on both
nodes for both local histories. Alert review is a bounded tail (at most 8 MiB), not a full
history search. No script, SQL statement or subprocess changes the cluster.
OS collection needs Python 3.6+ on each node. CPU and paging use three actual
one-second intervals by default (not top's first screen); nice, IRQ and softirq
time count as busy. Process names are collected, never command-line arguments.
JSON output is optional, private (0600), local to the executing node and never
overwrites an existing file. It excludes raw log excerpts; review before sharing.
--dbca-node identifies the creation node. A missing default DBCA directory is
informational unless evidence was explicitly expected locally.
SELinux mode is observed, never changed. Sampled setroubleshoot CPU is reported
separately; process names alone cannot identify AVC triggers or past hang causes.

Other overrides: DB_UNIQUE_NAME, DB_SID, ASM_SID, EXPECTED_NODES (comma list),
EXPECTED_PDBS, OSASM_GROUP, DBCA_LOG_DIR, DB_ALERT_LOG, ASM_ALERT_LOG,
ALERT_LOOKBACK_HOURS (24), ALERT_LOG_LINES (2000), COMMAND_TIMEOUT (45).
Exit: 0 no findings in completed checks; 1 warning/incomplete; 2 critical;
3 configuration error. A shell pipeline needs PIPESTATUS to retain this code.
Reports contain lab hostnames/paths and log excerpts: review before publishing.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import glob
import json
import math
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile


REVISION = "2026-10-19.3"
GRID_HOME = GRID_BASE = DB_HOME = DB_BASE = None
DB_CONFIG = {}
DB_ALERT = ASM_ALERT = None
DB_VERSION = None
DB_OPERATIONAL = False
KERNELS = {}
EXPECTED_INSTANCES = []
findings = []
coverage = {}
CFG = None
METRICS = {}
STARTED_AT = None


class ConfigError(Exception):
    pass


class Finding(object):
    def __init__(self, severity, category, message):
        self.severity, self.category, self.message = severity, category, message


def add(severity, category, message):
    findings.append(Finding(severity, category, message))


def section(title):
    print("\n" + "=" * 78 + "\n" + title + "\n" + "=" * 78)


def short_host(value):
    return value.lower().split(".")[0]


def split_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    opts = [("db", "DB_UNIQUE_NAME", "RAC"), ("pdb", "EXPECTED_PDBS", ""),
            ("nodes", "EXPECTED_NODES", ""), ("grid-home", "GRID_HOME", None),
            ("db-home", "DB_HOME", None), ("grid-base", "GRID_BASE", None),
            ("db-base", "DB_BASE", None), ("db-sid", "DB_SID", None),
            ("asm-sid", "ASM_SID", None), ("osasm-group", "OSASM_GROUP", "asmadmin"),
            ("dbca-dir", "DBCA_LOG_DIR", None), ("db-alert", "DB_ALERT_LOG", None),
            ("asm-alert", "ASM_ALERT_LOG", None)]
    for name, env, default in opts:
        p.add_argument("--" + name, default=os.getenv(env, default))
    p.add_argument("--alert-hours", type=float,
                   default=os.getenv("ALERT_LOOKBACK_HOURS", "24"))
    p.add_argument("--alert-lines", type=int,
                   default=os.getenv("ALERT_LOG_LINES", "2000"))
    p.add_argument("--timeout", type=int, default=os.getenv("COMMAND_TIMEOUT", "45"))
    p.add_argument("--os-samples", type=int, default=3,
                   help="CPU/paging intervals per node (2..10; default 3)")
    p.add_argument("--sample-seconds", type=float, default=1,
                   help="Seconds per OS interval (0.2..5; default 1)")
    p.add_argument("--dbca-node", help="Node where DBCA ran; absent local logs on other nodes are informational")
    p.add_argument("--json-out", help="Save a private JSON summary locally; no raw alert excerpts")
    p.add_argument("--version", action="version", version=REVISION)
    return p


def oracle_env(home, sid=None, base=None):
    env = os.environ.copy()
    env.update(ORACLE_HOME=home, LC_ALL="C", LANG="C")
    env["PATH"] = os.path.join(home, "bin") + os.pathsep + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = os.path.join(home, "lib")
    if sid:
        env["ORACLE_SID"] = sid
    else:
        env.pop("ORACLE_SID", None)
    if base:
        env["ORACLE_BASE"] = base
    else:
        env.pop("ORACLE_BASE", None)
    # TWO_TASK/LOCAL can redirect a supposedly local OS-authenticated login.
    env.pop("TWO_TASK", None)
    env.pop("LOCAL", None)
    return env


def run(cmd, timeout=None, env=None, input_text=None):
    """Bounded subprocess; terminate only our own process group on timeout."""
    command = ["/bin/bash", "-o", "pipefail", "-c", cmd] if isinstance(cmd, str) else cmd
    actual_env = os.environ.copy() if env is None else env.copy()
    actual_env.update(LC_ALL="C", LANG="C")
    process = None
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, errors="replace",
                                   env=actual_env, start_new_session=True)
        try:
            out, err = process.communicate(input_text, timeout=timeout or CFG.timeout)
            return process.returncode, (out + "\n" + err).strip()
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            return 124, "Collection command timed out"
    except (OSError, ValueError) as exc:
        return 127, str(exc)


def tool(home, name, *args, **kwargs):
    env = kwargs.get("env", oracle_env(home, base=GRID_BASE if home == GRID_HOME else DB_BASE))
    return run([os.path.join(home, "bin", name)] + list(args), env=env)


def config_pairs(text):
    return dict((key.strip(), value.strip()) for key, value in
                (line.split(":", 1) for line in text.splitlines() if ":" in line))


def absolute_dir(value, label):
    if not value or not os.path.isabs(value) or not os.path.isdir(value):
        raise ConfigError("{0} is missing or is not an absolute directory: {1}".format(label, value))
    return os.path.normpath(value)


def discover_base(home, override):
    if override:
        return absolute_dir(override, "Oracle base")
    rc, out = tool(home, "orabase", env=oracle_env(home))
    lines = out.strip().splitlines()
    if rc == 0 and lines:
        return absolute_dir(lines[-1].strip(), "orabase result")
    raise ConfigError("Cannot discover base for {0}; use --grid-base/--db-base".format(home))


def discover_config():
    global GRID_HOME, GRID_BASE, DB_HOME, DB_BASE, DB_CONFIG, EXPECTED_INSTANCES
    gh = CFG.grid_home
    if not gh:
        try:
            with open("/etc/oracle/olr.loc") as handle:
                for line in handle:
                    if line.strip().startswith("crs_home="):
                        gh = line.split("=", 1)[1].strip()
                        break
        except OSError:
            pass
    GRID_HOME = absolute_dir(gh, "Grid home (--grid-home or GRID_HOME)")
    rc, out = tool(GRID_HOME, "srvctl", "config", "database", "-db", CFG.db)
    if rc != 0 or not out:
        raise ConfigError("Cannot read srvctl configuration for {0}: {1}".format(CFG.db, out))
    DB_CONFIG = config_pairs(out)
    DB_HOME = absolute_dir(CFG.db_home or DB_CONFIG.get("Oracle home"), "Database home")
    EXPECTED_INSTANCES = split_list(DB_CONFIG.get("Database instances", ""))
    for home, binaries in [(GRID_HOME, ("crsctl", "srvctl", "olsnodes", "sqlplus", "asmcmd")),
                           (DB_HOME, ("sqlplus",))]:
        for binary in binaries:
            if not os.access(os.path.join(home, "bin", binary), os.X_OK):
                raise ConfigError("Missing/non-executable tool: {0}/bin/{1}".format(home, binary))
    GRID_BASE = discover_base(GRID_HOME, CFG.grid_base)
    DB_BASE = discover_base(DB_HOME, CFG.db_base)


def discover_nodes():
    rc, out = tool(GRID_HOME, "olsnodes", "-n", "-s")
    found = [line.split()[0] for line in out.splitlines()
             if re.match(r"^\S+\s+\d+\s+", line)] if rc == 0 else []
    expected = split_list(CFG.nodes) or split_list(DB_CONFIG.get("Configured nodes", ""))
    nodes = list(dict.fromkeys(expected + found))
    if not found:
        add("WARNING", "Discovery", "olsnodes did not return a usable node inventory")
    if not nodes:
        nodes = [socket.gethostname().split(".")[0]]
        add("WARNING", "Discovery", "Node scope is incomplete; use --nodes")
    for node in nodes:
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", node):
            raise ConfigError("Invalid node name in inventory")
    return nodes


def local_sid(asm=False):
    override = CFG.asm_sid if asm else CFG.db_sid
    if override:
        return override
    if not asm:
        rc, out = tool(GRID_HOME, "srvctl", "status", "database", "-db", CFG.db)
        local = short_host(socket.gethostname())
        for inst, node in re.findall(r"Instance\s+(\S+)\s+is running on node\s+(\S+)", out):
            if rc == 0 and short_host(node.rstrip(".")) == local:
                return inst
    rc, out = run(["ps", "-eo", "args"])
    pattern = r"(?:^|\s)asm_pmon_(\+ASM\S*)" if asm else r"(?:^|\s)ora_pmon_(\S+)"
    candidates = re.findall(pattern, out, re.M) if rc == 0 else []
    if not asm:
        # Avoid checking the first unrelated database in a multi-database VM.
        candidates = [sid for sid in candidates if sid in EXPECTED_INSTANCES]
    return candidates[0] if len(set(candidates)) == 1 else None


SQL_ERROR = re.compile(r"^\s*(?:ORA|SP2|TNS|PLS)-\d+", re.M)


def sqlplus(query, sid, home, sysasm=False):
    if not sid:
        return 1, "Local SID could not be determined; set --db-sid/--asm-sid"
    if not re.match(r"^[A-Za-z0-9_+$#.-]+$", sid):
        return 1, "Invalid local SID"
    role = "sysasm" if sysasm else "sysdba"
    text = """whenever oserror exit failure rollback
whenever sqlerror exit failure rollback
connect / as {0}
set heading off feedback off pages 0 lines 32767 trimspool on verify off echo off
prompt __RAC_HEALTH_BEGIN__
{1}
prompt __RAC_HEALTH_END__
exit success rollback
""".format(role, query)
    rc, out = run([os.path.join(home, "bin", "sqlplus"), "-L", "-s", "/nolog"],
                  timeout=max(CFG.timeout, 60), input_text=text,
                  env=oracle_env(home, sid, GRID_BASE if sysasm else DB_BASE))
    # SQL*Plus SP2 errors are not handled by WHENEVER SQLERROR.
    if rc != 0 or SQL_ERROR.search(out):
        return rc or 1, out
    begin, end = "__RAC_HEALTH_BEGIN__", "__RAC_HEALTH_END__"
    if begin not in out or end not in out or out.index(end) < out.index(begin):
        return 1, "SQL result is incomplete (completion markers missing): " + out
    return 0, out.split(begin, 1)[1].split(end, 1)[0].strip()


def collect_node(node, command):
    if short_host(node) == short_host(socket.gethostname()):
        return run(command)
    return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", node,
                "bash -o pipefail -c " + shlex.quote(command)])


# The sampler executes on each observed node. No process arguments or SQL text
# are collected; process identity uses only /proc/<pid>/stat's comm field.
OS_SAMPLER = r'''
import json, os, sys, time

def snapshot():
    with open('/proc/stat') as f:
        lines = f.readlines()
    cpu = [int(v) for v in lines[0].split()[1:9]]
    if len(cpu) != 8:
        raise ValueError('Incomplete /proc/stat CPU counters')
    with open('/proc/vmstat') as f:
        vm = dict(line.split() for line in f)
    processes = {}
    for pid in os.listdir('/proc'):
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            with open('/proc/' + pid + '/stat') as f:
                value = f.read()
            end = value.rfind(')')
            fields = value[end+2:].split()
            # fields start at stat field 3; include starttime to handle PID reuse.
            processes[pid] = (int(fields[19]), int(fields[11])+int(fields[12]),
                              value[value.find('(')+1:end])
        except (OSError, ValueError, IndexError):
            continue
    return (time.monotonic(), cpu, int(vm['pswpin']), int(vm['pswpout']), processes)

samples, seconds = int(sys.argv[1]), float(sys.argv[2])
previous = snapshot()
hz, page_kib = os.sysconf('SC_CLK_TCK'), os.sysconf('SC_PAGE_SIZE') / 1024.0
for index in range(samples):
    time.sleep(seconds)
    current = snapshot()
    elapsed = current[0]-previous[0]
    delta = [b-a for a,b in zip(previous[1], current[1])]
    if elapsed <= 0 or any(v < 0 for v in delta) or sum(delta) <= 0:
        raise ValueError('Non-monotonic CPU counters; sample unavailable')
    total = float(sum(delta))  # guest counters excluded: already counted in user/nice
    process_cpu = []
    for pid, (birth,ticks,name) in current[4].items():
        old = previous[4].get(pid)
        if old and old[0] == birth and ticks >= old[1]:
            pct = (ticks-old[1])*100.0/hz/elapsed
            if pct > 0:
                process_cpu.append({'pid':int(pid), 'name':name, 'cpu_pct_one_core':round(pct,1)})
    row = {'interval':index+1, 'seconds':round(elapsed,3),
           'busy_pct':round((sum(delta)-delta[3]-delta[4]-delta[7])*100.0/total,1),
           'iowait_pct':round(delta[4]*100.0/total,1),
           'steal_pct':round(delta[7]*100.0/total,1),
           'swap_in_kib_s':round((current[2]-previous[2])*page_kib/elapsed,1),
           'swap_out_kib_s':round((current[3]-previous[3])*page_kib/elapsed,1),
           'top_processes':sorted(process_cpu,key=lambda p:p['cpu_pct_one_core'],reverse=True)[:5]}
    print('OS_SAMPLE|' + json.dumps(row,sort_keys=True),flush=True)
    previous = current
'''


def evaluate_os_samples(out, node):
    category = 'OS:' + node
    samples = []
    try:
        for line in out.splitlines():
            if line.startswith('OS_SAMPLE|'):
                row = json.loads(line.split('|', 1)[1])
                for key in ('seconds', 'busy_pct', 'iowait_pct', 'steal_pct',
                            'swap_in_kib_s', 'swap_out_kib_s'):
                    if isinstance(row[key], bool) or not math.isfinite(float(row[key])) or float(row[key]) < 0:
                        raise ValueError('invalid interval metric')
                if row['seconds'] <= 0 or any(row[k] > 100 for k in ('busy_pct','iowait_pct','steal_pct')):
                    raise ValueError('invalid CPU percentage/elapsed time')
                samples.append(row)
        if len(samples) != CFG.os_samples:
            raise ValueError('missing interval samples')
        if [r.get('interval') for r in samples] != list(range(1, CFG.os_samples+1)):
            raise ValueError('duplicate/out-of-order interval samples')
    except (ValueError, KeyError, TypeError) as exc:
        add('WARNING', category, 'CPU/paging interval collection incomplete: ' + str(exc))
        return False
    METRICS.setdefault('os', {}).setdefault(node, {})['intervals'] = samples
    duration = sum(r['seconds'] for r in samples)
    weighted = lambda key: sum(r[key]*r['seconds'] for r in samples)/duration
    mean, peak = weighted('busy_pct'), max(r['busy_pct'] for r in samples)
    high = sum(r['busy_pct'] >= 85 for r in samples)
    print('Interval CPU busy mean {0:.1f}%, peak {1:.1f}% over {2:.1f}s; {3}/{4} intervals >=85%.'.format(
          mean, peak, duration, high, len(samples)))
    print('Process CPU percentages use one core = 100%; aggregate CPU uses all cores = 100%.')
    print('Interval  Busy%  IOWait%  Steal%  SwapIn KiB/s  SwapOut KiB/s')
    leaders = {}
    for row in samples:
        print('{0:8d} {1:6.1f} {2:8.1f} {3:7.1f} {4:13.1f} {5:14.1f}'.format(
              row['interval'],row['busy_pct'],row['iowait_pct'],row['steal_pct'],
              row['swap_in_kib_s'],row['swap_out_kib_s']))
        for process in row.get('top_processes', []):
            identity = (process['pid'], process['name'])
            leaders[identity] = max(leaders.get(identity, 0), process['cpu_pct_one_core'])
    print('Busiest visible processes (peak interval CPU; exited/short-lived processes may be missed):')
    for (pid, name), pct in sorted(leaders.items(),key=lambda p:p[1],reverse=True)[:5]:
        safe_name = ''.join(c if c.isprintable() else '?' for c in name)
        print('  PID {0}: {1} {2:.1f}%'.format(pid,safe_name,pct))
    diagnostic_cpu = [sum(p['cpu_pct_one_core'] for p in row.get('top_processes', [])
                          if p['name'].lower().startswith('setroubleshoot')) for row in samples]
    if max(diagnostic_cpu) > 0:
        METRICS['os'][node]['selinux_troubleshooting_peak_pct_one_core'] = max(diagnostic_cpu)
        add('INFO', category,
            'Visible SELinux troubleshooting processes used up to {0:.1f}% of one core combined in an interval. '
            'Review AVC/journal records; this does not establish the trigger or explain earlier ASM hangs.'.format(max(diagnostic_cpu)))
    if high >= 2 and high*2 >= len(samples):
        add('WARNING', category, 'Repeated high CPU within this short sample ({0}/{1} intervals >=85%); inspect listed processes'.format(high,len(samples)))
    elif peak >= 85:
        add('INFO', category, 'Isolated CPU spike in sampled intervals; not sustained-pressure evidence')
    if sum(r['iowait_pct'] >= 20 for r in samples) >= 2:
        add('WARNING', category, 'Repeated high I/O wait in sampled intervals; correlate storage latency')
    if sum(r['steal_pct'] >= 5 for r in samples) >= 2:
        add('WARNING', category, 'Repeated CPU steal in sampled intervals; inspect host scheduling')
    paging = sum(r['swap_in_kib_s'] > 0 or r['swap_out_kib_s'] > 0 for r in samples)
    if paging:
        add('WARNING' if paging >= 2 else 'INFO', category,
            'Paging observed in {0}/{1} intervals; mean in/out {2:.1f}/{3:.1f} KiB/s. Not by itself proof of thrashing.'.format(
             paging,len(samples),weighted('swap_in_kib_s'),weighted('swap_out_kib_s')))
    else:
        add('INFO', category, 'No paging observed during sampled intervals; allocated swap alone is not active pressure')
    return True


def check_os(nodes):
    section("OPERATING SYSTEM HEALTH")
    bad = False
    command = ("export LC_ALL=C; echo __KERNEL__; uname -r; "
               "echo __SELINUX__; if command -v getenforce >/dev/null 2>&1; then getenforce; "
               "elif test -r /sys/fs/selinux/enforce; then "
               "case $(cat /sys/fs/selinux/enforce) in 1) echo Enforcing;; 0) echo Permissive;; *) echo UNKNOWN;; esac; "
               "else echo UNKNOWN; fi; "
               "echo __MEM__; free -m; "
               "echo __HUGE__; grep -E '^(HugePages_Total|HugePages_Free|Hugepagesize):' /proc/meminfo; "
               "cat /sys/kernel/mm/transparent_hugepage/enabled; "
               "echo __DF__; df -Pk -x tmpfs -x devtmpfs && "
               "python3 -c " + shlex.quote(OS_SAMPLER) + " {0} {1}".format(CFG.os_samples, CFG.sample_seconds))
    for node in nodes:
        rc, out = collect_node(node, command)
        display = '\n'.join(line for line in out.splitlines() if not line.startswith('OS_SAMPLE|'))
        print("\n--- {0} ---\n{1}".format(node, display))
        category = "OS:" + node
        if rc != 0:
            add("WARNING", category, "OS collection failed/incomplete (exit {0})".format(rc))
            bad = True
            continue
        kernel = re.search(r"__KERNEL__\s*\n([^\n]+)", out)
        selinux = re.search(r"__SELINUX__\s*\n(Enforcing|Permissive|Disabled)\s*(?:\n|$)", out)
        mode = selinux.group(1) if selinux else 'UNKNOWN'
        METRICS.setdefault('os', {}).setdefault(node, {})['selinux_mode'] = mode
        if mode == 'UNKNOWN':
            add('WARNING', category, 'SELinux mode could not be established')
            bad = True
        elif mode == 'Permissive':
            add('INFO', category, 'SELinux is Permissive: AVC messages record policy violations without SELinux enforcement; no mode change performed')
        elif mode == 'Disabled':
            add('INFO', category, 'SELinux is Disabled; no mode change performed')
        mem = re.search(r"^Mem:\s+(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)", out, re.M)
        swap = re.search(r"^Swap:\s+(\d+)\s+(\d+)", out, re.M)
        huge = re.search(r"^HugePages_Total:\s+(\d+)", out, re.M)
        filesystems = []
        for line in out.splitlines():
            fields = line.split()
            if len(fields) >= 6 and re.match(r"^\d+%$", fields[4]):
                filesystems.append((int(fields[4][:-1]), fields[5]))
        thp = re.search(r"\[(?:always|madvise|never)\]", out)
        if not all((kernel, mem, swap, huge, thp, filesystems)):
            add("WARNING", category, "One or more OS metrics missing/unparseable")
            bad = True
        if kernel:
            KERNELS[node] = kernel.group(1).strip()
        if mem and int(mem.group(1)):
            pct = int(mem.group(2)) * 100.0 / int(mem.group(1))
            if pct < 10:
                add("WARNING", category, "Available memory is {0:.1f}%".format(pct))
        if swap and int(swap.group(1)):
            pct = int(swap.group(2)) * 100.0 / int(swap.group(1))
            if pct >= 50:
                add("WARNING", category, "Swap allocation is {0:.1f}%; check paging rates before inferring pressure".format(pct))
        if not evaluate_os_samples(out, node):
            bad = True
        METRICS.setdefault("os", {}).setdefault(node, {}).update({
            "kernel": kernel.group(1).strip() if kernel else None,
            "memory_total_mib": int(mem.group(1)) if mem else None,
            "memory_available_mib": int(mem.group(2)) if mem else None,
            "swap_used_mib": int(swap.group(2)) if swap else None,
            "filesystems": [{"mount": mount, "used_pct": pct} for pct, mount in filesystems]})
        if huge and int(huge.group(1)) == 0:
            add("INFO", category, "Explicit HugePages not configured; size against the intended SGA")
        if "[always]" in out:
            add("WARNING", category, "THP always enabled; review release/kernel guidance (26ai UEK7+ recommends madvise)")
        for pct, mount in filesystems:
            if pct >= 80:
                add("CRITICAL" if pct >= 90 else "WARNING", category,
                    "Filesystem {0} is {1}% full".format(mount, pct))
    coverage["OS nodes"] = "INCOMPLETE" if bad else "COLLECTED"


def parse_resource_rows(out):
    """19c and 26ai tables, including '(ora.asmgroup)' resource suffixes."""
    rows, resource = [], None
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or stripped.startswith("Name "):
            continue
        if stripped in ("Local Resources", "Cluster Resources"):
            continue
        if not line[0].isspace():
            resource = stripped
            continue
        fields = stripped.split()
        if fields and fields[0].isdigit():
            fields = fields[1:]
        if resource and len(fields) >= 2 and fields[0] in ("ONLINE", "OFFLINE"):
            rows.append((resource.split("(", 1)[0], fields[0], fields[1], " ".join(fields[2:])))
    return rows


def check_cluster(nodes):
    section("CLUSTERWARE AND NETWORK HEALTH")
    commands = [("Cluster status", "crsctl", "check", "cluster", "-all"),
                ("Cluster nodes", "olsnodes", "-n", "-s", "-t"),
                ("Cluster resources", "crsctl", "stat", "res", "-t"),
                ("SCAN status", "srvctl", "status", "scan"),
                ("SCAN listeners", "srvctl", "status", "scan_listener"),
                ("Node listeners", "srvctl", "status", "listener")]
    bad = False
    for entry in commands:
        title = entry[0]
        rc, out = tool(GRID_HOME, entry[1], *entry[2:])
        print("\n--- {0} ---\n{1}".format(title, out or "No output"))
        if rc != 0 or not out:
            add("CRITICAL" if title.startswith("Cluster") else "WARNING", "Clusterware",
                "{0} collection failed/empty (exit {1})".format(title, rc))
            bad = True
            continue
        if title == "Cluster status":
            blocks = re.findall(r"^(\S+):\s*\n(.*?)(?=^\S+:\s*$|\Z)", out, re.M | re.S)
            seen = dict((short_host(node), text) for node, text in blocks)
            for node in nodes:
                text = seen.get(short_host(node), "")
                if not all(code in text for code in ("CRS-4537", "CRS-4529", "CRS-4533")):
                    add("CRITICAL", "Clusterware", "Missing ONLINE CRS/CSS/EVM confirmation for " + node)
        elif title == "Cluster nodes":
            parsed = [line.split() for line in out.splitlines() if re.match(r"^\S+\s+\d+\s+", line)]
            if not parsed:
                add("WARNING", "Clusterware", "Node-state output could not be parsed")
                bad = True
            for fields in parsed:
                if fields[2].lower() != "active":
                    add("CRITICAL", "Clusterware", "Node {0} is {1}".format(fields[0], fields[2]))
        elif title == "Cluster resources":
            rows = parse_resource_rows(out)
            if not rows:
                add("WARNING", "Clusterware", "Resource table could not be parsed")
                bad = True
            for resource, target, state, details in rows:
                if target == "ONLINE" and (state != "ONLINE" or "FAILED OVER" in details):
                    severity = "CRITICAL" if resource.endswith((".db", ".dg")) or resource == "ora.asm" else "WARNING"
                    add(severity, "Clusterware", "{0}: target {1}, state {2}, {3}".format(resource, target, state, details))
        elif re.search(r"\bnot running\b|\bdisabled\b", out, re.I):
            add("WARNING", "Clusterware", title + " reports a stopped/disabled component; review intended configuration")
    for node in nodes:
        rc, out = tool(GRID_HOME, "srvctl", "status", "vip", "-node", node)
        print("\n--- VIP {0} ---\n{1}".format(node, out))
        if rc != 0 or not out:
            add("WARNING", "Clusterware", "VIP check failed/empty for " + node)
            bad = True
        elif "not running" in out.lower():
            add("WARNING", "Clusterware", "VIP is not running for " + node)
    coverage["Clusterware"] = "INCOMPLETE" if bad else "COLLECTED"


DB_QUERY = """
select 'INST|'||inst_id||'|'||instance_name||'|'||host_name||'|'||status||'|'||database_status
from gv$instance order by inst_id;
select 'CDB|'||name||'|'||open_mode from v$database;
select 'DBUNQ|'||db_unique_name from v$database;
select 'DBTYPE|'||cdb from v$database;
select 'PDB|'||inst_id||'|'||name||'|'||open_mode from gv$pdbs order by inst_id,con_id;
select 'LOG|'||log_mode from v$database;
select 'FRA|'||nvl(name,'UNCONFIGURED')||'|'||nvl(to_char(round((space_used-space_reclaimable)*100/nullif(space_limit,0),1)),'UNKNOWN')
from v$recovery_file_dest;
select 'VERSION|'||version_full from v$instance;
select 'TRACE|'||value from v$diag_info where name='Diag Trace';
"""


def tagged_rows(text):
    return [tuple(item.strip() for item in line.strip().split("|"))
            for line in text.splitlines() if "|" in line]


def evaluate_database(out):
    global DB_VERSION, DB_OPERATIONAL
    rows = tagged_rows(out)
    METRICS['database_sql'] = rows
    required = {"INST", "CDB", "DBUNQ", "DBTYPE", "LOG", "FRA", "VERSION"}
    seen = set(row[0] for row in rows)
    missing = sorted(required - seen)
    if missing:
        add("CRITICAL", "Database", "SQL results incomplete; missing " + ", ".join(missing))
        return False
    widths = {"CDB": 3, "DBUNQ": 2, "DBTYPE": 2, "LOG": 2, "FRA": 3, "VERSION": 2}
    for tag, width in widths.items():
        matching = [row for row in rows if row[0] == tag]
        if len(matching) != 1 or len(matching[0]) != width:
            add("CRITICAL", "Database", "Malformed/duplicate SQL result for " + tag)
            return False
    if not any(row in (("DBTYPE", "YES"), ("DBTYPE", "NO")) for row in rows):
        add("CRITICAL", "Database", "CDB/non-CDB type could not be established")
        return False
    instances = [row for row in rows if row[0] == "INST" and len(row) == 6 and row[1].isdigit()]
    if not instances:
        add("CRITICAL", "Database", "No valid database instance rows returned")
        return False
    if len(instances) != sum(row[0] == "INST" for row in rows):
        add("CRITICAL", "Database", "Malformed database instance row")
        return False
    unique = [row[1] for row in rows if row[0] == "DBUNQ" and len(row) == 2]
    if unique != [CFG.db] and [v.upper() for v in unique] != [CFG.db.upper()]:
        add("CRITICAL", "Database", "SQL connected to a different/unknown DB_UNIQUE_NAME; check local SID")
        return False
    found = set(row[2].upper() for row in instances)
    if not EXPECTED_INSTANCES:
        add("WARNING", "Database", "Expected database instance inventory unavailable; completeness cannot be established")
    for name in EXPECTED_INSTANCES:
        if name.upper() not in found:
            add("CRITICAL", "Database", "Configured instance missing from GV$INSTANCE: " + name)
    DB_OPERATIONAL = all(row[4] == "OPEN" for row in instances)
    for row in instances:
        if row[4] != "OPEN":
            add("CRITICAL", "Database", "Instance {0} is {1}".format(row[2], row[4]))
        if row[5] != "ACTIVE":
            add("WARNING", "Database", "Instance {0} database_status is {1}".format(row[2], row[5]))
    for row in rows:
        if row[0] == "CDB":
            if len(row) != 3:
                add("CRITICAL", "Database", "Malformed database open-mode result")
            elif row[2] != "READ WRITE":
                add("CRITICAL", "Database", "Database {0} is {1}".format(row[1], row[2]))
        elif row[0] == "LOG":
            if len(row) != 2 or row[1] != "ARCHIVELOG":
                add("WARNING", "Database", "ARCHIVELOG mode not confirmed")
        elif row[0] == "FRA":
            try:
                used = float(row[2])
                if len(row) != 3 or row[1] == "UNCONFIGURED" or not math.isfinite(used) or not 0 <= used <= 100:
                    raise ValueError()
                if used >= 80:
                    add("CRITICAL" if used >= 90 else "WARNING", "FRA",
                        "Non-reclaimable FRA usage is {0:.1f}%".format(used))
            except (ValueError, IndexError):
                add("WARNING", "FRA", "FRA destination/usage unavailable or unparseable")
        elif row[0] == "VERSION":
            if len(row) == 2 and re.match(r"^\d+\.\d+", row[1]):
                DB_VERSION = row[1]
            else:
                add("WARNING", "Database", "Runtime version could not be parsed")
    pdbs = [row for row in rows if row[0] == "PDB" and len(row) == 4]
    is_cdb = any(row == ("DBTYPE", "YES") for row in rows)
    expected_pdbs = split_list(CFG.pdb) or sorted(set(row[2] for row in pdbs if row[2] != "PDB$SEED"))
    if is_cdb and not pdbs:
        add("WARNING", "PDB", "CDB detected but no PDB rows returned")
    for row in pdbs:
        wanted = "READ ONLY" if row[2] == "PDB$SEED" else "READ WRITE"
        if row[3] != wanted:
            add("WARNING", "PDB", "{0} on inst_id {1} is {2}; check intended policy".format(row[2], row[1], row[3]))
    for pdb in expected_pdbs:
        for inst in instances:
            if not any(row[1] == inst[1] and row[2].upper() == pdb.upper() for row in pdbs):
                add("WARNING", "PDB", "Missing PDB row for {0} on {1}".format(pdb, inst[2]))
    return True


def trace_alert(out, sid):
    paths = [row[1] for row in tagged_rows(out) if row[0] == "TRACE" and len(row) == 2]
    return os.path.join(paths[0], "alert_" + sid + ".log") if len(paths) == 1 and os.path.isabs(paths[0]) else None


def check_database(sid):
    global DB_ALERT
    section("RAC DATABASE HEALTH")
    bad = False
    for title, args in [("Database configuration", ("config", "database")),
                        ("Database status", ("status", "database", "-verbose")),
                        ("Database services", ("status", "service"))]:
        rc, out = tool(GRID_HOME, "srvctl", *(list(args) + ["-db", CFG.db]))
        print("\n--- {0} ---\n{1}".format(title, out or "No output"))
        expected_service = bool(DB_CONFIG.get("Services", ""))
        if rc != 0 or (not out and (title != "Database services" or expected_service)):
            add("CRITICAL" if title == "Database status" else "WARNING", "Database",
                title + " failed/empty; coverage incomplete")
            bad = True
        elif re.search(r"\bnot running\b", out, re.I):
            add("CRITICAL" if title == "Database status" else "WARNING", "Database", title + " reports stopped components")
        if title == "Database services" and rc == 0:
            for service in split_list(DB_CONFIG.get("Services", "")):
                if not re.search(r"Service\s+" + re.escape(service) + r"\s+is running on instance", out, re.I):
                    add("WARNING", "Database", "Running service not confirmed in SRVCTL output: " + service)
                    bad = True
    rc, out = sqlplus(DB_QUERY, sid, DB_HOME)
    print("\n--- SQL validation ---\n" + out)
    if rc != 0:
        add("CRITICAL", "Database", "Database SQL collection failed (exit {0})".format(rc))
        bad = True
    else:
        bad = not evaluate_database(out) or bad
        DB_ALERT = trace_alert(out, sid) if sid else None
    coverage["Database SQL/services"] = "INCOMPLETE" if bad else "COLLECTED"


ASM_QUERY = """
select 'ASM_INST|'||inst_id||'|'||instance_name||'|'||host_name from gv$instance order by inst_id;
select 'ASM_DG|'||inst_id||'|'||name||'|'||state||'|'||total_mb||'|'||free_mb||'|'||offline_disks||'|'||usable_file_mb
from gv$asm_diskgroup_stat order by inst_id,name;
select 'ASM_DISK|'||inst_id||'|'||path||'|'||header_status||'|'||mount_status||'|'||mode_status||'|'||state||'|'||group_number
from gv$asm_disk_stat order by inst_id,path;
select 'TRACE|'||value from v$diag_info where name='Diag Trace';
"""


def evaluate_asm(out):
    rows = tagged_rows(out)
    instances = [r for r in rows if r[0] == "ASM_INST" and len(r) == 4]
    groups = [r for r in rows if r[0] == "ASM_DG" and len(r) == 8]
    disks = [r for r in rows if r[0] == "ASM_DISK" and len(r) == 8]
    if not all((instances, groups, disks)):
        add("CRITICAL", "ASM", "ASM SQL results incomplete/empty (instances, diskgroups or disks missing)")
        return False
    for row in groups:
        try:
            total, free, offline, usable = [float(v) for v in row[4:8]]
            if not all(math.isfinite(v) for v in (total, free, offline, usable)) or total <= 0 or free < 0:
                raise ValueError()
            if row[3] != "MOUNTED" or offline != 0 or usable < 0:
                add("CRITICAL", "ASM", "Diskgroup {0}, inst_id {1}: state={2}, offline_disks={3}, usable_file_mb={4}".format(row[2], row[1], row[3], row[6], row[7]))
            pct = free * 100 / total
            if pct < 20:
                add("CRITICAL" if pct < 10 else "WARNING", "ASM", "{0} on inst_id {1}: raw free {2:.1f}%; usable_file_mb={3}".format(row[2], row[1], pct, row[7]))
        except ValueError:
            add("WARNING", "ASM", "Unparseable capacity row for " + row[2])
    for row in disks:
        if not row[7].isdigit():
            add("WARNING", "ASM", "Malformed group number for disk " + row[2])
        elif int(row[7]) == 0:
            add("INFO", "ASM", "Unassigned disk {0}: header={1}; not an active diskgroup member".format(row[2], row[3]))
        elif row[3:7] != ("MEMBER", "CACHED", "ONLINE", "NORMAL"):
            add("CRITICAL", "ASM", "Disk {0}, inst_id {1}: {2}".format(row[2], row[1], "/".join(row[3:7])))
    for inst in instances:
        if not any(row[1] == inst[1] for row in groups):
            add("WARNING", "ASM", "No diskgroup rows for observed ASM instance " + inst[2])
        for group_name in set(row[2] for row in groups):
            if not any(row[1] == inst[1] and row[2] == group_name for row in groups):
                add("WARNING", "ASM", "{0} not returned on observed ASM instance {1}; review intended mount policy".format(group_name, inst[2]))
    return True


def check_asm(sid):
    global ASM_ALERT
    section("ASM HEALTH")
    rc, out = run(["id", "-nG"])
    if rc != 0 or CFG.osasm_group not in out.split():
        print("SYSASM checks skipped: current user lacks the configured OSASM group ({0}).".format(CFG.osasm_group))
        add("WARNING", "ASM", "SYSASM coverage incomplete; run as the authorized Grid owner (no privilege changes required)")
        coverage["ASM SQL/CLI"] = "SKIPPED"
        return
    bad = False
    env = oracle_env(GRID_HOME, sid, GRID_BASE)
    for title, binary, args in [("ASM status", "srvctl", ("status", "asm", "-detail")),
                                ("ASM diskgroups", "asmcmd", ("lsdg",))]:
        rc, out = tool(GRID_HOME, binary, *args, env=env)
        print("\n--- {0} ---\n{1}".format(title, out or "No output"))
        if rc != 0 or not out:
            add("CRITICAL", "ASM", title + " failed/empty")
            bad = True
    rc, out = sqlplus(ASM_QUERY, sid, GRID_HOME, sysasm=True)
    print("\n--- ASM SQL validation ---\n" + out)
    if rc != 0:
        add("CRITICAL", "ASM", "ASM SQL collection failed (exit {0})".format(rc))
        bad = True
    else:
        bad = not evaluate_asm(out) or bad
        ASM_ALERT = trace_alert(out, sid) if sid else None
    coverage["ASM SQL/CLI"] = "INCOMPLETE" if bad else "COLLECTED"


def read_tail(path, lines):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            position, chunks, count, size = handle.tell(), [], 0, 0
            while position > 0 and count <= lines and size < 8 * 1024 * 1024:
                amount = min(position, 65536, 8 * 1024 * 1024 - size)
                position -= amount
                handle.seek(position)
                block = handle.read(amount)
                chunks.append(block)
                count += block.count(b"\n")
                size += len(block)
            data = b"".join(reversed(chunks))
            return 0, b"".join(data.splitlines(True)[-lines:]).decode("utf-8", "replace")
    except OSError as exc:
        return 1, str(exc)


def parse_alert_time(line):
    """Oracle 19c/26ai ISO timestamps, plus legacy local text timestamps."""
    value = line.strip()
    match = re.match(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)$", value)
    formats = []
    if match:
        value = value.replace("T", " ")
        value = re.sub(r"Z$", "+0000", value)
        value = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", value)
        suffix = "%z" if re.search(r"[+-]\d{4}$", value) else ""
        formats = ["%Y-%m-%d %H:%M:%S.%f" + suffix,
                   "%Y-%m-%d %H:%M:%S" + suffix]
    else:
        formats = ["%a %b %d %H:%M:%S %Y"]
    for fmt in formats:
        try:
            result = datetime.strptime(value, fmt)
            return result.astimezone(timezone.utc)
        except ValueError:
            pass
    return None


ALERT_PATTERN = re.compile(r"ORA-\d{5}|TNS-\d{5}|RMAN-\d{5}|CRS-\d{4}|WARNING:|Errors in file|Process .* died|diskgroup .* incomplete|I/O error", re.I)


def alert_events(text, now, hours):
    current, events = None, []
    cutoff = now - timedelta(hours=hours)
    for line in text.splitlines():
        stamp = parse_alert_time(line)
        if stamp is not None:
            current = stamp
        if ALERT_PATTERN.search(line) and "If any errors are encountered" not in line:
            kind = ("UNDATED" if current is None else "FUTURE" if current > now + timedelta(minutes=5)
                    else "IN WINDOW" if current >= cutoff else "HISTORICAL")
            events.append((kind, current, line.strip()))
    return events


def review_alert(path):
    rc, out = read_tail(path, CFG.alert_lines)
    print("\n--- Local alert: {0} ---".format(path))
    if rc != 0:
        print("UNREADABLE: " + out)
        add("WARNING", "AlertLog", "Unable to read " + path + "; not a clean check")
        return False
    if not out.strip():
        add("WARNING", "AlertLog", "Alert log is empty; coverage unavailable: " + path)
        return False
    now = datetime.now(timezone.utc)
    events = alert_events(out, now, CFG.alert_hours)
    counts = dict((key, sum(e[0] == key for e in events)) for key in
                  ("IN WINDOW", "HISTORICAL", "UNDATED", "FUTURE"))
    print("Last {0} lines only; lookback {1:g}h. Counts: {2}".format(CFG.alert_lines, CFG.alert_hours, counts))
    stamps = [parse_alert_time(line) for line in out.splitlines()]
    stamps = [stamp for stamp in stamps if stamp is not None]
    earliest, latest = (min(stamps), max(stamps)) if stamps else (None, None)
    spans = earliest is not None and earliest <= now - timedelta(hours=CFG.alert_hours)
    codes = Counter(code.upper() for kind, stamp, line in events if kind == 'IN WINDOW'
                    for code in set(re.findall(r'(?:ORA|TNS|RMAN)-\d{5}|CRS-\d{4}', line, re.I)))
    METRICS.setdefault('alerts', {})[path] = {
        'lookback_hours': CFG.alert_hours, 'matching_line_counts': counts,
        'in_window_codes': dict(codes),
        'earliest_sample_timestamp': earliest.isoformat() if earliest else None,
        'latest_sample_timestamp': latest.isoformat() if latest else None,
        'sample_reaches_window_start': spans,
        'scope': 'bounded local sample; not a complete incident inventory'}
    print('Error-code matching-line counts in window (not incident counts): ' + str(dict(codes)))
    if earliest:
        print('Sample timestamp range: {0} to {1} (collector local timezone).'.format(
              earliest.astimezone().isoformat(), latest.astimezone().isoformat()))
    print('Sample reaches window start: {0}; rotated logs and gaps are not checked.'.format('YES' if spans else 'NO/UNKNOWN'))
    # Retain old evidence; do not relabel it as a current fault.
    selected = [e for e in events if e[0] != 'HISTORICAL'][-20:]
    selected += [e for e in events if e[0] == 'HISTORICAL'][-max(0, 20-len(selected)):] if len(selected) < 20 else []
    for kind, stamp, line in selected:
        print("[{0}] [{1}] {2}".format(kind, stamp.astimezone().isoformat() if stamp else "timestamp unknown", line))
    if counts["IN WINDOW"]:
        add("WARNING", "AlertLog", "{0}: {1} matching lines in lookback; correlate events before declaring an active fault".format(os.path.basename(path), counts["IN WINDOW"]))
    if counts["UNDATED"] or counts["FUTURE"]:
        add("WARNING", "AlertLog", "{0}: unknown/future event timestamps; review context/clock".format(os.path.basename(path)))
    if counts["HISTORICAL"]:
        add("INFO", "AlertLog", "{0}: {1} older matching lines retained as history".format(os.path.basename(path), counts["HISTORICAL"]))
    if not events:
        print("No matching error lines in the bounded sample; not proof of a complete clean time window.")
    return True


def fallback_alert(base, kind, sid):
    if not sid:
        return None
    paths = glob.glob(os.path.join(base, "diag", kind, "*", "*", "trace", "alert_*.log"))
    matches = [path for path in paths if os.path.basename(path).lower() == ("alert_" + sid + ".log").lower()]
    return matches[0] if len(matches) == 1 else None


def check_local_logs(db_sid, asm_sid):
    section("LOCAL DBCA AND ALERT REVIEW")
    print("Local node only; run on each node for its local history. Bounded samples are not exhaustive.")
    # Scope DBCA discovery to this database, not the most recent unrelated DB.
    root = CFG.dbca_dir or os.path.join(DB_BASE, "cfgtoollogs", "dbca")
    candidates = []
    wanted = {CFG.db.lower(), DB_CONFIG.get("Database name", CFG.db).lower()}
    expected_here = bool(CFG.dbca_node and short_host(CFG.dbca_node) == short_host(socket.gethostname()))
    try:
        if CFG.dbca_dir:
            os.listdir(root)  # explicit missing/unreadable path must not silently pass os.walk
        roots = ([root] if CFG.dbca_dir else
                 [os.path.join(root, name) for name in os.listdir(root) if name.lower() in wanted])
        for start in roots:
            def walk_error(exc):
                raise exc
            for directory, _, files in os.walk(start, onerror=walk_error):
                for name in files:
                    if name.startswith("trace.log_") or name.endswith((".log", ".trace")):
                        path = os.path.join(directory, name)
                        candidates.append(path)
        latest = max(candidates, key=os.path.getmtime) if candidates else None
    except FileNotFoundError as exc:
        latest = None
        if CFG.dbca_dir or expected_here:
            add("WARNING", "DBCA", "Expected local DBCA evidence path missing: " + str(exc))
        else:
            add("INFO", "DBCA", "No local DBCA directory; DBCA may have run on another node. Not an availability failure.")
    except OSError as exc:
        latest = None
        add("WARNING", "DBCA", "DBCA discovery could not be completed: " + str(exc))
    if latest:
        rc, out = read_tail(latest, 4000)
        print("\nLatest local DBCA log: " + latest)
        if rc != 0:
            add("WARNING", "DBCA", "DBCA log unreadable: " + latest)
        else:
            markers = [line for line in out.splitlines() if
                       re.search(r"overall status|Database creation complete|DBCA_PROGRESS\s*:\s*100%", line, re.I)]
            print("\n".join(markers[-10:]) or "No completion marker in this sample; DBCA outcome unverified")
            terminal = [line for line in markers if re.search(r"overall status|Database creation complete", line, re.I)]
            if terminal and re.search(r"overall status.*fail", terminal[-1], re.I):
                add("WARNING", "DBCA", "Latest sampled DBCA outcome failed; historical result, assess against current DB state")
    else:
        print("No local DBCA log discovered for this database; creation outcome unverified by this check.")
        add("INFO", "DBCA", "DBCA completion log unavailable; not itself a current availability failure")
        if expected_here and not any(f.category == 'DBCA' and f.severity == 'WARNING' for f in findings):
            add('WARNING', 'DBCA', 'DBCA evidence expected on this node but no creation log discovered')
    paths = [("DB", CFG.db_alert or DB_ALERT or fallback_alert(DB_BASE, "rdbms", db_sid)),
             ("ASM", CFG.asm_alert or ASM_ALERT or fallback_alert(GRID_BASE, "asm", asm_sid))]
    bad = False
    for kind, path in paths:
        if not path or not os.path.isabs(path):
            add("WARNING", "AlertLog", kind + " alert path not discovered; use --db-alert/--asm-alert")
            bad = True
        else:
            bad = not review_alert(path) or bad
    coverage["Local alerts"] = "INCOMPLETE" if bad else "SAMPLED (LOCAL ONLY)"


def check_compatibility():
    # Dated documentation check, not a substitute for complete OPatch inventories.
    # https://docs.oracle.com/en/database/oracle/oracle-database/26/cwlin/supported-oracle-linux-9-distributions-for-x86-64.html
    if DB_VERSION and re.match(r"^23\.26\.1(?:\.|$)", DB_VERSION):
        for node, kernel in KERNELS.items():
            if kernel.startswith("6.12.") and "el9uek" in kernel:
                add("WARNING", "Compatibility", node + ": reported 23.26.1 runtime with OL9 UEK8; documented UEK8 support starts at RU 23.26.2. Review full Grid/DB patch inventories and kernel certification.")
    add("INFO", "Scope", "Full patch inventories/certification, SCAN client login, backup/recovery and failover are not tested")


def final_report():
    section("OPERATIONAL ASSESSMENT")
    critical = [f for f in findings if f.severity == "CRITICAL"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    # No clean conclusion if any required collection was skipped or incomplete.
    for key, value in coverage.items():
        print("Coverage: {0}: {1}".format(key, value))
    if any(value in ("INCOMPLETE", "SKIPPED") for value in coverage.values()) and not warnings:
        add("WARNING", "Coverage", "Required collection incomplete; healthy state cannot be concluded")
        warnings = [f for f in findings if f.severity == "WARNING"]
    status = "CRITICAL" if critical else "REVIEW REQUIRED" if warnings else "NO FINDINGS IN COMPLETED CHECKS"
    print("Overall assessment: " + status)
    if DB_OPERATIONAL:
        print("Observed database instances are OPEN; check the individual instance/service findings and coverage above.")
    print("This read-only snapshot does not establish client connectivity, tested failover, backup recoverability or certification.")
    for f in sorted(findings, key=lambda item: {"CRITICAL": 0, "WARNING": 1, "INFO": 2}[item.severity]):
        print("[{0:<8}] [{1}] {2}".format(f.severity, f.category, f.message))
    print("Critical findings: {0}; warnings: {1}".format(len(critical), len(warnings)))
    return 2 if critical else 1 if warnings else 0


def save_json_report(path, exit_code):
    """Exclusive private output: never overwrite an existing file or symlink."""
    destination = os.path.abspath(os.path.expanduser(path))
    report = {
        'schema_version': 1, 'revision': REVISION,
        'started_at': STARTED_AT, 'finished_at': datetime.now().astimezone().isoformat(),
        'host': socket.gethostname(), 'database': CFG.db, 'database_version': DB_VERSION,
        'observed_instances_open': DB_OPERATIONAL, 'exit_code': exit_code,
        'coverage': coverage, 'metrics': METRICS,
        'findings': [dict(severity=f.severity, category=f.category, message=f.message) for f in findings],
        'limitations': ['Local bounded alert samples only', 'No client login or failover test',
                        'No backup/recovery validation or certification assessment',
                        'No OPatch inventory or SQL patch registry collection']}
    fd, temporary = tempfile.mkstemp(prefix='.rac-health-', dir=os.path.dirname(destination))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n')
        os.link(temporary, destination)  # atomic no-clobber publication, mode 0600
    finally:
        os.unlink(temporary)


def main(argv=None):
    global CFG, DB_VERSION, DB_OPERATIONAL, DB_ALERT, ASM_ALERT, STARTED_AT
    findings[:] = []
    coverage.clear()
    KERNELS.clear()
    METRICS.clear()
    STARTED_AT = datetime.now().astimezone().isoformat()
    DB_VERSION, DB_OPERATIONAL, DB_ALERT, ASM_ALERT = None, False, None, None
    CFG = build_parser().parse_args(argv)
    try:
        if (not math.isfinite(CFG.alert_hours) or CFG.alert_hours <= 0 or
                not 1 <= CFG.alert_lines <= 100000 or not 1 <= CFG.timeout <= 300):
            raise ConfigError("Use positive alert-hours, 1..100000 alert-lines, and 1..300 timeout")
        if (not 2 <= CFG.os_samples <= 10 or not math.isfinite(CFG.sample_seconds) or
                not 0.2 <= CFG.sample_seconds <= 5 or CFG.os_samples*CFG.sample_seconds + 5 > CFG.timeout):
            raise ConfigError('Use 2..10 OS samples, 0.2..5 sample-seconds, and timeout >= samples*seconds + 5')
        if CFG.dbca_node and not re.match(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$', CFG.dbca_node):
            raise ConfigError('Invalid DBCA node name')
        if not re.match(r"^[A-Za-z0-9_+$#.-]+$", CFG.db):
            raise ConfigError("Invalid database unique name")
        discover_config()
        nodes = discover_nodes()
        db_sid, asm_sid = local_sid(), local_sid(asm=True)
    except (ConfigError, ValueError) as exc:
        print("CONFIGURATION ERROR: " + str(exc))
        return 3
    print("ORACLE RAC HEALTH SNAPSHOT — revision " + REVISION)
    print("Collected at: " + datetime.now().astimezone().isoformat())
    print("Host: {0}; database: {1}; nodes: {2}".format(socket.gethostname(), CFG.db, ", ".join(nodes)))
    print("Grid home/base: {0} / {1}".format(GRID_HOME, GRID_BASE))
    print("DB home/base: {0} / {1}".format(DB_HOME, DB_BASE))
    print("Local DB SID: {0}; local ASM SID: {1}".format(db_sid, asm_sid))
    for label, check in [("OS", lambda: check_os(nodes)),
                         ("Clusterware", lambda: check_cluster(nodes)),
                         ("Database", lambda: check_database(db_sid)),
                         ("ASM", lambda: check_asm(asm_sid)),
                         ("Logs", lambda: check_local_logs(db_sid, asm_sid))]:
        try:
            check()
        except (OSError, ValueError, IndexError, KeyError) as exc:
            add("WARNING", label, "Collection incomplete: " + str(exc))
            coverage[label] = "INCOMPLETE"
    check_compatibility()
    result = final_report()
    if CFG.json_out:
        try:
            save_json_report(CFG.json_out, result)
            print('JSON report saved: ' + os.path.abspath(os.path.expanduser(CFG.json_out)))
        except (OSError, ValueError) as exc:
            print('REPORT SAVE FAILED (use a new filename): ' + str(exc), file=sys.stderr)
            return max(result, 1)
    return result


if __name__ == "__main__":
    sys.exit(main())
