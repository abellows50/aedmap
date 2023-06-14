import hashlib
import sys
PASSWORD = sys.argv[1]
with open('pass.txt','w') as outDoc:
  outDoc.write(hashlib.sha512(PASSWORD.encode()).hexdigest())

