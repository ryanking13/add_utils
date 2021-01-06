set shell = CreateObject("WScript.Shell")

For i = 1 To 100
  WScript.Sleep 180000
  shell.SendKeys"{SCROLLLOCK}"
  shell.SendKeys"{SCROLLLOCK}"
Next