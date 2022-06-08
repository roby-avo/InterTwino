from flask import Flask, request
from flask_restx import Api, Resource, reqparse, fields
from herepy import GeocoderApi
from pymongo import MongoClient
import os
import json
import requests

API_TOKEN = os.environ["API_TOKEN"]
HERE_API_KEY = os.environ["HERE_API_KEY"]
geocoder_api = GeocoderApi(api_key=HERE_API_KEY)

MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_USER = os.environ["MONGO_USER"]
MONGO_PASSWORD = os.environ["MONGO_PASSWORD"]
MONGO_DBNAME = os.environ["MONGO_DBNAME"]
client = MongoClient(MONGO_HOST,
                     username=MONGO_USER,
                     password=MONGO_PASSWORD,
                     authSource='admin',
                     authMechanism='SCRAM-SHA-256')
address_cache = client[MONGO_DBNAME].address            
route_cache = client[MONGO_DBNAME].route                  



with open("municipalities.geojson.json") as f:
    geodata = json.loads(f.read())
temp = geodata["features"]
sofia_geoshape = [t for t in temp if "SOF" in t["properties"]["nuts4"]]


app = Flask(__name__)
api = Api(app)


def validate_token(token):
    return token == API_TOKEN
    

def get_address(address):
    address = address.lower()
    result = address_cache.find_one({"address": address})
    return result


address_fields = api.model('Address', {
    'address': fields.String,
})

address_list_fields = api.model('AddressList', {
    'json': fields.List(
        fields.Nested(address_fields), 
        example=[
            {"address": "гр. София, УЛ.ВЛАДИМИР МИНКОВ-ЛОТКОВ бл./№ 023"},
            {"address": "гр. София, Ж.К.ХИПОДРУМА бл./№ 038"}
        ])
})

@api.route('/geocoords')
@api.doc(
    responses={200: "OK", 404: "Not found",
               400: "Bad request", 403: "Invalid token"},
    params={ "token": "token api key"}
)
class GeolocateAddress(Resource):

    def lookup_address(self, address):
        try:    
            response = geocoder_api.free_form(address)
            results = response.as_dict()
            address_cache.insert_one({
                "address": address.lower(),
                "items": results["items"]
            })
        except Exception as e:
            return {"Error": str(e)}, 400
        return results
    
    def init_geo_obj_debug(self):
        geo_obj_debug = {}
        geo_obj_debug["type"] = "FeatureCollection"
        geo_obj_debug["features"] = []
        geo_obj_debug["features"].append(sofia_geoshape[0])
        return geo_obj_debug

    def populate_debug(self, results, geo_obj_debug):
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
        
    @api.doc(
        params={
            "address": "Name to look for lookup an address"
        },
        description="""With this API endpoint you can search for address by entering a query string corresponding to the address 
                    (for e.g. гр. София, УЛ.ВЛАДИМИР МИНКОВ-ЛОТКОВ бл./№ 023.)
                    """
    )
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('address', type=str, help='variable 1', location='args')
        parser.add_argument('token', type=str, help='variable 2', location='args')
        args = parser.parse_args()
        name = args["address"]
        token = args["token"]
        if not validate_token(token):
            return {"Error": "Invalid Token"}, 403
        result = get_address(name)
        if result is None:    
            result = self.lookup_address(name)
        else:
            result = result["items"]    
        geo_obj_debug = self.init_geo_obj_debug()
        self.populate_debug(result, geo_obj_debug)
        result["debug"] = geo_obj_debug
        return result    


    @api.doc(
        body = address_list_fields,
        description="""With this API endpoint you can search for addresses by entering a json array of object 
                    that contains strings corresponding  the address  
                    (for e.g. [{"address":"гр. София, УЛ.ВЛАДИМИР МИНКОВ-ЛОТКОВ бл./№ 023.", {"address":"..."}, ...])
                    """
    )
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('token', type=str, help='variable 1', location='args')
        args = parser.parse_args()
        token = args["token"]
        if not validate_token(token):
            return {"Error": "Invalid Token"}, 403
        try:
            addresses = request.get_json()['json']
        except:
            return {"Error": "Invalid Token"}, 400
        geo_obj_debug = self.init_geo_obj_debug()      
        for address in addresses:
            result = self.lookup_address(address["address"])
            address["items"] = result["items"]
            self.populate_debug(result, geo_obj_debug)
        out = {
            "result": addresses,
            "debug": geo_obj_debug
        }    
        return out


routes_fields = api.model('Route', {
    'origin': fields.List(fields.Float),
    'destination': fields.List(fields.Float)
})

routes_list_fields = api.model('RouteList', {
    'json': fields.List(
        fields.Nested(routes_fields), 
        example=[
            {"origin": [42.68843, 23.37989], "destination": [42.70211, 23.33198]}
        ])
})


@api.route('/route')
@api.doc(
    responses={200: "OK", 404: "Not found",
               400: "Bad request", 403: "Invalid token"},
    params={
        "token": "token api key"
    }
)
class Routing(Resource):

    def get_route(self, origin, destination):
        query = {
            "transportMode": "pedestrian", 
            "origin": origin, 
            "destination": destination, 
            "return": "summary", 
            "apiKey": HERE_API_KEY
        }
        try:
            result = requests.get("https://router.hereapi.com/v8/routes", params=query)
        except Exception as e:   
            return {"Error": str(e)}, 400 
        
        return result.json()    

    @api.doc(
        params={
            "pointA": "Geocoords of point A (use oder lat,lng separeted to comma for e.g. 42.68843,23.37989)",
            "pointB": "Geocoords of point B (use order lat,lng separated to comma for e.g.  42.70211,23.33198)"
        },
        description='Compute path from point A to point B in pedestrian mode'
    )
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('pointA', type=str, help='variable 1', location='args')
        parser.add_argument('pointB', type=str, help='variable 2', location='args')
        parser.add_argument('token', type=str, help='variable 3', location='args')
        args = parser.parse_args()
        pointA = args["pointA"]
        pointB = args["pointB"]
        token = args["token"]
        if not validate_token(token):
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

    @api.doc(
        body=routes_list_fields,
        description='Compute path from point A to point B in pedestrian mode'
    )
    def post(self):
        pass


if __name__ == '__main__':
    app.run(debug=True)
