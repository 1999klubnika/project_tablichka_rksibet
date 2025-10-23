RKSIBET — Online Competition System
RKSIBET is a modern, real-time online competition platform built with Flask. It supports jury input, viewer engagement, and live leaderboards, all with instant updates via WebSocket. The interface features a stylish and vibrant design that appeals to all users, including those who prefer simple, intuitive visuals—like grandma!

Features
For Spectators
View all participants and their scores per contest.
Color-coded score visualization.
Tooltips with jury member names on hover.
Real-time score updates via WebSocket.
Button to navigate directly to the Leaderboard.
For Jury Members
Login via username/password or simple name entry.
Edit only your own scoring column.
Finalize scores (after which editing is disabled).
View other jury scores live.
See the total scores and their own scores separately.
View live leaderboard updates.
Leaderboard
Automatic total scores calculation for participants.
Medals 🥇🥈🥉 for top positions.
Smooth animations upon score changes.
Real-time data updates via WebSocket.
Stylish, modern design that is easy to navigate and visually pleasing.
Design & Visuals
Theme: Vibrant and attractive, designed to be clear and engaging for users of any age.
Fonts: Google Fonts — Press Start 2P and Orbitron for a modern look.
Animations & Effects:
Pulsing highlights on score updates.
Smooth hover effects on table rows and buttons.
Glowing headers for emphasis.
The interface is crafted to be elegant and user-friendly—so straightforward that even users who are less tech-savvy (including grandmothers!) will find it appealing and easy to use.
Technologies Used
Backend: Python with Flask
Frontend: HTML, CSS, JavaScript
Real-Time Communication: WebSocket via Flask-Sock
Database: SQLite (or other options for storing participants, jury, scores)
Fonts & Effects: Google Fonts, CSS animations
Installation & Running
Clone the repository:
bash

git clone https://github.com/username/project_tablichka_rksibet.git
cd project_tablichka_rksibet
Create a virtual environment and install dependencies:
bash

python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt
Run the server:
bash

python app.py
Access the system:
Spectator view: http://127.0.0.1:5000/viewer
Jury login: http://127.0.0.1:5000/jury_login
Main page: http://127.0.0.1:5000/
Project Structure
plaintext

project_tablichka_rksibet/
├─ app.py                          # Main Flask application
├─ templates/                      # HTML templates
│  ├─ index.html                   # Main page
│  ├─ viewer.html                  # Spectator page
│  ├─ jury_login.html              # Jury login
│  ├─ jury_name.html               # Jury name input
│  ├─ jury_panel.html              # Jury control panel
│  └─ leaderboard.html             # Leaderboard page
├─ static/                         # Static files: CSS, JS, images
├─ requirements.txt                # Dependencies list
Future Enhancements
Support for multiple simultaneous contests.
Score history and undo features.
Responsive, mobile-friendly interface.
Dark/light theme switching.
Useful Links
Main Page
Flask Documentation
Google Fonts
Author
Created by 1999klubnika with contributions from Ryokuchan and SubBupka.
Summary
This platform offers instant score updates in a clean, attractive design that will delight all users, from tech-savvy teenagers to grandma. Its simple yet stylish interface ensures an enjoyable experience for everyone involved.
