@echo off
rem Runs dev.ps1 without needing to change the PowerShell execution policy. Arguments pass through.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
