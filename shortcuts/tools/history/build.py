import json, plistlib, uuid, pathlib, contextlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/命运方舟快捷指令'; OUT.mkdir(parents=True,exist_ok=True)
RAW=ROOT/'work/shortcuts/unsigned'; RAW.mkdir(exist_ok=True)
FIELDS='token user_id openid access_token inv_user_id login_type sRoleld iUin sGiftPartition sGiftArea acctype appid'.split()
CONFIG='方舟助手·本机配置'; CORE='方舟助手·执行核心'

def token(v):return {'WFSerializationType':'WFTextTokenAttachment','Value':v}
def var(n):return token({'Type':'ExtensionInput'} if n=='Shortcut Input' else {'Type':'Variable','VariableName':n})
def out(u):return token({'Type':'ActionOutput','OutputUUID':u,'OutputName':'结果'})
def text(s):return {'WFSerializationType':'WFTextTokenString','Value':{'string':s,'attachmentsByRange':{}}}
# UTF-16 offsets are required by Shortcuts.
def interp(*parts):
 s='';att={}
 for p in parts:
  if isinstance(p,dict):
   att['{%d, 1}'%(len(s.encode('utf-16-le'))//2)]=p['Value'];s+='\ufffc'
  else:s+=str(p)
 return {'WFSerializationType':'WFTextTokenString','Value':{'string':s,'attachmentsByRange':att}}
def dictionary(d):
 items=[]
 for k,v in d.items():
  items.append({'WFItemType':0,'WFKey':text(k),'WFValue':v if isinstance(v,dict) else text(v)})
 return {'WFSerializationType':'WFDictionaryFieldValue','Value':{'WFDictionaryFieldValueItems':items}}
class Builder:
 def __init__(self):self.a=[]
 def add(self,id,**p):
  if id=='conditional' and p.get('WFControlFlowMode')==0 and p.get('WFInput',{}).get('WFSerializationType')=='WFTextTokenAttachment':p['WFInput']={'Type':'Variable','Variable':p['WFInput']}
  if id=='count' and 'WFInput' in p:p['Input']=p.pop('WFInput')
  if id=='text.match' and 'WFInput' in p:p['text']=interp(p.pop('WFInput'))
  u=str(uuid.uuid4()).upper();p['UUID']=u;self.a.append({'WFWorkflowActionIdentifier':'is.workflow.actions.'+id,'WFWorkflowActionParameters':p});return out(u)
 def txt(self,s):return self.add('gettext',WFTextActionText=s)
 def set(self,n,v):self.add('setvariable',WFVariableName=n,WFInput=v);return var(n)
 def get(self,v,k):return self.add('getvalueforkey',WFInput=v,WFDictionaryKey=k,WFGetDictionaryValueType='Value')
 @contextlib.contextmanager
 def cond(self,v,op,n=None):
  g=str(uuid.uuid4()).upper();p={'WFInput':v,'WFCondition':op,'GroupingIdentifier':g,'WFControlFlowMode':0}
  if n is not None:p['WFNumberValue' if isinstance(n,(int,float)) else 'WFConditionalActionString']=n
  self.add('conditional',**p);yield;self.add('conditional',GroupingIdentifier=g,WFControlFlowMode=2)
 @contextlib.contextmanager
 def each(self,v):
  g=str(uuid.uuid4()).upper();self.add('repeat.each',WFInput=v,GroupingIdentifier=g,WFControlFlowMode=0);yield var('Repeat Item');self.add('repeat.each',GroupingIdentifier=g,WFControlFlowMode=2)
 def stop(self,msg):
  r=self.txt(msg);self.add('showresult',Text=interp(r));self.add('exit',WFResult=r)
 def require(self,v,n,msg):
  with self.cond(v,5,n):self.stop(msg)
 def match(self,v,pattern):return self.add('text.match',WFInput=v,WFMatchTextPattern=pattern,WFMatchTextCaseSensitive=True)
 def count(self,v):return self.add('count',WFInput=v,WFCountType='Items')
 def regex(self,v,pattern,msg):self.require(self.count(self.match(v,pattern)),1,msg)
 def run(self,name,v=None):return self.add('runworkflow',WFWorkflowName=name,WFShowWorkflow=False,**({'WFInput':v} if v else {}))
 def request(self,endpoint,extra=None):
  form={k:interp(self.get(var('配置'), 'form.'+k)) for k in FIELDS};form.update(extra or {})
  headers={'Accept':'application/json, text/plain, */*','Content-Type':'application/x-www-form-urlencoded','Origin':'https://bbs.lostark.qq.com','Referer':'https://bbs.lostark.qq.com/','Cookie':interp(self.get(var('配置'),'cookie')),'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 GH_QQConnect GameHelper_1010/1.10.0.4.2103160004'}
  r=self.add('downloadurl',WFURL='https://api.bbs.lostark.qq.com/'+endpoint+'2611',WFHTTPMethod='POST',WFHTTPBodyType='Form',WFFormValues=dictionary(form),WFHTTPHeaders=dictionary(headers),ShowHeaders=True,Advanced=True)
  self.require(self.get(r,'code'),200,'接口外层响应异常，已停止；如刚提交过签到或领奖，请先在 App 核实，不要重试。')
  self.require(self.get(r,'data.code'),0,'接口业务响应异常，已停止；如刚提交过操作，请先在 App 核实，不要重试。')
  if endpoint=='partnergetusertask':
   self.regex(self.txt(interp(r)),r'"data"\s*:\s*\[','任务列表格式变化，已停止。')
  return self.get(r,'data.data')
 def signed(self):
  p=self.request('partnersignlist');s=self.txt(interp(p))
  self.regex(s,r'"is_sign"\s*:\s*(?:true|false)\b','签到状态格式变化，已停止。')
  return self.count(self.match(s,r'"is_sign"\s*:\s*true\b'))
 def tasks(self):
  p=self.request('partnergetusertask')
  with self.each(p) as item:
   for k,pat in [('id',r'^[1-9][0-9]*$'),('type',r'^[1-3]$'),('status',r'^[0-3]$')]:
    self.regex(self.txt(interp(self.get(item,k))),pat,'任务字段异常，已停止。')
  return p
 def find(self,items,tid):
  self.set('匹配数',self.txt(''))
  self.set('状态',self.txt('-1'))
  with self.each(items) as item:
   with self.cond(self.get(item,'id'),4,tid):
    self.add('appendvariable',WFVariableName='匹配数',WFInput=self.txt('匹配'))
    self.set('状态',self.get(item,'status'))
  return self.count(self.match(self.txt(interp(var('匹配数'))),'匹配'))
 def save(self,name,questions=None):
  p={'WFWorkflowClientVersion':'4040','WFWorkflowMinimumClientVersion':900,'WFWorkflowMinimumClientVersionString':'900','WFWorkflowName':name,'WFWorkflowActions':self.a,'WFWorkflowIcon':{'WFWorkflowIconStartColor':4282601983,'WFWorkflowIconGlyphNumber':59511},'WFWorkflowInputContentItemClasses':['WFStringContentItem'],'WFWorkflowTypes':[],'WFWorkflowImportQuestions':questions or []}
  path=RAW/(name+'.shortcut');path.write_bytes(plistlib.dumps(p,fmt=plistlib.FMT_BINARY))
  (OUT/(name+'.source.json')).write_text(json.dumps(p,ensure_ascii=False,indent=2))
  subprocess.run(['/usr/bin/shortcuts','sign','--mode','anyone','--input',str(path),'--output',str(OUT/(name+'.shortcut'))],check=True)
  return p

def build():
 cfg={'cookie':'<填写完整 Cookie>','form':{k:'<填写 '+k+'>' for k in FIELDS}}
 b=Builder();b.add('comment',WFCommentActionText='只在自己的设备填写。含真实凭据的版本请勿分享。快捷指令可能通过 iCloud 同步至自己的设备；不是钥匙串加密存储。不要改名，三个入口依赖此名称。')
 b.txt(json.dumps(cfg,ensure_ascii=False,indent=2));b.add('detect.dictionary');b.save(CONFIG)
 b=Builder();b.add('comment',WFCommentActionText='2611 活动原型。仅领取 2/3/4/5，type=1。网络错误会中止；提交后中断须先去 App 核实。不支持同时运行或无人值守重试。请勿改名。')
 b.set('模式',var('Shortcut Input'));b.regex(b.txt(interp(var('模式'))),r'^(query|sign|claim)$','请从查询、签到或签到领奖入口运行。')
 b.set('配置',b.run(CONFIG))
 for k in ['cookie']+['form.'+k for k in FIELDS]:
  v=b.txt(interp(b.get(var('配置'),k)))
  b.regex(v,r'(?s)^(?!\s*$)(?!.*[<>\r\n]).+$','请先编辑「方舟助手·本机配置」，填写完整的占位字段。')
 b.set('日志',b.txt('命运方舟助手 · 2611'))
 signed=b.signed();b.set('已签到',signed)
 with b.cond(var('模式'),5,'query'):
  with b.cond(var('已签到'),4,0):
   b.request('partnersignin');b.require(b.signed(),1,'签到已提交但状态未确认。已停止，请先在 App 核实，不要立即重跑。')
   b.set('已签到',b.txt('1'))
 b.add('appendvariable',WFVariableName='日志',WFInput=b.txt(interp('签到状态（1=已签到，0=未签到）：',var('已签到'))))
 items=b.tasks()
 with b.each(items) as item:
  b.add('appendvariable',WFVariableName='日志',WFInput=b.txt(interp('任务 ID=',b.get(item,'id'),'；状态=',b.get(item,'status'),'（0未完成/1可领/2已领/3结束）')))
  with b.cond(b.get(item,'status'),4,1):
   tid=b.txt(interp(b.get(item,'id')))
   with b.cond(b.count(b.match(tid,r'^[2345]$')),4,0):
    b.add('appendvariable',WFVariableName='日志',WFInput=b.txt('上述任务不在本原型白名单，已跳过。'))
 with b.cond(var('模式'),4,'claim'):
  # Each task is queried afresh immediately before submission. No cached candidate list.
  for tid in [2,3,4,5]:
   n=b.find(b.tasks(),tid)
   with b.cond(n,2,1):b.stop('任务 ID 重复，已停止。请在 App 核实。')
   with b.cond(n,4,1):
    with b.cond(var('状态'),4,1):
     b.request('partnergettaskreward',{'task_id':str(tid),'type':'1'})
     b.require(b.find(b.tasks(),tid),1,'领奖已提交但任务缺失或重复，已停止。请在 App 核实，不要立即重跑。')
     b.regex(b.txt(interp(var('状态'))),r'^[23]$','领奖已提交但状态未确认为已领取或结束。已停止，请在 App 核实，不要立即重跑。')
     b.add('appendvariable',WFVariableName='日志',WFInput=b.txt('任务 '+str(tid)+'：领取已确认。'))
 with b.cond(var('模式'),4,'query'):b.add('appendvariable',WFVariableName='日志',WFInput=b.txt('本次仅查询。'))
 b.txt(interp(var('日志')));core=b.save(CORE)
 for name,mode in [('方舟助手·查询','query'),('方舟助手·签到','sign'),('方舟助手·签到领奖','claim')]:
  b=Builder();b.add('comment',WFCommentActionText='请先导入「方舟助手·本机配置」和「方舟助手·执行核心」。单次运行；不要并行点击多个入口。')
  r=b.run(CORE,b.txt(mode));b.add('showresult',Text=interp(r));b.save(name)
 (OUT/'配置占位示例.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
 return core
if __name__=='__main__':build()
