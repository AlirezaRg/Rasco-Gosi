' RASCO Launcher - runs rasco.py silently without a console window
' این فایل رو کنار rasco.py بگذار، بعد یه شورتکات ازش روی دسکتاپ بساز

Set objShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strPath
objShell.Run "python """ & strPath & "\rasco.py""", 0, False