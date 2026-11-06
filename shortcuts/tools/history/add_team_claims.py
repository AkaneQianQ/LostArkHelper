import pathlib,json,copy,uuid,plistlib,subprocess,hashlib
D=pathlib.Path('outputs/命运方舟一键助手');src=D/'命运方舟一键助手.source.json';p=json.loads(src.read_text());a=p['WFWorkflowActions']
if any('task_id=12' in str(x) for x in []):raise RuntimeError()
# Preserve the full known task-5 pre-query, submission, post-query confirmation block.
block=a[1208:1440]
assert len(block)==232
assert block[-1]['WFWorkflowActionIdentifier'].endswith('.conditional')
def clone(tid):
 b=copy.deepcopy(block);ids={}
 for x in b:
  v=x['WFWorkflowActionParameters']
  for k in ['UUID','GroupingIdentifier']:
   if k in v:ids.setdefault(v[k],str(uuid.uuid4()).upper())
 def replace(x):
  if isinstance(x,dict):return {k:replace(v) for k,v in x.items()}
  if isinstance(x,list):return [replace(v) for v in x]
  if isinstance(x,str):return ids.get(x,x)
  return x
 b=replace(b)
 for x in b:
  v=x['WFWorkflowActionParameters'];k=x['WFWorkflowActionIdentifier']
  if k.endswith('.conditional') and v.get('WFNumberValue')==5:v['WFNumberValue']=tid
  if k.endswith('.downloadurl') and 'partnergettaskreward' in v.get('WFURL',''):
   for z in v['WFFormValues']['Value']['WFDictionaryFieldValueItems']:
    if z['WFKey']['Value']['string']=='task_id':z['WFValue']['Value']['string']=str(tid)
  if k.endswith('.gettext') and v.get('WFTextActionText')=='任务 5：领取已确认。':v['WFTextActionText']=f'任务 {tid}：领取已确认。'
 return b
for x in a:
 v=x['WFWorkflowActionParameters']
 if x['WFWorkflowActionIdentifier'].endswith('.text.match') and v.get('WFMatchTextPattern')=='^[2345]$':v['WFMatchTextPattern']='^(?:2|3|4|5|12|13)$'
 if x['WFWorkflowActionIdentifier'].endswith('.comment'):v['WFCommentActionText']=v.get('WFCommentActionText','').replace('仅领 2/3/4/5','仅领 2/3/4/5/12/13')
a[1440:1440]=clone(12)+clone(13)
p['WFWorkflowName']='命运方舟一键助手·小队任务版';src.write_text(json.dumps(p,ensure_ascii=False,indent=2))
raw=pathlib.Path('work/shortcuts/unsigned/team.shortcut');raw.write_bytes(plistlib.dumps(p,fmt=plistlib.FMT_BINARY));target=D/'命运方舟一键助手·小队任务版.shortcut'
subprocess.run(['/usr/bin/shortcuts','sign','--mode','anyone','--input',str(raw),'--output',str(target)],check=True)
(D/'SHA256SUMS.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
# Ensure every UUID reference resolves; enforce a balanced control-flow graph.
ids=[x['WFWorkflowActionParameters']['UUID'] for x in a];assert len(ids)==len(set(ids))
stack=[]
for x in a:
 v=x['WFWorkflowActionParameters']
 if 'WFControlFlowMode' not in v:continue
 if v['WFControlFlowMode']==0:stack.append(v['GroupingIdentifier'])
 elif v['WFControlFlowMode']==2:assert stack.pop()==v['GroupingIdentifier']
assert not stack
print('快捷指令已添加任务 12、13，控制流与 UUID 检查通过。')
