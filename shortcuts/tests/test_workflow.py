"""Execute the emitted Shortcuts action graph against a mocked activity API."""
import json,re,unittest,pathlib,urllib.parse
from copy import deepcopy
P=pathlib.Path(__file__).resolve().parents[1]/'source/workflow.json'
class Halt(Exception):pass
class Runner:
 def __init__(self,mode='claim',signed=False,tasks=None,fault=None):
  self.link='https://lostark.qq.com/cp/demo/h5.html?'+urllib.parse.urlencode(dict(token='dummy',userId='123',appOpenid='dummy',appid='102037747',roleId='456',serverId='1',areaId='2',uin='123456',acctype='qc',accessToken='dummy',access_token='dummy'));self.persisted=True;self.files={};self.prompts=0;self.saved=0;self.mode=mode;self.signed=signed;self.tasks=deepcopy(tasks if tasks is not None else [{'id':2,'type':1,'status':1},{'id':99,'type':1,'status':1}]);self.fault=fault;self.calls=[];self.v={};self.o={};self.last=None;self.config={'cookie':'dummy', 'form':{k:'dummy' for k in 'token user_id openid access_token inv_user_id login_type sRoleld iUin sGiftPartition sGiftArea acctype appid'.split()}}
 def string(self,v):
  if isinstance(v,dict):return json.dumps(v)
  if isinstance(v,list):return '\n'.join(self.string(i) for i in v)
  return '' if v is None else str(v)
 def value(self,x):
  if isinstance(x,dict) and x.get('Type')=='Variable' and 'Variable' in x:return self.value(x['Variable'])
  if not isinstance(x,dict) or 'WFSerializationType' not in x:return x
  v=x['Value'];t=x['WFSerializationType']
  if t=='WFTextTokenAttachment':
   return self.mode if v['Type']=='ExtensionInput' else self.v.get(v.get('VariableName')) if v['Type']=='Variable' else self.o.get(v['OutputUUID'])
  if t=='WFTextTokenString':
   s=v['string']
   for key,a in sorted(v['attachmentsByRange'].items(),key=lambda i:int(i[0][1:].split(',')[0]),reverse=True):
    pos=int(key[1:].split(',')[0]);raw=s.encode('utf-16-le');s=raw[:pos*2].decode('utf-16-le')+self.string(self.value({'WFSerializationType':'WFTextTokenAttachment','Value':a}))+raw[(pos+1)*2:].decode('utf-16-le')
   return s
  if t=='WFDictionaryFieldValue':return {self.value(i['WFKey']):self.value(i['WFValue']) for i in v['WFDictionaryFieldValueItems']}
  raise AssertionError(t)
 def api(self,p):
  ep=p['WFURL'].split('/')[-1];self.calls.append(ep)
  assert p['WFURL'].startswith('https://api.bbs.lostark.qq.com/')
  form=self.value(p['WFFormValues']);assert form['token']=='dummy';assert 'access_token=dummy;' in self.value(p['WFHTTPHeaders'])['Cookie'];assert 'uin=o0000123456' in self.value(p['WFHTTPHeaders'])['Cookie']
  if ep=='partnersignlist2611':data={'is_sign':self.signed} if self.fault!='bad_sign' else {'is_sign':'false'}
  elif ep=='partnersignin2611':
   if self.fault=='network_sign':raise Halt('network')
   if self.fault!='sign_unchanged':self.signed=True
   data={}
  elif ep=='partnergetusertask2611':data=deepcopy(self.tasks)
  elif ep=='partnergettaskreward2611':
   tid=int(form['task_id']);assert tid in [2,3,4,5,12,13];assert form['type']=='1'
   if self.fault=='network_claim':raise Halt('network')
   if self.fault!='claim_unchanged':
    for t in self.tasks:
     if t['id']==tid:t['status']=2
   data={}
  else:raise AssertionError(ep)
  return {'code':401 if self.fault=='outer' else 200,'data':{'code':1 if self.fault=='inner' else 0,'data':data}}
 def run(self):
  self.exec(json.loads(P.read_text())['WFWorkflowActions']);return self.last
 def exec(self,actions):
  i=0
  while i<len(actions):
   a=actions[i];p=a['WFWorkflowActionParameters'];kind=a['WFWorkflowActionIdentifier'].split('is.workflow.actions.')[1];v=self.value(p.get('WFInput',p.get('Input',p.get('text',self.last))));r=None
   if kind in ('conditional','repeat.each'):
    if p['WFControlFlowMode']!=0:raise AssertionError('unbalanced')
    j=i+1
    while not (actions[j]['WFWorkflowActionParameters'].get('GroupingIdentifier')==p['GroupingIdentifier'] and actions[j]['WFWorkflowActionParameters']['WFControlFlowMode']==2):j+=1
    body=actions[i+1:j]
    if kind=='conditional':
     n=self.value(p.get('WFNumberValue',p.get('WFConditionalActionString')));op=p['WFCondition']
     if isinstance(n,(int,float)):
      try:v=float(v)
      except (ValueError,TypeError):pass
     yes=(v==n) if op==4 else (v!=n) if op==5 else (v>n) if op==2 else False
     if yes:self.exec(body)
    else:
     for item in (v or []):self.v['Repeat Item']=item;self.exec(body)
    i=j+1;continue
   if kind=='gettext':r=self.value(p['WFTextActionText'])
   elif kind=='getvalueforkey':
    r=v
    for key in p['WFDictionaryKey'].split('.'):r=r.get(key) if isinstance(r,dict) else None
   elif kind=='setvariable':self.v[p['WFVariableName']]=v;r=v
   elif kind=='appendvariable':
    name=p['WFVariableName'];old=self.v.get(name,[]);self.v[name]=(old if isinstance(old,list) else [old])+[v];r=self.v[name]
   elif kind=='number':
    try:r=float(self.string(self.value(p['WFNumberActionNumber'])))
    except (ValueError,TypeError):raise Halt('invalid number')
   elif kind=='urlencode':r=urllib.parse.unquote(self.string(v))
   elif kind=='text.match':r=re.findall(p['WFMatchTextPattern'],self.string(v))
   elif kind=='count':r=len(v) if isinstance(v,list) else 0 if v is None else 1
   elif kind=='documentpicker.open':r=[self.link] if self.persisted else []
   elif kind=='ask':self.prompts+=1;r=self.link
   elif kind=='documentpicker.save':self.saved+=1;self.persisted=True;r=[v]
   elif kind=='detect.dictionary':
    try:r=json.loads(v[0] if isinstance(v,list) else v)
    except (TypeError,ValueError):raise Halt('invalid config')
   elif kind=='downloadurl':r=self.api(p)
   elif kind=='showresult':r=self.value(p['Text'])
   elif kind=='comment':r=self.last
   elif kind=='exit':raise Halt(self.value(p['WFResult']))
   else:raise AssertionError(kind)
   self.o[p['UUID']]=r;self.last=r;i+=1
