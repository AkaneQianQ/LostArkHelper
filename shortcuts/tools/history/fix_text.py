import json,pathlib,plistlib,subprocess,hashlib
from build import interp
D=pathlib.Path('outputs/命运方舟一键助手');p=json.loads((D/'命运方舟一键助手.source.json').read_text());n=0
for a in p['WFWorkflowActions']:
 k=a['WFWorkflowActionIdentifier'];v=a['WFWorkflowActionParameters']
 if k.endswith('.text.match'):
  x=v['text']
  if x.get('WFSerializationType')=='WFTextTokenAttachment':v['text']=interp(x);n+=1
 if k.endswith('.ask'):
  v.pop('WFInputType',None);v.pop('WFAllowsMultilineText',None)
  v['WFAskActionDefaultAnswer']=''
p['WFWorkflowName']='命运方舟一键助手·链接版v3'
(D/'命运方舟一键助手.source.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
f=pathlib.Path('work/shortcuts/unsigned/text-v3.shortcut');f.write_bytes(plistlib.dumps(p,fmt=plistlib.FMT_BINARY))
o=D/'命运方舟一键助手·链接版v3.shortcut'
subprocess.run(['/usr/bin/shortcuts','sign','--mode','anyone','--input',str(f),'--output',str(o)],check=True)
(D/'SHA256SUMS.txt').write_text(hashlib.sha256(o.read_bytes()).hexdigest()+'  '+o.name+'\n')
print('已修正文本参数数量：',n)
