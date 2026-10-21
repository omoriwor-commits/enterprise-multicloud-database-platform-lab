"""Failure-injection tests; no Oracle instance or credentials are used."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'dataguard_health_check.sh'

class DataGuardTests(unittest.TestCase):
    def run_pack(self, scenario):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            binaries = home / 'bin'
            binaries.mkdir()
            sql = '''#!/bin/bash
input=$(cat)
if [[ "$input" == *"database_role||"* ]]; then
  case "$SCENARIO" in
    unavailable) echo 'ORA-01034: ORACLE not available'; exit 1;;
    malformed) echo 'not a database identity'; exit 0;;
    zero_exit_error) echo 'SP2-0640: Not connected'; exit 0;;
    multiline) printf 'PRIMARY|RAC|READ WRITE\nPRIMARY|OTHER|READ WRITE\n'; exit 0;;
    *) echo 'PRIMARY|RAC|READ WRITE'; exit 0;;
  esac
fi
if [ "$SCENARIO" = later_sql_error ]; then echo 'ORA-00942: table or view does not exist'; exit 0; fi
echo 'test query completed'
'''
            for name in ('sqlplus', 'dgmgrl', 'lsnrctl', 'tnsping', 'hostname', 'uname', 'date', 'uptime', 'ip'):
                path = binaries / name
                body = sql if name == 'sqlplus' else '#!/bin/bash\nexit 0\n'
                if name == 'dgmgrl':
                    body = '#!/bin/bash\ncat >/dev/null\nif [ "$SCENARIO" = broker_error ]; then echo "ORA-16525: broker not yet available"; exit 0; fi\nexit 0\n'
                path.write_text(body)
                path.chmod(0o700)
            env = os.environ.copy()
            env.update(ORACLE_HOME=tmp, PATH=str(binaries)+':/usr/bin:/bin', SCENARIO=scenario)
            return subprocess.run(['/bin/bash', str(SCRIPT)], env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)

    def test_database_unavailable_is_failure(self):
        result = self.run_pack('unavailable')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Database identity query failed', result.stdout)

    def test_malformed_identity_is_failure(self):
        self.assertEqual(self.run_pack('malformed').returncode, 2)

    def test_sqlplus_error_with_zero_exit_is_failure(self):
        self.assertEqual(self.run_pack('zero_exit_error').returncode, 2)

    def test_multiple_identity_rows_are_rejected(self):
        self.assertEqual(self.run_pack('multiline').returncode, 2)

    def test_later_sql_error_increments_failures(self):
        result = self.run_pack('later_sql_error')
        self.assertEqual(result.returncode, 2)
        self.assertIn('SQL collection failed', result.stdout)

    def test_broker_error_with_zero_exit_is_failure(self):
        result = self.run_pack('broker_error')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Broker collection reported an error', result.stdout)

    def test_completed_collection_is_not_health_verdict(self):
        result = self.run_pack('success')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('not a Data Guard health verdict', result.stdout)

if __name__ == '__main__':
    unittest.main()
