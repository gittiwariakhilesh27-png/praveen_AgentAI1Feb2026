docker-compose up -d --build  

python main.py


POST 
http://0.0.0.0:9090/chat
{ "message": "please make a booking for 1 passeger age 24year male to paris from delhi" }
{ "session_id": "session_20260221_024926", "message": "confirm the booking" }

GET
http://0.0.0.0:9090/conversation/session_20260221_024926