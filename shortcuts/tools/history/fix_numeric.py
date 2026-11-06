import pathlib,json,plistlib,subprocess,uuid
from build import out
D=pathlib.Path('outputs/命运方舟一键助手');p=json.loads((D/'命运方舟一键助手.source.json').read_text());a=[];n=0
for item in p['WFWorkflowActions']:
 v=item['WFWorkflowActionParameters']
 if item['WFWorkflowActionIdentifier'].endswith('.conditional') and v.get('WFControlFlowMode')==0 and 'WFNumberValue' in v:
  u=str(uuid.uuid4()).upper();src=v['WFInput']['Variable']
  a.append({'WFWorkflowActionIdentifier':'is.workflow.actions.number','WFWorkflowActionParameters':{'UUID':u,'WFNumberActionNumber':src}})
  v['WFInput']={'Type':'Variable','Variable':out(u)};n+=1
 a.append(item)
p['WFWorkflowActions']=a;p['WFWorkflowName']='命运方舟一键助手·实机修复'
(D/'命运方舟一键助手.source.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
f=pathlib.Path('work/shortcuts/unsigned/numeric.shortcut');f.write_bytes(plistlib.dumps(p,fmt=plistlib.FMT_BINARY))
subprocess.run(['/usr/bin/shortcuts','sign','--mode','anyone','--input',str(f),'--output',str(D/'命运方舟一键助手·实机修复.shortcut')],check=True)
print('明确转换数字条件：',n)
