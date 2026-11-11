import sqlite3,sys,json
c=sqlite3.connect('/Volumes/Expansion/Development/Build/living-spaces-r1/home/plugin-data/living-spaces/spaces.db',timeout=10)
c.execute('pragma query_only=1')
for r in c.execute("select collection,id,rev,data from records where space=? order by collection,id",(sys.argv[1],)):
    d=r[3]; print(r[0],r[1],r[2],(d[:int(sys.argv[2]) if len(sys.argv)>2 else 200]))
