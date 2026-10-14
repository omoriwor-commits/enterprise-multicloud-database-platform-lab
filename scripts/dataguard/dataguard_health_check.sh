#!/usr/bin/env bash
#
# Oracle Data Guard Health Check Command Pack
#
# Purpose:
#   Run a practical Oracle Data Guard health review against the current database
#   and, when configured, perform connectivity and broker checks.
#
# Compatibility target:
#   Oracle Database 19c+
#
# Security:
#   - No passwords are embedded.
#   - Uses OS authentication: sqlplus / as sysdba
#   - DGMGRL uses OS authentication when available.
#
# Usage:
#   chmod 750 dataguard_health_check.sh
#   ./dataguard_health_check.sh
#
# Optional environment overrides:
#   PRIMARY_TNS=RAC_PRIMARY
#   STANDBY_TNS=RAC_STANDBY
#   PRIMARY_DB_UNIQUE_NAME=RAC
#   STANDBY_DB_UNIQUE_NAME=RACDG
#   ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1
#
# Example:
#   PRIMARY_TNS=RAC_PRIMARY \
#   STANDBY_TNS=RAC_STANDBY \
#   PRIMARY_DB_UNIQUE_NAME=RAC \
#   STANDBY_DB_UNIQUE_NAME=RACDG \
#   ./dataguard_health_check.sh
#

set -u
set -o pipefail

PRIMARY_TNS="${PRIMARY_TNS:-PRIMARY_TNS}"
STANDBY_TNS="${STANDBY_TNS:-STANDBY_TNS}"
PRIMARY_DB_UNIQUE_NAME="${PRIMARY_DB_UNIQUE_NAME:-PRIMARY_DB_UNIQUE_NAME}"
STANDBY_DB_UNIQUE_NAME="${STANDBY_DB_UNIQUE_NAME:-STANDBY_DB_UNIQUE_NAME}"

SQLPLUS="${ORACLE_HOME:+$ORACLE_HOME/bin/}sqlplus"
DGMGRL="${ORACLE_HOME:+$ORACLE_HOME/bin/}dgmgrl"
LSNRCTL="${ORACLE_HOME:+$ORACLE_HOME/bin/}lsnrctl"
TNSPING="${ORACLE_HOME:+$ORACLE_HOME/bin/}tnsping"

WARNINGS=0
FAILURES=0
DB_ROLE="UNKNOWN"
DB_UNIQUE_NAME="UNKNOWN"
OPEN_MODE="UNKNOWN"

line() {
    printf '%*s\n' 79 '' | tr ' ' '#'
}

section() {
    echo
    line
    printf '# %s\n' "$1"
    line
}

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

run_cmd() {
    echo "+ $*"
    "$@"
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "[WARN] command returned rc=$rc"
        WARNINGS=$((WARNINGS + 1))
    fi
    return 0
}

sql() {
    "$SQLPLUS" -s / as sysdba <<SQL
set lines 220 pages 200 trimspool on tab off verify off feedback on
whenever sqlerror continue
$1
exit
SQL
}

sql_quiet() {
    "$SQLPLUS" -s / as sysdba <<SQL
set heading off feedback off pages 0 verify off echo off trimspool on
whenever sqlerror exit sql.sqlcode
$1
exit
SQL
}

discover_role() {
    local out
    out="$(sql_quiet "select database_role||'|'||db_unique_name||'|'||open_mode from v\$database;" 2>/dev/null || true)"
    if [ -n "$out" ]; then
        IFS='|' read -r DB_ROLE DB_UNIQUE_NAME OPEN_MODE <<< "$(echo "$out" | head -1)"
        DB_ROLE="$(echo "$DB_ROLE" | xargs)"
        DB_UNIQUE_NAME="$(echo "$DB_UNIQUE_NAME" | xargs)"
        OPEN_MODE="$(echo "$OPEN_MODE" | xargs)"
    fi
}

is_primary() {
    [ "$DB_ROLE" = "PRIMARY" ]
}

