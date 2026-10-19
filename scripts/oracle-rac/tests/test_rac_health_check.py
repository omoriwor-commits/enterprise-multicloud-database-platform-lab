"""Fixture and mocked-collection tests; no Oracle or SSH access."""
import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import subprocess
import sys
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'rac_health_check.py'
spec = importlib.util.spec_from_file_location('rac_health_updated', str(SCRIPT))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

DB = '''INST|1|RAC1|racnode1|OPEN|ACTIVE
INST|2|RAC2|racnode2|OPEN|ACTIVE
CDB|RAC|READ WRITE
DBUNQ|RAC
DBTYPE|YES
PDB|1|PDB$SEED|READ ONLY
PDB|1|RACPDB1|READ WRITE
PDB|2|PDB$SEED|READ ONLY
PDB|2|RACPDB1|READ WRITE
LOG|ARCHIVELOG
FRA|+FRA|4.1
VERSION|23.26.1.0.0
TRACE|/custom/db/trace
'''
ASM = '''ASM_INST|1|+ASM1|racnode1
ASM_INST|2|+ASM2|racnode2
TRACE|/custom/grid/trace
'''
for i in [1, 2]:
    for number, (name, total) in enumerate([('OCR', 20480), ('DATA', 40960), ('FRA', 30720)], 1):
        ASM += 'ASM_DG|{}|{}|MOUNTED|{}|{}|0|{}\n'.format(i, name, total, total//2, total//2)
        ASM += 'ASM_DISK|{}|/dev/asm-disk{}|MEMBER|CACHED|ONLINE|NORMAL|{}\n'.format(i, number, number)

CLUSTER = '''**************************************************************
racnode1:
CRS-4537: Cluster Ready Services is online
CRS-4529: Cluster Synchronization Services is online
CRS-4533: Event Manager is online
**************************************************************
racnode2:
CRS-4537: Cluster Ready Services is online
CRS-4529: Cluster Synchronization Services is online
CRS-4533: Event Manager is online
'''
RESOURCES = '''Name Target State Server State details
Local Resources
ora.LISTENER.lsnr
               ONLINE ONLINE racnode1 STABLE
               ONLINE ONLINE racnode2 STABLE
ora.helper
               OFFLINE OFFLINE racnode1 IDLE,STABLE
Cluster Resources
ora.DATA.dg(ora.asmgroup)
      1        ONLINE ONLINE racnode1 STABLE
      2        ONLINE ONLINE racnode2 STABLE
ora.rac.db
      1        ONLINE ONLINE racnode1 Open,HOME=/u01/app/o
                                                             racle/product/23.26/
                                                             dbhome_1,STABLE
      2        ONLINE ONLINE racnode2 Open,STABLE
'''
OS = '''__KERNEL__
5.15.0-300.el9uek.x86_64
__SELINUX__
Permissive
%Cpu(s): 10.5 us, 10.5 sy, 0.0 ni, 76.3 id, 0.0 wa, 2.6 hi, 0.0 si, 0.0 st
__MEM__
Mem: 9487 7063 356 3204 5676 2424
Swap: 10155 2008 8147
__HUGE__
HugePages_Total: 0
Hugepagesize: 2048 kB
always [madvise] never
__DF__
Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/mapper/ol-root 66220032 26733504 39486528 41% /
/dev/sda1 983040 705212 277828 72% /boot
'''

def sample_text(busy=(20, 30, 25), paging=(0, 0, 0)):
    return ''.join('OS_SAMPLE|' + json.dumps({
        'interval':i+1, 'seconds':1.0, 'busy_pct':value,
        'iowait_pct':0, 'steal_pct':0,
        'swap_in_kib_s':paging[i], 'swap_out_kib_s':0,
        'top_processes':[{'pid':100, 'name':'ora_pmon_RAC1', 'cpu_pct_one_core':2}]
    }) + '\n' for i,value in enumerate(busy))

OS += sample_text()



class HealthTests(unittest.TestCase):
    def setUp(self):
        m.CFG = m.build_parser().parse_args(['--db', 'RAC', '--pdb', 'RACPDB1'])
        m.findings[:] = []
        m.coverage.clear()
        m.KERNELS.clear()
        m.METRICS.clear()
        m.DB_VERSION = None
        m.DB_OPERATIONAL = False
        m.DB_ALERT = m.ASM_ALERT = None
        m.GRID_HOME, m.DB_HOME = '/grid home/23.26', '/db home/23.26'
        m.GRID_BASE, m.DB_BASE = '/custom/grid', '/custom/db'
        m.DB_CONFIG = {'Database name': 'RAC', 'Services': 'RAC_RACPDB1',
                       'Database instances': 'RAC1,RAC2',
                       'Configured nodes': 'racnode1,racnode2'}
        m.EXPECTED_INSTANCES = ['RAC1', 'RAC2']

    def messages(self, severity=None):
        return '\n'.join(f.message for f in m.findings if not severity or f.severity == severity)

    def quiet(self, func, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return func(*args)

    def test_actual_database_values_parse(self):
        self.assertTrue(m.evaluate_database(DB))
        self.assertTrue(m.DB_OPERATIONAL)
        self.assertEqual(m.findings, [])

    def test_empty_sql_is_critical(self):
        self.assertFalse(m.evaluate_database(''))
        self.assertIn('missing', self.messages('CRITICAL'))

    def test_missing_second_instance(self):
        m.evaluate_database(DB.replace('INST|2|RAC2|racnode2|OPEN|ACTIVE\n', ''))
        self.assertIn('RAC2', self.messages('CRITICAL'))

    def test_wrong_database_not_checked_as_target(self):
        self.assertFalse(m.evaluate_database(DB.replace('DBUNQ|RAC', 'DBUNQ|OTHER')))
        self.assertIn('different', self.messages('CRITICAL'))

    def test_malformed_required_row(self):
        self.assertFalse(m.evaluate_database(DB.replace('DBTYPE|YES', 'DBTYPE|')))

    def test_missing_pdb_on_node_two(self):
        m.evaluate_database(DB.replace('PDB|2|RACPDB1|READ WRITE\n', ''))
        self.assertIn('Missing PDB row', self.messages('WARNING'))

    def test_noarchivelog_warning(self):
        m.evaluate_database(DB.replace('LOG|ARCHIVELOG', 'LOG|NOARCHIVELOG'))
        self.assertIn('ARCHIVELOG', self.messages('WARNING'))

    def test_unknown_fra_is_not_clean(self):
        m.evaluate_database(DB.replace('FRA|+FRA|4.1', 'FRA|UNCONFIGURED|UNKNOWN'))
        self.assertIn('FRA', self.messages('WARNING'))

    def test_asm_stat_values_parse(self):
        self.assertTrue(m.evaluate_asm(ASM))
        self.assertEqual(m.findings, [])

    def test_asm_empty_is_critical(self):
        self.assertFalse(m.evaluate_asm(''))
        self.assertIn('incomplete', self.messages('CRITICAL'))

    def test_unassigned_disk_not_false_critical(self):
        m.evaluate_asm(ASM + 'ASM_DISK|1|AFD:SPARE|CANDIDATE|CLOSED|ONLINE|NORMAL|0\n')
        self.assertEqual(self.messages('CRITICAL'), '')

    def test_active_disk_bad_state_critical(self):
        m.evaluate_asm(ASM.replace('CACHED|ONLINE|NORMAL|1', 'CACHED|OFFLINE|NORMAL|1', 1))
        self.assertIn('Disk', self.messages('CRITICAL'))

    def test_asm_missing_group_on_second_asm(self):
        m.evaluate_asm(ASM.replace('ASM_DG|2|DATA|MOUNTED|40960|20480|0|20480\n', ''))
        self.assertIn('DATA not returned', self.messages('WARNING'))

    def test_26ai_grouped_resources_and_wrapping(self):
        rows = m.parse_resource_rows(RESOURCES)
        self.assertEqual(len(rows), 7)
        self.assertTrue(any(r[0] == 'ora.DATA.dg' for r in rows))
        self.assertEqual(sum(r[0] == 'ora.rac.db' for r in rows), 2)

    def test_expected_offline_not_flagged(self):
        def fake_tool(home, binary, *args, **kw):
            if args[:3] == ('check', 'cluster', '-all'):
                return 0, CLUSTER
            if binary == 'olsnodes':
                return 0, 'racnode1 1 Active Unpinned\nracnode2 2 Active Unpinned'
            if binary == 'crsctl':
                return 0, RESOURCES
            return 0, 'component is running on node racnode1'
        with patch.object(m, 'tool', side_effect=fake_tool):
            self.quiet(m.check_cluster, ['racnode1', 'racnode2'])
        self.assertEqual(m.findings, [])

    def test_failed_target_is_critical(self):
        def fake_tool(home, binary, *args, **kw):
            if args[:3] == ('check', 'cluster', '-all'):
                return 0, CLUSTER
            if binary == 'olsnodes':
                return 0, 'racnode1 1 Active\nracnode2 2 Active'
            if binary == 'crsctl':
                return 0, RESOURCES.replace('ONLINE ONLINE racnode2 Open', 'ONLINE OFFLINE racnode2 Open')
            return 0, 'running'
        with patch.object(m, 'tool', side_effect=fake_tool):
            self.quiet(m.check_cluster, ['racnode1', 'racnode2'])
        self.assertIn('ora.rac.db', self.messages('CRITICAL'))

    def test_sqlplus_home_and_sid_are_isolated(self):
        with patch.dict(os.environ, {'ORACLE_HOME': '/wrong', 'ORACLE_BASE': '/wrong',
                                    'LD_LIBRARY_PATH': '/wrong', 'TWO_TASK': 'remote'}):
            with patch.object(m, 'run', return_value=(0, '__RAC_HEALTH_BEGIN__\nx\n__RAC_HEALTH_END__')) as r:
                rc, out = m.sqlplus('select 1 from dual;', 'RAC1', m.DB_HOME)
        self.assertEqual((rc, out), (0, 'x'))
        env = r.call_args.kwargs['env']
        self.assertEqual(env['ORACLE_HOME'], m.DB_HOME)
        self.assertEqual(env['ORACLE_BASE'], m.DB_BASE)
        self.assertEqual(env['ORACLE_SID'], 'RAC1')
        self.assertEqual(env['LD_LIBRARY_PATH'], m.DB_HOME + '/lib')
        self.assertNotIn('TWO_TASK', env)

    def test_sqlplus_sp2_error_with_zero_exit_is_failure(self):
        with patch.object(m, 'run', return_value=(0, '__RAC_HEALTH_BEGIN__\nSP2-0734: bad command\n__RAC_HEALTH_END__')):
            self.assertNotEqual(m.sqlplus('x', 'RAC1', m.DB_HOME)[0], 0)

    def test_sqlplus_missing_end_marker_is_failure(self):
        with patch.object(m, 'run', return_value=(0, '__RAC_HEALTH_BEGIN__\npartial')):
            self.assertNotEqual(m.sqlplus('x', 'RAC1', m.DB_HOME)[0], 0)

    def test_asm_cli_uses_grid_home_asm_sid(self):
        calls = []
        def fake_tool(home, binary, *args, **kw):
            calls.append((home, binary, kw.get('env')))
            return 0, 'running'
        with patch.object(m, 'run', return_value=(0, 'oinstall dba asmadmin')), \
             patch.object(m, 'tool', side_effect=fake_tool), \
             patch.object(m, 'sqlplus', return_value=(0, ASM)):
            self.quiet(m.check_asm, '+ASM1')
        asm_env = [c[2] for c in calls if c[1] == 'asmcmd'][0]
        self.assertEqual(asm_env['ORACLE_SID'], '+ASM1')
        self.assertEqual(asm_env['ORACLE_HOME'], m.GRID_HOME)

    def test_skipped_asm_prevents_clean_exit(self):
        with patch.object(m, 'run', return_value=(0, 'oinstall dba asmdba')):
            self.quiet(m.check_asm, '+ASM1')
        self.assertEqual(self.quiet(m.final_report), 1)

    def test_iso_timestamp_offset(self):
        stamp = m.parse_alert_time('2026-10-19T06:48:39.123456-05:00')
        self.assertEqual(stamp, datetime(2026, 10, 19, 11, 48, 39, 123456, tzinfo=timezone.utc))

    def test_19c_legacy_local_timestamp(self):
        self.assertIsNotNone(m.parse_alert_time('Mon Oct 19 06:48:39 2026'))

    def test_recent_old_undated_future_distinguished(self):
        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        text = '''ORA-00028: undated
2026-10-18T11:00:00Z
ORA-29770: old
2026-10-19T11:30:00+00:00
ORA-00028: recent
2026-10-20T11:30:00+00:00
WARNING: future
'''
        self.assertEqual([x[0] for x in m.alert_events(text, now, 1)],
                         ['UNDATED', 'HISTORICAL', 'IN WINDOW', 'FUTURE'])

    def test_unreadable_alert_does_not_print_clean(self):
        with patch.object(m, 'read_tail', return_value=(1, 'Permission denied')):
            self.assertFalse(self.quiet(m.review_alert, '/bad/log'))
        self.assertIn('Unable to read', self.messages('WARNING'))

    def test_empty_alert_incomplete(self):
        with patch.object(m, 'read_tail', return_value=(0, '')):
            self.assertFalse(self.quiet(m.review_alert, '/empty/log'))

    def test_historical_alert_does_not_raise_current_warning(self):
        with patch.object(m, 'read_tail', return_value=(0, '2000-01-01T00:00:00Z\nORA-29770: old\n')):
            self.assertTrue(self.quiet(m.review_alert, '/old/log'))
        self.assertEqual(self.messages('WARNING'), '')
        self.assertIn('older', self.messages('INFO'))

    def test_bounded_tail_and_unicode(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'alert.log'
            p.write_text('older\n' * 50000 + 'last α\nlast β\n', encoding='utf-8')
            self.assertEqual(m.read_tail(str(p), 2), (0, 'last α\nlast β\n'))

    def test_sysasm_trace_discovery(self):
        self.assertEqual(m.trace_alert(ASM, '+ASM1'), '/custom/grid/trace/alert_+ASM1.log')

    def test_base_override_does_not_inherit_other_home(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {'ORACLE_BASE': '/wrong'}):
                with patch.object(m, 'tool', return_value=(0, d)):
                    self.assertEqual(m.discover_base('/19c/home', None), d)

    def test_known_uek8_compatibility_review(self):
        m.DB_VERSION = '23.26.1.0.0'
        m.KERNELS['racnode1'] = '6.12.0-207.111.5.4.el9uek.x86_64'
        m.check_compatibility()
        self.assertIn('23.26.2', self.messages('WARNING'))

    def test_version_uses_full_release_string(self):
        self.assertIn("'VERSION|'||version_full", m.DB_QUERY)

    def test_summary_never_claims_proven_failover(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.final_report(), 0)
        self.assertNotIn('failover capability is intact', out.getvalue())
        self.assertIn('does not establish', out.getvalue())

    def test_os_missing_thp_marks_incomplete(self):
        with patch.object(m, 'collect_node', return_value=(0, OS.replace('always [madvise] never', ''))):
            self.quiet(m.check_os, ['racnode1'])
        self.assertEqual(m.coverage['OS nodes'], 'INCOMPLETE')

    def test_local_sid_avoids_unrelated_database(self):
        with patch.object(m, 'tool', return_value=(1, 'status unavailable')), \
             patch.object(m, 'run', return_value=(0, 'ora_pmon_OTHER\nora_pmon_RAC1')), \
             patch.object(m.socket, 'gethostname', return_value='racnode1'):
            self.assertEqual(m.local_sid(), 'RAC1')

    def test_main_with_full_mocked_26ai_collection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gh, dh = root/'grid 23.26', root/'db 23.26'
            gb, db = root/'grid base', root/'db base'
            for path in [gh, dh, gb, db]:
                path.mkdir()
            trace_db, trace_asm = root/'db trace', root/'asm trace'
            trace_db.mkdir(); trace_asm.mkdir()
            (trace_db/'alert_RAC1.log').write_text('2000-01-01T00:00:00Z\nDatabase opened.\n')
            (trace_asm/'alert_+ASM1.log').write_text('2000-01-01T00:00:00Z\nASM mounted.\n')
            dbca = db/'cfgtoollogs'/'dbca'/'RAC'
            dbca.mkdir(parents=True)
            (dbca/'trace.log_2026-10-19').write_text('INFO Setup completed with overall status as Succeeded\n')
            config = ('Database unique name: RAC\nDatabase name: RAC\nOracle home: '+str(dh)+
                      '\nDatabase instances: RAC1,RAC2\nConfigured nodes: racnode1,racnode2\nServices: RAC_RACPDB1\n')
            def fake_tool(home, binary, *args, **kw):
                if args[:2] == ('config', 'database'):
                    return 0, config
                if binary == 'olsnodes':
                    return 0, 'racnode1 1 Active Unpinned\nracnode2 2 Active Unpinned'
                if binary == 'crsctl':
                    return 0, CLUSTER if 'check' in args else RESOURCES
                if args[:2] == ('status', 'database'):
                    return 0, 'Instance RAC1 is running on node racnode1\nInstance RAC2 is running on node racnode2'
                if args[:2] == ('status', 'service'):
                    return 0, 'Service RAC_RACPDB1 is running on instances RAC1,RAC2'
                return 0, 'component is running on node racnode1'
            def fake_run(cmd, **kw):
                if cmd == ['id', '-nG']:
                    return 0, 'oinstall dba asmdba asmadmin'
                if cmd == ['ps', '-eo', 'args']:
                    return 0, 'asm_pmon_+ASM1\nora_pmon_RAC1'
                raise AssertionError('Unexpected real command request: '+str(cmd))
            def fake_sql(query, sid, home, sysasm=False):
                value = ASM.replace('/custom/grid/trace',str(trace_asm)) if sysasm else DB.replace('/custom/db/trace',str(trace_db))
                return 0, value
            args = ['--db','RAC','--pdb','RACPDB1','--grid-home',str(gh),
                    '--db-home',str(dh),'--grid-base',str(gb),'--db-base',str(db),
                    '--json-out',str(root/'report.json')]
            with patch.object(m, 'tool', side_effect=fake_tool), \
                 patch.object(m, 'run', side_effect=fake_run), \
                 patch.object(m, 'collect_node', return_value=(0,OS)), \
                 patch.object(m, 'sqlplus', side_effect=fake_sql), \
                 patch.object(m.os, 'access', return_value=True), \
                 patch.object(m.socket, 'gethostname', return_value='racnode1'):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = m.main(args)
            self.assertEqual(rc, 0, buf.getvalue())
            report = json.loads((root/'report.json').read_text())
            self.assertEqual(report['exit_code'], 0)
            self.assertEqual(len(report['metrics']['os']), 2)
            self.assertEqual(report['database_version'], '23.26.1.0.0')
            self.assertIn('overall status as Succeeded', buf.getvalue())
            self.assertEqual(m.DB_ALERT, str(trace_db/'alert_RAC1.log'))
            self.assertEqual(m.ASM_ALERT, str(trace_asm/'alert_+ASM1.log'))
            self.assertEqual(m.coverage['ASM SQL/CLI'], 'COLLECTED')

    def test_one_cpu_spike_is_info_not_warning(self):
        self.assertTrue(self.quiet(m.evaluate_os_samples, sample_text((99,10,20)), 'racnode1'))
        self.assertNotIn('high CPU', self.messages('WARNING'))
        self.assertIn('Isolated CPU', self.messages('INFO'))

    def test_repeated_cpu_pressure_flagged(self):
        self.quiet(m.evaluate_os_samples, sample_text((90,99,20)), 'racnode1')
        self.assertIn('Repeated high CPU', self.messages('WARNING'))

    def test_missing_interval_incomplete(self):
        self.assertFalse(self.quiet(m.evaluate_os_samples, sample_text((20,30)), 'racnode1'))
        self.assertIn('incomplete', self.messages('WARNING'))

    def test_nan_interval_incomplete(self):
        self.assertFalse(self.quiet(m.evaluate_os_samples, sample_text((float('nan'),20,30)), 'racnode1'))

    def test_cpu_counter_invalid_percentage(self):
        self.assertFalse(self.quiet(m.evaluate_os_samples, sample_text((101,20,30)), 'racnode1'))

    def test_duplicate_interval_rejected(self):
        value = sample_text().replace('"interval": 2', '"interval": 1')
        self.assertFalse(self.quiet(m.evaluate_os_samples, value, 'racnode1'))

    def test_paging_rates_not_allocated_swap(self):
        self.quiet(m.evaluate_os_samples, sample_text(paging=(10,20,0)), 'racnode1')
        self.assertIn('Paging observed', self.messages('WARNING'))
        self.assertIn('Not by itself proof of thrashing', self.messages('WARNING'))

    def test_zero_paging_information(self):
        self.quiet(m.evaluate_os_samples, sample_text(), 'racnode1')
        self.assertEqual(self.messages('WARNING'), '')
        self.assertIn('No paging', self.messages('INFO'))

    def test_real_linux_sampler_intervals(self):
        result = subprocess.run([sys.executable, '-c', m.OS_SAMPLER, '2', '0.2'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        m.CFG.os_samples = 2
        self.assertTrue(self.quiet(m.evaluate_os_samples, result.stdout, 'local-linux'))
        self.assertEqual(len(m.METRICS['os']['local-linux']['intervals']), 2)

    def test_missing_dbca_on_other_node_informational(self):
        m.CFG.dbca_node = 'racnode1'
        with tempfile.TemporaryDirectory() as d:
            m.DB_BASE = d
            with patch.object(m.socket, 'gethostname', return_value='racnode2'), \
                 patch.object(m, 'review_alert', return_value=True), \
                 patch.object(m, 'fallback_alert', return_value='/fake/alert'):
                self.quiet(m.check_local_logs, 'RAC2', '+ASM2')
        self.assertFalse(any(f.category == 'DBCA' and f.severity == 'WARNING' for f in m.findings))

    def test_explicit_missing_dbca_directory_warns(self):
        m.CFG.dbca_dir = '/missing/explicit/evidence'
        with patch.object(m, 'review_alert', return_value=True), \
             patch.object(m, 'fallback_alert', return_value='/fake/alert'):
            self.quiet(m.check_local_logs, 'RAC2', '+ASM2')
        self.assertIn('Expected local DBCA', self.messages('WARNING'))

    def test_json_private_and_no_clobber(self):
        m.METRICS['os'] = {'node':{'intervals':[]}}
        m.STARTED_AT = '2026-10-19T08:00:00-05:00'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'report.json'
            m.save_json_report(str(path), 1)
            data = json.loads(path.read_text())
            self.assertEqual(data['schema_version'], 1)
            self.assertEqual(data['exit_code'], 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                m.save_json_report(str(path), 2)
            self.assertEqual(json.loads(path.read_text())['exit_code'], 1)
            self.assertEqual(len(list(Path(d).iterdir())), 1)

    def test_json_does_not_follow_existing_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target, link = Path(d)/'keep.txt', Path(d)/'report.json'
            target.write_text('untouched')
            link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                m.save_json_report(str(link), 0)
            self.assertEqual(target.read_text(), 'untouched')

    def test_alert_window_metadata_local_time(self):
        with patch.object(m, 'read_tail', return_value=(0, '2000-01-01T00:00:00Z\nORA-29770: old\n')):
            self.quiet(m.review_alert, '/old/alert')
        self.assertTrue(m.METRICS['alerts']['/old/alert']['sample_reaches_window_start'])
        self.assertEqual(m.METRICS['alerts']['/old/alert']['matching_line_counts']['IN WINDOW'], 0)

    def test_invalid_sampling_args_configuration_error(self):
        self.assertEqual(self.quiet(m.main, ['--sample-seconds', 'nan']), 3)
        self.assertEqual(self.quiet(m.main, ['--os-samples', '1']), 3)


    def test_selinux_permissive_observation_not_outage(self):
        with patch.object(m, 'collect_node', return_value=(0, OS)):
            self.quiet(m.check_os, ['racnode1'])
        self.assertEqual(m.METRICS['os']['racnode1']['selinux_mode'], 'Permissive')
        self.assertEqual(m.coverage['OS nodes'], 'COLLECTED')
        self.assertEqual(self.messages('WARNING'), '')

    def test_selinux_unknown_explicitly_incomplete(self):
        value = OS.replace('__SELINUX__\nPermissive', '__SELINUX__\nUNKNOWN')
        with patch.object(m, 'collect_node', return_value=(0, value)):
            self.quiet(m.check_os, ['racnode1'])
        self.assertEqual(m.coverage['OS nodes'], 'INCOMPLETE')
        self.assertIn('SELinux mode', self.messages('WARNING'))

    def test_selinux_troubleshooting_cpu_attribution(self):
        value = sample_text().replace('ora_pmon_RAC1','setroubleshootd')
        self.assertTrue(self.quiet(m.evaluate_os_samples, value, 'racnode1'))
        self.assertIn('Visible SELinux troubleshooting', self.messages('INFO'))
        self.assertIn('does not establish', self.messages('INFO'))
        self.assertEqual(m.METRICS['os']['racnode1']['selinux_troubleshooting_peak_pct_one_core'], 2)
        self.assertEqual(self.messages('WARNING'), '')


if __name__ == '__main__':
    unittest.main()
