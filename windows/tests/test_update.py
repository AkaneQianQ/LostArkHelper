import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'service'))
import app
import updater
import update_worker


def archive_bytes(version='v0.3.0', windows=True, valid=True):
    root = f'LostArkHelper-{"Windows-x64" if windows else "Linux-x64"}-{version}'
    executable = 'LostArkHelper.exe' if windows else 'LostArkHelper'
    files = {
        executable: b'new executable',
        'README.md': b'new version',
        'VERSION': (version + '\n').encode(),
    }
    checks = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name, data in files.items())
    files['SHA256SUMS.txt'] = checks.encode()
    if not valid:
        files[executable] = b'changed'
    stream = io.BytesIO()
    if windows:
        with zipfile.ZipFile(stream, 'w') as output:
            for name, data in files.items():
                output.writestr(root+'/'+name, data)
    else:
        with tarfile.open(fileobj=stream, mode='w:gz') as output:
            for name, data in files.items():
                info = tarfile.TarInfo(root+'/'+name)
                info.size = len(data)
                info.mode = 0o755 if name == executable else 0o644
                output.addfile(info, io.BytesIO(data))
    return stream.getvalue()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_current_version_from_bundled_resource(self):
        self.root.joinpath('VERSION').write_text('v0.2.0\n')
        with patch.object(sys, '_MEIPASS', str(self.root), create=True):
            self.assertEqual(updater.current_version(), 'v0.2.0')

    def test_frozen_version_prefers_file_next_to_executable(self):
        install = self.root / 'install'
        bundle = self.root / 'bundle'
        install.mkdir()
        bundle.mkdir()
        executable = install / 'LostArkHelper.exe'
        executable.write_bytes(b'executable')
        install.joinpath('VERSION').write_text('v0.3.0\n')
        bundle.joinpath('VERSION').write_text('v0.2.0\n')
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)), \
                patch.object(sys, '_MEIPASS', str(bundle), create=True):
            self.assertEqual(updater.current_version(), 'v0.3.0')

    def test_new_version_comparison(self):
        with patch.object(updater, 'current_version', return_value='v0.9.9'):
            self.assertEqual(updater.version_tuple('v0.10.0'), (0, 10, 0))
            for invalid in ('latest', 'v0.2.0-beta', '../VERSION'):
                with self.assertRaises(ValueError):
                    updater.version_tuple(invalid)

    def test_corrupt_or_unlisted_file_never_replaces_old(self):
        root = self.root/'install'
        root.mkdir()
        executable = root/'LostArkHelper.exe'
        executable.write_bytes(b'old executable')
        name = 'LostArkHelper-Windows-x64-v0.3.0.zip'
        for data in (archive_bytes(valid=False),
                     archive_bytes().replace(b'v0.3.0', b'v0.4.0')):
            with patch.object(sys, 'frozen', True, create=True), patch.object(updater, 'current_version', return_value='v0.2.0'), patch.object(updater.subprocess, 'Popen') as launch:
                with self.assertRaises(ValueError):
                    updater.apply_downloaded(data, name, root, executable)
                launch.assert_not_called()
            self.assertEqual(executable.read_bytes(), b'old executable')
            self.assertFalse(root.with_name('install.previous').exists())

    def test_no_downgrade_or_wrong_program_path(self):
        root = self.root/'install'
        root.mkdir()
        executable = root/'LostArkHelper.exe'
        executable.write_bytes(b'old executable')
        with patch.object(sys, 'frozen', True, create=True), patch.object(updater, 'current_version', return_value='v0.3.0'), patch.object(updater.subprocess, 'Popen') as launch:
            with self.assertRaises(ValueError):
                updater.apply_downloaded(archive_bytes(), 'LostArkHelper-Windows-x64-v0.3.0.zip', root, executable)
            with self.assertRaises(ValueError):
                updater.apply_downloaded(archive_bytes(), 'LostArkHelper-Windows-x64-v0.3.0.zip', root, self.root/'elsewhere.exe')
            launch.assert_not_called()
        self.assertEqual(executable.read_bytes(), b'old executable')

    @unittest.skipIf(os.name == 'nt', 'POSIX archive paths are tested by Linux CI')
    def test_linux_archive_and_normalized_executable_path(self):
        root = self.root / 'install'
        root.mkdir()
        executable = root / 'LostArkHelper'
        executable.write_bytes(b'old executable')
        with patch.object(updater, 'platform_name', return_value='Linux-x64'), patch.object(updater.os, 'name', 'posix'), \
                patch.object(sys, 'frozen', True, create=True), patch.object(updater, 'current_version', return_value='v0.2.0'), \
                patch.object(updater.subprocess, 'Popen') as launch:
            updater.apply_downloaded(archive_bytes(windows=False), 'LostArkHelper-Linux-x64-v0.3.0.tar.gz', root, root / '.' / 'LostArkHelper')
        self.assertEqual(executable.read_bytes(), b'new executable')
        self.assertTrue(os.access(executable, os.X_OK))
        launch.assert_called_once()

    @unittest.skipUnless(os.name == 'nt', 'Requires Windows executable replacement')
    def test_windows_replacement_keeps_backup_and_launches_new(self):
        root = self.root/'install'
        root.mkdir()
        executable = root/'LostArkHelper.exe'
        executable.write_bytes(b'old executable')
        with patch.object(sys, 'frozen', True, create=True), patch.object(updater, 'current_version', return_value='v0.2.0'), patch.object(updater.subprocess, 'Popen') as launch:
            updater.apply_downloaded(archive_bytes(), 'LostArkHelper-Windows-x64-v0.3.0.zip', root, executable)
        self.assertEqual(executable.read_bytes(), b'new executable')
        self.assertEqual(root.with_name('install.previous').joinpath('LostArkHelper.exe').read_bytes(), b'old executable')
        launch.assert_called_once()
        self.assertEqual(Path(launch.call_args.args[0][0]), executable.resolve())
        self.assertEqual(launch.call_args.args[0][1:], ['--no-browser'])

    def test_check_publishes_version_and_expected_digest(self):
        release = {'tag_name': 'v0.3.0', 'html_url': 'https://github.com/youboRepo/LostArkHelper/releases/tag/v0.3.0', 'assets': [{'name': 'SHA256SUMS.txt'}, {'name': 'LostArkHelper-Windows-x64-v0.3.0.zip'}]}
        with patch.object(updater, 'platform_name', return_value='Windows-x64'), patch.object(updater, 'current_version', return_value='v0.2.0'), patch.object(updater, 'fetch_json', return_value=release), patch.object(updater, 'fetch_asset', return_value=(b'a'*64+b'  LostArkHelper-Windows-x64-v0.3.0.zip\n', 'SHA256SUMS.txt')):
            result = updater.check()
        self.assertEqual(result['latest_checksum'], 'a'*64)

    def test_start_never_downloads_when_stop_is_unavailable(self):
        with patch.object(updater.threading, 'Thread') as thread:
            with self.assertRaises(RuntimeError):
                updater.start()
            thread.assert_not_called()

    def test_worker_recovers_old_service_after_bad_archive(self):
        data_root = self.root / 'data'
        program_root = self.root / 'program'
        data_root.mkdir()
        program_root.mkdir()
        executable = program_root / 'LostArkHelper.exe'
        executable.write_bytes(b'old executable')
        data_root.joinpath('update-download.json').write_text(json.dumps({'name': 'LostArkHelper-Windows-x64-v0.3.0.zip'}))
        data_root.joinpath('update-download.bin').write_bytes(b'not an archive')
        with patch.object(sys, 'frozen', True, create=True), patch.object(updater, 'current_version', return_value='v0.2.0'), \
                patch.object(updater, 'apply_downloaded', side_effect=ValueError('bad archive')) as apply, \
                patch.object(update_worker.subprocess, 'Popen') as launch:
            self.assertEqual(update_worker.install(data_root, program_root, executable), 1)
            self.assertEqual(Path(launch.call_args.args[0][0]), executable.resolve())
            self.assertEqual(apply.call_args.kwargs['installed_version'], 'v0.2.0')

    def test_pending_game_operation_blocks_update_before_download(self):
        app.ROOT = self.root
        app.REQUEST_STOP = lambda: None
        self.root.joinpath('pending-operation.json').write_text('{}')
        with patch.object(sys, 'frozen', True, create=True), patch.object(updater, 'current_version', return_value='v0.2.0'), \
                patch.object(updater, 'state', return_value={'latest_version': 'v0.3.0', 'latest_checksum': 'unused'}), patch.object(updater, 'prepare') as prepare:
            with self.assertRaises(RuntimeError):
                updater.worker()
            prepare.assert_not_called()

    def test_staged_update_keeps_game_lock_until_old_instance_exits(self):
        data_root = self.root / 'data'
        program_root = self.root / 'program'
        data_root.mkdir()
        program_root.mkdir()
        executable = program_root / 'LostArkHelper.exe'
        executable.write_bytes(b'old executable')
        app.ROOT = data_root
        app.REQUEST_STOP = lambda: None
        archive = archive_bytes()
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)), \
                patch.object(updater, 'current_version', return_value='v0.2.0'), \
                patch.object(updater, 'state', return_value={'latest_version': 'v0.3.0', 'latest_checksum': hashlib.sha256(archive).hexdigest()}), \
                patch.object(updater, 'prepare', return_value=(archive, 'LostArkHelper-Windows-x64-v0.3.0.zip')), \
                patch.object(updater.subprocess, 'Popen') as launch, \
                patch.object(updater, 'finish_update', side_effect=lambda operation, root, stop: operation.release()) as finish:
            updater.worker()
            self.assertTrue(data_root.joinpath('update-download.bin').is_file())
            staged_executable = data_root / 'update-runtime' / 'program' / 'LostArkHelper.exe'
            launch.assert_called_once()
            self.assertEqual(Path(launch.call_args.args[0][0]).resolve(), staged_executable.resolve())
            self.assertEqual(launch.call_args.args[0][1], '--update-worker')
            self.assertEqual([Path(item).resolve() for item in launch.call_args.args[0][2:]],
                             [data_root.resolve(), program_root.resolve(), executable.resolve()])
            finish.assert_called_once()
            self.assertEqual(Path(finish.call_args.args[1]).resolve(), data_root.resolve())

    def test_api_requires_login_confirmation_and_source(self):
        app.ROOT = self.root
        app.LOCAL_TOKEN = 'test-local'
        app.INSTANCE_ID = 'test'
        import http.client
        from http.server import ThreadingHTTPServer
        import threading
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        app.PORT = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        def call(path, body, cookie='', origin=''):
            connection = http.client.HTTPConnection('127.0.0.1', app.PORT)
            connection.request('POST', path, body=body, headers={'Cookie': cookie, 'Origin': origin, 'Content-Type': 'application/json', 'X-Ark-Request': '1'})
            response = connection.getresponse()
            response.read()
            code = response.status
            connection.close()
            return code
        try:
            self.assertEqual(call('/api/local/update', '{"check":true}', origin='http://127.0.0.1:'+str(app.PORT)), 401)
            self.assertEqual(call('/api/local/update', '{"check":true}', 'ark_session=test-local', 'https://evil.example'), 403)
            self.assertEqual(call('/api/local/update', '{}', 'ark_session=test-local', 'http://127.0.0.1:'+str(app.PORT)), 400)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
