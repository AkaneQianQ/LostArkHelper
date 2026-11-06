import pathlib,json,hashlib
import build as lib
ROOT=pathlib.Path(__file__).resolve().parents[2];lib.OUT=ROOT/'outputs/命运方舟一键助手';NAME='命运方舟一键助手';FILE='lostark-local-link.txt'

def parse(b,link):
 b.regex(link,r'^https://(?:lostark\.qq\.com|bbs\.lostark\.qq\.com)(?::443)?/[^\s#]*\?[^\s#]+$','请提供官方 HTTPS 活动链接，需包含登录参数；不接受其他域名或带片段的链接。')
 def param(k,required=True):
  m=b.match(link,r'(?<=[?&]'+k+r'=)[^&#]*');n=b.count(m)
  if required:b.require(n,1,'链接缺少或重复参数：'+k+'。请重新获取完整链接。')
  else:
   with b.cond(n,2,1):b.stop('链接参数重复：'+k)
  d=b.add('urlencode',WFInput=b.txt(lib.interp(m)),WFEncodeMode='Decode')
  return b.set('链接_'+k,d)
 v={k:param(k) for k in ['token','userId','appOpenid','appid','roleId','serverId','areaId','uin','acctype']}
 for k in ['token','appOpenid']:b.regex(v[k],r'^[A-Za-z0-9_-]+$','登录字段异常：'+k)
 for k in ['userId','appid','roleId','serverId','areaId']:b.regex(v[k],r'^[0-9]+$','角色或账号字段异常：'+k)
 b.regex(v['uin'],r'^[0-9]{1,10}$','QQ 账号字段格式异常。')
 b.require(v['appid'],'102037747','链接不属于已验证的 QQ 登录应用。')
 b.require(v['acctype'],'qc','目前只支持已验证的 QQ 登录链接。')
 a=param('accessToken',False);c=param('access_token',False)
 b.set('链接_access',b.txt(''))
 for x in [a,c]:
  with b.cond(b.count(b.match(x,r'.+')),4,1):
   b.regex(x,r'^[A-Za-z0-9_-]+$','access token 格式异常。')
   with b.cond(b.count(b.match(lib.var('链接_access'),r'.+')),4,1):
    with b.cond(x,5,lib.interp(lib.var('链接_access'))):b.stop('链接中的两个 access token 不一致，请重新获取链接。')
   b.set('链接_access',x)
 access=lib.var('链接_access');b.regex(access,r'^[A-Za-z0-9_-]+$','链接缺少 access token。')
 uin=b.match(b.txt(lib.interp('0000000000',v['uin'])),r'[0-9]{10}$')
 cookie=lib.interp('access_token=',access,'; acctype=qc; appid=',v['appid'],'; openid=',v['appOpenid'],'; accessToken=',access,'; appId=',v['appid'],'; appOpenId=',v['appOpenid'],'; appOpenid=',v['appOpenid'],'; openId=',v['appOpenid'],'; uin=o',uin)
 form={'token':v['token'],'user_id':v['userId'],'openid':v['appOpenid'],'access_token':access,'inv_user_id':'false','login_type':'qc','sRoleld':v['roleId'],'iUin':v['uin'],'sGiftPartition':v['serverId'],'sGiftArea':v['areaId'],'acctype':'qc','appid':v['appid']}
 parts=['{"cookie":"',b.txt(cookie),'","form":{']
 for i,(k,x) in enumerate(form.items()):parts.extend([(',' if i else '')+json.dumps(k)+':"',x,'"'])
 parts+=['}}']
 return b.set('配置',b.add('detect.dictionary',WFInput=b.txt(lib.interp(*parts))))

def build():
 a=json.loads((ROOT/'outputs/命运方舟快捷指令/方舟助手·执行核心.source.json').read_text())['WFWorkflowActions']
 start=next(i for i,x in enumerate(a) if x['WFWorkflowActionIdentifier']=='is.workflow.actions.setvariable' and x['WFWorkflowActionParameters'].get('WFVariableName')=='日志')-1
 b=lib.Builder();b.add('comment',WFCommentActionText='首次只需粘贴官方活动登录链接，后续自动读取签到领奖。链接保存在 iCloud Drive/Shortcuts/lostark-local-link.txt；删除可重新设置。链接含登录凭据，勿分享。2611 活动仅领 2/3/4/5。不支持并行运行，提交后异常须先在 App 核实。')
 f=b.add('documentpicker.open',WFGetFilePath=FILE,WFFileErrorIfNotFound=False,WFShowFilePicker=False,WFFileStorageService='iCloud Drive')
 b.set('原始链接',b.add('gettext',WFTextActionText=lib.interp(f)))
 b.set('首次设置',b.count(f))
 with b.cond(lib.var('首次设置'),4,0):
  b.set('原始链接',b.add('ask',WFAskActionPrompt='首次设置：请粘贴从官方 App 获取的完整活动链接。会自动提取登录和角色信息，保存后自动签到领奖。链接保存在自己的 iCloud Drive/Shortcuts，请勿分享。',WFInputType='Text',WFAllowsMultilineText=False))
 parse(b,lib.var('原始链接'))
 with b.cond(lib.var('首次设置'),4,0):b.add('documentpicker.save',WFInput=lib.var('原始链接'),WFFileDestinationPath=FILE,WFAskWhereToSave=False,WFSaveFileOverwrite=True,WFFileStorageService='iCloud Drive')
 b.set('模式',b.txt('claim'));b.a.extend(a[start:]);b.add('showresult',Text=lib.interp(lib.out(a[-1]['WFWorkflowActionParameters']['UUID'])))
 assert not any(x['WFWorkflowActionIdentifier']=='is.workflow.actions.runworkflow' for x in b.a)
 b.save(NAME)
 f=lib.OUT/(NAME+'.shortcut');(lib.OUT/'SHA256SUMS.txt').write_text(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n')
if __name__=='__main__':build()
