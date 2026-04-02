@echo off

cd /d C:\Users\n8roc\PythonScripts\Streamlit\GitHub

echo ===============================
echo TABLE TENNIS DATA UPDATE START
echo %date% %time%
echo ===============================

echo Running TT Elite matchlogs...
python tabletennis\getelitematchlogs.py

timeout /t 45

echo Running Czech matchlogs...
python tabletennis\getczechmatchlogs.py

timout /t 45
echo Running Setka matchlogs...
python tabletennis\getsetkamatchlogs.py

timeout /t 45

echo Running TT Cup matchlogs...
python tabletennis\getttcupmatchlogs.py

timeout /t 45

echo Running TT Elite schedule...
python tabletennis\geteliteschedule.py

timeout /t 45

echo Running Czech schedule...
python tabletennis\getczechschedule.py

timeout /t 45

echo Running Setka schedule...
python tabletennis\getsetkaschedule.py

timeout /t 45

echo Running TT Cup schedule...
python tabletennis\getttcupschedule.py

timeout /t 45

echo Building TT Elite H2H...
python tabletennis\buildeliteh2h.py

echo Building Czech H2H...
python tabletennis\buildczechh2h.py

echo Building Setka H2H...
python tabletennis\buildsetkah2h.py

echo Building TT Cup H2H...
python tabletennis\buildttcuph2h.py

echo Pushing updates to GitHub...
git pull
git add tabletennis/data/
git commit -m "Updated table tennis data"
git push origin main

echo ===============================
echo UPDATE COMPLETE
echo %date% %time%
echo ===============================

pause