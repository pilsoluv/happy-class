Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\USER\happy-class"
WshShell.Run """C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"" ""C:\Users\USER\happy-class\run_air_loop.py""", 0, False