"""Offline credential fixtures only: no live env/token reads or auth requests."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import gui_bundle as bundle

API='https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/123'
PRIMARY='fixture-gui-token-never-live'
FALLBACK='fixture-debian-token-never-live'


class FixtureEnvironment(dict):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.reads=[]
    def get(self,key,default=None):
        self.reads.append(key);return super().get(key,default)


class Response(io.BytesIO):
    status=200


class GUIFetchCredentials(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=b'offline locked payload fixture\n'
        self.lock={'payload':{'size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}}

    def fetch(self,environment,*,error=None,check_redirect=False):
        env=FixtureEnvironment(environment);before=dict(env);requests=[];output=io.StringIO();diagnostic={}
        destination=self.root/str(len(list(self.root.iterdir())))
        def open_request(request,timeout):
            requests.append(request)
            if check_redirect:
                redirect=bundle.HTTPSOnlyRedirect().redirect_request(request,None,302,'Found',{},'https://release-assets.githubusercontent.com/fixture')
                self.assertFalse(redirect.has_header('Authorization'))
                with self.assertRaises(ValueError):
                    bundle.HTTPSOnlyRedirect().redirect_request(request,None,302,'Found',{},'http://example.invalid/fixture')
            if error:raise error
            return Response(self.data)
        # Swap in a synthetic mapping instead of inspecting/copying live env.
        with patch.object(bundle.os,'environ',env),patch.object(bundle,'load_lock',return_value=self.lock),\
                patch.object(bundle.urllib.request,'build_opener') as factory,contextlib.redirect_stdout(output):
            factory.return_value.open.side_effect=open_request
            try:
                result=bundle.fetch(destination,self.root/'unused-lock',diagnostic=diagnostic)
                failure=None
            except bundle.FetchError as caught:
                result=None;failure=caught
        self.assertEqual(dict(env),before) # Debian URL/token values are never replaced.
        rendered=output.getvalue()+json.dumps(diagnostic)+(str(failure) if failure else '')
        for secret in (PRIMARY,FALLBACK):self.assertNotIn(secret,rendered)
        if failure:
            self.assertFalse(destination.exists())
            self.assertFalse(list(self.root.glob('.gui-download-*')))
        else:
            self.assertEqual(destination.read_bytes(),self.data)
            self.assertEqual(result,self.lock['payload'])
        return env,requests,diagnostic,failure

    def test_fallback_only_for_exact_same_repo_asset_and_safe_redirect(self):
        for url in (API,API.replace('api.github.com/','api.github.com:443/')):
            with self.subTest(url=url):
                env,requests,diagnostic,error=self.fetch({'IDECK_GUI_PAYLOAD_URL':url,
                    'IDECK_DEBIAN_PAYLOAD_URL':'https://different.invalid/debian',
                    'IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK},check_redirect=True)
                self.assertIsNone(error);self.assertEqual(len(requests),1)
                self.assertEqual(requests[0].full_url,url)
                self.assertEqual(requests[0].get_header('Authorization'),'Bearer '+FALLBACK)
                self.assertIn('IDECK_DEBIAN_PAYLOAD_TOKEN',env.reads)
                self.assertNotIn('IDECK_DEBIAN_PAYLOAD_URL',env.reads)

    def test_gui_token_precedes_fallback_without_reading_it(self):
        env,requests,diagnostic,error=self.fetch({'IDECK_GUI_PAYLOAD_URL':API,
            'IDECK_GUI_PAYLOAD_TOKEN':PRIMARY,'IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK},check_redirect=True)
        self.assertIsNone(error)
        self.assertEqual(requests[0].get_header('Authorization'),'Bearer '+PRIMARY)
        self.assertNotIn('IDECK_DEBIAN_PAYLOAD_TOKEN',env.reads)

    def test_empty_gui_token_uses_existing_credential(self):
        env,requests,diagnostic,error=self.fetch({'IDECK_GUI_PAYLOAD_URL':API,
            'IDECK_GUI_PAYLOAD_TOKEN':'','IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK})
        self.assertIsNone(error);self.assertEqual(requests[0].get_header('Authorization'),'Bearer '+FALLBACK)

    def test_other_https_transports_never_read_or_receive_fallback(self):
        urls=['https://example.invalid/payload',API.replace('api.github.com','api.github.com.evil.invalid'),
              API.replace('Mi-Yomi/iDeck','Mi-Yomi/Other'),API.replace('Mi-Yomi/iDeck','Other/iDeck'),
              API.replace('Mi-Yomi/iDeck','mi-yomi/ideck'),API.replace('/assets/123','/123'),
              API.replace('/123','/not-a-number'),API+'?download=1',API+'#fragment',
              API.replace('api.github.com','api.github.com:444'),
              API.replace('https://','https://@'),API.replace('https://','https://:@')]
        for url in urls:
            with self.subTest(url=url):
                env,requests,diagnostic,error=self.fetch({'IDECK_GUI_PAYLOAD_URL':url,'IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK})
                self.assertIsNone(error);self.assertFalse(requests[0].has_header('Authorization'))
                self.assertNotIn('IDECK_DEBIAN_PAYLOAD_TOKEN',env.reads)

    def test_primary_token_outside_allowlist_still_fails_before_network(self):
        for url in ('https://example.invalid/payload',API.replace('https://','https://@')):
            with self.subTest(url=url):
                env,requests,diagnostic,error=self.fetch({'IDECK_GUI_PAYLOAD_URL':url,
                    'IDECK_GUI_PAYLOAD_TOKEN':PRIMARY,'IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK})
                self.assertIsNotNone(error);self.assertEqual(requests,[])
                self.assertEqual(diagnostic['code'],'GUI_FETCH_CONFIG_TOKEN_SCOPE')
                self.assertNotIn('IDECK_DEBIAN_PAYLOAD_TOKEN',env.reads)

    def test_invalid_url_never_reads_fallback(self):
        for url in (API.replace('https:','http:'),API.replace('https://','https://user:password@')):
            with self.subTest(url=url):
                env,requests,diagnostic,error=self.fetch({'IDECK_GUI_PAYLOAD_URL':url,'IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK})
                self.assertIsNotNone(error);self.assertEqual(requests,[])
                self.assertEqual(diagnostic['code'],'GUI_FETCH_CONFIG_URL')
                self.assertNotIn('IDECK_DEBIAN_PAYLOAD_TOKEN',env.reads)

    def test_fallback_http_failure_is_redacted_and_not_published(self):
        error=urllib.error.HTTPError(API+'?'+FALLBACK,401,FALLBACK,{'X-Fixture':PRIMARY},io.BytesIO(FALLBACK.encode()))
        env,requests,diagnostic,failure=self.fetch({'IDECK_GUI_PAYLOAD_URL':API,'IDECK_DEBIAN_PAYLOAD_TOKEN':FALLBACK},error=error)
        self.assertIsNotNone(failure);self.assertEqual(diagnostic['http_status'],401)
        self.assertEqual(diagnostic['received_bytes'],0)
