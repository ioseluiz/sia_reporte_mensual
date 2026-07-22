@echo off
chcp 65001 > nul
"C:\Users\jlmunoz\OneDrive - Autoridad del Canal de Panama\Documents\INICA\02_software\10_sia_reporte_mensual\venv\Scripts\python.exe" "C:\Users\jlmunoz\OneDrive - Autoridad del Canal de Panama\Documents\INICA\02_software\10_sia_reporte_mensual\exportar_proyectos_ph.py"
if %ERRORLEVEL% NEQ 0 pause
