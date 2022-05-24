from flask import Flask
from flask_restx import Api, Resource, reqparse
from herepy import GeocoderApi
import os
import json
import requests

API_TOKEN = os.environ["API_TOKEN"]
HERE_API_KEY = os.environ["HERE_API_KEY"]
geocoder_api = GeocoderApi(api_key=HERE_API_KEY)


with open("municipalities.geojson.json") as f:
    geodata = json.loads(f.read())
temp = geodata["features"]
sofia_geoshape = [t for t in temp if "SOF" in t["properties"]["nuts4"]]

app = Flask(__name__)
api = Api(app)


def validate_token(token):
    return token == API_TOKEN
    

@api.route('/geolocate')
@api.doc(
    responses={200: "OK", 404: "Not found",
               400: "Bad request", 403: "Invalid token"},
    params={
        "address": "Name to look for lookup an address",
        "token": "token api key"
    },
    headers = {"api-key": "api key of"},
    description="""With this API endpoint you can search for addresses by entering a query string corresponding to the address 
                (for e.g. гр. София, УЛ.ВЛАДИМИР МИНКОВ-ЛОТКОВ бл./№ 023.)
                """
)
class GeolocateAddress(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('address', type=str, help='variable 1', location='args')
        parser.add_argument('token', type=str, help='variable 2', location='args')
        args = parser.parse_args()
        name = args["address"]
        token = args["token"]
        if (not validate_token(token)):
            return {"Error": "Invalid Token"}, 403
        try:    
            response = geocoder_api.free_form(name)
        except Exception as e:
            return {"Error": str(e)}, 400
        results = response.as_dict()
        geo_obj_debug = {} 
        geo_obj_debug["type"] = "FeatureCollection"
        geo_obj_debug["features"] = []
        geo_obj_debug["features"].append(sofia_geoshape[0])
        for result in results["items"]:
            (lat, lng) = (result["position"]["lat"], result["position"]["lng"])
            geo_obj_debug["features"].append({
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        lng,
                        lat
                    ]
                }
            })
        results["debug"] = geo_obj_debug
        return results    


@api.route('/route')
@api.doc(
    responses={200: "OK", 404: "Not found",
               400: "Bad request", 403: "Invalid token"},
    params={
        "pointA": "Geocoords of point A (use oder lat,lng separeted to comma for e.g. 42.68843,23.37989)",
        "pointB": "Geocoords of point B (use order lat,lng separated to comma for e.g.  42.70211,23.33198)"
    },
    description='Compute path from point A to point B in pedestrian mode',
)
class Routing(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('pointA', type=str, help='variable 1', location='args')
        parser.add_argument('pointB', type=str, help='variable 2', location='args')
        parser.add_argument('token', type=str, help='variable 3', location='args')
        args = parser.parse_args()
        pointA = args["pointA"]
        pointB = args["pointB"]
        token = args["token"]
        if (not validate_token(token)):
            return {"Error": "Invalid Token"}, 403
        query = {
            "transportMode": "pedestrian", 
            "origin": pointA, 
            "destination": pointB, 
            "return": "summary", 
            "apiKey": HERE_API_KEY
        }
        try:
            result = requests.get("https://router.hereapi.com/v8/routes", params=query)
        except Exception as e:   
            return {"Error": str(e)}, 400 
        return result.json()

if __name__ == '__main__':
    app.run(debug=True)
