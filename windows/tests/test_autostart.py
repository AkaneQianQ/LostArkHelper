import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
import autostart

class Key:
    def __enter__(self):return self
    def __exit__(self,*args):pass
class Registry:
    HKEY_CURRENT_USER=1;KEY_READ=2;KEY_SET_VALUE=3;REG_SZ=1
    def __init__(self):self.values={}
    def OpenKey(self,*args):return Key()
    def CreateKeyEx(self,*args):return Key()
    def QueryValueEx(self,k,n):
        if n not in self.values:raise FileNotFoundError()
        return self.values[n],self.REG_SZ
    def SetValueEx(self,k,n,reserved,kind,value):self.values[n]=value
    def DeleteValue(self,k,n):
        if n not in self.values:raise FileNotFoundError()
        del self.values[n]

class StartupTests(unittest.TestCase):
    def test_enable_disable_and_external_change(self):
        reg=Registry()
        with patch.object(autostart,'registry',return_value=reg),patch.object(autostart.os,'name','nt'),patch.object(autostart,'COMMAND','"C:\\App Folder\\LostArkHelper.exe" --no-browser'):
            self.assertFalse(autostart.state()['enabled'])
            self.assertTrue(autostart.set_enabled(True)['matches_current'])
            reg.values[autostart.NAME]='old-location'
            self.assertFalse(autostart.state()['matches_current'])
            self.assertTrue(autostart.set_enabled(True)['matches_current'])
            self.assertFalse(autostart.set_enabled(False)['enabled'])
            self.assertFalse(autostart.set_enabled(False)['enabled'])
    def test_command_quoted_and_no_browser(self):
        cmd=autostart.command(executable='/test path/helper.exe',frozen=True)
        self.assertIn('"',cmd);self.assertTrue(cmd.endswith('--no-browser'))
        source=autostart.command(executable='/test path/python.exe',launcher='/app path/launcher.py',frozen=False)
        self.assertIn('launcher.py"',source);self.assertTrue(source.endswith('--no-browser'))
    def test_reject_nonboolean(self):
        with self.assertRaises(ValueError):autostart.set_enabled('true')
if __name__=='__main__':unittest.main()
