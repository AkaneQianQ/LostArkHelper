"""Build one self-contained shortcut with first-run credential persistence."""
import pathlib,json,importlib.util,hashlib
import build as lib
ROOT=pathlib.Path(__file__).resolve().parents[2]
DEST=ROOT/'outputs/命运方舟一键助手';DEST.mkdir(exist_ok=True)
lib.OUT=DEST
NAME='命运方舟一键助手'
PATH='lostark-local-config.json'

def validate(b):
 for k in ['cookie']+['form.'+k for k in lib.FIELDS]:
  b.regex(b.txt(lib.interp(b.get(lib.var('配置'),k))),r'(?s)^(?!\s*$)(?!.*[<>\r\n]).+$','配置不完整，请填写 Cookie 及全部表单字段；占位内容不能使用。配置不合格时不会发起请求。')

def build():
 # Reuse verified API/action graph, without external shortcut dependencies.
 old=ROOT/'outputs/命运方舟快捷指令/方舟助手·执行核心.source.json'
 actions=json.loads(old.read_text())['WFWorkflowActions']
 start=next(i for i,a in enumerate(actions) if a['WFWorkflowActionIdentifier']=='is.workflow.actions.setvariable' and a['WFWorkflowActionParameters'].get('WFVariableName')=='日志')-1
 # The preceding Text action initializes the log and must be retained.
 body=actions[start:]
 b=lib.Builder()
 b.add('comment',WFCommentActionText='单指令版，首次录入完整凭据，之后自动读取并签到领奖。配置在「文件 → iCloud Drive → Shortcuts → lostark-local-config.json」中；删除文件可重新录入。含 Cookie/token 的文件请勿分享。仅领取 2611 活动白名单 2/3/4/5。不支持并行运行。提交后异常请先去 App 核实。')
 f=b.add('documentpicker.open',WFGetFilePath=PATH,WFFileErrorIfNotFound=False,WFShowFilePicker=False,WFFileStorageService='iCloud Drive')
 # Count the file, not its text: missing file is an empty result.
 b.set('配置文件',f)
 with b.cond(b.count(f),4,0):
  cfg={'cookie':'<填写完整 Cookie>','form':{k:'<填写 '+k+'>' for k in lib.FIELDS}}
  inp=b.add('ask',WFAskActionPrompt='首次设置：粘贴完整凭据 JSON，或替换模板中的全部占位值。只需填写一次，之后自动签到领奖。Cookie/token 文件会保存到自己的 iCloud Drive/Shortcuts。',WFInputType='Text',WFAllowsMultilineText=True,WFAskActionDefaultAnswer=json.dumps(cfg,ensure_ascii=False,indent=2))
  b.set('新配置原文',inp)
  b.set('配置',b.add('detect.dictionary',WFInput=inp))
  validate(b)
  saved=b.add('documentpicker.save',WFInput=lib.var('新配置原文'),WFFileDestinationPath=PATH,WFAskWhereToSave=False,WFSaveFileOverwrite=True,WFFileStorageService='iCloud Drive')
  b.set('配置文件',saved)
 # Parse every run; an invalid/corrupt persisted file stops before requests.
 b.set('配置',b.add('detect.dictionary',WFInput=lib.var('配置文件')))
 validate(b)
 b.set('模式',b.txt('claim'))
 b.a.extend(body)
 b.add('showresult',Text=lib.interp(lib.out(body[-1]['WFWorkflowActionParameters']['UUID'])))
 assert not any(a['WFWorkflowActionIdentifier']=='is.workflow.actions.runworkflow' for a in b.a)
 p=b.save(NAME)
 (DEST/'配置占位示例.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
 f=DEST/(NAME+'.shortcut');(DEST/'SHA256SUMS.txt').write_text(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n')
 return p
if __name__=='__main__':build()
