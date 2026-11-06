import pathlib,json,plistlib,subprocess,hashlib,uuid
from build import interp,out
D=pathlib.Path('outputs/命运方舟一键助手');p=json.loads((D/'命运方舟一键助手.source.json').read_text());actions=[];n=0
for a in p['WFWorkflowActions']:
 k=a['WFWorkflowActionIdentifier'];v=a['WFWorkflowActionParameters']
 if k.endswith('.urlencode') and v.get('WFEncodeMode')=='Decode':
  # URL decoding is a text parameter, not a generic content input.
  x=v['WFInput']
  if x.get('WFSerializationType')=='WFTextTokenAttachment':v['WFInput']=interp(x);n+=1
  # A URL decoder may expose a URL content item: force its output to text
  # before downstream regex validation or cookie construction.
  old=v['UUID'];new=str(uuid.uuid4()).upper();v['UUID']=new
  actions.append(a)
  actions.append({'WFWorkflowActionIdentifier':'is.workflow.actions.gettext','WFWorkflowActionParameters':{'UUID':old,'WFTextActionText':interp(out(new))}})
  continue
 actions.append(a)
p['WFWorkflowActions']=actions;p['WFWorkflowName']='命运方舟一键助手·链接版v4'
(D/'命运方舟一键助手.source.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
f=pathlib.Path('work/shortcuts/unsigned/token-v4.shortcut');f.write_bytes(plistlib.dumps(p,fmt=plistlib.FMT_BINARY));o=D/'命运方舟一键助手·链接版v4.shortcut'
subprocess.run(['/usr/bin/shortcuts','sign','--mode','anyone','--input',str(f),'--output',str(o)],check=True)
(D/'SHA256SUMS.txt').write_text(hashlib.sha256(o.read_bytes()).hexdigest()+'  '+o.name+'\n')
print('规范化解码动作：',n)
