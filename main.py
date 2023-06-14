import os
from flask import Flask, render_template, request, url_for, flash, redirect, send_file

import requests
import json
import random
from werkzeug.utils import secure_filename
import datetime
import openrouteservice as ors
from haversine import haversine, Unit
import html

APIKEY = os.environ['APIKEY']

def distance(coordOne, coordTwo):
   return haversine(coordOne,coordTwo)

def getRoute(start,end):
  import requests

  headers = {
    'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
}
  call = requests.get(f'https://api.openrouteservice.org/v2/directions/foot-walking?api_key={APIKEY}&start={start[1]},{start[0]}&end={end[1]},{end[0]}', headers=headers)
  try:
    call = json.loads(call.text)
  except:
    call = ""
  return call
  #routes = client.directions(coords,format=geojson)
  #print(routes)
  #return routes
  

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic'}
app = Flask(__name__)
SESSION_TYPE = "redis"
LASTNAME_PATH = "systemFiles/lastFile.txt"
PERMANENT_SESSION_LIFETIME = 1800
app.config.update(SECRET_KEY=os.urandom(24))
app.config.from_object(__name__)
app.config['UPLOAD_FOLDER'] = "aeds"


def extension(filename):
  return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
  return '.' in filename and \
         filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sort_list(list1, list2):
 
    zipped_pairs = zip(list2, list1)
 
    z = [x for _, x in sorted(zipped_pairs)]
 
    return z

