# 205.2-assessment
Pathshield – User’s Guide
The pathshield app allows you to plot safer and more informed navigation routes, influenced by safety and traffic data. 
Dependencies
To run this app currently, you will need some dependencies in python. When officially released this will be running on a server so no need for dependencies.
Current python packages to be installed by pip are listed below:
-	Joblib
-	Osmnx
-	Network
-	Folium
-	Shapely
-	Geopandas
-	Pandas
-	Flask
-	Numpy
-	Dotenv
-	sklearn
once these are installed in the project’s environment, we can continue to run the application.
Running the Application
The application hosts on a local host server. To start the server, run “run.py” in the prototype 5 folder, then put http://127.0.0.1:5000 in your chrome or preferred browsers search bar while the program is running.

Navigating the program
If you don’t have an account, you can register with the register here link, it will prompt you to enter a username, email, and password.
 
Once you have an account, you can log in using the login screen. Enter your email and password to continue.
(for debugging there is a test user, email: testuser@gmail.com, password: 123456)

Once logged in there is a dashboard with 3 options: logout, preferences, and view map. Logout will exit the program back to the login screen, preferences will take you to settings (these are currently placeholders as for the MVP they were minor features like changing the UI appearance) and view map will take you to the map screen.
 
Map Input Screen
The map screen lets you input a starting point and a destination, with a mode of transport (currently for the MVP only driving is supported) the inputs should be names of landmarks or addresses with suburbs (e.g. Sky tower, 45 Colchester Avenue Glendowie, McDonalds Greenlane)

Once you’ve input your addresses, then click the Generate Route button. It’ll load for a few seconds, then move you to the interactive map.
If the address is invalid, then the app will pop up an error and let you reenter the addresses. (addresses must be in the Auckland region)
 
Map Screen
The route will be generated and displayed on the map. The red line is the non-machine learning adjusted route, and the green is the route adjusted for high crime areas and traffic. The cost calculator will calculate the cost for the route, as well as the time to get to the destination. You can compute a new route with the “Compute New Route” button.

That’s all you need to successfully navigate the app and generate routes!
