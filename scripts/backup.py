"""Binary-safe PostgreSQL backup and isolated restore rehearsal using Docker."""
import argparse
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


# Stream pg_dump bytes directly; PowerShell text redirection can corrupt custom archives.
def backup(destination):
    with destination.open('xb') as output:
        run('docker', 'compose', 'exec', '-T', 'db', 'sh', '-c',
            'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc', stdout=output)
    print(f'Backup created: {destination}')


# Restore only into a new disposable container; the operational database is never a target.
def verify(archive):
    image = subprocess.check_output(['docker', 'compose', 'images', '-q', 'api'], text=True).strip()
    if not image:
        raise RuntimeError('Build the application image before verifying a restore.')
    name = 'ota-restore-' + uuid4().hex[:12]
    password = uuid4().hex
    environment = dict(os.environ, POSTGRES_PASSWORD=password)
    run('docker', 'run', '-d', '--name', name, '-e', 'POSTGRES_PASSWORD',
        '-e', 'POSTGRES_DB=restore_check', 'postgres:17-bookworm', env=environment, stdout=subprocess.DEVNULL)
    try:
        for _ in range(60):
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'postgres'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Restore database did not become ready.')
        run('docker', 'cp', str(archive.resolve()), name + ':/tmp/backup.dump')
        run('docker', 'exec', name, 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl',
            '-U', 'postgres', '-d', 'restore_check', '/tmp/backup.dump')
        # Use the actual application reconciliation against the restored ledger and source documents.
        run('docker', 'run', '--rm', '--network', 'container:' + name,
            '-e', 'POSTGRES_HOST=127.0.0.1', '-e', 'POSTGRES_DB=restore_check',
            '-e', 'POSTGRES_USER=postgres', '-e', 'POSTGRES_PASSWORD',
            image, 'python', '-m', 'api.cli', 'reconcile', env=environment)
        run('docker', 'exec', name, 'psql', '-U', 'postgres', '-d', 'restore_check',
            '-v', 'ON_ERROR_STOP=1', '-c',
            'SELECT COUNT(*) AS users FROM auth_user; SELECT version_num FROM alembic_version;')
        print('PASS: archive restored; application ledger/source/lot reconciliation passed.')
    finally:
        run('docker', 'rm', '-f', '-v', name, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'verify'])
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    (backup if args.action == 'backup' else verify)(args.archive)
