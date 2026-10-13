!macro customInstall
  DetailPrint "Setting up Python environment..."
  nsExec::ExecToLog 'powershell.exe -ExecutionPolicy Bypass -File "$INSTDIR\resources\installer\download-deps.ps1" -InstallDir "$INSTDIR"'
  DetailPrint "Setting up tools (ADB)..."
  nsExec::ExecToLog 'powershell.exe -ExecutionPolicy Bypass -File "$INSTDIR\resources\installer\download-tools.ps1" -Only adb'
!macroend
