#THIS API WAS WRITTEN BE ABEL BELLOWS
#MODDIFYING THE CODE BEYOND THIS IS PROHIBITED
#UPDATES MAY BE ISSUED PERIODICALLY
#©2023 
import requests
import json
class ApiRequest:
  def __init__(self):
    self.response = False
    self.error = False
    self.errorText = False
    alive = False
    while not alive: 
      x = requests.get("https://aed-map.abelbellows.repl.co/awake").text
      alive = x == "Awake"   
  def request(self,lat,lng,r,format):
    self.lat = lat
    self.lng = lng
    self.r = r
    self.format = format
    url = f"https://aed-map.abelbellows.repl.co/api/lat={self.lat}&lng={self.lng}&r={self.r}&format={self.format}"
    self.response = requests.get(url).text
    try:
      self.response = json.loads(self.response)
    except:
      self.error = True
      self.errorText = self.response
    return self.response