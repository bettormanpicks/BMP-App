@echo off
cd /d C:\Users\n8roc\PythonScripts\Streamlit\GitHub
echo ===============================
echo TABLE TENNIS DATA UPDATE START
echo %date% %time%
echo ===============================
echo.
echo REMINDER: Have you updated curl_command.txt?
echo Copy as cURL (bash) from DevTools before continuing.
echo.
pause
echo Running TT Elite matchlogs...
python tabletennis\getelitematchlogs.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running Czech matchlogs...
python tabletennis\getczechmatchlogs.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running Setka matchlogs...
python tabletennis\getsetkamatchlogs.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running TT Cup matchlogs...
python tabletennis\getttcupmatchlogs.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running TT Elite schedule...
python tabletennis\geteliteschedule.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running Czech schedule...
python tabletennis\getczechschedule.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running Setka schedule...
python tabletennis\getsetkaschedule.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Running TT Cup schedule...
python tabletennis\getttcupschedule.py
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 20
echo Building TT Elite H2H...
python tabletennis\buildeliteh2h.py
echo Building Czech H2H...
python tabletennis\buildczechh2h.py
echo Building Setka H2H...
python tabletennis\buildsetkah2h.py
echo Building TT Cup H2H...
python tabletennis\buildttcuph2h.py
echo Building All Leagues...
python buildallleagues.py
echo Uploading League Files to Supabase...
python upload_tt_leagues_to_supabase.py
echo Uploading Combined Files to Supabase...
python upload_tt_all_to_supabase.py
echo ===============================
echo UPDATE COMPLETE
echo %date% %time%
echo ===============================
pause