#make an http request to openstreetmaps for reverse geocoding
def getAddress(lat,long):
  x = requests.get(f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={long}&format=json')
  data=json.loads(str(x.text))
  return data["display_name"]

def getData():
  with open('locations.csv','r') as dataFile:
    data = dataFile.readlines()

  data = [line[:-1].split("||") for line in data]
  dicData = []
  header = data[0]
  for line in data:
    thisLine = {}
    for i in range(len(line)):
      thisLine[header[i]] = line[i]
    dicData.append(thisLine)
  return dicData

#convert a diccionary to a string to be placed in the database
def dataBaseString(dic):
  return dic['LATITUDE']+"||"+dic['LONGITUDE'] +"||"+dic['ADDRESS'] + '||'+ dic['FILENAME'] + "||" + dic['COMMENTS'] + "||" +dic['DATE'] + "||" +dic['VALIDATED'] + "\n"

def inRadius(latmin,longmin,latmax,longmax,radius):
  data = getData()
  matched = []
  for line in data[1:]:
    if latmax>float(line['LATITUDE']) > latmin and longmax> float(line['LONGITUDE']) > longmin and line['VALIDATED']=="APPROVED!":
      matched.append(line)
  return matched

def nearestTen(lat,long):
  matched = []
  squareSize = 0
  while len(matched)<11 and squareSize < 2:
    squareSize += 0.1 
    
    matched = inRadius(
      lat-squareSize,
      long-squareSize,
      lat+squareSize,
      long+squareSize,
      squareSize)
  if matched == []:
    return False
  return matched

def getNearest(lat,long):
  matched = []
  distances = []

  data = getData()

  for line in data[1:]:
    matched.append(line)
    pointLong = float(line['LONGITUDE'])
    pointLat = float(line['LATITUDE'])
    distances.append(distance((lat,long),(pointLat,pointLong)))

  matched = sort_list(matched,distances)
  matched = matched[0]
  distances.sort()
  
  return [(matched['LATITUDE'],matched['LONGITUDE']),distances[0]]
    
#home
@app.route('/')
def index():
  return render_template('index.html')

#nearest AEDs
@app.route("/nearme", methods=('GET', "POST"))
def nearme():
  if request.method == "POST":
    location = request.form['location']
    location = location.split(",")
    try:
      lat = float(location[0])
      long=float(location[1])
    except:
      return render_template('AED ERROR.html')
    nearest = nearestTen(lat,long)
    distances = []
    for line in nearest:
      pointLong = float(line['LONGITUDE'])
      pointLat = float(line['LATITUDE'])
      distances.append(distance((lat,long),(pointLat,pointLong)))

    nearest = sort_list(nearest,distances) 
    header = getData()[0]
    return render_template('aedNearMeResponse.html',
                         len=len(nearest),
                         header=header,
                         Hlen=len(header),
                         lines=nearest,
                        )
  
  return render_template("aedsNearMe.html")

  
#accept new AED's
@app.route('/addPoint/', methods=('GET', 'POST'))
def addPoint():
  if request.method == 'POST':
    # check if the post request has the file part
    if 'pic' not in request.files:
      flash('No file part')
      return redirect(request.url)
    file = request.files['pic']
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
      flash('No selected file')
      return redirect(request.url)
    if file and allowed_file(file.filename):
      with open(LASTNAME_PATH, "r") as lastName:
        newNameNum = int(lastName.read()) + 1
        filename = f"{newNameNum}.{extension(file.filename)}"
      with open(LASTNAME_PATH, "w") as lastName:
        lastName.write(str(newNameNum))
      with open('locations.csv', "a") as data:
        location = request.form['location']
        if location == '':
          flash('location failed to upload')
          return redirect(request.url)
        comments = request.form['comments']
        lat = location.split(',')[0]
        long = location.split(',')[1]
        baseDic = {
          'LATITUDE':lat,
          'LONGITUDE':long,
          'ADDRESS':getAddress(lat,long),
          'FILENAME':app.config['UPLOAD_FOLDER'] + "/" + filename,
          'COMMENTS':comments,
          'DATE':str(datetime.datetime.today().strftime('%Y-%m-%d')),
          'VALIDATED':"NOT REVIEWED"
        }
        dataBaseWrite = dataBaseString(baseDic)
        data.write(dataBaseWrite)
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
  return render_template('addPoint.html')

#provide method to confirm validity of images
@app.route('/confirm/', methods=('GET', 'POST'))
def confirm():
  data = getData()
  #get random sampling of the data in the sheet
  dataSize = len(data)
  print(dataSize)
  lines = []
  indexes = []
  newRandom = 1
  i = 0
 # print(data[5])
  while newRandom < dataSize and i < 10:
    #print(newRandom,data[newRandom])
    if data[newRandom]['VALIDATED'] == "NOT REVIEWED":
      indexes.append(newRandom)
      lines.append(data[newRandom])
      i += 1
    newRandom += 1
  if request.method == 'POST':
    data = getData()
    for i in range(len(indexes)):
      valid = request.form[f'aproved?{i}'] == 'Approved'
      if valid:
        data[indexes[i]]["VALIDATED"] = "APPROVED!"
      else:
        data[indexes[i]]["VALIDATED"] = "REJECTED!"
        

    rewrite = ""
    for line in data:
      dataBase = dataBaseString(line)
      rewrite += dataBase
    with open('locations.csv', "w") as dataFile:
      dataFile.write(rewrite)
    return redirect('/confirm')
  return render_template('confirm.html',
                         len=len(lines),
                         header=data[0].keys(),
                         Hlen=len(data[0].keys()),
                         lines=lines)

#respond to image requests
@app.route('/confirm/aeds/<filename>', methods=('GET', 'POST'))
def sendImage(filename):
  if request.method == 'GET':
    return send_file(fr'aeds/{filename}', mimetype='image/gif')

#AED use and how to use website instructions
@app.route('/instructions', methods=('GET', 'POST'))
def instructions():
  return render_template('instructions.html')

#display all data in database and give methods to filter.
@app.route('/allSubmissions', methods=('GET', 'POST'))
def allSubmissions():
  data = getData()
  header=data[0].keys()
  lines = data[1:]
  address = True
  latLong = True
  if request.method == "POST":
    try:
      reviewed = request.form['aprovalStatus']
      dataSize = len(data)
      lines = []
      i = 0
      while i < dataSize:
        if data[i]['VALIDATED'] == reviewed:
          lines.append(data[i])
        i += 1
    except:
      pass
    try:
      if request.form['latlong'] == "TRUE":
        latLong = True
    except:
      latLong=False
    try:
      if request.form['ADDRESS'] == "TRUE":
        address = True
    except:
      address=False
    return render_template('allSub.html',
                         len=len(lines),
                         header=header,
                         Hlen=len(header),
                         lines=lines,
                         latLong=latLong,
                         address=address
                        )
  return render_template('allSub.html',
                         len=len(lines),
                         header=header,
                         Hlen=len(header),
                         lines=lines,
                         latLong=latLong,
                         address=address
                        )

#respond to image requests
@app.route('/aeds/<filename>', methods=('GET', 'POST'))
def allSubSend(filename):
  if request.method == 'GET':
    print(filename)
    return send_file(fr'aeds/{filename}', mimetype='image/gif')

#about us
@app.route('/about', methods=('GET', "POST"))
def about_us():
  return render_template('aboutus.html')
#this will have cpr instructions
@app.route('/cpr', methods=('GET', "POST"))
def cpr():
  return render_template('cprBeat.html')

#This function displays the valid points on the map with a picture in each popup.
@app.route('/tmap',methods=('GET','POST'))
def omap():
  if request.method == "POST":
    location = request.form['location']
    location = location.split(",")
    try:
      lat = float(location[0])
      long=float(location[1])
    except:
      lat = 40
      long = -70
    
    data = getData()
    markers = []
    for line in data:
      if "APPROVED!" == line['VALIDATED']:
        markers.append(
          {'lat':line['LATITUDE'],
           'lon':line['LONGITUDE'],
           'address':line['ADDRESS'],
           'comments':line['COMMENTS'],
           'img':line['FILENAME']
          }
        )

    nearest = getNearest(lat,long)
    if nearest[1]*1000 < 430*2:
      route = getRoute((lat,long),nearest[0])
    else:
      route = ""
    return render_template('openviewmap.html',markers=markers,route=route)

  return render_template("aedsNearMe.html")

@app.route('/emergencymap',methods=('GET','POST'))
def omapInCircle():
  if request.method == "POST":
    location = request.form['location']
    location = location.split(",")
    try:
      lat = float(location[0])
      long=float(location[1])
    except:
      lat = 40
      long = -70
    
    data = getData()
    markers = []
    for line in data:
      if "APPROVED!" == line['VALIDATED'] and distance((lat,long),(float(line['LATITUDE']),float(line['LONGITUDE']))) * 1000 < 500*2:
        markers.append(
          {'lat':line['LATITUDE'],
           'lon':line['LONGITUDE'],
           'address':line['ADDRESS'],
        'comments':line['COMMENTS'],
           'img':line['FILENAME']
          }
        )

    nearest = getNearest(lat,long)
    if nearest[1]*1000 < 430*2:
      route = getRoute((lat,long),nearest[0])
    else:
      route = ""
    return render_template('openviewmap.html',markers=markers,route=route)

  return render_template("aedsNearMe.html")

@app.route('/awake')
def awake():
  return "Awake"
@app.route('/api/lat=<lat>&lng=<lng>&r=<r>&format=<format>')
#aed-map.abelbellows.repl.co/api/lat=40&lng=-70&r=4000000a0=json
def api(lat,lng,r,format):
  try:
    lat =float(lat)
    long=float(lng)
    r=float(r)
  except:
    
    return f"Server Error: could not parse {[r,lat,lng]} as float" 
  if not (-90 <= lat <= 90):
    return f"Lat value of {lat} is out of range [-90->90]"
  if not (-180 <= long <= 180):
    return f"Lng of {lng} is out of range [-180->180]"

  
  
  
  
  data = getData()
  markers = []
  for line in data:
      if "APPROVED!" == line['VALIDATED'] and distance((lat,long),(float(line['LATITUDE']),float(line['LONGITUDE']))) * 1000 < r:
        markers.append(
          {'lat':line['LATITUDE'],
           'lon':line['LONGITUDE'],
           'address':line['ADDRESS'],
        'comments':line['COMMENTS'],
           'img':line['FILENAME']
          }
        )
  if format=="json":
    return json.dumps(markers)
  if format=="text":
    return markers

@app.route("/apiReasorces",methods=("GET","POST"))
def apiReasorces():
  return render_template('api.html')
app.run(host='0.0.0.0', port=81, debug=True)