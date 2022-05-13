from flask import Flask
from flask_restx import Resource, Api
from herepy import GeocoderApi

geocoder_api = GeocoderApi(api_key="")


app = Flask(__name__)
api = Api(app)

@api.route('/geocode')
class GeoData(Resource):
    def get(self):
        # geocodes given search text
        response = geocoder_api.free_form("street")
        return response.as_dict()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)