class Tests(unittest.TestCase):
 def test_existing_config(self):
  r=Runner();r.run();self.assertEqual(r.prompts,0);self.assertEqual(r.saved,0)
 def test_first_run(self):
  r=Runner();r.persisted=False;r.run();self.assertEqual(r.prompts,1);self.assertEqual(r.saved,1);self.assertTrue(r.signed)
  r.run();self.assertEqual(r.prompts,1);self.assertEqual(r.calls.count('partnersignin2611'),1)
 def test_bad_first_run_not_saved(self):
  r=Runner();r.persisted=False;r.link=r.link.replace('token=dummy','token=%3Ctoken%3E')
  with self.assertRaises(Halt):r.run()
  self.assertEqual(r.saved,0);self.assertEqual(r.calls,[])
 def test_link_rejections(self):
  for change in [lambda s:s.replace('https://lostark.qq.com','https://evil.example'),lambda s:s+'&token=other',lambda s:s.replace('access_token=dummy','access_token=other'),lambda s:s.replace('acctype=qc','acctype=wx'),lambda s:s.replace('roleId=456','roleId='),lambda s:s.replace('accessToken=dummy&access_token=dummy','other=x')]:
   r=Runner();r.persisted=False;r.link=change(r.link)
   with self.assertRaises(Halt):r.run()
   self.assertEqual(r.calls,[]);self.assertEqual(r.saved,0)
 def test_ios_action_schema(self):
  for a in json.loads(P.read_text())['WFWorkflowActions']:
   k=a['WFWorkflowActionIdentifier'];p=a['WFWorkflowActionParameters']
   if k.endswith('.conditional') and p.get('WFControlFlowMode')==0:
    self.assertEqual(p['WFInput']['Type'],'Variable');self.assertEqual(p['WFInput']['Variable']['WFSerializationType'],'WFTextTokenAttachment')
   if k.endswith('.count'):self.assertIn('Input',p);self.assertNotIn('WFInput',p)
   if k.endswith('.text.match'):self.assertIn('text',p);self.assertNotIn('WFInput',p);self.assertEqual(p['text']['WFSerializationType'],'WFTextTokenString')
 def test_team_claims(self):
  r=Runner(tasks=[{'id':i,'type':3 if i==12 else 1,'status':1} for i in [12,13,99]]);r.run()
  self.assertEqual([t['status'] for t in r.tasks],[2,2,1]);self.assertEqual(r.calls.count('partnergettaskreward2611'),2)
 def test_team_already_claimed(self):
  r=Runner(tasks=[{'id':i,'type':1,'status':2} for i in [12,13]]);r.run();self.assertNotIn('partnergettaskreward2611',r.calls)
 def test_team_uncertain_stop(self):
  r=Runner(tasks=[{'id':i,'type':1,'status':1} for i in [12,13]],fault='claim_unchanged')
  with self.assertRaises(Halt):r.run()
  self.assertEqual(r.calls.count('partnergettaskreward2611'),1)
 def test_decode_text_schema(self):
  for a in json.loads(P.read_text())['WFWorkflowActions']:
   if a['WFWorkflowActionIdentifier'].endswith('.urlencode'):
    self.assertEqual(a['WFWorkflowActionParameters']['WFInput']['WFSerializationType'],'WFTextTokenString')
 def test_alias(self):
  r=Runner();r.link=r.link.replace('&access_token=dummy','');r.run();self.assertTrue(r.signed)
 def test_self_contained(self):
  a=json.loads(P.read_text())['WFWorkflowActions'];self.assertFalse(any(i['WFWorkflowActionIdentifier']=='is.workflow.actions.runworkflow' for i in a))
 def test_claim(self):
  r=Runner();r.run();self.assertEqual(r.tasks[0]['status'],2);self.assertEqual(r.tasks[1]['status'],1);self.assertEqual(r.calls.count('partnergettaskreward2611'),1)
 def test_empty(self):
  r=Runner(tasks=[]);r.run();self.assertNotIn('partnergettaskreward2611',r.calls)
 def test_signed(self):
  r=Runner(signed=True);r.run();self.assertNotIn('partnersignin2611',r.calls)
 def test_stop_faults(self):
  for fault in ['bad_sign','network_sign','sign_unchanged','claim_unchanged','network_claim','outer','inner']:
   with self.subTest(fault=fault):
    r=Runner(fault=fault)
    with self.assertRaises(Halt):r.run()
    self.assertLessEqual(r.calls.count('partnersignin2611'),1);self.assertLessEqual(r.calls.count('partnergettaskreward2611'),1)
 def test_duplicate(self):
  r=Runner(tasks=[{'id':2,'type':1,'status':1}]*2)
  with self.assertRaises(Halt):r.run()
  self.assertNotIn('partnergettaskreward2611',r.calls)
 def test_placeholder(self):
  r=Runner();r.link=r.link.replace('token=dummy','token=%3Ctoken%3E')
  with self.assertRaises(Halt):r.run()
  self.assertEqual(r.calls,[])
 def test_invalid_fields(self):
  for task in [{'id':2,'status':1},{'id':2,'type':1,'status':4}]:
   r=Runner(tasks=[task])
   with self.assertRaises(Halt):r.run()
   self.assertNotIn('partnergettaskreward2611',r.calls)
 def test_all_whitelist(self):
  r=Runner(tasks=[{'id':i,'type':1,'status':1} for i in [1,2,3,4,5,6]]);r.run();self.assertEqual([t['status'] for t in r.tasks],[1,2,2,2,2,1])
if __name__=='__main__':unittest.main()
