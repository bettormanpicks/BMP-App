@echo off

cd /d C:\Users\n8roc\PythonScripts\Streamlit\GitHub

echo ===============================
echo TABLE TENNIS DATA UPDATE START
echo %date% %time%
echo ===============================

echo Running TT Elite matchlogs...
python tabletennis\getttmatchlogs.py

timeout /t 45

echo Running Czech matchlogs...
python tabletennis\getczechmatchlogs.py

timeout /t 45

echo Running TT Elite schedule...
python tabletennis\getttschedule.py

timeout /t 45

echo Running Czech schedule...
python tabletennis\getczechschedule.py

timeout /t 45

echo Building TT Elite H2H...
python tabletennis\buildtth2h.py

echo Building Czech H2H...
python tabletennis\buildczechh2h.py

echo Pushing updates to GitHub...
git add tabletennis/data/
git commit -m "Updated table tennis data"
git push origin main

echo ===============================
echo UPDATE COMPLETE
echo %date% %time%
echo ===============================

pause