is_standby() {
    case "$DB_ROLE" in
        "PHYSICAL STANDBY"|"LOGICAL STANDBY"|"SNAPSHOT STANDBY")
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

check_required_tools() {
    section "PRE-FLIGHT — REQUIRED TOOLS"

    for tool in "$SQLPLUS" "$LSNRCTL" "$TNSPING"; do
        if [ -x "$tool" ] || have_cmd "$tool"; then
            echo "[OK] $tool"
        else
            echo "[FAIL] Missing command: $tool"
            FAILURES=$((FAILURES + 1))
        fi
    done

    if [ -x "$DGMGRL" ] || have_cmd "$DGMGRL"; then
        echo "[OK] dgmgrl available"
    else
        echo "[INFO] dgmgrl not found; broker checks will be skipped"
    fi
}

check_os() {
    section "1) BASIC OS / HOST / TIME CHECKS"

    run_cmd hostname
    run_cmd hostname -f
    run_cmd uname -r
    run_cmd date
    run_cmd uptime
    run_cmd ip -br addr
    run_cmd ip route
}

check_listener_network() {
    section "2) LISTENER / NETWORK CHECKS"

    run_cmd "$LSNRCTL" status

    if [ "$PRIMARY_TNS" != "PRIMARY_TNS" ]; then
        run_cmd "$TNSPING" "$PRIMARY_TNS"
    else
        echo "[INFO] PRIMARY_TNS placeholder not replaced — skipping tnsping"
    fi

    if [ "$STANDBY_TNS" != "STANDBY_TNS" ]; then
        run_cmd "$TNSPING" "$STANDBY_TNS"
    else
        echo "[INFO] STANDBY_TNS placeholder not replaced — skipping tnsping"
    fi
}

check_identity() {
    section "3) DATABASE ROLE / OPEN MODE / SWITCHOVER STATUS"

    sql "
col name format a15
col db_unique_name format a20
col open_mode format a22
col database_role format a20
col switchover_status format a25
col protection_mode format a25
col protection_level format a25

select name,
       db_unique_name,
       open_mode,
       database_role,
       switchover_status,
       protection_mode,
       protection_level
from v\$database;
"
}

check_instance() {
    section "4) INSTANCE STATUS"

    sql "
col instance_name format a15
col host_name format a30
col status format a12
col version format a15

select instance_name, host_name, status, version
from v\$instance;
"
}

check_archive_destinations() {
    section "5) ARCHIVE DESTINATION CONFIGURATION"

    sql "
col dest_name format a22
col status format a12
col target format a10
col schedule format a10
col destination format a50
col error format a60
col db_unique_name format a20

select dest_id,
       dest_name,
       status,
       target,
       schedule,
       db_unique_name,
       destination,
       error
from v\$archive_dest
where status <> 'INACTIVE'
order by dest_id;
"
}

check_dg_status() {
    section "6) DATAGUARD TRANSPORT / APPLY STATUS"

    sql "
col severity format a12
col message format a120
col timestamp format a20

select to_char(timestamp,'YYYY-MM-DD HH24:MI:SS') as timestamp,
       severity,
       message
from v\$dataguard_status
order by timestamp desc
fetch first 30 rows only;
"
}

check_gap() {
    section "7) ARCHIVE LOG GAP CHECK"

    if is_standby; then
        sql "
col thread# format 999
col low_sequence# format 999999
col high_sequence# format 999999

select * from v\$archive_gap;
"
    else
        echo "[SKIP] Current role is $DB_ROLE; archive gap check is standby-oriented."
    fi
}

check_recovery_processes() {
    section "8) REDO TRANSPORT / APPLY PROCESS STATUS"

    if is_standby; then
        echo "--- Preferred process view: V\$DATAGUARD_PROCESS ---"
        sql "
col name format a16
col role format a32
col action format a32
col client_role format a20
col thread# format 999
col sequence# format 999999

select name,
       role,
       action,
       client_role,
       thread#,
       sequence#
from v\$dataguard_process
order by name;
"

        echo
        echo "--- Compatibility view: V\$MANAGED_STANDBY ---"
        sql "
col process format a12
col client_process format a15
col status format a22
col thread# format 999
col sequence# format 999999
col block# format 999999999
col blocks format 999999999

select process,
       client_process,
       status,
       thread#,
       sequence#,
       block#,
       blocks
from v\$managed_standby;
"
    else
        echo "[SKIP] Current role is $DB_ROLE; managed recovery check is standby-oriented."
    fi
}

