' IGRIS helper - launch a command in a fully hidden, detached window.
' Usage:  wscript.exe _hidden.vbs "<command line>"
' Window style 0 = hidden, bWaitOnReturn = False (fire-and-forget).
' The child keeps running after the launcher window closes.
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count < 1 Then WScript.Quit 1
sh.Run WScript.Arguments(0), 0, False
