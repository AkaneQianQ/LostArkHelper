import contextlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'service'))
import app
import automation
import credentials
import helper
import scheduler
import store
import updater
from http.server import ThreadingHTTPServer

class LocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def test_database_closes_on_success_and_error(self):
        import sqlite3
        with store.connect(self.root) as db:
            db.execute("INSERT INTO settings VALUES (1, '{}')")
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')
        with self.assertRaises(RuntimeError):
            with store.connect(self.root) as rollback_db:
                rollback_db.execute("UPDATE settings SET value='changed'")
                raise RuntimeError('abort transaction')
        with self.assertRaises(sqlite3.ProgrammingError):
            rollback_db.execute('SELECT 1')
        with store.connect(self.root) as check:
            self.assertEqual(check.execute('SELECT value FROM settings').fetchone()[0], '{}')

    def test_activity(self):
        self.assertEqual(helper.VERSION, '2611')
        self.assertEqual(set(helper.VERIFIED), set(range(1,14)))
        self.assertEqual(helper.ACTIVITY['inferred_task_ids'], list(range(6,12)))

    def test_credentials_encrypted_and_private(self):
        config = {'cookie':'private-test-value', 'form':{'token':'private-test-token'}}
        credentials.write(self.root, config)
        self.assertEqual(credentials.read(self.root), config)
        self.assertNotIn(b'private-test-token', (self.root/credentials.NAME).read_bytes())
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        for name in (credentials.NAME, credentials.KEY_NAME):
            self.assertEqual((self.root/name).stat().st_mode & 0o777, 0o600)
        (self.root/credentials.KEY_NAME).unlink()
        with self.assertRaises(OSError):
            credentials.read(self.root)
        self.assertFalse((self.root/credentials.KEY_NAME).exists())

    def test_credentials_reject_wide_key_permissions(self):
        credentials.write(self.root, {'cookie':'test'})
        (self.root/credentials.KEY_NAME).chmod(0o644)
        with self.assertRaises(OSError):
            credentials.read(self.root)

    def test_signin_refreshes_newly_claimable_milestone(self):
        class Fake:
            SIGN_IN='sign'; CLAIM='claim'; VERIFIED={6:1}; ApiError=helper.ApiError
            signed=False; claimed=False; calls=[]
            @classmethod
            def sign_status(cls, config): return cls.signed
            @classmethod
            def tasks(cls, config):
                return [{'id':6,'status':2 if cls.claimed else 1 if cls.signed else 0,'name':'milestone'}]
            @classmethod
            def request(cls, config, endpoint, params=None):
                cls.calls.append((endpoint, params))
                if endpoint == cls.SIGN_IN: cls.signed=True
                else: cls.claimed=True
        report={}
        self.assertEqual(automation.run(Fake,{},self.root,report=report),0)
        self.assertEqual(Fake.calls,[('sign',None),('claim',{'task_id':'6','type':'1'})])
        self.assertEqual(report['claimed'],[{'id':6,'name':'milestone'}])
        self.assertFalse((self.root/'pending-operation.json').exists())

    def test_process_lock(self):
        a, b = automation.OperationLock(self.root), automation.OperationLock(self.root)
        self.assertTrue(a.acquire())
        self.assertFalse(b.acquire())
        a.release()
        self.assertTrue(b.acquire())
        b.release()

    def test_atomic_state(self):
        p = self.root / 'state.json'
        automation.save_state(p, {'value': 1})
        automation.save_state(p, {'value': 2})
        self.assertEqual(json.loads(p.read_text()), {'value': 2})

    def test_schedule_coalesces(self):
        at = datetime(2026, 11, 5, 12, 42, tzinfo=store.TZ)
        hourly = dict(store.DEFAULT, enabled=True, minute=5)
        self.assertEqual(scheduler.latest_slot(hourly, at).isoformat(), '2026-11-05T12:05:00+08:00')
        daily = dict(store.DEFAULT, enabled=True, mode='daily', times=['09:00','18:00'])
        self.assertEqual(scheduler.latest_slot(daily, at).hour, 9)
        self.assertIsNone(scheduler.latest_slot(store.DEFAULT, at))

    def test_schedule_slot_persisted_once(self):
        store.settings(self.root, dict(store.DEFAULT, enabled=True, minute=5))
        at = datetime(2026,11,5,12,5,tzinfo=store.TZ)
        with patch.object(credentials, 'exists', return_value=True), patch.object(credentials, 'read', return_value={}), patch.object(automation,'run',return_value=0) as run:
            automation.execute_user(self.root, helper, scheduled_at=at)
            automation.execute_user(self.root, helper, scheduled_at=at)
            self.assertEqual(run.call_count,1)
        self.assertEqual(len(store.history(self.root)['items']),1)

    def test_uncertain_submission_blocks_later_claims_and_restart(self):
        class Fake:
            SIGN_IN='sign'; CLAIM='claim'; VERIFIED={12:1,13:1};ApiError=helper.ApiError
            @staticmethod
            def sign_status(c):return True
            @staticmethod
            def tasks(c):return [{'id':12,'status':1,'name':'team'}, {'id':13,'status':1,'name':'login'}]
            calls=[]
            @classmethod
            def request(cls,*args):cls.calls.append(args)
        report={}
        self.assertEqual(automation.run(Fake,{},self.root,report=report),1)
        self.assertEqual(len(Fake.calls),1)
        self.assertTrue((self.root/'pending-operation.json').exists())
        with self.assertRaises(helper.ApiError):automation.run(Fake,{},self.root)
        self.assertEqual(len(Fake.calls),1)

    def test_confirmed_pending_clears_without_resubmitting(self):
        class Fake:
            VERIFIED={12:1};ApiError=helper.ApiError
            @staticmethod
            def sign_status(c):return True
            @staticmethod
            def tasks(c):return [{'id':12,'status':2,'name':'team'}]
        automation.save_state(self.root/'pending-operation.json',{'action':12})
        self.assertEqual(automation.run(Fake,{},self.root),0)
        self.assertFalse((self.root/'pending-operation.json').exists())

    def test_http_security_and_bootstrap(self):
        app.ROOT=self.root;app.LOCAL_TOKEN='test-local-secret';app.INSTANCE_ID='test-instance'
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        app.PORT=server.server_address[1]
        thread=threading.Thread(target=server.serve_forever);thread.start()
        def call(method,path,body=None,**headers):
            c=http.client.HTTPConnection('127.0.0.1',app.PORT)
            c.request(method,path,body=body,headers=headers)
            r=c.getresponse();data=r.read();head=dict(r.getheaders());status=r.status;c.close();return status,head,data
        try:
            self.assertEqual(call('GET','/api/status')[0],401)
            self.assertEqual(call('GET','/open?key=wrong')[0],403)
            status,head,_=call('GET','/open?key='+app.LOCAL_TOKEN)
            self.assertEqual(status,303);self.assertIn('HttpOnly',head['Set-Cookie'])
            cookie=head['Set-Cookie'].split(';')[0]
            self.assertEqual(call('GET','/api/auth/me',Cookie=cookie)[0],200)
            self.assertEqual(call('GET','/api/status',Cookie=cookie)[0],200)
            self.assertEqual(call('GET','/api/auth/me',Host='evil.example')[0],403)
            h={'Cookie':cookie,'Content-Type':'application/json','X-Ark-Request':'1'}
            self.assertEqual(call('POST','/api/schedule','{}',Origin='https://evil.example',**h)[0],403)
            h['Origin']='http://127.0.0.1:'+str(app.PORT)
            settings=dict(store.DEFAULT,enabled=True,minute=5)
            self.assertEqual(call('POST','/api/schedule',json.dumps(settings),**h)[0],200)
            self.assertEqual(store.settings(self.root)['minute'],5)
            self.assertEqual(call('POST','/api/auth/register','{}',**h)[0],403)
            with patch.object(app, 'REQUEST_STOP') as stop:
                self.assertEqual(call('POST','/api/local/stop','{}',**h)[0],400)
                stop.assert_not_called()
                self.assertEqual(call('POST','/api/local/stop','{"confirm":true}',**h)[0],200)
                stop.assert_called_once()
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