check_redo_logs() {
    section "9) ONLINE REDO / STANDBY REDO LOG CHECK"

    sql "
col member format a70

prompt --- Online redo logs ---
select l.group#,
       l.thread#,
       l.sequence#,
       round(l.bytes/1024/1024) as mb,
       l.status,
       lf.member
from v\$log l
join v\$logfile lf on l.group# = lf.group#
order by l.thread#, l.group#;

prompt --- Standby redo logs ---
select l.group#,
       l.thread#,
       round(l.bytes/1024/1024) as mb,
       l.status,
       lf.member
from v\$standby_log l
join v\$logfile lf on l.group# = lf.group#
order by l.thread#, l.group#;
"
}

check_archive_status() {
    section "10) ARCHIVED LOG SHIPPING / DESTINATION STATUS"

    sql "
col status format a12
col error format a60
col destination format a45

select dest_id,
       status,
       destination,
       error,
       archived_seq#,
       applied_seq#
from v\$archive_dest_status
where status <> 'INACTIVE'
order by dest_id;
"
}

check_sequence_progress() {
    section "11) ARCHIVE / RECEIVE / APPLY SEQUENCE PROGRESS"

    if is_primary; then
        sql "
select thread#,
       max(sequence#) as last_archived
from v\$archived_log
where resetlogs_change# = (select resetlogs_change# from v\$database)
group by thread#
order by thread#;
"
    elif is_standby; then
        sql "
prompt --- Last received ---
select thread#,
       max(sequence#) as last_received
from v\$archived_log
where resetlogs_change# = (select resetlogs_change# from v\$database)
group by thread#
order by thread#;

prompt --- Last applied ---
select thread#,
       max(sequence#) as last_applied
from v\$archived_log
where applied = 'YES'
and resetlogs_change# = (select resetlogs_change# from v\$database)
group by thread#
order by thread#;
"
        echo
        echo "[NOTE] Sequence equality alone does not prove zero real-time apply lag."
        echo "       Use V\$DATAGUARD_STATS and process status together."
    else
        echo "[INFO] Database role is $DB_ROLE"
    fi
}

check_lag() {
    section "12) APPLY LAG / TRANSPORT LAG"

    if is_standby; then
        sql "
col name format a20
col value format a30
col unit format a15
col time_computed format a25
col datum_time format a25

select name,
       value,
       unit,
       time_computed,
       datum_time
from v\$dataguard_stats
where name in ('transport lag','apply lag','apply finish time');
"
    else
        echo "[SKIP] V\$DATAGUARD_STATS lag values are most useful on the standby."
    fi
}

check_logging_protection() {
    section "13) FORCE LOGGING / FLASHBACK / SUPPLEMENTAL LOGGING"

    sql "
col force_logging format a15
col flashback_on format a15
col supplemental_log_data_min format a25
col supplemental_log_data_pk format a25
col supplemental_log_data_ui format a25

select force_logging,
       flashback_on,
       supplemental_log_data_min,
       supplemental_log_data_pk,
       supplemental_log_data_ui
from v\$database;
"
}

check_parameters() {
    section "14) STANDBY FILE MANAGEMENT / DATAGUARD PARAMETERS"

    sql "
show parameter db_name
show parameter db_unique_name
show parameter log_archive_config
show parameter log_archive_dest_1
show parameter log_archive_dest_2
show parameter log_archive_dest_state_1
show parameter log_archive_dest_state_2
show parameter fal_server
show parameter fal_client
show parameter standby_file_management
show parameter remote_login_passwordfile
show parameter dg_broker_start
"
}

check_controlfiles_spfile() {
    section "15) PASSWORD FILE / SPFILE / CONTROLFILE CHECKS"

    sql "
show parameter spfile
show parameter control_files
show parameter remote_login_passwordfile
"
}

check_files() {
    section "16) DATAFILE / TEMPFILE / FILE NAME CONVERSION CHECKS"

    sql "
col name format a90

select file#, name, status
from v\$datafile
order by file#;

select file#, name, status
from v\$tempfile
order by file#;

show parameter db_file_name_convert
show parameter log_file_name_convert
"
}

check_fra() {
    section "17) RECOVERY AREA / ARCHIVE DEST SPACE CHECK"

    sql "
col name format a35

select name,
       round(space_limit/1024/1024) as space_limit_mb,
       round(space_used/1024/1024) as space_used_mb,
       round(space_reclaimable/1024/1024) as reclaimable_mb,
       number_of_files
from v\$recovery_file_dest;
"

    sql "archive log list;"
}

check_broker() {
    section "18) BROKER CONFIGURATION / VALIDATION"

    if ! { [ -x "$DGMGRL" ] || have_cmd "$DGMGRL"; }; then
        echo "[SKIP] dgmgrl not available"
        return
    fi

    if [ "$PRIMARY_DB_UNIQUE_NAME" = "PRIMARY_DB_UNIQUE_NAME" ] ||
       [ "$STANDBY_DB_UNIQUE_NAME" = "STANDBY_DB_UNIQUE_NAME" ]; then
        echo "[INFO] Broker DB_UNIQUE_NAME placeholders not replaced."
        echo "       Running SHOW CONFIGURATION only."
        "$DGMGRL" / <<DGMGRL
show configuration;
exit;
DGMGRL
        return
    fi

    "$DGMGRL" / <<DGMGRL
show configuration;
show database verbose '$PRIMARY_DB_UNIQUE_NAME';
show database verbose '$STANDBY_DB_UNIQUE_NAME';
validate database '$PRIMARY_DB_UNIQUE_NAME';
validate database '$STANDBY_DB_UNIQUE_NAME';
exit;
DGMGRL
}

check_real_time_apply() {
    section "19) REAL-TIME APPLY CHECK"

    if ! is_standby; then
        echo "[SKIP] Current role is $DB_ROLE"
        return
    fi

    echo "--- Recovery process evidence ---"
    sql "
col name format a16
col role format a30
col action format a35

select name, role, action, thread#, sequence#
from v\$dataguard_process
where name like 'PR%' or name like 'MRP%' or name like 'RFS%'
order by name;
"

    echo
    echo "--- Apply/transport lag evidence ---"
    sql "
col name format a20
col value format a30
col datum_time format a25

select name, value, datum_time
from v\$dataguard_stats
where name in ('transport lag','apply lag','apply finish time');
"

    echo
    echo "[NOTE] Real-time apply should be judged from recovery-process state,"
    echo "       standby redo log usage, and lag together — not from MRP0 presence alone."
}

check_errors() {
    section "20) DATAGUARD ERROR / FATAL MESSAGE CHECK"

    sql "
col timestamp format a20
col severity format a12
col message format a120

select to_char(timestamp,'YYYY-MM-DD HH24:MI:SS') as timestamp,
       severity,
       message
from v\$dataguard_status
where upper(severity) in ('ERROR','FATAL')
order by timestamp desc
fetch first 30 rows only;
"
}

check_invalid_objects() {
    section "21) INVALID OBJECTS CHECK"

    sql "
select owner,
       object_type,
       count(*) as invalid_count
from dba_objects
where status = 'INVALID'
group by owner, object_type
order by owner, object_type;
"
}

check_tablespaces() {
    section "22) TABLESPACE / DATAFILE STATUS"

    sql "
col tablespace_name format a28
col status format a12

select tablespace_name,
       status,
       contents
from dba_tablespaces
order by tablespace_name;

select file#, name, status
from v\$datafile
order by file#;
"
}

check_diag() {
    section "23) ALERT LOG / DIAGNOSTIC LOCATION"

    sql "
col name format a28
col value format a110

select name, value
from v\$diag_info
order by name;
"
}

check_processes() {
    section "24) PMON / SMON / LGWR / DBWR / MRP / RFS CHECK"

    ps -ef | egrep 'pmon|smon|lgwr|dbwr|mrp|rfs' | grep -v grep || true
}

check_services() {
    section "25) LISTENERS / SERVICES REGISTRATION"

    sql "
col name format a30
col network_name format a45

select name, network_name
from v\$services
order by name;
"

    run_cmd "$LSNRCTL" status
}

check_redo_activity() {
    section "26) REDO GENERATION RATE / RECENT ARCHIVE ACTIVITY"

    if ! is_primary; then
        echo "[SKIP] Redo generation rate is a primary-side check."
        return
    fi

    echo "--- Estimated archived redo volume per hour (last 24h) ---"
    sql "
col hour format a16

select to_char(first_time,'YYYY-MM-DD HH24') as hour,
       count(*) as logs,
       round(sum(blocks * block_size)/1024/1024, 2) as redo_mb
from v\$archived_log
where first_time >= sysdate - 1
  and dest_id = 1
  and resetlogs_change# = (select resetlogs_change# from v\$database)
group by to_char(first_time,'YYYY-MM-DD HH24')
order by hour;
"

    echo "--- Recent archive logs ---"
    sql "
select thread#,
       sequence#,
       first_time,
       next_time,
       applied
from v\$archived_log
where first_time > sysdate - 1
  and resetlogs_change# = (select resetlogs_change# from v\$database)
order by first_time desc
fetch first 50 rows only;
"
}

quick_summary() {
    section "27) QUICK PRIMARY/STANDBY SUMMARY"

    sql "
col name format a15
col db_unique_name format a20
col open_mode format a22
col database_role format a20
col switchover_status format a25

select name,
       db_unique_name,
       open_mode,
       database_role,
       switchover_status
from v\$database;

select inst_id,
       instance_name,
       host_name,
       status
from gv\$instance
order by inst_id;
"

    if is_standby; then
        sql "
col name format a20
col value format a30
col unit format a15

select name, value, unit
from v\$dataguard_stats
where name in ('transport lag','apply lag','apply finish time');
"
    fi
}

final_summary() {
    section "FINAL SCRIPT SUMMARY"

    echo "Database role:       $DB_ROLE"
    echo "DB unique name:      $DB_UNIQUE_NAME"
    echo "Open mode:           $OPEN_MODE"
    echo "Warnings encountered: $WARNINGS"
    echo "Tool/pre-flight failures: $FAILURES"

    if [ "$FAILURES" -gt 0 ]; then
        echo "Overall script status: ATTENTION REQUIRED"
        return 2
    elif [ "$WARNINGS" -gt 0 ]; then
        echo "Overall script status: COMPLETED WITH WARNINGS"
        return 1
    else
        echo "Overall script status: COMPLETED"
        return 0
    fi
}

main() {
    check_required_tools

    if [ "$FAILURES" -gt 0 ]; then
        echo
        echo "Required tools are missing. Fix the environment before continuing."
        final_summary
        exit $?
    fi

    discover_role

    echo
    echo "Detected database context:"
    echo "  Role:          $DB_ROLE"
    echo "  DB_UNIQUE_NAME:$DB_UNIQUE_NAME"
    echo "  Open mode:     $OPEN_MODE"

    check_os
    check_listener_network
    check_identity
    check_instance
    check_archive_destinations
    check_dg_status
    check_gap
    check_recovery_processes
    check_redo_logs
    check_archive_status
    check_sequence_progress
    check_lag
    check_logging_protection
    check_parameters
    check_controlfiles_spfile
    check_files
    check_fra
    check_broker
    check_real_time_apply
    check_errors
    check_invalid_objects
    check_tablespaces
    check_diag
    check_processes
    check_services
    check_redo_activity
    quick_summary

    final_summary
    exit $?
}

main "$@"
