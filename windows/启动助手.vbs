Option Explicit
Dim shell, fso, entry, result
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
entry = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "background.pyw")
On Error Resume Next
result = shell.Run("py -3 " & Chr(34) & entry & Chr(34), 0, False)
If Err.Number <> 0 Then
  MsgBox "Unable to start. Install Python 3.11+ with the py launcher, or use the debug CMD.", 16, "LostArkHelper"
End If
