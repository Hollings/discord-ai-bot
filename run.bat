:: update line 5 with your webui location

start /B cmd /C ".\venv\Scripts\activate.bat && python bot.py"
start /B cmd /C ".\venv\Scripts\activate.bat && python bot-generator.py"
cd Z:\Documents\stable-diffusion-webui
start /B webui.bat
pause